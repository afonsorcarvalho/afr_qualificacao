"""Bloco de proposta montado por cotação (F8.2 — Proposta LEGO).

Cada `afr.proposal.block` é uma peça de lego de uma proposta concreta.
O wizard configurador (ou o botão "Carregar Blocos") copia os slots do
`afr.proposal.template` escolhido para blocos da `sale.order`, onde o
comercial monta a proposta: reordena, liga/desliga (`included`) e edita
o texto (`body`) sem afetar a biblioteca institucional de seções.

O relatório de cotação (F8.3) percorre os blocos `included=True` na
ordem de `sequence`.
"""

from odoo import fields, models

from .proposal_template import PROPOSAL_BLOCK_KINDS


class AfrProposalBlock(models.Model):
    """Bloco de proposta de uma sale.order específica."""

    _name = "afr.proposal.block"
    _description = "Bloco de Proposta da Cotação"
    _order = "sequence, id"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    block_kind = fields.Selection(
        selection=PROPOSAL_BLOCK_KINDS,
        string="Tipo de Bloco",
        required=True,
        default="static",
    )
    section_id = fields.Many2one(
        comodel_name="afr.proposal.section",
        string="Seção de Origem",
        ondelete="set null",
        help="Bloco de texto da biblioteca que originou este bloco.",
    )
    title = fields.Char(
        string="Título",
        help="Título exibido no relatório (editável por proposta).",
    )
    body = fields.Html(
        string="Conteúdo",
        sanitize=True,
        help=(
            "Conteúdo do bloco, cópia editável da seção de origem. Aceita "
            "expressões {{ ... }} resolvidas na renderização da proposta."
        ),
    )
    included = fields.Boolean(
        string="Incluir na Proposta",
        default=True,
        help="Desmarque para omitir este bloco do PDF sem apagá-lo.",
    )

    def name_get(self):
        """Display: título do bloco ou rótulo do tipo dinâmico."""
        kind_labels = dict(PROPOSAL_BLOCK_KINDS)
        result = []
        for record in self:
            label = record.title or kind_labels.get(
                record.block_kind, record.block_kind or ""
            )
            result.append((record.id, label))
        return result
