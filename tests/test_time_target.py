# -*- coding: utf-8 -*-
"""Tempo combinado por equipamento — helper puro + camada ORM."""

from odoo.tests.common import TransactionCase, tagged

from ..models.time_allocation import allocate_hours
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestTimeAllocation(TransactionCase):

    def test_proportional(self):
        self.assertEqual(allocate_hours(12.0, [2.0, 4.0]), [4.0, 8.0])

    def test_quarter_steps_exact_sum(self):
        res = allocate_hours(10.0, [1.0, 1.0, 1.0])
        self.assertAlmostEqual(sum(res), 10.0, places=6)
        for h in res:
            self.assertAlmostEqual((h / 0.25) - round(h / 0.25), 0.0,
                                   places=6)
        # resíduo na maior (empate → primeira): 3,25 + 3,25 + 3,5 ou similar
        self.assertEqual(sorted(res), [3.25, 3.25, 3.5])

    def test_residual_on_largest(self):
        res = allocate_hours(10.0, [1.0, 2.0])
        # 3,333 → 3,25 ; 6,667 → 6,75 ; soma 10
        self.assertEqual(res, [3.25, 6.75])

    def test_zero_weights_equal_split(self):
        self.assertEqual(allocate_hours(6.0, [0.0, 0.0]), [3.0, 3.0])

    def test_empty(self):
        self.assertEqual(allocate_hours(6.0, []), [])


@tagged("post_install", "-at_install")
class TestEquipmentTimeTarget(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _section(self, so, equip):
        return self.env["sale.order.line"].create({
            "order_id": so.id, "display_type": "line_section",
            "name": equip.display_name, "is_qualificacao_managed": True,
            "equipment_id": equip.id, "work_hours_per_day": 8.0,
        })

    def _cycle_line(self, so, equip, qty_cycles, hours, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo", "is_qualificacao_managed": True,
            "qualification_type": "performance", "equipment_id": equip.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": qty_cycles, "estimated_hours": hours,
            "product_uom_qty": qty_cycles * hours, "price_unit": price,
        })

    def test_hours_and_state(self):
        so = self._so()
        section = self._section(so, self.equip1).with_context(
            afr_no_target_autoapply=True)
        self._cycle_line(so, self.equip1, 3, 2.0, 100.0)  # 6h
        self.assertEqual(section.equipment_time_state, "none")
        section.equipment_target_days = 1.5
        self.assertEqual(section.equipment_target_hours, 12.0)
        self.assertEqual(section.equipment_time_state, "drift")
        section.equipment_target_days = 0.75
        self.assertEqual(section.equipment_time_state, "ok")

    def test_qty_gt1_per_cycle_derived(self):
        so = self._so()
        section = self._section(so, self.equip1)
        a = self._cycle_line(so, self.equip1, 3, 2.0, 100.0)  # 6h
        b = self._cycle_line(so, self.equip1, 1, 2.0, 100.0)  # 2h
        section.equipment_target_days = 1.0  # 8h → sem mudança
        section.equipment_target_days = 1.5  # 12h → 9 + 3
        section._apply_equipment_time_target()
        self.assertEqual(a.product_uom_qty, 9.0)
        self.assertEqual(a.estimated_hours, 3.0)
        self.assertEqual(b.product_uom_qty, 3.0)
        self.assertEqual(b.estimated_hours, 3.0)
        self.assertEqual(section.equipment_time_state, "ok")

    def test_without_price_target_price_follows_hours(self):
        so = self._so()
        section = self._section(so, self.equip1)
        line = self._cycle_line(so, self.equip1, 2, 2.0, 100.0)  # 4h, 400
        section.equipment_target_days = 1.0
        section._apply_equipment_time_target()
        self.assertEqual(line.product_uom_qty, 8.0)
        self.assertEqual(line.price_unit, 100.0)
        self.assertEqual(section.equipment_subtotal, 800.0)

    def test_with_price_target_total_unchanged(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self._cycle_line(so, self.equip1, 3, 4.1, 300.0)
        section.equipment_target_price = 10000.0
        section._apply_equipment_target()
        section.equipment_target_days = 2.3  # 18,4h
        section._apply_equipment_time_target()
        base = section._rateio_base_lines()
        self.assertAlmostEqual(sum(base.mapped("product_uom_qty")), 18.4,
                               places=6)
        self.assertEqual(sum(base.mapped("price_subtotal")), 10000.0)
        self.assertEqual(section.equipment_target_state, "ok")
        self.assertEqual(section.equipment_time_state, "ok")

    def test_apply_all(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        section.equipment_target_days = 1.0
        so.action_apply_all_equipment_time_targets()
        self.assertEqual(section.equipment_time_state, "ok")

    def _qs_line(self, so, equip, hours, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.product_qs.id,
            "name": "QS", "is_qualificacao_managed": True,
            "qualification_type": "software", "equipment_id": equip.id,
            "qualif_cycle_qty": 1, "estimated_hours": hours,
            "product_uom_qty": 1.0, "price_unit": price,
        })

    def test_price_target_with_fixed_qty_lines(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self._cycle_line(so, self.equip1, 2, 4.1, 300.0)
        qs = self._qs_line(so, self.equip1, 4.0, 800.0)
        section.equipment_target_price = 9876.54
        section._apply_equipment_target()
        section.equipment_target_days = 3.0
        section._apply_equipment_time_target()
        base = section._rateio_base_lines()
        self.assertEqual(qs.product_uom_qty, 1.0)
        self.assertEqual(round(sum(base.mapped("price_subtotal")), 2),
                         9876.54)
        self.assertEqual(section.equipment_target_state, "ok")
        self.assertEqual(section.equipment_time_state, "ok")

    def test_apply_all_rolls_back_failing_section(self):
        so = self._so()
        bad = self._section(so, self.equip1)
        bad_line = self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        bad_line.discount = 10.0
        bad.equipment_target_price = 500.0
        bad.equipment_target_days = 1.0
        good = self._section(so, self.equip2)
        good_line = self._cycle_line(so, self.equip2, 2, 2.0, 100.0)
        good.equipment_target_days = 1.0
        res = so.action_apply_all_equipment_time_targets()
        self.assertIsInstance(res, dict)  # notificação da falha
        self.assertEqual(bad_line.product_uom_qty, 4.0)
        self.assertEqual(bad_line.estimated_hours, 2.0)
        self.assertEqual(good_line.product_uom_qty, 8.0)
        self.assertEqual(good.equipment_time_state, "ok")

    def test_single_apply_raises_before_writing(self):
        from odoo.exceptions import UserError
        so = self._so()
        section = self._section(so, self.equip1)
        line = self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        line.discount = 10.0
        section.equipment_target_price = 500.0
        section.equipment_target_days = 1.0
        with self.assertRaises(UserError):
            section._apply_equipment_time_target()
        self.assertEqual(line.product_uom_qty, 4.0)

    def test_cycle_line_zero_cycle_qty(self):
        so = self._so()
        section = self._section(so, self.equip1)
        line = self._cycle_line(so, self.equip1, 0, 0.0, 100.0)
        line.write({"product_uom_qty": 3.0, "estimated_hours": 3.0})
        section.equipment_target_days = 0.5
        section._apply_equipment_time_target()
        self.assertEqual(line.product_uom_qty, 4.0)
        self.assertEqual(line.estimated_hours, 4.0)
