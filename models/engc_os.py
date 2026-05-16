"""Extensão de engc.os via _inherit (sem tocar submodule engenapp/engc_os).

Adiciona:
- sale_order_id: SO origem que disparou a criação da OS
- afr_qualificacao_ids: qualificações executadas nesta OS
- Stat button para qualificações (render via view inherit)
"""

from odoo import api, fields, models


class EngcOs(models.Model):
    _inherit = "engc.os"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Pedido de Venda",
        copy=False,
        ondelete="set null",
        help="Pedido de venda que originou esta OS via fluxo quote-first.",
    )
    afr_qualificacao_ids = fields.One2many(
        comodel_name="afr.qualificacao",
        inverse_name="engc_os_id",
        string="Qualificações",
    )
    afr_qualificacao_count = fields.Integer(
        compute="_compute_afr_qualificacao_count",
        string="Total de Qualificações",
    )

    @api.depends("afr_qualificacao_ids")
    def _compute_afr_qualificacao_count(self):
        for os in self:
            os.afr_qualificacao_count = len(os.afr_qualificacao_ids)

    def action_view_qualificacoes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Qualificações",
            "res_model": "afr.qualificacao",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.afr_qualificacao_ids.ids)],
        }
