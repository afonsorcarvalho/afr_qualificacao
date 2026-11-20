"""Cotação multi-serviço — helpers de `sale.order` para linhas de serviço."""

from odoo import api, fields, models


class SaleOrderServico(models.Model):
    _inherit = "sale.order"

    has_service_lines = fields.Boolean(
        compute="_compute_has_service_lines",
        string="Possui Linhas de Serviço",
        help="True se a cotação tem linhas de serviço do catálogo.",
    )
    is_managed_quote = fields.Boolean(
        compute="_compute_is_managed_quote",
        string="Cotação Gerenciada",
        help=(
            "True se a cotação tem linhas de qualificação ou de serviço "
            "(usa o layout dedicado de proposta)."
        ),
    )

    @api.depends("order_line.is_service_managed", "order_line.display_type")
    def _compute_has_service_lines(self):
        for order in self:
            order.has_service_lines = any(
                line.is_service_managed and not line.display_type
                for line in order.order_line
            )

    @api.depends("has_qualif_lines", "has_service_lines")
    def _compute_is_managed_quote(self):
        for order in self:
            order.is_managed_quote = (
                order.has_qualif_lines or order.has_service_lines
            )

    def _service_lines(self, group=None):
        """Linhas de serviço ordenadas por (grupo, serviço, id).

        `group`: se dado, só as linhas desse `afr.servico.grupo`.
        """
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda l: l.is_service_managed
            and not l.display_type
            and (not group or l.service_group_id == group)
        )
        return lines.sorted(
            key=lambda l: (
                l.service_group_id.sequence,
                l.service_group_id.id,
                l.service_id.sequence,
                l.id,
            )
        )

    def _service_groups(self):
        """Grupos de serviço presentes na cotação, ordenados por `sequence`."""
        self.ensure_one()
        return self._service_lines().mapped("service_group_id").sorted(
            key=lambda g: (g.sequence, g.name, g.id)
        )
