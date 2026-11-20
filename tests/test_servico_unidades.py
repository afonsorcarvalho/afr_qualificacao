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

    # -- Task 9: aba de unidades e acabamento ------------------------------

    def test_order_unit_o2m(self):
        order, sel, nr = self._confirmed_order(3, 1)
        units = order.service_unit_ids
        self.assertEqual(
            units.mapped("item_number"), [1, 2, 3, 4])
        self.assertEqual(units, sel.service_unit_ids | nr.service_unit_ids)

    def test_order_o2m_unit_with_only_line(self):
        """Unidade criada só com `line_id` aparece na lista da cotação."""
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 3)
        unit = self.env["afr.servico.unidade"].create({"line_id": line.id})
        self.assertEqual(unit.order_id, order)
        self.assertEqual(order.service_unit_ids, unit)
        # Pela aba (comando 0 na O2M da cotação): `order_id` vem do comando.
        order.write({"service_unit_ids": [
            (0, 0, {"line_id": line.id, "tag": "TAG-001"}),
        ]})
        self.assertEqual(len(order.service_unit_ids), 2)
        self.assertEqual(len(line.service_unit_ids), 2)
        self.assertEqual(order.service_units_summary,
                         "1 de 3 unidades identificadas")

    def test_view_loads(self):
        view = self.env.ref(
            "afr_qualificacao.view_sale_order_form_inherit_qualificacao")
        result = self.env["sale.order"].get_view(view_id=view.id)
        self.assertIn('name="service_units"', result["arch"])
        self.assertIn("service_unit_ids", result["arch"])
        self.assertIn("hidden_reason", result["arch"])

    def test_manual_unit_on_confirmed_gets_number(self):
        order, sel, nr = self._confirmed_order(3, 1)
        self.assertEqual(self._numbers(sel), [1, 2, 3])
        # Apaga a unidade pendente de maior número (4) e uma do meio.
        nr.service_unit_ids.unlink()
        sel.service_unit_ids.filtered(lambda u: u.item_number == 2).unlink()
        self.assertEqual(self._numbers(sel), [1, 3])
        unit = self.env["afr.servico.unidade"].create({"line_id": sel.id})
        self.assertEqual(unit.item_number, 5)
        self.assertEqual(order.service_unit_last_number, 5)
        # Apagar não completa nada sozinho.
        unit.unlink()
        self.assertEqual(len(sel.service_unit_ids), 2)

    def test_manual_unit_on_draft_stays_unnumbered(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        unit = self.env["afr.servico.unidade"].create({"line_id": line.id})
        self.assertEqual(unit.item_number, 0)

    def test_lower_qty_and_delete_identified_in_same_write(self):
        order, sel, nr = self._confirmed_order(3, 0)
        for unit in sel.service_unit_ids:
            unit.tag = "TAG-%d" % unit.item_number
        first, second, third = sel.service_unit_ids.sorted("item_number")
        sel.write({
            "product_uom_qty": 1,
            "service_unit_ids": [(2, second.id), (2, third.id)],
        })
        self.assertEqual(sel.service_unit_ids, first)
        self.assertEqual(sel.product_uom_qty, 1)

    def test_lower_qty_still_blocks_when_identified_remain(self):
        order, sel, nr = self._confirmed_order(3, 0)
        for unit in sel.service_unit_ids:
            unit.tag = "TAG-%d" % unit.item_number
        third = sel.service_unit_ids.filtered(lambda u: u.item_number == 3)
        with self.assertRaises(UserError):
            sel.write({
                "product_uom_qty": 1,
                "service_unit_ids": [(2, third.id)],
            })
        self.assertEqual(len(sel.service_unit_ids), 3)
        self.assertEqual(sel.product_uom_qty, 3)

    def test_lower_qty_with_clear_all_command(self):
        """Comando 5 (apagar todas) conta como remoção das unidades."""
        order, sel, nr = self._confirmed_order(3, 0)
        for unit in sel.service_unit_ids:
            unit.tag = "TAG-%d" % unit.item_number
        sel.write({
            "product_uom_qty": 1,
            "service_unit_ids": [(5, 0, 0)],
        })
        # As identificadas saíram; a linha (qtd 1) é completada com uma vazia.
        self.assertEqual(len(sel.service_unit_ids), 1)
        self.assertFalse(sel.service_unit_ids.is_identified)

    def test_summary_singular(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 1)
        self.assertEqual(
            order.service_units_summary, "0 de 1 unidade identificada")
        self.env["afr.servico.unidade"].create({
            "line_id": line.id, "tag": "TAG-001"})
        self.assertEqual(
            order.service_units_summary, "1 de 1 unidade identificada")
        self._add_service(order, self.svc_nr13, 1)
        self.assertEqual(
            order.service_units_summary, "1 de 2 unidades identificadas")

    def test_equipment_onchange_keeps_typed_text(self):
        """Só sobrescreve o campo quando o equipamento tem valor para ele.

        No cadastro só a TAG pode ficar vazia (marca, modelo, série e local
        são obrigatórios), então ela é o campo que prova a regra.
        """
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        self.assertFalse(self.equip1.tag)
        unit = self.env["afr.servico.unidade"].create({
            "line_id": line.id, "tag": "TAG-001",
        })
        unit.equipment_id = self.equip1
        unit._onchange_equipment_id()
        self.assertEqual(unit.tag, "TAG-001")
        self.assertEqual(unit.serial_number, "TSN-001")

        self.equip2.tag = "TAG-002"
        other = self.env["afr.servico.unidade"].create({
            "line_id": line.id, "tag": "TAG-DIGITADA",
        })
        other.equipment_id = self.equip2
        other._onchange_equipment_id()
        self.assertEqual(other.tag, "TAG-002")

    def test_lower_qty_and_delete_identified_order_level(self):
        """Mesmo save do form da cotação: aba Linhas + aba Unidades."""
        order, sel, nr = self._confirmed_order(3, 0)
        for unit in sel.service_unit_ids:
            unit.tag = "TAG-%d" % unit.item_number
        first, second, third = sel.service_unit_ids.sorted("item_number")
        order.write({
            "order_line": [(1, sel.id, {"product_uom_qty": 1})],
            "service_unit_ids": [(2, second.id), (2, third.id)],
        })
        self.assertEqual(sel.service_unit_ids, first)
