"""Unidades numeradas das linhas de serviço (afr.servico.unidade)."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common_servico import AfrServicoTestCommon


@tagged("post_install", "-at_install")
class TestServicoUnidades(AfrServicoTestCommon):

    def _confirmed_order(self, sel_qty=3, nr13_qty=1):
        order = self._make_order()
        sel = self._add_service(order, self.svc_seladora, sel_qty)
        nr = self._add_service(order, self.svc_nr13, nr13_qty) if nr13_qty else None
        order.action_confirm()
        return order, sel, nr

    def _numbers(self, line):
        return sorted(line.service_unit_ids.mapped("item_number"))

    def test_draft_units_optional(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 8)
        self.assertEqual(len(line.service_unit_ids), 0)
        self.assertEqual(line.service_unit_count, 0)
        self.assertEqual(
            order.service_units_summary, "0 de 8 unidades identificadas")

    def test_summary_empty_without_service(self):
        order = self._make_order()
        self.assertFalse(order.service_units_summary)

    def test_confirm_fills_and_numbers(self):
        order, sel, nr = self._confirmed_order(3, 1)
        self.assertEqual(len(sel.service_unit_ids), 3)
        self.assertEqual(len(nr.service_unit_ids), 1)
        self.assertEqual(self._numbers(sel), [1, 2, 3])
        self.assertEqual(self._numbers(nr), [4])

    def test_identified_flag(self):
        order, sel, nr = self._confirmed_order(3, 1)
        unit = sel.service_unit_ids[0]
        self.assertFalse(unit.is_identified)
        unit.tag = "TAG-001"
        self.assertTrue(unit.is_identified)
        self.assertEqual(sel.service_unit_identified_count, 1)
        self.assertEqual(
            order.service_units_summary, "1 de 4 unidades identificadas")
        unit.tag = False
        unit.serial_number = "SN-001"
        self.assertTrue(unit.is_identified)

    def test_increase_after_confirm_appends(self):
        order, sel, nr = self._confirmed_order(3, 1)
        old = {u.id: u.item_number for u in sel.service_unit_ids | nr.service_unit_ids}
        sel.product_uom_qty = 5
        self.assertEqual(len(sel.service_unit_ids), 5)
        self.assertEqual(self._numbers(sel), [1, 2, 3, 5, 6])
        for uid, num in old.items():
            self.assertEqual(self.env["afr.servico.unidade"].browse(uid).item_number, num)

    def test_numbers_never_reused(self):
        order, sel, nr = self._confirmed_order(3, 0)
        sel.product_uom_qty = 1
        self.assertEqual(self._numbers(sel), [1])
        sel.product_uom_qty = 3
        self.assertEqual(self._numbers(sel), [1, 4, 5])

    def test_reduce_removes_pending_highest_first(self):
        order, sel, nr = self._confirmed_order(3, 1)
        first = sel.service_unit_ids.filtered(lambda u: u.item_number == 1)
        first.tag = "TAG-001"
        sel.product_uom_qty = 1
        self.assertEqual(sel.service_unit_ids, first)

    def test_reduce_keeps_identified_over_higher_pending(self):
        order, sel, nr = self._confirmed_order(3, 0)
        third = sel.service_unit_ids.filtered(lambda u: u.item_number == 3)
        third.tag = "TAG-003"
        sel.product_uom_qty = 1
        self.assertEqual(sel.service_unit_ids, third)

    def test_reduce_below_identified_blocks(self):
        order, sel, nr = self._confirmed_order(3, 1)
        for unit in sel.service_unit_ids[:2]:
            unit.tag = "TAG-%d" % unit.item_number
        with self.assertRaises(UserError):
            sel.product_uom_qty = 1
        self.assertEqual(len(sel.service_unit_ids), 3)
        self.assertEqual(sel.product_uom_qty, 3)

    def test_reduce_in_draft_removes_pending(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 3)
        Unit = self.env["afr.servico.unidade"]
        keep = Unit.create({"line_id": line.id, "tag": "TAG-001"})
        Unit.create({"line_id": line.id})
        line.product_uom_qty = 1
        self.assertEqual(line.service_unit_ids, keep)

    def test_unlink_line_with_identified_blocks(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        other = self._add_service(order, self.svc_nr13, 1)
        Unit = self.env["afr.servico.unidade"]
        Unit.create({"line_id": line.id, "tag": "TAG-001"})
        Unit.create({"line_id": other.id})
        with self.assertRaises(UserError):
            line.unlink()
        self.assertTrue(line.exists())
        # Só unidade pendente: apaga a linha e leva as unidades junto.
        units = other.service_unit_ids
        other.unlink()
        self.assertFalse(other.exists())
        self.assertFalse(units.exists())

    def test_cancel_draft_reconfirm_keeps_numbers(self):
        order, sel, nr = self._confirmed_order(3, 1)
        before = {u.id: u.item_number for u in order.order_line.service_unit_ids}
        self.assertEqual(len(before), 4)
        order.action_cancel()
        order.action_draft()
        order.action_confirm()
        after = {u.id: u.item_number for u in order.order_line.service_unit_ids}
        self.assertEqual(before, after)

    def test_copy_does_not_carry_units(self):
        order, sel, nr = self._confirmed_order(3, 1)
        new = order.copy()
        new_lines = new._service_lines()
        self.assertEqual(len(new_lines), 2)
        self.assertFalse(new_lines.service_unit_ids)
        self.assertEqual(new.service_units_summary, "0 de 4 unidades identificadas")

    def test_more_units_than_qty_blocked(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 1)
        Unit = self.env["afr.servico.unidade"]
        Unit.create({"line_id": line.id})
        with self.assertRaises(ValidationError):
            Unit.create({"line_id": line.id})

    def test_equipment_onchange_fills(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        unit = self.env["afr.servico.unidade"].create({"line_id": line.id})
        unit.equipment_id = self.equip1
        unit._onchange_equipment_id()
        self.assertEqual(unit.serial_number, "TSN-001")
        self.assertEqual(unit.model, "TestModel1")
        self.assertEqual(unit.marca, self.marca.name)
        self.assertEqual(unit.location, self.location.name)
        self.assertTrue(unit.is_identified)

    def test_group_and_line_order_agree_on_ties(self):
        """Grupos com a mesma sequence: mesma ordem em grupos e linhas."""
        self.group_nr13.sequence = self.group_calib.sequence
        self.group_calib.name = "Zzz Calibração"  # nome desempataria ao contrário
        order = self._make_order()
        self._add_service(order, self.svc_nr13, 1)
        self._add_service(order, self.svc_seladora, 1)
        self.assertEqual(
            order._service_groups(),
            order._service_lines().mapped("service_group_id"),
        )
        self.assertEqual(order._service_groups()[0], self.group_calib)
