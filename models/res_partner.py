# -*- coding: utf-8 -*-
"""Extensão de res.partner: equipamentos do cliente (smart button).

F10.6 (16.0.5.5.0): botão inteligente no cliente abre a lista de equipamentos
(view de Qualificação) filtrada por cliente; "Novo" já cria o equipamento
vinculado a esse cliente (default_client_id).
"""
from odoo import api, fields, models


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
