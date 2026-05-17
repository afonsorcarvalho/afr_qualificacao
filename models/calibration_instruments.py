# -*- coding: utf-8 -*-
"""Extensões em engc.calibration.instruments para o módulo afr_qualificacao.

F4 (16.0.3.3.0): expõe flag computed `has_valid_certificate` para
sinalização visual nos listings de padrões metrológicos consumidos pelas
coletas (afr.qualificacao.collect.item).
"""
from odoo import api, fields, models


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
