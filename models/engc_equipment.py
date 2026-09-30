# -*- coding: utf-8 -*-
"""Extensão de engc.equipment para o módulo afr_qualificacao (não-destrutiva).

F10.5 (16.0.5.4.0):
- Relaxa obrigatoriedade de campos não essenciais à Qualificação
  (Meio de Aquisição, Local de Uso, Departamento) — equipamento de cliente
  cadastrado pelo comercial nem sempre tem esses dados.
- Expõe as OS de Qualificação do equipamento (afr.qualificacao.os via as
  qualifs) para a aba dedicada da view de Qualificação.
NÃO edita o módulo engc_os (terceiro) — tudo via _inherit.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EngcEquipment(models.Model):
    _inherit = "engc.equipment"

    afr_procedimento_id = fields.Many2one(
        comodel_name="afr.qualificacao.procedimento",
        string="Procedimento de Qualificação",
        domain=(
            "[('active', '=', True), ('company_id', 'in', [company_id, False]), "
            "'|', ('equipment_category_id', '=', False), "
            "('equipment_category_id', '=', category_id)]"
        ),
        help=(
            "Procedimento específico deste equipamento — tem prioridade "
            "sobre o procedimento do cliente e sobre o padrão da categoria "
            "na resolução automática (afr.qualificacao.procedimento."
            "_resolve_for_equipment)."
        ),
    )

    @api.constrains("afr_procedimento_id", "category_id")
    def _check_afr_procedimento_category(self):
        for equip in self:
            proc = equip.afr_procedimento_id
            if proc and proc.equipment_category_id and proc.equipment_category_id != equip.category_id:
                raise ValidationError(
                    _(
                        "O procedimento '%(proc)s' é específico da categoria "
                        "'%(proc_cat)s', incompatível com a categoria do "
                        "equipamento '%(equip)s' ('%(equip_cat)s')."
                    ) % {
                        "proc": proc.name,
                        "proc_cat": proc.equipment_category_id.name,
                        "equip": equip.display_name,
                        "equip_cat": equip.category_id.name if equip.category_id else _("(sem categoria)"),
                    }
                )

    # --- relaxa required (mantém demais atributos do campo original) ---
    means_of_aquisition_id = fields.Many2one(
        "engc.equipment.means.of.aquisition",
        "Meio de Aquisição",
        required=False,
    )
    location_id = fields.Many2one(
        "engc.equipment.location",
        "Local de Uso",
        required=False,
        check_company=True,
    )
    department = fields.Many2one(
        "hr.department",
        string="Departamento",
        required=False,
        check_company=True,
    )

    # --- OS de Qualificação do equipamento ---
    afr_qualificacao_ids = fields.One2many(
        comodel_name="afr.qualificacao",
        inverse_name="equipment_id",
        string="Qualificações",
    )
    afr_qualificacao_os_ids = fields.Many2many(
        comodel_name="afr.qualificacao.os",
        string="OS de Qualificação",
        compute="_compute_afr_qualificacao_os_ids",
    )
    afr_qualificacao_os_count = fields.Integer(
        compute="_compute_afr_qualificacao_os_ids",
        string="Nº OS Qualif",
    )

    @api.depends("afr_qualificacao_ids.os_id")
    def _compute_afr_qualificacao_os_ids(self):
        for rec in self:
            oss = rec.afr_qualificacao_ids.mapped("os_id")
            rec.afr_qualificacao_os_ids = oss
            rec.afr_qualificacao_os_count = len(oss)

    def action_view_afr_qualificacao_os(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "OS de Qualificação",
            "res_model": "afr.qualificacao.os",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.afr_qualificacao_os_ids.ids)],
        }
