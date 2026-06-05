# -*- coding: utf-8 -*-
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestOptionalRefSubtotal(AfrQualificacaoTestCommon):

    def _svc(self):
        return self.env["product.product"].create(
            {"name": "Pasta", "type": "service", "sale_ok": True,
             "list_price": 150.0})

    def test_ref_subtotal_service_not_accepted(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id, "name": "Opt",
            "is_proposal_optional": True, "optional_accepted": False,
            "optional_qty": 2.0, "price_unit": 150.0})
        line._sync_optional_qty()
        self.assertEqual(line.product_uom_qty, 0.0)
        self.assertEqual(line.optional_ref_subtotal, 300.0)

    def test_ref_subtotal_service_accepted(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id, "name": "Opt",
            "is_proposal_optional": True, "optional_accepted": True,
            "optional_qty": 2.0, "price_unit": 150.0})
        line._sync_optional_qty()
        self.assertEqual(line.optional_ref_subtotal, 300.0)
        self.assertEqual(line.price_subtotal, 300.0)

    def test_ref_subtotal_cycle(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo opt", "is_qualificacao_managed": True,
            "is_proposal_optional": True, "optional_accepted": False,
            "qualification_type": "performance", "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id, "qualif_cycle_qty": 3,
            "estimated_hours": 2.0, "price_unit": 100.0})
        self.assertEqual(line.optional_ref_subtotal, 600.0)

    def test_ref_subtotal_non_optional_zero(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id, "name": "Normal",
            "product_uom_qty": 1.0, "price_unit": 150.0})
        self.assertEqual(line.optional_ref_subtotal, 0.0)
