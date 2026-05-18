# -*- coding: utf-8 -*-
"""Configurações do módulo AFR Qualificação (F4/F4.3)."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    qualif_block_approval_expired_standards = fields.Boolean(
        string="Bloquear aprovação com padrão expirado",
        config_parameter="afr_qualificacao.qualif_block_approval_expired_standards",
        help=(
            "Quando ativo, action_mark_approved levanta erro se algum padrão "
            "metrológico (engc.calibration.instruments) referenciado pelos "
            "collect.items não possuir certificado de calibração válido (data "
            "de validade >= hoje). Quando inativo (padrão), apenas registra "
            "aviso no chatter."
        ),
    )
    qualif_block_approval_incomplete_coverage = fields.Boolean(
        string="Bloquear aprovação com cobertura incompleta",
        config_parameter="afr_qualificacao.qualif_block_approval_incomplete_coverage",
        help=(
            "F4.3: quando ativo, action_mark_approved levanta erro se algum "
            "collect.item required + requires_instrument tem cobertura de "
            "grandezas incompleta (algum sensor_kind requerido não está "
            "coberto pelos instrumentos selecionados). Quando inativo (padrão), "
            "apenas registra aviso no chatter."
        ),
    )
