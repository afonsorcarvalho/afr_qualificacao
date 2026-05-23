# F8.14 Cronograma Estimado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-execution time estimate (hours) to cycle/malha/QI/QS catalog with override at template/configurator/SO line level. Aggregate as hours + business-days (8h/day) per equipment and total. Display in PDF: `<tfoot>` subtotals in QO/QD/cycle_specs tables, Equipment Scope footer with total, new `schedule` block kind for cross-equipment table.

**Architecture:** Field rename + new field cascade across 6 models (cycle_type, malha_type, type.config, template lines, configurator sublines, SO line). Helpers in `sale.order` aggregate from SO lines (override) or fall back to type. QWeb additions to existing `quotation_template.xml`. New block handler in `proposal_block.py`. CSS additions to existing report `<style>`.

**Tech Stack:** Odoo 16, Python 3.9, PostgreSQL, QWeb, docker test runner (`docker exec odoo_engenapp-web-1 odoo ...`).

**Worktree:** `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/.claude/worktrees/f8-proposta-lego` (branch `worktree-f8-proposta-lego`).

**Test runner pattern:** Sync changes from worktree to submodule main checkout (mounted in container), drop+create `qualif_test_f811`, run `odoo -i afr_qualificacao --test-enable --test-tags=afr_qualificacao`, restore main via `git checkout --`.

---

## File Structure

**Modified (existing):**
- `models/cycle_type.py` — rename field.
- `models/malha_type.py` — rename field.
- `models/type_config.py` — new field.
- `models/config_template.py` — new field in 3 line classes.
- `models/sale_order_line.py` — new field.
- `models/sale_order.py` — new helpers (3).
- `models/proposal_block.py` — new block_kind handler `_html_schedule`.
- `models/proposal_template.py` — extend `PROPOSAL_BLOCK_KINDS` selection.
- `wizards/qualificacao_configurator.py` — new fields in 6 line classes + onchange + autofill + apply + computed totals on equipment + wizard.
- `wizards/qualificacao_configurator_views.xml` — tree columns + readonly totals.
- `views/config_template_views.xml` — column in 3 tabs.
- `reports/quotation_template.xml` — CSS additions + tfoot rows in 3 tables + equipment scope footer + schedule block QWeb.
- `data/cycle_type_seed.xml` — set `estimated_hours` on seed records.
- `data/malha_type_seed.xml` — same.
- `tests/test_proposal_report.py` — 3 new test methods.
- `tests/common.py` — adjust `cycle_qo_test` if needed (no estimated_hours assumed).
- `__manifest__.py` — bump version + roadmap.
- `TODO.md` — entry.

**Created:**
- `tests/test_estimated_hours.py` — new test file (8 tests).
- `data/migration_estimated_hours_seed.xml` (optional) — only if seeds need re-populated values.

---

## Pre-flight

- [ ] **Step 1: Confirm worktree branch is current**

Run:
```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/.claude/worktrees/f8-proposta-lego
git status
git log --oneline -2
```
Expected: branch `worktree-f8-proposta-lego`, HEAD includes `4a59944` (spec commit) or later.

- [ ] **Step 2: Confirm submodule main is clean**

Run:
```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git status -s
```
Expected: only `.claude/`, `.vscode/`, `.gitignore` as untracked. No modified files.

---

## Phase 1 — Models

### Task 1: Rename cycle_type.estimated_days → estimated_hours

**Files:**
- Modify: `models/cycle_type.py:72-75`

- [ ] **Step 1: Edit field**

Open `models/cycle_type.py`, find the `estimated_days` field around line 72-75 and replace:

```python
    estimated_days = fields.Float(
        string="Dias Estimados",
        help="Dias de execução estimados deste ciclo (sugestão para a proposta).",
    )
```

with:

```python
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits="Product Price",
        help=(
            "Horas estimadas por execução deste ciclo (sugestão pra "
            "cronograma da proposta). Convertido em dias úteis via /8."
        ),
    )
```

- [ ] **Step 2: Syntax check**

Run: `python3 -c "import ast; ast.parse(open('models/cycle_type.py').read())"`
Expected: no output (exit 0).

- [ ] **Step 3: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/.claude/worktrees/f8-proposta-lego
git add models/cycle_type.py
git commit -m "refactor(cycle_type): rename estimated_days → estimated_hours (F8.14)"
```

### Task 2: Rename malha_type.estimated_days → estimated_hours

**Files:**
- Modify: `models/malha_type.py:64-67`

- [ ] **Step 1: Edit field**

In `models/malha_type.py`, replace:

```python
    estimated_days = fields.Float(
        string="Dias Estimados",
        help="Dias de execução estimados desta malha (sugestão para a proposta).",
    )
```

with:

```python
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits="Product Price",
        help=(
            "Horas estimadas por execução desta malha (sugestão pra "
            "cronograma da proposta). Convertido em dias úteis via /8."
        ),
    )
```

- [ ] **Step 2: Syntax check**

Run: `python3 -c "import ast; ast.parse(open('models/malha_type.py').read())"`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add models/malha_type.py
git commit -m "refactor(malha_type): rename estimated_days → estimated_hours (F8.14)"
```

### Task 3: Add type_config.estimated_hours

**Files:**
- Modify: `models/type_config.py` (find class `AfrQualificacaoTypeConfig`)

- [ ] **Step 1: Inspect existing fields**

Run: `grep -n "fields\.\|class AfrQualificacao" models/type_config.py | head -20`

- [ ] **Step 2: Add field after existing fields (before any methods)**

Add inside `AfrQualificacaoTypeConfig`:

```python
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits="Product Price",
        help=(
            "Horas estimadas pra execução deste tipo (QI/QO/QS/Calib) "
            "quando não há ciclo específico. Usado pelo cronograma."
        ),
    )
```

- [ ] **Step 3: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('models/type_config.py').read())"
git add models/type_config.py
git commit -m "feat(type_config): add estimated_hours field (F8.14)"
```

### Task 4: Add estimated_hours to template line models

**Files:**
- Modify: `models/config_template.py` (3 classes: Qd, Qo, Calib lines)

- [ ] **Step 1: Add field after `description` in each class**

Pattern to add in each of `AfrQualificacaoConfigTemplateQd`, `AfrQualificacaoConfigTemplateQo`, `AfrQualificacaoConfigTemplateCalib` (right after the `description` field added in F8.13):

```python
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits="Product Price",
        help=(
            "Override de horas/run do tipo neste template. 0 = usa "
            "cycle_type/malha_type.estimated_hours."
        ),
    )
```

- [ ] **Step 2: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('models/config_template.py').read())"
git add models/config_template.py
git commit -m "feat(config_template): add estimated_hours override per template line (F8.14)"
```

### Task 5: Add sale.order.line.estimated_hours

**Files:**
- Modify: `models/sale_order_line.py`

- [ ] **Step 1: Locate qualification fields**

Run: `grep -n "is_qualificacao_managed\|qualification_type\|estimated_hours" models/sale_order_line.py | head`

- [ ] **Step 2: Add field near other qualif fields**

```python
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits="Product Price",
        help=(
            "Horas estimadas por execução desta linha (override do "
            "cycle_type/malha_type/type_config). Usado pelo cronograma."
        ),
    )
```

- [ ] **Step 3: Verify field is copied on SO duplicate**

If file has `copy=False` pattern on qualif fields, follow suit; otherwise default copy=True is fine.

- [ ] **Step 4: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('models/sale_order_line.py').read())"
git add models/sale_order_line.py
git commit -m "feat(sale_order_line): add estimated_hours field (F8.14)"
```

---

## Phase 2 — Configurator wizard

### Task 6: Add estimated_hours to configurator subline models

**Files:**
- Modify: `wizards/qualificacao_configurator.py` (6 classes: QdLine, QoLine, CalibLine, BulkQd, BulkQo, BulkCalib)

- [ ] **Step 1: Locate each subline class**

Run: `grep -n "class AfrQualificacaoConfigurator\(Qd\|Qo\|Calib\|BulkQd\|BulkQo\|BulkCalib\)" wizards/qualificacao_configurator.py`

- [ ] **Step 2: Add field after unit_price in each**

```python
    estimated_hours = fields.Float(
        string="Horas",
        digits="Product Price",
    )
```

- [ ] **Step 3: Update onchange in QdLine, QoLine, BulkQd, BulkQo**

Locate `_onchange_cycle_type_defaults` (4 occurrences). After the unit_price block, add:

```python
                if not line.estimated_hours:
                    line.estimated_hours = line.cycle_type_id.estimated_hours
```

- [ ] **Step 4: Update onchange in CalibLine, BulkCalib**

Locate `_onchange_malha_type_defaults` (2 occurrences). After the unit_price block, add:

```python
                if not line.estimated_hours:
                    line.estimated_hours = line.malha_type_id.estimated_hours
```

- [ ] **Step 5: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('wizards/qualificacao_configurator.py').read())"
git add wizards/qualificacao_configurator.py
git commit -m "feat(configurator): add estimated_hours to QO/QD/Calib sublines + bulk (F8.14)"
```

### Task 7: Update template autofill to propagate estimated_hours

**Files:**
- Modify: `wizards/qualificacao_configurator.py` (`_onchange_config_template`, around line 500-549)

- [ ] **Step 1: Add `estimated_hours` to all 3 list comprehensions**

For QO + QD blocks, add inside the dict:

```python
                "estimated_hours": (
                    line.estimated_hours
                    or line.cycle_type_id.estimated_hours
                    or 0.0
                ),
```

For Calib block:

```python
                "estimated_hours": (
                    line.estimated_hours
                    or line.malha_type_id.estimated_hours
                    or 0.0
                ),
```

- [ ] **Step 2: Update `action_duplicate` (~line 580-600) — copy estimated_hours from sublines**

For QO/QD sublines:

```python
                    "estimated_hours": l.estimated_hours,
```

For Calib:

```python
                    "estimated_hours": l.estimated_hours,
```

- [ ] **Step 3: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('wizards/qualificacao_configurator.py').read())"
git add wizards/qualificacao_configurator.py
git commit -m "feat(configurator): autofill template + duplicate propagate estimated_hours (F8.14)"
```

### Task 8: Update action_apply to propagate estimated_hours to SO lines

**Files:**
- Modify: `wizards/qualificacao_configurator.py` (action_apply: QO block ~line 314, QD ~line 351, Calib ~line 363, QI/QS ~line 289)

- [ ] **Step 1: QO block — add after price_unit conditional**

```python
                hours = qo.estimated_hours or qo.cycle_type_id.estimated_hours
                if hours:
                    qo_vals["estimated_hours"] = hours
```

- [ ] **Step 2: QD block — same pattern**

```python
                hours = qd.estimated_hours or qd.cycle_type_id.estimated_hours
                if hours:
                    qd_vals["estimated_hours"] = hours
```

- [ ] **Step 3: Calib block — use malha_type**

```python
                hours = c.estimated_hours or c.malha_type_id.estimated_hours
                if hours:
                    c_vals["estimated_hours"] = hours
```

- [ ] **Step 4: QI/QS block — pull from type.config**

In the QI/QS loop where `cfg = TypeConfig.get_config_for(qtype, ...)`, after `if cfg.default_unit_price: vals["price_unit"] = ...`:

```python
                if cfg.estimated_hours:
                    vals["estimated_hours"] = cfg.estimated_hours
```

- [ ] **Step 5: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('wizards/qualificacao_configurator.py').read())"
git add wizards/qualificacao_configurator.py
git commit -m "feat(configurator): action_apply propagates estimated_hours to SO lines (F8.14)"
```

### Task 9: Computed totals on equipment_line + wizard root

**Files:**
- Modify: `wizards/qualificacao_configurator.py` (class `AfrQualificacaoConfiguratorEquipment` ~line 460, class `AfrQualificacaoConfigurator` ~line 100)

- [ ] **Step 1: Add fields in equipment_line class (after `subtotal` field)**

```python
    estimated_hours_total = fields.Float(
        string="Horas Totais",
        compute="_compute_estimated_totals",
        digits="Product Price",
    )
    estimated_days_total = fields.Float(
        string="Dias Úteis",
        compute="_compute_estimated_totals",
        digits=(8, 1),
        help="Horas estimadas / 8 (1 dia útil = 8h).",
    )
```

- [ ] **Step 2: Add compute method after `_compute_subtotal`**

```python
    @api.depends(
        "do_qi", "do_qs",
        "qo_line_ids.estimated_hours", "qo_line_ids.qty",
        "qd_line_ids.estimated_hours", "qd_line_ids.qty",
        "calib_line_ids.estimated_hours", "calib_line_ids.qty",
    )
    def _compute_estimated_totals(self):
        TypeConfig = self.env["afr.qualificacao.type.config"]
        for el in self:
            hours = 0.0
            for flag, qtype in (("do_qi", "installation"), ("do_qs", "software")):
                if not el[flag]:
                    continue
                cfg = TypeConfig.get_config_for(qtype, el.wizard_id.company_id)
                if cfg:
                    hours += cfg.estimated_hours or 0.0
            for line in el.qo_line_ids:
                h = line.estimated_hours or line.cycle_type_id.estimated_hours
                hours += (h or 0.0) * (line.qty or 0)
            for line in el.qd_line_ids:
                h = line.estimated_hours or line.cycle_type_id.estimated_hours
                hours += (h or 0.0) * (line.qty or 0)
            for line in el.calib_line_ids:
                h = line.estimated_hours or line.malha_type_id.estimated_hours
                hours += (h or 0.0) * (line.qty or 0)
            el.estimated_hours_total = hours
            el.estimated_days_total = hours / 8.0 if hours else 0.0
```

- [ ] **Step 3: Add fields in wizard root class**

In `AfrQualificacaoConfigurator`:

```python
    estimated_hours_total = fields.Float(
        string="Horas (Total)",
        compute="_compute_wizard_estimated_totals",
        digits="Product Price",
    )
    estimated_days_total = fields.Float(
        string="Dias Úteis (Total)",
        compute="_compute_wizard_estimated_totals",
        digits=(8, 1),
    )

    @api.depends(
        "equipment_line_ids.estimated_hours_total",
    )
    def _compute_wizard_estimated_totals(self):
        for wiz in self:
            hours = sum(wiz.equipment_line_ids.mapped("estimated_hours_total"))
            wiz.estimated_hours_total = hours
            wiz.estimated_days_total = hours / 8.0 if hours else 0.0
```

- [ ] **Step 4: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('wizards/qualificacao_configurator.py').read())"
git add wizards/qualificacao_configurator.py
git commit -m "feat(configurator): computed estimated_hours/days totals per equip + wizard (F8.14)"
```

### Task 10: Update configurator views (tree columns + readonly totals)

**Files:**
- Modify: `wizards/qualificacao_configurator_views.xml`

- [ ] **Step 1: Add Horas column in 3 sublines tree (equipment modal — lines ~72, ~83, ~94)**

After `<field name="qty"/>` add `<field name="estimated_hours"/>` in each of QO/QD/Calib pages.

- [ ] **Step 2: Add readonly totals in equipment modal sheet (near `subtotal` field, ~line 67)**

```xml
                                            <field name="estimated_hours_total" readonly="1"/>
                                            <field name="estimated_days_total" readonly="1"/>
```

- [ ] **Step 3: Add Horas column in equipment tree (~line 116)**

After `<field name="subtotal"/>`:

```xml
                                <field name="estimated_days_total" optional="show"/>
```

- [ ] **Step 4: Add Horas in Bulk wizard trees (~line 232+)**

Same pattern: `<field name="estimated_hours"/>` after `<field name="qty"/>` in 3 tabs.

- [ ] **Step 5: Display wizard-level totals (find wizard form footer or summary group, add)**

```xml
                <field name="estimated_days_total" readonly="1"/>
                <field name="estimated_hours_total" readonly="1"/>
```

- [ ] **Step 6: XML syntax check**

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('wizards/qualificacao_configurator_views.xml')"
```

- [ ] **Step 7: Commit**

```bash
git add wizards/qualificacao_configurator_views.xml
git commit -m "feat(configurator-views): Horas column + estimated totals readonly (F8.14)"
```

---

## Phase 3 — sale.order helpers

### Task 11: Write failing test for _qualif_estimated_hours

**Files:**
- Create: `tests/test_estimated_hours.py`

- [ ] **Step 1: Create test file with first 2 tests**

```python
"""F8.14 — testes do cronograma estimado (estimated_hours)."""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestEstimatedHours(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cycle_cmax.estimated_hours = 2.0
        cls.cycle_qo_test.estimated_hours = 0.5
        cls.malha_temp.estimated_hours = 4.0

    def _wizard_with(self, *, qo=None, qd=None, calib=None, do_qi=False):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": do_qi,
            "qo_line_ids": [
                (0, 0, {"cycle_type_id": ct.id, "qty": qty})
                for ct, qty in (qo or [])
            ],
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": ct.id, "qty": qty})
                for ct, qty in (qd or [])
            ],
            "calib_line_ids": [
                (0, 0, {"malha_type_id": mt.id, "qty": qty})
                for mt, qty in (calib or [])
            ],
        })
        wiz.action_apply()
        return so

    def test_qualif_estimated_hours_aggregates_per_equipment(self):
        """Soma horas considera qty × estimated_hours por linha."""
        so = self._wizard_with(qd=[(self.cycle_cmax, 3)])  # 3 × 2h = 6h
        self.assertAlmostEqual(
            so._qualif_estimated_hours(self.equip1), 6.0,
        )

    def test_qualif_estimated_days_divides_by_8(self):
        """24h = 3 dias úteis; 12h = 1.5 dias."""
        so = self._wizard_with(qd=[(self.cycle_cmax, 12)])  # 12 × 2h = 24h
        self.assertAlmostEqual(
            so._qualif_estimated_days(self.equip1), 3.0,
        )
```

- [ ] **Step 2: Sync to submodule main + run tests (expect FAIL — helpers don't exist)**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
for f in tests/test_estimated_hours.py tests/common.py models/cycle_type.py models/malha_type.py models/type_config.py models/config_template.py models/sale_order_line.py wizards/qualificacao_configurator.py wizards/qualificacao_configurator_views.xml; do cp .claude/worktrees/f8-proposta-lego/$f $f 2>/dev/null; done
docker exec odoo_engenapp-db-1 psql -U odoo -c "DROP DATABASE qualif_test_f811;" 2>&1 | tail -1
docker exec odoo_engenapp-db-1 psql -U odoo -c "CREATE DATABASE qualif_test_f811 OWNER odoo;" 2>&1 | tail -1
docker exec -e PGPASSWORD=odoo odoo_engenapp-web-1 odoo --stop-after-init --no-http --workers=0 --db_host=db --db_user=odoo --db_password=odoo -d qualif_test_f811 -i afr_qualificacao --test-enable --test-tags=/afr_qualificacao:TestEstimatedHours --log-level=warn 2>&1 | tail -10
```
Expected: AttributeError or FAIL on `_qualif_estimated_hours`/`_qualif_estimated_days`. Also `cycle_qo_test` must have `estimated_hours` field accepted (Task 1 already passed).

If `cycle_qo_test` fixture is missing in common.py, Task 11 may fail earlier — that's the fixture added in F8.12; verify it exists via `grep cycle_qo_test tests/common.py`.

- [ ] **Step 3: Implement `_qualif_estimated_hours` + `_qualif_estimated_days` in `models/sale_order.py`**

After `_qualif_equipment_summary` (around line 257-330):

```python
    def _qualif_estimated_hours(self, equipment=None):
        """F8.14 — soma horas estimadas das qualif lines do SO.

        Override `sale.order.line.estimated_hours` prevalece; fallback
        cycle_type/malha_type/type.config.estimated_hours. QI/QS via
        type.config.estimated_hours quando line.estimated_hours=0.
        """
        self.ensure_one()
        TypeConfig = self.env["afr.qualificacao.type.config"]
        lines = self.order_line.filtered("is_qualificacao_managed")
        if equipment:
            lines = lines.filtered(lambda l: l.equipment_id == equipment)
        total = 0.0
        for line in lines:
            hours = line.estimated_hours
            if not hours:
                if line.cycle_type_id:
                    hours = line.cycle_type_id.estimated_hours
                elif line.malha_type_id:
                    hours = line.malha_type_id.estimated_hours
                elif line.qualification_type in ("installation", "software"):
                    cfg = TypeConfig.get_config_for(
                        line.qualification_type, self.company_id,
                    )
                    if cfg:
                        hours = cfg.estimated_hours
            total += (hours or 0.0) * (line.product_uom_qty or 0)
        return total

    def _qualif_estimated_days(self, equipment=None):
        """F8.14 — horas / 8 (Float decimal — 1 dia útil = 8h)."""
        return self._qualif_estimated_hours(equipment) / 8.0
```

- [ ] **Step 4: Sync + rerun tests (expect PASS)**

```bash
cp .claude/worktrees/f8-proposta-lego/models/sale_order.py /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/models/sale_order.py
docker exec odoo_engenapp-db-1 psql -U odoo -c "DROP DATABASE qualif_test_f811;" 2>&1 | tail -1
docker exec odoo_engenapp-db-1 psql -U odoo -c "CREATE DATABASE qualif_test_f811 OWNER odoo;" 2>&1 | tail -1
docker exec -e PGPASSWORD=odoo odoo_engenapp-web-1 odoo --stop-after-init --no-http --workers=0 --db_host=db --db_user=odoo --db_password=odoo -d qualif_test_f811 -i afr_qualificacao --test-enable --test-tags=/afr_qualificacao:TestEstimatedHours --log-level=warn 2>&1 | grep -E "Ran |FAIL|ERROR" | tail
```
Expected: 2 tests passed, 0 failures.

- [ ] **Step 5: Restore submodule main + commit (in worktree)**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git checkout -- tests/ models/ wizards/
cd .claude/worktrees/f8-proposta-lego
git add models/sale_order.py tests/test_estimated_hours.py
git commit -m "feat(sale_order): _qualif_estimated_hours/days helpers + 2 tests (F8.14)"
```

### Task 12: Add _qualif_schedule_rows helper + test

**Files:**
- Modify: `models/sale_order.py`
- Modify: `tests/test_estimated_hours.py`

- [ ] **Step 1: Append test**

In `TestEstimatedHours` class:

```python
    def test_qualif_schedule_rows_returns_per_equipment(self):
        """Helper retorna lista equipamento × horas × dias + total."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        wiz.equipment_line_ids = [
            (0, 0, {
                "equipment_id": self.equip1.id,
                "qd_line_ids": [(0, 0, {
                    "cycle_type_id": self.cycle_cmax.id, "qty": 4,  # 4×2h = 8h
                })],
            }),
            (0, 0, {
                "equipment_id": self.equip2.id,
                "qd_line_ids": [(0, 0, {
                    "cycle_type_id": self.cycle_cmax.id, "qty": 8,  # 8×2h = 16h
                })],
            }),
        ]
        wiz.action_apply()
        rows = so._qualif_schedule_rows()
        self.assertEqual(len(rows), 2)
        e1 = next(r for r in rows if r["equipment"] == self.equip1)
        e2 = next(r for r in rows if r["equipment"] == self.equip2)
        self.assertAlmostEqual(e1["hours"], 8.0)
        self.assertAlmostEqual(e1["days"], 1.0)
        self.assertAlmostEqual(e2["hours"], 16.0)
        self.assertAlmostEqual(e2["days"], 2.0)
```

- [ ] **Step 2: Sync + run (expect FAIL — helper missing)**

Same sync pattern as Task 11 Step 2.

- [ ] **Step 3: Implement `_qualif_schedule_rows` in `models/sale_order.py`**

After `_qualif_estimated_days`:

```python
    def _qualif_schedule_rows(self):
        """F8.14 — retorna lista [{equipment, hours, days}] por equip + total geral.

        Usado pelo bloco `schedule` do PDF. Equipments na ordem de
        primeira aparição nas qualif lines.
        """
        self.ensure_one()
        equipments = []
        for line in self.order_line.filtered("is_qualificacao_managed"):
            if line.equipment_id and line.equipment_id not in equipments:
                equipments.append(line.equipment_id)
        rows = []
        for eq in equipments:
            hours = self._qualif_estimated_hours(eq)
            rows.append({
                "equipment": eq,
                "hours": hours,
                "days": hours / 8.0 if hours else 0.0,
            })
        return rows
```

- [ ] **Step 4: Sync + rerun (expect PASS, all 3 tests now)**

Same as Task 11 Step 4 but expecting 3 passed.

- [ ] **Step 5: Restore + commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git checkout -- tests/ models/
cd .claude/worktrees/f8-proposta-lego
git add models/sale_order.py tests/test_estimated_hours.py
git commit -m "feat(sale_order): _qualif_schedule_rows helper + test (F8.14)"
```

### Task 13: Add subline + bulk + autofill + apply propagation tests

**Files:**
- Modify: `tests/test_estimated_hours.py`

- [ ] **Step 1: Append 5 tests**

```python
    def test_cycle_type_default_propagates_to_subline_via_onchange(self):
        """_onchange_cycle_type_defaults seta estimated_hours = type.estimated_hours."""
        line = self.env["afr.qualificacao.configurator.qd.line"].new({
            "cycle_type_id": self.cycle_cmax.id,
            "qty": 1,
        })
        line._onchange_cycle_type_defaults()
        self.assertAlmostEqual(line.estimated_hours, 2.0)

    def test_subline_override_persists_to_so_line(self):
        """Override estimated_hours na subline propaga via action_apply."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id,
                "qty": 1,
                "estimated_hours": 5.0,  # override (type is 2.0)
            })],
        })
        wiz.action_apply()
        qd_line = so.order_line.filtered(
            lambda l: l.qualification_type == "performance"
        )
        self.assertAlmostEqual(qd_line.estimated_hours, 5.0)

    def test_fallback_to_type_when_subline_zero(self):
        """Sem override (subline.estimated_hours=0), apply usa type.estimated_hours."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id,
                "qty": 1,
                # no estimated_hours override
            })],
        })
        wiz.action_apply()
        qd_line = so.order_line.filtered(
            lambda l: l.qualification_type == "performance"
        )
        self.assertAlmostEqual(qd_line.estimated_hours, 2.0)

    def test_template_autofill_propagates_estimated_hours(self):
        """_onchange_config_template usa template.line.estimated_hours."""
        tpl = self.env["afr.qualificacao.config.template"].create({
            "name": "TPL Test F8.14",
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id,
                "qty": 1,
                "estimated_hours": 7.5,  # template override
            })],
        })
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": self.env["sale.order"].create({
                "partner_id": self.partner.id,
            }).id,
        })
        eq = self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
        })
        eq.config_template_id = tpl
        eq._onchange_config_template()
        self.assertEqual(len(eq.qd_line_ids), 1)
        self.assertAlmostEqual(eq.qd_line_ids.estimated_hours, 7.5)

    def test_bulk_wizard_propagates_estimated_hours(self):
        """Bulk wizard.action_apply propaga estimated_hours pra equipment_line."""
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": self.env["sale.order"].create({
                "partner_id": self.partner.id,
            }).id,
        })
        bulk = self.env["afr.qualificacao.configurator.bulk"].create({
            "parent_wizard_id": wiz.id,
            "equipment_ids": [(6, 0, [self.equip1.id, self.equip2.id])],
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id,
                "qty": 1,
                "estimated_hours": 9.0,
            })],
        })
        bulk.action_apply()
        for eq in wiz.equipment_line_ids:
            self.assertAlmostEqual(eq.qd_line_ids.estimated_hours, 9.0)
```

- [ ] **Step 2: Sync + run (expect 8 PASS — Tasks 6-9 already implemented)**

If `test_template_autofill_propagates_estimated_hours` fails because the template line `estimated_hours` was passed but not stored, verify Task 4 added field correctly.

- [ ] **Step 3: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git checkout -- tests/
cd .claude/worktrees/f8-proposta-lego
git add tests/test_estimated_hours.py
git commit -m "test(estimated_hours): 5 more tests covering propagation paths (F8.14)"
```

---

## Phase 4 — Template form view

### Task 14: Add Horas column to template form

**Files:**
- Modify: `views/config_template_views.xml`

- [ ] **Step 1: Add column in 3 tabs (QO ~line 47, QD ~line 57, Calib ~line 67)**

After `<field name="description"/>` in each tab, add:

```xml
                                    <field name="estimated_hours"/>
```

- [ ] **Step 2: XML syntax check + commit**

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('views/config_template_views.xml')"
git add views/config_template_views.xml
git commit -m "feat(config-template-view): coluna Horas nas 3 abas QD/QO/Calib (F8.14)"
```

---

## Phase 5 — PDF report

### Task 15: CSS additions (tfoot + qq-equip-schedule)

**Files:**
- Modify: `reports/quotation_template.xml` (CSS block ~line 100-200)

- [ ] **Step 1: Add to `.qq-table` definition area**

After the existing `.qq-table td { ... }` block:

```css
                    .qq-table tfoot td {
                        border-top: 2px solid #333;
                        font-weight: bold;
                        padding: 6px 10px;
                        background-color: #fafafa;
                    }
                    .qq-equip-schedule {
                        border-top: 1px solid #999;
                        padding-top: 8px;
                        margin-top: 10px;
                        font-size: 14px;
                        color: #222;
                        text-align: right;
                    }
```

- [ ] **Step 2: XML syntax check + commit**

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('reports/quotation_template.xml')"
git add reports/quotation_template.xml
git commit -m "style(report): tfoot subtotal CSS + qq-equip-schedule (F8.14)"
```

### Task 16: Add <tfoot> to QO + QD tables in Equipment Scope

**Files:**
- Modify: `reports/quotation_template.xml` (lines 360-376 QO, 382-398 QD)

- [ ] **Step 1: QO table — add tfoot after `</t>` closing the foreach**

After the existing rows close (`</t>` ending the foreach loop, right before `</table>`):

```xml
                                                <t t-set="qo_total_qty" t-value="sum(r['qty'] or 0 for r in qo_rows)"/>
                                                <t t-set="qo_total_hours" t-value="doc._qualif_section_hours(eq['equipment'], 'qo')"/>
                                                <tfoot>
                                                    <tr>
                                                        <td t-esc="qo_total_qty"/>
                                                        <td colspan="2">Total: <t t-esc="len(qo_rows)"/> ciclo(s)</td>
                                                        <td style="text-align: right;">
                                                            <t t-esc="'%.1f h · %.2f dias' % (qo_total_hours, qo_total_hours / 8.0)"/>
                                                        </td>
                                                    </tr>
                                                </tfoot>
```

- [ ] **Step 2: QD table — same pattern (`'qd'` phase)**

```xml
                                                <t t-set="qd_total_qty" t-value="sum(r['qty'] or 0 for r in qd_rows)"/>
                                                <t t-set="qd_total_hours" t-value="doc._qualif_section_hours(eq['equipment'], 'qd')"/>
                                                <tfoot>
                                                    <tr>
                                                        <td t-esc="qd_total_qty"/>
                                                        <td colspan="2">Total: <t t-esc="len(qd_rows)"/> ciclo(s)</td>
                                                        <td style="text-align: right;">
                                                            <t t-esc="'%.1f h · %.2f dias' % (qd_total_hours, qd_total_hours / 8.0)"/>
                                                        </td>
                                                    </tr>
                                                </tfoot>
```

- [ ] **Step 3: Add `_qualif_section_hours` helper in `models/sale_order.py`**

After `_qualif_estimated_days`:

```python
    def _qualif_section_hours(self, equipment, phase):
        """F8.14 — soma horas só de uma fase (qo/qd/calibration) por equip.

        Usado pelos tfoots das tabelas QO/QD/Calib inline no Equipment Scope.
        phase ∈ {'qo', 'qd', 'calibration'}.
        """
        self.ensure_one()
        phase_to_qtype = {
            "qo": "operational",
            "qd": "performance",
            "calibration": "calibration",
        }
        qtype = phase_to_qtype.get(phase)
        if not qtype:
            return 0.0
        lines = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and l.equipment_id == equipment
            and l.qualification_type == qtype
        )
        total = 0.0
        for line in lines:
            hours = line.estimated_hours
            if not hours:
                if line.cycle_type_id:
                    hours = line.cycle_type_id.estimated_hours
                elif line.malha_type_id:
                    hours = line.malha_type_id.estimated_hours
            total += (hours or 0.0) * (line.product_uom_qty or 0)
        return total
```

- [ ] **Step 4: XML syntax check + commit**

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('reports/quotation_template.xml')"
python3 -c "import ast; ast.parse(open('models/sale_order.py').read())"
git add reports/quotation_template.xml models/sale_order.py
git commit -m "feat(report): tfoot subtotal horas/dias em tabelas QO/QD do Equipment Scope (F8.14)"
```

### Task 17: Equipment Scope footer (cronograma per equipment)

**Files:**
- Modify: `reports/quotation_template.xml` (after closing `</div>` of qq-equip-card at line ~432)

- [ ] **Step 1: Inside the qq-equip-card, before its closing `</div>`, add footer**

Right after `<!-- F8.10 — subtotal por equipamento removido do escopo... -->` and before `</div>`:

```xml
                                        <t t-set="eq_hours" t-value="doc._qualif_estimated_hours(eq['equipment'])"/>
                                        <t t-if="eq_hours">
                                            <div class="qq-equip-schedule">
                                                <strong>Cronograma estimado:</strong>
                                                <t t-esc="'%.1f dias úteis (%.1f horas — base 8h/dia)' % (eq_hours / 8.0, eq_hours)"/>
                                            </div>
                                        </t>
```

- [ ] **Step 2: XML syntax check + commit**

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('reports/quotation_template.xml')"
git add reports/quotation_template.xml
git commit -m "feat(report): rodapé Cronograma estimado por equipamento no Equipment Scope (F8.14)"
```

### Task 18: Add <tfoot> to cycle_specs block table

**Files:**
- Modify: `reports/quotation_template.xml` (cycle_specs block ~line 448-465)

- [ ] **Step 1: Add tfoot to the cycle_specs table**

Right before `</table>` (line ~465):

```xml
                                        <t t-set="cs_total_qty" t-value="sum(r['qty'] or 0 for r in cs['rows'])"/>
                                        <tfoot>
                                            <tr>
                                                <td t-esc="cs_total_qty"/>
                                                <td colspan="4">Total: <t t-esc="len(cs['rows'])"/> ciclo(s)</td>
                                            </tr>
                                        </tfoot>
```

(No horas/dias here — cycle_specs is technical specs only, hours aggregation happens in Equipment Scope footer.)

- [ ] **Step 2: XML syntax check + commit**

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('reports/quotation_template.xml')"
git add reports/quotation_template.xml
git commit -m "feat(report): tfoot total ciclos em cycle_specs block (F8.14)"
```

### Task 19: New block_kind 'schedule' — model + handler + QWeb

**Files:**
- Modify: `models/proposal_template.py` (PROPOSAL_BLOCK_KINDS list)
- Modify: `models/proposal_block.py` (handler dict + `_html_schedule`)
- Modify: `reports/quotation_template.xml` (QWeb for schedule block)

- [ ] **Step 1: Extend PROPOSAL_BLOCK_KINDS**

In `models/proposal_template.py`:

```python
PROPOSAL_BLOCK_KINDS = [
    ("static", "Bloco de Texto"),
    ("equipment_scope", "Escopo por Equipamento"),
    ("cycle_specs", "Tabela de Ciclos"),
    ("schedule", "Cronograma Estimado"),
    ("standards_table", "Tabela de Normas"),
    ("financial", "Resumo Financeiro"),
    ("optionals", "Serviços Opcionais"),
    ("acceptance", "Aceite / Assinatura"),
]
```

- [ ] **Step 2: Register handler in `models/proposal_block.py`**

In the handler dict (~line 118):

```python
            "cycle_specs": self._html_cycle_specs,
            "schedule": self._html_schedule,
            "standards_table": self._html_standards,
```

- [ ] **Step 3: Implement `_html_schedule` after `_html_cycle_specs`**

```python
    def _html_schedule(self, order):
        """F8.14 — tabela cronograma equipamento × horas × dias úteis."""
        rows = order._qualif_schedule_rows()
        if not rows:
            return Markup("<p></p>")
        body = [Markup(
            "<table class='qq-table'>"
            "<thead><tr><th>Equipamento</th>"
            "<th style='text-align:right;'>Horas</th>"
            "<th style='text-align:right;'>Dias úteis</th></tr></thead><tbody>"
        )]
        total_h = 0.0
        for r in rows:
            body.append(Markup(
                "<tr><td>%s</td>"
                "<td style='text-align:right;'>%.1f</td>"
                "<td style='text-align:right;'>%.2f</td></tr>"
            ) % (
                escape(r["equipment"].display_name or ""),
                r["hours"], r["days"],
            ))
            total_h += r["hours"]
        body.append(Markup(
            "<tfoot><tr><td><strong>TOTAL</strong></td>"
            "<td style='text-align:right;'><strong>%.1f</strong></td>"
            "<td style='text-align:right;'><strong>%.2f</strong></td></tr></tfoot>"
            "</tbody></table>"
        ) % (total_h, total_h / 8.0 if total_h else 0.0))
        return Markup("").join(body)
```

- [ ] **Step 4: Add QWeb dispatch for `schedule` block in `reports/quotation_template.xml`**

Find the foreach over `proposal_block_ids` and add a `<t t-if="block.block_kind == 'schedule'">` branch parallel to cycle_specs (right after cycle_specs block ~line 468):

```xml
                        <!-- F8.14 — Bloco Cronograma (template-opcional) -->
                        <t t-if="block.block_kind == 'schedule'">
                            <div t-att-class="sec_class">
                                <div class="qq-section-title">
                                    <t t-esc="block.title or 'Cronograma Estimado'"/>
                                </div>
                                <t t-set="rows" t-value="doc._qualif_schedule_rows()"/>
                                <t t-if="rows">
                                    <table class="qq-table">
                                        <thead>
                                            <tr>
                                                <th>Equipamento</th>
                                                <th style="text-align: right; width: 18%;">Horas</th>
                                                <th style="text-align: right; width: 18%;">Dias úteis</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <t t-foreach="rows" t-as="r">
                                                <tr>
                                                    <td t-esc="r['equipment'].display_name"/>
                                                    <td style="text-align: right;" t-esc="'%.1f' % r['hours']"/>
                                                    <td style="text-align: right;" t-esc="'%.2f' % r['days']"/>
                                                </tr>
                                            </t>
                                        </tbody>
                                        <t t-set="total_h" t-value="sum(r['hours'] for r in rows)"/>
                                        <tfoot>
                                            <tr>
                                                <td><strong>TOTAL</strong></td>
                                                <td style="text-align: right;"><strong t-esc="'%.1f' % total_h"/></td>
                                                <td style="text-align: right;"><strong t-esc="'%.2f' % (total_h / 8.0)"/></td>
                                            </tr>
                                        </tfoot>
                                    </table>
                                </t>
                            </div>
                        </t>
```

(Both `_html_schedule` and QWeb branch exist — block can be rendered via either path; QWeb is used by Equipment Scope-style flow, handler is used by `action_edit_block` snapshot.)

- [ ] **Step 5: Syntax check + commit**

```bash
python3 -c "import ast; ast.parse(open('models/proposal_template.py').read())"
python3 -c "import ast; ast.parse(open('models/proposal_block.py').read())"
python3 -c "import xml.etree.ElementTree as ET; ET.parse('reports/quotation_template.xml')"
git add models/proposal_template.py models/proposal_block.py reports/quotation_template.xml
git commit -m "feat(proposal_block): novo block_kind='schedule' + handler + QWeb (F8.14)"
```

### Task 20: Tests for PDF rendering

**Files:**
- Modify: `tests/test_proposal_report.py`

- [ ] **Step 1: Add 3 tests at end of `TestProposalReport` class**

```python
    def test_render_table_tfoot_subtotals(self):
        """Tabelas QO/QD do Equipment Scope têm <tfoot> com 'Total: N ciclo'."""
        self.cycle_cmax.estimated_hours = 2.0
        so = self._built_so()
        html = self._render(so)
        self.assertIn("<tfoot>", html)
        self.assertIn("Total:", html)
        self.assertIn("ciclo", html)

    def test_render_equipment_scope_footer_cronograma(self):
        """Rodapé Equipment Scope mostra 'Cronograma estimado'."""
        self.cycle_cmax.estimated_hours = 2.0
        so = self._built_so()  # 1 ciclo cmax qty=1 → 2h → 0.25 dias
        html = self._render(so)
        self.assertIn("Cronograma estimado", html)
        self.assertIn("dias úteis", html)
        self.assertIn("8h/dia", html)

    def test_render_schedule_block(self):
        """Bloco schedule renderiza tabela equipamento × horas × dias."""
        self.cycle_cmax.estimated_hours = 2.0
        # injeta linha schedule no template
        if not self.proposal_tpl.line_ids.filtered(
            lambda l: l.block_kind == "schedule"
        ):
            self.env["afr.proposal.template.line"].create({
                "template_id": self.proposal_tpl.id,
                "sequence": 95,
                "block_kind": "schedule",
                "title": "Cronograma Estimado",
            })
        so = self._built_so()
        html = self._render(so)
        self.assertIn("Cronograma Estimado", html)
        self.assertIn("Equipamento", html)
        self.assertIn("Dias úteis", html)
        self.assertIn("TOTAL", html)
```

- [ ] **Step 2: Sync + run full suite (expect 225 + 3 + 8 = 236 PASS, 0/0)**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
for f in models/proposal_template.py models/proposal_block.py reports/quotation_template.xml tests/test_proposal_report.py; do cp .claude/worktrees/f8-proposta-lego/$f $f; done
docker exec odoo_engenapp-db-1 psql -U odoo -c "DROP DATABASE qualif_test_f811;" 2>&1 | tail -1
docker exec odoo_engenapp-db-1 psql -U odoo -c "CREATE DATABASE qualif_test_f811 OWNER odoo;" 2>&1 | tail -1
docker exec -e PGPASSWORD=odoo odoo_engenapp-web-1 odoo --stop-after-init --no-http --workers=0 --db_host=db --db_user=odoo --db_password=odoo -d qualif_test_f811 -i afr_qualificacao --test-enable --test-tags=afr_qualificacao --log-level=info 2>&1 | grep -E "tests in|^Ran |0 failed|0 error|FAIL|ERROR" | tail
```
Expected: `0 failed, 0 error(s)` of ~236 tests.

- [ ] **Step 3: Restore submodule main + commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git checkout -- .
cd .claude/worktrees/f8-proposta-lego
git add tests/test_proposal_report.py
git commit -m "test(proposal_report): 3 testes render tfoot + footer + schedule block (F8.14)"
```

---

## Phase 6 — Seeds + manifest

### Task 21: Seed estimated_hours em cycle_type + malha_type

**Files:**
- Modify: `data/cycle_type_seed.xml`
- Modify: `data/malha_type_seed.xml`

- [ ] **Step 1: Cycle seeds**

For each `<record id="cycle_*"...>` in `data/cycle_type_seed.xml`, add:

```xml
        <field name="estimated_hours">0.5</field>
```

Recommended values:
- `cycle_autoclave_bowie_dick`: 0.5
- `cycle_autoclave_vazio_sensiveis`: 1.0
- `cycle_autoclave_carga_mista`: 2.0
- `cycle_autoclave_carga_sensiveis`: 3.0
- Termodesinfectora vazio: 1.0
- Outros: 2.0 default

- [ ] **Step 2: Malha seeds**

For each `<record id="malha_*"...>` in `data/malha_type_seed.xml`:

```xml
        <field name="estimated_hours">4.0</field>
```

Recommended: 4.0 para temperatura, 4.0 pressão, 4.0 umidade.

- [ ] **Step 3: XML syntax check + commit**

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('data/cycle_type_seed.xml')"
python3 -c "import xml.etree.ElementTree as ET; ET.parse('data/malha_type_seed.xml')"
git add data/cycle_type_seed.xml data/malha_type_seed.xml
git commit -m "data(seeds): cycle_type + malha_type estimated_hours iniciais (F8.14)"
```

### Task 22: Bump version + roadmap + TODO

**Files:**
- Modify: `__manifest__.py`
- Modify: `TODO.md`

- [ ] **Step 1: Bump version**

Replace `"version": "16.0.4.12.1"` with `"version": "16.0.4.13.0"`.

- [ ] **Step 2: Add roadmap entry**

After F8.13.1 block in description:

```
            F8.14 (16.0.4.13.0): cronograma estimado — estimated_hours
              em cycle_type/malha_type/type.config + override no
              template/configurator/SO line. Helpers _qualif_estimated_hours,
              _qualif_estimated_days (hours/8), _qualif_schedule_rows,
              _qualif_section_hours. PDF: tfoot subtotal em tabelas QO/QD
              do Equipment Scope, rodapé "Cronograma estimado: N dias úteis"
              por equipamento, novo block_kind='schedule' opcional com
              tabela equipamento × horas × dias.
```

- [ ] **Step 3: TODO.md entry (Feito section, topo)**

```markdown
- 2026-05-23 — F8.14 (16.0.4.13.0): cronograma estimado. Campo `estimated_hours` (Float) em cycle_type + malha_type + type.config + template lines (QD/QO/Calib) + configurator sublines (incl bulk) + sale.order.line. Onchange/autofill/apply cascade. Helpers em sale.order: `_qualif_estimated_hours(equipment=None)`, `_qualif_estimated_days(...)` (/8), `_qualif_schedule_rows()`, `_qualif_section_hours(equip, phase)`. PDF: `<tfoot>` em tabelas QO/QD/cycle_specs (corrige rodapé faltante + breakdown), rodapé "Cronograma estimado: N dias úteis (M horas)" no Equipment Scope, novo block_kind='schedule' (template-opcional) com tabela equipamento×horas×dias e total geral. Seeds iniciais nos cycle/malha types. 11 tests novos (8 estimated_hours + 3 proposal_report).
```

- [ ] **Step 4: Commit**

```bash
git add __manifest__.py TODO.md
git commit -m "feat(afr_qualificacao): F8.14 bump 16.0.4.13.0 + roadmap + TODO (F8.14)"
```

---

## Phase 7 — Final integration + push

### Task 23: Final full suite test

- [ ] **Step 1: Sync ALL worktree mods to submodule main**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
for f in __manifest__.py models/cycle_type.py models/malha_type.py models/type_config.py models/config_template.py models/sale_order_line.py models/sale_order.py models/proposal_block.py models/proposal_template.py wizards/qualificacao_configurator.py wizards/qualificacao_configurator_views.xml views/config_template_views.xml reports/quotation_template.xml data/cycle_type_seed.xml data/malha_type_seed.xml tests/test_estimated_hours.py tests/test_proposal_report.py TODO.md; do cp .claude/worktrees/f8-proposta-lego/$f $f; done
git status -s
```
Expected: ~18 modified files.

- [ ] **Step 2: Drop+create test DB + full run**

```bash
docker exec odoo_engenapp-db-1 psql -U odoo -c "DROP DATABASE qualif_test_f811;" 2>&1 | tail -1
docker exec odoo_engenapp-db-1 psql -U odoo -c "CREATE DATABASE qualif_test_f811 OWNER odoo;" 2>&1 | tail -1
docker exec -e PGPASSWORD=odoo odoo_engenapp-web-1 odoo --stop-after-init --no-http --workers=0 --db_host=db --db_user=odoo --db_password=odoo -d qualif_test_f811 -i afr_qualificacao --test-enable --test-tags=afr_qualificacao --log-level=info 2>&1 | grep -E "^Ran|tests in|0 failed|0 error|FAIL|ERROR" | tail -10
```
Expected: `0 failed, 0 error(s) of 236 tests` (or close, depending on test count).

- [ ] **Step 3: Restore submodule main**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git checkout -- .
git status -s
```
Expected: only `.claude/`, `.vscode/`, `.gitignore` untracked.

### Task 24: Single bundled commit (alternative) OR rely on individual commits + merge

This plan creates ~20 small commits. If preferred, before push you can squash via interactive rebase. Default: keep the granular history (helps bisect later).

- [ ] **Step 1: Verify worktree commit count**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/.claude/worktrees/f8-proposta-lego
git log --oneline 84c4f57..HEAD | wc -l
```
Expected: 15-20 commits.

- [ ] **Step 2: Push worktree branch**

```bash
git push origin worktree-f8-proposta-lego
```

- [ ] **Step 3: Merge into submodule main + push**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git fetch origin
git merge --ff-only worktree-f8-proposta-lego
git push origin main
```

- [ ] **Step 4: Update monorepo pointer + commit + push**

```bash
cd /home/afonso/docker/odoo_engenapp
git add addons/afr_qualificacao
git commit -m "$(cat <<'EOF'
chore: bump afr_qualificacao submodule (F8.14, 16.0.4.13.0)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main
```

- [ ] **Step 5: Report final SHAs**

Output:
- Submodule main: `<sha>`
- Monorepo main: `<sha>`
- Test count: `<N>/0/0`

---

## Notes for Implementer

- **CWD discipline:** all worktree edits in `.claude/worktrees/f8-proposta-lego`. All test runs require sync to submodule main checkout first (container mount `/tmp/wt_addons_f8/afr_qualificacao` symlinked to worktree; the addons_path includes it before `/mnt/extra-addons`). Either path works for tests; the `cp` sync to submodule main is for the FINAL merge step.
- **`docker exec -e PGPASSWORD=odoo`** required; DB connection params not in `odoo.conf`.
- **`--workers=0`** required for test runs (multi-worker fails).
- **Pre-existing baseline:** F8.13.1 baseline = 225 tests, 0/0. After F8.14 expect 225 + 8 (test_estimated_hours) + 3 (test_proposal_report) = 236 tests.
- **Commits SEMPRE via worktree branch.** Submodule main fast-forward merge at end. NEVER edit submodule main directly except as transient test sync.
- **Spec ref:** `docs/superpowers/specs/2026-05-23-f814-cronograma-estimado-design.md` (commit `4a59944`).
