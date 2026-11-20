"""Linhas de cotação de serviço (sale.order.line.is_service_managed)."""

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common_servico import AfrServicoTestCommon


@tagged("post_install", "-at_install")
class TestServicoLines(AfrServicoTestCommon):

    def test_line_vals_defaults(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 8)
        self.assertTrue(line.is_service_managed)
        self.assertEqual(line.service_id, self.svc_seladora)
        self.assertEqual(line.service_group_id, self.group_calib)
        self.assertEqual(line.name, self.svc_seladora.name)
        self.assertEqual(line.price_unit, 120)
        self.assertEqual(line.price_subtotal, 960)
        self.assertEqual(line.estimated_hours, 0.5)
        self.assertEqual(line._service_hours(), 4.0)

    def test_service_hours_zero_for_non_service(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.product_qi.id,
            "product_uom_qty": 3,
            "estimated_hours": 2.0,
        })
        self.assertEqual(line._service_hours(), 0.0)

    def test_price_survives_qty_change(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 5, unit_price=100)
        self.assertEqual(line.price_unit, 100)
        line.write({"product_uom_qty": 10})
        self.assertEqual(line.price_unit, 100)
        self.assertEqual(line.price_subtotal, 1000)

    def test_flags(self):
        order = self._make_order()
        self._add_service(order, self.svc_seladora, 2)
        self.assertTrue(order.has_service_lines)
        self.assertFalse(order.has_qualif_lines)
        self.assertTrue(order.is_managed_quote)

    def test_flags_empty_order(self):
        order = self._make_order()
        self.assertFalse(order.has_service_lines)
        self.assertFalse(order.is_managed_quote)

    def test_service_line_cannot_be_qualif(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        with self.assertRaises(ValidationError):
            line.write({"is_qualificacao_managed": True})
        with self.assertRaises(ValidationError):
            line.write({"equipment_id": self.equip1.id})
        with self.assertRaises(ValidationError):
            line.write({"qualification_type": "installation"})

    def test_service_line_requires_service(self):
        order = self._make_order()
        vals = self.env["sale.order.line"]._service_line_vals(
            self.svc_seladora, 1,
        )
        vals.update({"order_id": order.id, "service_id": False})
        with self.assertRaises(ValidationError):
            self.env["sale.order.line"].create(vals)

    def test_groups_ordered(self):
        order = self._make_order()
        self._add_service(order, self.svc_nr13, 1)
        self._add_service(order, self.svc_seladora, 3)
        self.assertEqual(
            order._service_groups(), self.group_calib | self.group_nr13,
        )
        self.assertEqual(
            order._service_groups().mapped("id"),
            [self.group_calib.id, self.group_nr13.id],
        )

    def test_service_lines_filter_and_order(self):
        order = self._make_order()
        l_nr13 = self._add_service(order, self.svc_nr13, 1)
        l_inc = self._add_service(order, self.svc_incubadora, 2)
        l_sel = self._add_service(order, self.svc_seladora, 3)
        # Mesmo grupo e mesma sequence de serviço: desempata por id da linha.
        self.assertEqual(
            order._service_lines().ids, [l_inc.id, l_sel.id, l_nr13.id],
        )
        self.assertEqual(
            order._service_lines(self.group_nr13), l_nr13,
        )

    def test_not_pending_qualif(self):
        order = self._make_order()
        self._add_service(order, self.svc_seladora, 2)
        self.assertFalse(order._pending_qualif_lines())
