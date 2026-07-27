"""Controller público de verificação de certificado.

Rota /qualificacao/verify/<token> aceita acesso público (auth=public).
Busca afr.qualificacao pelo token, recomputa o hash SHA-256 do snapshot
atual, compara com o hash congelado no approval. Mostra resultado em
template (verified / tampered / not_found).
"""

from odoo import http
from odoo.http import request


def _resolve_public_status(qualif):
    """Determina status público (valid/tampered) considerando hash + state.

    Task 12 — Finding 1 (endurecimento secundário): antes, `status` vinha
    só de `verify_certificate()['valid']` (comparação de hash). Um registro
    cujo certificado tenha sido emitido mas que depois teve o `state`
    revertido (Finding 2) ou forjado por outro caminho ainda respondia
    `valid=True` publicamente enquanto não estivesse `approved`. Extraído
    como função de módulo (em vez de inline na rota) para ser testável sem
    precisar montar um contexto HTTP/request real.

    :return: tupla (status:str, result:dict) — result é o retorno cru de
        `qualif.verify_certificate()`, usado para popular o template.
    """
    result = qualif.verify_certificate()
    status = "valid" if (result["valid"] and qualif.state == "approved") else "tampered"
    return status, result


class QualificacaoVerifyController(http.Controller):

    @http.route(
        ["/qualificacao/verify/<string:token>"],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        csrf=False,
    )
    def verify_certificate(self, token, **kwargs):
        """Verifica certificado por token público.

        Retorna template renderizado com status:
        - 'not_found': token não localizado
        - 'pending': qualif existe mas certificado ainda não emitido
        - 'tampered': hash atual diverge do congelado, OU hash bate mas
          `state` não é mais 'approved' (Task 12 — Finding 2: registro
          revertido após emissão)
        - 'valid': hash bate E `state == 'approved'`
        """
        if not token or len(token) != 32:
            return request.render(
                "afr_qualificacao.certificate_verify_template",
                {"status": "not_found", "token": token},
            )

        qualif = request.env["afr.qualificacao"].sudo().search(
            [("certificate_token", "=", token)], limit=1
        )
        if not qualif:
            return request.render(
                "afr_qualificacao.certificate_verify_template",
                {"status": "not_found", "token": token},
            )

        if not qualif.certificate_hash:
            return request.render(
                "afr_qualificacao.certificate_verify_template",
                {"status": "pending", "qualif": qualif, "token": token},
            )

        status, result = _resolve_public_status(qualif)
        return request.render(
            "afr_qualificacao.certificate_verify_template",
            {
                "status": status,
                "qualif": qualif,
                "token": token,
                "expected_hash": result["expected_hash"],
                "current_hash": result["current_hash"],
                "issued_at": result["issued_at"],
            },
        )
