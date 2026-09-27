"""Relatório Final: verificação pública e aprovação do cliente (spec §8).

Mesmo padrão de `controllers/main.py`: a lógica fica em funções de módulo
(testáveis sem request HTTP — os testes rodam com --no-http) e as rotas só
renderizam. O QR do PDF aponta para o token da emissão, não para o hash.

Nenhuma rota pública grava nada além da aprovação do cliente (que passa
pelo token da linha, comparado em tempo constante). O PDF emitido segue
`public=False`: só sai pelo portal, com o token do aprovador.
"""
import hashlib

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.exceptions import UserError
from odoo.http import content_disposition, request
from odoo.tools import consteq

# Maior id aceito pelo Postgres (int4): acima disso o browse().exists()
# estouraria em SQL (500) em vez de responder 404.
_MAX_PG_INT = 2 ** 31 - 1


def _relatorio_verify_values(env, token):
    """Valores do template público de verificação.

    status: 'not_found' | 'valid' | 'superseded' | 'tampered' (bytes do PDF
    armazenado não batem com o SHA-256 congelado na emissão).
    Só leitura (sudo restrito à busca pelo token); o SHA é recalculado a
    cada acesso (ruling 1.17).
    """
    values = {"status": "not_found", "token": token}
    if not isinstance(token, str) or len(token) != 32:
        return values
    emissao = env["afr.relatorio.emissao"].sudo().search([("token", "=", token)], limit=1)
    if not emissao:
        return values
    rel = emissao.relatorio_id
    raw = emissao.pdf_attachment_id.with_context(bin_size=False).raw or b""
    if not raw or hashlib.sha256(raw).hexdigest() != emissao.sha256:
        status = "tampered"
    elif emissao.superseded:
        status = "superseded"
    else:
        status = "valid"
    values.update({
        "status": status,
        "emissao": emissao,
        "relatorio": rel,
        "current": rel.current_emissao_id,
        "under_revision": status == "valid" and rel.state == "draft",
        "client_approvals": rel.aprovacao_ids.filtered(
            lambda a: a.papel == "cliente" and a.approved_at
        ) if status == "valid" else rel.aprovacao_ids.browse(),
    })
    return values


def _portal_aprovacao(env, aprovacao_id, access_token):
    """Linha de aprovação do cliente se o token confere (comparação em tempo
    constante). None em qualquer falha — sem revelar se o id existe."""
    try:
        aprovacao_id = int(aprovacao_id)
    except (TypeError, ValueError):
        return None
    if not isinstance(access_token, str) or not access_token or not 0 < aprovacao_id <= _MAX_PG_INT:
        return None
    aprovacao = env["afr.relatorio.aprovacao"].sudo().browse(aprovacao_id).exists()
    if (not aprovacao or aprovacao.papel != "cliente" or not aprovacao.access_token
            or not consteq(aprovacao.access_token, access_token)):
        return None
    return aprovacao


class RelatorioFinalPublicController(http.Controller):

    @http.route(
        ["/qualificacao/relatorio/verify/<string:token>"],
        type="http", auth="public", website=True, sitemap=False, csrf=False,
    )
    def relatorio_verify(self, token, **kwargs):
        return request.render(
            "afr_qualificacao.relatorio_verify_template",
            _relatorio_verify_values(request.env, token),
        )

    @http.route(
        ["/my/relatorio/<int:aprovacao_id>"],
        type="http", auth="public", website=True, sitemap=False,
    )
    def portal_relatorio(self, aprovacao_id, access_token=None, message=None, **kwargs):
        aprovacao = _portal_aprovacao(request.env, aprovacao_id, access_token)
        if not aprovacao:
            raise NotFound()
        rel = aprovacao.relatorio_id
        return request.render("afr_qualificacao.portal_relatorio_aprovacao", {
            "aprovacao": aprovacao,
            "relatorio": rel,
            "emissao": rel.current_emissao_id,
            "access_token": access_token,
            "message": message if message in ("ok", "erro") else None,
        })

    @http.route(
        ["/my/relatorio/<int:aprovacao_id>/pdf"],
        type="http", auth="public", website=True, sitemap=False,
    )
    def portal_relatorio_pdf(self, aprovacao_id, access_token=None, **kwargs):
        aprovacao = _portal_aprovacao(request.env, aprovacao_id, access_token)
        attachment = aprovacao and aprovacao.relatorio_id.current_emissao_id.pdf_attachment_id
        raw = attachment and attachment.with_context(bin_size=False).raw
        if not raw:
            raise NotFound()
        return request.make_response(raw, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", content_disposition(attachment.name)),
        ])

    @http.route(
        ["/my/relatorio/<int:aprovacao_id>/aprovar"],
        type="http", auth="public", website=True, sitemap=False, methods=["POST"],
    )
    def portal_relatorio_aprovar(self, aprovacao_id, access_token=None, nome=None, **kwargs):
        aprovacao = _portal_aprovacao(request.env, aprovacao_id, access_token)
        if not aprovacao:
            raise NotFound()
        try:
            aprovacao._portal_approve(nome, request.httprequest.remote_addr)
            message = "ok"
        except UserError:
            message = "erro"
        return request.redirect("/my/relatorio/%d?access_token=%s&message=%s" % (
            aprovacao.id, access_token, message))
