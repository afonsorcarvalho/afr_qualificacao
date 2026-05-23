"""Template de configuração de qualificações (atalho do wizard configurador).

Permite salvar uma matriz de qualificações + ciclos + malhas reusável em
múltiplos orçamentos. Comercial cria um template "Pacote Padrão Autoclave"
e aplica em N orçamentos futuros sem reconfigurar manualmente.

Filtrável por `equipment_category_id` para sugerir templates relevantes ao
tipo de equipamento sendo orçado.
"""

from odoo import api, fields, models


class AfrQualificacaoConfigTemplate(models.Model):
    """Template de configuração de qualificações reusável."""

    _name = "afr.qualificacao.config.template"
    _description = "Template de Configuração de Qualificações"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Nome descritivo do template (ex: Pacote Padrão Autoclave).",
    )
    equipment_category_id = fields.Many2one(
        comodel_name="engc.equipment.category",
        string="Categoria de Equipamento",
        help=(
            "Restringe sugestão deste template no wizard configurador para "
            "equipamentos desta categoria. Vazio = todas categorias."
        ),
    )
    do_qi = fields.Boolean(string="Inclui QI")
    do_qo = fields.Boolean(string="Inclui QO")
    do_qs = fields.Boolean(string="Inclui QS")
    qo_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.config.template.qo",
        inverse_name="template_id",
        string="Ciclos QO (sem carga)",
        copy=True,
    )
    qd_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.config.template.qd",
        inverse_name="template_id",
        string="Ciclos QD",
        copy=True,
    )
    calib_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.config.template.calib",
        inverse_name="template_id",
        string="Malhas Calibração",
        copy=True,
    )
    description = fields.Text(translate=True)
    # F8.1 — preço/dias sugeridos do pacote de equipamento (modelo híbrido:
    # template sugere, comercial ajusta na proposta).
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        string="Moeda",
        readonly=True,
    )
    price_base = fields.Monetary(
        string="Preço Base",
        currency_field="currency_id",
        help="Preço sugerido do pacote de equipamento. Sempre editável na proposta.",
    )
    estimated_days = fields.Float(
        string="Dias Estimados",
        help="Dias de execução estimados do pacote completo.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class AfrQualificacaoConfigTemplateQd(models.Model):
    """Linha de ciclo QD dentro de um template."""

    _name = "afr.qualificacao.config.template.qd"
    _description = "Ciclo QD do Template"
    _order = "sequence, id"

    template_id = fields.Many2one(
        comodel_name="afr.qualificacao.config.template",
        required=True,
        ondelete="cascade",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo",
        required=True,
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    sequence = fields.Integer(default=10)

    @api.constrains("qty")
    def _check_qty_positive(self):
        for record in self:
            if record.qty < 1:
                from odoo.exceptions import ValidationError
                raise ValidationError("Quantidade deve ser ≥ 1.")


class AfrQualificacaoConfigTemplateQo(models.Model):
    """F8.8 — Linha de ciclo QO (sem carga) dentro de um template de equipamento."""

    _name = "afr.qualificacao.config.template.qo"
    _description = "Ciclo QO do Template"
    _order = "sequence, id"

    template_id = fields.Many2one(
        comodel_name="afr.qualificacao.config.template",
        required=True,
        ondelete="cascade",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo",
        required=True,
        domain=[("load_type", "in", ["vazio", "sem_carga"])],
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    sequence = fields.Integer(default=10)

    @api.constrains("qty")
    def _check_qty_positive(self):
        for record in self:
            if record.qty < 1:
                from odoo.exceptions import ValidationError
                raise ValidationError("Quantidade deve ser ≥ 1.")


class AfrQualificacaoConfigTemplateCalib(models.Model):
    """Linha de malha de calibração dentro de um template."""

    _name = "afr.qualificacao.config.template.calib"
    _description = "Malha Calib do Template"
    _order = "sequence, id"

    template_id = fields.Many2one(
        comodel_name="afr.qualificacao.config.template",
        required=True,
        ondelete="cascade",
    )
    malha_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.malha.type",
        string="Tipo de Malha",
        required=True,
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    sequence = fields.Integer(default=10)

    @api.constrains("qty")
    def _check_qty_positive(self):
        for record in self:
            if record.qty < 1:
                from odoo.exceptions import ValidationError
                raise ValidationError("Quantidade deve ser ≥ 1.")
