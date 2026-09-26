"""Registro de aprovações do Relatório Final (P3: só o registro).

Fluxo de aprovação (botões, portal, gate) é de P4.
"""

import uuid

from odoo import api, fields, models

APROVACAO_PAPEIS = [
    ("elaborador", "Elaborador"),
    ("emissor", "Emissor / Responsável Técnico"),
    ("executor", "Executor"),
    ("cliente", "Cliente"),
]


class AfrRelatorioAprovacao(models.Model):
    _name = "afr.relatorio.aprovacao"
    _description = "Aprovação do Relatório Final"
    _order = "sequence, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    papel = fields.Selection(APROVACAO_PAPEIS, required=True)
    user_id = fields.Many2one("res.users", string="Usuário")
    partner_id = fields.Many2one("res.partner", string="Contato")
    nome_exibicao = fields.Char(string="Nome no relatório")
    registro = fields.Char(string="Registro (CREA etc.)")
    approved_at = fields.Datetime(string="Aprovado em", readonly=True, copy=False)
    ip = fields.Char(readonly=True, copy=False)
    access_token = fields.Char(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("papel") == "cliente" and not vals.get("access_token"):
                vals["access_token"] = uuid.uuid4().hex
        return super().create(vals_list)
