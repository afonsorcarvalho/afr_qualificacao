"""Cotação multi-serviço — instala o template TPL-MULTI (default).

post_init_hook só roda em install; bases existentes recebem o template aqui.
Idempotente (mesma função do hooks.py). Cotações já existentes mantêm o
template que têm; só as novas pegam o TPL-MULTI (sequence 1).
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.afr_qualificacao.hooks import _install_proposal_multi_template


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _install_proposal_multi_template(env)
