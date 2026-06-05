# Opcionais no Wizard — Fase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. O CÓDIGO COMPLETO de cada bloco está na spec `docs/superpowers/specs/2026-06-05-opcionais-wizard-fase2-design.md` — ler a spec antes de cada task; este plano dá os pontos de inserção, comandos e testes.

**Goal:** Reintroduzir a seleção de opcionais (serviço do catálogo + qualificação opcional) no wizard configurador, num step próprio "Opcionais", gerando linhas `is_proposal_optional=True` que a Fase 1 já trata no confirm.

**Architecture:** 2 novos transient sub-models + 2 O2M no header + step "opcionais" no `_STEP_ORDER` + geração no `action_apply` + repopulação no `_load_from_existing_lines`. Reusa o núcleo da Fase 1 (optional_accepted/optional_qty, confirm, _optional_target_qty).

**Tech Stack:** Odoo 16, Python, QWeb. afr_qualificacao é **submodule** (branch main). Testes herdam `AfrQualificacaoTestCommon` (self.partner, self.equip1, self.cycle_cmax, self.malha_temp). Wizard aberto via `sale.order.action_open_configurator` (cria wizard + chama `_load_from_existing_lines`). DB de teste: odoo_ecm_test.

---

## File Map

| Ficheiro | Mudança |
|---|---|
| `wizards/qualificacao_configurator.py` | 2 transient models novos; header O2M `optional_service_ids`/`optional_qualif_ids`; `_STEP_ORDER` + `step` Selection; geração no `action_apply`; repopulação no `_load_from_existing_lines` |
| `security/ir.model.access.csv` | 2 linhas (acesso user aos 2 models novos) |
| `wizards/qualificacao_configurator_views.xml` | div do step "opcionais" com 2 trees |
| `tests/test_optional_wizard.py` | **novo** — 6 testes |
| `__manifest__.py` | version bump |

---

## Task 1: Models, header, step, security

**Files:** `wizards/qualificacao_configurator.py`, `security/ir.model.access.csv`

- [ ] **Step 1: Adicionar os 2 transient models**

No fim de `wizards/qualificacao_configurator.py` (após o último model, `...BulkCalib` ~linha 1185+), adicionar as classes `AfrQualificacaoConfiguratorOptional` e `AfrQualificacaoConfiguratorOptionalQualif` — CÓDIGO COMPLETO na spec secção 1 (copiar verbatim). Confirmar que `api`, `fields`, `models` estão importados no topo (estão).

- [ ] **Step 2: Header — 2 O2M**

No model `afr.qualificacao.configurator` (perto de `equipment_line_ids`, ~linha 60-70), adicionar `optional_service_ids` e `optional_qualif_ids` — spec secção 2.

- [ ] **Step 3: Step "opcionais"**

Linha 25: `_STEP_ORDER = ["escopo", "opcionais", "revisao"]`.
Linha 72-77, o `step` Selection passa a:
```python
    step = fields.Selection(
        selection=[
            ("escopo", "1. Escopo"),
            ("opcionais", "2. Opcionais"),
            ("revisao", "3. Revisão"),
        ],
        default="escopo",
```
(manter o resto da definição do field). `action_next_step`/`action_prev_step` não mudam (operam sobre `_STEP_ORDER`).

- [ ] **Step 4: Security CSV**

Em `security/ir.model.access.csv`, após a linha `access_configurator_calib_user...`, adicionar:
```
access_configurator_optional_user,configurator_optional_user,model_afr_qualificacao_configurator_optional,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
access_configurator_optional_qualif_user,configurator_optional_qualif_user,model_afr_qualificacao_configurator_optional_qualif,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
```

- [ ] **Step 5: Verificar sintaxe**
`cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao && python3 -c "import ast; ast.parse(open('wizards/qualificacao_configurator.py').read()); print('OK')"`

- [ ] **Step 6: NÃO commitar.**

---

## Task 2: action_apply gera opcionais + _load repopula (TDD)

**Files:** `wizards/qualificacao_configurator.py`, `tests/test_optional_wizard.py` (novo)

- [ ] **Step 1: Escrever os 6 testes**

Create `tests/test_optional_wizard.py` herdando `AfrQualificacaoTestCommon`. Os 6 cenários estão na spec secção "Testes". Estrutura base:
```python
# -*- coding: utf-8 -*-
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestOptionalWizard(AfrQualificacaoTestCommon):

    def _wizard(self, so):
        return self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id})

    def _svc_optional(self):
        # um afr.proposal.optional do catálogo (cria produto serviço + registro)
        prod = self.env["product.product"].create(
            {"name": "Pasta Opt", "type": "service", "sale_ok": True,
             "list_price": 150.0})
        return self.env["afr.proposal.optional"].create({
            "name": "Pasta impressa", "code": "OPT-T", "kind": "folder",
            "product_id": prod.id, "default_price": 150.0, "default_qty": 1.0})

    def _equip_line(self, wiz):
        return self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id, "do_qi": True})

    def test_wizard_service_optional_generates_line(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        opt = self._svc_optional()
        self.env["afr.qualificacao.configurator.optional"].create({
            "wizard_id": wiz.id, "optional_id": opt.id, "qty": 1.0,
            "unit_price": 150.0, "accepted": False})
        wiz.action_apply()
        line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and not l.qualification_type)
        self.assertEqual(len(line), 1)
        self.assertFalse(line.optional_accepted)
        self.assertEqual(line.product_uom_qty, 0.0)

    def test_wizard_service_optional_accepted_sums(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        opt = self._svc_optional()
        self.env["afr.qualificacao.configurator.optional"].create({
            "wizard_id": wiz.id, "optional_id": opt.id, "qty": 2.0,
            "unit_price": 150.0, "accepted": True})
        wiz.action_apply()
        line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and not l.qualification_type)
        self.assertEqual(line.product_uom_qty, 2.0)
        self.assertEqual(line.price_subtotal, 300.0)

    def test_wizard_qualif_optional_not_accepted(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 2,
            "estimated_hours": 2.0, "accepted": False})
        wiz.action_apply()
        line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.qualification_type)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_uom_qty, 0.0)
        so.action_confirm()
        self.assertFalse(so.qualificacao_ids)

    def test_wizard_qualif_optional_accepted_generates(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 2,
            "estimated_hours": 2.0, "accepted": True})
        wiz.action_apply()
        line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.qualification_type)
        self.assertEqual(line.product_uom_qty, 4.0)  # 2 ciclos × 2h
        so.action_confirm()
        self.assertTrue(so.qualificacao_ids)

    def test_load_roundtrip_optionals(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        opt = self._svc_optional()
        self.env["afr.qualificacao.configurator.optional"].create({
            "wizard_id": wiz.id, "optional_id": opt.id, "qty": 1.0,
            "unit_price": 150.0, "accepted": False})
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 1,
            "estimated_hours": 2.0, "accepted": False})
        wiz.action_apply()
        wiz2 = self._wizard(so)
        wiz2._load_from_existing_lines()
        self.assertEqual(len(wiz2.optional_service_ids), 1)
        self.assertEqual(len(wiz2.optional_qualif_ids), 1)

    def test_reapply_preserves_optionals(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        opt = self._svc_optional()
        self.env["afr.qualificacao.configurator.optional"].create({
            "wizard_id": wiz.id, "optional_id": opt.id, "qty": 1.0,
            "unit_price": 150.0, "accepted": True})
        wiz.action_apply()
        n1 = len(so.order_line.filtered("is_proposal_optional"))
        wiz2 = self._wizard(so)
        wiz2._load_from_existing_lines()
        wiz2.action_apply()
        n2 = len(so.order_line.filtered("is_proposal_optional"))
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 1)
```

Registar `from . import test_optional_wizard` em `tests/__init__.py`.

- [ ] **Step 2: Rodar → FAIL** (action_apply ainda não gera opcionais; O2M/models não existem se Task 1 não estiver feita — Task 1 é pré-requisito; rodar após Task 1). test-runner tags `/afr_qualificacao:TestOptionalWizard`.

- [ ] **Step 3: Implementar geração no action_apply**

Em `action_apply`, ANTES de `so.write({"order_line": new_lines})` (linha ~502), inserir os 2 blocos (serviços + qualificações) — CÓDIGO COMPLETO na spec secção 4 (copiar verbatim). LER o método à volta da linha 500-502 para inserir no ponto certo (depois do loop `for eq_line`, antes do write).

- [ ] **Step 4: Implementar repopulação no _load_from_existing_lines**

Em `_load_from_existing_lines`, após `if cmds: self.equipment_line_ids = cmds` (~linha 300), inserir o bloco de repopulação dos opcionais — CÓDIGO COMPLETO na spec secção 5 (copiar verbatim).

- [ ] **Step 5: Rodar → PASS** (6 testes). test-runner, `-u afr_qualificacao` + tags `/afr_qualificacao:TestOptionalWizard`.

- [ ] **Step 6: NÃO commitar.**

---

## Task 3: View do step Opcionais

**Files:** `wizards/qualificacao_configurator_views.xml`

- [ ] **Step 1: Adicionar div do step**

LER a view à volta dos divs `step=='escopo'` e `step=='revisao'`. Entre eles, inserir:
```xml
                <div attrs="{'invisible': [('step', '!=', 'opcionais')]}">
                    <separator string="Serviços Opcionais"/>
                    <field name="optional_service_ids">
                        <tree editable="bottom">
                            <field name="optional_id"/>
                            <field name="qty"/>
                            <field name="unit_price"/>
                            <field name="accepted" widget="boolean_toggle"/>
                        </tree>
                    </field>
                    <separator string="Qualificações Opcionais"/>
                    <field name="optional_qualif_ids">
                        <tree editable="bottom">
                            <field name="equipment_id"/>
                            <field name="qualification_type"/>
                            <field name="cycle_type_id"/>
                            <field name="malha_type_id"/>
                            <field name="qty"/>
                            <field name="estimated_hours"/>
                            <field name="accepted" widget="boolean_toggle"/>
                        </tree>
                    </field>
                </div>
```

- [ ] **Step 2: Validar XML**
`python3 -c "import xml.dom.minidom as m; m.parse('wizards/qualificacao_configurator_views.xml'); print('OK')"`

- [ ] **Step 3: NÃO commitar.**

---

## Task 4: Bump + suite + commit

**Files:** `__manifest__.py`

- [ ] **Step 1: Version bump** `16.0.5.12.0` → `16.0.5.13.0`.

- [ ] **Step 2: Update + suite completa** (test-runner, `-u afr_qualificacao`):
- 6 testes TestOptionalWizard PASS
- update sem erro de view/CSV
- 0 regressões novas (3 falhas pré-existentes conhecidas aceitáveis)

- [ ] **Step 3: Commit submodule + bump pointer**

Via git-commit-push, cwd submodule. Push origin main. Mensagem:
```
feat(qualif): step "Opcionais" no wizard — serviço + qualificação opcional (Fase 2)

2 transient models (optional / optional.qualif) + O2M no header + step
opcionais; action_apply gera linhas is_proposal_optional (serviço do catálogo
e qualificação extra); _load_from_existing_lines repopula no re-open.
v16.0.5.13.0. 6 testes. Fase 2 de 4 (PDF/portal seguem).
```
Depois bump pointer no monorepo (`git add addons/afr_qualificacao`, commit `chore: bump afr_qualificacao (opcionais wizard fase 2)`, push main-monorepo).

---

## Manual Test Checklist (pós-merge)
| Cenário | Esperado |
|---|---|
| Abrir wizard, step Opcionais | 2 secções (Serviços / Qualificações) |
| Add serviço opcional, não aceito, aplicar | linha no SO, não soma |
| Marcar aceito | soma ao total |
| Add qualif opcional aceita, confirmar | gera afr.qualificacao + OS |
| Reabrir wizard | opcionais repopulados nas 2 secções |
