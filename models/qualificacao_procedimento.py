# -*- coding: utf-8 -*-
"""Procedimento de Qualificação (template master) + linhas (procedimento.item).

Template pré-programado que define o que deve ser COLETADO em campo durante
a execução de uma qualificação (fotos cargas, dados qualificador, planilhas,
indicadores biológicos, fitas etc.).

Resolve por (applicable_qualification_type + equipment_category_id) com
fallback para apenas tipo. Explosão para collect.items acontece em
sale_order._explode_collect_items() na confirmação do SO (F3 16.0.3.2.0).
"""
from odoo import _, api, fields, models


KIND_SELECTION = [
    ("foto", "Foto"),
    ("excel", "Planilha Excel/CSV"),
    ("pdf", "PDF"),
    ("qualificador_data", "Arquivo do Qualificador (raw)"),
    ("outro", "Outro"),
]


class AfrQualificacaoProcedimento(models.Model):
    _name = "afr.qualificacao.procedimento"
    _description = "Procedimento de Qualificação (Template)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True, tracking=True)
    code = fields.Char(tracking=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    applicable_qualification_type = fields.Selection(
        [
            ("installation", "QI"),
            ("operational", "QO"),
            ("performance", "QD"),
            ("software", "QS"),
            ("calibration", "Calibração"),
        ],
        required=True,
        string="Tipo aplicável",
        tracking=True,
    )
    equipment_category_id = fields.Many2one(
        "engc.equipment.category",
        string="Categoria do equipamento",
        help="Vazio = aplica a qualquer categoria (fallback). Específica = match preferencial.",
        tracking=True,
    )
    item_ids = fields.One2many(
        "afr.qualificacao.procedimento.item",
        "procedimento_id",
        copy=True,
        string="Itens (esperados)",
    )
    item_count = fields.Integer(compute="_compute_item_count")

    _sql_constraints = [
        (
            "uniq_type_category_company",
            "unique(applicable_qualification_type, equipment_category_id, company_id)",
            "Já existe procedimento ativo para esse tipo + categoria + empresa.",
        ),
    ]

    @api.depends("item_ids")
    def _compute_item_count(self):
        for r in self:
            r.item_count = len(r.item_ids)

    @api.model
    def resolve_for(self, qualification_type, equipment_category):
        """Retorna melhor match para (type + category) ativo.

        Preferência: 1) match exato (type + category) → 2) só type
        (equipment_category_id vazio = fallback genérico). Retorna recordset
        vazio se nenhum.
        """
        domain = [
            ("active", "=", True),
            ("applicable_qualification_type", "=", qualification_type),
        ]
        cat_id = equipment_category.id if equipment_category else False
        if cat_id:
            rec = self.search(
                domain + [("equipment_category_id", "=", cat_id)], limit=1
            )
            if rec:
                return rec
        return self.search(
            domain + [("equipment_category_id", "=", False)], limit=1
        )


class AfrQualificacaoProcedimentoItem(models.Model):
    _name = "afr.qualificacao.procedimento.item"
    _description = "Item do Procedimento (Esperado de Coleta)"
    _order = "procedimento_id, sequence, id"

    procedimento_id = fields.Many2one(
        "afr.qualificacao.procedimento",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    kind = fields.Selection(
        KIND_SELECTION,
        required=True,
        default="foto",
        string="Tipo de mídia",
    )
    required = fields.Boolean(default=True)
    instruction = fields.Text(translate=True, help="Instrução para o técnico em campo.")
    mimetypes_hint = fields.Char(
        string="Mime types sugeridos",
        help="Ex: image/png,image/jpeg,application/pdf (informativo apenas).",
    )
    target_level = fields.Selection(
        [
            ("qualificacao", "Qualificação (1 por qualif)"),
            ("cycle", "Ciclo (1 por ciclo da qualif QD)"),
            ("malha", "Malha (1 por malha da qualif Calib)"),
        ],
        required=True,
        default="qualificacao",
        help="Cycle/malha explodem N collect.items conforme qty da qualif.",
    )
