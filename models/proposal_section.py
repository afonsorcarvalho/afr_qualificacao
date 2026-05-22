"""Biblioteca de blocos de texto reutilizáveis da proposta (F8 — Proposta LEGO).

Cada `afr.proposal.section` é uma "peça de lego" de texto: objetivo,
metodologia, rastreabilidade, entregáveis, responsabilidades do cliente,
condições comerciais, credenciais técnicas, etc.

O corpo (`body`) aceita expressões QWeb/Jinja (`{{ partner.name }}`,
`{{ doc.amount_total }}`) — resolvidas no momento da renderização do
relatório de cotação com contexto restrito.

Edição restrita ao grupo Gestor: o conteúdo é institucional e versionado
via seeds. Comerciais consomem (leitura) e ajustam por proposta na cópia
`afr.proposal.block` (F8.2).
"""

from odoo import fields, models


PROPOSAL_SECTION_CATEGORIES = [
    ("cover", "Capa"),
    ("objetivo", "Objetivo"),
    ("metodologia", "Metodologia"),
    ("tecnico", "Descrição Técnica (QI/QO/QD)"),
    ("escopo", "Escopo"),
    ("normas", "Normas / Rastreabilidade"),
    ("financeiro", "Condições Financeiras"),
    ("condicoes", "Condições Comerciais"),
    ("responsabilidades", "Responsabilidades do Cliente"),
    ("credenciais", "Credenciais Técnicas"),
    ("validadores", "Sistemas de Aquisição (Validadores)"),
    ("aceite", "Aceite / Assinatura"),
    ("custom", "Personalizado"),
]


class AfrProposalSection(models.Model):
    """Bloco de texto reutilizável montável na proposta de cotação."""

    _name = "afr.proposal.section"
    _description = "Bloco de Proposta (Texto Reutilizável)"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Título do bloco, exibido como cabeçalho da seção na proposta.",
    )
    code = fields.Char(
        help="Código curto para referência interna e seeds (ex: SEC-OBJETIVO).",
    )
    category = fields.Selection(
        selection=PROPOSAL_SECTION_CATEGORIES,
        default="custom",
        required=True,
        help="Categoria do bloco — agrupa e orienta estilo no relatório.",
    )
    body = fields.Html(
        string="Conteúdo",
        translate=True,
        sanitize=True,
        help=(
            "Conteúdo HTML do bloco. Aceita expressões QWeb/Jinja "
            "({{ partner.name }}, {{ doc.amount_total }}) resolvidas na "
            "renderização da proposta."
        ),
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )

    def name_get(self):
        """Display 'CODE — Name' para facilitar identificação em widgets M2O."""
        result = []
        for record in self:
            if record.code and record.name and record.code != record.name:
                label = "%s — %s" % (record.code, record.name)
            else:
                label = record.name or record.code or ""
            result.append((record.id, label))
        return result
