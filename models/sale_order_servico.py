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

    def _service_group_table(self, group):
        """Dados do capítulo de um grupo de serviço (fonte única de impressão).

        PDF, portal e snapshot HTML do bloco `service_group` partem deste
        dict para não divergirem:

        - `rows`: uma por linha de serviço do grupo (`item` = 1..n na
          tabela), com `qty` = unidades e `subtotal` = valor da linha;
        - `subtotal`/`hours`: soma das linhas e horas (unidades x horas por
          unidade);
        - `days_label`: previsão de dias de serviço (vazio sem horas);
        - `units`: só as unidades identificadas (TAG ou série), por número
          de item.
        """
        self.ensure_one()
        lines = self._service_lines(group)
        rows = []
        for index, line in enumerate(lines, start=1):
            service = line.service_id
            procedure = service.procedure_code or ""
            if procedure and service.procedure_revision:
                procedure = "%s rev. %s" % (
                    procedure, service.procedure_revision)
            rows.append({
                "item": index,
                "line": line,
                "name": service.name or line.name or "",
                "description": service.scope_description or "",
                "procedure": procedure,
                "qty": line.product_uom_qty,
                "price_unit": line.price_unit,
                "subtotal": line.price_subtotal,
            })
        hours = sum(line._service_hours() for line in lines)
        days_label = ""
        if hours > 0:
            days_label = self._qualif_days_label(
                self._qualif_days_from_hours(
                    hours, self.env["engc.equipment"]))
        units = lines.service_unit_ids.filtered("is_identified").sorted(
            key=lambda u: (u.item_number, u.sequence, u.id))
        return {
            "group": group,
            "rows": rows,
            "subtotal": sum(row["subtotal"] for row in rows),
            "hours": hours,
            "days_label": days_label,
            "units": units,
        }

    def _proposal_service_titles(self):
        """Frentes cotadas, por extenso, para usar nos textos da proposta.

        "Qualificação Térmica" (se há qualificação) mais o título do
        capítulo de cada grupo de serviço, unidos por vírgula e " e " antes
        do último. Vazio se a cotação não tem nenhum dos dois.
        """
        self.ensure_one()
        titles = []
        if self.has_qualif_lines:
            titles.append(_("Qualificação Térmica"))
        titles += [group._chapter_title() for group in self._service_groups()]
        if len(titles) < 2:
            return "".join(titles)
        return _("%(head)s e %(last)s", head=", ".join(titles[:-1]),
                 last=titles[-1])
