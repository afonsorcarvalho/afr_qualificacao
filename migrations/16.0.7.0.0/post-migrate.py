"""Remove os blocos financial/optionals do template LabQuali em upgrade, e
os blocos financial/cycle_specs já materializados nas cotações.

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

Ajuste de 2026-08-20 (fix pós-validação do PDF pelo cliente): o bloco
`financial` ("Resumo Financeiro") deixou de ter QUALQUER renderização nos
três renders (PDF/portal/snapshot Python) — a tabela de totais agora é
emitida sempre, incondicionalmente, ao fim do escopo por equipamento. O
tipo `cycle_specs` ("Tabela de Ciclos") também já não é mais semeado no
template default desde que os ciclos passaram a aparecer embutidos nas
tabelas de escopo por equipamento (`_qualif_scope_tables`).

Isso significa que blocos `afr.proposal.block` materializados com
`block_kind in ('financial', 'cycle_specs')` em cotações já existentes
(labquali) viraram lixo: não renderizam mais nada, mas continuam
contando na numeração hierárquica dos tópicos
(`SaleOrder._proposal_block_numbering()` conta todo bloco `included`,
independente do que ele renderiza), deixando um buraco na numeração do
PDF (ex.: o índice pula do 7 pro 9). Por isso, ao contrário do
comentário original acima ("Só mexe no TEMPLATE"), esta migração agora
TAMBÉM remove esses blocos materializados, em todas as cotações — não só
no template.
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
    if template:
        lines = template.line_ids.filtered(
            lambda l: l.block_kind in ("financial", "optionals"))
        if lines:
            _logger.info(
                "afr_qualificacao 16.0.7.0.0: removendo %d linha(s) "
                "financial/optionals do template %s (id=%d).",
                len(lines), template.display_name, template.id,
            )
            lines.unlink()

    blocks = env["afr.proposal.block"].search(
        [("block_kind", "in", ("financial", "cycle_specs"))]
    )
    if blocks:
        n_orders = len(blocks.mapped("sale_order_id"))
        _logger.info(
            "afr_qualificacao 16.0.7.0.0: removendo %d bloco(s) "
            "financial/cycle_specs materializados em %d cotação(ões) — "
            "esses tipos não renderizam mais nada e deixavam buraco na "
            "numeração hierárquica dos tópicos.",
            len(blocks), n_orders,
        )
        blocks.unlink()
