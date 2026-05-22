"""Template de proposta — layout LEGO ordenado (F8 — Proposta LEGO).

Um `afr.proposal.template` é uma sequência ordenada de "slots". Cada slot
(`afr.proposal.template.line`) é ou um bloco de texto estático
(`afr.proposal.section`) ou um bloco dinâmico gerado pelo relatório
(escopo por equipamento, tabela de ciclos, financeiro, etc.).

A `sale.order` escolhe um template; o wizard configurador copia os slots
para `afr.proposal.block` (F8.2), onde o comercial monta a proposta como
peças de lego — reordena, liga/desliga, edita.

Multi-cliente: cada cliente em potencial pode ter seu próprio template.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# Tipos de bloco montáveis numa proposta. Reutilizado por afr.proposal.block
# (F8.2). 'static' renderiza um afr.proposal.section; os demais são blocos
# dinâmicos resolvidos pelo relatório a partir dos dados da sale.order.
PROPOSAL_BLOCK_KINDS = [
    ("static", "Bloco de Texto"),
    ("equipment_scope", "Escopo por Equipamento"),
    ("cycle_specs", "Tabela de Ciclos"),
    ("standards_table", "Tabela de Normas"),
    ("financial", "Resumo Financeiro"),
    ("optionals", "Serviços Opcionais"),
    ("acceptance", "Aceite / Assinatura"),
]


class AfrProposalTemplate(models.Model):
    """Layout de proposta reutilizável — coleção ordenada de blocos."""

    _name = "afr.proposal.template"
    _description = "Template de Proposta"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Nome do template (ex: Proposta LabQuali QI/QO/QD).",
    )
    code = fields.Char(
        help="Código curto para referência interna e seeds.",
    )
    line_ids = fields.One2many(
        comodel_name="afr.proposal.template.line",
        inverse_name="template_id",
        string="Blocos",
        copy=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )


class AfrProposalTemplateLine(models.Model):
    """Slot ordenado de um template de proposta."""

    _name = "afr.proposal.template.line"
    _description = "Bloco do Template de Proposta"
    _order = "sequence, id"

    template_id = fields.Many2one(
        comodel_name="afr.proposal.template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    block_kind = fields.Selection(
        selection=PROPOSAL_BLOCK_KINDS,
        string="Tipo de Bloco",
        required=True,
        default="static",
        help=(
            "'Bloco de Texto' renderiza uma seção reutilizável; os demais "
            "são gerados dinamicamente a partir dos dados da cotação."
        ),
    )
    section_id = fields.Many2one(
        comodel_name="afr.proposal.section",
        string="Seção de Texto",
        ondelete="restrict",
        help="Bloco de texto reutilizável (obrigatório quando tipo = Bloco de Texto).",
    )

    @api.constrains("block_kind", "section_id")
    def _check_static_has_section(self):
        for record in self:
            if record.block_kind == "static" and not record.section_id:
                raise ValidationError(
                    _("Bloco de texto exige uma Seção de Texto selecionada.")
                )

    def name_get(self):
        """Display do slot: seção (se static) ou rótulo do tipo dinâmico."""
        kind_labels = dict(PROPOSAL_BLOCK_KINDS)
        result = []
        for record in self:
            if record.block_kind == "static" and record.section_id:
                label = record.section_id.display_name
            else:
                label = kind_labels.get(record.block_kind, record.block_kind or "")
            result.append((record.id, label))
        return result
