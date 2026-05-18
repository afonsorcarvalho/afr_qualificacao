# -*- coding: utf-8 -*-
"""Extensões em engc.calibration.* para o módulo afr_qualificacao.

F4   (16.0.3.3.0): `has_valid_certificate` em instruments + hotfix is_valid
F4.3 (16.0.3.4.0): mapeamento grandeza/unidade ↔ instrumento via certificados,
                    permitindo casar coleta com instrumento compatível.
"""
from odoo import api, fields, models


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
