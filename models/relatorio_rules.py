# -*- coding: utf-8 -*-
"""Regras determinísticas da varredura do Relatório Final (spec §7.1).

Cada regra é uma função pura `rule(relatorio) -> list[dict]`; o dict tem
`codigo`, `gravidade` (bloqueia/alerta/info), `mensagem`, `onde`. Nenhuma
regra grava nada. `onde` é estável entre verificações (chave de carry-over
das decisões) e inclui `[#id]` quando o rótulo pode repetir.

`RULES` é o registro (ordem = execução). `run_rules` isola cada regra num
savepoint e converte exceção em achado bloqueante com o código da regra.
"""
import base64
import logging
import re
from collections import OrderedDict
from html import unescape  # Task 3 (ANEXO_REF/TOKEN dinâmico)
from itertools import zip_longest

from odoo import fields  # Task 3 (DATA_FORA_JANELA)

from .relatorio_anexo_files import PROBLEM_EMPTY
from .relatorio_certificados import _afr_resolve_mimetype
from .relatorio_emissao_flow import INTERNAL_ROLES, ROLE_LABELS, company_tz

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
# renderiza para `block_kind not in ('capa', 'indice')` — capa/índice têm
# sub-template próprio, `rq_block_capa`/`rq_block_indice`).
_TOKEN_SKIP_KINDS = ("capa", "indice")


def rendered_blocks(rel):
    """Blocos que efetivamente aparecem no documento renderizado: o corpo
    (`_body_blocks()`, sem capa/índice — `_TOKEN_SKIP_KINDS`) mais, para cada
    anexo incluído de origem 'bloco', o `anexo.block_id` quando incluído e não
    capa/índice. Espelha `reports/relatorio_corpo_templates.xml` (`rq_block`/
    `rq_anexo`) e `tests/relatorio_fakes.py::FakeCorpo.render`, para as regras
    de token não acusarem bloco que nunca é impresso."""
    rel.ensure_one()
    blocks = rel._body_blocks().filtered(
        lambda b: b.block_kind not in _TOKEN_SKIP_KINDS)
    for anexo in rel._anexos_included():
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
    """Item 1 (P5 final fix wave): pula ciclos ainda `pending` — um ciclo
    com carga que nem foi executado não tem como ter leitura de IB, e
    bloquear a emissão por isso deixaria o relatório inemitível enquanto o
    ciclo não roda (quem sinaliza o ciclo pendente, decidível, é
    CICLOS_CONTAGEM)."""
    lidos = set(rel.leitura_ib_ids.filtered(lambda l: l.resultado).mapped("cycle_id").ids)
    out = []
    for cycle in rel.cycle_ids:
        if (cycle.cycle_type_id.load_type == "com_carga"
                and cycle.state != "pending" and cycle.id not in lidos):
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


# ------------------------------------------------------------ alerta
def rule_anexo_ref_excluido(rel):
    """Ruling 1.4/1.6 (P5 preflight): percorre `rendered_blocks(rel)` — o
    mesmo universo de `rule_token_nao_resolvido` — para não acusar
    referência num bloco que nunca é impresso (capa/índice, ou conteúdo de
    um anexo excluído). O `body` é lido cru (sem passar por
    `_render_block_body`): o `anexo('code')` aparece como texto literal no
    HTML digitado, não como resultado de render."""
    out = []
    for block in rendered_blocks(rel):
        codes = sorted(set(ANEXO_REF_RE.findall(unescape(block.body or ""))))
        for code in codes:
            if not rel._anexo_number(code):
                out.append(finding(
                    "ANEXO_REF_EXCLUIDO", "alerta",
                    "O texto referencia anexo('%s'), que está excluído ou não existe."
                    % code,
                    "Bloco: %s → anexo('%s')" % (block_label(block), code),
                ))
    return out


def cycle_counts(rel):
    """{cycle_type: [contratados, executados]} do equipamento do relatório.

    Contratados = Σ qualif_cycle_qty das linhas SO (da OS e dos ciclos) com
    cycle_type, do mesmo equipamento, excluindo opcional não aceito; ciclo
    sem linha SO conta 1 contratado. Executados = ciclos com state != pending.

    Ruling 1.8 (P5 T3): a leitura de `sale.order.line` roda em `sudo()` —
    o usuário `afr_qualificacao_user` não necessariamente tem acesso ao
    módulo de vendas, e esta função só soma quantidades (nunca expõe preço,
    parceiro nem qualquer outro dado da proposta)."""
    counts = {}
    lines = rel.cycle_ids.mapped("sale_order_line_id").sudo()
    so = rel.os_id.sale_order_id
    if so:
        lines |= so.sudo().order_line.filtered(
            lambda l: l.cycle_type_id
            and l.equipment_id == rel.equipment_id
            and not (l.is_proposal_optional and not l.optional_accepted)
        )
    for line in lines:
        ctype = line.cycle_type_id or line.cycle_ids[:1].cycle_type_id
        if ctype:
            counts.setdefault(ctype, [0, 0])[0] += line.qualif_cycle_qty or 0
    for cycle in rel.cycle_ids:
        entry = counts.setdefault(cycle.cycle_type_id, [0, 0])
        if not cycle.sale_order_line_id:
            entry[0] += 1
        if cycle.state != "pending":
            entry[1] += 1
    return counts


def rule_ciclos_contagem(rel):
    out = []
    items = sorted(cycle_counts(rel).items(), key=lambda kv: kv[0].name or "")
    for ctype, (contratados, executados) in items:
        if contratados != executados:
            out.append(finding(
                "CICLOS_CONTAGEM", "alerta",
                "Ciclos '%s': %d contratado(s), %d executado(s)."
                % (ctype.name, contratados, executados),
                # Fix round 1, minor: [#id] do cycle_type — Decisão 10, o
                # rótulo (nome do tipo de ciclo) pode repetir.
                "Ciclos: %s [#%d]" % (ctype.name, ctype.id),
            ))
    return out


def _is_pdf(item):
    """Ruling 1.9 (P5 T3): mesmo sniff de `_afr_resolve_mimetype` usado por
    P2/P4 — o mimetype gravado (às vezes `application/octet-stream`, como
    o PWA grava) não é confiável sozinho; sem sniff, um PDF real gravado
    assim disparava CICLO_SEM_DADOS por engano."""
    if not item.file:
        return False
    content = base64.b64decode(item.file)
    return _afr_resolve_mimetype(item.mimetype, content) == "application/pdf"


def rule_ciclo_sem_dados(rel):
    out = []
    for cycle in rel.cycle_ids:
        has_pdf = any(
            i.state == "collected" and i.file and _is_pdf(i)
            for i in cycle.collect_item_ids
        )
        if not has_pdf:
            out.append(finding(
                "CICLO_SEM_DADOS", "alerta",
                "Ciclo %s sem PDF de dados do validador." % cycle.display_name,
                "Ciclo: %s" % cycle_label(cycle),
            ))
    return out


def rule_ciclo_sem_janela(rel):
    out = []
    for cycle in rel.cycle_ids:
        if not cycle.janela_inicio or not cycle.janela_fim:
            msg = "Ciclo %s sem janela de esterilização (início/fim)." % cycle.display_name
        elif cycle.janela_fim <= cycle.janela_inicio:
            msg = ("Ciclo %s com fim da janela anterior ou igual ao início."
                   % cycle.display_name)
        else:
            continue
        out.append(finding(
            "CICLO_SEM_JANELA", "alerta", msg, "Ciclo: %s" % cycle_label(cycle),
        ))
    return out


def rule_data_fora_janela(rel):
    """Decisão 9: silenciosa quando as datas dos ensaios não estão
    preenchidas (quem cobre isso é CERT_ANTES_AUSENTE). Ruling 1.11: fuso
    de conversão na ordem contexto → usuário → empresa emissora →
    'America/Sao_Paulo' (`company_tz`, mesmo padrão de P4)."""
    if _dates_missing(rel):
        return []
    ini, fim = rel.data_inicio_ensaios, rel.data_fim_ensaios
    tz = rel.env.context.get("tz") or rel.env.user.tz or company_tz(rel.company_id)
    items = rel.env["afr.qualificacao.collect.item"].search([
        ("qualif_id", "in", rel.qualificacao_ids.ids),
        ("captured_at", "!=", False),
    ])
    out = []
    for item in items:
        # fuso do usuário/contexto (tz) — evita falso alerta perto da meia-noite
        local = fields.Datetime.context_timestamp(
            rel.with_context(tz=tz), item.captured_at).date()
        if local < ini or local > fim:
            out.append(finding(
                "DATA_FORA_JANELA", "alerta",
                "Item de coleta '%s' capturado em %s, fora do período dos "
                "ensaios (%s a %s)." % (item.name, _fmt(local), _fmt(ini), _fmt(fim)),
                "Coleta: %s [#%d]" % (item.name, item.id),
            ))
    return out


def rule_ambiente_vazio(rel):
    out = []
    for field_name, label in (
        ("amb_temperatura", "Temperatura ambiente"),
        ("amb_umidade", "Umidade ambiente"),
    ):
        if not (rel[field_name] or "").strip():
            out.append(finding(
                "AMBIENTE_VAZIO", "alerta",
                "%s não informada." % label,
                "Campo: %s" % label,
            ))
    return out


def rule_checklist_reprovado(rel):
    out = []
    for line in rel.checklist_ids.filtered(lambda l: l.status == "reprovado"):
        comentario = (" — %s" % line.comentario) if line.comentario else ""
        out.append(finding(
            "CHECKLIST_REPROVADO", "alerta",
            "Item de checklist reprovado: %s — %s%s"
            % (line.grupo or "", line.descricao or "", comentario),
            "Checklist: %s / %s [#%d]" % (line.grupo or "", line.descricao or "", line.id),
        ))
    return out


def validator_channel_capacity(rel):
    """Ruling 1.10 (P5 T3): mesmo filtro de `equipment_ids` da seleção de
    certificado (`_afr_certificate_selection`) — linha da OS inteira quando
    `equipment_ids` vazio, senão só quando o equipamento deste relatório
    está na lista."""
    equipment = rel.equipment_id
    lines = rel.os_id.resource_plan_line_ids.filtered(
        lambda l: l.resource_role == "validador"
        and l.instrument_id
        and (not l.equipment_ids or equipment in l.equipment_ids)
    )
    return sum(lines.mapped("instrument_id.measurement_capacity_ids.qty"))


def rule_canal_sem_cert(rel):
    """Heurística (ver plano P5, decisão 7): nº do canal > capacidade total."""
    capacity = validator_channel_capacity(rel)
    if not capacity:
        return []
    out = []
    for cycle in rel.cycle_ids:
        for pos in cycle.sensor_pos_ids:
            match = CANAL_NUM_RE.search(pos.canal or "")
            if not match:
                continue
            if int(match.group(1)) > capacity:
                out.append(finding(
                    "CANAL_SEM_CERT", "alerta",
                    "Canal %s (posição %s) fora da faixa 1–%d dos validadores do "
                    "plano de recursos — sem cobertura de certificado."
                    % (pos.canal, pos.posicao or "—", capacity),
                    # Fix round 1, minor: [#id] do sensor.pos — Decisão 10,
                    # o mesmo texto de canal pode se repetir entre linhas.
                    "Ciclo: %s / canal %s [#%d]" % (cycle_label(cycle), pos.canal, pos.id),
                ))
    return out


def rule_aprovacao_interna(rel):
    """Decisão 5: só roda na emissão (`EMISSION_CTX`) — no gate normal
    (`_check_emission_gate`) quem já relata aprovação interna faltante é o
    `super()` de P4 (`_rq_internal_approval_problems`); esta regra existe
    para os achados (decisão/carry-over) da varredura de emissão.

    Fix round 1: os achados são DERIVADOS de `rel._rq_internal_approval_problems()`
    — a mesma função que o gate usa — em vez de reimplementar a checagem por
    papel. A versão anterior só olhava `any(not a.approved_at for a in
    lines)` por papel (uma checagem agregada, não por linha, e sem checar
    `user_id`); a review encontrou o caso real que ela deixava passar: uma
    linha JÁ aprovada cujo `user_id` foi esvaziado depois (usuário
    removido) — o gate bloqueia (`_rq_internal_approval_problems` testa
    `not line.user_id` primeiro, independente de `approved_at`), mas a
    regra antiga ficava em silêncio. Derivar do mesmo método torna as duas
    checagens impossíveis de discordar por construção.

    `_rq_internal_approval_problems()` devolve só as mensagens (sem papel
    nem id da linha) — o `onde` é reconstruído aqui espelhando a MESMA
    ordem/condição do método (`INTERNAL_ROLES`, depois cada linha de
    `aprovacao_ids`), não o texto da mensagem. `zip_longest` com uma sobra
    genérica garante que uma divergência de contagem (se o método mudar de
    um lado sem o outro) nunca faça a regra perder um achado — a contagem
    exata é travada por teste
    (`test_aprovacao_interna_espelha_o_gate`, que compara a lista de
    mensagens da regra com a do gate diretamente)."""
    if not rel.env.context.get(EMISSION_CTX):
        return []
    ondes = []
    for papel in INTERNAL_ROLES:
        label = ROLE_LABELS[papel]
        lines = rel.aprovacao_ids.filtered(lambda a, p=papel: a.papel == p)
        if not lines:
            ondes.append("Aprovação: %s" % label)
        for line in lines:
            if not line.user_id or not line.approved_at:
                ondes.append("Aprovação: %s [#%d]" % (label, line.id))
    problems = rel._rq_internal_approval_problems()
    out = []
    for msg, onde in zip_longest(problems, ondes, fillvalue=None):
        if msg is None:
            continue
        out.append(finding("APROVACAO_INTERNA", "bloqueia", msg, onde or "Aprovação"))
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
    ("ANEXO_REF_EXCLUIDO", rule_anexo_ref_excluido),
    ("CICLOS_CONTAGEM", rule_ciclos_contagem),
    ("CICLO_SEM_DADOS", rule_ciclo_sem_dados),
    ("CICLO_SEM_JANELA", rule_ciclo_sem_janela),
    ("DATA_FORA_JANELA", rule_data_fora_janela),
    ("AMBIENTE_VAZIO", rule_ambiente_vazio),
    ("CHECKLIST_REPROVADO", rule_checklist_reprovado),
    ("CANAL_SEM_CERT", rule_canal_sem_cert),
    ("APROVACAO_INTERNA", rule_aprovacao_interna),
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
