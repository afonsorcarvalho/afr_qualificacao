"""Remove os blocos financial/optionals do template LabQuali em upgrade.

Escopo tabela de ciclos (2026-08-20): o template default "Proposta LabQuali
QI/QO/QD" deixou de ter linhas `financial`/`optionals` — os totais passaram
para o fim do bloco `equipment_scope` e os opcionais aceitos aparecem lá
como adicionais (ver hooks.PROPOSAL_TEMPLATE_LINES). O post_init_hook só
cria esse template no install; em bases já instaladas (labquali) esta
migração remove as duas linhas do template EXISTENTE, no próximo -u.

Mira o template pelo XMLID `afr_qualificacao.proposal_template_labquali`,
NÃO pelo `code` ("TPL-LABQUALI") — o `code` não é único: a base real do
cliente tem um segundo template ("Proposta LabQuali QI/QO/QD CLIETE TAL",
id=6) com o MESMO code, criado pelo cliente customizando uma cópia do
default. Um `<delete>` por `code` (como o data file anterior fazia)
apagava as linhas dos dois templates — incluindo o customizado do
cliente — a cada `-u`, o que contradiz a filosofia do módulo (o
utilizador controla o template default 100%, ver __manifest__.py).

Migração roda uma vez só (versão fixa), então não tem esse problema:
mira só o template com o XMLID do seed, e só nesse upgrade específico.

Só mexe no TEMPLATE. Blocos já materializados em cotações
(afr.proposal.block) não são tocados de propósito — cotação antiga
continua renderizando como foi montada.
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    template = env.ref(
        "afr_qualificacao.proposal_template_labquali",
        raise_if_not_found=False,
    )
    if not template:
        return
    lines = template.line_ids.filtered(
        lambda l: l.block_kind in ("financial", "optionals"))
    if lines:
        _logger.info(
            "afr_qualificacao 16.0.7.0.0: removendo %d linha(s) "
            "financial/optionals do template %s (id=%d).",
            len(lines), template.display_name, template.id,
        )
        lines.unlink()
