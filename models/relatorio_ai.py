# -*- coding: utf-8 -*-
"""Revisão assistiva por IA (OpenRouter) do Relatório Final — spec §7.2.

Desligada por padrão (`afr_qualificacao.ai_enabled`). Uma chamada para o
corpo (texto dos blocos efetivamente renderizados — `rendered_blocks` — +
dados estruturados JSON) + uma por anexo com texto extraído (pdfminer), cada
uma truncada a MAX_CHUNK_CHARS e acompanhada do "cartão de identidade".
Achados só `alerta`/`info` (a IA nunca bloqueia).

Falhas nunca derrubam a verificação: rede/HTTP, JSON inválido, erro ao
montar os trechos e trechos pulados por falta de orçamento viram UM único
achado IA_INDISPONIVEL (info). Falha de rede interrompe os trechos seguintes.

Ruling 1.14 (P5): orçamento total de parede por revisão
(`afr_qualificacao.ai_total_budget`, 60 s). Cada chamada usa
`timeout = min(ai_timeout, restante)`; com menos de MIN_CALL_SECONDS
restantes os trechos seguintes não são enviados (entram no IA_INDISPONIVEL).
Obs.: o `timeout` do `requests` vale por operação de socket, não para a
resposta inteira — é um limite prático, não absoluto.

Segredo: a chave fica só em `ir.config_parameter` e vai apenas no header
Authorization; nunca é registrada em log nem entra em mensagem de achado.
"""
import io
import json
import logging
import math
import re
import time

import requests

from odoo import _, fields, models
from odoo.tools import html2plaintext

from . import relatorio_rules

_logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PARAM_ENABLED = "afr_qualificacao.ai_enabled"
PARAM_API_KEY = "afr_qualificacao.ai_api_key"
PARAM_MODEL = "afr_qualificacao.ai_model"
PARAM_TIMEOUT = "afr_qualificacao.ai_timeout"
PARAM_TOTAL_BUDGET = "afr_qualificacao.ai_total_budget"
# Mesmo modelo que o PWA usa em produção (variante paga; `:free` devolve 429).
DEFAULT_MODEL = "google/gemma-4-31b-it"
DEFAULT_TIMEOUT = 60
DEFAULT_TOTAL_BUDGET = 60
MIN_CALL_SECONDS = 5
MAX_CHUNK_CHARS = 12000
MAX_PDF_PAGES = 15
CODIGO_IA = "IA_ACHADO"
CODIGO_INDISPONIVEL = "IA_INDISPONIVEL"
TRUNC_MARKER = "\n[... texto truncado ...]"

SYSTEM_PROMPT = """Você é um revisor técnico de relatórios de qualificação térmica de autoclaves (esterilização a vapor), redigidos em português do Brasil. Sua tarefa é apontar INCONSISTÊNCIAS DE DOCUMENTO no trecho recebido, comparando-o com o CARTÃO DE IDENTIDADE do relatório (fonte da verdade) e com ele mesmo.

Procure principalmente:
1. Identificação divergente do cartão: nome do cliente, TAG, número de série, modelo do equipamento, número do relatório ou revisão.
2. Datas incoerentes: datas fora do período de ensaios do cartão, ano diferente, gráficos ou impressões de outro período (arquivo reaproveitado), leitura de indicador biológico antes da incubação.
3. Numeração e contagem: "Página X de Y" com X maior que Y, quantidade de ciclos no texto diferente dos ciclos contratados, anexo citado que não existe.
4. Valores técnicos que se contradizem dentro do trecho: temperatura, tempo, pressão, F0, tolerância e critérios de aceitação.
5. Texto de modelo não preenchido: marcadores como {{ }}, "XXX", "[preencher]", nome de outro cliente.

Regras:
- Não invente problemas. Se não houver inconsistência, devolva a lista vazia.
- Não julgue se o equipamento foi aprovado ou reprovado; aponte apenas inconsistências do documento.
- Use "alerta" para inconsistência provável que pode invalidar o relatório e "info" para observação menor (grafia, formatação).
- Nunca use gravidade diferente de "alerta" ou "info".
- "onde" localiza o problema no trecho (seção, página, tabela ou ciclo). "trecho" copia literalmente o texto problemático (até 200 caracteres). "explicacao" diz, em uma ou duas frases, por que é inconsistente.

Responda SOMENTE com um JSON válido, sem nenhum texto antes ou depois, exatamente neste formato:
{"achados": [{"gravidade": "alerta", "onde": "...", "trecho": "...", "explicacao": "..."}]}"""

FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


def _now():
    """Relógio da revisão (ponto de patch dos testes de orçamento)."""
    return time.monotonic()


def parse_ai_json(content):
    """Extrai a lista `achados` de uma resposta possivelmente suja."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("resposta vazia")
    text = content.strip()
    fence = FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("JSON não encontrado na resposta")
        data = json.loads(text[start:end + 1])
    if not isinstance(data, dict) or not isinstance(data.get("achados"), list):
        raise ValueError("JSON sem a lista 'achados'")
    return data["achados"]


def truncate(text, limit=MAX_CHUNK_CHARS):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - len(TRUNC_MARKER)] + TRUNC_MARKER


def pdf_to_text(data, limit=MAX_CHUNK_CHARS):
    """Texto do PDF (até MAX_PDF_PAGES páginas), parando assim que o texto
    acumulado atinge `limit` (ruling 1.14: não varrer PDFs de 150 páginas).
    `extract_pages` é gerador: interromper o laço interrompe o parse."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer

    parts, total = [], 0
    for page in extract_pages(io.BytesIO(data), maxpages=MAX_PDF_PAGES):
        for element in page:
            if isinstance(element, LTTextContainer):
                text = element.get_text()
                parts.append(text)
                total += len(text)
        if total >= limit:
            break
    return "".join(parts)


class AfrRelatorioAi(models.AbstractModel):
    _name = "afr.relatorio.ai"
    _description = "Revisão do Relatório Final por IA"

    # ------------------------------------------------------------ config
    def _param(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param(key, default)

    def _int_param(self, key, default):
        try:
            return max(MIN_CALL_SECONDS, int(self._param(key, default)))
        except (TypeError, ValueError):
            return default

    def _is_enabled(self):
        return str(self._param(PARAM_ENABLED, "False")).strip().lower() in (
            "1", "true", "yes", "on",
        )

    def _timeout(self):
        return self._int_param(PARAM_TIMEOUT, DEFAULT_TIMEOUT)

    def _total_budget(self):
        return self._int_param(PARAM_TOTAL_BUDGET, DEFAULT_TOTAL_BUDGET)

    # ------------------------------------------------------------ HTTP
    def _call(self, messages, timeout=None):
        """POST no OpenRouter; devolve o `content` da 1ª escolha."""
        api_key = self._param(PARAM_API_KEY)
        if not api_key:
            raise ValueError("chave de API não configurada")
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": "Bearer %s" % api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": self._param(PARAM_MODEL) or DEFAULT_MODEL,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 2000,
            },
            timeout=timeout or self._timeout(),
        )
        resp.raise_for_status()
        data = resp.json()
        content = (((data or {}).get("choices") or [{}])[0].get("message") or {}).get("content")
        if not isinstance(content, str):
            raise ValueError("resposta sem conteúdo")
        return content

    # ------------------------------------------------------------ contexto
    def _identity_card(self, rel):
        eq = rel.equipment_id
        return {
            "relatorio": rel.name,
            "revisao": rel.revision_label or "",
            "cliente": rel.partner_id.name or "",
            "equipamento": eq.display_name or "",
            "tag": eq.tag or "",
            "numero_serie": eq.serial_number or "",
            "data_inicio_ensaios": str(rel.data_inicio_ensaios or ""),
            "data_fim_ensaios": str(rel.data_fim_ensaios or ""),
            # cycle_counts lê sale.order.line em sudo (ruling 1.8) — só qtd.
            "ciclos_contratados": {
                (ctype.name or _("(sem tipo)")): vals[0]
                for ctype, vals in relatorio_rules.cycle_counts(rel).items()
            },
        }

    def _structured_data(self, rel):
        return {
            "ambiente": {"temperatura": rel.amb_temperatura or "", "umidade": rel.amb_umidade or ""},
            "criterios": {"tolerancia_acima_c": rel.tolerancia_acima, "f0_fator": rel.criterio_f0_fator},
            "checklist": [
                {"grupo": ln.grupo or "", "descricao": ln.descricao or "",
                 "status": ln.status or "", "comentario": ln.comentario or ""}
                for ln in rel.checklist_ids
            ],
            "indicadores": [
                {"tipo": i.tipo or "", "marca": i.marca or "", "modelo_tipo": i.modelo_tipo or "",
                 "lote": i.lote or "", "validade": str(i.validade or ""),
                 "valor_d": i.valor_d, "populacao": i.populacao or ""}
                for i in rel.indicador_ids
            ],
            "leituras_ib": [
                {"ciclo": ln.cycle_id.display_name or "", "resultado": ln.resultado or "",
                 "data_leitura": str(ln.data_leitura or ""),
                 "controle_positivo_ok": ln.controle_positivo_ok}
                for ln in rel.leitura_ib_ids
            ],
            "ciclos": [
                {"ciclo": c.display_name, "estado": c.state,
                 "janela_inicio": str(c.janela_inicio or ""), "janela_fim": str(c.janela_fim or ""),
                 "sensores": [{"canal": s.canal or "", "posicao": s.posicao or "", "ib": s.ib_label or ""}
                              for s in c.sensor_pos_ids]}
                for c in rel.cycle_ids
            ],
        }

    def _body_text(self, rel):
        """Texto do mesmo conjunto que as regras varrem (ruling 1.4/1.6)."""
        parts = []
        for block in relatorio_rules.rendered_blocks(rel):
            try:
                html = rel._render_block_body(block)
            except Exception:  # noqa: BLE001 — TOKEN_NAO_RESOLVIDO já reporta
                continue
            text = html2plaintext(str(html or "")).strip()
            if text:
                parts.append("## %s\n%s" % (block.title or block.block_kind, text))
        return "\n\n".join(parts)

    def _anexo_text(self, anexo):
        try:
            files = anexo._resolve_files()
        except Exception:  # noqa: BLE001 — ANEXO_* já reportam
            return ""
        texts, total = [], 0
        for content, mimetype, legenda in files:
            if total >= MAX_CHUNK_CHARS:
                break
            if (mimetype or "") != "application/pdf":
                continue
            try:
                text = pdf_to_text(content, limit=MAX_CHUNK_CHARS - total).strip()
            except Exception as exc:  # noqa: BLE001
                _logger.info("pdfminer falhou no anexo %s: %s", anexo.id, exc)
                continue
            if text:
                piece = "### %s\n%s" % (legenda or "", text)
                texts.append(piece)
                total += len(piece)
        return "\n\n".join(texts)

    def _build_chunks(self, rel):
        chunks = [{
            # Item 5 (P5 final fix wave): literal fixo, NÃO _() — este label
            # entra na chave de carry-over (`onde`) das decisões de achado
            # de IA; `_()` traduz pelo idioma do usuário que roda a
            # verificação, e o mesmo relatório verificado por usuários com
            # idiomas diferentes geraria chaves diferentes para o MESMO
            # trecho, perdendo a decisão já tomada.
            "label": "Corpo do relatório",
            "text": truncate("TEXTO DO RELATÓRIO:\n%s\n\nDADOS ESTRUTURADOS (JSON):\n%s" % (
                self._body_text(rel),
                json.dumps(self._structured_data(rel), ensure_ascii=False, indent=1),
            )),
        }]
        for anexo in rel._anexos_included():
            text = self._anexo_text(anexo)
            if text:
                chunks.append({
                    # rótulo estável (chave de carry-over): código/título + id,
                    # não o número, que muda quando anexos são reordenados.
                    "label": "Anexo %s [#%d]" % (anexo.title or anexo.code, anexo.id),
                    "text": truncate(text),
                })
        return chunks

    def _messages(self, card, chunk):
        user = (
            "CARTÃO DE IDENTIDADE DO RELATÓRIO (fonte da verdade):\n%s\n\n"
            "TRECHO EM ANÁLISE: %s\n\n%s"
        ) % (json.dumps(card, ensure_ascii=False, indent=1), chunk["label"], chunk["text"])
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    # ------------------------------------------------------------ saída
    def _indisponivel(self, msg):
        return {"codigo": CODIGO_INDISPONIVEL, "gravidade": "info",
                "mensagem": msg[:1000], "onde": "IA"}

    def _to_findings(self, label, itens, used_onde):
        out = []
        for it in itens:
            if not isinstance(it, dict):
                continue
            grav = "info" if str(it.get("gravidade") or "").strip().lower() == "info" else "alerta"
            explic = str(it.get("explicacao") or "").strip()
            trecho = str(it.get("trecho") or "").strip()
            if not explic and not trecho:
                continue
            msg = _("IA — verificar: %s") % (explic or trecho)
            if explic and trecho:
                msg += ' — trecho: "%s"' % trecho[:300]
            onde = "%s: %s" % (label, str(it.get("onde") or "").strip()[:200])
            # `_run_verificacao` deduplica por (origem, codigo, onde):
            # desambigua achados distintos no mesmo lugar.
            base, n = onde, 1
            while onde in used_onde:
                n += 1
                onde = "%s (%d)" % (base, n)
            used_onde.add(onde)
            out.append({
                "codigo": CODIGO_IA,
                "gravidade": grav,
                "mensagem": msg[:2000],
                "onde": onde,
            })
        return out

    def review(self, relatorio):
        """Lista de achados (dicts) da IA; [] quando desligada. Nunca lança."""
        relatorio.ensure_one()
        if not self._is_enabled():
            return []
        if not self._param(PARAM_API_KEY):
            return [self._indisponivel(_("IA ligada, mas sem chave de API configurada."))]
        start = _now()
        try:
            with self.env.cr.savepoint():
                card = self._identity_card(relatorio)
                chunks = self._build_chunks(relatorio)
        except Exception as exc:  # noqa: BLE001 — a IA nunca derruba a verificação
            _logger.warning("IA: falha ao montar os trechos do relatório %s: %s",
                            relatorio.id, exc)
            return [self._indisponivel(
                _("IA indisponível: falha ao montar os trechos (%s).") % exc)]

        budget, timeout = self._total_budget(), self._timeout()
        out, falhas, skipped, used_onde = [], [], [], set()
        for idx, chunk in enumerate(chunks):
            remaining = budget - (_now() - start)
            if remaining < MIN_CALL_SECONDS:
                skipped = [c["label"] for c in chunks[idx:]]
                _logger.warning("IA: orçamento de %ss esgotado no relatório %s; "
                                "%d trecho(s) não enviados", budget, relatorio.id, len(skipped))
                break
            call_timeout = min(timeout, int(math.ceil(remaining)))
            try:
                itens = parse_ai_json(self._call(self._messages(card, chunk), timeout=call_timeout))
            except (requests.JSONDecodeError, ValueError) as exc:
                # Item 4 (P5 final fix wave): `requests.JSONDecodeError` é
                # subclasse de `RequestException` (herda de `InvalidJSONError`)
                # — sem este `except` ANTES do de rede, uma resposta com
                # corpo não-JSON de `resp.json()` era tratada como falha de
                # REDE (abortava os trechos seguintes). É resposta inválida
                # de UM trecho, como qualquer outro `ValueError` (JSON sem a
                # lista 'achados', chave de API ausente etc.): os demais
                # trechos continuam sendo enviados.
                _logger.warning("IA: resposta inválida no relatório %s: %s", relatorio.id, exc)
                falhas.append("%s (%s)" % (chunk["label"], exc))
                continue
            except requests.RequestException as exc:
                _logger.warning("IA: falha de rede no relatório %s: %s", relatorio.id, exc)
                falhas.append("%s (%s)" % (chunk["label"], exc))
                skipped = [c["label"] for c in chunks[idx + 1:]]
                break
            except Exception as exc:  # noqa: BLE001 — resposta inválida
                _logger.warning("IA: resposta inválida no relatório %s: %s", relatorio.id, exc)
                falhas.append("%s (%s)" % (chunk["label"], exc))
                continue
            out.extend(self._to_findings(chunk["label"], itens, used_onde))
        if falhas or skipped:
            partes = []
            if falhas:
                partes.append(_("falha em %d trecho(s): %s") % (len(falhas), "; ".join(falhas)))
            if skipped:
                partes.append(_("%d trecho(s) não enviados: %s") % (
                    len(skipped), "; ".join(skipped)))
            out.append(self._indisponivel(_("IA indisponível — %s.") % " — ".join(partes)))
        return out


class ResConfigSettings(models.TransientModel):
    """Ruling 0.2: campos de IA aqui (não em res_config_settings.py), para
    não depender da ordem de import dos models."""

    _inherit = "res.config.settings"

    # Relatório Final P5 — revisão por IA (OpenRouter), spec §7.2
    afr_ai_enabled = fields.Boolean(
        string="Revisão por IA no Relatório Final",
        config_parameter=PARAM_ENABLED,
        help="Envia o texto do relatório e dos anexos ao OpenRouter na verificação. "
             "Desligado por padrão (dado do cliente sai do servidor).",
    )
    # Na view, usar `password="True"` (chave só em ir.config_parameter).
    afr_ai_api_key = fields.Char(
        string="Chave de API (OpenRouter)",
        config_parameter=PARAM_API_KEY,
    )
    afr_ai_model = fields.Char(
        string="Modelo",
        config_parameter=PARAM_MODEL,
        default=DEFAULT_MODEL,
        help="Use modelo pago; variantes ':free' devolvem 429 na prática.",
    )
    afr_ai_timeout = fields.Integer(
        string="Timeout (s)",
        config_parameter=PARAM_TIMEOUT,
        default=DEFAULT_TIMEOUT,
    )
