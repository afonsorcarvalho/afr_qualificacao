"""Posição de anexo do Relatório Final (P3: posições e numeração).

Resolução de arquivos (`_resolve_files`, `_check_files`) é de P4.
"""

from odoo import api, fields, models

from ._numbering import sort_key
from .relatorio_template import ANEXO_SLOT_KINDS


class AfrRelatorioAnexo(models.Model):
    _name = "afr.relatorio.anexo"
    _description = "Anexo do Relatório Final"
    _order = "sequence, id"

    _sql_constraints = [
        (
            "relatorio_anexo_code_uniq",
            "unique(relatorio_id, code)",
            "Já existe um anexo com este código neste relatório.",
        ),
    ]

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    included = fields.Boolean(string="Incluir", default=True)
    code = fields.Char(required=True)
    title = fields.Char(string="Título", required=True)
    slot_kind = fields.Selection(ANEXO_SLOT_KINDS, string="Origem", required=True, default="upload")
    collect_sections = fields.Char(string="Seções de coleta")
    cert_roles = fields.Char(string="Papéis de certificado")
    block_id = fields.Many2one(
        "afr.relatorio.block", string="Bloco", ondelete="set null",
        domain="[('relatorio_id', '=', relatorio_id)]")
    attachment_ids = fields.Many2many(
        "ir.attachment", relation="afr_relatorio_anexo_attachment_rel",
        column1="anexo_id", column2="attachment_id", string="Arquivos")
    numero = fields.Integer(string="Nº", compute="_compute_numero")

    @api.depends(
        "included", "sequence",
        "relatorio_id.anexo_ids.included", "relatorio_id.anexo_ids.sequence",
    )
    def _compute_numero(self):
        """1..N sobre os incluídos, na ordem (sequence, id); excluído = 0."""
        for anexo in self:
            anexo.numero = 0
        for rel in self.mapped("relatorio_id"):
            n = 0
            for anexo in rel.anexo_ids.sorted(sort_key):
                if anexo.included:
                    n += 1
                    anexo.numero = n
                else:
                    anexo.numero = 0
