"""P3 — corpo QWeb do Relatório Final (HTML; PDF é P4)."""

import re

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
        self.assertIn('class="rq-anexo-num">1<', html)
        self.assertIn('class="rq-anexo-title">Protocolo de Qualificação Térmica<', html)

    def test_no_unresolved_tokens(self):
        self.assertNotIn("{{", self._render())

    def test_excluded_anexo_not_rendered(self):
        self.rel.anexo_ids.filtered(lambda a: a.code == "micro").included = False
        html = self._render(with_markers=True)
        self.assertNotIn("@@RQ:anexo:micro@@", html)
        self.assertNotIn(self.rel._doc_number("ReQM"), html)
        self.assertIn('class="rq-anexo-num">4<', html)
        self.assertIn('class="rq-anexo-title">Curvas de Letalidade (F0)<', html)

    def test_signatures_list_client(self):
        html = self._render()
        self.assertIn("Quadro de Assinaturas", html)
        self.assertIn(self.rel.partner_id.name, html)

    def test_full_render_as_plain_user_does_not_raise(self):
        """Achado 5 (findings review P3 final): o corpo QWeb completo (com
        marcadores) precisa renderizar para um Usuário comum sem
        AccessError — inclusive lendo dados do plano de recursos/engc_os que
        o próprio relatório expõe (instrumentos, certificados, IB, sensores).
        `invalidate_all()` antes do render: cache compartilhado entre
        usuários na mesma transação pularia o ACL check."""
        user = self.env["res.users"].create({
            "name": "Usuário RQ Corpo P3Fix", "login": "usuario.rqcorpo.p3fix.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
            ])],
        })
        Inst = self.env["engc.calibration.instruments"]
        validador = Inst.create({"name": "Validador RQ Corpo", "id_number": "VRQC-01"})
        self.rel.os_id.resource_plan_line_ids.unlink()
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.rel.os_id.id, "resource_role": "validador",
            "instrument_id": validador.id,
        })
        self.env["engc.calibration.instruments.certificates"].create({
            "instrument_id": validador.id, "afr_role": "antes",
            "date_calibration": "2026-08-01", "certificate_number": "CERT-RQ-CORPO-01",
        })
        self.env["afr.relatorio.indicador"].create({
            "relatorio_id": self.rel.id, "tipo": "biologico", "valor_d": 1.5,
        })
        cycle = self.rel.cycle_ids[:1]
        self.assertTrue(cycle, "fixture precisa gerar ao menos 1 ciclo")
        self.env["afr.relatorio.sensor.pos"].create({
            "cycle_id": cycle.id, "canal": "CH001",
        })
        self.env["afr.relatorio.leitura.ib"].create({
            "relatorio_id": self.rel.id, "cycle_id": cycle.id,
        })
        self.env.invalidate_all()
        html, _t = self.env["ir.actions.report"].with_user(user)._render_qweb_html(
            REPORT, self.rel.ids, data={"with_markers": True})
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn("CERT-RQ-CORPO-01", html)

    def test_bad_token_does_not_break_render(self):
        self._block("Conclusão").body = "<p>{{ relatorio.nao_existe }}</p>"
        html = self._render()
        self.assertIn("{{ relatorio.nao_existe }}", html)
        self.assertIn("TSN-001", html)

    def test_cycle_order_uses_relatorio_sort_key(self):
        """P1-M5: ciclos em QO < QD < demais (rank), não por string do
        qualification_type ("calibration" < "operational") nem por
        (sequence, id)."""
        os = self.env["afr.qualificacao.os"].create({
            "tecnico_default_id": self.env["hr.employee"].create(
                {"name": "Técnico Ordem"}).id,
            "date_planned_start": "2026-09-01 12:00:00",
            "date_planned_end": "2026-09-03 18:00:00",
        })
        Cycle = self.env["afr.qualificacao.cycle"]

        def qualif(qtype):
            return self.env["afr.qualificacao"].create({
                "name": "ORD-%s-%s" % (os.id, qtype),
                "equipment_id": self.equip1.id,
                "qualification_type": qtype,
                "os_id": os.id,
                "company_id": os.company_id.id,
            })

        def cycle(q, ctype, seq):
            c = Cycle.create({"qualificacao_id": q.id,
                              "cycle_type_id": ctype.id, "sequence": seq})
            self.env["afr.relatorio.sensor.pos"].create(
                {"cycle_id": c.id, "canal": "CH%03d" % seq})
            return c

        # Criados na ordem "errada" e com sequence invertida de propósito.
        c_cal = cycle(qualif("calibration"), self.cycle_qo_test, 5)
        c_qd = cycle(qualif("performance"), self.cycle_cmax, 10)
        c_qo = cycle(qualif("operational"), self.cycle_qo_test, 30)
        rel = os.action_generate_relatorios().filtered(
            lambda r: r.equipment_id == self.equip1)
        self.assertEqual(rel.cycle_ids, c_cal | c_qd | c_qo)

        labels = dict(self.env["afr.qualificacao"]._fields["qualification_type"]
                      ._description_selection(self.env))
        self.assertEqual(
            [r["etapa"] for r in rel._report_cycle_rows()],
            [labels["operational"], labels["performance"], labels["calibration"]])
        self.assertEqual(
            [t["cycle"] for t in rel._report_sensor_tables()],
            [c_qo.display_name, c_qd.display_name, c_cal.display_name])

    def test_laudo_valor_d_zero_renders_blank(self):
        """Carry-in P3 final: valor_d 0.0 (não informado) sai em branco no
        laudo, não "0"."""
        self.env["afr.relatorio.indicador"].create({
            "relatorio_id": self.rel.id, "tipo": "biologico", "valor_d": 0.0,
            "lote": "LOTE-VD-ZERO", "validade": "2027-01-31", "marca": "Marca VD",
            "modelo_tipo": "Modelo VD", "populacao": "1,0x10^6",
        })
        html = self._render()
        start = html.index("LOTE-VD-ZERO")
        row = html[start:html.index("</tr>", start)]
        self.assertIn("31/01/2027", row)
        self.assertNotIn("<td>0</td>", row)
        self.assertIn("<td></td>", row)

    def test_marker_is_out_of_flow(self):
        """Spike P4-T1: o `.rq-mark` fora do fluxo (position: absolute) não
        desloca o bloco (sem ele, ~16.6 pt por bloco no wkhtmltopdf)."""
        html = self._render(with_markers=True)
        rule = re.search(r"\.rq-mark\s*\{([^}]*)\}", html)
        self.assertTrue(rule)
        self.assertIn("position: absolute", rule.group(1))

    def test_level1_title_zero_padded_and_toc_uses_same_number(self):
        html = self._render()
        self.assertRegex(html, r'class="rq-title-num">0\d<')
        self.assertRegex(html, r'class="rq-toc-num"><a [^>]*>0\d<')

    def test_styles_define_manual_palette_and_boxes(self):
        html = self._render()
        for token in ("#0A3D62", "#F86A30", ".rq-box-warn", ".rq-box-info", "blockquote"):
            self.assertIn(token, html)

    def test_cover_has_identification_table(self):
        html = self._render()
        for label in ("Código", "Revisão", "Emitente", "Cliente"):
            self.assertIn(label, html)

    def test_cover_shows_cover_date_in_emissao_row(self):
        html = self._render(cover_date="02/01/2026")
        self.assertIn("<th>Data de emissão</th><td>02/01/2026</td>", html)

    def test_cover_shows_minuta_as_cover_date(self):
        html = self._render(cover_date="MINUTA")
        self.assertIn("<th>Data de emissão</th><td>MINUTA</td>", html)
