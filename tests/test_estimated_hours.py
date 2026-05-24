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
