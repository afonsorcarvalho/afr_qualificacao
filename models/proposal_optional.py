"""Catálogo de serviços opcionais/extras da proposta (F8 — Proposta LEGO).

Itens que o comercial liga/desliga na cotação sem fazer parte do escopo
técnico de qualificação: pasta impressa, despesas de viagem, diária
técnica adicional, etc.

Cada opcional aponta para um `product.product` de serviço; quando
selecionado no wizard configurador, vira uma linha da `sale.order`.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AfrProposalOptional(models.Model):
    """Serviço opcional/extra disponível para incluir numa cotação."""

    _name = "afr.proposal.optional"
    _description = "Serviço Opcional de Proposta"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Nome do opcional (ex: Pasta impressa, Despesas de viagem).",
    )
    code = fields.Char(
        help="Código curto para referência interna e seeds.",
    )
    kind = fields.Selection(
        selection=[
            ("folder", "Pasta Impressa / Postagem"),
            ("travel", "Despesas de Viagem"),
            ("extra_day", "Diária Técnica Adicional"),
            ("custom", "Outro"),
        ],
        string="Tipo",
        default="custom",
        required=True,
        help="Classifica o opcional para agrupamento no relatório.",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Produto de Serviço",
        required=True,
        domain=[("type", "=", "service"), ("sale_ok", "=", True)],
        help="Produto serviço usado ao gerar a linha da cotação.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        string="Moeda",
        readonly=True,
    )
    default_price = fields.Monetary(
        string="Preço Padrão",
        currency_field="currency_id",
        help="Preço sugerido. Vazio (0) = usa preço de lista do produto.",
    )
    default_qty = fields.Float(
        string="Quantidade Padrão",
        default=1.0,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.constrains("product_id")
    def _check_product_is_service(self):
        for record in self:
            if record.product_id and record.product_id.type != "service":
                raise ValidationError(
                    _("Produto '%s' não é do tipo serviço.")
                    % record.product_id.display_name
                )
