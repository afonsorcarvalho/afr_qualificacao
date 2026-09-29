from odoo import api, fields, models

SNIPPET_CATEGORIES = [
    ("tabela", "Tabelas técnicas"),
    ("lista", "Listas e texto"),
    ("destaque", "Destaques"),
    ("layout", "Layout"),
]


class RelatorioSnippet(models.Model):
    """Bloco pronto inserido no corpo de um bloco do Relatório Final pelo
    editor `rq_block_html`. Gestor mantém a biblioteca sem deploy."""

    _name = "afr.relatorio.snippet"
    _description = "Bloco pronto do relatório"
    _order = "category, sequence, id"

    name = fields.Char(string="Nome", required=True)
    category = fields.Selection(SNIPPET_CATEGORIES, string="Categoria", required=True)
    sequence = fields.Integer(default=10)
    body = fields.Html(string="Conteúdo", sanitize=True)
    active = fields.Boolean(default=True)

    @api.model
    def rq_snippet_list(self):
        return [
            {"id": s.id, "name": s.name, "category": s.category, "body": s.body or ""}
            for s in self.search([])
        ]
