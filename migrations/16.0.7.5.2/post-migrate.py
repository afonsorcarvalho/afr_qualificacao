# -*- coding: utf-8 -*-
"""Recalcula engc.equipment.name com o novo _compute_name (partes opcionais)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    equipments = env["engc.equipment"].with_context(active_test=False).search([])
    env.add_to_compute(equipments._fields["name"], equipments)
    equipments.flush_recordset(["name"])
