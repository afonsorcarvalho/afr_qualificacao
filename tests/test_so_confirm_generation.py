"""Testa geração ao SO confirm: engc.os + afr.qualificacao + sub-records."""

from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestSoConfirmGeneration(AfrQualificacaoTestCommon):

    def _build_so_with_lines(self, equipment_lines_spec):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, spec) for spec in equipment_lines_spec]
        wiz.action_apply()
        return so

    def test_confirm_creates_one_os_per_equipment(self):
        so = self._build_so_with_lines([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qo": True},
        ])
        so.action_confirm()
        self.assertEqual(so.engc_os_count, 2)
        equips = so.engc_os_ids.mapped("equipment_id")
        self.assertEqual(set(equips.ids), {self.equip1.id, self.equip2.id})

    def test_confirm_creates_qualif_per_equipment_type_pair(self):
        so = self._build_so_with_lines([
            {
                "equipment_id": self.equip1.id,
                "do_qi": True,
                "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 3})],
                "calib_line_ids": [(0, 0, {"malha_type_id": self.malha_temp.id, "qty": 5})],
            },
            {"equipment_id": self.equip2.id, "do_qo": True},
        ])
        so.action_confirm()
        self.assertEqual(so.qualificacao_count, 4)
        types_equip1 = so.qualificacao_ids.filtered(
            lambda q: q.equipment_id == self.equip1
        ).mapped("qualification_type")
        self.assertEqual(set(types_equip1), {"installation", "performance", "calibration"})

    def test_confirm_explodes_cycles_by_qty(self):
        so = self._build_so_with_lines([{
            "equipment_id": self.equip1.id,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 3}),
                (0, 0, {"cycle_type_id": self.cycle_cmin.id, "qty": 2}),
            ],
        }])
        so.action_confirm()
        qd = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "performance")
        self.assertEqual(qd.cycle_count, 5)
        cmax_cycles = qd.cycle_ids.filtered(lambda c: c.cycle_type_id == self.cycle_cmax)
        cmin_cycles = qd.cycle_ids.filtered(lambda c: c.cycle_type_id == self.cycle_cmin)
        self.assertEqual(len(cmax_cycles), 3)
        self.assertEqual(len(cmin_cycles), 2)
        # back-refs nas linhas SO
        self.assertTrue(all(c.sale_order_line_id for c in qd.cycle_ids))

    def test_confirm_explodes_malhas_by_qty(self):
        so = self._build_so_with_lines([{
            "equipment_id": self.equip1.id,
            "calib_line_ids": [
                (0, 0, {"malha_type_id": self.malha_temp.id, "qty": 5}),
                (0, 0, {"malha_type_id": self.malha_press.id, "qty": 2}),
            ],
        }])
        so.action_confirm()
        calib = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "calibration")
        self.assertEqual(calib.malha_count, 7)
        temps = calib.malha_ids.filtered(lambda m: m.malha_type_id == self.malha_temp)
        self.assertEqual(len(temps), 5)
        self.assertEqual(temps[0].sensor_kind_id, self.sensor_temp)

    def test_confirm_back_refs_so_lines(self):
        so = self._build_so_with_lines([{
            "equipment_id": self.equip1.id,
            "do_qi": True,
        }])
        so.action_confirm()
        qi_line = so.order_line.filtered(lambda l: l.qualification_type == "installation")
        self.assertTrue(qi_line.afr_qualificacao_id)
        self.assertEqual(qi_line.afr_qualificacao_id.qualification_type, "installation")
