# -*- coding: utf-8 -*-
"""Wizard para aplicar/re-aplicar procedimento a qualifs de uma OS.

Útil quando:
- OS criada sem procedimento (não havia template adequado no momento)
- User quer aplicar procedimento alternativo a algumas qualifs específicas
- Procedimento foi atualizado e quer-se regenerar items pendentes
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoOsApplyProcedimentoWizard(models.TransientModel):
    _name = "afr.qualificacao.os.apply.procedimento.wizard"
    _description = "Wizard: aplicar procedimento a qualifs da OS"

    os_id = fields.Many2one(
        "afr.qualificacao.os",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    procedimento_id = fields.Many2one(
        "afr.qualificacao.procedimento",
        required=True,
        string="Procedimento a aplicar",
        domain="[('active', '=', True)]",
    )
    qualificacao_ids = fields.Many2many(
        "afr.qualificacao",
        relation="afr_qualif_apply_proc_wizard_qualif_rel",
        column1="wizard_id",
        column2="qualif_id",
        required=True,
        string="Qualificações alvo",
        domain="[('os_id', '=', os_id)]",
    )
    overwrite_existing = fields.Boolean(
        string="Substituir itens existentes do procedimento",
        default=False,
        help="Se True, apaga collect.items vinculados ao mesmo procedimento.item "
             "antes de criar novos. Útil para re-aplicar após atualização do template.",
    )

    @api.onchange("os_id")
    def _onchange_os_default_qualifs(self):
        if self.os_id:
            self.qualificacao_ids = [(6, 0, self.os_id.qualificacao_ids.ids)]

    def action_apply(self):
        self.ensure_one()
        if not self.qualificacao_ids:
            raise UserError(_("Selecione ao menos uma qualificação."))
        Item = self.env["afr.qualificacao.collect.item"]
        total = 0
        for qualif in self.qualificacao_ids:
            # Filtra qualifs incompatíveis com o tipo aplicável do procedimento
            if qualif.qualification_type != self.procedimento_id.applicable_qualification_type:
                continue
            if self.overwrite_existing:
                existing = qualif.collect_item_ids.filtered(
                    lambda c: c.procedimento_item_id in self.procedimento_id.item_ids
                )
                existing.unlink()
            total += self._explode_for_qualif(Item, qualif, self.procedimento_id)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Procedimento aplicado"),
                "message": _("%d itens de coleta criados.") % total,
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _explode_for_qualif(self, Item, qualif, procedimento):
        """Cria N collect.items conforme target_level de cada procedimento.item."""
        created = 0
        for pi in procedimento.item_ids:
            base_vals = {
                "name": pi.name,
                "sequence": pi.sequence,
                "kind": pi.kind,
                "required": pi.required,
                "instruction": pi.instruction,
                "procedimento_item_id": pi.id,
                "qualif_id": qualif.id,
            }
            if pi.target_level == "qualificacao":
                Item.create(base_vals)
                created += 1
            elif pi.target_level == "cycle":
                for cycle in qualif.cycle_ids:
                    vals = dict(base_vals)
                    vals["cycle_id"] = cycle.id
                    vals["name"] = _("%s — Ciclo %d") % (pi.name, cycle.sequence)
                    Item.create(vals)
                    created += 1
            elif pi.target_level == "malha":
                for malha in qualif.malha_ids:
                    vals = dict(base_vals)
                    vals["malha_id"] = malha.id
                    vals["name"] = _("%s — Malha %d") % (pi.name, malha.sequence)
                    Item.create(vals)
                    created += 1
        return created
