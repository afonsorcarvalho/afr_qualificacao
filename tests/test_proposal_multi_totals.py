"""Testes da Task 6 — resumo financeiro multi-serviço e emissor único de totais.

Garante que (1) as linhas do resumo (PDF, portal e banner do form) saem de
uma única fonte, `_qualif_total_rows()`; (2) as linhas de serviço entram no
resumo sem duplicar nem virar "Outros"; (3) a tabela de totais é impressa
exatamente uma vez em qualquer combinação de template e conteúdo.
"""

from odoo.tests.common import tagged

from .common_servico import AfrServicoTestCommon

QUALIF_LABEL = "Valor total dos Serviços de Qualificação"
GRAND_LABEL = "Valor Geral da Proposta"


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestProposalMultiTotals(AfrServicoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("sale.action_report_saleorder")
        cls.product_trip = cls.env["product.product"].create({
            "name": "Test Despesas", "type": "service",
            "invoice_policy": "delivery", "list_price": 500,
        })

    # -- helpers -----------------------------------------------------------

    def _qualif_order(self, template=None):
        order = self._make_order()
        if template:
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
        return order

    def _services_order(self, template=None):
        order = self._make_order()
        if template:
            order.proposal_template_id = template
        self._add_service(order, self.svc_seladora, 8)
        return order

    def _manual_line(self, order, name, price, **extra):
        vals = {
            "order_id": order.id,
            "product_id": self.product_trip.id,
            "name": name,
            "product_uom_qty": 1.0,
            "price_unit": price,
        }
        vals.update(extra)
        return self.env["sale.order.line"].create(vals)

    def _template(self, kinds):
        """Template só com linhas de bloco dinâmico, na ordem de `kinds`.

        `kinds`: lista de `block_kind` ou tuplas `(block_kind, extra_vals)`.
        """
        tpl = self.env["afr.proposal.template"].create({
            "name": "Tpl Totais Teste",
        })
        for index, item in enumerate(kinds):
            kind, extra = item if isinstance(item, tuple) else (item, {})
            vals = {
                "template_id": tpl.id,
                "sequence": (index + 1) * 10,
                "block_kind": kind,
            }
            vals.update(extra)
            self.env["afr.proposal.template.line"].create(vals)
        return tpl

    def _seeded(self, order):
        order._seed_proposal_blocks()
        return order

    def _render(self, order):
        html, _ctype = self.report._render_qweb_html(
            self.report.report_name, order.ids
        )
        return html.decode() if isinstance(html, bytes) else html

    # -- linhas do resumo --------------------------------------------------

    def test_rows_multi_front(self):
        order = self._qualif_order()
        qualif_value = order.amount_untaxed
        self.assertGreater(qualif_value, 0)
        self._add_service(order, self.svc_seladora, 8)
        self._add_service(order, self.svc_nr13, 1)
        self._manual_line(order, "Despesas de viagem", 500.0)

        self.assertEqual(order._qualif_total_rows(), [
            (QUALIF_LABEL, qualif_value),
            ("Calibração de Instrumentos", 960.0),
            ("NR-13", 2400.0),
            ("Despesas de viagem", 500.0),
        ])
        self.assertEqual(
            sum(value for _name, value in order._qualif_total_rows()),
            order.amount_untaxed,
        )

    def test_service_lines_not_double_counted(self):
        order = self._services_order()
        self._add_service(order, self.svc_nr13, 1)
        totals = order._qualif_proposal_totals()
        self.assertEqual(totals["adicionais"], [])
        self.assertEqual(totals["residual"], 0)
        self.assertEqual(
            [(g["group"], g["name"], g["amount"])
             for g in totals["service_groups"]],
            [
                (self.group_calib, "Calibração de Instrumentos", 960.0),
                (self.group_nr13, "NR-13", 2400.0),
            ],
        )
        self.assertEqual(totals["grand_total"], order.amount_untaxed)

    def test_single_front_prints_only_grand_total(self):
        order = self._services_order()
        self.assertEqual(order._qualif_total_rows(), [])

    def test_qualification_only_unchanged(self):
        order = self._qualif_order()
        qualif_value = order.amount_untaxed
        self.assertEqual(order._qualif_total_rows(), [])
        self._manual_line(order, "Pasta impressa", 150.0)
        self.assertEqual(order._qualif_total_rows(), [
            (QUALIF_LABEL, qualif_value),
            ("Pasta impressa", 150.0),
        ])
        self.assertEqual(order._qualif_proposal_totals()["service_groups"], [])

    def test_optional_not_accepted_excluded(self):
        order = self._services_order()
        product = self.env["product.product"].create({
            "name": "Test Pasta", "type": "service", "list_price": 150.0,
        })
        optional = self._manual_line(
            order, "Opcional Pasta", 150.0,
            product_id=product.id,
            is_proposal_optional=True, optional_accepted=False,
            optional_qty=1.0,
        )
        optional._sync_optional_qty()
        self.assertEqual(order._qualif_total_rows(), [])
        self.assertEqual(order.amount_untaxed, 960.0)

        optional.optional_accepted = True
        optional._sync_optional_qty()
        self.assertEqual(order._qualif_total_rows(), [
            ("Calibração de Instrumentos", 960.0),
            ("Opcional Pasta", 150.0),
        ])
        self.assertEqual(order.amount_untaxed, 1110.0)

    def test_residual_still_explains_unaccounted_value(self):
        """Invariante C26-06-0005: o que não é explicado vai para "Outros"."""
        order = self._services_order()
        self._add_service(order, self.svc_nr13, 1)
        # Simula valor do total que nenhuma linha explica (alvo desviado,
        # arredondamento...): só o residual pode mostrá-lo.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE sale_order SET amount_untaxed = amount_untaxed + 300 "
            "WHERE id = %s", [order.id])
        order.invalidate_recordset(["amount_untaxed"])
        totals = order._qualif_proposal_totals()
        self.assertEqual(totals["residual"], 300.0)
        rows = order._qualif_total_rows()
        self.assertEqual(rows, [
            ("Calibração de Instrumentos", 960.0),
            ("NR-13", 2400.0),
            ("Outros", 300.0),
        ])
        self.assertEqual(
            sum(value for _name, value in rows), order.amount_untaxed)

    def test_form_banner_for_services_only(self):
        order = self._services_order()
        self._add_service(order, self.svc_nr13, 1)
        html = order.qualif_subtotals_html
        self.assertTrue(html)
        self.assertIn("NR-13", html)
        self.assertIn("Calibração de Instrumentos", html)
        self.assertIn(GRAND_LABEL, html)

    # -- emissor -----------------------------------------------------------

    def test_emitter_prefers_financial(self):
        tpl = self._template(["equipment_scope", "financial"])
        order = self._qualif_order(tpl)
        self._add_service(order, self.svc_seladora, 8)
        self._seeded(order)
        emitter = order._proposal_totals_emitter()
        self.assertEqual(emitter.block_kind, "financial")
        self.assertEqual(len(emitter), 1)

    def test_emitter_falls_back_to_scope(self):
        tpl = self._template(["equipment_scope"])
        order = self._qualif_order(tpl)
        self._seeded(order)
        emitter = order._proposal_totals_emitter()
        self.assertEqual(emitter.block_kind, "equipment_scope")

    def test_emitter_empty_without_totals_block(self):
        order = self._services_order(self._template([
            ("equipment_scope", {"applies_when": "qualification"}),
        ]))
        self._seeded(order)
        self.assertFalse(order._proposal_totals_emitter())

    # -- impresso exatamente uma vez --------------------------------------

    def test_totals_printed_exactly_once(self):
        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")

        # (a) template padrão + só qualificação
        order = self._seeded(self._qualif_order(labquali))
        self.assertEqual(self._render(order).count(GRAND_LABEL), 1)

        # (b) template padrão + só serviços
        order = self._seeded(self._services_order(labquali))
        self.assertEqual(self._render(order).count(GRAND_LABEL), 1)

        # (c) template com bloco financeiro + cotação mista
        tpl = self._template(["equipment_scope", "financial"])
        order = self._qualif_order(tpl)
        self._add_service(order, self.svc_seladora, 8)
        self._manual_line(order, "Despesas de viagem", 500.0)
        self._seeded(order)
        html = self._render(order)
        self.assertEqual(html.count(GRAND_LABEL), 1)
        self.assertIn("Despesas de viagem", html)
        self.assertIn("Calibração de Instrumentos", html)

    def test_totals_printed_once_without_emitter_block(self):
        """Sem `financial` nem `equipment_scope` visível: tabela depois dos blocos."""
        order = self._services_order(self._template([
            ("equipment_scope", {"applies_when": "qualification"}),
        ]))
        self._add_service(order, self.svc_nr13, 1)
        self._seeded(order)
        html = self._render(order)
        self.assertEqual(html.count(GRAND_LABEL), 1)
        self.assertIn("NR-13", html)

    def test_financial_block_renders_at_its_position(self):
        """Com `financial` e `equipment_scope`, o total sai só no financeiro."""
        tpl = self._template(["financial", "equipment_scope"])
        order = self._qualif_order(tpl)
        self._add_service(order, self.svc_seladora, 8)
        self._seeded(order)
        html = self._render(order)
        self.assertEqual(html.count(GRAND_LABEL), 1)
        financial = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "financial")
        scope = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "equipment_scope")
        self.assertLess(
            html.index('id="qq-anchor-%s"' % financial.id),
            html.index(GRAND_LABEL),
        )
        self.assertLess(
            html.index(GRAND_LABEL),
            html.index('id="qq-anchor-%s"' % scope.id),
        )

    def _freeze_scope(self, order):
        """`action_edit_block` no escopo: snapshot vira bloco `static`."""
        scope = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "equipment_scope")
        self.assertEqual(len(scope), 1)
        scope.action_edit_block()
        self.assertEqual(scope.block_kind, "static")
        self.assertNotIn(GRAND_LABEL, str(scope.body))
        return scope

    def test_totals_once_after_scope_block_frozen(self):
        """Escopo editado (static) não duplica nem congela os totais."""
        # (a) template antigo (sem `financial`): totais ao fim dos blocos
        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")
        order = self._seeded(self._qualif_order(labquali))
        self._manual_line(order, "Despesas de viagem", 500.0)
        self._freeze_scope(order)
        self.assertFalse(order._proposal_totals_emitter())
        self.assertEqual(self._render(order).count(GRAND_LABEL), 1)

        # (c) portal, mesmo cenário
        html = str(self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": order},
        ))
        self.assertEqual(html.count(GRAND_LABEL), 1)
        self.assertIn("Despesas de viagem", html)

        # (b) template com `financial`: o bloco financeiro é o emissor
        tpl = self._template(["equipment_scope", "financial"])
        order = self._qualif_order(tpl)
        self._manual_line(order, "Despesas de viagem", 500.0)
        self._seeded(order)
        self._freeze_scope(order)
        self.assertEqual(order._proposal_totals_emitter().block_kind, "financial")
        html = self._render(order)
        self.assertEqual(html.count(GRAND_LABEL), 1)
        self.assertIn("Despesas de viagem", html)

    def test_portal_prints_totals_once(self):
        qweb = self.env["ir.qweb"]
        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")
        for order in (
            self._seeded(self._services_order(labquali)),
            self._seeded(self._qualif_order(labquali)),
        ):
            self._add_service(order, self.svc_nr13, 1)
            html = str(qweb._render(
                "afr_qualificacao.sale_order_online_qualif_content",
                {"sale_order": order},
            ))
            self.assertEqual(html.count(GRAND_LABEL), 1)
            self.assertIn("NR-13", html)

    # -- gates -------------------------------------------------------------

    def test_portal_and_mail_gate(self):
        order = self._services_order()
        self.assertFalse(order.has_qualif_lines)
        self.assertTrue(order.is_managed_quote)
        template = order._find_mail_template()
        self.assertEqual(
            template,
            self.env.ref("afr_qualificacao.email_template_proposal_labquali"),
        )

    # -- Task 9: escopo vazio em cotação só de serviços --------------------

    def test_old_template_services_only_has_no_empty_scope_heading(self):
        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")
        order = self._seeded(self._services_order(labquali))
        scope = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "equipment_scope")
        self.assertEqual(len(scope), 1)
        self.assertTrue(scope._is_applicable())
        self.assertEqual(order._proposal_totals_emitter(), scope)
        title = scope.title or "Escopo por Equipamento"

        # PDF
        html = self._render(order)
        self.assertNotIn(title, html)
        self.assertEqual(html.count(GRAND_LABEL), 1)

        # Portal
        portal = str(self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": order},
        ))
        self.assertNotIn(title, portal)
        self.assertEqual(portal.count(GRAND_LABEL), 1)

    def test_old_template_qualification_keeps_scope_heading(self):
        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")
        order = self._seeded(self._qualif_order(labquali))
        scope = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "equipment_scope")
        title = scope.title or "Escopo por Equipamento"
        self.assertIn(title, self._render(order))
        portal = str(self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": order},
        ))
        self.assertIn(title, portal)

    def test_old_template_services_only_numbering_has_no_gap(self):
        import re
        from ..models._numbering import hierarchical_numbering

        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")
        # Com norma no serviço a tabela de normas também imprime (sem norma
        # ela some do documento, mas segue numerada: vale para qualquer
        # cotação e não é objeto deste teste).
        self.svc_seladora.standard_ids = self.env[
            "afr.qualificacao.standard"].create({
                "code": "TST-001", "name": "Norma de Teste"})
        order = self._seeded(self._services_order(labquali))
        scope = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "equipment_scope")
        self.assertIn(scope, order._proposal_visible_blocks())
        self.assertNotIn(scope, order._proposal_chapter_blocks())
        numbers = order._proposal_block_numbering()
        self.assertNotIn(scope.id, numbers)
        roots = sorted(
            int(n) for bid, n in numbers.items()
            if n and "." not in n
        )
        self.assertTrue(roots)
        self.assertEqual(roots, list(range(1, len(roots) + 1)))

        html = self._render(order)
        self.assertEqual(html.count(GRAND_LABEL), 1)
        toc = re.findall(r'qq-toc-num">\s*([\d.]+)\s*<', html)
        body = re.findall(r'>([\d.]+)</span> — ', html)
        self.assertTrue(toc)
        self.assertEqual(toc, body)
        self.assertEqual(
            [n for n in toc if "." not in n],
            [str(i) for i in range(1, len(roots) + 1)],
        )

        portal = str(self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": order},
        ))
        self.assertEqual(portal.count(GRAND_LABEL), 1)
        self.assertEqual(
            re.findall(r'lq-toc-num">\s*([\d.]+)\s*<', portal), toc)

    def test_old_template_qualification_numbering_unchanged(self):
        from ..models._numbering import hierarchical_numbering

        labquali = self.env.ref("afr_qualificacao.proposal_template_labquali")
        order = self._seeded(self._qualif_order(labquali))
        scope = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "equipment_scope")
        self.assertIn(scope, order._proposal_chapter_blocks())
        self.assertTrue(order._proposal_block_numbering()[scope.id])

        # Sem normas e sem opcionais, os blocos que não imprimem saem da
        # numeração (e seus filhos assumem o lugar do pai); o resto segue a
        # numeração de sempre.
        self.assertFalse(order.qualif_standard_ids)
        visible = order._proposal_visible_blocks()
        self.assertEqual(
            order._proposal_block_numbering(),
            hierarchical_numbering(
                visible.filtered(lambda b: b.block_kind not in (
                    "standards_table", "optionals")),
                promote_children_of=(
                    order._proposal_non_chapter_blocks().ids),
            ),
        )

        # Com norma (sem opcionais) só o bloco de opcionais vazio sai.
        self.svc_seladora.standard_ids = self.env[
            "afr.qualificacao.standard"].create({
                "code": "TST-001", "name": "Norma de Teste"})
        self._add_service(order, self.svc_seladora, 1)
        self.assertTrue(order.qualif_standard_ids)
        self.assertEqual(
            order._proposal_block_numbering(),
            hierarchical_numbering(
                order._proposal_visible_blocks().filtered(
                    lambda b: b.block_kind != "optionals"),
                promote_children_of=(
                    order._proposal_non_chapter_blocks().ids),
            ),
        )
