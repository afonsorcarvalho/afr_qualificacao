# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestPortalOptional(AfrQualificacaoTestCommon):

    def _svc(self):
        return self.env["product.product"].create(
            {"name": "Pasta", "type": "service", "sale_ok": True,
             "list_price": 150.0})

    def _so_with_optional(self, accepted=False):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id, "name": "Opt",
            "is_proposal_optional": True, "optional_accepted": accepted,
            "optional_qty": 2.0, "price_unit": 150.0})
        return so, line

    def test_toggle_accepts(self):
        so, line = self._so_with_optional(accepted=False)
        res = so._portal_toggle_optional(line.id, True)
        self.assertTrue(line.optional_accepted)
        self.assertEqual(line.product_uom_qty, 2.0)
        self.assertEqual(res["accepted"], True)
        self.assertEqual(res["amount_total"], so.amount_total)

    def test_toggle_unaccepts(self):
        so, line = self._so_with_optional(accepted=True)
        line._sync_optional_qty()
        so._portal_toggle_optional(line.id, False)
        self.assertFalse(line.optional_accepted)
        self.assertEqual(line.product_uom_qty, 0.0)

    def test_toggle_confirmed_raises(self):
        so, line = self._so_with_optional(accepted=False)
        so.state = "sale"
        with self.assertRaises(UserError):
            so._portal_toggle_optional(line.id, True)
        self.assertFalse(line.optional_accepted)

    def test_toggle_non_optional_raises(self):
        so, _line = self._so_with_optional(accepted=False)
        normal = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id,
            "name": "Normal", "product_uom_qty": 1.0, "price_unit": 150.0})
        with self.assertRaises(UserError):
            so._portal_toggle_optional(normal.id, True)

    def test_toggle_foreign_line_raises(self):
        so1, _l1 = self._so_with_optional(accepted=False)
        so2, l2 = self._so_with_optional(accepted=False)
        with self.assertRaises(UserError):
            so1._portal_toggle_optional(l2.id, True)
