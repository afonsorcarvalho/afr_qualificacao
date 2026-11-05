# -*- coding: utf-8 -*-
"""Desconto geral da cotação (qualif_discount_type / qualif_discount_value).

Base = só `equip_total`. Materializado como linha negativa "Desconto"
(`is_qualif_discount_line`) para amount_untaxed == Valor Geral impresso.
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from .test_scope_table import TestScopeTable


@tagged("post_install", "-at_install")
class TestQualifDiscount(TestScopeTable):
    # _full_so(): equip_total ~ 5048 (preço_unit arredondado a 2 casas por
    # linha -> 5048.01); os testes leem a base real em vez de fixar o valor.

    def _base(self, so):
        return so._qualif_proposal_totals()["equip_total"]

    def _extra(self, so, name, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": name,
            "product_uom_qty": 1.0,
            "price_unit": price,
        })

    def _disc_lines(self, so):
        return so.order_line.filtered("is_qualif_discount_line")

    def _render_pdf(self, so):
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "equipment_scope",
            "included": True,
        })
        report = self.env.ref("sale.action_report_saleorder")
        html, _ct = report._render_qweb_html(report.report_name, so.ids)
        return html.decode("utf-8") if isinstance(html, bytes) else html

    def _render_portal(self, so):
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "equipment_scope",
            "included": True,
        })
        return str(self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": so},
        ))

    # -- cálculo ------------------------------------------------------
    def test_defaults_no_discount(self):
        so = self._full_so()
        self.assertEqual(so.qualif_discount_type, "percent")
        self.assertEqual(so.qualif_discount_value, 0.0)
        self.assertFalse(self._disc_lines(so))
        self.assertEqual(so._qualif_proposal_totals()["discount_amount"], 0.0)

    def test_percent_discount(self):
        so = self._full_so()
        so.write({"qualif_discount_type": "percent",
                  "qualif_discount_value": 10.0})
        lines = self._disc_lines(so)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.name, "Desconto")
        base = self._base(so)
        disc = round(base * 0.10, 2)
        self.assertAlmostEqual(lines.price_subtotal, -disc, places=2)
        self.assertAlmostEqual(so.amount_untaxed, base - disc, places=2)
        totals = so._qualif_proposal_totals()
        self.assertAlmostEqual(totals["discount_amount"], disc, places=2)
        self.assertAlmostEqual(totals["residual"], 0.0, places=2)
        self.assertAlmostEqual(totals["grand_total"], so.amount_untaxed,
                               places=2)

    def test_amount_discount(self):
        so = self._full_so()
        so.write({"qualif_discount_type": "amount",
                  "qualif_discount_value": 300.0})
        self.assertAlmostEqual(self._disc_lines(so).price_subtotal, -300.0,
                               places=2)
        self.assertAlmostEqual(so.amount_untaxed, self._base(so) - 300.0,
                               places=2)

    def test_create_with_discount(self):
        so = self._full_so()
        so2 = so.copy({"qualif_discount_type": "amount",
                       "qualif_discount_value": 100.0})
        self.assertEqual(len(self._disc_lines(so2)), 1)
        self.assertAlmostEqual(so2.amount_untaxed, self._base(so2) - 100.0,
                               places=2)

    def test_zero_removes_line(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        self.assertTrue(self._disc_lines(so))
        so.qualif_discount_value = 0.0
        self.assertFalse(self._disc_lines(so))
        self.assertAlmostEqual(so.amount_untaxed, self._base(so), places=2)

    def test_switch_type_updates_single_line(self):
        so = self._full_so()
        so.write({"qualif_discount_type": "percent",
                  "qualif_discount_value": 10.0})
        so.write({"qualif_discount_type": "amount",
                  "qualif_discount_value": 50.0})
        lines = self._disc_lines(so)
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines.price_subtotal, -50.0, places=2)

    def test_base_change_resyncs_percent(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        qd = so.order_line.filtered(lambda l: l.name == "Carga Mista")
        qd.price_unit = qd.price_unit * 2
        base = self._base(so)
        self.assertAlmostEqual(base, 5048.0 + 948.0, delta=0.05)
        disc = round(base * 0.10, 2)
        self.assertAlmostEqual(self._disc_lines(so).price_subtotal, -disc,
                               places=2)
        self.assertAlmostEqual(so.amount_untaxed, base - disc, places=2)

    def test_base_unlink_does_not_raise_for_amount(self):
        """Re-apply do configurador apaga linhas managed: sem erro."""
        so = self._full_so()
        so.write({"qualif_discount_type": "amount",
                  "qualif_discount_value": 300.0})
        so.order_line.filtered("is_qualificacao_managed").unlink()
        lines = self._disc_lines(so)
        self.assertFalse(lines)  # base 0 -> desconto 0 -> sem linha

    def test_price_not_reset_by_recompute(self):
        """'Atualizar Preços' reprecifica o escopo; o desconto acompanha a
        nova base e nunca vira 0 (pricelist do produto 'Desconto')."""
        so = self._full_so()
        so.qualif_discount_value = 10.0
        so._recompute_prices()
        line = self._disc_lines(so)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.price_subtotal,
                               -round(self._base(so) * 0.10, 2), places=2)
        self.assertLess(line.price_subtotal, 0)

    # -- validação ----------------------------------------------------
    def test_percent_over_100_rejected(self):
        so = self._full_so()
        with self.assertRaises(ValidationError):
            so.write({"qualif_discount_type": "percent",
                      "qualif_discount_value": 100.01})

    def test_negative_rejected(self):
        so = self._full_so()
        with self.assertRaises(ValidationError):
            so.qualif_discount_value = -1.0

    def test_amount_over_base_rejected(self):
        so = self._full_so()
        with self.assertRaises(ValidationError):
            so.write({"qualif_discount_type": "amount",
                      "qualif_discount_value": self._base(so) + 0.01})

    def test_amount_equal_base_ok_and_percent_100_ok(self):
        so = self._full_so()
        so.write({"qualif_discount_type": "percent",
                  "qualif_discount_value": 100.0})
        self.assertAlmostEqual(so.amount_untaxed, 0.0, places=2)
        so.write({"qualif_discount_type": "amount",
                  "qualif_discount_value": self._base(so)})
        self.assertAlmostEqual(so.amount_untaxed, 0.0, places=2)

    def test_not_editable_after_confirm(self):
        so = self._full_so()
        so.state = "sale"
        with self.assertRaises(UserError):
            so.qualif_discount_value = 10.0

    def test_discount_line_cannot_be_deleted_manually(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        with self.assertRaises(UserError):
            self._disc_lines(so).unlink()

    # -- exclusões ----------------------------------------------------
    def test_adicionais_not_discounted_and_line_not_listed(self):
        so = self._full_so()
        self._extra(so, "Despesas de viagem", 1000.0)
        so.write({"qualif_discount_type": "percent",
                  "qualif_discount_value": 10.0})
        adic = so._qualif_additional_lines()
        self.assertEqual([a["name"] for a in adic], ["Despesas de viagem"])
        totals = so._qualif_proposal_totals()
        disc = round(totals["equip_total"] * 0.10, 2)  # adicional fora da base
        self.assertAlmostEqual(totals["discount_amount"], disc, places=2)
        self.assertAlmostEqual(totals["residual"], 0.0, places=2)
        self.assertAlmostEqual(totals["grand_total"],
                               totals["equip_total"] + 1000.0 - disc, places=2)

    def test_discount_line_outside_scope_and_summary(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        line = self._disc_lines(so)
        self.assertNotIn(line, so._qualif_scope_lines(self.equip1))
        for eq in so._qualif_equipment_summary():
            for t in eq["types"]:
                for it in t["items"]:
                    self.assertNotEqual(it["line"], line)
        self.assertFalse(line.is_qualificacao_managed)
        self.assertNotIn(line, so._pending_qualif_lines())

    def test_residual_still_flags_drift_with_discount(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        self.section.equipment_target_price = self.section.equipment_subtotal
        self.section.equipment_target_price = (
            self.section.equipment_subtotal + 50.0)
        totals = so._qualif_proposal_totals()
        self.assertAlmostEqual(
            totals["equip_total"]
            + sum(a["amount"] for a in totals["adicionais"])
            - totals["discount_amount"] + totals["residual"],
            totals["grand_total"], places=2)

    def test_invoiced_with_discount(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        line = self._disc_lines(so)
        self.assertTrue(line.product_id)
        self.assertEqual(line.product_id.invoice_policy, "order")

    # -- renders ------------------------------------------------------
    def _assert_descontos_before_grand(self, html):
        self.assertIn("Descontos", html)
        self.assertLess(html.index("Descontos"),
                        html.index("Valor Geral da Proposta"))
        self.assertIn("Valor total dos Serviços de Qualificação", html)

    def test_grand_total_html_has_descontos(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        html = str(so._qualif_grand_total_html())
        self._assert_descontos_before_grand(html)
        self.assertIn("-", html[html.index("Descontos"):])

    def test_pdf_has_descontos(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        html = self._render_pdf(so)
        self._assert_descontos_before_grand(html)
        self.assertEqual(html.count("Valor Geral da Proposta"), 1)
        # linha do Odoo "Desconto" nunca aparece como adicional
        tail = html[html.index("Valor total dos Serviços de Qualificação"):]
        self.assertEqual(tail.count("Descontos"), 1)

    def test_portal_has_descontos(self):
        so = self._full_so()
        so.qualif_discount_value = 10.0
        self._assert_descontos_before_grand(self._render_portal(so))

    def test_no_descontos_row_when_zero(self):
        so = self._full_so()
        self.assertNotIn("Descontos", str(so._qualif_grand_total_html()))
        self.assertNotIn("Descontos", self._render_pdf(so))
        self.assertNotIn("Descontos", self._render_portal(so))

    def test_breakdown_shown_without_adicionais_when_discount(self):
        so = self._full_so()
        self.assertNotIn("Valor total dos Serviços de Qualificação",
                         str(so._qualif_grand_total_html()))
        so.qualif_discount_value = 5.0
        self.assertIn("Valor total dos Serviços de Qualificação",
                      str(so._qualif_grand_total_html()))

    def test_displayed_grand_total_equals_amount_untaxed(self):
        so = self._full_so()
        self._extra(so, "Pasta", 400.0)
        so.write({"qualif_discount_type": "amount",
                  "qualif_discount_value": 123.45})
        totals = so._qualif_proposal_totals()
        self.assertAlmostEqual(totals["grand_total"], so.amount_untaxed,
                               places=2)
        self.assertAlmostEqual(
            totals["equip_total"] + sum(a["amount"] for a in totals["adicionais"])
            - totals["discount_amount"], so.amount_untaxed, places=2)
