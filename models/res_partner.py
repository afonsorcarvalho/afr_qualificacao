# -*- coding: utf-8 -*-
"""Extensão de res.partner: equipamentos do cliente (smart button).

F10.6 (16.0.5.5.0): botão inteligente no cliente abre a lista de equipamentos
(view de Qualificação) filtrada por cliente; "Novo" já cria o equipamento
vinculado a esse cliente (default_client_id).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
