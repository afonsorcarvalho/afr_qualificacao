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

    # Task 9 (16.0.9.1.0): marca/modelo/série opcionais e sem unicidade
    # série+marca — o time de Qualificação cadastra direto na lista do
    # cliente, muitas vezes só com categoria/TAG. ondelete mantém o
    # restrict original (FK não muda).
    marca_id = fields.Many2one(
        "engc.equipment.marca", "Marca", required=False, ondelete="restrict",
    )
    model = fields.Char("Modelo", required=False)
    serial_number = fields.Char("Número de Série", required=False)

    # Odoo MESCLA _sql_constraints de todas as classes por nome — lista
    # vazia não remove a herdada. Redefinir o mesmo nome com CHECK(true)
    # substitui a definição: o Odoo dropa o UNIQUE e cria um no-op.
    # (A migração 16.0.9.1.0 também dropa o UNIQUE antigo.)
    _sql_constraints = [
        ("serial_marca_company_id_no_uniq", "CHECK (true)",
         "Série/marca não exigem unicidade."),
    ]

    @api.depends("category_id", "model", "marca_id", "serial_number", "tag")
    def _compute_name(self):
        # Original do engc_os zera o nome se faltar qualquer parte; aqui
        # monta só com as partes presentes, com fallback TAG / id.
        for record in self:
            parts = [
                record.category_id.name,
                record.model,
                record.serial_number,
                record.marca_id.name,
            ]
            name = " ".join(p.strip() for p in parts if p and p.strip())
            if not name:
                name = (record.tag or "").strip()
            if not name:
                rid = record._origin.id or (record.id if isinstance(record.id, int) else False)
                name = _("Equipamento %s") % rid if rid else _("Novo equipamento")
            record.name = name

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

    def action_open_afr_equipment_form(self):
        """Abre a ficha completa a partir da lista editável do cliente."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "engc.equipment",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref("afr_qualificacao.view_engc_equipment_qualif_form").id, "form")],
            "target": "current",
        }
