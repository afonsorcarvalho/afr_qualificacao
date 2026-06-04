# -*- coding: utf-8 -*-
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestOptionalAccepted(AfrQualificacaoTestCommon):

    def _svc(self):
        return self.env["product.product"].create(
            {"name": "Pasta", "type": "service", "sale_ok": True,
             "list_price": 150.0})

    def _opt_line(self, so, accepted=False, qty=1.0, price=150.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self._svc().id,
            "name": "Opcional Pasta",
            "is_proposal_optional": True,
            "optional_accepted": accepted,
            "optional_qty": qty,
            "price_unit": price,
        })

    def _opt_qualif_line(self, so, accepted, qtype="performance"):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo opcional",
            "is_qualificacao_managed": True,
            "is_proposal_optional": True,
            "optional_accepted": accepted,
            "optional_qty": 1.0,
            "qualification_type": qtype,
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 1,
        })

    def test_optional_not_accepted_qty_zero(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self._opt_line(so, accepted=False, qty=2.0)
        line._sync_optional_qty()
        self.assertEqual(line.product_uom_qty, 0.0)
        self.assertEqual(so.amount_untaxed, 0.0)

    def test_optional_accepted_sums(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self._opt_line(so, accepted=True, qty=2.0, price=150.0)
        line._sync_optional_qty()
        self.assertEqual(line.product_uom_qty, 2.0)
        self.assertEqual(so.amount_untaxed, 300.0)

    def test_confirm_optional_service_no_qualif(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self._opt_line(so, accepted=True, qty=1.0)
        so.action_confirm()
        self.assertGreater(line.product_uom_qty, 0.0)
        self.assertFalse(so.qualificacao_ids)

    def test_confirm_optional_qualif_generates(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self._opt_qualif_line(so, accepted=True)
        so.action_confirm()
        self.assertTrue(so.qualificacao_ids)

    def test_confirm_optional_not_accepted_skipped(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self._opt_qualif_line(so, accepted=False)
        so.action_confirm()
        self.assertFalse(so.qualificacao_ids)

    def test_optional_cycle_qty_is_hours(self):
        # opcional-qualificação de ciclo: qty = qualif_cycle_qty × horas/ciclo,
        # NÃO optional_qty (que é p/ serviços tipo pasta/viagem).
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo opcional 3x2h",
            "is_qualificacao_managed": True,
            "is_proposal_optional": True,
            "optional_accepted": True,
            "optional_qty": 1.0,
            "qualification_type": "performance",
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 3,
            "estimated_hours": 2.0,
        })
        line._sync_optional_qty()
        self.assertEqual(line.product_uom_qty, 6.0)

    def test_optional_cycle_not_accepted_qty_zero(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo opcional recusado",
            "is_qualificacao_managed": True,
            "is_proposal_optional": True,
            "optional_accepted": False,
            "optional_qty": 1.0,
            "qualification_type": "performance",
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 3,
            "estimated_hours": 2.0,
        })
        line._sync_optional_qty()
        self.assertEqual(line.product_uom_qty, 0.0)

    def test_constraint_optional_qualif_requires_equipment(self):
        from odoo.exceptions import ValidationError
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        with self.assertRaises(ValidationError):
            self.env["sale.order.line"].create({
                "order_id": so.id,
                "product_id": self.cycle_cmax.product_id.id,
                "name": "Ciclo opcional sem equip",
                "is_qualificacao_managed": True,
                "is_proposal_optional": True,
                "optional_accepted": True,
                "qualification_type": "performance",
                "cycle_type_id": self.cycle_cmax.id,
            })
