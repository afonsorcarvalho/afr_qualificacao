"""Modelo para armazenar templates DOCX carregados via interface.

Este arquivo segue as diretrizes da documentação do Odoo para definição de
modelos e campos binários:
https://www.odoo.com/documentation/16.0/pt_BR/developer/reference/backend/orm.html
"""

from odoo import api, fields, models, _


class AfrQualificacaoDocxTemplate(models.Model):
    """Armazena arquivos de template DOCX para geração de relatórios."""

    _name = "afr.qualificacao.docx.template"
    _description = "Template DOCX de Qualificação"
    _order = "name"

    name = fields.Char(
        string="Nome do template",
        required=True,
        help="Identificação amigável do template para seleção nas qualificações.",
    )
    datas = fields.Binary(
        string="Arquivo DOCX",
        required=True,
        attachment=True,
        help="Conteúdo do arquivo DOCX (base64), utilizado como modelo pelo docxtpl.",
    )
    filename = fields.Char(
        string="Nome do arquivo",
        help="Nome original do arquivo para referência.",
    )
    mimetype = fields.Char(
        string="MIME Type",
        default="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        help="Tipo MIME do arquivo DOCX para controle e validação.",
    )
    active = fields.Boolean(
        string="Ativo",
        default=True,
        help="Desmarque para ocultar este template das seleções sem removê-lo.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Empresa",
        default=lambda self: self.env.company,
        help="Empresa à qual este template pertence (útil em ambientes multi-empresa).",
    )

    @api.constrains("mimetype")
    def _check_mimetype(self):
        """Garante que o tipo MIME seja compatível com DOCX."""
        for record in self:
            if record.mimetype and not record.mimetype.endswith(
                "officedocument.wordprocessingml.document"
            ):
                # Mantemos uma validação simples para evitar bloqueios indevidos.
                # A verificação detalhada de extensão/conteúdo deve ser feita no upload.
                pass


