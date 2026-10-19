# -*- coding: utf-8 -*-
"""Extensão da OS de Qualificação para o Relatório Final (P1, 16.0.8.0.0).

Mantida fora de `qualificacao_os.py` de propósito: o relatório final é um
subsistema próprio e evolui em P2–P5 sem tocar o arquivo da OS.
"""
from odoo import _, api, fields, models


class AfrQualificacaoOsRelatorioFinal(models.Model):
    _inherit = "afr.qualificacao.os"

    relatorio_final_ids = fields.One2many(
        "afr.qualificacao.relatorio",
        "os_id",
        string="Relatórios finais",
    )
    relatorio_final_count = fields.Integer(
        string="Relatórios finais",
        compute="_compute_relatorio_final_count",
    )

    @api.depends("relatorio_final_ids")
    def _compute_relatorio_final_count(self):
        for os in self:
            os.relatorio_final_count = len(os.relatorio_final_ids)

    def _relatorio_final_equipments(self):
        """Equipamentos elegíveis a relatório final, na ordem canônica
        `(name, id)`.

        Derivado das qualificações da OS com `state != "cancelled"` — e não
        de `equipment_ids` diretamente: esse M2M é computado a partir de
        TODAS as qualificações da OS (`_compute_equipment_ids`, sem filtro de
        estado), então um equipamento cujas qualificações estejam todas
        canceladas ainda apareceria em `equipment_ids`. Sem este filtro,
        `action_generate_relatorios()` geraria um relatório final vazio para
        esse equipamento (spec §12).
        """
        self.ensure_one()
        equips = self.sudo().qualificacao_ids.filtered(
            lambda q: q.state != "cancelled"
        ).mapped("equipment_id")
        return equips.sorted(key=lambda e: (e.name or "", e.id)).with_env(self.env)

    def _relatorio_final_default_dates(self):
        """(início, fim) dos ensaios: datas reais da OS, senão as planejadas.

        Converte o Datetime (UTC) para a data local do usuário.
        """
        self.ensure_one()
        start = self.date_actual_start or self.date_planned_start
        end = self.date_actual_end or self.date_planned_end

        def to_date(dt):
            return fields.Datetime.context_timestamp(self, dt).date() if dt else False

        return to_date(start), to_date(end)

    def action_generate_relatorios(self):
        """Cria os relatórios finais faltantes (um por equipamento). Idempotente.

        Relatórios existentes nunca são renumerados nem apagados. Equipamento
        novo recebe `index = max + 1` (via `create()` do relatório).

        Retorna o recordset com TODOS os relatórios finais das OSs em `self`.
        """
        Relatorio = self.env["afr.qualificacao.relatorio"]
        for os in self:
            existing = os.relatorio_final_ids.mapped("equipment_id")
            date_start, date_end = os._relatorio_final_default_dates()
            vals_list = [
                {
                    "os_id": os.id,
                    "equipment_id": equip.id,
                    "data_inicio_ensaios": date_start,
                    "data_fim_ensaios": date_end,
                }
                for equip in os._relatorio_final_equipments()
                if equip not in existing
            ]
            if vals_list:
                Relatorio.create(vals_list)
        return self.mapped("relatorio_final_ids").sorted(
            key=lambda r: (r.os_id.id, r.index, r.id)
        )

    def _relatorio_final_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Relatórios Finais"),
            "res_model": "afr.qualificacao.relatorio",
            "view_mode": "tree,form",
            "domain": [("os_id", "=", self.id)],
            "context": {"default_os_id": self.id, "create": False},
        }

    def action_generate_relatorios_open(self):
        """Botão "Gerar relatórios finais": gera os faltantes e abre a lista.

        Wrapper de UI: `action_generate_relatorios()` retorna recordset
        (contrato P1), que o web client não sabe serializar.
        """
        self.ensure_one()
        self.action_generate_relatorios()
        return self._relatorio_final_action()

    def action_view_relatorios_finais(self):
        """Smart button: só abre a lista, não gera."""
        return self._relatorio_final_action()
