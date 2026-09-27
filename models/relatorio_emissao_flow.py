"""Relatório Final — emissão, revisão, aprovações e portal (P4).

Parte 1 (Task 4): campos de emissão, URL pública e guarda dos campos que só
as ações mudam. Tasks 7–9 acrescentam métodos a estas classes.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    @api.model_create_multi
    def create(self, vals_list):
        """Fix round 1 (review do Task 4): o `write()` acima já bloqueava
        `_RQ_INTERNAL_FIELDS` fora de `env.su`, mas o `create()` não tinha
        override nenhum — o grupo Usuário (`create=1` na ACL de
        `afr.qualificacao.relatorio`) conseguia nascer o registro já
        `create({'state': 'issued', 'revision': 5, 'current_emissao_id': ...})`,
        sem passar pelas ações Emitir/Revisar/aprovação do cliente.

        Mesmo padrão de `qualificacao.py::create()` (Task 13/14): pré-check
        no `vals` recebido (erro cedo/claro no caso comum) + pós-check no
        registro EFETIVO já criado. O pós-check é o que realmente fecha o
        buraco — o ORM aplica `context['default_<campo>']`/`ir.default` a
        campos AUSENTES de `vals` dentro do próprio `super().create()`,
        depois deste pré-check, então um `with_context(default_state='issued')`
        sem `state` no vals sobreviveria só com o pré-check.
        """
        if not self.env.su:
            for vals in vals_list:
                if self._RQ_INTERNAL_FIELDS.intersection(vals):
                    raise UserError(_(
                        "Status, revisão e emissão vigente do relatório final só "
                        "mudam pelas ações Emitir, Revisar e pela aprovação do "
                        "cliente — nunca na criação do registro."
                    ))
        records = super().create(vals_list)
        if not self.env.su:
            for record in records:
                if (
                    record.state != "draft"
                    or record.revision != 0
                    or record.current_emissao_id
                ):
                    raise UserError(_(
                        "Status, revisão e emissão vigente do relatório final só "
                        "mudam pelas ações Emitir, Revisar e pela aprovação do "
                        "cliente — nunca na criação do registro."
                    ))
        return records

    @api.constrains("current_emissao_id")
    def _check_current_emissao_pertence_ao_relatorio(self):
        """A emissão vigente de um relatório só pode ser uma emissão DELE
        mesmo — sem isto, `current_emissao_id` podia ser apontado (por
        escrita interna ou bug futuro) para a emissão de outro relatório,
        e `verify_url`/o QR passariam a "confirmar" o relatório errado."""
        for rec in self:
            if rec.current_emissao_id and rec.current_emissao_id.relatorio_id != rec:
                raise ValidationError(_(
                    "A emissão vigente de um relatório precisa pertencer a ele "
                    "mesmo, nunca à emissão de outro relatório."
                ))
