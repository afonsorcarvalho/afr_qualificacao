"""Descrição de venda por variante.

No Odoo nativo, `description_sale` vive em `product.template` e é delegado a
`product.product` via `_inherits`, logo é compartilhado por todas as variantes.
Este override permite texto específico por variante: quando preenchido,
SUBSTITUI a descrição do template na linha de venda/fatura/compra.
"""

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    variant_description_sale = fields.Text(
        string="Descrição de Vendas (Variante)",
        translate=True,
        help=(
            "Descrição de vendas específica desta variante. Quando "
            "preenchida, SUBSTITUI a descrição de vendas do produto-pai "
            "(template) na linha de venda/fatura/compra. Vazia = usa a "
            "descrição do template (comportamento padrão)."
        ),
    )

    def get_product_multiline_description_sale(self):
        self.ensure_one()
        if self.variant_description_sale:
            return self.variant_description_sale
        return super().get_product_multiline_description_sale()
