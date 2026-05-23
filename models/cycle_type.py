"""Catálogo técnico de tipos de ciclo para qualificação de desempenho (QD).

Cada tipo de ciclo (ex: "Carga Máxima", "Carga Mínima", "Penetração de Calor")
é vinculado a 1 `product.product` que define o preço unitário no orçamento.

Reuso de `engc.equipment.category` (módulo `engc_os`) para filtrar ciclos
aplicáveis a cada categoria de equipamento (ex: autoclave vs estufa) durante
o wizard configurador.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AfrQualificacaoCycleType(models.Model):
    """Tipo de ciclo de qualificação de desempenho (QD)."""

    _name = "afr.qualificacao.cycle.type"
    _description = "Tipo de Ciclo de Qualificação (QD)"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Nome do tipo de ciclo (ex: Ciclo Carga Máxima).",
    )
    code = fields.Char(
        help="Código curto para referência interna / DOCX (ex: QD-CMAX).",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Produto de Serviço",
        required=True,
        domain=[("type", "=", "service"), ("sale_ok", "=", True)],
        help=(
            "Produto serviço que define preço unitário deste ciclo no "
            "orçamento. Cada execução de ciclo gera 1 unidade do produto."
        ),
    )
    equipment_category_id = fields.Many2one(
        comodel_name="engc.equipment.category",
        string="Categoria de Equipamento",
        help=(
            "Restringe disponibilidade do ciclo no wizard configurador para "
            "equipamentos desta categoria. Deixe vazio para 'todas categorias'."
        ),
    )
    description = fields.Text(
        translate=True,
        help="Detalhe técnico do ciclo (carga, parâmetros, finalidade).",
    )
    # F8.1 — specs técnicas para renderizar a tabela de ciclos da proposta.
    temperature = fields.Char(
        string="Temperatura",
        translate=True,
        help="Temperatura nominal do ciclo (ex: 134°C). Texto livre.",
    )
    duration = fields.Char(
        string="Tempo",
        translate=True,
        help="Duração do ciclo (ex: 7 min, 24 h). Texto livre.",
    )
    load_type = fields.Selection(
        selection=[
            ("vazio", "Câmara Vazia"),
            ("sem_carga", "Sem Carga"),
            ("com_carga", "Com Carga"),
        ],
        string="Tipo de Carga",
        help="Classifica o ciclo na tabela da proposta (QO sem carga, QD com carga).",
    )
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits="Product Price",
        help=(
            "Horas estimadas por execução deste ciclo (sugestão pra "
            "cronograma da proposta). Convertido em dias úteis via /8."
        ),
    )
    default_unit_price = fields.Float(
        string="Preço Unit. Padrão",
        digits="Product Price",
        help=(
            "Preço unitário sugerido pra cada execução deste ciclo no "
            "configurador. Override do product.list_price; 0 = usa list_price."
        ),
    )
    standard_ids = fields.Many2many(
        comodel_name="afr.qualificacao.standard",
        relation="afr_cycle_type_standard_rel",
        column1="cycle_type_id",
        column2="standard_id",
        string="Normas Aplicáveis",
        help=(
            "Normas técnicas/regulatórias atendidas por este ciclo. "
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
