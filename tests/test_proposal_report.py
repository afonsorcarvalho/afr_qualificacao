"""Testes F8.3 — relatório de cotação percorrendo os blocos LEGO.

Cobre:
- o report percorre proposal_block_ids e renderiza blocos static;
- expressões {{ ... }} resolvidas com dados do cliente;
- bloco dinâmico cycle_specs renderiza as specs técnicas;
- fallback para o layout fixo quando a SO não tem blocos.
"""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestProposalReport(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cycle_cmax.write({
            "temperature": "134°C",
            "duration": "7 min",
            "load_type": "com_carga",
        })
        cls.proposal_tpl = cls.env.ref(
            "afr_qualificacao.proposal_template_labquali"
        )
        # F8.8 — cycle_specs removido do seed default; injeta linha pros
        # tests que validam render do bloco (test_render_cycle_specs_block).
        if not cls.proposal_tpl.line_ids.filtered(
            lambda l: l.block_kind == "cycle_specs"
        ):
            cls.env["afr.proposal.template.line"].create({
                "template_id": cls.proposal_tpl.id,
                "sequence": 75,
                "block_kind": "cycle_specs",
                "title": "Tabela Resumo de Ciclos",
            })
        cls.report = cls.env.ref("sale.action_report_saleorder")

    def _built_so(self, with_blocks=True):
        """Cria SO + configura equip via wizard. with_blocks controla seed."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        so.proposal_template_id = (
            self.proposal_tpl if with_blocks else False
        )
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 1}),
            ],
        })
        wiz.action_apply()
        return so

    def _render(self, so):
        html, _ctype = self.report._render_qweb_html(
            self.report.report_name, so.ids
        )
        return html.decode() if isinstance(html, bytes) else html

    def test_render_walks_static_blocks(self):
        """Report exibe os títulos dos blocos static do template."""
        so = self._built_so()
        self.assertTrue(so.proposal_block_ids)
        html = self._render(so)
        self.assertIn("Objetivo", html)
        self.assertIn("Metodologia", html)

    def test_render_resolves_tokens(self):
        """Expressão {{ partner.name }} do bloco resolve com o cliente."""
        so = self._built_so()
        html = self._render(so)
        self.assertIn(self.partner.name, html)

    def test_render_cycle_specs_block(self):
        """Bloco cycle_specs renderiza temperatura/tempo do tipo de ciclo."""
        so = self._built_so()
        html = self._render(so)
        # título do bloco cycle_specs = rótulo do tipo ("Tabela Resumo de Ciclos")
        self.assertIn("Tabela Resumo de Ciclos", html)
        self.assertIn("134°C", html)

    def test_render_falls_back_without_blocks(self):
        """SO de qualificação sem blocos cai no layout fixo (Sumário)."""
        so = self._built_so(with_blocks=False)
        self.assertFalse(so.proposal_block_ids)
        html = self._render(so)
        self.assertIn("PROPOSTA TÉCNICO-COMERCIAL", html)
        self.assertIn("Sumário Executivo", html)

    def test_page_break_controls_section_class(self):
        """F8.6 — bloco sem page_break usa classe qq-section-cont (continua)."""
        so = self._built_so()
        so.proposal_block_ids.write({"page_break": False})
        html = self._render(so)
        self.assertIn("qq-section-cont", html)

    def test_excluded_block_not_rendered(self):
        """Bloco com included=False é omitido do PDF."""
        so = self._built_so()
        objetivo = so.proposal_block_ids.filtered(
            lambda b: b.title == "Objetivo"
        )
        objetivo.included = False
        objetivo.body = "<p>MARCADOR_UNICO_OMITIDO</p>"
        html = self._render(so)
        self.assertNotIn("MARCADOR_UNICO_OMITIDO", html)

    def test_render_table_tfoot_subtotals(self):
        """Tabelas QO/QD do Equipment Scope têm <tfoot> com 'Total: N ciclo'."""
        self.cycle_cmax.estimated_hours = 2.0
        so = self._built_so()
        html = self._render(so)
        self.assertIn("<tfoot>", html)
        self.assertIn("Total:", html)
        self.assertIn("ciclo", html)

    def test_render_equipment_scope_omits_cronograma_footer(self):
        """Rodapé Equipment Scope NÃO mostra cronograma (movido para bloco schedule)."""
        self.cycle_cmax.estimated_hours = 2.0
        so = self._built_so()
        html = self._render(so)
        self.assertNotIn("qq-equip-schedule", html)

    def test_render_schedule_block(self):
        """Bloco schedule renderiza tabela equipamento × horas × dias."""
        self.cycle_cmax.estimated_hours = 2.0
        # injeta linha schedule no template
        if not self.proposal_tpl.line_ids.filtered(
            lambda l: l.block_kind == "schedule"
        ):
            self.env["afr.proposal.template.line"].create({
                "template_id": self.proposal_tpl.id,
                "sequence": 95,
                "block_kind": "schedule",
                "title": "Cronograma Estimado",
            })
        so = self._built_so()
        html = self._render(so)
        self.assertIn("Cronograma Estimado", html)
        self.assertIn("Equipamento", html)
        self.assertIn("Dias úteis", html)
        self.assertIn("TOTAL", html)
