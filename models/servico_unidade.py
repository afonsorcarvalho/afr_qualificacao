"""Unidades numeradas de uma linha de serviço da cotação.

Cada unidade cotada (ex.: cada uma das 8 seladoras) vira um registro com
número de item estável, porque os certificados são numerados
`<proposta>-<item>`. O número é fixado na confirmação da cotação e nunca é
alterado nem reaproveitado (ver `sale.order._service_sync_units`).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Chave de contexto do fluxo interno de numeração
# (`sale.order._service_assign_item_numbers`): só ele grava `item_number`.
UNIT_NUMBERING_CTX = "afr_servico_unit_numbering"


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
        """Preenche a unidade a partir do equipamento.

        Só sobrescreve o campo que o equipamento tem; o que a pessoa já
        digitou nunca é apagado por cadastro incompleto.
        """
        equipment = self.equipment_id
        if not equipment:
            return
        values = {
            "description": equipment.name,
            "marca": equipment.marca_id.name,
            "model": equipment.model,
            "serial_number": equipment.serial_number,
            "location": equipment.location_id.name,
            "tag": equipment.tag,
        }
        for fname, value in values.items():
            if value:
                self[fname] = value

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(UNIT_NUMBERING_CTX) and any(
            vals.get("item_number") for vals in vals_list
        ):
            raise UserError(_(
                "O número do item é atribuído pelo sistema na confirmação "
                "da cotação e não pode ser informado."))
        units = super().create(vals_list)
        # Unidade criada à mão numa cotação já confirmada recebe o próximo
        # número na hora (nas em rascunho, o número sai na confirmação).
        units.order_id.filtered(
            lambda o: o.state in ("sale", "done")
        )._service_assign_item_numbers()
        return units

    def write(self, vals):
        """Número do item é identidade (certificado `<proposta>-<item>`).

        Fora do fluxo interno de numeração (`UNIT_NUMBERING_CTX`): o
        `item_number` não pode ser alterado (nem atribuído à mão), e a
        unidade já numerada não pode trocar de linha.
        """
        if not self.env.context.get(UNIT_NUMBERING_CTX):
            for unit in self:
                if (
                    "item_number" in vals
                    and (vals["item_number"] or 0) != unit.item_number
                ):
                    if unit.item_number:
                        raise UserError(_(
                            "O item %(item)d já foi numerado: o número não "
                            "pode ser alterado.", item=unit.item_number))
                    raise UserError(_(
                        "O número do item é atribuído pelo sistema na "
                        "confirmação da cotação e não pode ser informado."))
                if (
                    "line_id" in vals
                    and unit.item_number
                    and (vals["line_id"] or False) != unit.line_id.id
                ):
                    raise UserError(_(
                        "O item %(item)d já foi numerado e não pode mudar de "
                        "linha de serviço. Remova-o e crie uma unidade na "
                        "outra linha.", item=unit.item_number))
        return super().write(vals)

    @api.constrains("line_id")
    def _check_units_within_qty(self):
        self.mapped("line_id")._check_service_units_within_qty()
