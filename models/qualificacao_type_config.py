"""Configuração comercial por tipo de qualificação.

Mapeia cada tipo de qualificação (instalação, operacional, etc.) a um
produto de serviço (`product.product`) usado como padrão ao criar pedidos
de venda associados às qualificações. Também permite definir uma conta
analítica padrão por tipo, útil para rastreio de custos.

Referência Odoo 16 — produtos serviço:
https://www.odoo.com/documentation/16.0/applications/sales/sales/invoicing/time_materials.html
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AfrQualificacaoTypeConfig(models.Model):
    """Configuração tipo de qualificação → produto serviço (default p/ SO)."""

    _name = "afr.qualificacao.type.config"
    _description = "Configuração Comercial de Tipo de Qualificação"
    _order = "company_id, qualification_type"

    qualification_type = fields.Selection(
        selection=[
            ("installation", "Instalação (QI)"),
            ("operational", "Operacional (QO)"),
            ("performance", "Desempenho (QD)"),
            ("software", "Software (QS)"),
        ],
        string="Tipo de Qualificação",
        required=True,
        help=(
            "Tipo de qualificação ao qual esta configuração se aplica. Quando "
            "uma nova qualificação for criada com este tipo, o produto e a "
            "conta analítica configurados aqui serão usados como padrão."
        ),
    )
    service_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Produto de Serviço",
        required=True,
        domain=[("type", "=", "service"), ("sale_ok", "=", True)],
        help=(
            "Produto do tipo serviço usado nas linhas de pedido de venda "
            "geradas a partir de qualificações deste tipo. Deve ter "
            "type='service' e sale_ok=True."
        ),
    )
    default_unit_price = fields.Monetary(
        string="Preço Padrão",
        currency_field="currency_id",
        help=(
            "Preço unitário sugerido para a linha de pedido de venda. Se 0, "
            "será usado o list_price do produto."
        ),
    )
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Conta Analítica Padrão",
        help="Conta analítica usada para classificar custos e receitas.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
        help="Empresa à qual esta configuração se aplica.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        readonly=True,
        help="Moeda derivada da empresa.",
    )
    active = fields.Boolean(
        default=True,
        help="Configurações inativas não são consideradas como padrão.",
    )

    _sql_constraints = [
        (
            "uniq_type_company",
            "unique(qualification_type, company_id)",
            "Já existe uma configuração ativa para este tipo nesta empresa.",
        ),
    ]

    @api.constrains("service_product_id")
    def _check_product_is_service(self):
        """Garante que o produto selecionado é do tipo serviço.

        O `domain` na view já restringe a UI, mas a constraint defende contra
        criação programática (ex.: import) com produto inválido.
        """
        for record in self:
            if record.service_product_id and record.service_product_id.type != "service":
                raise ValidationError(
                    _(
                        "Produto '%s' não é do tipo serviço. Apenas produtos "
                        "com type='service' podem ser usados em qualificações."
                    )
                    % record.service_product_id.display_name
                )

    @api.model
    def get_config_for(self, qualification_type, company=None):
        """Retorna o registro de configuração para o tipo + empresa.

        Helper usado pelos computes em `afr.qualificacao` para evitar duplicar
        a lógica de busca. Retorna o primeiro registro ativo encontrado ou
        recordset vazio se nenhum configurado.
        """
        company = company or self.env.company
        return self.search(
            [
                ("qualification_type", "=", qualification_type),
                ("company_id", "=", company.id),
                ("active", "=", True),
            ],
            limit=1,
        )
