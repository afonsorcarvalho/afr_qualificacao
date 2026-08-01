# -*- coding: utf-8 -*-
"""Wizard: gerar OS de Qualificação por grupo de equipamentos.

Uma cotação confirmada pode render N OS — tipicamente uma por visita de campo
(setor, andar, disponibilidade do cliente). Cada execução cria UMA OS com o
subconjunto de equipamentos escolhido; repete-se até não sobrar pendente.

Invariante: um equipamento nunca entra em duas OS da mesma cotação. Garantida
aqui (domínio + revalidação) e no modelo (`afr.qualificacao`
`_check_equipamento_unico_por_os_da_so`).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoOsGenerateWizard(models.TransientModel):
    _name = "afr.qualificacao.os.generate.wizard"
    _description = "Wizard: gerar OS de Qualificação por grupo de equipamentos"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Cotação",
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    equipamento_disponivel_ids = fields.Many2many(
        "engc.equipment",
        relation="afr_qualif_gen_os_wizard_disp_rel",
        column1="wizard_id",
        column2="equipment_id",
        string="Disponíveis",
        compute="_compute_equipamento_disponivel_ids",
        help="Equipamentos da cotação que ainda não têm OS. Alimenta o domínio.",
    )
    equipment_ids = fields.Many2many(
        "engc.equipment",
        relation="afr_qualif_gen_os_wizard_equip_rel",
        column1="wizard_id",
        column2="equipment_id",
        string="Equipamentos desta OS",
        required=True,
    )

    @api.depends("sale_order_id")
    def _compute_equipamento_disponivel_ids(self):
        for wiz in self:
            wiz.equipamento_disponivel_ids = wiz.sale_order_id.equipamentos_sem_os_ids

    @api.onchange("sale_order_id")
    def _onchange_sale_order_default_equipments(self):
        """Default = todos os pendentes; o usuário desmarca o que não vai agora."""
        if self.sale_order_id:
            self.equipment_ids = [
                (6, 0, self.sale_order_id.equipamentos_sem_os_ids.ids)
            ]

    def action_generate(self):
        self.ensure_one()
        so = self.sale_order_id
        if so.state != "sale":
            raise UserError(_(
                "Confirme a cotação antes de gerar OS de Qualificação."
            ))
        if not self.equipment_ids:
            raise UserError(_("Selecione ao menos um equipamento."))

        # Revalidação no momento da execução: outra aba/sessão pode ter gerado
        # OS para parte da seleção depois que este wizard foi aberto.
        pendentes = so.equipamentos_sem_os_ids
        ja_gerados = self.equipment_ids - pendentes
        if ja_gerados:
            raise UserError(_(
                "Estes equipamentos já têm OS nesta cotação: %s"
            ) % ", ".join(ja_gerados.mapped("display_name")))

        lines = so._pending_qualif_lines().filtered(
            lambda l: l.equipment_id in self.equipment_ids
        )
        if not lines:
            raise UserError(_(
                "Nenhuma linha de qualificação pendente para os equipamentos "
                "selecionados."
            ))

        os = self.env["afr.qualificacao.os"].create(
            so._prepare_qualificacao_os_values(self.equipment_ids, pendentes)
        )
        so._materialize_qualificacoes(lines, os)
        return {
            "type": "ir.actions.act_window",
            "name": os.display_name,
            "res_model": "afr.qualificacao.os",
            "res_id": os.id,
            "view_mode": "form",
            "target": "current",
        }
