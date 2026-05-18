# -*- coding: utf-8 -*-
"""Relatório parcial da OS de qualificação (afr.qualificacao.os.relatorio).

Cada relatório registra um intervalo de execução (técnico, datas, descrição,
ciclos/malhas cobertos). Os campos `date_actual_*` e `duration_actual` da OS
são computados a partir dos relatórios não cancelados.

F1 (16.0.3.0.0): modelo base + workflow + cálculo tempo.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AfrQualificacaoOsRelatorio(models.Model):
    _name = "afr.qualificacao.os.relatorio"
    _description = "Relatório parcial de OS de qualificação"
    _inherit = ["mail.thread"]
    _order = "data_inicio desc, id desc"

    # ───────── Identificação ─────────
    name = fields.Char(
        string="Referência",
        readonly=True,
        copy=False,
        default=lambda self: _("Novo"),
        tracking=True,
    )
    os_id = fields.Many2one(
        "afr.qualificacao.os",
        string="Ordem de serviço",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        related="os_id.company_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Rascunho"),
            ("done", "Concluído"),
            ("cancel", "Cancelado"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    # ───────── Intervalo ─────────
    data_inicio = fields.Datetime(
        string="Início",
        required=True,
        tracking=True,
    )
    data_fim = fields.Datetime(
        string="Fim",
        required=True,
        tracking=True,
    )
    time_execution = fields.Float(
        string="Tempo (h)",
        compute="_compute_time_execution",
        store=True,
        help="(data_fim − data_inicio) em horas.",
    )

    # ───────── Equipe ─────────
    tecnico_ids = fields.Many2many(
        "hr.employee",
        relation="afr_qualif_os_relatorio_tecnico_rel",
        column1="relatorio_id",
        column2="employee_id",
        string="Técnicos",
        required=True,
        tracking=True,
    )

    # ───────── Conteúdo ─────────
    descricao = fields.Text(
        string="Descrição do serviço",
        required=True,
        tracking=True,
    )
    observacoes = fields.Text(string="Observações")

    # ───────── Cobertura técnica ─────────
    # F1: M2M sem filtro dinâmico por OS (qualif.os_id chega em F2).
    # F2: adicionar domain=[('qualificacao_id.os_id', '=', os_id)]
    cycle_ids = fields.Many2many(
        "afr.qualificacao.cycle",
        relation="afr_qualif_os_relatorio_cycle_rel",
        column1="relatorio_id",
        column2="cycle_id",
        string="Ciclos cobertos",
    )
    malha_ids = fields.Many2many(
        "afr.qualificacao.malha",
        relation="afr_qualif_os_relatorio_malha_rel",
        column1="relatorio_id",
        column2="malha_id",
        string="Malhas cobertas",
    )

    # F4.7 (16.0.3.4.0): coletas realizadas neste relatório
    collect_item_ids = fields.One2many(
        "afr.qualificacao.collect.item",
        "relatorio_id",
        string="Coletas realizadas",
        help="Itens de coleta materializados neste relatório (state=collected).",
    )
    pending_collect_item_ids = fields.Many2many(
        "afr.qualificacao.collect.item",
        compute="_compute_pending_collect_items",
        store=False,
        string="Coletas pendentes da OS",
        help="Coletas required ainda em state=pending na OS deste relatório.",
    )
    # F4.8 (16.0.3.4.0): ciclos/malhas coletados neste relatório
    cycles_collected_ids = fields.One2many(
        "afr.qualificacao.cycle",
        "relatorio_id",
        string="Ciclos coletados",
    )
    malhas_collected_ids = fields.One2many(
        "afr.qualificacao.malha",
        "relatorio_id",
        string="Malhas coletadas",
    )
    pending_cycles_ids = fields.Many2many(
        "afr.qualificacao.cycle",
        compute="_compute_pending_subrecords",
        store=False,
        string="Ciclos pendentes da OS",
    )
    pending_malhas_ids = fields.Many2many(
        "afr.qualificacao.malha",
        compute="_compute_pending_subrecords",
        store=False,
        string="Malhas pendentes da OS",
    )
    pending_collect_count = fields.Integer(
        compute="_compute_pending_collect_items", store=False,
    )
    pending_cycles_count = fields.Integer(
        compute="_compute_pending_subrecords", store=False,
    )
    pending_malhas_count = fields.Integer(
        compute="_compute_pending_subrecords", store=False,
    )

    @api.depends("os_id",
                 "os_id.qualificacao_ids.cycle_ids.state",
                 "os_id.qualificacao_ids.malha_ids.state")
    def _compute_pending_subrecords(self):
        for r in self:
            if not r.os_id:
                r.pending_cycles_ids = False
                r.pending_malhas_ids = False
                r.pending_cycles_count = 0
                r.pending_malhas_count = 0
                continue
            cycles = r.os_id.qualificacao_ids.mapped("cycle_ids")
            malhas = r.os_id.qualificacao_ids.mapped("malha_ids")
            pending_c = cycles.filtered(lambda c: c.state == "pending")
            # F4.10: malha sai de "Pendentes" só quando certificada
            pending_m = malhas.filtered(lambda m: m.state != "certified")
            r.pending_cycles_ids = pending_c
            r.pending_malhas_ids = pending_m
            r.pending_cycles_count = len(pending_c)
            r.pending_malhas_count = len(pending_m)

    @api.depends("os_id", "os_id.qualificacao_ids.collect_item_ids.state",
                 "os_id.qualificacao_ids.collect_item_ids.required")
    def _compute_pending_collect_items(self):
        for r in self:
            if not r.os_id:
                r.pending_collect_item_ids = False
                r.pending_collect_count = 0
                continue
            all_items = r.os_id.qualificacao_ids.mapped("collect_item_ids")
            pending = all_items.filtered(
                lambda c: c.required and c.state == "pending"
            )
            r.pending_collect_item_ids = pending
            r.pending_collect_count = len(pending)

    def action_open_pending_collects(self):
        """Abre lista de collect.items pendentes da OS em modo edit.
        Context auto-vincula `relatorio_id` ao registro aberto.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Coletas Pendentes — %s") % (self.name or ""),
            "res_model": "afr.qualificacao.collect.item",
            "view_mode": "tree,form",
            "domain": [
                ("os_id", "=", self.os_id.id),
                ("required", "=", True),
                ("state", "=", "pending"),
            ],
            "context": {
                "default_relatorio_id": self.id,
                "default_required": True,
            },
            "target": "current",
        }

    def action_open_pending_cycles(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Ciclos Pendentes — %s") % (self.name or ""),
            "res_model": "afr.qualificacao.cycle",
            "view_mode": "tree,form",
            "domain": [
                ("qualificacao_id.os_id", "=", self.os_id.id),
                ("state", "=", "pending"),
            ],
            "context": {"default_relatorio_id": self.id},
            "target": "current",
        }

    def action_open_pending_malhas(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Malhas Pendentes — %s") % (self.name or ""),
            "res_model": "afr.qualificacao.malha",
            "view_mode": "tree,form",
            "domain": [
                ("qualificacao_id.os_id", "=", self.os_id.id),
                ("state", "=", "pending"),
            ],
            "context": {"default_relatorio_id": self.id},
            "target": "current",
        }

    def action_open_collected_items(self):
        """Abre lista de collect.items deste relatório (já coletados)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Coletas — %s") % (self.name or ""),
            "res_model": "afr.qualificacao.collect.item",
            "view_mode": "tree,form",
            "domain": [("relatorio_id", "=", self.id)],
            "context": {"default_relatorio_id": self.id},
            "target": "current",
        }

    # ═════════════════════════════════════════════════════════════
    # CREATE OVERRIDE — sequence
    # ═════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Novo"):
                seq = self.env["ir.sequence"].next_by_code(
                    "afr.qualificacao.os.relatorio.sequence"
                )
                vals["name"] = seq or _("Novo")
        return super().create(vals_list)

    # ═════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ═════════════════════════════════════════════════════════════
    @api.depends("data_inicio", "data_fim")
    def _compute_time_execution(self):
        for r in self:
            if r.data_inicio and r.data_fim:
                delta = r.data_fim - r.data_inicio
                r.time_execution = max(delta.total_seconds() / 3600.0, 0.0)
            else:
                r.time_execution = 0.0

    # ═════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═════════════════════════════════════════════════════════════
    @api.constrains("data_inicio", "data_fim")
    def _check_dates(self):
        for r in self:
            if r.data_inicio and r.data_fim and r.data_fim < r.data_inicio:
                raise ValidationError(
                    _("Data fim deve ser ≥ data início no relatório %s.") % r.name
                )

    # ═════════════════════════════════════════════════════════════
    # WORKFLOW
    # ═════════════════════════════════════════════════════════════
    def action_done(self):
        for r in self:
            if r.state != "draft":
                raise UserError(_("Só é possível concluir relatório em rascunho."))
            if not r.descricao or not r.descricao.strip():
                raise UserError(_("Descrição do serviço é obrigatória."))
            if r.time_execution <= 0:
                raise UserError(
                    _("Tempo de execução deve ser > 0 (verifique datas).")
                )
            if not r.tecnico_ids:
                raise UserError(_("Informe ao menos um técnico."))
            r.write({"state": "done"})
        return True

    def action_cancel(self):
        for r in self:
            r.write({"state": "cancel"})
        return True

    def action_reopen(self):
        """done|cancel → draft (manager-only via view groups=)."""
        for r in self:
            if r.state not in ("done", "cancel"):
                raise UserError(_("Só relatórios concluídos/cancelados podem reabrir."))
            r.write({"state": "draft"})
        return True
