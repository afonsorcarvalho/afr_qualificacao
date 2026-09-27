# -*- coding: utf-8 -*-
"""Relatório Final — varredura de inconsistência e gate de emissão (P5)."""
from odoo import api, fields, models


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    achado_ids = fields.One2many(
        "afr.relatorio.achado",
        "relatorio_id",
        string="Achados da verificação",
    )
    has_blocking = fields.Boolean(compute="_compute_blocking", string="Tem bloqueio")
    blocking_summary = fields.Text(compute="_compute_blocking", string="Aguardando")
    achado_pendente_count = fields.Integer(
        compute="_compute_blocking", string="Achados pendentes"
    )

    @api.depends("achado_ids.gravidade", "achado_ids.decisao", "achado_ids.mensagem")
    def _compute_blocking(self):
        for r in self:
            blocking = r.achado_ids.filtered(
                lambda a: a.gravidade == "bloqueia" and a.decisao == "pendente"
            )
            r.has_blocking = bool(blocking)
            r.blocking_summary = "\n".join("• %s" % a.mensagem for a in blocking)
            r.achado_pendente_count = len(r.achado_ids.filtered(
                lambda a: a.decisao == "pendente" and a.gravidade != "info"
            ))
