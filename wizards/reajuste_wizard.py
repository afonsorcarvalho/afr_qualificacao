# -*- coding: utf-8 -*-
"""Wizard "Reajustar preços combinados" do cliente (Task 5)."""
from datetime import date

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round

from ..models import bcb_index
from ..models.reajuste import INDICES, TIPOS


class AfrQualificacaoReajusteWizard(models.TransientModel):
    _name = "afr.qualificacao.reajuste.wizard"
    _description = "Reajustar preços combinados"

    partner_id = fields.Many2one("res.partner", string="Cliente",
                                 required=True, readonly=True)
    tipo = fields.Selection(TIPOS, string="Reajustar por", required=True,
                            default="indice")
    indice = fields.Selection(INDICES, string="Índice", default="ipca")
    percentual = fields.Float(
        string="Percentual (%)", digits=(16, 4),
        help="Preenchido pelo acumulado de 12 meses do Banco Central; "
             "pode ser editado.")
    valor = fields.Float(string="Valor a somar (R$)",
                         help="Somado ao preço combinado de cada template.")
    periodo = fields.Char(string="Período", readonly=True)
    bcb_aviso = fields.Char(readonly=True)
    line_ids = fields.One2many("afr.qualificacao.reajuste.wizard.line",
                               "wizard_id", string="Prévia")

    @api.model
    def _lines_for(self, partner_id):
        partner = self.env["res.partner"].browse(partner_id)
        return [(0, 0, {"template_id": t.id})
                for t in partner._afr_reajuste_templates()]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get("partner_id") and "line_ids" in fields_list:
            res["line_ids"] = self._lines_for(res["partner_id"])
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("partner_id") and not vals.get("line_ids"):
                vals["line_ids"] = self._lines_for(vals["partner_id"])
        return super().create(vals_list)

    def _ref_date(self):
        """Mês de referência: aniversário deste ano (ou hoje, sem data)."""
        today = fields.Date.context_today(self)
        aniv = self.partner_id.afr_reajuste_data
        if not aniv:
            return today
        Partner = self.env["res.partner"]
        ref = Partner._afr_aniversario_em(aniv, today.year)
        if ref > today:
            ref = Partner._afr_aniversario_em(aniv, today.year - 1)
        return ref.replace(day=1)

    def _periodo_txt(self):
        ini, fim = bcb_index.period_12m(self._ref_date())
        return "%s a %s" % (ini.strftime("%m/%Y"), fim.strftime("%m/%Y"))

    def _fetch_index(self):
        """Busca o acumulado no BCB; em falha, entra no modo manual."""
        for wiz in self:
            if wiz.tipo != "indice" or not wiz.indice:
                continue
            ref = wiz._ref_date()
            wiz.periodo = wiz._periodo_txt()
            try:
                wiz.percentual = bcb_index.accumulated_12m(
                    bcb_index.SERIES[wiz.indice], ref)
                wiz.bcb_aviso = False
            except UserError as e:
                wiz.percentual = 0.0
                wiz.bcb_aviso = _(
                    "Não foi possível obter o índice no Banco Central (%s). "
                    "Informe o percentual manualmente.") % e.args[0]

    @api.onchange("tipo", "indice")
    def _onchange_indice(self):
        self._fetch_index()

    def _novo_preco(self, antes):
        if self.tipo == "valor":
            novo = antes + (self.valor or 0.0)
        else:
            novo = antes * (1 + (self.percentual or 0.0) / 100.0)
        return float_round(novo, precision_digits=2)

    def action_confirm(self):
        self.ensure_one()
        self.partner_id._check_afr_reajuste_manager()
        if not self.line_ids:
            raise UserError(_("Este cliente não tem preços combinados."))
        if self.tipo == "valor" and not self.valor:
            raise UserError(_("Informe o valor a somar."))
        if self.tipo != "valor" and not self.percentual:
            raise UserError(_("Informe o percentual do reajuste."))
        if self.tipo == "indice" and not self.periodo:
            self.periodo = self._periodo_txt()
        lines = []
        for line in self.line_ids:
            tpl = line.template_id
            antes = tpl.price_base
            depois = self._novo_preco(antes)
            tpl.price_base = depois
            lines.append((0, 0, {
                "template_id": tpl.id,
                "equipment_category_id": tpl.equipment_category_id.id,
                "valor_antigo": antes, "valor_novo": depois}))
        hist = self.env["afr.qualificacao.reajuste"].create({
            "partner_id": self.partner_id.id, "tipo": self.tipo,
            "indice": self.indice if self.tipo == "indice" else False,
            "periodo": self.periodo if self.tipo == "indice" else False,
            "percentual": self.percentual if self.tipo != "valor" else 0.0,
            "valor": self.valor if self.tipo == "valor" else 0.0,
            "line_ids": lines,
        })
        if self.tipo == "valor":
            desc = _("valor fixo de %.2f") % self.valor
        else:
            desc = "%.4f%%" % self.percentual
            if self.tipo == "indice":
                desc += " (%s %s)" % (dict(INDICES)[self.indice],
                                      self.periodo or "")
        rows = Markup("").join(
            Markup("<li>%s: %.2f → %.2f</li>") % (
                l.template_id.display_name, l.valor_antigo, l.valor_novo)
            for l in hist.line_ids)
        # sudo: o gestor de Qualificação pode não ter direito de escrita em
        # contatos (exigido pelo chatter); a permissão do reajuste já foi
        # checada acima. Autor = usuário real.
        self.partner_id.sudo().message_post(body=Markup(
            "<p>%s %s</p><ul>%s</ul>") % (
                _("Reajuste dos preços combinados:"), desc, rows),
            author_id=self.env.user.partner_id.id)
        return {"type": "ir.actions.act_window_close"}


class AfrQualificacaoReajusteWizardLine(models.TransientModel):
    _name = "afr.qualificacao.reajuste.wizard.line"
    _description = "Prévia do reajuste"

    wizard_id = fields.Many2one("afr.qualificacao.reajuste.wizard",
                                required=True, ondelete="cascade")
    template_id = fields.Many2one("afr.qualificacao.config.template",
                                  string="Template", required=True,
                                  readonly=True)
    equipment_category_id = fields.Many2one(
        related="template_id.equipment_category_id", string="Categoria")
    currency_id = fields.Many2one(related="template_id.currency_id")
    antes = fields.Monetary(related="template_id.price_base", string="Antes",
                            currency_field="currency_id")
    depois = fields.Monetary(compute="_compute_depois", string="Depois",
                             currency_field="currency_id")

    @api.depends("antes", "wizard_id.tipo", "wizard_id.percentual",
                 "wizard_id.valor")
    def _compute_depois(self):
        for line in self:
            line.depois = line.wizard_id._novo_preco(line.antes)
