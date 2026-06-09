# Qualificações: remover Etapas/Desvios/Mensagens + aba Coletas — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Remover models/UI de Etapas e Desvios, esconder aba Mensagens, e adicionar aba "Coletas" (editável, full width) no form de `afr.qualificacao`.

**Architecture:** Deleções coordenadas em model/views/menu/security/report + uma page nova reutilizando o One2many `collect_item_ids` (inverse `qualif_id`) já existente. Sem mudança de dados.

**Tech Stack:** Odoo 16, Python, XML. labquali em DEV (sem migração; tabelas órfãs inertes).

**Submodule:** `addons/afr_qualificacao/` é submodule (branch `main`). Commit/push de dentro do dir; bump pointer no monorepo depois. Commits via agente haiku.

**Versão alvo:** 16.0.5.19.2 → 16.0.5.20.0.

**Teste:** `docker exec odoo_engenapp-web-1 odoo -u afr_qualificacao -d qualif_test_f811 --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo --test-enable --test-tags=/afr_qualificacao --stop-after-init --no-http`

---

## Task 1: Remover models step/deviation + campos/computes

**Files:** `models/qualificacao.py`

- [ ] **Step 1:** Remover bloco de campos (linhas ~120-141): `deviation_ids`, `step_ids`, `step_count`, `deviation_count` (os 4 campos consecutivos). Manter `summary` antes e `docx_template_id` depois.
- [ ] **Step 2:** Remover os computes `_compute_step_count` e `_compute_deviation_count` (linhas ~540-550).
- [ ] **Step 3:** Remover as classes `AfrQualificacaoStep` (linha ~1313) e `AfrQualificacaoDeviation` (linha ~1363) por completo — do `class AfrQualificacaoStep` até o fim de `AfrQualificacaoDeviation` (antes de `class AfrQualificacaoQdPointSnapshot`).
- [ ] **Step 4:** Verificar que nada mais no arquivo referencia `step_ids`/`deviation_ids`/`afr.qualificacao.step`/`afr.qualificacao.deviation` (grep).

## Task 2: Remover security das 2 models

**Files:** `security/ir.model.access.csv`

- [ ] Remover as 4 linhas: `access_afr_qualificacao_step_user`, `access_afr_qualificacao_step_manager`, `access_afr_qualificacao_deviation_user`, `access_afr_qualificacao_deviation_manager`.

## Task 3: Views — remover Etapas/Desvios/Mensagens + records deviation, adicionar Coletas

**Files:** `views/qualificacao_views.xml`

- [ ] **Step 1:** Remover record `view_afr_qualificacao_deviation_search` (linhas ~29-41).
- [ ] **Step 2:** Remover record `action_afr_qualificacao_deviation` (linhas ~42-47).
- [ ] **Step 3:** Remover o smart button de Desvios no `button_box` (o `<button>` com `name="%(afr_qualificacao.action_afr_qualificacao_deviation)d"` contendo `deviation_count`, linhas ~102-114).
- [ ] **Step 4:** Remover `<page string="Etapas">` (linhas ~179-189) e `<page string="Desvios">` (linhas ~190-200).
- [ ] **Step 5:** Remover `<page string="Mensagens">` (linhas ~330-334).
- [ ] **Step 6:** Remover records `view_afr_qualificacao_deviation_tree` (~375-388) e `view_afr_qualificacao_deviation_form` (~390-415).
- [ ] **Step 7:** Adicionar a page Coletas **imediatamente antes** de `<page string="Comercial">` (onde ficavam Etapas/Desvios). Field direto no page (page já é full width — NÃO envolver em `<group>`):

```xml
<page string="Coletas">
    <field name="collect_item_ids">
        <tree editable="bottom"
              decoration-success="state == 'collected' and relatorio_id"
              decoration-muted="state == 'skipped'"
              decoration-warning="state == 'pending' and required"
              decoration-danger="collected_without_relatorio">
            <field name="sequence" widget="handle"/>
            <field name="name"/>
            <field name="kind"/>
            <field name="cycle_id" optional="show"/>
            <field name="malha_id" optional="hide"/>
            <field name="required"/>
            <field name="state" widget="badge"
                   decoration-success="state == 'collected'"
                   decoration-warning="state == 'pending'"
                   decoration-muted="state == 'skipped'"/>
            <field name="relatorio_id" optional="show"/>
            <field name="captured_by" optional="hide"/>
            <field name="filename" optional="hide"/>
        </tree>
    </field>
</page>
```

## Task 4: Menu — remover Desvios

**Files:** `views/qualificacao_menus.xml`

- [ ] Remover `menuitem id="menu_afr_qualificacao_deviation"` (linhas ~51-58).

## Task 5: Report certificate — remover seções step/deviation

**Files:** `reports/qualificacao_certificate_template.xml`

- [ ] **Step 1:** Remover a seção Etapas: do `<br/>` + `<h4>Etapas de Qualificação</h4>` (linha ~62) até `<p t-if="not o.step_ids">...</p>` inclusive (linha ~84).
- [ ] **Step 2:** Remover a seção Desvios: o bloco `<!-- Desvios --> <t t-if="o.deviation_ids">...</t>` (linhas ~140-161).

## Task 6: Bump versão

**Files:** `__manifest__.py`

- [ ] `16.0.5.19.2` → `16.0.5.20.0`.

## Task 7: Testes

**Files:** `tests/test_remove_models_coletas.py` (novo) + `tests/__init__.py`

- [ ] **Step 1:** Criar teste:

```python
"""Verifica remoção de step/deviation e presença da aba Coletas."""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestRemoveModelsColetas(TransactionCase):

    def test_step_deviation_models_removed(self):
        self.assertNotIn("afr.qualificacao.step", self.env)
        self.assertNotIn("afr.qualificacao.deviation", self.env)

    def test_qualif_fields_removed(self):
        fields = self.env["afr.qualificacao"]._fields
        for f in ("step_ids", "deviation_ids", "step_count", "deviation_count"):
            self.assertNotIn(f, fields)

    def test_collect_item_ids_present(self):
        self.assertIn("collect_item_ids", self.env["afr.qualificacao"]._fields)
```

- [ ] **Step 2:** Adicionar `from . import test_remove_models_coletas` em `tests/__init__.py`.
- [ ] **Step 3:** Rodar `-u afr_qualificacao --test-enable --test-tags=/afr_qualificacao` e garantir suíte verde. Corrigir qualquer teste que referencie os models/campos removidos (não há conhecidos — `test_configurator_steps` usa `wiz.step` do wizard, OK).

## Task 8: Validação de layout via agent-browser (controller faz)

- [ ] Restart container. Abrir form de uma qualificação. Verificar: abas Etapas/Desvios/Mensagens sumiram; aba Coletas presente; **tree da aba Coletas ocupa largura total** (não suprimida); smart button Desvios sumiu. Screenshot de evidência.

## Task 9: Commit + push + bump pointer

- [ ] Commit submodule (de dentro do dir) → push origin main → bump pointer monorepo → push.

---

## Self-Review

- Models removidos → Task 1. Security → Task 2. Views (pages/button/records/Coletas) → Task 3. Menu → Task 4. Report → Task 5. Versão → Task 6. Testes → Task 7. Layout → Task 8. Git → Task 9. ✓
- Sem placeholders. `collect_item_ids` confirmado existente (qualificacao.py:274). Page = full width sem `<group>` (lição das larguras suprimidas anteriores). ✓
- labquali DEV: tabelas órfãs aceitáveis, sem cleanup. ✓
