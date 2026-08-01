# -*- coding: utf-8 -*-
"""Wizard: gerar OS de Qualificação por grupo de equipamentos.

Uma cotação confirmada pode render N OS — tipicamente uma por visita de campo
(setor, andar, disponibilidade do cliente). Cada execução cria uma OS nova com
o subconjunto de equipamentos escolhido que ainda não tem OS; repete-se até
não sobrar pendente.

Exceção: se um equipamento selecionado JÁ TEM OS nesta cotação (ex.: um
opcional dele foi aceito depois que outra OS já o cobriu), a linha nova cai
DENTRO da OS existente do equipamento em vez de abrir uma OS nova — é o único
jeito de manter a invariante abaixo sem deixar o serviço vendido sem OS.

Invariante: um equipamento nunca entra em duas OS da mesma cotação. Garantida
aqui (domínio + revalidação + roteamento p/ OS existente) e no modelo
(`afr.qualificacao._check_equipamento_unico_por_os_da_so`).
"""
from collections import defaultdict

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

        # Um equipamento selecionado pode já ter OS nesta cotação (ex.: um
        # opcional dele foi aceito depois que outra OS já o cobriu — ver
        # `_compute_equipamentos_sem_os`, que o recoloca no pool de
        # pendentes de propósito). Nesse caso a linha nova precisa cair
        # DENTRO da OS existente do equipamento, nunca numa OS nova —
        # senão a constraint de equipamento único por OS da cotação
        # (`afr.qualificacao._check_equipamento_unico_por_os_da_so`)
        # rejeita a criação e o clique vira um dead-end sem saída pela UI.
        # sudo(): record rule não pode esconder uma qualificação irmã e
        # reabrir o dead-end (mesmo argumento de `_next_free_qualificacao_os_name`).
        qualifs_existentes = self.env["afr.qualificacao"].sudo().search([
            ("sale_order_id", "=", so.id),
            ("equipment_id", "in", self.equipment_ids.ids),
            ("os_id", "!=", False),
        ])
        os_por_equipamento = {
            q.equipment_id.id: q.os_id for q in qualifs_existentes
        }

        lines_os_existente = lines.filtered(
            lambda l: l.equipment_id.id in os_por_equipamento
        )
        lines_os_nova = lines - lines_os_existente

        os_afetadas = self.env["afr.qualificacao.os"]
        por_os_existente = defaultdict(lambda: self.env["sale.order.line"])
        for line in lines_os_existente:
            por_os_existente[os_por_equipamento[line.equipment_id.id]] |= line
        for os_existente, grupo in por_os_existente.items():
            so._materialize_qualificacoes(grupo, os_existente)
            os_afetadas |= os_existente

        os_nova = self.env["afr.qualificacao.os"]
        if lines_os_nova:
            os_nova = self.env["afr.qualificacao.os"].create(
                so._prepare_qualificacao_os_values(self.equipment_ids, pendentes)
            )
            so._materialize_qualificacoes(lines_os_nova, os_nova)

        if os_nova:
            return {
                "type": "ir.actions.act_window",
                "name": os_nova.display_name,
                "res_model": "afr.qualificacao.os",
                "res_id": os_nova.id,
                "view_mode": "form",
                "target": "current",
            }
        if len(os_afetadas) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": os_afetadas.display_name,
                "res_model": "afr.qualificacao.os",
                "res_id": os_afetadas.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("OS de Qualificação Afetadas"),
            "res_model": "afr.qualificacao.os",
            "view_mode": "tree,form",
            "domain": [("id", "in", os_afetadas.ids)],
        }
