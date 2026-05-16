"""Grandezas físicas usadas em malhas de calibração.

Catálogo extensível (em vez de Selection hardcoded) para permitir adicionar
novas grandezas (pH, condutividade, etc.) via UI, sem deploy de código.

Cada `afr.qualificacao.malha.type` aponta para uma `afr.qualificacao.sensor.kind`
para identificar qual grandeza física é medida (temperatura, pressão, etc.).
"""

from odoo import fields, models


class AfrQualificacaoSensorKind(models.Model):
    """Grandeza física medida em uma malha de calibração."""

    _name = "afr.qualificacao.sensor.kind"
    _description = "Grandeza Física de Sensor"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Nome da grandeza física (ex: Temperatura, Pressão, Umidade).",
    )
    code = fields.Char(
        help="Código curto da grandeza (ex: TEMP, PRESS, HUM).",
    )
    unit = fields.Char(
        help="Unidade de medida default da grandeza (ex: °C, Pa, % UR).",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
