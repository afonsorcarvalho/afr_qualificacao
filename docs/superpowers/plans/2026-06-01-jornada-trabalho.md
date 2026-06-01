# Jornada de Trabalho (h/dia) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o divisor de dias úteis (hoje fixo `/8`) uma jornada (h/dia) configurável por equipamento, default 8, cadastrada no template, puxada no configurador (override), exibida na tabela resumo do cronograma.

**Architecture:** Campo `work_hours_per_day` em config.template → linha do configurador (onchange) → snapshot na section line do SO. Helper `_qualif_work_hours_per_day(equip)` (fallback 8) substitui os `/8.0`. Tabelas de cronograma ganham coluna h/dia.

**Tech Stack:** Odoo 16, Python, QWeb XML, TransactionCase.

---

## Convenções
- `afr_qualificacao` é submodule. **NÃO commitar** (commit só após teste do user, via agente). Trabalho in-place.
- Rodar testes:
  ```bash
  docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
    --test-enable --test-tags /afr_qualificacao:<Class> --stop-after-init \
    --no-http --workers=0 --max-cron-threads=0 \
    --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
    grep -iE 'FAIL:|tests.stats|failed,.*error|AssertionError'
  ```

## File Structure
- **Modify** `models/config_template.py` — campo `work_hours_per_day`.
- **Modify** `views/config_template_views.xml` — campo no form.
- **Modify** `wizards/qualificacao_configurator.py` — campo na equipment line + onchange + computes (per-equip days, wizard total soma) + snapshot no apply + bulk.
- **Modify** `wizards/qualificacao_configurator_views.xml` — campo h/dia editável na equipment line.
- **Modify** `models/sale_order_line.py` — campo `work_hours_per_day`.
- **Modify** `models/sale_order.py` — helper + `_qualif_estimated_days` + `_qualif_schedule_rows` + `qualif_subtotals_html` total.
- **Modify** `models/proposal_block.py` — `_html_schedule` coluna h/dia + total soma.
- **Modify** `reports/quotation_template.xml` + `views/sale_order_portal_template.xml` — coluna h/dia no schedule + remove nota "8 horas/dia".
- **Modify** `__manifest__.py` — versão.
- **Create** `tests/test_work_hours_per_day.py` + registrar em `tests/__init__.py`.

---

## Task 1: Campo `work_hours_per_day` no template

**Files:**
- Modify: `models/config_template.py` (após `estimated_days`, ~linha 89)
- Modify: `views/config_template_views.xml` (grupo "Sugestão Comercial", ~linha 42)

- [ ] **Step 1: Adicionar o campo no modelo**

Em `models/config_template.py`, imediatamente após o campo `estimated_days` (que termina na linha ~89, antes de `sequence = fields.Integer`):

```python
    work_hours_per_day = fields.Float(
        string="Jornada (h/dia)",
        default=8.0,
        help=(
            "Horas úteis por dia usadas no cálculo de dias do cronograma "
            "(dias = horas estimadas ÷ jornada). Default 8h."
        ),
    )
```

- [ ] **Step 2: Adicionar o campo no form**

Em `views/config_template_views.xml`, dentro do `<group string="Sugestão Comercial (Proposta)">`, após `<field name="estimated_days"/>` (linha 42):

```xml
                            <field name="work_hours_per_day"/>
```

- [ ] **Step 3: Verificar que o módulo atualiza sem erro**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --stop-after-init --no-http --workers=0 --max-cron-threads=0 --db_host=db --db_user=odoo --db_password=odoo 2>&1 | grep -iE 'ERROR|Traceback|Loaded' | tail -5
```
Esperado: sem ERROR/Traceback; "Modules loaded."

---

## Task 2: Configurador — campo, onchange, computes, view

**Files:**
- Modify: `wizards/qualificacao_configurator.py` (equipment line ~538-688, wizard compute ~139-144, bulk apply)
- Modify: `wizards/qualificacao_configurator_views.xml` (equipment line form, ~67)
- Create/Modify: `tests/test_work_hours_per_day.py`, `tests/__init__.py`

- [ ] **Step 1: Registrar o teste em `tests/__init__.py`**

Append:
```python

from . import test_work_hours_per_day
```

- [ ] **Step 2: Escrever o teste falhante do onchange**

Criar `tests/test_work_hours_per_day.py`:
```python
"""Jornada (h/dia) por equipamento — cálculo de dias configurável."""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestWorkHoursPerDay(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.malha_temp.estimated_hours = 4.0
        cls.tpl_wh = cls.env["afr.qualificacao.config.template"].create({
            "name": "Pacote Jornada 6h",
            "work_hours_per_day": 6.0,
            "do_qi": True,
        })

    def test_template_onchange_pulls_work_hours(self):
        line = self.env["afr.qualificacao.configurator.equipment"].new({
            "equipment_id": self.equip1.id,
            "config_template_id": self.tpl_wh.id,
        })
        line._onchange_config_template()
        self.assertAlmostEqual(line.work_hours_per_day, 6.0)
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestWorkHoursPerDay --stop-after-init --no-http --workers=0 --max-cron-threads=0 --db_host=db --db_user=odoo --db_password=odoo 2>&1 | grep -iE 'FAIL:|tests.stats|failed,.*error|AttributeError'
```
Esperado: falha — campo `work_hours_per_day` inexistente na equipment line.

- [ ] **Step 4: Adicionar o campo na equipment line**

Em `wizards/qualificacao_configurator.py`, na classe `AfrQualificacaoConfiguratorEquipment`, após o campo `estimated_days_total` (que termina na linha ~548, antes do comentário `# F8.2 — template`):

```python
    work_hours_per_day = fields.Float(
        string="Jornada (h/dia)",
        default=8.0,
        help="Horas úteis/dia deste equipamento (puxada do template, editável).",
    )
```

- [ ] **Step 5: Puxar do template no onchange**

No mesmo arquivo, em `_onchange_config_template`, após `self.do_qs = tpl.do_qs` (linha ~567):

```python
        self.work_hours_per_day = tpl.work_hours_per_day or 8.0
```

- [ ] **Step 6: Rodar e ver passar (onchange)**

Comando do Step 3. Esperado: `test_template_onchange_pulls_work_hours` passa.

- [ ] **Step 7: Usar a jornada no compute de dias por-equipamento**

Em `_compute_estimated_totals` (linha ~688), trocar:
```python
            el.estimated_days_total = hours / 8.0 if hours else 0.0
```
por:
```python
            el.estimated_days_total = (
                hours / (el.work_hours_per_day or 8.0) if hours else 0.0
            )
```
E no `@api.depends` desse compute (linha ~662-667), adicionar `"work_hours_per_day"`:
```python
    @api.depends(
        "do_qi", "do_qs", "work_hours_per_day",
        "qo_line_ids.estimated_hours", "qo_line_ids.qty",
        "qd_line_ids.estimated_hours", "qd_line_ids.qty",
        "calib_line_ids.estimated_hours", "calib_line_ids.qty",
    )
```

- [ ] **Step 8: Total do wizard = soma dos dias por-equipamento**

Em `_compute_wizard_estimated_totals` (linha ~139-144), trocar o corpo por:
```python
    @api.depends(
        "equipment_line_ids.estimated_hours_total",
        "equipment_line_ids.estimated_days_total",
    )
    def _compute_wizard_estimated_totals(self):
        for wiz in self:
            wiz.estimated_hours_total = sum(
                wiz.equipment_line_ids.mapped("estimated_hours_total")
            )
            wiz.estimated_days_total = sum(
                wiz.equipment_line_ids.mapped("estimated_days_total")
            )
```

- [ ] **Step 9: Propagar no bulk wizard**

Em `wizards/qualificacao_configurator.py`, localizar o `AfrQualificacaoConfiguratorBulk` e o ponto onde ele cria/propaga as `equipment_line_ids` (método `action_apply`/`_prepare` que monta os vals da equipment line). Adicionar `work_hours_per_day` aos vals da equipment line, puxando do template se houver:
```python
            "work_hours_per_day": (
                self.config_template_id.work_hours_per_day or 8.0
            ) if self.config_template_id else 8.0,
```
(Se o bulk não referencia `config_template_id`, usar `8.0` fixo. Ler o método antes de editar; manter o default 8 se a estrutura não tiver template.)

- [ ] **Step 10: Adicionar o campo editável na view do wizard**

Em `wizards/qualificacao_configurator_views.xml`, na form da equipment line (onde estão `estimated_hours_total`/`estimated_days_total`, ~linha 67-68), adicionar antes de `estimated_days_total`:
```xml
                                            <field name="work_hours_per_day"/>
```

- [ ] **Step 11: Rodar a classe de teste + suite do configurador**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestWorkHoursPerDay,/afr_qualificacao:TestEstimatedHours --stop-after-init --no-http --workers=0 --max-cron-threads=0 --db_host=db --db_user=odoo --db_password=odoo 2>&1 | grep -iE 'FAIL:|tests.stats|failed,.*error'
```
Esperado: 0 failed (TestEstimatedHours continua verde — total do wizard agora soma dias; com jornada 8 default o resultado é idêntico).

---

## Task 3: SO — snapshot, helper e cálculo de dias

**Files:**
- Modify: `models/sale_order_line.py` (campo)
- Modify: `wizards/qualificacao_configurator.py` (`action_apply`, section line vals ~318-327)
- Modify: `models/sale_order.py` (helper + `_qualif_estimated_days` 424-426 + `_qualif_schedule_rows` 459-478 + `qualif_subtotals_html` total ~233)
- Modify: `models/proposal_block.py` (`_html_schedule` 300-325)
- Modify: `tests/test_work_hours_per_day.py`

- [ ] **Step 1: Escrever os testes falhantes (dias)**

Adicionar à classe `TestWorkHoursPerDay`:
```python
    def _apply_calib(self, work_hours=None, malha_qty=1):
        """SO + 1 equip com 1 malha (4h) via configurador. work_hours override."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id}
        )
        eq_vals = {
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "calib_line_ids": [(0, 0, {
                "malha_type_id": self.malha_temp.id,
                "qty": malha_qty,
                "estimated_hours": 4.0,
            })],
        }
        if work_hours is not None:
            eq_vals["work_hours_per_day"] = work_hours
        self.env["afr.qualificacao.configurator.equipment"].create(eq_vals)
        wiz.action_apply()
        return so

    def test_apply_snapshots_to_section_line(self):
        so = self._apply_calib(work_hours=4.0)
        section = so.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == self.equip1
        )
        self.assertTrue(section)
        self.assertAlmostEqual(section.work_hours_per_day, 4.0)

    def test_estimated_days_uses_work_hours(self):
        # 1 malha × 4h = 4h; jornada 4h/dia → 1 dia. (malha_qty=4 → 16h → 4 dias)
        so = self._apply_calib(work_hours=4.0, malha_qty=4)
        self.assertAlmostEqual(
            so._qualif_estimated_hours(self.equip1), 16.0
        )
        self.assertAlmostEqual(
            so._qualif_estimated_days(self.equip1), 4.0
        )

    def test_fallback_8_when_no_section_or_zero(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        # equipamento sem section line → fallback 8.0
        self.assertAlmostEqual(
            so._qualif_work_hours_per_day(self.equip1), 8.0
        )

    def test_schedule_rows_include_work_hours(self):
        so = self._apply_calib(work_hours=4.0, malha_qty=4)
        rows = so._qualif_schedule_rows()
        self.assertTrue(rows)
        row = rows[0]
        self.assertAlmostEqual(row["work_hours_per_day"], 4.0)
        self.assertAlmostEqual(row["days"], 4.0)  # 16h / 4
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestWorkHoursPerDay --stop-after-init --no-http --workers=0 --max-cron-threads=0 --db_host=db --db_user=odoo --db_password=odoo 2>&1 | grep -iE 'FAIL:|tests.stats|failed,.*error|AttributeError|KeyError'
```
Esperado: falhas — campo na sale.order.line / helper inexistentes; schedule_rows sem `work_hours_per_day`.

- [ ] **Step 3: Campo na `sale.order.line`**

Em `models/sale_order_line.py`, após o campo `estimated_hours` (~linha 69-86, antes do onchange `_onchange_qualif_cycle_qty_hours`):
```python
    work_hours_per_day = fields.Float(
        string="Jornada (h/dia)",
        default=8.0,
        help=(
            "Horas úteis/dia do equipamento (congelado da proposta; usado "
            "no cronograma). Editável."
        ),
    )
```

- [ ] **Step 4: Snapshot na section line no apply**

Em `wizards/qualificacao_configurator.py`, `action_apply`, nos vals da section line por equipamento (o dict com `"display_type": "line_section"`, ~linha 318-327), adicionar:
```python
                "work_hours_per_day": eq_line.work_hours_per_day or 8.0,
```

- [ ] **Step 5: Helper + cálculo de dias em `sale_order.py`**

Em `models/sale_order.py`, adicionar o helper logo antes de `_qualif_estimated_days` (linha ~424):
```python
    def _qualif_work_hours_per_day(self, equipment):
        """Jornada (h/dia) do equipamento — lê da section line; fallback 8.0."""
        self.ensure_one()
        section = self.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == equipment
        )[:1]
        return section.work_hours_per_day or 8.0
```
Trocar `_qualif_estimated_days` (425-426):
```python
    def _qualif_estimated_days(self, equipment=None):
        """F8.14 — horas / jornada (h/dia) do equipamento (default 8)."""
        wh = self._qualif_work_hours_per_day(equipment) if equipment else 8.0
        return self._qualif_estimated_hours(equipment) / (wh or 8.0)
```
Trocar `_qualif_schedule_rows` (470-477) — enriquecer cada row:
```python
        rows = []
        for eq in equipments:
            hours = self._qualif_estimated_hours(eq)
            wh = self._qualif_work_hours_per_day(eq)
            rows.append({
                "equipment": eq,
                "hours": hours,
                "work_hours_per_day": wh,
                "days": hours / wh if hours else 0.0,
            })
        return rows
```

- [ ] **Step 6: Corrigir total de dias no `qualif_subtotals_html`**

Em `_compute_qualif_subtotals_html` (linha ~233), o total usa `total_hours / 8.0`. Acumular dias por-equipamento no loop e usar a soma. No loop (após `total_hours += hours`, ~linha 217) adicionar acumulador; declarar `total_days = 0.0` junto de `total_hours = 0.0` (linha ~205) e somar `total_days += days` (linha ~217). Depois trocar (linha 233):
```python
            total_days_str = formatLang(self.env, total_days, digits=1)
```
(Não adicionar coluna h/dia neste painel — só a correção do total. A jornada aparece só na tabela de cronograma.)

- [ ] **Step 7: `_html_schedule` (proposal_block) — coluna h/dia + total soma**

Em `models/proposal_block.py`, `_html_schedule` (300-325): adicionar coluna "h/dia" no thead, na row e somar dias no tfoot.
Thead (303-305) — adicionar `<th>` h/dia antes de "Dias úteis":
```python
            "<table class='qq-table'>"
            "<thead><tr><th>Equipamento</th>"
            "<th style='text-align:right;'>Horas</th>"
            "<th style='text-align:right;'>h/dia</th>"
            "<th style='text-align:right;'>Dias úteis</th></tr></thead><tbody>"
```
Row (309-316) — adicionar célula h/dia + acumular dias:
```python
        total_h = 0.0
        total_d = 0.0
        for r in rows:
            body.append(Markup(
                "<tr><td>%s</td>"
                "<td style='text-align:right;'>%.1f</td>"
                "<td style='text-align:right;'>%.1f</td>"
                "<td style='text-align:right;'>%.2f</td></tr>"
            ) % (
                escape(r["equipment"].display_name or ""),
                r["hours"], r["work_hours_per_day"], r["days"],
            ))
            total_h += r["hours"]
            total_d += r["days"]
```
Tfoot (318-324) — célula h/dia vazia + total de dias = `total_d`:
```python
        body.append(Markup(
            "</tbody>"
            "<tfoot><tr><td><strong>TOTAL</strong></td>"
            "<td style='text-align:right;'><strong>%.1f</strong></td>"
            "<td></td>"
            "<td style='text-align:right;'><strong>%.2f</strong></td></tr></tfoot>"
            "</table>"
        ) % (total_h, total_d))
```

- [ ] **Step 8: Rodar e ver passar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestWorkHoursPerDay --stop-after-init --no-http --workers=0 --max-cron-threads=0 --db_host=db --db_user=odoo --db_password=odoo 2>&1 | grep -iE 'FAIL:|tests.stats|failed,.*error'
```
Esperado: todos os testes de TestWorkHoursPerDay passam (0 failed).

---

## Task 4: Coluna h/dia no cronograma (PDF + portal) + remover nota

**Files:**
- Modify: `reports/quotation_template.xml` (bloco schedule ~627-668)
- Modify: `views/sale_order_portal_template.xml` (bloco schedule ~248-292)

- [ ] **Step 1: PDF — coluna h/dia + remover nota**

Em `reports/quotation_template.xml`, bloco `schedule`:
(a) Remover o `<p>` da nota (linhas 635-637):
```xml
                                <p class="text-muted" style="font-size: 14px; margin-bottom: 12px;">
                                    <em>Base de cálculo: 8 horas por dia útil.</em>
                                </p>
```
(b) Thead (642-646) — adicionar coluna h/dia:
```xml
                                            <tr>
                                                <th>Equipamento</th>
                                                <th style="text-align: right; width: 15%;">h/dia</th>
                                                <th style="text-align: right; width: 15%;">Horas</th>
                                                <th style="text-align: right; width: 15%;">Dias úteis</th>
                                            </tr>
```
(c) Row (650-654):
```xml
                                                <tr>
                                                    <td t-esc="r['equipment'].display_name"/>
                                                    <td style="text-align: right;" t-esc="'%.1f' % r['work_hours_per_day']"/>
                                                    <td style="text-align: right;" t-esc="'%.1f' % r['hours']"/>
                                                    <td style="text-align: right;" t-esc="'%.1f' % r['days']"/>
                                                </tr>
```
(d) Tfoot (657-663) — total de dias = soma das rows, célula h/dia vazia:
```xml
                                        <t t-set="total_h" t-value="sum(r['hours'] for r in rows)"/>
                                        <t t-set="total_d" t-value="sum(r['days'] for r in rows)"/>
                                        <tfoot>
                                            <tr>
                                                <td><strong>TOTAL</strong></td>
                                                <td></td>
                                                <td style="text-align: right;"><strong t-esc="'%.1f' % total_h"/></td>
                                                <td style="text-align: right;"><strong t-esc="'%.1f' % total_d"/></td>
                                            </tr>
                                        </tfoot>
```

- [ ] **Step 2: Portal — coluna h/dia + remover nota**

Em `views/sale_order_portal_template.xml`, bloco `schedule` (~248-292):
(a) Remover `<p class="text-muted small">Base de cálculo: 8 horas por dia útil.</p>` (linha 255).
(b) Thead (260-266) — adicionar coluna h/dia antes de "Dias úteis":
```xml
                                        <tr>
                                            <th>Equipamento</th>
                                            <th class="text-end">h/dia</th>
                                            <th class="text-end">Horas</th>
                                            <th class="text-end">Dias úteis</th>
                                        </tr>
```
(c) Row (268-274):
```xml
                                        <t t-foreach="rows" t-as="r">
                                            <tr>
                                                <td t-esc="r['equipment'].display_name"/>
                                                <td class="text-end" t-esc="'%.1f' % r['work_hours_per_day']"/>
                                                <td class="text-end" t-esc="'%.1f' % r['hours']"/>
                                                <td class="text-end" t-esc="'%.1f' % r['days']"/>
                                            </tr>
                                        </t>
```
(d) Tfoot (276-287) — total dias = soma; célula h/dia vazia:
```xml
                                    <t t-set="total_h" t-value="sum(r['hours'] for r in rows)"/>
                                    <t t-set="total_d" t-value="sum(r['days'] for r in rows)"/>
                                    <tfoot>
                                        <tr>
                                            <td><strong>TOTAL</strong></td>
                                            <td></td>
                                            <td class="text-end"><strong t-esc="'%.1f' % total_h"/></td>
                                            <td class="text-end"><strong t-esc="'%.1f' % total_d"/></td>
                                        </tr>
                                    </tfoot>
```

- [ ] **Step 3: Render sanity — PDF do cronograma não quebra**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestProposalReport,/afr_qualificacao:TestWorkHoursPerDay --stop-after-init --no-http --workers=0 --max-cron-threads=0 --db_host=db --db_user=odoo --db_password=odoo 2>&1 | grep -iE 'FAIL:|tests.stats|failed,.*error|QWebException'
```
Esperado: sem novas falhas (TestProposalReport mantém só as pré-existentes conhecidas; sem QWebException).

---

## Task 5: Manifest + validação

**Files:** `__manifest__.py` + validação.

- [ ] **Step 1: Bump version**

`__manifest__.py`: `"version": "16.0.5.7.0",` → `"version": "16.0.5.8.0",`.

- [ ] **Step 2: Suite completa**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags afr_qualificacao --stop-after-init --no-http --workers=0 --max-cron-threads=0 --db_host=db --db_user=odoo --db_password=odoo 2>&1 | grep -iE 'FAIL:|tests.stats|failed,.*error'
```
Esperado: novos testes passam; falhas remanescentes só as 3 pré-existentes/ambientais (`TestResourcePlan.test_fleet_single_logger_two_temp_standards`, `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`, `TestProposalReport.test_render_schedule_block`). **Nenhuma nova**.

- [ ] **Step 3: Atualizar handoff** em `.remember/remember.md` (jornada h/dia entregue, v16.0.5.8.0, aguarda teste/OK user p/ commit).

---

## Self-Review
**Spec coverage:** C1→T1; C2→T2; C3→T3(campo+snapshot); C4→T3(helper+calc); C5→T3(_html_schedule)+T4(PDF/portal); C6→T5. Refinamento: coluna h/dia só nas tabelas de cronograma; `qualif_subtotals_html` só corrige total (sem coluna) — consistente com "jornada na tabela resumo [cronograma]".
**Placeholder scan:** sem TODO/TBD. Step 9 (bulk) instrui ler antes de editar (estrutura variável) com fallback 8 explícito.
**Type consistency:** `work_hours_per_day` idêntico em config.template, equipment line, sale.order.line; `_qualif_work_hours_per_day(equipment)` assinatura única; row key `work_hours_per_day` consistente entre `_qualif_schedule_rows`, `_html_schedule`, QWeb PDF/portal.
