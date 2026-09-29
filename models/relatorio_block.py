"""Bloco do texto de um Relatório Final (cópia editável do template)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ._numbering import check_anexo_code_format
from .relatorio_template import REPORT_BLOCK_KINDS


class AfrRelatorioBlock(models.Model):
    _name = "afr.relatorio.block"
    _description = "Bloco do Relatório Final"
    _order = "sequence, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    block_kind = fields.Selection(
        REPORT_BLOCK_KINDS, string="Tipo de Bloco", required=True, default="static")
    section_id = fields.Many2one(
        "afr.proposal.section", string="Seção de Origem", ondelete="set null",
        domain=[("document_type", "=", "report")])
    title = fields.Char(string="Título")
    body = fields.Html(
        string="Conteúdo", sanitize=True,
        help="Aceita {{ expressões }}: relatorio, os, partner, equipment, company, "
             "criterio['tolerancia'|'f0_fator'|'f0_minimo'|'valor_d'], anexo('code').")
    included = fields.Boolean(string="Incluir", default=True)
    page_break = fields.Boolean(string="Nova Página", default=False)
    parent_id = fields.Many2one(
        "afr.relatorio.block", string="Bloco Pai", ondelete="set null", index=True,
        domain="[('relatorio_id', '=', relatorio_id), ('id', '!=', id)]")
    show_number = fields.Boolean(string="Numerado", default=True)
    show_title = fields.Boolean(string="Titulado", default=True)
    anexo_code = fields.Char(string="Código do anexo")
    anexo_ids = fields.One2many(
        "afr.relatorio.anexo", "block_id", string="Anexos que usam este bloco")
    is_anexo_content = fields.Boolean(
        compute="_compute_is_anexo_content", store=True, index=True,
        help="Bloco apontado por um anexo (origem 'Bloco do relatório'): "
             "impresso na posição do anexo, fora do corpo e da numeração.")
    display_label = fields.Char(compute="_compute_display_label", string="Conteúdo")
    display_number = fields.Char(compute="_compute_display_number", string="Nº")

    @api.depends("title", "section_id", "block_kind")
    def _compute_display_label(self):
        labels = dict(REPORT_BLOCK_KINDS)
        for block in self:
            block.display_label = (
                block.title or block.section_id.name or labels.get(block.block_kind, ""))

    @api.depends("anexo_ids", "anexo_ids.relatorio_id")
    def _compute_is_anexo_content(self):
        """Achado M3 (review final): `anexo_ids` é o inverso de `block_id`
        sem domain — um `block_id` de RPC (ou dado legado) apontando pra um
        bloco de OUTRO relatório marcava esse bloco como conteúdo de anexo
        por engano. Filtra pelo mesmo `relatorio_id` do bloco."""
        for block in self:
            block.is_anexo_content = bool(
                block.anexo_ids.filtered(lambda a: a.relatorio_id == block.relatorio_id))

    @api.depends(
        "relatorio_id", "sequence", "parent_id", "show_number", "included", "is_anexo_content",
        "relatorio_id.block_ids.sequence", "relatorio_id.block_ids.parent_id",
        "relatorio_id.block_ids.show_number", "relatorio_id.block_ids.included",
        "relatorio_id.block_ids.is_anexo_content",
    )
    def _compute_display_number(self):
        # Atribui SÓ a `self` (ver `afr.relatorio.anexo._compute_numero`):
        # irmão fora do recorte viraria write() e bump editorial.
        numbers = {rel: rel._block_numbering() for rel in self.mapped("relatorio_id")}
        for block in self:
            block.display_number = numbers.get(block.relatorio_id, {}).get(block.id, "")

    @api.constrains("parent_id")
    def _check_no_cycle(self):
        """Achado 6 (fix round 1): `_check_recursion()` embutido do Odoo
        substitui o loop manual — mesmo algoritmo (segue `parent_id` até
        repetir ou chegar ao topo), sem mudança de comportamento."""
        for rec in self:
            if not rec._check_recursion():
                raise ValidationError(
                    _("Hierarquia circular detectada no bloco '%s'.") % (rec.title or rec.id))

    @api.constrains("anexo_code")
    def _check_anexo_code_format(self):
        """Findings review P3 (final), achado 3."""
        for rec in self:
            if rec.anexo_code and not check_anexo_code_format(rec.anexo_code):
                raise ValidationError(_(
                    "Código do anexo só pode conter letras, números, "
                    "'_' e '-' (sem espaços ou acentos)."
                ))

    def name_get(self):
        labels = dict(REPORT_BLOCK_KINDS)
        return [(r.id, r.title or labels.get(r.block_kind, r.block_kind or "")) for r in self]

    def action_edit_block(self):
        """Abre o bloco em modal. Só blocos de texto têm corpo livre; nos
        dinâmicos o corpo é um texto opcional exibido após as tabelas."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Editar Bloco do Relatório"),
            "res_model": "afr.relatorio.block",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref("afr_qualificacao.view_relatorio_block_form").id, "form")],
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }
