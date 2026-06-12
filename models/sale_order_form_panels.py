# -*- coding: utf-8 -*-
"""Painéis HTML read-only do form de cotação (aba Detalhes Técnicos).

Mantido separado de sale_order.py (já grande) por coesão: só renderização
HTML de conferência reusando os métodos de dados do relatório
(_qualif_equipment_summary, _qualif_cycle_specs, _qualif_estimated_hours/days).
"""
from markupsafe import Markup, escape

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    qualif_tecnico_html = fields.Html(
        compute="_compute_qualif_tecnico_html",
        string="Detalhes Técnicos",
        sanitize=False,
        help=(
            "Render read-only por equipamento: escopo + tabela de ciclos "
            "(temperatura/tempo/carga/tempo estimado) + tempo de execução. "
            "Reusa os métodos de dados do relatório de cotação."
        ),
    )

    @api.depends(
        "order_line.equipment_id",
        "order_line.qualification_type",
        "order_line.is_qualificacao_managed",
        "order_line.cycle_type_id",
        "order_line.malha_type_id",
        "order_line.name",
        "order_line.product_id",
        "order_line.qualif_cycle_qty",
        "order_line.product_uom_qty",
        "order_line.display_type",
        "order_line.temperature",
        "order_line.duration",
        "order_line.load_type",
        "order_line.estimated_hours",
    )
    def _compute_qualif_tecnico_html(self):
        for order in self:
            if not order.has_qualif_lines:
                order.qualif_tecnico_html = False
                continue
            summary = order._qualif_equipment_summary()
            if not summary:
                order.qualif_tecnico_html = False
                continue
            specs_by_equip = {
                s["equipment"].id: s for s in order._qualif_cycle_specs()
            }
            cards = Markup("")
            for s in summary:
                equip = s["equipment"]
                cards += order._qualif_tecnico_card(
                    equip, s, specs_by_equip.get(equip.id))
            total_h = order._qualif_estimated_hours()
            total_d = order._qualif_estimated_days()
            footer = (
                Markup('<div style="margin-top:10px;padding:8px 14px;'
                       'background:#714B67;color:#fff;border-radius:6px;'
                       'font-size:13px;font-weight:bold;">'
                       'TEMPO TOTAL DE EXECUÇÃO DA PROPOSTA: ')
                + escape('%.1f horas · %.1f dias úteis' % (total_h, total_d))
                + Markup('</div>')
            )
            order.qualif_tecnico_html = (
                Markup('<div style="width:100%;">') + cards + footer
                + Markup('</div>')
            )

    def _qualif_tecnico_card(self, equip, summary_entry, cycle_spec):
        """Card HTML de um equipamento: header + escopo + ciclos + tempo."""
        self.ensure_one()
        header = escape(equip.display_name or _("Equipamento"))
        if equip.serial_number:
            header = header + Markup(" — S/N: ") + escape(equip.serial_number)
        if equip.category_id:
            header = (header + Markup(" · Categoria: ")
                      + escape(equip.category_id.name))
        escopo = self._qualif_tecnico_escopo(summary_entry)
        ciclos = (self._qualif_tecnico_ciclos(cycle_spec, equip)
                  if cycle_spec and cycle_spec.get("rows") else Markup(""))
        h = self._qualif_estimated_hours(equip)
        d = self._qualif_estimated_days(equip)
        tempo = (
            Markup('<div style="margin-top:12px;font-size:12px;">'
                   '<span style="font-weight:bold;color:#714B67;">'
                   'TEMPO DE EXECUÇÃO (equipamento):</span> ')
            + escape('%.1f horas · %.1f dias úteis' % (h, d))
            + Markup('</div>')
        )
        return (
            Markup('<div style="border:1px solid #ddd;border-radius:6px;'
                   'margin:8px 0;padding:10px 14px;background:#fafafa;">'
                   '<div style="font-weight:bold;font-size:14px;color:#222;'
                   'border-bottom:1px solid #eee;padding-bottom:5px;'
                   'margin-bottom:8px;">')
            + header + Markup('</div>') + escopo + ciclos + tempo
            + Markup('</div>')
        )

    def _qualif_tecnico_escopo(self, summary_entry):
        """Tabela ESCOPO: Tipo (cabeçalho) → itens agrupados por parte."""
        rows = Markup("")
        for tp in summary_entry["types"]:
            rows += (
                Markup('<tr style="background:#f0eef0;">'
                       '<td style="padding:4px 10px;font-weight:bold;" '
                       'colspan="2">')
                + escape(tp["label"]) + Markup('</td></tr>')
            )
            for pcode, plabel in (("01", "Parte 01"), ("02", "Parte 02"),
                                  ("", "")):
                part_items = [
                    i for i in tp["items"] if (i.get("part") or "") == pcode]
                if not part_items:
                    continue
                # Sem "× qty": o nome já traz "— N ciclo(s)/malha(s)" e as
                # quantidades/horas estão na TABELA DE CICLOS (igual ao print).
                names = Markup(" · ").join(
                    (Markup('<span style="text-decoration:line-through;'
                            'color:#999;">') + escape(i["name"])
                     + Markup('</span>'))
                    if i.get("declined") else escape(i["name"])
                    for i in part_items
                )
                rows += (
                    Markup('<tr><td style="padding:3px 10px;width:70px;'
                           'color:#888;">') + escape(plabel)
                    + Markup('</td><td style="padding:3px 10px;">')
                    + names + Markup('</td></tr>')
                )
        return (
            Markup('<div style="font-weight:bold;color:#714B67;'
                   'font-size:12px;margin:10px 0 4px;">ESCOPO</div>'
                   '<table style="border-collapse:collapse;width:100%;'
                   'font-size:12px;border:1px solid #e0e0e0;"><tbody>')
            + rows + Markup('</tbody></table>')
        )

    def _qualif_tecnico_ciclos(self, cycle_spec, equip):
        """Tabela de Ciclos (cycle_spec de _qualif_cycle_specs)."""
        wh = self._qualif_work_hours_per_day(equip) or 8.0
        rows = Markup("")
        total_qty = 0
        total_hours = 0.0
        for idx, row in enumerate(cycle_spec["rows"]):
            bg = "background:#fafafa;" if idx % 2 else ""
            total_qty += row["qty"] or 0
            total_hours += row["estimated_hours_total"] or 0.0
            rows += (
                Markup('<tr style="%s">' % bg)
                + Markup('<td style="padding:4px 10px;">')
                + escape(row["name"]) + Markup('</td>')
                + Markup('<td style="padding:4px 8px;text-align:center;">')
                + escape(str(row["qty"])) + Markup('</td>')
                + Markup('<td style="padding:4px 8px;text-align:center;">')
                + escape(row["temperature"] or "") + Markup('</td>')
                + Markup('<td style="padding:4px 8px;text-align:center;">')
                + escape(row["duration"] or "") + Markup('</td>')
                + Markup('<td style="padding:4px 8px;text-align:center;">')
                + escape(row["load_type"] or "") + Markup('</td>')
                + Markup('<td style="padding:4px 10px;text-align:right;">')
                + escape('%.1f h' % (row["estimated_hours_total"] or 0.0))
                + Markup('</td></tr>')
            )
        head = (
            Markup('<thead><tr style="background:#714B67;color:#fff;">'
                   '<th style="padding:5px 10px;text-align:left;">Ciclo</th>'
                   '<th style="padding:5px 8px;text-align:center;">Qtd</th>'
                   '<th style="padding:5px 8px;text-align:center;">'
                   'Temperatura</th>'
                   '<th style="padding:5px 8px;text-align:center;">')
            + escape(cycle_spec.get("time_label") or "Tempo")
            + Markup('</th>'
                     '<th style="padding:5px 8px;text-align:center;">Carga</th>'
                     '<th style="padding:5px 10px;text-align:right;">'
                     'Tempo Estimado</th></tr></thead>')
        )
        foot = (
            Markup('<tfoot><tr style="border-top:2px solid #333;'
                   'font-weight:bold;"><td style="padding:5px 10px;" '
                   'colspan="5">Total: ')
            + escape('%d ciclo(s)' % total_qty)
            + Markup('</td><td style="padding:5px 10px;text-align:right;">')
            + escape('%.1f h · %.1f dias' % (total_hours, total_hours / wh))
            + Markup('</td></tr></tfoot>')
        )
        return (
            Markup('<div style="font-weight:bold;color:#714B67;'
                   'font-size:12px;margin:14px 0 4px;">TABELA DE CICLOS</div>'
                   '<table style="border-collapse:collapse;width:100%;'
                   'font-size:12px;border:1px solid #e0e0e0;">')
            + head + Markup('<tbody>') + rows + Markup('</tbody>') + foot
            + Markup('</table>')
        )
