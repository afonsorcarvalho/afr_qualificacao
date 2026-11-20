"""Cotação multi-serviço — instala o template TPL-MULTI (default).

post_init_hook só roda em install; bases existentes recebem o template aqui.
Idempotente (mesma função do hooks.py). Cotações já existentes mantêm o
template que têm; só as novas pegam o TPL-MULTI (menor sequence).

Também ajusta dados `noupdate` que o -u não reprocessa: o corpo do e-mail da
proposta (só se ainda tiver a frase antiga exata) e o plural do rótulo da
unidade dos grupos semeados (só onde está vazio).
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.afr_qualificacao.hooks import (
    _fill_service_group_plurals,
    _install_proposal_multi_template,
    _upgrade_proposal_mail_body,
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _install_proposal_multi_template(env)
    _upgrade_proposal_mail_body(env)
    _fill_service_group_plurals(env)
