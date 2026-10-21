# -*- coding: utf-8 -*-
"""Histórico de reajustes dos preços combinados do cliente (Task 5)."""
from odoo import fields, models

TIPOS = [("indice", "Índice"), ("percentual", "Percentual"),
         ("valor", "Valor fixo")]
INDICES = [("ipca", "IPCA"), ("igpm", "IGP-M"), ("inpc", "INPC")]


class AfrQualificacaoReajuste(models.Model):
    _name = "afr.qualificacao.reajuste"
    _description = "Reajuste de preços combinados"
    _order = "date desc, id desc"

    partner_id = fields.Many2one(
        "res.partner", string="Cliente", required=True, index=True,
        ondelete="cascade")
    date = fields.Date(string="Data", required=True,
                       default=fields.Date.context_today)
    tipo = fields.Selection(TIPOS, string="Tipo", required=True)
    indice = fields.Selection(INDICES, string="Índice")
    periodo = fields.Char(string="Período")
    percentual = fields.Float(string="Percentual (%)", digits=(16, 4))
    valor = fields.Float(string="Valor somado")
    user_id = fields.Many2one("res.users", string="Usuário",
                              default=lambda s: s.env.user)
    line_ids = fields.One2many(
        "afr.qualificacao.reajuste.line", "reajuste_id", string="Templates")


class AfrQualificacaoReajusteLine(models.Model):
    _name = "afr.qualificacao.reajuste.line"
    _description = "Linha do reajuste de preços combinados"

    reajuste_id = fields.Many2one(
        "afr.qualificacao.reajuste", required=True, ondelete="cascade")
    template_id = fields.Many2one(
        "afr.qualificacao.config.template", string="Template",
        ondelete="set null")
    equipment_category_id = fields.Many2one(
        "engc.equipment.category", string="Categoria")
    valor_antigo = fields.Float(string="Antes")
    valor_novo = fields.Float(string="Depois")
