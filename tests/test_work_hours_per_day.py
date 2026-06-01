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
        so = self._apply_calib(work_hours=4.0, malha_qty=4)
        self.assertAlmostEqual(so._qualif_estimated_hours(self.equip1), 16.0)
        self.assertAlmostEqual(so._qualif_estimated_days(self.equip1), 4.0)

    def test_fallback_8_when_no_section_or_zero(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertAlmostEqual(so._qualif_work_hours_per_day(self.equip1), 8.0)

    def test_schedule_rows_include_work_hours(self):
        so = self._apply_calib(work_hours=4.0, malha_qty=4)
        rows = so._qualif_schedule_rows()
        self.assertTrue(rows)
        row = rows[0]
        self.assertAlmostEqual(row["work_hours_per_day"], 4.0)
        self.assertAlmostEqual(row["days"], 4.0)
