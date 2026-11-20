"""Textos da proposta multi-serviço: e-mail, plural do rótulo da unidade,
nome da linha, cabeçalho do cronograma, previsão de dias, escaping e
`sequence` do TPL-MULTI.
"""

from psycopg2.extras import Json

from odoo.tests.common import tagged
from odoo.tools import file_open

from odoo.addons.afr_qualificacao import hooks

from .common_servico import AfrServicoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestServicoTexts(AfrServicoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("sale.action_report_saleorder")
        cls.mail = cls.env.ref(
            "afr_qualificacao.email_template_proposal_labquali")

    # -- helpers -----------------------------------------------------------

    def _group_order(self, group, service, qty=2):
        order = self._make_order()
        line = self._add_service(order, service, qty)
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Textos"})
        self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id, "sequence": 10,
            "block_kind": "service_group", "applies_when": "service_group",
            "service_group_id": group.id,
        })
        order.proposal_template_id = tpl
        order._seed_proposal_blocks()
        return order, line

    def _block(self, order):
        return order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "service_group")

    def _pdf(self, order):
        html, _ctype = self.report._render_qweb_html(
            self.report.report_name, order.ids)
        return html.decode() if isinstance(html, bytes) else html

    def _portal(self, order):
        return str(self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": order},
        ))

    def _identify_first_unit(self, order, tag="TAG-001"):
        order._service_sync_units(force=True)
        order._service_lines()[0].service_unit_ids[0].tag = tag

    def _set_mail_body(self, value):
        self.env.cr.execute(
            "UPDATE mail_template SET body_html = %s WHERE id = %s",
            [Json(value), self.mail.id])
        self.mail.invalidate_recordset(["body_html"])

    def _raw_mail_body(self):
        self.env.cr.execute(
            "SELECT body_html FROM mail_template WHERE id = %s",
            [self.mail.id])
        return self.env.cr.fetchone()[0]

    def _render_mail(self, order):
        return str(self.mail._render_field("body_html", order.ids)[order.id])

    # -- I1: e-mail da proposta --------------------------------------------

    def test_mail_xml_uses_helper(self):
        with file_open(
            "afr_qualificacao/data/mail_template_proposal.xml"
        ) as handle:
            source = handle.read()
        self.assertIn("object._proposal_cover_subtitle()", source)
        self.assertNotIn(hooks.PROPOSAL_MAIL_OLD_PHRASE, source)

    def test_mail_upgrade_replaces_old_phrase(self):
        old = (
            "<p>Apresentamos nossa proposta %s, elaborada conforme o "
            "processo.</p>" % hooks.PROPOSAL_MAIL_OLD_PHRASE
        )
        self._set_mail_body({"en_US": old, "pt_BR": old})
        self.assertTrue(hooks._upgrade_proposal_mail_body(self.env))
        raw = self._raw_mail_body()
        for lang in ("en_US", "pt_BR"):
            self.assertNotIn(hooks.PROPOSAL_MAIL_OLD_PHRASE, raw[lang])
            self.assertIn("object._proposal_cover_subtitle()", raw[lang])
            self.assertTrue(raw[lang].startswith(
                "<p>Apresentamos nossa proposta para os serviços de "))
            self.assertTrue(raw[lang].endswith(
                " solicitados, elaborada conforme o processo.</p>"))
        # Idempotente: a segunda chamada não acha mais a frase.
        self.assertFalse(hooks._upgrade_proposal_mail_body(self.env))

        services = self._make_order()
        self._add_service(services, self.svc_nr13, 1)
        body = self._render_mail(services)
        self.assertIn("para os serviços de NR-13 solicitados", body)
        self.assertNotIn("Qualificação de Equipamentos", body)

        qualif = self._make_order()
        self.assertFalse(qualif.has_service_lines)
        self.assertIn(
            hooks.PROPOSAL_MAIL_OLD_PHRASE, self._render_mail(qualif))

    def test_mail_upgrade_keeps_user_edit(self):
        edited = "<p>Segue nossa proposta para os serviços combinados.</p>"
        self._set_mail_body({"en_US": edited})
        self.assertFalse(hooks._upgrade_proposal_mail_body(self.env))
        self.assertEqual(self._raw_mail_body(), {"en_US": edited})

    # -- I2: plural do rótulo da unidade -----------------------------------

    def test_plural_helper(self):
        group = self.env["afr.servico.grupo"].create({
            "name": "Grupo Plural", "unit_label": "exaustor",
        })
        self.assertEqual(group._unit_label_plural(), "exaustors")
        group.unit_label_plural = "exaustores"
        self.assertEqual(group._unit_label_plural(), "exaustores")

    def test_fill_seed_plurals_only_when_empty(self):
        calib = self.env.ref("afr_qualificacao.servico_grupo_calibracao")
        vazao = self.env.ref("afr_qualificacao.servico_grupo_vazao")
        nr13 = self.env.ref("afr_qualificacao.servico_grupo_nr13")
        calib.unit_label_plural = False
        vazao.unit_label_plural = False
        nr13.unit_label_plural = "vasos de pressão"
        hooks._fill_service_group_plurals(self.env)
        self.assertEqual(calib.unit_label_plural, "instrumentos")
        self.assertEqual(vazao.unit_label_plural, "exaustores")
        self.assertEqual(nr13.unit_label_plural, "vasos de pressão")

    def test_unit_list_uses_plural_in_all_renderers(self):
        group = self.env["afr.servico.grupo"].create({
            "name": "Vazão Teste", "unit_label": "exaustor",
            "unit_label_plural": "exaustores",
        })
        service = self.env["afr.servico"].create({
            "name": "Test Vazão Exaustor", "group_id": group.id,
            "product_id": self.svc_nr13.product_id.id,
        })
        order, _line = self._group_order(group, service)
        self._identify_first_unit(order)
        snapshot = str(self._block(order)._snapshot_html())
        for html in (self._pdf(order), self._portal(order), snapshot):
            self.assertIn("Relação de exaustores", html)
            self.assertNotIn("exaustors", html)

    # -- M1: nome da linha -------------------------------------------------

    def test_table_uses_line_name(self):
        order, line = self._group_order(self.group_calib, self.svc_seladora)
        line.name = "Seladora do centro cirúrgico (texto do vendedor)"
        table = order._service_group_table(self.group_calib)
        self.assertEqual(table["rows"][0]["name"], line.name)
        snapshot = str(self._block(order)._snapshot_html())
        for html in (self._pdf(order), self._portal(order), snapshot):
            self.assertIn("texto do vendedor", html)

    # -- M12: cabeçalho do cronograma --------------------------------------

    def _schedule_order(self, with_service):
        order = self._make_order()
        if with_service:
            self._add_service(order, self.svc_seladora, 8)
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Cron"})
        self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id, "sequence": 10, "block_kind": "schedule",
        })
        order.proposal_template_id = tpl
        order._seed_proposal_blocks()
        return order

    def test_schedule_header_names_services(self):
        order = self._schedule_order(with_service=True)
        block = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "schedule")
        snapshot = str(block._snapshot_html())
        for html in (self._pdf(order), self._portal(order), snapshot):
            self.assertIn("Equipamento / Serviço", html)

    def test_schedule_header_equipment_only(self):
        order = self._make_order()
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": order.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "do_qi": True,
        })
        wiz.action_apply()
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Cron"})
        self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id, "sequence": 10, "block_kind": "schedule",
        })
        order.proposal_block_ids.unlink()
        order.proposal_template_id = tpl
        order._seed_proposal_blocks()
        block = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "schedule")
        self.assertTrue(order._qualif_schedule_rows())
        self.assertNotIn("Equipamento / Serviço", str(block._snapshot_html()))
        self.assertNotIn("Equipamento / Serviço", self._pdf(order))

    # -- previsão de dias do capítulo: 8,0 h/dia fixas --------------------

    def test_days_label_ignores_manual_section_hours(self):
        order = self._make_order()
        self.env["sale.order.line"].create({
            "order_id": order.id, "display_type": "line_section",
            "name": "Seção manual", "work_hours_per_day": 4.0,
        })
        # 8 × 0,5 h = 4 h → 0,5 dia a 8 h/dia (seria 1,0 a 4 h/dia).
        self._add_service(order, self.svc_seladora, 8)
        table = order._service_group_table(self.group_calib)
        self.assertEqual(table["hours"], 4.0)
        self.assertEqual(
            table["days_label"], order._qualif_days_label(0.5))

    # -- escaping do snapshot ----------------------------------------------

    def test_snapshot_escapes_service_texts(self):
        service = self.env["afr.servico"].create({
            "name": "<b>Svc</b>", "group_id": self.group_calib.id,
            "product_id": self.svc_seladora.product_id.id,
            "scope_description": "<b>Escopo</b>",
        })
        order, line = self._group_order(self.group_calib, service, qty=1)
        line.name = "<b>Svc</b>"
        self._identify_first_unit(order, tag="<b>TAG</b>")
        html = str(self._block(order)._snapshot_html())
        self.assertNotIn("<b>", html)
        self.assertIn("&lt;b&gt;Svc&lt;/b&gt;", html)
        self.assertIn("&lt;b&gt;Escopo&lt;/b&gt;", html)
        self.assertIn("&lt;b&gt;TAG&lt;/b&gt;", html)

    # -- M7: TPL-MULTI abaixo de todos os templates ------------------------

    def test_multi_default_sequence(self):
        Template = self.env["afr.proposal.template"]
        lowest = Template.search([], order="sequence", limit=1)
        expected = min(1, lowest.sequence - 1) if lowest else 1
        self.assertEqual(
            hooks._proposal_multi_default_sequence(self.env), expected)
        Template.create({"name": "Tpl Muito Baixo", "sequence": -5})
        self.assertEqual(hooks._proposal_multi_default_sequence(self.env), -6)

    def test_multi_default_sequence_never_above_one(self):
        Template = self.env["afr.proposal.template"]
        Template.search([]).write({"sequence": 50})
        self.assertEqual(hooks._proposal_multi_default_sequence(self.env), 1)
