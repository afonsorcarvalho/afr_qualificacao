"""P3 — corpo QWeb do Relatório Final (HTML; PDF é P4)."""

from odoo.addons.afr_qualificacao.hooks import _seed_relatorio_templates

from .common import AfrQualificacaoTestCommon

REPORT = "afr_qualificacao.action_report_relatorio_corpo"


class TestRelatorioCorpoReport(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_relatorio_templates(cls.env)
        cls.hosp = cls.env.ref("afr_qualificacao.relatorio_template_hosp")

    def setUp(self):
        super().setUp()
        so = self._apply(do_qi=True, qo_cycles=1)
        os = self._confirm_and_generate_os(so)
        rels = os.action_generate_relatorios()
        self.rel = rels.filtered(lambda r: r.equipment_id == self.equip1)
        self.rel.write({
            "template_id": self.hosp.id,
            "data_inicio_ensaios": "2026-09-01",
            "data_fim_ensaios": "2026-09-02",
            "amb_temperatura": "22 a 25 °C",
            "amb_umidade": "45 %UR",
        })
        self.rel.action_reload_template()

    def _render(self, **data):
        html, _t = self.env["ir.actions.report"]._render_qweb_html(
            REPORT, self.rel.ids, data=dict(data))
        return html.decode() if isinstance(html, bytes) else html

    def _block(self, title):
        return self.rel.block_ids.filtered(lambda b: b.title == title)

    def test_report_action_and_paperformat(self):
        report = self.env.ref(REPORT)
        self.assertEqual(report.report_name, "afr_qualificacao.report_relatorio_corpo")
        pf = self.env.ref("afr_qualificacao.paperformat_relatorio_final")
        self.assertEqual(report.paperformat_id, pf)
        self.assertEqual((pf.format, pf.margin_top, pf.margin_bottom), ("A4", 35, 25))

    def test_markers_absent_by_default(self):
        self.assertNotIn("@@RQ:", self._render())

    def test_markers_present_with_flag(self):
        html = self._render(with_markers=True)
        for blk in self.rel._body_blocks():
            self.assertIn("@@RQ:bloco:%d@@" % blk.id, html)
        for anexo in self.rel._anexos_included():
            self.assertIn("@@RQ:anexo:%s@@" % anexo.code, html)
        self.assertIn('class="rq-mark"', html)

    def test_marker_inside_page_break_container(self):
        blk = self._block("Objetivo")
        self.assertTrue(blk.page_break)
        html = self._render(with_markers=True)
        pos = html.index("@@RQ:bloco:%d@@" % blk.id)
        opening = html[html.rindex("<div", 0, pos):pos]
        self.assertIn("rq-page-break", opening)

    def test_anexo_separator_breaks_both_sides(self):
        html = self._render(with_markers=True)
        pos = html.index("@@RQ:anexo:dados@@")
        opening = html[html.rindex("<div", 0, pos):pos]
        self.assertIn("rq-anexo-sep", opening)
        self.assertIn("page-break-after: always", html)

    def test_index_uses_page_map(self):
        blk = self._block("Objetivo")
        html = self._render(page_map={"bloco:%d" % blk.id: 7, "anexo:dados": 23})
        self.assertIn('<span class="rq-toc-page">7</span>', html)
        self.assertIn('<span class="rq-toc-page">23</span>', html)
        self.assertIn("Anexo 2 — Resultados dos Valores Coletados", html)

    def test_index_without_page_map_renders_blank_pages(self):
        html = self._render()
        self.assertIn('<span class="rq-toc-page"></span>', html)

    def test_protocolo_contains_equipment_and_numbers(self):
        html = self._render()
        self.assertIn("TSN-001", html)
        self.assertIn(self.rel._doc_number("PrQT"), html)
        self.assertIn(self.rel._doc_number("ReQM"), html)
        self.assertIn("22 a 25 °C", html)
        self.assertIn("Anexo 1: Protocolo de Qualificação Térmica", html)

    def test_no_unresolved_tokens(self):
        self.assertNotIn("{{", self._render())

    def test_excluded_anexo_not_rendered(self):
        self.rel.anexo_ids.filtered(lambda a: a.code == "micro").included = False
        html = self._render(with_markers=True)
        self.assertNotIn("@@RQ:anexo:micro@@", html)
        self.assertNotIn(self.rel._doc_number("ReQM"), html)
        self.assertIn("Anexo 4: Curvas de Letalidade (F0)", html)

    def test_signatures_list_client(self):
        html = self._render()
        self.assertIn("Quadro de Assinaturas", html)
        self.assertIn(self.rel.partner_id.name, html)

    def test_bad_token_does_not_break_render(self):
        self._block("Conclusão").body = "<p>{{ relatorio.nao_existe }}</p>"
        html = self._render()
        self.assertIn("{{ relatorio.nao_existe }}", html)
        self.assertIn("TSN-001", html)
