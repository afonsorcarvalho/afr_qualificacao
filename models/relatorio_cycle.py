# -*- coding: utf-8 -*-
"""Extensão do ciclo para o Relatório Final (P1, 16.0.8.0.0).

Acrescenta ao `afr.qualificacao.cycle` a janela de esterilização, a disposição
dos sensores (canal do validador → posição física → IB) e o `extracted_json`
reservado para a extração futura do arquivo bruto do validador (spec D1).
Fica fora de `qualificacao_cycle.py` de propósito, como `relatorio_os.py`.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AfrRelatorioSensorPos(models.Model):
    """Posição de um sensor (canal do validador) dentro da câmara num ciclo."""

    _name = "afr.relatorio.sensor.pos"
    _description = "Posição de Sensor no Ciclo"
    _order = "cycle_id, sequence, id"
    _rec_name = "canal"

    cycle_id = fields.Many2one(
        "afr.qualificacao.cycle",
        string="Ciclo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    canal = fields.Char(required=True, help='Canal do validador, ex.: "CH006".')
    posicao = fields.Char(string="Posição", help='Ex.: "Dreno", "Centro geométrico".')
    ib_label = fields.Char(string="IB", help='Rótulo do IB junto ao sensor, ex.: "IB1".')


class AfrQualificacaoCycleRelatorio(models.Model):
    _inherit = "afr.qualificacao.cycle"

    janela_inicio = fields.Datetime(
        string="Início da esterilização",
        help="Início da janela de esterilização (patamar) do ciclo.",
    )
    janela_fim = fields.Datetime(
        string="Fim da esterilização",
    )
    sensor_pos_ids = fields.One2many(
        "afr.relatorio.sensor.pos",
        "cycle_id",
        string="Posição dos sensores",
        copy=True,
    )
    sensor_pos_count = fields.Integer(
        string="Sensores",
        compute="_compute_sensor_pos_count",
    )
    extracted_json = fields.Text(
        string="Dados extraídos (JSON)",
        copy=False,
        help=(
            "Reservado para a extração futura do arquivo do validador "
            "(min/max/média/F0 por canal). Vazio na fase 1."
        ),
    )

    @api.depends("sensor_pos_ids")
    def _compute_sensor_pos_count(self):
        for cycle in self:
            cycle.sensor_pos_count = len(cycle.sensor_pos_ids)

    @api.constrains("janela_inicio", "janela_fim")
    def _check_janela(self):
        for cycle in self:
            if (
                cycle.janela_inicio
                and cycle.janela_fim
                and cycle.janela_fim < cycle.janela_inicio
            ):
                raise ValidationError(_(
                    "Fim da esterilização deve ser ≥ início (%s)."
                ) % cycle.display_name)

    # Ordem das etapas no relatório: QI < QO < QD (demais tipos ao fim).
    _QUALIF_TYPE_RANK = {"installation": 0, "operational": 1, "performance": 2}

    def _relatorio_cycle_sort_key(self):
        """Chave de ordem dos ciclos no relatório do equipamento:
        tipo de qualificação (QI<QO<QD), tipo de ciclo (`sequence, name, id`
        do cycle.type, como o `_order` dele), sequence, id."""
        ctype = self.cycle_type_id
        return (
            self._QUALIF_TYPE_RANK.get(self.qualificacao_id.qualification_type, 9),
            ctype.sequence or 0,
            ctype.name or "",
            ctype.id,
            self.sequence or 0,
            self.id,
        )

    def _previous_cycle_with_sensor_pos(self):
        """Ciclo anterior mais próximo, no relatório do mesmo equipamento, com
        posições.

        Considera todos os ciclos das qualificações não canceladas da mesma
        OS e do mesmo equipamento (o escopo de um relatório final), na ordem
        `_relatorio_cycle_sort_key` — assim o 1º ciclo de QD copia do último
        ciclo de QO. Pula ciclos anteriores ainda sem posições. Retorna
        recordset vazio quando não há nenhum.
        """
        self.ensure_one()
        qualif = self.qualificacao_id
        if not qualif.os_id:
            return self.browse()
        siblings = self.search([
            ("qualificacao_id.os_id", "=", qualif.os_id.id),
            ("qualificacao_id.equipment_id", "=", qualif.equipment_id.id),
            ("qualificacao_id.state", "!=", "cancelled"),
        ]).sorted(key=lambda c: c._relatorio_cycle_sort_key())
        ids = siblings.ids
        if self.id not in ids:
            return self.browse()
        for candidate in reversed(siblings[: ids.index(self.id)]):
            if candidate.sensor_pos_ids:
                return candidate
        return self.browse()

    def action_copy_sensor_pos_from_previous(self):
        """Copia as posições de sensor do ciclo anterior (mesma OS + equipamento).

        Substitui as linhas atuais deste ciclo. Sem ciclo anterior com
        posições, não faz nada e retorna False (sem UserError: o botão
        simplesmente não tem efeito).
        """
        self.ensure_one()
        source = self._previous_cycle_with_sensor_pos()
        if not source:
            return False
        self.sensor_pos_ids.unlink()
        self.env["afr.relatorio.sensor.pos"].create([
            {
                "cycle_id": self.id,
                "sequence": pos.sequence,
                "canal": pos.canal,
                "posicao": pos.posicao,
                "ib_label": pos.ib_label,
            }
            for pos in source.sensor_pos_ids
        ])
        return True

    def action_open_relatorio_cycle(self):
        """Abre o form do ciclo (janela, sensores, arquivos) a partir da aba
        Ciclos do relatório final."""
        self.ensure_one()
        return self.action_open_for_collect()
