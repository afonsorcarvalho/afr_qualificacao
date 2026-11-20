"""Testes da Task 8 — template TPL-MULTI e seus textos.

O template multi-serviço vira o default das cotações novas e a proposta se
adapta ao que foi cotado (qualificação e/ou grupos de serviço). Em produção
ele é instalado pela migração 16.0.9.3.0; aqui `setUpClass` chama o mesmo
instalador (idempotente) para o teste não depender do bump de versão.
"""

from odoo.tests.common import tagged

from ..hooks import _install_proposal_multi_template

from .common_servico import AfrServicoTestCommon

GRAND_LABEL = "Valor Geral da Proposta"


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestProposalMultiTemplate(AfrServicoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _install_proposal_multi_template(cls.env)
        cls.template = cls.env.ref("afr_qualificacao.proposal_template_multi")
        cls.report = cls.env.ref("sale.action_report_saleorder")
        # Serviços dos grupos SEMEADOS (os fixtures de AfrServicoTestCommon
        # são grupos de teste, sem capítulo no template).
        cls.seeded_calib = cls.env.ref("afr_qualificacao.servico_calib_seladora")
        cls.seeded_nr13 = cls.env.ref("afr_qualificacao.servico_nr13_inspecao")

    # -- helpers -----------------------------------------------------------

    def _seeded_order(self, with_qualif=False):
        order = self._make_order()
        order.proposal_template_id = self.template
        if with_qualif:
            wiz = self.env["afr.qualificacao.configurator"].create({
                "sale_order_id": order.id,
            })
            self.env["afr.qualificacao.configurator.equipment"].create({
                "wizard_id": wiz.id,
                "equipment_id": self.equip1.id,
                "do_qi": True,
            })
            wiz.action_apply()
        self._add_service(order, self.seeded_calib, 3, unit_price=100.0)
        self._add_service(order, self.seeded_nr13, 1, unit_price=2000.0)
        order._seed_proposal_blocks()
        return order

    def _render(self, order):
        html, _ctype = self.report._render_qweb_html(
            self.report.report_name, order.ids
        )
        return html.decode() if isinstance(html, bytes) else html

    # -- instalação --------------------------------------------------------

    def test_template_installed(self):
        self.assertTrue(self.template)
        self.assertEqual(self.template.code, "TPL-MULTI")
        self.assertEqual(len(self.template.line_ids), 24)
        self.assertEqual(self.template.sequence, 1)
        conditions = self.template.line_ids.mapped("applies_when")
        self.assertEqual(conditions.count("always"), 11)
        self.assertEqual(conditions.count("qualification"), 7)
        self.assertEqual(conditions.count("service_group"), 6)
        groups = self.template.line_ids.filtered("service_group_id")
        self.assertEqual(
            set(groups.mapped("service_group_id")),
            {
                self.env.ref("afr_qualificacao.servico_grupo_calibracao"),
                self.env.ref("afr_qualificacao.servico_grupo_nr13"),
                self.env.ref("afr_qualificacao.servico_grupo_vazao"),
            },
        )
        children = self.template.line_ids.filtered("parent_id")
        self.assertEqual(len(children), 6)

    def test_is_default_for_new_quotes(self):
        self.assertEqual(
            self.env["sale.order"]._default_proposal_template(), self.template)
        self.assertEqual(self._make_order().proposal_template_id, self.template)

    def test_old_template_untouched(self):
        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")
        self.assertEqual(len(labquali.line_ids), 17)
        self.assertFalse(
            labquali.line_ids.filtered(lambda l: l.applies_when != "always"))

    def test_idempotent(self):
        lines_before = self.env["afr.proposal.template.line"].search_count([])
        templates_before = self.env["afr.proposal.template"].search_count([])
        _install_proposal_multi_template(self.env)
        self.assertEqual(
            self.env["afr.proposal.template.line"].search_count([]),
            lines_before)
        self.assertEqual(
            self.env["afr.proposal.template"].search_count([]),
            templates_before)

    def test_existing_quote_keeps_template(self):
        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "proposal_template_id": labquali.id,
        })
        order._seed_proposal_blocks()
        blocks = order.proposal_block_ids
        self.assertTrue(blocks)
        _install_proposal_multi_template(self.env)
        self.assertEqual(order.proposal_template_id, labquali)
        self.assertEqual(order.proposal_block_ids, blocks)

    # -- documento ---------------------------------------------------------

    def test_services_only_document(self):
        order = self._seeded_order()
        titles = order._proposal_visible_blocks().mapped("title")
        self.assertIn("Calibração de Instrumentos", titles)
        self.assertIn("NR-13", titles)
        self.assertNotIn("Qualificação Térmica", titles)
        self.assertNotIn("Vazão de Exaustores e Trocas de Ar", titles)
        html = self._render(order)
        self.assertEqual(html.count(GRAND_LABEL), 1)

    def test_mixed_document_order(self):
        order = self._seeded_order(with_qualif=True)
        html = self._render(order)
        qualif = html.index("Qualificação Térmica")
        calib = html.index("Calibração de Instrumentos")
        summary = html.index("Resumo Financeiro")
        self.assertLess(qualif, calib)
        self.assertLess(calib, summary)

    def test_objective_cites_services(self):
        order = self._seeded_order()
        self.assertIn(
            "serviços de Calibração de Instrumentos e NR-13",
            self._render(order))

    def test_provisional_texts_marked(self):
        for xmlid in ("proposal_section_grp_nr13", "proposal_section_grp_vazao"):
            body = self.env.ref("afr_qualificacao.%s" % xmlid).body
            self.assertIn("[REVISAR — texto provisório]", body)

    # -- numeração sem buraco (capítulos que não imprimem) ----------------

    def _printed_numbers(self, order):
        import re
        html = self._render(order)
        toc = re.findall(r'qq-toc-num">\s*([\d.]+)\s*<', html)
        body = re.findall(r'>([\d.]+)</span> — ', html)
        return html, toc, body

    def _assert_no_gap(self, toc, body):
        self.assertTrue(toc)
        self.assertEqual(toc, body)
        roots = [n for n in toc if "." not in n]
        self.assertEqual(roots, [str(i) for i in range(1, len(roots) + 1)])

    def test_services_only_numbering_without_norms_has_no_gap(self):
        order = self._seeded_order()
        self.assertFalse(order.qualif_standard_ids)
        standards = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "standards_table")
        self.assertEqual(len(standards), 1)
        self.assertTrue(standards._is_applicable())
        self.assertNotIn(standards, order._proposal_chapter_blocks())
        self.assertNotIn(standards.id, order._proposal_block_numbering())
        title = standards.title or "Normas Aplicáveis"

        html, toc, body = self._printed_numbers(order)
        self._assert_no_gap(toc, body)
        self.assertNotIn(title, html)
        self.assertEqual(html.count(GRAND_LABEL), 1)

    def test_services_only_numbering_with_norm_has_no_gap(self):
        order = self._seeded_order()
        standard = self.env["afr.qualificacao.standard"].create({
            "code": "TST-001", "name": "Norma de Teste"})
        self.seeded_calib.standard_ids = standard
        order.invalidate_recordset()
        standards = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "standards_table")
        self.assertIn(standards, order._proposal_chapter_blocks())
        title = standards.title or "Normas Aplicáveis"

        html, toc, body = self._printed_numbers(order)
        self._assert_no_gap(toc, body)
        self.assertIn(title, html)
        self.assertEqual(html.count(GRAND_LABEL), 1)
