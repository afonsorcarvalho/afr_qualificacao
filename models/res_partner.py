# -*- coding: utf-8 -*-
"""Extensão de res.partner: equipamentos do cliente (smart button).

F10.6 (16.0.5.5.0): botão inteligente no cliente abre a lista de equipamentos
(view de Qualificação) filtrada por cliente; "Novo" já cria o equipamento
vinculado a esse cliente (default_client_id).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

REAJUSTE_SUMMARY = "Reajustar preços combinados"


class ResPartner(models.Model):
    _inherit = "res.partner"

    afr_equipment_ids = fields.One2many(
        comodel_name="engc.equipment",
        inverse_name="client_id",
        string="Equipamentos",
    )
    afr_equipment_count = fields.Integer(
        compute="_compute_afr_equipment_count",
        string="Nº Equipamentos",
    )
    afr_relatorio_template_id = fields.Many2one(
        comodel_name="afr.relatorio.template",
        string="Template de Relatório padrão",
        help=(
            "Template do Relatório Final sugerido para os equipamentos "
            "deste cliente (commercial partner), quando não houver "
            "template já gravado na qualificação nem match por categoria "
            "do equipamento."
        ),
    )
    afr_procedimento_ids = fields.Many2many(
        comodel_name="afr.qualificacao.procedimento",
        relation="afr_res_partner_procedimento_rel",
        column1="partner_id",
        column2="procedimento_id",
        string="Procedimentos padrão do cliente",
        help=(
            "Procedimentos de qualificação preferidos deste cliente, no "
            "máximo 1 por categoria de equipamento. Usados na resolução "
            "antes do padrão genérico da categoria."
        ),
    )

    afr_config_template_ids = fields.One2many(
        comodel_name="afr.qualificacao.config.template",
        inverse_name="partner_id",
        string="Templates de cotação",
        context={"active_test": False},
    )

    afr_reajuste_data = fields.Date(
        string="Aniversário do reajuste",
        help="Todo ano, neste dia, o responsável recebe uma atividade "
             "para reajustar os preços combinados.")
    afr_reajuste_indice = fields.Selection(
        [("ipca", "IPCA"), ("igpm", "IGP-M"), ("inpc", "INPC")],
        string="Índice de reajuste", default="ipca")
    afr_reajuste_ids = fields.One2many(
        "afr.qualificacao.reajuste", "partner_id",
        string="Histórico de reajustes")

    def _afr_reajuste_templates(self):
        """Templates ativos do cliente com preço combinado."""
        self.ensure_one()
        return self.env["afr.qualificacao.config.template"].search([
            ("partner_id", "=", self.commercial_partner_id.id),
            ("price_base", ">", 0)])

    def _check_afr_reajuste_manager(self):
        if not self.env.user.has_group(
                "afr_qualificacao.group_afr_qualificacao_manager"):
            raise UserError(_(
                "Apenas gestores podem reajustar os preços combinados."))

    def action_afr_reajuste_wizard(self):
        self.ensure_one()
        self._check_afr_reajuste_manager()
        partner = self.commercial_partner_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Reajustar preços combinados"),
            "res_model": "afr.qualificacao.reajuste.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": partner.id,
                "default_indice": partner.afr_reajuste_indice or "ipca",
            },
        }

    @api.model
    def _cron_afr_reajuste_activity(self):
        """Aniversário hoje → atividade de reajuste (sem duplicar aberta)."""
        today = fields.Date.context_today(self)
        partners = self.search([("afr_reajuste_data", "!=", False)])
        admin = self.env.ref("base.user_admin")
        todo = self.env.ref("mail.mail_activity_data_todo")
        Activity = self.env["mail.activity"]
        for partner in partners:
            aniv = partner.afr_reajuste_data
            if (aniv.month, aniv.day) != (today.month, today.day):
                continue
            if not partner._afr_reajuste_templates():
                continue
            if Activity.search_count([
                    ("res_model", "=", "res.partner"),
                    ("res_id", "=", partner.id),
                    ("summary", "=", REAJUSTE_SUMMARY)]):
                continue
            partner.activity_schedule(
                activity_type_id=todo.id, summary=REAJUSTE_SUMMARY,
                user_id=(partner.user_id or admin).id,
                date_deadline=today)

    @api.constrains("afr_procedimento_ids")
    def _check_afr_procedimento_ids_unique_category(self):
        for partner in self:
            seen = set()
            for proc in partner.afr_procedimento_ids:
                key = proc.equipment_category_id.id or False
                if key in seen:
                    raise ValidationError(
                        _(
                            "'%(partner)s' já tem um procedimento padrão para "
                            "a categoria '%(cat)s'."
                        ) % {
                            "partner": partner.display_name,
                            "cat": proc.equipment_category_id.name if proc.equipment_category_id else _("(genérico)"),
                        }
                    )
                seen.add(key)

    @api.depends("afr_equipment_ids")
    def _compute_afr_equipment_count(self):
        for partner in self:
            partner.afr_equipment_count = len(partner.afr_equipment_ids)

    def action_view_afr_equipments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Equipamentos",
            "res_model": "engc.equipment",
            "view_mode": "tree,form",
            "domain": [("client_id", "=", self.id)],
            "context": {
                "default_client_id": self.id,
                "form_view_ref": "afr_qualificacao.view_engc_equipment_qualif_form",
                "tree_view_ref": "afr_qualificacao.view_engc_equipment_qualif_tree",
                "search_default_group_category": 0,
            },
            "help": """<p class="o_view_nocontent_smiling_face">
                Cadastre um equipamento para este cliente
            </p>""",
        }
