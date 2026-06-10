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

    def test_cycle_specs_line_overrides_cycle_type(self):
        """Proposta lê specs da LINHA quando preenchidas; fallback no cycle_type."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        prod = self.cycle_cmax.product_id
        common = {
            "order_id": so.id, "product_id": prod.id,
            "is_qualificacao_managed": True, "qualification_type": "performance",
            "equipment_id": self.equip1.id, "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 1, "estimated_hours": 1.0,
        }
        self.env["sale.order.line"].create({
            **common, "name": "Override",
            "temperature": "999°C", "duration": "99 min", "load_type": "vazio",
        })
        self.env["sale.order.line"].create({**common, "name": "Fallback"})
        specs = so._qualif_cycle_specs()
        rows = specs[0]["rows"]
        # Ordenar por name para garantir ordem determinística
        rows_by_name = {r["name"]: r for r in rows}
        # A linha override usa cycle_type.name como "name" no row, mas
        # podemos verificar pelas specs: uma linha deve ter 999°C e outra 134°C
        temps = {r["temperature"] for r in rows}
        self.assertIn("999°C", temps, "Linha com override deve mostrar 999°C")
        self.assertIn("134°C", temps, "Linha sem override deve cair no cycle_type (134°C)")
        # Verificar a linha override completa
        override_row = next(r for r in rows if r["temperature"] == "999°C")
        self.assertEqual(override_row["duration"], "99 min")
        self.assertEqual(override_row["load_type"], "Câmara Vazia")
        # Verificar a linha fallback
        fallback_row = next(r for r in rows if r["temperature"] == "134°C")
        self.assertEqual(fallback_row["duration"], "7 min")
        self.assertEqual(fallback_row["load_type"], "Com Carga")

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

    def test_configurator_reopen_preserves_specs(self):
        """Apply grava specs na linha SO; _load_from_existing_lines as relê."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id, "qty": 1, "estimated_hours": 1.0,
                "temperature": "777°C", "duration": "77 min", "load_type": "vazio",
            })],
        })
        wiz.action_apply()
        so_line = so.order_line.filtered(
            lambda l: l.cycle_type_id == self.cycle_cmax and not l.display_type)
        self.assertEqual(so_line.temperature, "777°C")
        self.assertEqual(so_line.duration, "77 min")
        self.assertEqual(so_line.load_type, "vazio")
        wiz2 = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz2._load_from_existing_lines()
        rt = wiz2.equipment_line_ids.qd_line_ids.filtered(
            lambda l: l.cycle_type_id == self.cycle_cmax)
        self.assertEqual(rt.temperature, "777°C")
        self.assertEqual(rt.duration, "77 min")
        self.assertEqual(rt.load_type, "vazio")
