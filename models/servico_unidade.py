"""Unidades numeradas de uma linha de serviço da cotação.

Cada unidade cotada (ex.: cada uma das 8 seladoras) vira um registro com
número de item estável, porque os certificados são numerados
`<proposta>-<item>`. O número é fixado na confirmação da cotação e nunca é
alterado nem reaproveitado (ver `sale.order._service_sync_units`).
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AfrServicoUnidade(models.Model):
    _name = "afr.servico.unidade"
    _description = "Unidade de Serviço da Cotação"
    _order = "item_number, sequence, id"

    line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Linha da Cotação",
        required=True,
        ondelete="cascade",
        index=True,
    )
    order_id = fields.Many2one(
        comodel_name="sale.order",
        related="line_id.order_id",
        string="Cotação",
        store=True,
        index=True,
    )
    service_id = fields.Many2one(
        comodel_name="afr.servico",
        related="line_id.service_id",
        string="Serviço",
        store=True,
    )
    sequence = fields.Integer(string="Sequência", default=10)
    item_number = fields.Integer(
        string="Item",
        readonly=True,
        copy=False,
        help=(
            "Número do item, sequencial na cotação e fixado na confirmação. "
            "0 = ainda sem número."
        ),
    )
    equipment_id = fields.Many2one(
        comodel_name="engc.equipment",
        string="Equipamento",
        help="Opcional: preenche os dados da unidade a partir do cadastro.",
    )
    tag = fields.Char(string="TAG")
    description = fields.Char(string="Descrição")
    marca = fields.Char(string="Marca")
    model = fields.Char(string="Modelo")
    serial_number = fields.Char(string="Nº de Série")
    location = fields.Char(string="Local de Uso")
    range_spec = fields.Char(string="Faixa de Utilização")
    is_identified = fields.Boolean(
        string="Identificada",
        compute="_compute_is_identified",
        store=True,
        help="Identificada = tem TAG ou número de série.",
    )

    @api.depends("tag", "serial_number")
    def _compute_is_identified(self):
        for unit in self:
            unit.is_identified = bool(unit.tag or unit.serial_number)

    @api.onchange("equipment_id")
    def _onchange_equipment_id(self):
        equipment = self.equipment_id
        if not equipment:
            return
        self.description = equipment.name
        self.marca = equipment.marca_id.name
        self.model = equipment.model
        self.serial_number = equipment.serial_number
        self.location = equipment.location_id.name
        self.tag = equipment.tag

    @api.constrains("line_id")
    def _check_units_within_qty(self):
        self.mapped("line_id")._check_service_units_within_qty()
