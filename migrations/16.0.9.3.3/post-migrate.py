"""TPL-MULTI — capítulo de NR-13 passa a se chamar
"Inspeção de segurança conforme a NR-13".

Template criado por hook (`noupdate`): bases que já o têm recebem o título
aqui, só onde ainda é o "NR-13" semeado. Ver
`hooks._retitle_proposal_multi_nr13`.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.afr_qualificacao.hooks import _retitle_proposal_multi_nr13


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _retitle_proposal_multi_nr13(env)
