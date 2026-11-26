"""TPL-MULTI — declaração de aceite antes das assinaturas.

O template é `noupdate` e criado por hook, então bases que já o têm (desde a
16.0.9.3.0) recebem a nova ordem aqui. Idempotente e conservador: ver
`hooks._reorder_proposal_multi_acceptance`.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.afr_qualificacao.hooks import (
    _reorder_proposal_multi_acceptance,
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _reorder_proposal_multi_acceptance(env)
