# -*- coding: utf-8 -*-
"""Wizard "Copiar padrões de outro cliente" (Task 8)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoCopiarPadroesWizard(models.TransientModel):
    _name = "afr.qualificacao.copiar.padroes.wizard"
    _description = "Copiar padrões de outro cliente"

    partner_id = fields.Many2one("res.partner", string="Copiar para",
                                 required=True, readonly=True)
    source_partner_id = fields.Many2one(
        "res.partner", string="Copiar de", required=True,
        domain="[('parent_id', '=', False), ('id', '!=', partner_id)]",
        help="Cliente cujos padrões de cotação serão copiados.")
    line_ids = fields.One2many(
        "afr.qualificacao.copiar.padroes.wizard.line", "wizard_id",
        string="Padrões do cliente de origem")

    def _source_templates(self):
        self.ensure_one()
        return self.env["afr.qualificacao.config.template"].search([
            ("partner_id", "=", self.source_partner_id.commercial_partner_id.id),
            ("company_id", "=", self.env.company.id),
        ])

    def _existing_for(self, tpl):
        self.ensure_one()
        return self.env["afr.qualificacao.config.template"].search([
            ("partner_id", "=", self.partner_id.commercial_partner_id.id),
            ("equipment_category_id", "=", tpl.equipment_category_id.id),
            ("company_id", "=", self.env.company.id),
        ], limit=1)

    @api.onchange("source_partner_id")
    def _onchange_source_partner_id(self):
        cmds = [(5, 0, 0)]
        if self.source_partner_id and self.partner_id:
            for tpl in self._source_templates():
                cmds.append((0, 0, {
                    "template_id": tpl.id,
                    "existente_id": self._existing_for(tpl).id,
                    "copiar": True,
                }))
        self.line_ids = cmds

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wiz in wizards:
            if wiz.source_partner_id and not wiz.line_ids:
                wiz._onchange_source_partner_id()
        return wizards

    def action_copy(self):
        self.ensure_one()
        self.partner_id._check_afr_copiar_manager()
        dest = self.partner_id.commercial_partner_id
        if self.source_partner_id.commercial_partner_id == dest:
            raise UserError(_(
                "Escolha um cliente de origem diferente do destino."))
        Tpl = self.env["afr.qualificacao.config.template"]
        company = self.env.company
        done = 0
        for line in self.line_ids.filtered("copiar"):
            src = line.template_id
            if src.company_id != company or src.partner_id.commercial_partner_id \
                    != self.source_partner_id.commercial_partner_id:
                continue
            existing = self._existing_for(src)
            vals = src.copy_data({
                "partner_id": dest.id, "company_id": company.id,
            })[0]
            if existing:
                # substitui o escopo: as linhas antigas saem, as copiadas entram
                for fname in ("qo_line_ids", "qd_line_ids", "calib_line_ids",
                              "qd_point_ids"):
                    vals[fname] = [(5, 0, 0)] + vals.get(fname, [])
                vals.pop("name", None)  # mantém o nome do padrão do destino
                existing.write(vals)
            else:
                Tpl.create(vals)
            done += 1
        if not done:
            raise UserError(_("Marque ao menos um padrão para copiar."))
        return {"type": "ir.actions.act_window_close"}


class AfrQualificacaoCopiarPadroesWizardLine(models.TransientModel):
    _name = "afr.qualificacao.copiar.padroes.wizard.line"
    _description = "Padrão a copiar"

    wizard_id = fields.Many2one("afr.qualificacao.copiar.padroes.wizard",
                                required=True, ondelete="cascade")
    template_id = fields.Many2one("afr.qualificacao.config.template",
                                  string="Padrão", required=True)
    existente_id = fields.Many2one("afr.qualificacao.config.template",
                                   string="Já existe no destino")
    copiar = fields.Boolean(string="Copiar", default=True)
    equipment_category_id = fields.Many2one(
        related="template_id.equipment_category_id", string="Categoria")
    currency_id = fields.Many2one(related="template_id.currency_id")
    price_base = fields.Monetary(related="template_id.price_base",
                                 string="Preço combinado",
                                 currency_field="currency_id")
    estimated_days = fields.Float(related="template_id.estimated_days",
                                  string="Tempo combinado (dias)")
    aviso = fields.Char(string="Já existe no destino",
                        compute="_compute_aviso")

    @api.depends("existente_id", "template_id.price_base",
                 "template_id.estimated_days")
    def _compute_aviso(self):
        for line in self:
            old = line.existente_id
            if not old:
                line.aviso = False
                continue
            new = line.template_id
            line.aviso = _(
                "Substitui: preço %(p0).2f → %(p1).2f, tempo %(d0)g → %(d1)g dias"
            ) % {"p0": old.price_base, "p1": new.price_base,
                 "d0": old.estimated_days, "d1": new.estimated_days}
