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
    ("schedule", "Cronograma Estimado"),
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
    page_break = fields.Boolean(
        string="Nova Página",
        default=False,
        help=(
            "Se marcado, o bloco inicia em nova página no PDF. Caso "
            "contrário, continua na mesma página do bloco anterior."
        ),
    )
    title = fields.Char(
        string="Título",
        translate=True,
        help=(
            "Título do bloco no relatório. Vazio = usa o nome da seção "
            "(blocos de texto) ou o rótulo do tipo (blocos dinâmicos)."
        ),
    )
    # F9.1 — Hierarquia no template (propagada para os blocos ao seed)
    parent_id = fields.Many2one(
        comodel_name="afr.proposal.template.line",
        string="Linha Pai",
        domain="[('template_id', '=', template_id), ('id', '!=', id)]",
        ondelete="set null",
        help="Linha pai neste template — define hierarquia propagada ao sedar blocos na cotação.",
    )
    show_number = fields.Boolean(
        string="Numerado",
        default=True,
        help="Exibe numeração hierárquica automática no PDF (ex: 3.1). Propagado ao bloco ao sedar.",
    )
    show_title = fields.Boolean(
        string="Titulado",
        default=True,
        help="Exibe título no PDF. Desmarque para renderizar só o conteúdo. Propagado ao bloco ao sedar.",
    )
    # F9.1.x — campos de display (preview UX no editor de template)
    display_label = fields.Char(
        compute="_compute_display_label",
        string="Conteúdo",
        help="Cascade: título → nome da seção → rótulo do tipo. Identifica a linha visualmente.",
    )
    display_number = fields.Char(
        compute="_compute_display_number",
        string="Nº",
        help="Preview do número hierárquico que aparecerá no PDF (1, 2, 3, 3.1…).",
    )

    @api.depends("title", "section_id", "block_kind")
    def _compute_display_label(self):
        """Cascade: title → section name → kind label."""
        kind_labels = dict(PROPOSAL_BLOCK_KINDS)
        for line in self:
            line.display_label = (
                line.title
                or (line.section_id.name if line.section_id else "")
                or kind_labels.get(line.block_kind, "")
            )

    @api.depends(
        "template_id",
        "sequence",
        "parent_id",
        "show_number",
        "template_id.line_ids.sequence",
        "template_id.line_ids.parent_id",
        "template_id.line_ids.show_number",
    )
    def _compute_display_number(self):
        """Preview da numeração hierárquica das linhas do template.

        Espelha a lógica de SaleOrder._proposal_block_numbering, aplicada
        às linhas do template (todas; sem filtrar por 'included').
        """
        # Inicializa todas com ""
        for line in self:
            line.display_number = ""
        # Agrupa por template e calcula
        templates = self.mapped("template_id")
        for template in templates:
            lines = template.line_ids.sorted(lambda l: (l.sequence, l.id))
            numbers = {}
            root_counter = 0
            child_counters = {}
            for line in lines:
                if not line.parent_id:
                    if line.show_number:
                        root_counter += 1
                        numbers[line.id] = str(root_counter)
                        child_counters[line.id] = 0
                    else:
                        numbers[line.id] = ""
                else:
                    pid = line.parent_id.id
                    child_counters.setdefault(pid, 0)
                    if line.show_number:
                        child_counters[pid] += 1
                        parent_num = numbers.get(pid, "")
                        numbers[line.id] = (
                            f"{parent_num}.{child_counters[pid]}"
                            if parent_num
                            else str(child_counters[pid])
                        )
                    else:
                        numbers[line.id] = ""
            for line in template.line_ids:
                line.display_number = numbers.get(line.id, "")

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
