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
