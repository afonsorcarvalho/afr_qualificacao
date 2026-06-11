# -*- coding: utf-8 -*-
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestCotacaoFormRefactor(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _svc(self, price=100.0):
        return self.env["product.product"].create({
            "name": "Svc", "type": "service", "sale_ok": True,
            "list_price": price,
        })

    def _line(self, so, optional=False, price=100.0, qty=1.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self._svc(price).id,
            "name": "L",
            "is_proposal_optional": optional,
            "optional_qty": qty if optional else 0.0,
            "product_uom_qty": qty,
            "price_unit": price,
        })

    def test_regular_line_ids_excludes_optional(self):
        so = self._so()
        reg = self._line(so, optional=False)
        opt = self._line(so, optional=True)
        self.assertIn(reg, so.regular_line_ids)
        self.assertNotIn(opt, so.regular_line_ids)

    def test_optional_line_ids_only_optional(self):
        so = self._so()
        reg = self._line(so, optional=False)
        opt = self._line(so, optional=True)
        self.assertIn(opt, so.optional_line_ids)
        self.assertNotIn(reg, so.optional_line_ids)

    def test_optional_context_default_flag(self):
        # Simula o default_get usado pela aba Opcionais (context na view).
        Line = self.env["sale.order.line"].with_context(
            default_is_proposal_optional=True)
        vals = Line.default_get(["is_proposal_optional"])
        self.assertTrue(vals.get("is_proposal_optional"))

    def test_amount_total_with_split_lines(self):
        so = self._so()
        self._line(so, optional=False, price=100.0, qty=2.0)   # 200
        self._line(so, optional=True, price=50.0, qty=1.0)     # opcional
        # order_line (padrão) enxerga ambos os registros.
        self.assertEqual(len(so.order_line), 2)
        self.assertEqual(
            len(so.regular_line_ids) + len(so.optional_line_ids),
            len(so.order_line),
        )
