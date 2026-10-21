"""Confirmação ao substituir o padrão de cotação de um cliente."""

from odoo import _, fields, models


class AfrQualificacaoClientDefaultConfirm(models.TransientModel):
    _name = "afr.qualificacao.client.default.confirm"
    _description = "Confirmar substituição do padrão do cliente"

    equipment_line_id = fields.Many2one(
        "afr.qualificacao.configurator.equipment", required=True,
        ondelete="cascade")
    template_id = fields.Many2one(
        "afr.qualificacao.config.template", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    category_id = fields.Many2one(
        "engc.equipment.category", string="Categoria", readonly=True)
    currency_id = fields.Many2one(
        "res.currency", related="template_id.currency_id", readonly=True)
    old_price = fields.Monetary(
        string="Preço combinado atual", currency_field="currency_id",
        readonly=True)
    new_price = fields.Monetary(
        string="Novo preço combinado", currency_field="currency_id",
        readonly=True)
    old_days = fields.Float(string="Tempo atual (dias)", readonly=True)
    new_days = fields.Float(string="Novo tempo (dias)", readonly=True)
    message = fields.Char(compute="_compute_message")
    # Aberto da linha de seção da cotação: fecha ao terminar (não há
    # configurador a reabrir).
    return_to_so = fields.Boolean()

    def _compute_message(self):
        for rec in self:
            rec.message = _("Substituir o padrão de %(cat)s de %(partner)s?") % {
                "cat": rec.category_id.name or "",
                "partner": rec.partner_id.name or "",
            }
            if not rec.new_price:
                rec.message += _(" Atenção: o novo padrão ficará sem preço combinado.")

    def action_confirm(self):
        self.ensure_one()
        notification, _tpl = self.equipment_line_id._write_client_default(
            template=self.template_id, price=self.new_price,
            days=self.new_days)
        # O Odoo só mantém um modal de ação: este diálogo substituiu o
        # configurador; ao terminar, reabre-o para o user seguir a cotação.
        notification["params"]["next"] = self._back_to_configurator()
        return notification

    def _back_to_configurator(self):
        wizard = self.equipment_line_id.wizard_id
        if wizard and not self.return_to_so:
            return wizard._reopen()
        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        self.ensure_one()
        return self._back_to_configurator()
