"""Emissão imutável do Relatório Final (spec §4.6).

Mesmo espírito de `afr.qualificacao._CERTIFICATE_FIELDS`: ACL é só leitura
para todos os grupos e, além disso, create/write exigem `env.su` + contexto
`rq_emissao_internal` — o único chamador é `action_emitir` (manager-only).
A única escrita posterior permitida é marcar `superseded=True` quando a
revisão seguinte é emitida. Exclusão nunca (só na desinstalação do módulo).
"""
from odoo import _, api, fields, models
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context

INTERNAL_CTX = "rq_emissao_internal"


class AfrRelatorioEmissao(models.Model):
    _name = "afr.relatorio.emissao"
    _description = "Emissão do Relatório Final"
    _order = "relatorio_id, revision desc, id desc"

    name = fields.Char(compute="_compute_name")
    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", string="Relatório", required=True,
        ondelete="restrict", index=True, readonly=True,
    )
    revision = fields.Integer(string="Revisão", readonly=True)
    pdf_attachment_id = fields.Many2one(
        "ir.attachment", string="PDF", ondelete="restrict", readonly=True,
    )
    sha256 = fields.Char(string="SHA-256", readonly=True)
    token = fields.Char(string="Token", readonly=True, index=True, copy=False)
    issued_at = fields.Datetime(string="Emitido em", readonly=True)
    issued_by = fields.Many2one("res.users", string="Emitido por", readonly=True)
    blocks_snapshot = fields.Text(string="Blocos congelados (JSON)", readonly=True)
    scan_snapshot = fields.Text(string="Verificação congelada (JSON)", readonly=True)
    superseded = fields.Boolean(string="Substituída", readonly=True, default=False)

    _sql_constraints = [
        ("token_unique", "unique(token)", "Token de emissão duplicado."),
    ]

    @api.depends("relatorio_id.name", "revision")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s Rev.%02d" % (rec.relatorio_id.name or "", rec.revision)

    def _rq_is_internal(self):
        return self.env.su and bool(self.env.context.get(INTERNAL_CTX))

    @api.model_create_multi
    def create(self, vals_list):
        if not self._rq_is_internal():
            raise UserError(_(
                "Emissões do relatório final só são criadas pela ação Emitir."
            ))
        # Ruling 5.1: `context['default_<campo>']` é aplicado pelo ORM
        # DENTRO do `super().create()`, depois deste pre-check — um
        # `default_superseded=True`/`default_token=...` sobreviveria ao
        # guard acima (mesmo raciocínio de `relatorio_aprovacao.py` e
        # `relatorio_texto.py::action_generate_relatorios_open`). Duas
        # camadas: contexto limpo + `superseded` sempre explícito no vals.
        for vals in vals_list:
            vals["superseded"] = False
        return super(
            AfrRelatorioEmissao, self.with_context(clean_context(self.env.context))
        ).create(vals_list)

    def write(self, vals):
        if not self._rq_is_internal() or set(vals) - {"superseded"}:
            raise UserError(_(
                "A emissão do relatório final é imutável: nada pode ser "
                "alterado depois de emitida."
            ))
        if not vals.get("superseded") and any(self.mapped("superseded")):
            raise UserError(_("Uma emissão substituída não volta a ser vigente."))
        return super().write(vals)

    def unlink(self):
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(_("A emissão do relatório final não pode ser excluída."))
