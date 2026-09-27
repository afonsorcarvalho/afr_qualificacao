# -*- coding: utf-8 -*-
"""Regras determinísticas da varredura do Relatório Final (spec §7.1).

Cada regra é uma função pura `rule(relatorio) -> list[dict]`; o dict tem
`codigo`, `gravidade` (bloqueia/alerta/info), `mensagem`, `onde`. Nenhuma
regra grava nada. `onde` é estável entre verificações (chave de carry-over
das decisões) e inclui `[#id]` quando o rótulo pode repetir.

`RULES` é o registro (ordem = execução). `run_rules` isola cada regra num
savepoint e converte exceção em achado bloqueante com o código da regra.
"""
import logging
import re
from collections import OrderedDict
from html import unescape  # noqa: F401 — Task 3 (ANEXO_REF/TOKEN dinâmico)

from odoo import fields  # noqa: F401 — Task 3 (DATA_FORA_JANELA)

from .relatorio_anexo_files import PROBLEM_EMPTY

_logger = logging.getLogger(__name__)

EMISSION_CTX = "afr_emission_check"
ANEXO_REF_RE = re.compile(r"""anexo\(\s*['"]([\w\-]+)['"]\s*\)""")  # Task 3
CANAL_NUM_RE = re.compile(r"(\d+)")  # Task 3


def finding(codigo, gravidade, mensagem, onde=""):
    return {
        "codigo": codigo,
        "gravidade": gravidade,
        "mensagem": mensagem,
        "onde": onde or "",
    }


def _fmt(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def cycle_label(cycle):
    return "%s [#%d]" % (cycle.display_name, cycle.id)


def block_label(block):
    name = block.title or block.section_id.display_name or block.block_kind
    return "%s [#%d]" % (name, block.id)


def _anexo_label(anexo):
    return anexo.title or anexo.code or ("Anexo #%d" % anexo.id)


# Kinds cujo `body` nunca passa por `_render_block_body` no template
# (`reports/relatorio_corpo_templates.xml::rq_block`, div `rq-body`: só
# renderiza para `block_kind not in ('capa', 'indice', 'anexo_separador')`
# — capa/índice têm sub-template próprio, `rq_block_capa`/`rq_block_indice`).
# `anexo_separador` fica fora desta lista porque, apesar do `rq_block`
# excluir esse kind também, o `rq_anexo` renderiza o separador via
# `doc._render_block_body(sep)` direto — por isso ele CONTINUA em
# `rendered_blocks()` (Fix round 1, achado 1).
_TOKEN_SKIP_KINDS = ("capa", "indice")


def rendered_blocks(rel):
    """Blocos que efetivamente aparecem no documento renderizado (Ruling
    1.4/1.6 — P5 preflight, + Fix round 1 achado 1): o corpo principal
    (`_body_blocks()`, sem capa/índice — `_TOKEN_SKIP_KINDS`) mais, para
    cada anexo incluído, o separador (`_anexo_separator_block(code)`,
    sempre renderizado por `rq_anexo`) e — só quando `slot_kind == 'bloco'`,
    o bloco vinculado está incluído e não é capa/índice — o próprio
    `anexo.block_id`. As duas condições (kind do `t-if` de `rq_anexo` e a
    exclusão de capa/índice do `rq_block`) são copiadas literalmente de
    `reports/relatorio_corpo_templates.xml`, reforçadas por
    `tests/relatorio_fakes.py::FakeCorpo.render`, para as regras de token
    não acusarem falso positivo num bloco que nunca é impresso (bloco
    excluído do corpo, vinculado a um anexo excluído/trocado, ou capa/índice
    cujo body nunca é resolvido)."""
    rel.ensure_one()
    blocks = rel._body_blocks().filtered(
        lambda b: b.block_kind not in _TOKEN_SKIP_KINDS)
    for anexo in rel._anexos_included():
        blocks |= rel._anexo_separator_block(anexo.code)
        if (anexo.slot_kind == "bloco" and anexo.block_id and anexo.block_id.included
                and anexo.block_id.block_kind not in _TOKEN_SKIP_KINDS):
            blocks |= anexo.block_id
    return blocks


def _dates_missing(rel):
    return not rel.data_inicio_ensaios or not rel.data_fim_ensaios


def _cert_rows(rel, resource_role, role):
    return [
        row for row in rel._afr_certificate_selection()
        if row["resource_role"] == resource_role and row["role"] == role
    ]


# ------------------------------------------------------------ bloqueia
def rule_cert_depois_ausente(rel):
    if _dates_missing(rel):
        return []
    rows = _cert_rows(rel, "validador", "depois")
    if not rows and not _cert_rows(rel, "validador", "antes"):
        return [finding(
            "CERT_DEPOIS_AUSENTE", "bloqueia",
            "Nenhum validador no plano de recursos da OS — impossível "
            "comprovar a calibração pós-campanha.",
            "Plano de recursos",
        )]
    out = []
    for row in rows:
        if not row["certificate"]:
            name = row["instrument"].display_name
            out.append(finding(
                "CERT_DEPOIS_AUSENTE", "bloqueia",
                "Validador %s sem certificado 'depois' com data ≥ %s."
                % (name, _fmt(rel.data_fim_ensaios)),
                "Validador: %s" % name,
            ))
    return out


def rule_cert_antes_ausente(rel):
    if _dates_missing(rel):
        return [finding(
            "CERT_ANTES_AUSENTE", "bloqueia",
            "Datas de início/fim dos ensaios não preenchidas — a seleção de "
            "certificados depende delas.",
            "Campo: Datas dos ensaios",
        )]
    out = []
    for row in _cert_rows(rel, "validador", "antes"):
        if not row["certificate"]:
            name = row["instrument"].display_name
            out.append(finding(
                "CERT_ANTES_AUSENTE", "bloqueia",
                "Validador %s sem certificado 'antes' com data ≤ %s."
                % (name, _fmt(rel.data_inicio_ensaios)),
                "Validador: %s" % name,
            ))
    return out


def rule_padrao_vencido(rel):
    if _dates_missing(rel):
        return []
    out = []
    for row in _cert_rows(rel, "padrao", "externo"):
        if not row["certificate"]:
            name = row["instrument"].display_name
            out.append(finding(
                "PADRAO_VENCIDO", "bloqueia",
                "Padrão %s sem certificado vigente em %s."
                % (name, _fmt(rel.data_inicio_ensaios)),
                "Padrão: %s" % name,
            ))
    return out


def rule_ib_sem_leitura(rel):
    lidos = set(rel.leitura_ib_ids.filtered(lambda l: l.resultado).mapped("cycle_id").ids)
    out = []
    for cycle in rel.cycle_ids:
        if cycle.cycle_type_id.load_type == "com_carga" and cycle.id not in lidos:
            out.append(finding(
                "IB_SEM_LEITURA", "bloqueia",
                "Ciclo com carga %s sem leitura de indicador biológico registrada."
                % cycle.display_name,
                "Ciclo: %s" % cycle_label(cycle),
            ))
    return out


def rule_ib_vencido(rel):
    ref = rel.data_fim_ensaios or rel.data_inicio_ensaios
    if not ref:
        return []
    out = []
    for ind in rel.indicador_ids:
        if ind.validade and ind.validade < ref:
            out.append(finding(
                "IB_VENCIDO", "bloqueia",
                "Indicador %s lote %s vencido em %s (ensaios até %s)."
                % (ind.modelo_tipo or ind.tipo, ind.lote or "—",
                   _fmt(ind.validade), _fmt(ref)),
                "Indicador: lote %s [#%d]" % (ind.lote or "—", ind.id),
            ))
    return out


_ANEXO_FILES_CACHE_KEY = "_afr_anexo_files_cache"


def _anexo_problems(rel, anexo):
    """`anexo._check_files()`, memoizado dentro de uma única chamada de
    `run_rules()` (Fix round 1, achado 3): `rule_anexo_vazio` e
    `rule_anexo_ilegivel` percorrem o MESMO conjunto de anexos incluídos, e
    sem isso cada anexo tinha `_check_files()` recalculado duas vezes por
    varredura. O cache vive só no `context` que `run_rules()` cria — um
    dict NOVO a cada chamada — nunca em cache de módulo nem em outro lugar
    que sobreviva entre chamadas/transações: uma regra chamada direto (como
    os testes fazem, sem passar por `run_rules`) não encontra a chave no
    contexto e recalcula sempre, sem risco de devolver resultado velho de
    outra transação. Continua uma regra pura de `rel` — o cache é
    carregado pelo próprio `rel` (via `context`), não por um parâmetro
    extra na assinatura."""
    cache = rel.env.context.get(_ANEXO_FILES_CACHE_KEY)
    if cache is None:
        return anexo._check_files()
    if anexo.id not in cache:
        cache[anexo.id] = anexo._check_files()
    return cache[anexo.id]


def rule_anexo_vazio(rel):
    """P4: `_check_files()` contém PROBLEM_EMPTY ⇔ anexo sem nenhum
    arquivo. Ruling 1.3 (P5 T2): roda em TODO anexo incluído — inclusive
    `slot_kind='bloco'`, cujo `_check_files()` devolve `PROBLEM_EMPTY`
    quando o `block_id` está ausente ou o bloco vinculado foi excluído."""
    out = []
    for anexo in rel._anexos_included():
        if PROBLEM_EMPTY in _anexo_problems(rel, anexo):
            out.append(finding(
                "ANEXO_VAZIO", "bloqueia",
                "Anexo '%s' incluído sem arquivo." % _anexo_label(anexo),
                "Anexo: %s" % _anexo_label(anexo),
            ))
    return out


def rule_anexo_ilegivel(rel):
    """P4: todo item de `_check_files()` diferente de PROBLEM_EMPTY é
    "<legenda>: <motivo>" (ilegível, criptografado, sem páginas, tipo não
    suportado). Anexo com todos os arquivos ilegíveis → ILEGIVEL, não VAZIO.
    Ruling 1.3 (P5 T2): mesmo universo de `rule_anexo_vazio` — todo anexo
    incluído, sem pular `slot_kind='bloco'`."""
    out = []
    for anexo in rel._anexos_included():
        for problema in _anexo_problems(rel, anexo):
            if problema == PROBLEM_EMPTY:
                continue
            out.append(finding(
                "ANEXO_ILEGIVEL", "bloqueia",
                "Anexo '%s': %s" % (_anexo_label(anexo), problema),
                "Anexo: %s — %s" % (_anexo_label(anexo), problema),
            ))
    return out


def rule_token_nao_resolvido(rel):
    """Ruling 1.4/1.6 (P5 preflight): só percorre `rendered_blocks(rel)` —
    o corpo principal mais separadores/conteúdo de anexo que de fato entram
    no documento — para não acusar token não resolvido num bloco que nunca
    é impresso.

    Fix round 1, achado 2: o render de cada bloco roda no seu próprio
    savepoint — igual ao isolamento por regra de `run_rules` — para que um
    erro de render de UM bloco não deixe o cursor num estado que quebre o
    render dos blocos seguintes; a exceção é sempre logada (`id` do bloco e
    do relatório) antes de virar achado, nunca engolida em silêncio."""
    out = []
    for block in rendered_blocks(rel):
        label = block_label(block)
        try:
            with rel.env.cr.savepoint():
                html = str(rel._render_block_body(block) or "")
        except Exception as exc:  # noqa: BLE001 — erro de render é o achado
            _logger.exception(
                "Falha ao renderizar o bloco %s do relatório %s", block.id, rel.id)
            out.append(finding(
                "TOKEN_NAO_RESOLVIDO", "bloqueia",
                "Erro ao renderizar o bloco: %s" % exc,
                "Bloco: %s" % label,
            ))
            continue
        if "{{" in html:
            out.append(finding(
                "TOKEN_NAO_RESOLVIDO", "bloqueia",
                "Token '{{' não resolvido após a renderização do bloco.",
                "Bloco: %s" % label,
            ))
    return out


RULES = OrderedDict([
    ("CERT_DEPOIS_AUSENTE", rule_cert_depois_ausente),
    ("CERT_ANTES_AUSENTE", rule_cert_antes_ausente),
    ("PADRAO_VENCIDO", rule_padrao_vencido),
    ("IB_SEM_LEITURA", rule_ib_sem_leitura),
    ("IB_VENCIDO", rule_ib_vencido),
    ("ANEXO_VAZIO", rule_anexo_vazio),
    ("ANEXO_ILEGIVEL", rule_anexo_ilegivel),
    ("TOKEN_NAO_RESOLVIDO", rule_token_nao_resolvido),
])


def run_rules(rel):
    """Executa todas as regras do registro. Regra que falha vira bloqueio.

    Fix round 1, achado 3: injeta um cache NOVO de `_check_files()` por
    anexo (via `context`) só para esta chamada — `_anexo_problems` usa
    quando presente, e as regras chamadas direto (sem `run_rules`) não o
    veem e recalculam sempre."""
    rel = rel.with_context(**{_ANEXO_FILES_CACHE_KEY: {}})
    out = []
    for code, fn in list(RULES.items()):
        try:
            with rel.env.cr.savepoint():
                found = fn(rel) or []
        except Exception as exc:  # noqa: BLE001 — fail closed
            _logger.exception("Regra %s falhou no relatório %s", code, rel.id)
            found = [finding(
                code, "bloqueia",
                "Falha ao executar a regra %s: %s" % (code, exc),
                "Regra: %s" % code,
            )]
        out.extend(found)
    return out
