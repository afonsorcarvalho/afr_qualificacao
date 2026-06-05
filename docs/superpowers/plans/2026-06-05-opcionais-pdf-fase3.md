# Opcionais no PDF/Portal — Fase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. Código completo dos blocos de template na spec `docs/superpowers/specs/2026-06-05-opcionais-pdf-fase3-design.md` — ler antes de cada task.

**Goal:** PDF e portal mostram opcionais com preço de referência + caixa ☑/☐ (autorizado), claramente fora do total (que já exclui não-aceitos).

**Architecture:** Campo computed `optional_ref_subtotal` em `sale.order.line` (preço de referência = price_unit × qty-se-aceito, via `_optional_full_qty()`). 3 templates (PDF block_optionals, portal, snapshot _html_optionals) usam optional_qty + optional_ref_subtotal + ☑/☐.

**Tech Stack:** Odoo 16, Python, QWeb. afr_qualificacao é **submodule** (branch main). Testes herdam `AfrQualificacaoTestCommon`. DB teste odoo_ecm_test.

---

## File Map

| Ficheiro | Mudança |
|---|---|
| `models/sale_order_line.py` | `_optional_full_qty()` extraído; `_optional_target_qty` usa-o; campo computed `optional_ref_subtotal` |
| `reports/templates_blocos/block_optionals.xml` | caixa ☑/☐, Qtd=optional_qty, Subtotal=optional_ref_subtotal, nota |
| `views/sale_order_portal_template.xml` | idem no bloco optionals |
| `models/proposal_block.py` | `_html_optionals` espelha |
| `tests/test_optional_ref_subtotal.py` | **novo** — 4 testes |
| `__manifest__.py` | version bump |

---

## Task 1: Campo optional_ref_subtotal (TDD)

**Files:** `models/sale_order_line.py`, `tests/test_optional_ref_subtotal.py` (novo)

- [ ] **Step 1: Escrever os 4 testes**

Create `tests/test_optional_ref_subtotal.py`:
```python
# -*- coding: utf-8 -*-
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestOptionalRefSubtotal(AfrQualificacaoTestCommon):

    def _svc(self):
        return self.env["product.product"].create(
            {"name": "Pasta", "type": "service", "sale_ok": True,
             "list_price": 150.0})

    def test_ref_subtotal_service_not_accepted(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id, "name": "Opt",
            "is_proposal_optional": True, "optional_accepted": False,
            "optional_qty": 2.0, "price_unit": 150.0})
        line._sync_optional_qty()
        self.assertEqual(line.product_uom_qty, 0.0)
        self.assertEqual(line.optional_ref_subtotal, 300.0)

    def test_ref_subtotal_service_accepted(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id, "name": "Opt",
            "is_proposal_optional": True, "optional_accepted": True,
            "optional_qty": 2.0, "price_unit": 150.0})
        line._sync_optional_qty()
        self.assertEqual(line.optional_ref_subtotal, 300.0)
        self.assertEqual(line.price_subtotal, 300.0)

    def test_ref_subtotal_cycle(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo opt", "is_qualificacao_managed": True,
            "is_proposal_optional": True, "optional_accepted": False,
            "qualification_type": "performance", "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id, "qualif_cycle_qty": 3,
            "estimated_hours": 2.0, "price_unit": 100.0})
        self.assertEqual(line.optional_ref_subtotal, 600.0)

    def test_ref_subtotal_non_optional_zero(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id, "name": "Normal",
            "product_uom_qty": 1.0, "price_unit": 150.0})
        self.assertEqual(line.optional_ref_subtotal, 0.0)
```
Registar `from . import test_optional_ref_subtotal` em `tests/__init__.py`.

- [ ] **Step 2: Rodar → FAIL** (campo não existe). test-runner tags `/afr_qualificacao:TestOptionalRefSubtotal`.

- [ ] **Step 3: Refatorar _optional_target_qty + campo computed**

Em `models/sale_order_line.py`, localizar `_optional_target_qty` (Fase 1, ~linha 141-152). Substituir o método por:
```python
    def _optional_full_qty(self):
        """Qty de uma linha opcional SE aceita (ignora o estado aceito):
        ciclo/malha → qualif_cycle_qty × estimated_hours; serviço → optional_qty."""
        self.ensure_one()
        if self.cycle_type_id or self.malha_type_id:
            return (self.qualif_cycle_qty or 0) * (self.estimated_hours or 0.0)
        return self.optional_qty

    def _optional_target_qty(self):
        """Qty efetiva: 0 se não aceito, senão a qty cheia."""
        self.ensure_one()
        return self._optional_full_qty() if self.optional_accepted else 0.0
```
> LER o método atual antes de substituir (match exato). NÃO alterar `_sync_optional_qty` nem `_onchange_optional_sync_qty` (continuam a chamar `_optional_target_qty`).

Adicionar o campo + compute (perto dos outros campos opcionais):
```python
    optional_ref_subtotal = fields.Monetary(
        string="Subtotal Referência",
        compute="_compute_optional_ref_subtotal",
        currency_field="currency_id",
        help="Preço de referência do opcional (preço unit. × qtd pretendida), "
             "mostrado na proposta mesmo quando ainda não aceito.",
    )

    @api.depends("is_proposal_optional", "price_unit", "optional_qty",
                 "qualif_cycle_qty", "estimated_hours", "cycle_type_id",
                 "malha_type_id")
    def _compute_optional_ref_subtotal(self):
        for line in self:
            if line.is_proposal_optional:
                line.optional_ref_subtotal = (
                    line.price_unit * line._optional_full_qty())
            else:
                line.optional_ref_subtotal = 0.0
```
> `currency_id` já existe em sale.order.line (Odoo nativo). `fields`/`api` importados.

- [ ] **Step 4: Rodar → PASS** (4 testes). `-u afr_qualificacao` + tags.

- [ ] **Step 5: NÃO commitar.**

---

## Task 2: Template PDF block_optionals

**Files:** `reports/templates_blocos/block_optionals.xml`

- [ ] **Step 1: Substituir a tabela**

Substituir o bloco `<table class="qq-table">...</table>` por (e adicionar a nota `<p>` depois) — CÓDIGO COMPLETO na spec secção 2 (copiar verbatim).

- [ ] **Step 2: Validar XML**
`cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao && python3 -c "import xml.dom.minidom as m; m.parse('reports/templates_blocos/block_optionals.xml'); print('OK')"`

- [ ] **Step 3: NÃO commitar.**

---

## Task 3: Template Portal + snapshot _html_optionals

**Files:** `views/sale_order_portal_template.xml`, `models/proposal_block.py`

- [ ] **Step 1: Portal**

No bloco `block_kind == 'optionals'` (linhas ~461-502), substituir `<thead>` e `<tbody>` por (e adicionar nota após a tabela) — CÓDIGO COMPLETO na spec secção 3.

- [ ] **Step 2: Snapshot**

Substituir `_html_optionals` em `models/proposal_block.py` — CÓDIGO COMPLETO na spec secção 4.

- [ ] **Step 3: Validar**
`python3 -c "import xml.dom.minidom as m; m.parse('views/sale_order_portal_template.xml'); print('xml OK')" && python3 -c "import ast; ast.parse(open('models/proposal_block.py').read()); print('py OK')"`

- [ ] **Step 4: NÃO commitar.**

---

## Task 4: Bump + suite + commit

**Files:** `__manifest__.py`

- [ ] **Step 1: Version bump** `16.0.5.13.0` → `16.0.5.14.0`.

- [ ] **Step 2: Update + suite completa** (test-runner, `-u afr_qualificacao`):
- 4 testes TestOptionalRefSubtotal PASS
- update sem erro de template/XML
- 0 regressões novas (3 falhas pré-existentes conhecidas aceitáveis: TestProposalReport CSS×2, TestResourcePlan poluição). Atenção: `TestProposalReport` testa render de blocos — confirmar que as mudanças no block_optionals/_html_optionals não adicionam NOVA falha lá.

- [ ] **Step 3: Commit submodule + bump pointer**

Via git-commit-push, cwd submodule. Push origin main. Mensagem:
```
feat(qualif): opcionais no PDF/portal — preço de referência + caixa ☑/☐ (Fase 3)

Campo optional_ref_subtotal (price_unit × qty-se-aceito) mostra o preço da
oferta mesmo não aceita; block_optionals (PDF), portal e snapshot
_html_optionals ganham coluna ☑/☐ (autorizado), Qtd=optional_qty e
Subtotal (ref.). Total geral inalterado (só aceitos somam). v16.0.5.14.0.
4 testes. Fase 3 de 4 (portal interativo = Fase 4).
```
Depois bump pointer no monorepo (`git add addons/afr_qualificacao`, commit `chore: bump afr_qualificacao (opcionais PDF fase 3)`, push main-monorepo).

---

## Manual Test Checklist
| Cenário | Esperado |
|---|---|
| Proposta PDF com opcional não aceito | mostra ☐, Qtd pretendida, Subtotal (ref.) > 0 |
| Marcar opcional aceito | PDF mostra ☑; entra no total geral |
| Portal | mesma tabela com caixas |
| Total geral | só opcionais aceitos somam |
