# -*- coding: utf-8 -*-
"""Task 11: preço/tempo combinados aplicados ao gravar na própria linha."""

from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestTargetAutoApply(AfrQualificacaoTestCommon):

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

    def _total(self, section):
        return round(sum(section._rateio_base_lines().mapped(
            "price_subtotal")), 2)

    def test_write_price_autoapplies(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)  # 1500
        sec.write({"equipment_target_price": 1125.0})
        self.assertEqual(self._total(sec), 1125.0)
        self.assertEqual(sec.equipment_target_state, "ok")
        self.assertEqual(sec.equipment_apply_state, "ok")
        self.assertFalse(sec.equipment_target_issue)

    def test_write_via_order_o2m(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        so.write({"equipment_target_ids": [
            (1, sec.id, {"equipment_target_price": 1050.0})]})
        self.assertEqual(self._total(sec), 1050.0)

    def test_write_days_rehours_keeps_price(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        line = self._cycle_line(so, self.equip1, 3, 2.0, 100.0)  # 6h
        sec.write({"equipment_target_price": 900.0})
        sec.write({"equipment_target_days": 1.5})  # 12h
        self.assertEqual(line.product_uom_qty, 12.0)
        self.assertEqual(self._total(sec), 900.0)
        self.assertEqual(sec.equipment_time_state, "ok")
        self.assertEqual(sec.equipment_apply_state, "ok")

    def test_discount_no_exception_issue_set(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        line = self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        line.discount = 10.0
        sec.write({"equipment_target_price": 500.0,
                   "equipment_target_days": 1.0})
        self.assertEqual(sec.equipment_target_price, 500.0)
        self.assertEqual(sec.equipment_target_days, 1.0)
        self.assertTrue(sec.equipment_target_issue)
        self.assertIn("desconto", sec.equipment_target_issue)
        self.assertEqual(line.product_uom_qty, 4.0)
        self.assertEqual(line.estimated_hours, 2.0)
        self.assertEqual(sec.equipment_apply_state, "issue")
        # corrigido o desconto, Reaplicar resolve e limpa o motivo
        line.discount = 0.0
        sec.action_reapply_equipment_targets()
        self.assertFalse(sec.equipment_target_issue)
        self.assertEqual(self._total(sec), 500.0)
        self.assertEqual(line.product_uom_qty, 8.0)

    def test_reapply_after_drift(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        line = self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        sec.write({"equipment_target_price": 700.0,
                   "equipment_target_days": 1.0})
        line.write({"price_unit": 50.0, "product_uom_qty": 3.0})
        self.assertEqual(sec.equipment_apply_state, "drift")
        sec.action_reapply_equipment_targets()
        self.assertEqual(sec.equipment_apply_state, "ok")
        self.assertEqual(self._total(sec), 700.0)

    def test_no_targets_state_none(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        self.assertEqual(sec.equipment_apply_state, "none")

    def test_internal_writes_do_not_recurse(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        Line = type(self.env["sale.order.line"])
        calls = []
        orig = Line._auto_apply_equipment_targets

        def spy(self_):
            calls.append(self_.ids)
            return orig(self_)
        Line._auto_apply_equipment_targets = spy
        try:
            sec.write({"equipment_target_price": 300.0,
                       "equipment_target_days": 1.0})
        finally:
            Line._auto_apply_equipment_targets = orig
        self.assertEqual(len(calls), 1)
        self.assertEqual(self._total(sec), 300.0)

    def test_copy_order_keeps_targets_without_breaking(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        sec.write({"equipment_target_price": 400.0,
                   "equipment_target_days": 1.0})
        new = so.copy()
        nsec = new.equipment_target_ids.filtered(
            lambda l: l.equipment_id == self.equip1)
        self.assertEqual(nsec.equipment_target_price, 400.0)
        self.assertEqual(self._total(nsec), 400.0)
        self.assertEqual(nsec.equipment_apply_state, "ok")

    def test_confirmed_order_not_autoapplied(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 2, 2.0, 100.0)
        so.state = "sale"
        sec.write({"equipment_target_price": 123.0})
        self.assertEqual(self._total(sec), 400.0)

    def test_rounding_residue_counts_as_applied(self):
        so = self._so()
        sec = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)  # 7,5h
        sec.write({"equipment_target_price": 1234.0})
        self.assertNotEqual(self._total(sec), 1234.0)  # não atingível
        self.assertLessEqual(abs(self._total(sec) - 1234.0), 0.0375)
        self.assertEqual(sec.equipment_target_state, "ok")
        self.assertEqual(sec.equipment_apply_state, "ok")
