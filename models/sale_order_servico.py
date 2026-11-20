"""Cotação multi-serviço — helpers de `sale.order` para linhas de serviço."""

from odoo import _, api, fields, models


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

    service_unit_last_number = fields.Integer(
        string="Último Nº de Item de Serviço",
        copy=False,
        readonly=True,
        help=(
            "Maior número de item já atribuído a uma unidade de serviço desta "
            "cotação. Garante que número apagado nunca seja reaproveitado."
        ),
    )
    service_units_summary = fields.Char(
        compute="_compute_service_units_summary",
        string="Unidades Identificadas",
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

    @api.depends(
        "order_line.is_service_managed",
        "order_line.display_type",
        "order_line.product_uom_qty",
        "order_line.service_unit_ids.is_identified",
    )
    def _compute_service_units_summary(self):
        for order in self:
            lines = order._service_lines()
            if not lines:
                order.service_units_summary = False
                continue
            total = sum(int(l.product_uom_qty) for l in lines)
            done = sum(l.service_unit_identified_count for l in lines)
            order.service_units_summary = _(
                "%(done)d de %(total)d unidades identificadas",
                done=done, total=total,
            )

    def _service_sync_units(self, force=False):
        """Completa e numera as unidades das linhas de serviço.

        Só age em cotação confirmada (`sale`/`done`), ou com `force=True`
        (usado em `action_confirm`, ainda em rascunho):

        - completa com unidades vazias até `int(product_uom_qty)`;
        - dá número às unidades sem número (`item_number == 0`), seguindo a
          ordem de `_service_lines()` e, na linha, (`sequence`, `id`). O
          número vem de `service_unit_last_number`, nunca diminui; assim
          número atribuído não muda nem é reaproveitado, mesmo que a
          unidade de maior número tenha sido apagada.

        Reduzir quantidade não passa por aqui: é `sale.order.line.write`
        (`_service_trim_units`).
        """
        Unit = self.env["afr.servico.unidade"]
        for order in self:
            if not force and order.state not in ("sale", "done"):
                continue
            lines = order._service_lines()
            if not lines:
                continue
            for line in lines:
                missing = int(line.product_uom_qty) - len(line.service_unit_ids)
                if missing > 0:
                    Unit.create([{"line_id": line.id}] * missing)
            last = max(
                [order.service_unit_last_number]
                + lines.service_unit_ids.mapped("item_number")
            )
            for line in lines:
                for unit in line.service_unit_ids.sorted(
                    key=lambda u: (u.sequence, u.id)
                ):
                    if not unit.item_number:
                        last += 1
                        unit.item_number = last
            if last != order.service_unit_last_number:
                order.service_unit_last_number = last

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
        """Grupos de serviço presentes na cotação, ordenados por `sequence`.

        Empate de `sequence` desfeito por id, igual a `_service_lines`, para
        que a ordem dos grupos e a das linhas nunca discordem.
        """
        self.ensure_one()
        return self._service_lines().mapped("service_group_id").sorted(
            key=lambda g: (g.sequence, g.id)
        )
