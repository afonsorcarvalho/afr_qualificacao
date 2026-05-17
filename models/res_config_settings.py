# -*- coding: utf-8 -*-
"""Configurações do módulo AFR Qualificação (F4 16.0.3.3.0)."""
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
