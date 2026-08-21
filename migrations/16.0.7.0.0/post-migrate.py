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
emitida sempre, incondicionalmente, ao fim do escopo por equipamento.

Os dois tipos abaixo viram lixo por motivos DIFERENTES — nenhum dos dois
é "inofensivo" de deixar para trás:

- `financial`: não renderiza mais NENHUM conteúdo (nenhum `qq_block_*` é
  chamado para esse `block_kind`), mas continua contando na numeração
  hierárquica dos tópicos (`SaleOrder._proposal_block_numbering()` conta
  todo bloco `included`, independente do que ele desenha) e ainda aparece
  como entrada fantasma (link morto) no Índice/TOC do PDF — daí o buraco
  na numeração (ex.: o índice pula do 7 pro 9).
- `cycle_specs` ("Tabela de Ciclos"): ao contrário do `financial`, ESTE
  AINDA RENDERIZA — `quotation_template.xml` e o portal continuam com um
  ramo `t-if="block.block_kind == 'cycle_specs'"` ativo. O problema aqui
  não é numeração: desde que os ciclos passaram a aparecer embutidos nas
  tabelas de escopo por equipamento (`_qualif_scope_tables`), um bloco
  `cycle_specs` materializado imprime os MESMOS ciclos DUAS VEZES na
  mesma proposta (uma vez dentro do escopo, outra na tabela solta do
  bloco). `cycle_specs` também já não é mais semeado no template default
  por esse motivo. Apagar esses blocos é remoção de conteúdo duplicado,
  não uma correção de numeração.

Isso significa que blocos `afr.proposal.block` materializados com
`block_kind in ('financial', 'cycle_specs')` em cotações já existentes
(labquali) precisam sumir — um por deixar buraco na numeração/TOC, o
outro por duplicar a tabela de ciclos. Por isso, ao contrário do
comentário original acima ("Só mexe no TEMPLATE"), esta migração agora
TAMBÉM remove esses blocos materializados, em todas as cotações — não só
no template.

Ajuste de 2026-08-21 (fix round, F1): existe ainda um TERCEIRO caso —
bloco `financial` que alguém converteu para `static` (snapshot manual)
ANTES do `UserError` em `action_edit_block` passar a proibir essa
conversão (caso real: afr.proposal.block id=636, SO C26-08-0018, com
"TOTAL GERAL: R$ 10.373,48" congelado no body). Um bloco `static` sempre
renderiza seu `body` incondicionalmente — com o guard antigo removido,
esse registro específico voltaria a imprimir DOIS totais (o congelado no
body + o novo incondicional do fim do escopo).

Diferente de `financial`/`cycle_specs` (que dá para identificar só pelo
`block_kind`), aqui é preciso um critério mais cuidadoso, porque um bloco
`static` pode ter conteúdo de texto livre editado pelo usuário — não dá
para apagar todo `static` com um título parecido. O critério ESTREITO
(3 condições cumulativas, ver `AfrProposalBlock.
_qualif_is_frozen_financial_summary`) é: `block_kind == 'static'` E
`title` igual ao rótulo do bloco financeiro ("Resumo Financeiro") E
`body` contendo o texto "TOTAL GERAL". Só com as três é seguro afirmar
que é um Resumo Financeiro congelado, e não um bloco de texto que o
usuário só batizou assim. Cada remoção é logada individualmente com o
nome da cotação, para o registro ficar auditável.
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
            "financial não renderiza mais nada e deixava buraco na "
            "numeração hierárquica dos tópicos; cycle_specs ainda "
            "renderiza e duplicava a tabela de ciclos já embutida no "
            "escopo por equipamento.",
            len(blocks), n_orders,
        )
        blocks.unlink()

    # F1 (fix round 2026-08-21): bloco `financial` congelado em `static`
    # ANTES do UserError em action_edit_block existir — critério estreito,
    # ver AfrProposalBlock._qualif_is_frozen_financial_summary. Candidatos
    # filtrados pelo título no domain (barato); o critério completo
    # (inclui checar "TOTAL GERAL" no body) roda em Python por registro,
    # e cada remoção é logada individualmente com a cotação, por ser uma
    # exclusão sensível de conteúdo potencialmente editado pelo usuário.
    financial_label = dict(
        env["afr.proposal.block"]._fields["block_kind"].selection
    ).get("financial")
    frozen_candidates = env["afr.proposal.block"].search([
        ("block_kind", "=", "static"),
        ("title", "=", financial_label),
    ]) if financial_label else env["afr.proposal.block"]
    frozen_financial = frozen_candidates.filtered(
        lambda b: b._qualif_is_frozen_financial_summary())
    for block in frozen_financial:
        _logger.info(
            "afr_qualificacao 16.0.7.0.0: removendo bloco static "
            "'Resumo Financeiro' congelado (id=%d) da cotação %s — "
            "'TOTAL GERAL' encontrado no body, teria duplicado o total.",
            block.id, block.sale_order_id.display_name,
        )
    if frozen_financial:
        frozen_financial.unlink()
