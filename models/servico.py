"""Catálogo de serviços cotados por unidade (cotação multi-serviço).

`afr.servico.grupo` agrupa serviços de mesma natureza (ex.: Calibração de
Instrumentos, NR-13) e define o capítulo da proposta e o rótulo da unidade.
`afr.servico` é o item cotável: aponta para um `product.product` de serviço
(preço unitário) e carrega os dados de proposta e de execução.
"""

from odoo import fields, models


class AfrServicoGrupo(models.Model):
    """Grupo de serviços (capítulo da proposta)."""

    _name = "afr.servico.grupo"
    _description = "Grupo de Serviços"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Código curto do grupo.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    chapter_title = fields.Char(
        string="Título do Capítulo",
        translate=True,
        help="Título do capítulo na proposta. Vazio = usa o nome do grupo.",
    )
    unit_label = fields.Char(
        string="Rótulo da Unidade",
        default="unidade",
        help="Como a unidade cotada é chamada (ex.: instrumento, equipamento).",
    )
    unit_label_plural = fields.Char(
        string="Rótulo da Unidade (plural)",
        translate=True,
        help=(
            "Plural do rótulo, usado em \"Relação de …\" na proposta (ex.: "
            "exaustores). Vazio = rótulo + \"s\"."
        ),
    )
    service_ids = fields.One2many(
        comodel_name="afr.servico",
        inverse_name="group_id",
        string="Serviços",
    )

    def _chapter_title(self):
        """Título do capítulo na proposta: `chapter_title` ou o nome do grupo."""
        self.ensure_one()
        return self.chapter_title or self.name

    def _unit_label_plural(self):
        """Plural do rótulo da unidade: `unit_label_plural` ou rótulo + "s"."""
        self.ensure_one()
        return self.unit_label_plural or "%ss" % (self.unit_label or "unidade")


class AfrServico(models.Model):
    """Serviço cotável por unidade."""

    _name = "afr.servico"
    _inherit = "afr.product.service.mixin"
    _description = "Serviço"
    _order = "group_id, sequence, name"

    name = fields.Char(string="Nome", required=True, translate=True)
    code = fields.Char(string="Código", help="Código curto do serviço.")
    sequence = fields.Integer(string="Sequência", default=10)
    active = fields.Boolean(string="Ativo", default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Moeda",
    )
    group_id = fields.Many2one(
        comodel_name="afr.servico.grupo",
        string="Grupo",
        required=True,
        ondelete="restrict",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Produto de Serviço",
        required=True,
        domain=[("type", "=", "service"), ("sale_ok", "=", True)],
        help=(
            "Produto de serviço faturado. Define o preço unitário quando o "
            "campo Preço Unitário do serviço está vazio."
        ),
    )
    default_unit_price = fields.Monetary(
        string="Preço Unitário",
        currency_field="currency_id",
        help=(
            "Preço por unidade sugerido na cotação. Vazio (zero) = usa o "
            "preço de lista do produto de serviço."
        ),
    )
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits=(16, 2),
        help="Horas estimadas por unidade cotada (base do cronograma).",
    )
    scope_description = fields.Text(
        string="Escopo",
        translate=True,
        help="Descrição do escopo exibida na proposta.",
    )
    procedure_code = fields.Char(string="Código do Procedimento")
    procedure_revision = fields.Char(string="Revisão do Procedimento")
    standard_ids = fields.Many2many(
        comodel_name="afr.qualificacao.standard",
        relation="afr_servico_standard_rel",
        column1="servico_id",
        column2="standard_id",
        string="Normas Aplicáveis",
    )
    equipment_category_id = fields.Many2one(
        comodel_name="engc.equipment.category",
        string="Categoria de Equipamento",
        help="Restringe o serviço a equipamentos desta categoria. Vazio = todas.",
    )

    def _default_unit_price(self):
        """Preço unitário sugerido: o do serviço; se vazio, o do produto."""
        self.ensure_one()
        return self.default_unit_price or self.product_id.list_price
