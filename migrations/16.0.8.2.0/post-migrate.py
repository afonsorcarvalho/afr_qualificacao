"""Relatório Final P3 — semeia seções e templates RQT-HOSP / RQT-IND.

post_init_hook só roda em install; bases existentes recebem os seeds aqui.
Idempotente (mesma função do hooks.py).
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.afr_qualificacao.hooks import _seed_relatorio_templates


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_relatorio_templates(env)
