# -*- coding: utf-8 -*-
"""Wizard para criar um relatório parcial rápido a partir da OS de qualificação.

Disparado pelo botão "Iniciar execução" ou "Novo relatório" na form da OS.
Pré-preenche data_inicio=now e tecnico_ids=current user (employee).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoOsRelatorioWizard(models.TransientModel):
    _name = "afr.qualificacao.os.relatorio.wizard"
    _description = "Wizard: novo relatório parcial de OS qualificação"

    os_id = fields.Many2one(
        "afr.qualificacao.os",
        string="Ordem de serviço",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    data_inicio = fields.Datetime(
        string="Início",
        required=True,
        default=fields.Datetime.now,
    )
    data_fim = fields.Datetime(string="Fim")
    tecnico_ids = fields.Many2many(
        "hr.employee",
        relation="afr_qualif_os_relatorio_wizard_tecnico_rel",
        column1="wizard_id",
        column2="employee_id",
        string="Técnicos",
        required=True,
        default=lambda self: self._default_tecnico_ids(),
    )
    descricao = fields.Text(string="Descrição", required=True)
    cycle_ids = fields.Many2many(
        "afr.qualificacao.cycle",
        relation="afr_qualif_os_relatorio_wizard_cycle_rel",
        column1="wizard_id",
        column2="cycle_id",
        string="Ciclos realizados",
    )
    malha_ids = fields.Many2many(
        "afr.qualificacao.malha",
        relation="afr_qualif_os_relatorio_wizard_malha_rel",
        column1="wizard_id",
        column2="malha_id",
        string="Malhas realizadas",
    )

    def _default_tecnico_ids(self):
        emp = self.env["hr.employee"].search(
            [("user_id", "=", self.env.uid)], limit=1
        )
        return [(6, 0, emp.ids)] if emp else False

    def action_create(self):
        """Cria o relatório (state=draft) e abre seu form."""
        self.ensure_one()
        if not self.os_id:
            raise UserError(_("OS obrigatória."))
        if self.data_fim and self.data_fim < self.data_inicio:
            raise UserError(_("Fim deve ser ≥ início."))
        relatorio = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": self.os_id.id,
            "data_inicio": self.data_inicio,
            "data_fim": self.data_fim or self.data_inicio,
            "tecnico_ids": [(6, 0, self.tecnico_ids.ids)],
            "descricao": self.descricao,
            "cycle_ids": [(6, 0, self.cycle_ids.ids)],
            "malha_ids": [(6, 0, self.malha_ids.ids)],
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Relatório parcial"),
            "res_model": "afr.qualificacao.os.relatorio",
            "view_mode": "form",
            "res_id": relatorio.id,
            "target": "current",
        }
