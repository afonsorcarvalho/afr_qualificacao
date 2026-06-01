"""Proposta Venda + Calibração — block_kind sales_items + template seed."""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestProposalVendaCalib(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("sale.action_report_saleorder")

    def _render_block(self, so):
        report = self.env.ref("sale.action_report_saleorder")
        html, _c = report._render_qweb_html(report.report_name, so.ids)
        return html.decode() if isinstance(html, bytes) else html

    def _make_so_with_lines(self):
        """SO com 2 linhas de venda comuns (não-qualif, não-opcional)."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": "Venda + Calibração de Termômetro",
            "product_uom_qty": 3,
            "price_unit": 95.0,
        })
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qo.id,
            "name": "Venda + Calibração de Válvula de segurança",
            "product_uom_qty": 2,
            "price_unit": 1350.0,
        })
        return so

    def test_sales_items_renders_lines(self):
        so = self._make_so_with_lines()
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "sequence": 10,
            "block_kind": "sales_items",
            "title": "Equipamentos a serem Calibrados",
            "included": True,
        })
        html = self._render_block(so)
        self.assertIn("Equipamentos a serem Calibrados", html)
        self.assertIn("Venda + Calibração de Termômetro", html)
        self.assertIn("Venda + Calibração de Válvula de segurança", html)
        self.assertIn("285", html)
        self.assertIn("2.700", html.replace(",", "."))

    def test_sales_items_excludes_sections_and_optionals(self):
        so = self._make_so_with_lines()
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": "SEÇÃO_NAO_LISTAR",
        })
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qs.id,
            "name": "OPCIONAL_NAO_LISTAR",
            "product_uom_qty": 1,
            "price_unit": 50.0,
            "is_proposal_optional": True,
        })
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "sequence": 10,
            "block_kind": "sales_items",
            "title": "Itens",
            "included": True,
        })
        html = self._render_block(so)
        self.assertNotIn("SEÇÃO_NAO_LISTAR", html)
        self.assertNotIn("OPCIONAL_NAO_LISTAR", html)
        # garante que o bloco renderizou (senão o assertNotIn passa à toa)
        self.assertIn("Venda + Calibração de Termômetro", html)
        self.assertIn("Venda + Calibração de Válvula de segurança", html)

    def test_template_seed_structure(self):
        tpl = self.env.ref("afr_qualificacao.proposal_template_venda_calib")
        self.assertTrue(tpl)
        kinds = tpl.line_ids.mapped("block_kind")
        self.assertIn("sales_items", kinds)
        sec = self.env.ref("afr_qualificacao.sec_dados_cadastrais")
        self.assertIn(sec, tpl.line_ids.mapped("section_id"))
        sales_seqs = [l.sequence for l in tpl.line_ids if l.block_kind == "sales_items"]
        accept_seqs = [l.sequence for l in tpl.line_ids if l.block_kind == "acceptance"]
        self.assertTrue(sales_seqs and accept_seqs)
        self.assertLess(max(sales_seqs), min(accept_seqs))

    def test_render_contains_institucional(self):
        tpl = self.env.ref("afr_qualificacao.proposal_template_venda_calib")
        so = self._make_so_with_lines()
        so.proposal_template_id = tpl.id
        so._seed_proposal_blocks()
        self.assertTrue(so.proposal_block_ids.filtered("included"),
                        "blocos do template devem ser carregados e incluídos")
        html = self._render_block(so)
        self.assertIn("NBR 16328", html)
        self.assertIn("SEDEX", html)
        self.assertIn("60 dias", html)
        self.assertIn("52.230.210/0001-70", html)

    def test_ensure_company_data_block_idempotent(self):
        from ..hooks import _ensure_company_data_block
        tpl = self.env.ref("afr_qualificacao.proposal_template_labquali")
        sec = self.env.ref("afr_qualificacao.sec_dados_cadastrais")

        def _count():
            return len(tpl.line_ids.filtered(lambda l: l.section_id == sec))

        tpl.line_ids.filtered(lambda l: l.section_id == sec).unlink()
        self.assertEqual(_count(), 0)

        _ensure_company_data_block(self.env)
        self.assertEqual(_count(), 1, "deve adicionar exatamente 1 linha")

        _ensure_company_data_block(self.env)
        self.assertEqual(_count(), 1, "2ª chamada não duplica")
