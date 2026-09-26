"""Template do Relatório Final de Qualificação (P3).

Espelha afr.proposal.template/line (sem mixin — decisão do spec §5): um
template é a lista ordenada de blocos do texto + checklist padrão + posições
de anexo padrão. `_apply_template()` do relatório copia tudo para registros
editáveis por relatório.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ._numbering import check_anexo_code_format, hierarchical_numbering

REPORT_BLOCK_KINDS = [
    ("static", "Bloco de Texto"),
    ("capa", "Capa"),
    ("indice", "Índice"),
    ("protocolo", "Protocolo (PrQT)"),
    ("laudo_micro", "Laudo Microbiológico (ReQM)"),
    ("assinaturas", "Quadro de Assinaturas"),
    ("anexo_separador", "Separador de Anexo"),
]

ANEXO_SLOT_KINDS = [
    ("collect_section", "Itens de coleta (por seção)"),
    ("instrument_certs", "Certificados de instrumentos"),
    ("malha_certs", "Certificados das malhas"),
    ("bloco", "Bloco do relatório"),
    ("upload", "Arquivos anexados"),
]


class AfrRelatorioTemplate(models.Model):
    _name = "afr.relatorio.template"
    _description = "Template de Relatório Final"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    line_ids = fields.One2many(
        "afr.relatorio.template.line", "template_id", string="Blocos", copy=True)
    checklist_line_ids = fields.One2many(
        "afr.relatorio.template.checklist.line", "template_id",
        string="Checklist padrão", copy=True)
    anexo_line_ids = fields.One2many(
        "afr.relatorio.template.anexo.line", "template_id",
        string="Anexos padrão", copy=True)
    equipment_category_ids = fields.Many2many(
        "engc.equipment.category",
        relation="afr_relatorio_template_equip_category_rel",
        column1="template_id", column2="category_id",
        string="Categorias de equipamento",
        help="O relatório sugere o template cuja categoria bate com a do equipamento.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)


class AfrRelatorioTemplateLine(models.Model):
    _name = "afr.relatorio.template.line"
    _description = "Bloco do Template de Relatório"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "afr.relatorio.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    block_kind = fields.Selection(
        REPORT_BLOCK_KINDS, string="Tipo de Bloco", required=True, default="static")
    section_id = fields.Many2one(
        "afr.proposal.section", string="Seção de Texto", ondelete="restrict",
        domain=[("document_type", "=", "report")],
        help="Obrigatória em Bloco de Texto; opcional nos dinâmicos (texto após as tabelas).",
    )
    page_break = fields.Boolean(string="Nova Página", default=False)
    title = fields.Char(string="Título", translate=True)
    parent_id = fields.Many2one(
        "afr.relatorio.template.line", string="Linha Pai", ondelete="set null",
        domain="[('template_id', '=', template_id), ('id', '!=', id)]")
    show_number = fields.Boolean(string="Numerado", default=True)
    show_title = fields.Boolean(string="Titulado", default=True)
    anexo_code = fields.Char(
        string="Código do anexo",
        help="Liga o bloco a uma posição de anexo (separador ou conteúdo do anexo 'bloco').",
    )
    display_label = fields.Char(compute="_compute_display_label", string="Conteúdo")
    display_number = fields.Char(compute="_compute_display_number", string="Nº")

    @api.depends("title", "section_id", "block_kind")
    def _compute_display_label(self):
        labels = dict(REPORT_BLOCK_KINDS)
        for line in self:
            line.display_label = (
                line.title or line.section_id.name or labels.get(line.block_kind, ""))

    @api.depends(
        "template_id", "sequence", "parent_id", "show_number", "anexo_code",
        "template_id.line_ids.sequence", "template_id.line_ids.parent_id",
        "template_id.line_ids.show_number", "template_id.line_ids.anexo_code",
    )
    def _compute_display_number(self):
        """Achado 3 (fix round 1): linhas com `anexo_code` (separador de
        anexo) não contam na numeração — como `_body_blocks()` já as exclui
        do corpo renderizado; manter os dois alinhados evita numeração que
        diverge do PDF."""
        for line in self:
            line.display_number = ""
        for template in self.mapped("template_id"):
            numbered_lines = template.line_ids.filtered(lambda l: not l.anexo_code)
            numbers = hierarchical_numbering(numbered_lines)
            for line in template.line_ids:
                line.display_number = numbers.get(line.id, "")

    @api.constrains("block_kind", "section_id")
    def _check_static_has_section(self):
        for rec in self:
            if rec.block_kind == "static" and not rec.section_id:
                raise ValidationError(_("Bloco de texto exige uma Seção de Texto selecionada."))

    @api.constrains("block_kind", "anexo_code")
    def _check_separator_has_code(self):
        for rec in self:
            if rec.block_kind == "anexo_separador" and not rec.anexo_code:
                raise ValidationError(_("Separador de anexo exige o código do anexo."))

    @api.constrains("anexo_code")
    def _check_anexo_code_format(self):
        """Findings review P3 (final), achado 3."""
        for rec in self:
            if rec.anexo_code and not check_anexo_code_format(rec.anexo_code):
                raise ValidationError(_(
                    "Código do anexo só pode conter letras, números, "
                    "'_' e '-' (sem espaços ou acentos)."
                ))

    @api.constrains("parent_id")
    def _check_no_cycle(self):
        """Achado 6 (fix round 1)."""
        for rec in self:
            if not rec._check_recursion():
                raise ValidationError(
                    _("Hierarquia circular detectada na linha do template."))

    def action_edit_template_line(self):
        """Abre a seção (static) ou a própria linha em modal — igual à cotação."""
        self.ensure_one()
        if self.block_kind == "static" and self.section_id:
            return {
                "type": "ir.actions.act_window", "name": _("Editar Seção"),
                "res_model": "afr.proposal.section", "res_id": self.section_id.id,
                "view_mode": "form", "target": "new",
            }
        return {
            "type": "ir.actions.act_window", "name": _("Editar Linha do Template"),
            "res_model": "afr.relatorio.template.line", "res_id": self.id,
            "view_mode": "form", "target": "new",
        }


class AfrRelatorioTemplateChecklistLine(models.Model):
    _name = "afr.relatorio.template.checklist.line"
    _description = "Item de Checklist Padrão do Template de Relatório"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "afr.relatorio.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    grupo = fields.Char(required=True)
    descricao = fields.Char(string="Descrição", required=True)


class AfrRelatorioTemplateAnexoLine(models.Model):
    _name = "afr.relatorio.template.anexo.line"
    _description = "Posição de Anexo Padrão do Template de Relatório"
    _order = "sequence, id"

    _sql_constraints = [
        (
            "template_anexo_line_code_uniq",
            "unique(template_id, code)",
            "Já existe uma posição de anexo com este código neste template.",
        ),
    ]

    template_id = fields.Many2one(
        "afr.relatorio.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(required=True, help="Chave estável usada pelo token anexo('code').")
    title = fields.Char(string="Título", required=True, translate=True)
    slot_kind = fields.Selection(ANEXO_SLOT_KINDS, string="Origem", required=True, default="upload")
    collect_sections = fields.Char(
        string="Seções de coleta", help="docx_section separados por vírgula.")
    cert_roles = fields.Char(
        string="Papéis de certificado", help="afr_role separados por vírgula (antes,depois,externo).")
    included_default = fields.Boolean(string="Incluído por padrão", default=True)

    @api.constrains("code")
    def _check_code_format(self):
        """Findings review P3 (final), achado 3."""
        for rec in self:
            if not check_anexo_code_format(rec.code):
                raise ValidationError(_(
                    "Código do anexo só pode conter letras, números, "
                    "'_' e '-' (sem espaços ou acentos)."
                ))
