# -*- coding: utf-8 -*-
"""Ordem de Serviço de Qualificação (afr.qualificacao.os).

Container hierárquico das qualificações: 1 OS = N equipamentos × N tipos
qualif. Substitui engc.os no fluxo quote-first de qualificação.

F1 (16.0.3.0.0): modelos OS + relatório + workflow.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AfrQualificacaoOs(models.Model):
    _name = "afr.qualificacao.os"
    _description = "Ordem de Serviço de Qualificação"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name desc, id desc"

    # ───────── Identificação ─────────
    name = fields.Char(
        string="Referência",
        readonly=True,
        copy=False,
        default=lambda self: _("Novo"),
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        compute="_compute_partner_id",
        store=True,
        readonly=True,
        tracking=True,
    )

    # ───────── Origem comercial ─────────
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Pedido de venda",
        copy=False,
        ondelete="set null",
        index=True,
        tracking=True,
    )

    # ───────── Equipe ─────────
    tecnico_default_id = fields.Many2one(
        "hr.employee",
        string="Técnico padrão",
        tracking=True,
        help="Técnico padrão da OS. Pode ser sobrescrito em cada qualificação.",
    )
    approver_id = fields.Many2one(
        "res.users",
        string="Aprovador",
        tracking=True,
    )

    # ───────── Cronograma ─────────
    date_planned_start = fields.Datetime(
        string="Início planejado",
        tracking=True,
    )
    date_planned_end = fields.Datetime(
        string="Fim planejado",
        tracking=True,
    )
    duration_planned = fields.Float(
        string="Duração planejada (h)",
        compute="_compute_duration_planned",
        store=True,
        help="date_planned_end − date_planned_start em horas.",
    )
    date_actual_start = fields.Datetime(
        string="Início real",
        compute="_compute_actual_times",
        store=True,
        readonly=True,
        help="Mínimo das datas de início dos relatórios não cancelados.",
    )
    date_actual_end = fields.Datetime(
        string="Fim real",
        compute="_compute_actual_times",
        store=True,
        readonly=True,
        help="Máximo das datas de fim dos relatórios não cancelados.",
    )
    duration_actual = fields.Float(
        string="Duração real (h)",
        compute="_compute_actual_times",
        store=True,
        readonly=True,
        help="Soma de time_execution dos relatórios não cancelados.",
    )

    # ───────── Workflow ─────────
    STATE_SELECTION = [
        ("draft", "Rascunho"),
        ("scheduled", "Agendada"),
        ("in_progress", "Em execução"),
        ("in_approved", "Aguardando aprovação"),
        ("approved", "Aprovada"),
        ("done", "Concluída"),
        ("cancelled", "Cancelada"),
    ]
    state = fields.Selection(
        STATE_SELECTION,
        default="draft",
        required=True,
        tracking=True,
        group_expand="_group_expand_states",
    )

    # ───────── Relações ─────────
    qualificacao_ids = fields.One2many(
        "afr.qualificacao",
        "os_id",
        string="Qualificações",
    )
    qualificacao_count = fields.Integer(
        compute="_compute_qualificacao_counts",
    )
    qualificacao_done_count = fields.Integer(
        compute="_compute_qualificacao_counts",
        string="Qualif aprovadas",
    )
    equipment_ids = fields.Many2many(
        "engc.equipment",
        compute="_compute_equipment_ids",
        store=True,
        compute_sudo=True,
        string="Equipamentos",
    )
    equipment_count = fields.Integer(
        compute="_compute_equipment_ids",
        compute_sudo=True,
    )
    relatorio_ids = fields.One2many(
        "afr.qualificacao.os.relatorio",
        "os_id",
        string="Relatórios parciais",
    )
    relatorio_count = fields.Integer(
        compute="_compute_relatorio_count",
    )

    # ───────── Assinaturas ─────────
    signature_technician = fields.Image(
        string="Assinatura técnico",
        max_width=512,
        max_height=512,
    )
    signature_supervisor = fields.Image(
        string="Assinatura supervisor",
        max_width=512,
        max_height=512,
    )
    signature_technician_date = fields.Datetime(readonly=True)
    signature_supervisor_date = fields.Datetime(readonly=True)

    # ═════════════════════════════════════════════════════════════
    # CREATE OVERRIDE — sequence
    # ═════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Novo"):
                seq = self.env["ir.sequence"].with_company(
                    vals.get("company_id") or self.env.company.id
                ).next_by_code("afr.qualificacao.os.sequence")
                vals["name"] = seq or _("Novo")
        return super().create(vals_list)

    # ═════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ═════════════════════════════════════════════════════════════
    @api.depends("qualificacao_ids.partner_id")
    def _compute_partner_id(self):
        for r in self:
            partners = r.qualificacao_ids.mapped("partner_id")
            r.partner_id = partners[:1]

    @api.depends("date_planned_start", "date_planned_end")
    def _compute_duration_planned(self):
        for r in self:
            if r.date_planned_start and r.date_planned_end:
                delta = r.date_planned_end - r.date_planned_start
                r.duration_planned = delta.total_seconds() / 3600.0
            else:
                r.duration_planned = 0.0

    @api.depends(
        "relatorio_ids.data_inicio",
        "relatorio_ids.data_fim",
        "relatorio_ids.time_execution",
        "relatorio_ids.state",
    )
    def _compute_actual_times(self):
        for r in self:
            ativos = r.relatorio_ids.filtered(lambda x: x.state != "cancel")
            starts = ativos.mapped("data_inicio")
            ends = ativos.mapped("data_fim")
            r.date_actual_start = min(starts) if starts else False
            r.date_actual_end = max(ends) if ends else False
            r.duration_actual = sum(ativos.mapped("time_execution"))

    @api.depends("qualificacao_ids", "qualificacao_ids.state")
    def _compute_qualificacao_counts(self):
        for r in self:
            r.qualificacao_count = len(r.qualificacao_ids)
            r.qualificacao_done_count = len(
                r.qualificacao_ids.filtered(lambda q: q.state == "approved")
            )

    @api.depends("qualificacao_ids.equipment_id")
    def _compute_equipment_ids(self):
        for r in self:
            equips = r.qualificacao_ids.mapped("equipment_id")
            r.equipment_ids = equips
            r.equipment_count = len(equips)

    @api.depends("relatorio_ids")
    def _compute_relatorio_count(self):
        for r in self:
            r.relatorio_count = len(r.relatorio_ids)

    def _group_expand_states(self, states, domain, order):
        """Mostra todos os estados no kanban mesmo se vazios."""
        return [s[0] for s in self.STATE_SELECTION]

    # ═════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═════════════════════════════════════════════════════════════
    @api.constrains("date_planned_start", "date_planned_end")
    def _check_planned_dates(self):
        for r in self:
            if (
                r.date_planned_start
                and r.date_planned_end
                and r.date_planned_end < r.date_planned_start
            ):
                raise ValidationError(
                    _("Fim planejado deve ser ≥ início planejado.")
                )

    # ═════════════════════════════════════════════════════════════
    # WORKFLOW ACTIONS
    # ═════════════════════════════════════════════════════════════
    def action_schedule(self):
        """draft → scheduled"""
        for r in self:
            if r.state != "draft":
                raise UserError(_("Só é possível agendar OS em rascunho."))
            if not r.qualificacao_ids:
                raise UserError(
                    _("OS sem qualificações. Confirme o pedido de venda primeiro.")
                )
            if not r.date_planned_start or not r.date_planned_end:
                raise UserError(
                    _("Preencha datas planejadas antes de agendar.")
                )
            if not r.tecnico_default_id:
                missing = r.qualificacao_ids.filtered(lambda q: not q.responsible_id)
                if missing:
                    raise UserError(
                        _("Defina um técnico padrão OU responsável em cada qualificação. "
                          "Sem responsável: %s") % ", ".join(missing.mapped("name"))
                    )
            r.write({"state": "scheduled"})
        return True

    def action_start_execution(self):
        """scheduled → in_progress (abre wizard de novo relatório)."""
        self.ensure_one()
        if self.state not in ("scheduled", "in_progress"):
            raise UserError(
                _("OS deve estar agendada ou em execução para iniciar relatório.")
            )
        if self.state == "scheduled":
            self.write({"state": "in_progress"})
        # Abre wizard de novo relatório
        return self.action_open_new_relatorio_wizard()

    def action_open_new_relatorio_wizard(self):
        """Abre wizard transient para criar novo relatório parcial."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Novo relatório parcial"),
            "res_model": "afr.qualificacao.os.relatorio.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_os_id": self.id,
                "default_data_inicio": fields.Datetime.now(),
            },
        }

    def action_request_approval(self):
        """in_progress → in_approved"""
        for r in self:
            if r.state != "in_progress":
                raise UserError(
                    _("Só é possível solicitar aprovação de OS em execução.")
                )
            # Valida que nenhum relatório está draft
            drafts = r.relatorio_ids.filtered(lambda x: x.state == "draft")
            if drafts:
                raise UserError(
                    _("Existem %d relatórios pendentes (em rascunho). "
                      "Conclua todos antes de solicitar aprovação.") % len(drafts)
                )
            # Bloqueia se ∃ qualif em estado rejected
            rejected = r.qualificacao_ids.filtered(lambda q: q.state == "rejected")
            if rejected:
                raise UserError(
                    _("Existem qualificações rejeitadas: %s. "
                      "Corrija ou cancele a OS antes de aprovar.")
                    % ", ".join(rejected.mapped("name"))
                )
            r.write({"state": "in_approved"})
        return True

    def action_approve(self):
        """in_approved → approved (manager-only via groups XML)."""
        for r in self:
            if r.state != "in_approved":
                raise UserError(
                    _("Só é possível aprovar OS aguardando aprovação.")
                )
            # Cascata: aprovar qualifs em in_progress (não as rejected/cancelled)
            for q in r.qualificacao_ids.filtered(
                lambda x: x.state in ("draft", "in_progress")
            ):
                if q.state == "draft":
                    q.action_start()  # draft → in_progress (método existente)
                q.action_mark_approved()  # in_progress → approved + certificado
            r.write({"state": "approved"})
        return True

    def action_done(self):
        """approved → done"""
        for r in self:
            if r.state != "approved":
                raise UserError(
                    _("Só é possível concluir OS aprovada.")
                )
            if not r.signature_technician:
                raise UserError(
                    _("Assinatura do técnico é obrigatória para concluir.")
                )
            # Assinatura supervisor opcional mas recomendada (warning via log apenas)
            pendentes = r.qualificacao_ids.filtered(
                lambda q: q.state != "approved"
            )
            if pendentes:
                raise UserError(
                    _("Existem qualificações não aprovadas: %s.")
                    % ", ".join(pendentes.mapped("name"))
                )
            r.write({"state": "done"})
        return True

    def action_cancel(self):
        """qualquer → cancelled"""
        for r in self:
            if r.state == "done":
                raise UserError(
                    _("Não é possível cancelar OS concluída. Use estorno.")
                )
            r.write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        """cancelled → draft (rare, manager-only via view groups=)"""
        for r in self:
            if r.state != "cancelled":
                raise UserError(_("Só OS cancelada pode voltar para rascunho."))
            r.write({"state": "draft"})
        return True

    # ═════════════════════════════════════════════════════════════
    # SIGNATURE TRACKING
    # ═════════════════════════════════════════════════════════════
    def write(self, vals):
        if "signature_technician" in vals and vals["signature_technician"]:
            vals["signature_technician_date"] = fields.Datetime.now()
        if "signature_supervisor" in vals and vals["signature_supervisor"]:
            vals["signature_supervisor_date"] = fields.Datetime.now()
        return super().write(vals)

    # ═════════════════════════════════════════════════════════════
    # STAT BUTTON ACTIONS
    # ═════════════════════════════════════════════════════════════
    def action_view_qualificacoes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Qualificações"),
            "res_model": "afr.qualificacao",
            "view_mode": "tree,form",
            "domain": [("os_id", "=", self.id)],
            "context": {"default_os_id": self.id},
        }

    def action_view_relatorios(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Relatórios parciais"),
            "res_model": "afr.qualificacao.os.relatorio",
            "view_mode": "tree,form",
            "domain": [("os_id", "=", self.id)],
            "context": {"default_os_id": self.id},
        }

    def action_view_equipamentos(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Equipamentos"),
            "res_model": "engc.equipment",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.equipment_ids.ids)],
        }
