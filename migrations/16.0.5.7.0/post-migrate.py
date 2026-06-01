"""Retrofit do bloco Dados Cadastrais no template QI/QO/QD em upgrade.

post_init_hook só roda em install; em -u (labquali já instalada) este
post-migrate garante o bloco institucional no template existente.
"""

from odoo import api, SUPERUSER_ID

from odoo.addons.afr_qualificacao.hooks import _ensure_company_data_block


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_company_data_block(env)
