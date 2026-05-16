"""Controller público de verificação de certificado.

Rota /qualificacao/verify/<token> aceita acesso público (auth=public).
Busca afr.qualificacao pelo token, recomputa o hash SHA-256 do snapshot
atual, compara com o hash congelado no approval. Mostra resultado em
template (verified / tampered / not_found).
"""

from odoo import http
from odoo.http import request


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
        - 'pending': qualif existe mas certificado ainda não emitido (state != approved)
        - 'tampered': hash atual diverge do congelado
        - 'valid': hash bate, certificado íntegro
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

        result = qualif.verify_certificate()
        status = "valid" if result["valid"] else "tampered"
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
