# -*- coding: utf-8 -*-
"""Renders da tabela de escopo — PDF, portal e HTML do bloco."""

from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon
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

    def test_pdf_day_forecast_uses_comma_not_dot(self):
        """pt-BR: vírgula no separador decimal — nunca o `.` cru do `%.1f`."""
        html = self._render_pdf(self._full_so())
        self.assertIn("dia(s) de serviço", html)
        self.assertNotIn(".0 dia(s)", html)
        self.assertNotIn(".5 dia(s)", html)

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

    def test_totals_not_duplicated_when_static_frozen_financial_block_present(self):
        """C3: bloco `financial` congelado em `static` ANTES do guard novo.

        Reproduz a base real (afr.proposal.block id=636, SO C26-08-0018):
        um bloco `financial` foi convertido para `static` (snapshot) antes
        do UserError em `action_edit_block` passar a proibir essa
        conversão. O guard antigo só reconhecia `block_kind == 'financial'`
        e deixava esse bloco passar batido — o escopo reimprimia um total
        novo por cima do total antigo congelado no corpo `static`.
        """
        so = self._full_so()
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "static",
            "title": "Resumo Financeiro",
            "included": True,
            "body": "<p>TOTAL GERAL: R$ 10.373,48</p>",
        })
        html = self._render_pdf(so)
        self.assertEqual(html.count("TOTAL GERAL"), 1)


@tagged("post_install", "-at_install")
class TestScopeHtmlBlock(TestScopeTable):

    def _block(self, so, kind="equipment_scope"):
        return self.env["afr.proposal.block"].create({
            "sale_order_id": so.id, "block_kind": kind,
        })

    def test_html_scope_has_table_and_forecast(self):
        so = self._full_so()
        html = str(self._block(so)._html_equipment_scope(so))
        self.assertIn("<table", html)
        self.assertIn("Previsão de", html)
        self.assertIn("Subtotal QI", html)
        self.assertIn("Valor Unitário", html)

    def test_html_scope_day_forecast_uses_comma_not_dot(self):
        """pt-BR: vírgula no separador decimal — nunca o `.` cru do `%.1f`."""
        so = self._full_so()
        html = str(self._block(so)._html_equipment_scope(so))
        self.assertIn("dia(s) de serviço", html)
        self.assertNotIn(".0 dia(s)", html)
        self.assertNotIn(".5 dia(s)", html)

    def test_html_scope_has_cycle_rows(self):
        so = self._full_so()
        html = str(self._block(so)._html_equipment_scope(so))
        self.assertIn("Execução dos ciclos com carga", html)
        self.assertIn(self.cycle_cmax.name, html)

    def test_html_scope_keeps_declined_box(self):
        so = self._full_so()
        decl = self._line(so, self.equip1, "installation", "01", 900.0,
                          name="Verificação recusada")
        decl.write({"part01_declined": True, "product_uom_qty": 0.0})
        html = str(self._block(so)._html_equipment_scope(so))
        self.assertIn("Itens Não Solicitados", html)

    def test_html_financial_uses_new_totals(self):
        so = self._full_so()
        html = str(self._block(so, "financial")._html_financial(so))
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)

    def test_snapshot_to_static_preserves_table(self):
        so = self._full_so()
        block = self._block(so)
        block.action_edit_block()
        self.assertEqual(block.block_kind, "static")
        self.assertIn("Previsão de", str(block.body))

    def test_html_totals_not_duplicated_when_financial_block_present(self):
        """Cotação com `financial` materializado não duplica o total no HTML.

        Simula a concatenação feita pelo consumidor da proposta (DOCX):
        cada bloco incluído contribui com seu snapshot HTML, na ordem —
        aqui, `equipment_scope` seguido de `financial`.
        """
        so = self._full_so()
        financial_block = self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "financial",
            "included": True,
        })
        scope_html = str(self._block(so)._html_equipment_scope(so))
        financial_html = str(financial_block._html_financial(so))
        html = scope_html + financial_html
        self.assertEqual(html.count("TOTAL GERAL DA PROPOSTA"), 1)

    def test_html_scope_emits_totals_when_no_financial_block(self):
        """Sem bloco `financial` materializado, o escopo imprime o total."""
        so = self._full_so()
        html = str(self._block(so)._html_equipment_scope(so))
        self.assertEqual(html.count("TOTAL GERAL DA PROPOSTA"), 1)

    def test_html_scope_skips_totals_when_static_frozen_financial_block_present(self):
        """C3: bloco `financial` congelado em `static` também suprime o total no snapshot.

        Simula a concatenação feita pelo consumidor da proposta (DOCX):
        o snapshot do `equipment_scope` não deve reimprimir "TOTAL GERAL"
        quando já existe um bloco `static` com o título do resumo
        financeiro (caso de dado legado, ver C3 do review da branch).
        """
        so = self._full_so()
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "static",
            "title": "Resumo Financeiro",
            "included": True,
            "body": "<p>TOTAL GERAL: R$ 10.373,48</p>",
        })
        scope_html = str(self._block(so)._html_equipment_scope(so))
        self.assertNotIn("TOTAL GERAL DA PROPOSTA", scope_html)

    def test_html_scope_carries_the_pdf_css_classes(self):
        """Snapshot é reaproveitado sob o mesmo CSS do PDF — classes têm de bater."""
        so = self._full_so()
        html = str(self._block(so)._html_equipment_scope(so))
        for css_class in ("qq-equip-card", "qq-scope-table", "qq-scope-stage",
                          "qq-scope-description", "qq-scope-group-row",
                          "qq-scope-subtotal-row", "qq-scope-footer-row"):
            self.assertIn(css_class, html)

    def test_html_scope_css_classes_survive_the_sanitize_roundtrip(self):
        """`body` é `Html(sanitize=True)` — classes têm de sobreviver ao write().

        `_html_equipment_scope` direto prova só que o gerador emite as
        classes; o PDF/portal reaproveitam o snapshot lendo `block.body`
        de volta do banco, passando pelo sanitizer do campo Html.
        """
        so = self._full_so()
        block = self._block(so)
        block.action_edit_block()
        body = str(block.body)
        for css_class in ("qq-equip-card", "qq-scope-table", "qq-scope-stage",
                          "qq-scope-description", "qq-scope-group-row",
                          "qq-scope-subtotal-row", "qq-scope-footer-row",
                          "qq-scope-list", "qq-cycle-table"):
            self.assertIn(css_class, body)
        self.assertIn("<thead>", body)
        self.assertIn("<tbody>", body)


@tagged("post_install", "-at_install")
class TestScopePortalRender(TestScopeTable):

    def _render_portal(self, so):
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "equipment_scope",
            "included": True,
        })
        html = self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": so},
        )
        return str(html)

    def test_portal_has_stage_column_and_forecast(self):
        html = self._render_portal(self._full_so())
        self.assertIn("lq-scope-stage", html)
        self.assertIn("Previsão de", html)
        self.assertIn("Subtotal QD", html)

    def test_portal_day_forecast_uses_comma_not_dot(self):
        """pt-BR: vírgula no separador decimal — nunca o `.` cru do `%.1f`."""
        html = self._render_portal(self._full_so())
        self.assertIn("dia(s) de serviço", html)
        self.assertNotIn(".0 dia(s)", html)
        self.assertNotIn(".5 dia(s)", html)

    def test_portal_has_cycle_table(self):
        html = self._render_portal(self._full_so())
        self.assertIn("Execução dos ciclos com carga", html)
        self.assertIn(self.cycle_cmax.name, html)

    def test_portal_has_unit_price_and_grand_total(self):
        html = self._render_portal(self._full_so())
        self.assertIn("Valor Unitário", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)

    def test_portal_lists_additionals(self):
        so = self._full_so()
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": "Pasta impressa e envio correio",
            "product_uom_qty": 1.0,
            "price_unit": 400.0,
        })
        html = self._render_portal(so)
        self.assertIn("Pasta impressa e envio correio", html)
        self.assertIn("Total dos Serviços de Qualificação", html)

    def test_portal_totals_not_duplicated_when_financial_block_present(self):
        """Cotação antiga com `financial` materializado não imprime 2 totais no portal.

        C2: o bloco `financial` do portal foi reduzido para só os totais
        (a tabela "Equipamento / Subtotal" saiu — ela vinha de
        `_qualif_equipment_summary()`, que não filtra opcionais/declinadas
        e podia contradizer o total logo abaixo). Confirma as duas pontas:
        o cabeçalho da tabela removida não aparece mais, e o total geral
        (que agora só vem do bloco `equipment_scope`, via
        `_qualif_has_financial_block`) aparece exatamente uma vez.
        """
        so = self._full_so()
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "financial",
            "included": True,
        })
        html = self._render_portal(so)
        self.assertNotIn("<th>Equipamento</th>", html)
        self.assertEqual(html.count("TOTAL GERAL DA PROPOSTA"), 1)

    def test_portal_totals_not_duplicated_when_static_frozen_financial_block_present(self):
        """C3: bloco `financial` congelado em `static` também é reconhecido no portal."""
        so = self._full_so()
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "static",
            "title": "Resumo Financeiro",
            "included": True,
            "body": "<p>TOTAL GERAL: R$ 10.373,48</p>",
        })
        html = self._render_portal(so)
        self.assertEqual(html.count("TOTAL GERAL"), 1)


@tagged("post_install", "-at_install")
class TestTemplateCleanup(AfrQualificacaoTestCommon):
    """Seed do template default (hooks.PROPOSAL_TEMPLATE_LINES).

    NOTA (2026-08-20): esta classe testava o efeito do antigo
    `data/proposal_template_cleanup.xml` (um <delete> reexecutado em todo
    -u), lendo o template JÁ instalado no banco de teste — o que só
    confirmava a mutação, não a fonte. Esse data file foi substituído por
    uma migração one-shot (migrations/16.0.7.0.0/post-migrate.py), que não
    roda durante os testes (só dispara num upgrade real de versão). Testar
    o template instalado neste banco de teste passaria por acidente
    (dependeria de quantas vezes -u já rodou nesta DB e com qual versão).

    O teste honesto e determinístico é sobre a fonte da verdade: a
    constante `PROPOSAL_TEMPLATE_LINES` que o post_init_hook usa para criar
    o template default numa instalação NOVA. Ver também C1 do review da
    branch escopo-tabela-ciclos: o XML `data/proposal_template_seed.xml`
    não é carregado por ninguém — é só referência histórica.
    """

    def test_seed_lines_have_no_financial_or_optionals(self):
        from odoo.addons.afr_qualificacao.hooks import PROPOSAL_TEMPLATE_LINES

        kinds = [line[2] for line in PROPOSAL_TEMPLATE_LINES]
        self.assertNotIn("financial", kinds)
        self.assertNotIn("optionals", kinds)
        self.assertIn("equipment_scope", kinds)

    def test_seed_l14_inherits_the_page_break(self):
        """l14 (responsabilidades) herda a quebra de página que era do l12
        (financial, removido) — senão a seção passaria a colar na anterior.
        """
        from odoo.addons.afr_qualificacao.hooks import PROPOSAL_TEMPLATE_LINES

        by_suffix = {line[0]: line for line in PROPOSAL_TEMPLATE_LINES}
        l14 = by_suffix["l14"]
        self.assertEqual(l14[3], "proposal_section_responsabilidades")
        self.assertTrue(l14[4], "l14.page_break deveria ser True")
