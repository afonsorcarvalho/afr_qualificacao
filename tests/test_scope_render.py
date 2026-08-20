# -*- coding: utf-8 -*-
"""Renders da tabela de escopo — PDF, portal e HTML do bloco."""

from odoo.tests.common import tagged
from .test_scope_table import TestScopeTable


@tagged("post_install", "-at_install")
class TestScopePdfRender(TestScopeTable):

    def _render_pdf(self, so):
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "equipment_scope",
            "included": True,
        })
        report = self.env.ref("sale.action_report_saleorder")
        html, _ct = report._render_qweb_html(report.report_name, so.ids)
        return html.decode("utf-8") if isinstance(html, bytes) else html

    def _extra(self, so, name, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": name,
            "product_uom_qty": 1.0,
            "price_unit": price,
        })

    def test_pdf_has_group_labels(self):
        html = self._render_pdf(self._full_so())
        self.assertIn("QI (primeira parte)", html)
        self.assertIn("QO (primeira parte)", html)
        self.assertIn("QO (segunda parte)", html)

    def test_pdf_has_day_forecast_and_subtotal_rows(self):
        html = self._render_pdf(self._full_so())
        self.assertIn("Previsão de", html)
        self.assertIn("dia(s) de serviço", html)
        self.assertIn("Subtotal QI", html)
        self.assertIn("Subtotal QO", html)
        self.assertIn("Subtotal QD", html)

    def test_pdf_has_cycle_table_headers(self):
        html = self._render_pdf(self._full_so())
        self.assertIn("Execução dos ciclos com carga", html)
        self.assertIn("Quantidade", html)
        self.assertIn(self.cycle_cmax.name, html)

    def test_pdf_has_unit_price_footer(self):
        html = self._render_pdf(self._full_so())
        self.assertIn("Valor Unitário", html)

    def test_pdf_lists_additionals_in_totals(self):
        so = self._full_so()
        self._extra(so, "Despesas de viagem", 1000.0)
        html = self._render_pdf(so)
        self.assertIn("Total dos Serviços de Qualificação", html)
        self.assertIn("Despesas de viagem", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)

    def test_pdf_totals_without_additionals_is_single_line(self):
        html = self._render_pdf(self._full_so())
        self.assertNotIn("Total dos Serviços de Qualificação", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)
        self.assertEqual(html.count("TOTAL GERAL DA PROPOSTA"), 1)

    def test_totals_not_duplicated_when_financial_block_present(self):
        """Cotação antiga com `financial` materializado não imprime 2 totais."""
        so = self._full_so()
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "financial",
            "included": True,
        })
        html = self._render_pdf(so)
        self.assertEqual(html.count("TOTAL GERAL DA PROPOSTA"), 1)
