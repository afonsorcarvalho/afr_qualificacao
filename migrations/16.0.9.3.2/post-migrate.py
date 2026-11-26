"""TPL-MULTI — textos de NR-13, calibração e aceite a partir das propostas reais.

As seções são `noupdate`; bases que já as têm (desde a 16.0.9.3.0) recebem o
texto novo aqui, só onde o corpo ainda é o semeado. Ver
`hooks._refresh_proposal_multi_texts`.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.afr_qualificacao.hooks import _refresh_proposal_multi_texts

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    changed = _refresh_proposal_multi_texts(env)
    _logger.info("TPL-MULTI: textos atualizados em %s", changed or "nenhuma seção")
