"""Testa wizard configurador: matriz → linhas SO."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestConfigurator(AfrQualificacaoTestCommon):

    def _build_so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _open_wizard(self, so):
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        wiz._load_from_existing_lines()
        return wiz

    def test_apply_generates_so_lines_with_metadata(self):
        so = self._build_so()
        wiz = self._open_wizard(so)
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 3}),
                (0, 0, {"cycle_type_id": self.cycle_cmin.id, "qty": 2}),
            ],
            "calib_line_ids": [
                (0, 0, {"malha_type_id": self.malha_temp.id, "qty": 5}),
            ],
        })]
        wiz.action_apply()

        lines = so.order_line.filtered("is_qualificacao_managed")
        self.assertEqual(len(lines), 4)  # QI + 2 QD + 1 Calib

        qi = lines.filtered(lambda l: l.qualification_type == "installation")
        self.assertEqual(qi.product_uom_qty, 1)
        self.assertEqual(qi.equipment_id, self.equip1)

        cmax = lines.filtered(lambda l: l.cycle_type_id == self.cycle_cmax)
        self.assertEqual(cmax.product_uom_qty, 3)
        self.assertEqual(cmax.product_id, self.product_qd_cmax)

        temp = lines.filtered(lambda l: l.malha_type_id == self.malha_temp)
        self.assertEqual(temp.product_uom_qty, 5)
        self.assertEqual(temp.product_id, self.product_malha_temp)

    def test_apply_recreates_managed_preserves_manual(self):
        so = self._build_so()
        # linha manual avulsa
        manual = self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "product_uom_qty": 1.0,
            "name": "Visita Tecnica",
        })

        wiz = self._open_wizard(so)
        wiz.equipment_line_ids = [(5, 0, 0), (0, 0, {
            "equipment_id": self.equip1.id,
            "do_qi": True,
        })]
        wiz.action_apply()
        self.assertIn(manual, so.order_line)
        self.assertEqual(len(so.order_line.filtered("is_qualificacao_managed")), 1)

        # Reapply (recria managed; manual preservada)
        wiz2 = self._open_wizard(so)
        wiz2.equipment_line_ids = [(5, 0, 0), (0, 0, {
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "do_qo": True,
        })]
        wiz2.action_apply()
        self.assertIn(manual, so.order_line)
        self.assertEqual(len(so.order_line.filtered("is_qualificacao_managed")), 2)

    def test_load_from_existing_lines_idempotent(self):
        so = self._build_so()
        wiz = self._open_wizard(so)
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 3})],
        })]
        wiz.action_apply()

        # Reabre — wizard deve remontar matriz a partir das linhas
        wiz2 = self._open_wizard(so)
        self.assertEqual(len(wiz2.equipment_line_ids), 1)
        eq_line = wiz2.equipment_line_ids
        self.assertEqual(eq_line.equipment_id, self.equip1)
        self.assertTrue(eq_line.do_qi)
        self.assertEqual(len(eq_line.qd_line_ids), 1)
        self.assertEqual(eq_line.qd_line_ids.qty, 3)

    def test_validation_no_equipments(self):
        so = self._build_so()
        wiz = self._open_wizard(so)
        with self.assertRaises(UserError):
            wiz.action_apply()

    def test_validation_no_qualifs_per_equipment(self):
        so = self._build_so()
        wiz = self._open_wizard(so)
        wiz.equipment_line_ids = [(0, 0, {"equipment_id": self.equip1.id})]
        with self.assertRaises(UserError):
            wiz.action_apply()

    def test_duplicate_equipment_blocked(self):
        so = self._build_so()
        wiz = self._open_wizard(so)
        with self.assertRaises(ValidationError):
            wiz.equipment_line_ids = [
                (0, 0, {"equipment_id": self.equip1.id, "do_qi": True}),
                (0, 0, {"equipment_id": self.equip1.id, "do_qo": True}),
            ]
