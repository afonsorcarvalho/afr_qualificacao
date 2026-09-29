# -*- coding: utf-8 -*-
"""Wizard para aplicar/re-aplicar procedimento a qualifs de uma OS.

Útil quando:
- OS criada sem procedimento (não havia template adequado no momento)
- User quer aplicar procedimento alternativo a algumas qualifs específicas
- Procedimento foi atualizado e quer-se regenerar items pendentes

Uma OS pode misturar categorias de equipamento (autoclave a vapor, ETO,
seladora...), cada uma com seu próprio procedimento (afr.qualificacao.
procedimento.resolve_for). Por isso o wizard resolve o procedimento default
POR LINHA (por qualificação) em vez de um único procedimento de cabeçalho
aplicado indiscriminadamente a todas as qualifs selecionadas.
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
    line_ids = fields.One2many(
        "afr.qualificacao.os.apply.procedimento.wizard.line",
        "wizard_id",
        string="Qualificações alvo",
    )
    overwrite_existing = fields.Boolean(
        string="Substituir itens existentes do procedimento",
        default=False,
        help="Se True, apaga TODOS os collect.items derivados de procedimento "
             "(procedimento_item_id preenchido) da qualificação antes de criar "
             "os novos — de qualquer procedimento de origem, não só o "
             "selecionado. Evita duplicar coletas ao trocar de procedimento. "
             "Bloqueado (UserError) se algum desses itens já estiver "
             "coletado (state=collected): dado coletado nunca é apagado "
             "silenciosamente.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "line_ids" not in fields_list:
            return res

        os_id = res.get("os_id")
        if not os_id and self.env.context.get("active_model") == "afr.qualificacao.os":
            os_id = self.env.context.get("active_id")
        if not os_id:
            return res

        os = self.env["afr.qualificacao.os"].browse(os_id)
        Procedimento = self.env["afr.qualificacao.procedimento"]
        lines = []
        for qualif in os.qualificacao_ids:
            proc = Procedimento.with_company(qualif.company_id).resolve_for(
                qualif.equipment_id.category_id
            )
            lines.append((0, 0, {
                "qualificacao_id": qualif.id,
                "procedimento_id": proc.id if proc else False,
            }))
        res["line_ids"] = lines
        return res

    def action_apply(self):
        self.ensure_one()
        selected = self.line_ids.filtered("selected")
        if not selected:
            raise UserError(_("Selecione ao menos uma qualificação."))

        # ── validação prévia (server-side; o domain do campo só protege a UI) ──
        for line in selected:
            if not line.procedimento_id:
                raise UserError(
                    _("Selecione um procedimento para a qualificação '%s'.")
                    % line.qualificacao_id.display_name
                )
            proc_cat = line.procedimento_id.equipment_category_id
            qualif_cat = line.qualificacao_id.equipment_id.category_id
            if proc_cat and proc_cat != qualif_cat:
                raise UserError(
                    _("Procedimento '%(proc)s' é específico da categoria "
                      "'%(proc_cat)s', incompatível com a qualificação "
                      "'%(qualif)s' (categoria '%(qualif_cat)s').") % {
                        "proc": line.procedimento_id.name,
                        "proc_cat": proc_cat.name,
                        "qualif": line.qualificacao_id.display_name,
                        "qualif_cat": qualif_cat.name if qualif_cat else _("(sem categoria)"),
                    }
                )
            if self.overwrite_existing:
                collected = line.qualificacao_id.collect_item_ids.filtered(
                    lambda c: c.procedimento_item_id and c.state == "collected"
                )
                if collected:
                    raise UserError(
                        _("Qualificação '%s' já tem item(ns) coletado(s) "
                          "derivados de procedimento — não é possível "
                          "substituir sem perder dado coletado.")
                        % line.qualificacao_id.display_name
                    )

        # ── mutação (só depois de validar todas as linhas selecionadas) ──
        total = 0
        for line in selected:
            qualif = line.qualificacao_id
            if self.overwrite_existing:
                existing = qualif.collect_item_ids.filtered(
                    lambda c: c.procedimento_item_id
                )
                existing.unlink()
            total += line.procedimento_id._explode_into(
                qualif, phase=qualif.qualification_type
            )

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


class AfrQualificacaoOsApplyProcedimentoWizardLine(models.TransientModel):
    _name = "afr.qualificacao.os.apply.procedimento.wizard.line"
    _description = "Linha do wizard Aplicar Procedimento: qualif + procedimento"

    wizard_id = fields.Many2one(
        "afr.qualificacao.os.apply.procedimento.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(default=True)
    qualificacao_id = fields.Many2one(
        "afr.qualificacao",
        required=True,
    )
    equipment_id = fields.Many2one(
        related="qualificacao_id.equipment_id",
        readonly=True,
    )
    equipment_category_id = fields.Many2one(
        related="qualificacao_id.equipment_id.category_id",
        readonly=True,
    )
    qualification_type = fields.Selection(
        related="qualificacao_id.qualification_type",
        readonly=True,
    )
    state = fields.Selection(
        related="qualificacao_id.state",
        readonly=True,
    )
    company_id = fields.Many2one(
        related="qualificacao_id.company_id",
        readonly=True,
        help="Auxiliar apenas para o domain client-side de procedimento_id.",
    )
    procedimento_id = fields.Many2one(
        "afr.qualificacao.procedimento",
        string="Procedimento a aplicar",
        domain="[('active', '=', True), ('company_id', '=', company_id), "
               "'|', ('equipment_category_id', '=', False), "
               "('equipment_category_id', '=', equipment_category_id)]",
    )
