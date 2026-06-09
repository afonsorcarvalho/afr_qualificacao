"""Mixin: valida que o `product_id` do registro é do tipo serviço.

Reaproveitado por catálogos que apontam para um `product.product` de
serviço (tipos de ciclo, tipos de malha, opcionais de proposta) — evita
repetir a mesma `@api.constrains` em cada modelo.
"""

from odoo import api, models, _
from odoo.exceptions import ValidationError


class AfrProductServiceMixin(models.AbstractModel):
    """Garante que o `product_id` do modelo concreto seja serviço."""

    _name = "afr.product.service.mixin"
    _description = "Validação de produto de serviço"

    @api.constrains("product_id")
    def _check_product_is_service(self):
        for record in self:
            if record.product_id and record.product_id.type != "service":
                raise ValidationError(
                    _("Produto '%s' não é do tipo serviço.")
                    % record.product_id.display_name
                )
