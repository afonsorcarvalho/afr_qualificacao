# Opcionais Aceitos — Fase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** Opcional na cotação só conta (total/fatura/geração) se aceito; opcional aceito com `qualification_type` gera qualificação + OS no confirm.

**Architecture:** Dois campos novos em `sale.order.line` (`optional_accepted`, `optional_qty`) + regra `product_uom_qty = optional_qty se aceito senão 0` (reusa padrão `part01_declined`, via onchange + helper `_sync_optional_qty`). `action_confirm` sincroniza e inclui opcionais aceitos com `qualification_type` na geração. Toggle no form. Zero override de `_compute_amount`.

**Tech Stack:** Odoo 16, Python. afr_qualificacao é **submodule** (repo github.com/afonsorcarvalho/afr_qualificacao.git, branch main). Testes herdam de `AfrQualificacaoTestCommon` (tests/common.py — fixtures: `self.partner`, `self.equip1`, `self.cycle_cmax`, `self.category`).

---

## File Map

| Ficheiro | Mudança |
|---|---|
| `models/sale_order_line.py` | campos `optional_accepted`/`optional_qty` + onchange `_onchange_optional_sync_qty` + helper `_sync_optional_qty` + ajuste constraint |
| `models/sale_order.py` | `action_confirm` chama sync; `_create_qualificacoes_from_lines` inclui opcionais aceitos c/ qualification_type |
| `views/sale_order_views.xml` | colunas `optional_qty` + `optional_accepted` no tree de order_line |
| `tests/test_optional_accepted.py` | **novo** — 6 testes |
| `__manifest__.py` | version bump |

---

## Task 1: Campos + sync de quantidade (TDD)

**Files:**
- Modify: `models/sale_order_line.py`
- Test: `tests/test_optional_accepted.py` (novo)

- [ ] **Step 1: Escrever testes do sync de qty**

Create `tests/test_optional_accepted.py`:
```python
# -*- coding: utf-8 -*-
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestOptionalAccepted(AfrQualificacaoTestCommon):

    def _svc(self):
        return self.env["product.product"].create(
            {"name": "Pasta", "type": "service", "sale_ok": True,
             "list_price": 150.0})

    def _opt_line(self, so, accepted=False, qty=1.0, price=150.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self._svc().id,
            "name": "Opcional Pasta",
            "is_proposal_optional": True,
            "optional_accepted": accepted,
            "optional_qty": qty,
            "price_unit": price,
        })

    def test_optional_not_accepted_qty_zero(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self._opt_line(so, accepted=False, qty=2.0)
        line._sync_optional_qty()
        self.assertEqual(line.product_uom_qty, 0.0)
        self.assertEqual(so.amount_untaxed, 0.0)

    def test_optional_accepted_sums(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self._opt_line(so, accepted=True, qty=2.0, price=150.0)
        line._sync_optional_qty()
        self.assertEqual(line.product_uom_qty, 2.0)
        self.assertEqual(so.amount_untaxed, 300.0)
```

- [ ] **Step 2: Rodar → FAIL** (campos/helper não existem). Via test-runner, tags `/afr_qualificacao:TestOptionalAccepted`. Expected: FAIL (AttributeError optional_accepted / _sync_optional_qty).

- [ ] **Step 3: Implementar campos + onchange + helper**

Em `models/sale_order_line.py`, após a definição de `part01_declined` (campo, ~linha 115, antes do `@api.onchange("qualif_cycle_qty"...)`), adicionar:
```python
    optional_accepted = fields.Boolean(
        string="Opcional Aceito",
        default=False,
        copy=True,
        help="Opcional autorizado pelo cliente. Quando aceito, soma ao total, "
             "vai à fatura e — se for qualificação — gera afr.qualificacao + OS.",
    )
    optional_qty = fields.Float(
        string="Qtd. do Opcional",
        default=1.0,
        copy=True,
        help="Quantidade pretendida do opcional. Guardada enquanto não aceito "
             "(product_uom_qty fica 0); aplicada quando aceito.",
    )

    @api.onchange("optional_accepted", "optional_qty", "is_proposal_optional")
    def _onchange_optional_sync_qty(self):
        """Linha opcional: qty efetiva = optional_qty se aceito, senão 0."""
        for line in self:
            if not line.is_proposal_optional:
                continue
            line.product_uom_qty = (
                line.optional_qty if line.optional_accepted else 0.0)

    def _sync_optional_qty(self):
        """Aplica a regra de qty dos opcionais (chamável fora de onchange)."""
        for line in self:
            if not line.is_proposal_optional:
                continue
            target = line.optional_qty if line.optional_accepted else 0.0
            if line.product_uom_qty != target:
                line.product_uom_qty = target
        return True
```

> Confirmar que `api` está importado no topo (`from odoo import ... api ...`). Já está (onchange existente usa `@api.onchange`).

- [ ] **Step 4: Rodar → PASS** (2 testes). 

- [ ] **Step 5: NÃO commitar.**

---

## Task 2: Confirm gera opcionais aceitos + constraint (TDD)

**Files:**
- Modify: `models/sale_order.py` (`action_confirm` + `_create_qualificacoes_from_lines`)
- Modify: `models/sale_order_line.py` (constraint `_check_qualificacao_consistency`)
- Test: `tests/test_optional_accepted.py` (adicionar)

- [ ] **Step 1: Escrever testes de confirm + constraint**

Adicionar à classe `TestOptionalAccepted`:
```python
    def _opt_qualif_line(self, so, accepted, qtype="performance"):
        # opcional que É qualificação (gera no confirm se aceito)
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo opcional",
            "is_qualificacao_managed": True,
            "is_proposal_optional": True,
            "optional_accepted": accepted,
            "optional_qty": 1.0,
            "qualification_type": qtype,
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 1,
        })

    def test_confirm_optional_service_no_qualif(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self._opt_line(so, accepted=True, qty=1.0)
        so.action_confirm()
        self.assertGreater(line.product_uom_qty, 0.0)
        self.assertFalse(so.qualificacao_ids)

    def test_confirm_optional_qualif_generates(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self._opt_qualif_line(so, accepted=True)
        so.action_confirm()
        self.assertTrue(so.qualificacao_ids)
        self.assertTrue(so.qualificacao_os_ids)

    def test_confirm_optional_not_accepted_skipped(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self._opt_qualif_line(so, accepted=False)
        so.action_confirm()
        self.assertFalse(so.qualificacao_ids)

    def test_constraint_optional_qualif_requires_equipment(self):
        from odoo.exceptions import ValidationError
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        with self.assertRaises(ValidationError):
            self.env["sale.order.line"].create({
                "order_id": so.id,
                "product_id": self.cycle_cmax.product_id.id,
                "name": "Ciclo opcional sem equip",
                "is_qualificacao_managed": True,
                "is_proposal_optional": True,
                "optional_accepted": True,
                "qualification_type": "performance",
                "cycle_type_id": self.cycle_cmax.id,
                # equipment_id ausente → deve falhar
            })
```

> Nota: `qualificacao_os_ids` é o O2M de OS no sale.order (confirmar o nome real lendo sale_order.py — pode ser `qualificacao_os_ids` ou `engc_os_ids`; usar o que existir para a asserção de OS). Se o nome diferir, ajustar a asserção em `test_confirm_optional_qualif_generates`.

- [ ] **Step 2: Rodar → FAIL** (opcional não gera hoje; constraint pula opcional).

- [ ] **Step 3: Implementar — confirm**

Em `models/sale_order.py`, `action_confirm` (linha 942):
```python
    def action_confirm(self):
        """Override: após confirmar SO, gera estrutura de qualificações."""
        for order in self:
            order.order_line._sync_optional_qty()
        result = super().action_confirm()
        for order in self:
            order._create_qualificacoes_from_lines()
        return result
```

No `_create_qualificacoes_from_lines`, o filtro `managed` (~linha 957):
```python
        managed = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and not l.display_type
            and not l.is_proposal_optional
            and not l.part01_declined
        )
```
Substituir por:
```python
        managed = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and not l.display_type
            and not l.part01_declined
            and not (l.is_proposal_optional and not l.optional_accepted)
            and not (l.is_proposal_optional and not l.qualification_type)
        )
```
> LER o filtro exato antes de substituir (o texto pode ter espaçamento diferente).

- [ ] **Step 4: Implementar — constraint**

Em `models/sale_order_line.py`, `_check_qualificacao_consistency` (~linha 204-207), substituir:
```python
            # Serviço opcional (F8.2): linha managed sem equipamento/tipo —
            # não é linha de qualificação, pular consistência.
            if line.is_proposal_optional:
                continue
```
por:
```python
            # Opcional de SERVIÇO (sem qualification_type) — não é linha de
            # qualificação, pula consistência. Opcional de QUALIFICAÇÃO
            # (com qualification_type) segue as regras normais abaixo.
            if line.is_proposal_optional and not line.qualification_type:
                continue
```

- [ ] **Step 5: Rodar → PASS** (6 testes no total da classe).

- [ ] **Step 6: NÃO commitar.**

---

## Task 3: Toggle no form

**Files:**
- Modify: `views/sale_order_views.xml`

- [ ] **Step 1: Adicionar colunas ao tree de order_line**

Localizar (view de sale.order, no xpath do tree de order_line):
```xml
                <field name="is_proposal_optional" string="Opcional" optional="show" widget="boolean_toggle"/>
```
Substituir por:
```xml
                <field name="is_proposal_optional" string="Opcional" optional="show" widget="boolean_toggle"/>
                <field name="optional_qty" string="Qtd Opc."
                       attrs="{'invisible': [('is_proposal_optional', '=', False)]}"
                       optional="show"/>
                <field name="optional_accepted" string="Aceito"
                       attrs="{'invisible': [('is_proposal_optional', '=', False)]}"
                       widget="boolean_toggle" optional="show"/>
```

- [ ] **Step 2: Validar XML**
`cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao && python3 -c "import xml.dom.minidom as m; m.parse('views/sale_order_views.xml'); print('OK')"`

- [ ] **Step 3: NÃO commitar.**

---

## Task 4: Version bump + suite + commit

**Files:**
- Modify: `__manifest__.py`

- [ ] **Step 1: Version bump**

Em `__manifest__.py`, `version` atual `16.0.5.11.0` → `16.0.5.12.0`.

- [ ] **Step 2: Atualizar módulo + suite completa**

Via test-runner: `-u afr_qualificacao` + suite completa. Confirmar:
- 6 testes novos (TestOptionalAccepted) PASS
- 0 regressões novas (3 falhas pré-existentes conhecidas: TestProposalReport CSS×2, TestResourcePlan poluição — aceitáveis)

- [ ] **Step 3: Commit submodule + bump pointer**

Via git-commit-push, cwd = `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`. Push origin main. Mensagem:
```
feat(qualif): opcional só conta se aceito + gera qualif/OS (Fase 1)

optional_accepted + optional_qty em sale.order.line; qty=0 até aceito (não
soma ao total); confirm inclui opcionais aceitos com qualification_type
gerando afr.qualificacao + OS; toggle Aceito/Qtd no form. v16.0.5.12.0.
6 testes. Fase 1 de 4 (wizard/PDF/portal seguem).
```
Depois, cwd = `/home/afonso/docker/odoo_engenapp`: `git add addons/afr_qualificacao`, commit `chore: bump afr_qualificacao (opcionais aceitos fase 1)`, push origin main-monorepo.

---

## Manual Test Checklist (pós-merge, opcional)
| Cenário | Esperado |
|---|---|
| Linha opcional não aceita | qty=0, não soma ao total |
| Ligar "Aceito" no form | qty volta a optional_qty, soma ao total |
| Confirmar c/ opcional-serviço aceito | fatura, sem qualif |
| Confirmar c/ opcional-qualif aceito | gera afr.qualificacao + OS |
| Confirmar c/ opcional não aceito | nada gerado, linha fica qty=0 referência |
