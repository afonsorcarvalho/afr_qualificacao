"""Relatório Final — texto (blocos), anexos (posições) e aprovações (P3).

Esqueleto da Task 3 (O2M + helpers de numeração); completado na Task 5.
"""

from odoo import fields, models

from ._numbering import hierarchical_numbering, sort_key


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    template_id = fields.Many2one(
        "afr.relatorio.template", string="Template", ondelete="set null",
        tracking=True, help="Sugerido pela categoria do equipamento.")
    block_ids = fields.One2many(
        "afr.relatorio.block", "relatorio_id", string="Blocos do texto", copy=False)
    anexo_ids = fields.One2many(
        "afr.relatorio.anexo", "relatorio_id", string="Anexos", copy=False)
    aprovacao_ids = fields.One2many(
        "afr.relatorio.aprovacao", "relatorio_id", string="Aprovações", copy=False)

    def _body_blocks(self):
        """Blocos do texto principal (incluídos e sem vínculo a anexo), ordenados."""
        self.ensure_one()
        return self.block_ids.filtered(
            lambda b: b.included and not b.anexo_code).sorted(sort_key)

    def _block_numbering(self):
        self.ensure_one()
        return hierarchical_numbering(self._body_blocks())

    def _anexos_included(self):
        self.ensure_one()
        return self.anexo_ids.filtered("included").sorted(sort_key)
