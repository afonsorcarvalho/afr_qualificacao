# -*- coding: utf-8 -*-
from odoo import _, fields, models


class EngcEquipmentCategory(models.Model):
    _inherit = "engc.equipment.category"

    process_type = fields.Selection(
        selection=[
            ("esterilizacao", "Esterilização"),
            ("lavagem", "Lavagem"),
            ("desinfeccao", "Desinfecção"),
            ("monitoramento", "Monitoramento"),
        ],
        string="Tipo de Processo",
        default="esterilizacao",
        required=True,
        help="Define o rótulo da coluna de tempo na tabela de ciclos da "
             "proposta (Esterilização / Lavagem / Desinfecção / Monitoramento).",
    )

    def _qualif_time_label(self):
        """Rótulo da coluna de tempo da tabela de ciclos, por tipo de processo."""
        self.ensure_one()
        labels = {
            "esterilizacao": _("Tempo de Esterilização"),
            "lavagem": _("Tempo de Lavagem"),
            "desinfeccao": _("Tempo de Desinfecção"),
            "monitoramento": _("Tempo de Ciclo"),
        }
        return labels.get(self.process_type or "esterilizacao",
                          _("Tempo de Esterilização"))

    def _qualif_process_word(self):
        """Substantivo do processo p/ os bullets do Escopo (ex: '10 min <word>').

        Segue o mesmo `process_type` que dirige a coluna da tabela de ciclos,
        mantendo Escopo e Tabela de Ciclos coerentes. Monitoramento → '' (o
        bullet exibe só o tempo, sem sufixo de processo).
        """
        self.ensure_one()
        words = {
            "esterilizacao": _("esterilização"),
            "lavagem": _("lavagem"),
            "desinfeccao": _("desinfecção"),
            "monitoramento": "",
        }
        return words.get(self.process_type or "esterilizacao",
                         _("esterilização"))
