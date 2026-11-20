"""Capítulos da proposta: uma regra só para "este bloco imprime capítulo?"
(`afr.proposal.block._prints_chapter`) e a tabela de totais do fim
(`sale.order._proposal_trailing_totals`).
"""

from odoo.tests.common import tagged

from .common_servico import AfrServicoTestCommon

GRAND_LABEL = "Valor Geral da Proposta"
SALES_ITEMS_GRAND = "TOTAL GERAL:"


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestProposalMultiChapters(AfrServicoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("sale.action_report_saleorder")
        cls.tpl_venda = cls.env.ref(
            "afr_qualificacao.proposal_template_venda_calib")
        cls.section = cls.env["afr.proposal.section"].create({
            "name": "Sec Capitulos Teste",
            "body": "<p>Texto.</p>",
        })

    # -- helpers -----------------------------------------------------------

    def _template(self, items):
        """Template com uma linha por item `(block_kind, extra_vals)`."""
        tpl = self.env["afr.proposal.template"].create({
            "name": "Tpl Capitulos Teste",
        })
        for index, (kind, extra) in enumerate(items):
            vals = {
                "template_id": tpl.id,
                "sequence": (index + 1) * 10,
                "block_kind": kind,
            }
            if kind == "static":
                vals["section_id"] = self.section.id
            vals.update(extra)
            self.env["afr.proposal.template.line"].create(vals)
        return tpl

    def _services_order(self, template):
        order = self._make_order()
        order.proposal_template_id = template
        self._add_service(order, self.svc_seladora, 8)
        order._seed_proposal_blocks()
        return order

    def _qualif_order(self, template):
        order = self._make_order()
        order.proposal_template_id = template
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": order.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
        })
        wiz.action_apply()
        order._seed_proposal_blocks()
        return order

    def _block(self, order, title):
        block = order.proposal_block_ids.filtered(lambda b: b.title == title)
        self.assertEqual(len(block), 1, title)
        return block

    def _pdf(self, order):
        html, _ctype = self.report._render_qweb_html(
            self.report.report_name, order.ids)
        return html.decode() if isinstance(html, bytes) else html

    def _portal(self, order):
        return str(self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": order},
        ))

    # -- I5: capítulo forçado vazio e segundo `financial` ------------------

    def test_forced_empty_service_group_not_numbered(self):
        """`service_group` "sempre" de grupo sem linhas: sem número nem índice."""
        tpl = self._template([
            ("static", {"title": "Objetivo"}),
            ("service_group", {
                "title": "Capitulo NR13 vazio",
                "applies_when": "always",
                "service_group_id": self.group_nr13.id,
            }),
            ("static", {"title": "Condicoes"}),
        ])
        order = self._services_order(tpl)
        empty = self._block(order, "Capitulo NR13 vazio")
        self.assertTrue(empty in order._proposal_visible_blocks())
        self.assertFalse(empty._prints_chapter())
        self.assertNotIn(empty, order._proposal_chapter_blocks())
        self.assertNotIn(empty, order._proposal_toc_blocks())
        numbers = order._proposal_block_numbering()
        self.assertEqual(numbers.get(empty.id, ""), "")
        self.assertEqual(numbers[self._block(order, "Condicoes").id], "2")
        self.assertEqual(empty.display_number, "")
        for html in (self._pdf(order), self._portal(order)):
            self.assertNotIn("Capitulo NR13 vazio", html)
            self.assertIn("Condicoes", html)

    def test_service_group_with_lines_is_chapter(self):
        tpl = self._template([
            ("static", {"title": "Objetivo"}),
            ("service_group", {
                "title": "Capitulo Calibracao",
                "applies_when": "always",
                "service_group_id": self.group_calib.id,
            }),
        ])
        order = self._services_order(tpl)
        block = self._block(order, "Capitulo Calibracao")
        self.assertTrue(block._prints_chapter())
        self.assertEqual(order._proposal_block_numbering()[block.id], "2")
        self.assertIn(block, order._proposal_toc_blocks())

    def test_second_financial_not_numbered(self):
        tpl = self._template([
            ("financial", {"title": "Resumo A"}),
            ("financial", {"title": "Resumo B"}),
            ("static", {"title": "Condicoes"}),
        ])
        order = self._services_order(tpl)
        first = self._block(order, "Resumo A")
        second = self._block(order, "Resumo B")
        self.assertEqual(order._proposal_totals_emitter(), first)
        self.assertTrue(first._prints_chapter())
        self.assertFalse(second._prints_chapter())
        numbers = order._proposal_block_numbering()
        self.assertEqual(numbers[first.id], "1")
        self.assertEqual(numbers.get(second.id, ""), "")
        self.assertEqual(numbers[self._block(order, "Condicoes").id], "2")
        self.assertNotIn(second, order._proposal_toc_blocks())
        for html in (self._pdf(order), self._portal(order)):
            self.assertEqual(html.count(GRAND_LABEL), 1)
            self.assertNotIn("Resumo B", html)

    def test_sales_items_without_lines_not_numbered(self):
        tpl = self._template([
            ("sales_items", {"title": "Itens de venda"}),
            ("static", {"title": "Condicoes"}),
        ])
        order = self._make_order()
        order.proposal_template_id = tpl
        order._seed_proposal_blocks()
        block = self._block(order, "Itens de venda")
        self.assertFalse(block._prints_chapter())
        self.assertEqual(
            order._proposal_block_numbering()[
                self._block(order, "Condicoes").id], "1")

    # -- I4: TPL-VENDA-CALIB fecha com o total do `sales_items` ------------

    def _assert_sales_items_total_once(self, order):
        self.assertFalse(order._proposal_totals_emitter())
        self.assertFalse(order._proposal_trailing_totals())
        for html in (self._pdf(order), self._portal(order)):
            self.assertEqual(html.count(GRAND_LABEL), 0)
            self.assertEqual(html.count(SALES_ITEMS_GRAND), 1)

    def test_venda_calib_qualification_prints_one_total(self):
        order = self._qualif_order(self.tpl_venda)
        self.assertTrue(order.has_qualif_lines)
        self._assert_sales_items_total_once(order)

    def test_venda_calib_services_only_prints_one_total(self):
        order = self._services_order(self.tpl_venda)
        self.assertFalse(order.has_qualif_lines)
        self.assertTrue(order.is_managed_quote)
        self._assert_sales_items_total_once(order)

    def test_trailing_totals_kept_without_sales_items(self):
        """Sem emissor e sem `sales_items`: a tabela do fim continua."""
        tpl = self._template([("static", {"title": "Objetivo"})])
        order = self._services_order(tpl)
        self.assertTrue(order._proposal_trailing_totals())
        for html in (self._pdf(order), self._portal(order)):
            self.assertEqual(html.count(GRAND_LABEL), 1)
