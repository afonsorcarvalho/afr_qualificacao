# -*- coding: utf-8 -*-
"""Extensões em engc.calibration.* para o módulo afr_qualificacao.

F4   (16.0.3.3.0): `has_valid_certificate` em instruments + hotfix is_valid
F4.3 (16.0.3.4.0): mapeamento grandeza/unidade ↔ instrumento via certificados,
                    permitindo casar coleta com instrumento compatível.
F10  (16.0.5.0.0): Plano de recursos metrológicos — instrumento ganha papéis
                    (validador/padrão via tags), capacidade por grandeza e
                    horas de setup, alimentando o bin-packing em sale.order.
"""
from odoo import api, fields, models


class AfrQualificacaoInstrumentFunction(models.Model):
    """Papel metrológico de um instrumento (tag).

    M2M (não Selection) porque um mesmo ativo pode atuar como padrão de
    calibração E como validador (data logger) simultaneamente. O algoritmo
    de plano de recursos filtra por estas tags:
      - demanda de pontos QD → função "validador"
      - demanda de malha     → função "padrão"
    """

    _name = "afr.qualificacao.instrument.function"
    _description = "Papel Metrológico de Instrumento"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        help="Código curto (ex: VALIDADOR, PADRAO).",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Código de papel deve ser único."),
    ]


class AfrQualificacaoInstrumentCapacity(models.Model):
    """Capacidade de medição de um instrumento por grandeza.

    Padrão típico = [(pressão, 1)]; logger típico = [(temp, 28), (pressão, 2)].
    `qty` é o nº de canais/pontos simultâneos que o instrumento cobre naquela
    grandeza. range_min/range_max ficam preparados para uso futuro (faixa de
    medição) — NÃO usados pelo algoritmo nesta versão.
    """

    _name = "afr.qualificacao.instrument.capacity"
    _description = "Capacidade de Medição por Grandeza"
    _order = "instrument_id, sensor_kind_id"

    instrument_id = fields.Many2one(
        comodel_name="engc.calibration.instruments",
        string="Instrumento",
        required=True,
        ondelete="cascade",
    )
    sensor_kind_id = fields.Many2one(
        comodel_name="afr.qualificacao.sensor.kind",
        string="Grandeza",
        required=True,
    )
    qty = fields.Integer(
        string="Canais",
        default=1,
        required=True,
        help="Nº de canais/pontos simultâneos cobertos nesta grandeza.",
    )
    # Preparado para faixa de medição (NÃO usado pelo algoritmo nesta versão).
    range_min = fields.Float(string="Faixa Mín.")
    range_max = fields.Float(string="Faixa Máx.")

    _sql_constraints = [
        (
            "instrument_kind_uniq",
            "unique(instrument_id, sensor_kind_id)",
            "Uma capacidade por grandeza por instrumento.",
        ),
    ]


class EngcCalibration(models.Model):
    """F4.10: ao concluir engc.calibration (state=done), cascateia malhas
    vinculadas via measurement → state=certified."""
    _inherit = "engc.calibration"

    def write(self, vals):
        res = super().write(vals)
        if vals.get("state") == "done":
            Malha = self.env["afr.qualificacao.malha"]
            for cal in self:
                # malhas vinculadas via engc_calibration_measurement_id.calibration_id == cal
                meas_ids = cal.measurement_ids.ids
                if not meas_ids:
                    continue
                malhas = Malha.search([
                    ("engc_calibration_measurement_id", "in", meas_ids),
                    ("state", "!=", "certified"),
                ])
                if malhas:
                    malhas.write({"state": "certified"})
        return res


class EngcCalibrationMeasurementUnit(models.Model):
    """F4.3: liga unidade de medida do engc_os à grandeza interna do
    afr_qualificacao para casar instrumentos com requisitos de coleta."""
    _inherit = "engc.calibration.measurement.unit"

    afr_sensor_kind_id = fields.Many2one(
        "afr.qualificacao.sensor.kind",
        string="Grandeza (AFR)",
        help=(
            "Grandeza correspondente em afr_qualificacao (Temp, Press, Hum…). "
            "Usada para derivar quais grandezas um instrumento padrão cobre, "
            "a partir das linhas de incerteza dos seus certificados."
        ),
    )


class EngcCalibrationInstrumentsCertificates(models.Model):
    """Hotfix: o compute `_compute_is_valid` no engc_os não itera self
    nem atribui valor — gera CacheMiss/ValueError em qualquer leitura.
    Sobrescreve aqui sem tocar o submódulo.
    """
    _inherit = "engc.calibration.instruments.certificates"

    @api.depends("validate_calibration")
    def _compute_is_valid(self):
        today = fields.Date.today()
        for r in self:
            r.is_valid = bool(
                r.validate_calibration and r.validate_calibration >= today
            )


class EngcCalibrationInstruments(models.Model):
    _inherit = "engc.calibration.instruments"

    # F10 — papéis, capacidade e setup para o plano de recursos.
    function_ids = fields.Many2many(
        comodel_name="afr.qualificacao.instrument.function",
        relation="afr_instrument_function_rel",
        column1="instrument_id",
        column2="function_id",
        string="Papéis Metrológicos",
        help=(
            "Papéis do instrumento no plano de recursos (validador, padrão "
            "de calibração ou ambos). Um data logger pode ter os dois."
        ),
    )
    measurement_capacity_ids = fields.One2many(
        comodel_name="afr.qualificacao.instrument.capacity",
        inverse_name="instrument_id",
        string="Capacidade por Grandeza",
        help=(
            "Canais/pontos simultâneos por grandeza. Ex.: logger "
            "[(Temp,28),(Press,2)]; padrão [(Press,1)]."
        ),
    )
    setup_hours = fields.Float(
        string="Horas de Setup",
        default=0.0,
        digits="Product Price",
        help=(
            "Tempo de instrumentação/re-instrumentação do recurso a cada "
            "grupo de execução. Somado às horas de utilização no plano."
        ),
    )

    has_valid_certificate = fields.Boolean(
        string="Cert. Válido",
        compute="_compute_has_valid_certificate",
        store=False,
        help=(
            "Verdadeiro quando pelo menos um certificado de calibração do "
            "instrumento possui data de validade >= hoje."
        ),
    )

    @api.depends("certificate_ids.validate_calibration")
    def _compute_has_valid_certificate(self):
        today = fields.Date.today()
        for r in self:
            r.has_valid_certificate = any(
                c.validate_calibration and c.validate_calibration >= today
                for c in r.certificate_ids
            )

    # ------------------------------------------------------------------
    # F4.3 — Cobertura grandeza/unidade derivada dos certificados
    # ------------------------------------------------------------------
    measurement_unit_ids = fields.Many2many(
        "engc.calibration.measurement.unit",
        compute="_compute_coverage",
        store=False,
        string="Unidades cobertas",
        help="Unidades de medida presentes nas linhas de incerteza dos certificados.",
    )
    sensor_kind_ids = fields.Many2many(
        "afr.qualificacao.sensor.kind",
        compute="_compute_coverage",
        store=False,
        string="Grandezas cobertas",
        help=(
            "Grandezas (TEMP, PRESS, etc) derivadas das unidades dos certificados "
            "via mapeamento engc.calibration.measurement.unit.afr_sensor_kind_id."
        ),
    )

    @api.depends(
        "certificate_ids.uncertainty_lines.unit_of_measurement",
        "certificate_ids.uncertainty_lines.unit_of_measurement.afr_sensor_kind_id",
    )
    def _compute_coverage(self):
        for r in self:
            units = self.env["engc.calibration.measurement.unit"]
            for cert in r.certificate_ids:
                for line in cert.uncertainty_lines:
                    if line.unit_of_measurement:
                        units |= line.unit_of_measurement
            r.measurement_unit_ids = units
            r.sensor_kind_ids = units.mapped("afr_sensor_kind_id")

    def name_get(self):
        # Garante exibição consistente nos M2M widgets: usa name; se faltar,
        # cai em id_number/tag/marca/modelo antes de "Sem identificação".
        result = []
        for r in self:
            label = (
                r.name
                or r.id_number
                or r.tag
                or (r.marca and r.modelo and "%s %s" % (r.marca, r.modelo))
                or r.marca
                or r.modelo
                or "Instrumento #%s" % r.id
            )
            result.append((r.id, label))
        return result
