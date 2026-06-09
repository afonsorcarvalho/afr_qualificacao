"""Catálogo técnico de tipos de malha para Calibração.

Cada tipo de malha (ex: "Malha Temperatura", "Malha Pressão") é vinculado a:
- 1 `product.product` (preço unitário no orçamento)
- 1 `afr.qualificacao.sensor.kind` (grandeza física medida)

Reusa `engc.equipment.category` para filtrar malhas por categoria de
equipamento no wizard configurador.
"""

from odoo import fields, models


class AfrQualificacaoMalhaType(models.Model):
    """Tipo de malha de calibração."""

    _name = "afr.qualificacao.malha.type"
    _inherit = "afr.product.service.mixin"
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
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits="Product Price",
        help=(
            "Horas estimadas por execução desta malha (sugestão pra "
            "cronograma da proposta). Convertido em dias úteis via /8."
        ),
    )
    default_unit_price = fields.Float(
        string="Preço Unit. Padrão",
        digits="Product Price",
        help=(
            "Preço unitário sugerido pra cada execução desta malha no "
            "configurador. Override do product.list_price; 0 = usa list_price."
        ),
    )
    # F10 — quantos instrumentos padrão (da grandeza desta malha) cada
    # execução exige simultaneamente. Usado no bin-packing de padrões.
    standards_per_malha = fields.Integer(
        string="Padrões por Malha",
        default=1,
        required=True,
        help=(
            "Nº de instrumentos padrão (da grandeza desta malha) usados "
            "simultaneamente em cada execução. Default 1."
        ),
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
