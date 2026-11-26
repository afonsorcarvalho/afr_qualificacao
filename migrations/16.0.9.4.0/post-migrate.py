"""Descrição editável nas linhas de serviço da cotação.

Campo novo `sale.order.line.service_description`. Linhas de serviço que já
existiam passam a guardar o escopo do catálogo, que era o texto impresso
abaixo do nome — a proposta delas não muda.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["sale.order.line"].search([
        ("is_service_managed", "=", True),
        ("service_id", "!=", False),
        ("service_description", "=", False),
    ])
    for line in lines:
        if line.service_id.scope_description:
            line.service_description = line.service_id.scope_description
