"""Catálogo técnico de tipos de malha para Calibração.

Cada tipo de malha (ex: "Malha Temperatura", "Malha Pressão") é vinculado a:
- 1 `product.product` (preço unitário no orçamento)
- 1 `afr.qualificacao.sensor.kind` (grandeza física medida)

Reusa `engc.equipment.category` para filtrar malhas por categoria de
equipamento no wizard configurador.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AfrQualificacaoMalhaType(models.Model):
    """Tipo de malha de calibração."""

    _name = "afr.qualificacao.malha.type"
    _description = "Tipo de Malha de Calibração"
    _order = "sensor_kind_id, sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Nome do tipo de malha (ex: Malha Temperatura).",
    )
    code = fields.Char(
        help="Código curto (ex: MLH-TEMP).",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Produto de Serviço",
        required=True,
        domain=[("type", "=", "service"), ("sale_ok", "=", True)],
        help=(
            "Produto serviço que define preço unitário desta malha no "
            "orçamento. Cada execução de malha gera 1 unidade do produto."
        ),
    )
    sensor_kind_id = fields.Many2one(
        comodel_name="afr.qualificacao.sensor.kind",
        string="Grandeza",
        required=True,
        help="Grandeza física medida (temperatura, pressão, etc.).",
    )
    equipment_category_id = fields.Many2one(
        comodel_name="engc.equipment.category",
        string="Categoria de Equipamento",
        help=(
            "Restringe disponibilidade da malha no wizard configurador para "
            "equipamentos desta categoria. Deixe vazio para 'todas categorias'."
        ),
    )
    description = fields.Text(
        translate=True,
        help="Detalhe técnico da malha (pontos típicos, faixa, instrumento).",
    )
    # F8.1 — specs técnicas para renderizar a tabela de calibração da proposta.
    range_spec = fields.Char(
        string="Faixa Nominal",
        translate=True,
        help="Faixa nominal da malha (ex: 0–150 °C). Texto livre.",
    )
    estimated_days = fields.Float(
        string="Dias Estimados",
        help="Dias de execução estimados desta malha (sugestão para a proposta).",
    )
    standard_ids = fields.Many2many(
        comodel_name="afr.qualificacao.standard",
        relation="afr_malha_type_standard_rel",
        column1="malha_type_id",
        column2="standard_id",
        string="Normas Aplicáveis",
        help=(
            "Normas técnicas/regulatórias atendidas por esta malha. "
            "Agregadas no relatório de cotação por sale.order."
        ),
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    @api.constrains("product_id")
    def _check_product_is_service(self):
        for record in self:
            if record.product_id and record.product_id.type != "service":
                raise ValidationError(
                    _(
                        "Produto '%s' não é do tipo serviço."
                    )
                    % record.product_id.display_name
                )
