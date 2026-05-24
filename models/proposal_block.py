"""Bloco de proposta montado por cotação (F8.2 — Proposta LEGO).

Cada `afr.proposal.block` é uma peça de lego de uma proposta concreta.
O wizard configurador (ou o botão "Carregar Blocos") copia os slots do
`afr.proposal.template` escolhido para blocos da `sale.order`, onde o
comercial monta a proposta: reordena, liga/desliga (`included`) e edita
o texto (`body`) sem afetar a biblioteca institucional de seções.

O relatório de cotação (F8.3) percorre os blocos `included=True` na
ordem de `sequence`.
"""

from markupsafe import Markup, escape

from odoo import fields, models, _
from odoo.tools.misc import formatLang

from .proposal_template import PROPOSAL_BLOCK_KINDS


class AfrProposalBlock(models.Model):
    """Bloco de proposta de uma sale.order específica."""

    _name = "afr.proposal.block"
    _description = "Bloco de Proposta da Cotação"
    _order = "sequence, id"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    block_kind = fields.Selection(
        selection=PROPOSAL_BLOCK_KINDS,
        string="Tipo de Bloco",
        required=True,
        default="static",
    )
    section_id = fields.Many2one(
        comodel_name="afr.proposal.section",
        string="Seção de Origem",
        ondelete="set null",
        help="Bloco de texto da biblioteca que originou este bloco.",
    )
    title = fields.Char(
        string="Título",
        help="Título exibido no relatório (editável por proposta).",
    )
    body = fields.Html(
        string="Conteúdo",
        sanitize=True,
        help=(
            "Conteúdo do bloco, cópia editável da seção de origem. Aceita "
            "expressões {{ ... }} resolvidas na renderização da proposta."
        ),
    )
    included = fields.Boolean(
        string="Incluir na Proposta",
        default=True,
        help="Desmarque para omitir este bloco do PDF sem apagá-lo.",
    )
    page_break = fields.Boolean(
        string="Nova Página",
        default=False,
        help=(
            "Se marcado, o bloco inicia em nova página no PDF. Caso "
            "contrário, continua na mesma página do bloco anterior."
        ),
    )

    def name_get(self):
        """Display: título do bloco ou rótulo do tipo dinâmico."""
        kind_labels = dict(PROPOSAL_BLOCK_KINDS)
        result = []
        for record in self:
            label = record.title or kind_labels.get(
                record.block_kind, record.block_kind or ""
            )
            result.append((record.id, label))
        return result

    # ------------------------------------------------------------------
    # F8.5 — editar bloco (modal); snapshot de bloco dinâmico → texto
    # ------------------------------------------------------------------
    def action_edit_block(self):
        """Abre o editor do bloco em modal.

        Bloco dinâmico (escopo, ciclos, financeiro...) é convertido por
        snapshot: o conteúdo auto-gerado é congelado em HTML editável e o
        bloco passa a ser `static` — a partir daí é texto livre.
        """
        self.ensure_one()
        if self.block_kind != "static":
            self.body = self._snapshot_html()
            if not self.title:
                self.title = dict(PROPOSAL_BLOCK_KINDS).get(self.block_kind, "")
            self.block_kind = "static"
        return {
            "type": "ir.actions.act_window",
            "name": _("Editar Bloco da Proposta"),
            "res_model": "afr.proposal.block",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(
                self.env.ref("afr_qualificacao.view_proposal_block_form").id,
                "form",
            )],
            "target": "new",
        }

    def _snapshot_html(self):
        """Renderiza o conteúdo dinâmico atual do bloco em HTML editável."""
        self.ensure_one()
        builder = {
            "equipment_scope": self._html_equipment_scope,
            "cycle_specs": self._html_cycle_specs,
            "schedule": self._html_schedule,
            "standards_table": self._html_standards,
            "financial": self._html_financial,
            "optionals": self._html_optionals,
            "acceptance": self._html_acceptance,
        }.get(self.block_kind)
        if not builder:
            return self.body or Markup("")
        return builder(self.sale_order_id)

    def _money(self, order, value):
        """Formata valor monetário na moeda da cotação."""
        return formatLang(self.env, value, currency_obj=order.currency_id)

    def _html_equipment_scope(self, order):
        # F8.10 — sem subtotal por equipamento; calib formatado como
        # "0N Calibração de <malha>" (item.name já traz o prefixo
        # "Calibração de " via _qualif_equipment_summary).
        parts = []
        for eq in order._qualif_equipment_summary():
            equip = eq["equipment"]
            head = escape(equip.name or "")
            if equip.serial_number:
                head += Markup(" — S/N: ") + escape(equip.serial_number)
            parts.append(Markup("<h4>%s</h4>") % head)
            for tipo in eq["types"]:
                parts.append(
                    Markup("<p><strong>%s</strong></p>") % escape(tipo["label"])
                )
                is_calib = tipo["code"] == "calibration"
                items = []
                for it in tipo["items"]:
                    if is_calib:
                        items.append(Markup("<li>%02d %s</li>") % (
                            int(it["qty"] or 0), escape(it["name"]),
                        ))
                    else:
                        suffix = (
                            Markup(" — qtd: %s") % it["qty"]
                            if it["qty"] and it["qty"] != 1 else Markup("")
                        )
                        items.append(Markup("<li>%s%s</li>") % (
                            escape(it["name"]), suffix,
                        ))
                parts.append(Markup("<ul>%s</ul>") % Markup("").join(items))
        return Markup("").join(parts) or Markup("<p></p>")

    def _html_cycle_specs(self, order):
        parts = []
        for spec in order._qualif_cycle_specs():
            parts.append(
                Markup("<h4>%s</h4>") % escape(spec["equipment"].name or "")
            )
            rows = Markup("").join(
                Markup(
                    "<tr><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s</td><td>%s</td></tr>"
                ) % (
                    row["qty"], escape(row["name"]),
                    escape(row["temperature"]), escape(row["duration"]),
                    escape(row["load_type"]),
                )
                for row in spec["rows"]
            )
            parts.append(Markup(
                "<table><thead><tr><th>Qtd</th><th>Ciclo</th>"
                "<th>Temperatura</th><th>Tempo</th><th>Carga</th></tr>"
                "</thead><tbody>%s</tbody></table>"
            ) % rows)
        return Markup("").join(parts) or Markup("<p></p>")

    def _html_schedule(self, order):
        """F8.14 — tabela cronograma equipamento × horas × dias úteis."""
        rows = order._qualif_schedule_rows()
        if not rows:
            return Markup("<p></p>")
        body = [Markup(
            "<table class='qq-table'>"
            "<thead><tr><th>Equipamento</th>"
            "<th style='text-align:right;'>Horas</th>"
            "<th style='text-align:right;'>Dias úteis</th></tr></thead><tbody>"
        )]
        total_h = 0.0
        for r in rows:
            body.append(Markup(
                "<tr><td>%s</td>"
                "<td style='text-align:right;'>%.1f</td>"
                "<td style='text-align:right;'>%.2f</td></tr>"
            ) % (
                escape(r["equipment"].display_name or ""),
                r["hours"], r["days"],
            ))
            total_h += r["hours"]
        body.append(Markup(
            "</tbody>"
            "<tfoot><tr><td><strong>TOTAL</strong></td>"
            "<td style='text-align:right;'><strong>%.1f</strong></td>"
            "<td style='text-align:right;'><strong>%.2f</strong></td></tr></tfoot>"
            "</table>"
        ) % (total_h, total_h / 8.0 if total_h else 0.0))
        return Markup("").join(body)

    def _html_standards(self, order):
        rows = Markup("").join(
            Markup(
                "<tr><td><strong>%s</strong></td><td>%s</td>"
                "<td>%s</td><td>%s</td></tr>"
            ) % (
                escape(std.code or ""), escape(std.name or ""),
                escape(std.organism or ""), escape(std.description or ""),
            )
            for std in order.qualif_standard_ids
        )
        return Markup(
            "<table><thead><tr><th>Código</th><th>Nome</th>"
            "<th>Organismo</th><th>Escopo</th></tr></thead>"
            "<tbody>%s</tbody></table>"
        ) % rows

    def _html_financial(self, order):
        rows = Markup("").join(
            Markup("<tr><td>%s</td><td>%s</td></tr>") % (
                escape(eq["equipment"].name or ""),
                escape(self._money(order, eq["subtotal"])),
            )
            for eq in order._qualif_equipment_summary()
        )
        return Markup(
            "<table><thead><tr><th>Equipamento</th><th>Subtotal</th></tr>"
            "</thead><tbody>%s</tbody></table>"
            "<p><strong>Subtotal: %s</strong></p>"
            "<p><strong>Impostos: %s</strong></p>"
            "<p><strong>TOTAL GERAL: %s</strong></p>"
        ) % (
            rows,
            escape(self._money(order, order.amount_untaxed)),
            escape(self._money(order, order.amount_tax)),
            escape(self._money(order, order.amount_total)),
        )

    def _html_optionals(self, order):
        opt_lines = order.order_line.filtered("is_proposal_optional")
        rows = Markup("").join(
            Markup(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            ) % (
                escape(line.name or ""),
                line.product_uom_qty,
                escape(self._money(order, line.price_unit)),
                escape(self._money(order, line.price_subtotal)),
            )
            for line in opt_lines
        )
        return Markup(
            "<table><thead><tr><th>Serviço</th><th>Qtd</th>"
            "<th>Valor Unit.</th><th>Subtotal</th></tr></thead>"
            "<tbody>%s</tbody></table>"
        ) % rows

    def _html_acceptance(self, order):
        return Markup(
            "<p>Declaro estar de acordo com os termos, escopo e valores "
            "apresentados nesta proposta.</p>"
            "<p><br/></p>"
            "<p>____________________________________</p>"
            "<p><strong>CLIENTE</strong> — %s</p>"
            "<p><br/></p>"
            "<p>____________________________________</p>"
            "<p><strong>EMPRESA</strong> — %s</p>"
            "<p>Local e data: ____________________, ____ / ____ / ________</p>"
        ) % (
            escape(order.partner_id.name or ""),
            escape(order.company_id.name or ""),
        )
