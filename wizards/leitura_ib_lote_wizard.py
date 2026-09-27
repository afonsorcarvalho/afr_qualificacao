# -*- coding: utf-8 -*-
"""Wizard "Preencher leituras de IB em lote" (F11 relatório final, 16.0.8.4.1).

Cria uma leitura de IB por ciclo marcado que AINDA NÃO tem leitura no
relatório — ciclos marcados que já têm leitura são pulados (nunca
sobrescritos; o usuário edita a linha existente na tabela se precisar
corrigir um IB que deu positivo). A trava editorial do próprio
`afr.relatorio.leitura.ib` já recusa a criação fora de rascunho — o botão
que abre este wizard só aparece com o relatório em rascunho.
"""
from odoo import _, api, fields, models


class AfrRelatorioLeituraIbLote(models.TransientModel):
    _name = "afr.relatorio.leitura.ib.lote"
    _description = "Wizard: preencher leituras de IB em lote"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    cycle_all_ids = fields.Many2many(
        "afr.qualificacao.cycle",
        related="relatorio_id.cycle_ids",
        string="Ciclos do relatório",
    )
    cycle_ids = fields.Many2many(
        "afr.qualificacao.cycle",
        relation="afr_relatorio_leitura_ib_lote_cycle_rel",
        column1="wizard_id",
        column2="cycle_id",
        string="Ciclos",
        domain="[('id', 'in', cycle_all_ids)]",
        help="Pré-marcados os ciclos que ainda não têm leitura registrada. "
             "Desmarque/marque conforme necessário.",
    )
    indicador_id = fields.Many2one(
        "afr.relatorio.indicador",
        string="Indicador",
        domain="[('relatorio_id', '=', relatorio_id), ('tipo', '=', 'biologico')]",
    )
    data_incubacao = fields.Date(string="Data de incubação")
    data_leitura = fields.Date(string="Data de leitura")
    leitor = fields.Char(string="Leitor", help="Quem fez a leitura.")
    resultado = fields.Selection(
        [("negativo", "Negativo"), ("positivo", "Positivo")],
        default="negativo",
    )
    controle_positivo_ok = fields.Boolean(
        string="Controle positivo OK", default=True
    )
    quantidade = fields.Integer(
        string="Qtd. IB por ciclo",
        default=1,
        help="Quantos indicadores biológicos foram usados em cada ciclo marcado.",
    )

    @api.onchange("relatorio_id")
    def _onchange_relatorio_id(self):
        for wiz in self:
            rel = wiz.relatorio_id
            if not rel:
                continue
            existentes = set(rel.leitura_ib_ids.mapped("cycle_id").ids)
            faltantes = rel.cycle_ids.filtered(lambda c: c.id not in existentes)
            faltantes = faltantes.sorted(key=lambda c: c._relatorio_cycle_sort_key())
            wiz.cycle_ids = [(6, 0, faltantes.ids)]
            biologicos = rel.indicador_ids.filtered(lambda i: i.tipo == "biologico")
            if len(biologicos) == 1:
                wiz.indicador_id = biologicos.id

    def action_confirm(self):
        """Cria uma leitura por ciclo marcado sem leitura; pula os demais."""
        self.ensure_one()
        rel = self.relatorio_id
        existentes = set(rel.leitura_ib_ids.mapped("cycle_id").ids)
        ciclos = self.cycle_ids.sorted(key=lambda c: c._relatorio_cycle_sort_key())
        Leitura = self.env["afr.relatorio.leitura.ib"]
        criadas = 0
        puladas = 0
        for cycle in ciclos:
            if cycle.id in existentes:
                puladas += 1
                continue
            Leitura.create({
                "relatorio_id": rel.id,
                "cycle_id": cycle.id,
                "indicador_id": self.indicador_id.id,
                "data_incubacao": self.data_incubacao,
                "data_leitura": self.data_leitura,
                "leitor": self.leitor,
                "resultado": self.resultado,
                "controle_positivo_ok": self.controle_positivo_ok,
                "quantidade": self.quantidade,
            })
            criadas += 1
        if puladas:
            message = _(
                "%(criadas)d leitura(s) criada(s). %(puladas)d ciclo(s) já tinha(m) "
                "leitura e foram pulados."
            ) % {"criadas": criadas, "puladas": puladas}
        else:
            message = _("%(criadas)d leitura(s) criada(s).") % {"criadas": criadas}
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Leituras de IB"),
                "message": message,
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
