"""Relatório Final — emissão, revisão, aprovações e portal (P4).

Parte 1 (Task 4): campos de emissão, URL pública e guarda dos campos que só
as ações mudam. Tasks 7–9 acrescentam métodos a estas classes.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoRelatorioEmissao(models.Model):
    _name = "afr.qualificacao.relatorio"
    _inherit = ["afr.qualificacao.relatorio", "afr.qualificacao.manager.guard.mixin"]

    # Só as ações (Emitir / Revisar / aprovação do cliente) mudam estes
    # campos — via sudo(). Mesmo motivo do _CERTIFICATE_FIELDS de
    # afr.qualificacao: a ir.rule escopa registros, não valores.
    _RQ_INTERNAL_FIELDS = frozenset({"state", "revision", "current_emissao_id"})

    emissao_ids = fields.One2many(
        "afr.relatorio.emissao", "relatorio_id", string="Emissões", readonly=True,
    )
    current_emissao_id = fields.Many2one(
        "afr.relatorio.emissao", string="Emissão vigente", readonly=True, copy=False,
    )
    minuta_attachment_id = fields.Many2one(
        "ir.attachment", string="Última minuta", readonly=True, copy=False,
    )
    verify_url = fields.Char(
        compute="_compute_verify_url", string="URL pública de verificação",
    )

    @api.depends("current_emissao_id.token")
    @api.depends_context("rq_emission_token")
    def _compute_verify_url(self):
        """URL do QR. Durante a emissão o token vem do contexto: ele é gerado
        ANTES do PDF (o QR precisa dele) e a emissão só é criada depois,
        com o hash do PDF pronto."""
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param("web.base.url", default="")
        db_param = icp.get_param(
            "afr_qualificacao.verify_url_db", default=self.env.cr.dbname,
        )
        ctx_token = self.env.context.get("rq_emission_token")
        for rec in self:
            token = ctx_token or rec.current_emissao_id.token
            if not token:
                rec.verify_url = False
                continue
            url = "%s/qualificacao/relatorio/verify/%s" % (base, token)
            if db_param:
                url += "?db=%s" % db_param
            rec.verify_url = url

    def write(self, vals):
        if not self.env.su and self._RQ_INTERNAL_FIELDS.intersection(vals):
            raise UserError(_(
                "Status, revisão e emissão vigente do relatório final só mudam "
                "pelas ações Emitir, Revisar e pela aprovação do cliente."
            ))
        return super().write(vals)
