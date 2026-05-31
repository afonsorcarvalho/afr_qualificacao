# -*- coding: utf-8 -*-
"""Ordem de Serviço de Qualificação (afr.qualificacao.os).

Container hierárquico das qualificações: 1 OS = N equipamentos × N tipos
qualif. Substitui engc.os no fluxo quote-first de qualificação.

F1 (16.0.3.0.0): modelos OS + relatório + workflow.
"""
from collections import OrderedDict, defaultdict

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
    # F3 (16.0.3.2.0): coletas explodidas do procedimento por qualif/cycle/malha
    collect_item_ids = fields.One2many(
        "afr.qualificacao.collect.item",
        "os_id",
        string="Itens de coleta",
    )
    collect_total_count = fields.Integer(
        compute="_compute_collect_counts",
    )
    collect_pending_count = fields.Integer(
        compute="_compute_collect_counts",
        help="Itens required ainda pendentes.",
    )
    collect_collected_count = fields.Integer(
        compute="_compute_collect_counts",
    )

    # ───────── F10 — Plano de recursos metrológicos ─────────
    resource_plan_line_ids = fields.One2many(
        "afr.qualificacao.resource.plan.line",
        "os_id",
        string="Plano de Recursos",
        copy=False,
    )
    resource_plan_dirty = fields.Boolean(
        string="Plano Desatualizado",
        default=False,
        copy=False,
        help=(
            "True quando a OS mudou (ciclos, malhas, grupos paralelos) desde "
            "o último cálculo do plano de recursos. Recalcule."
        ),
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

    @api.depends(
        "collect_item_ids",
        "collect_item_ids.state",
        "collect_item_ids.required",
    )
    def _compute_collect_counts(self):
        for r in self:
            r.collect_total_count = len(r.collect_item_ids)
            r.collect_collected_count = len(
                r.collect_item_ids.filtered(lambda c: c.state == "collected")
            )
            r.collect_pending_count = len(
                r.collect_item_ids.filtered(
                    lambda c: c.required and c.state == "pending"
                )
            )

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
            # Warning não-bloqueante: coletas required pendentes
            if r.collect_pending_count:
                r.message_post(
                    body=_("⚠ %d itens de coleta obrigatórios ainda pendentes. "
                           "Aprovação solicitada mesmo assim.") % r.collect_pending_count,
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

    def action_view_collect_items(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Coletas / Checklist"),
            "res_model": "afr.qualificacao.collect.item",
            "view_mode": "kanban,tree,form",
            "domain": [("os_id", "=", self.id)],
            "context": {"default_qualif_id": False, "search_default_group_kind": 1},
        }

    def action_apply_procedimento(self):
        """Abre wizard para aplicar/re-aplicar procedimento a qualifs."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Aplicar Procedimento"),
            "res_model": "afr.qualificacao.os.apply.procedimento.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_os_id": self.id},
        }

    # ═════════════════════════════════════════════════════════════
    # F10 — Plano de recursos metrológicos (bin-packing)
    # ═════════════════════════════════════════════════════════════
    # Papel do plano → code da tag afr.qualificacao.instrument.function.
    _RESOURCE_ROLE_FUNCTION_CODE = {
        "validador": "VALIDADOR",
        "padrao": "PADRAO",
    }

    def action_compute_resource_plan(self):
        """Regenera o plano de recursos da OS (bin-packing).

        Demanda lida dos SUB-RECORDS reais (ciclos QD, malhas, snapshot de
        pontos QD). Preserva linhas com is_overridden=True. Limpa o flag dirty.
        """
        for os in self:
            os._compute_resource_plan()
            os.resource_plan_dirty = False
        return True

    # ---- instrumentos -------------------------------------------------
    def _instrument_capacity(self, instrument):
        """{sensor_kind: canais} a partir de measurement_capacity_ids."""
        return {
            c.sensor_kind_id: c.qty
            for c in instrument.measurement_capacity_ids
            if c.qty > 0
        }

    def _available_instruments(self, role, sensor_kind=None):
        """Instrumentos com papel `role`, certificado válido e (opcional)
        capacidade na grandeza `sensor_kind`."""
        code = self._RESOURCE_ROLE_FUNCTION_CODE[role]
        Instr = self.env["engc.calibration.instruments"]
        candidates = Instr.search([("function_ids.code", "=", code)])
        result = []
        for instr in candidates:
            if not instr.has_valid_certificate:
                continue
            cap = self._instrument_capacity(instr)
            if sensor_kind is not None and cap.get(sensor_kind, 0) <= 0:
                continue
            result.append(instr)
        return result

    def _bin_pack_validators(self, instruments, needed):
        """Greedy multidimensional: conjunto mínimo de instrumentos cobrindo
        `needed` (grandeza→canais). Prefere caixa única. Retorna
        (chosen_list, remaining_dict)."""
        remaining = {k: v for k, v in needed.items() if v > 0}
        pool = list(instruments)
        chosen = []
        guard = 0
        while any(v > 0 for v in remaining.values()) and pool:
            best, best_score = None, 0
            for instr in pool:
                cap = self._instrument_capacity(instr)
                score = sum(
                    min(cap.get(k, 0), remaining[k]) for k in remaining
                )
                if score > best_score:
                    best, best_score = instr, score
            if not best or best_score <= 0:
                break
            chosen.append(best)
            pool.remove(best)
            cap = self._instrument_capacity(best)
            for k in list(remaining):
                remaining[k] = max(0, remaining[k] - cap.get(k, 0))
            guard += 1
            if guard > 200:
                break
        return chosen, remaining

    # ---- demanda (dos sub-records reais) ------------------------------
    def _cycle_hours(self, cycle):
        """Horas de 1 ciclo QD: override da linha SO, senão do cycle_type."""
        line = cycle.sale_order_line_id
        return (
            (line.estimated_hours if line else 0.0)
            or cycle.cycle_type_id.estimated_hours
            or 0.0
        )

    def _malha_hours(self, malha):
        """Horas de 1 malha: override da linha SO, senão do malha_type.

        NOTA: o record afr.qualificacao.malha não tem horas próprias —
        "campo próprio da malha" resolve p/ malha_type.estimated_hours."""
        line = malha.sale_order_line_id
        return (
            (line.estimated_hours if line else 0.0)
            or malha.malha_type_id.estimated_hours
            or 0.0
        )

    def _resource_demand_by_equipment(self):
        """Demanda por equipamento, a partir dos sub-records reais da OS.

        Retorna OrderedDict {equipment: {qd_points, qd_hours, malha_simul,
        malha_hours, group, has_qd}}.
        """
        self.ensure_one()
        demand = OrderedDict()
        for qualif in self.qualificacao_ids:
            eq = qualif.equipment_id
            if not eq:
                continue
            d = demand.setdefault(eq, {
                "qd_points": defaultdict(int),
                "qd_hours": 0.0,
                "malha_simul": defaultdict(int),
                "malha_hours": defaultdict(float),
                "group": "",
                "has_qd": False,
            })
            if qualif.parallel_group and not d["group"]:
                d["group"] = qualif.parallel_group.strip()
            if qualif.qualification_type == "performance":
                d["has_qd"] = d["has_qd"] or bool(qualif.cycle_ids)
                for s in qualif.qd_point_snapshot_ids:
                    d["qd_points"][s.sensor_kind_id] += s.points
                for cyc in qualif.cycle_ids:
                    d["qd_hours"] += self._cycle_hours(cyc)
            elif qualif.qualification_type == "calibration":
                # Dentro de 1 equip as malhas rodam sequencialmente → demanda
                # simultânea por grandeza = máx de standards_per_malha.
                for malha in qualif.malha_ids:
                    kind = malha.malha_type_id.sensor_kind_id
                    spm = malha.malha_type_id.standards_per_malha or 1
                    d["malha_simul"][kind] = max(d["malha_simul"][kind], spm)
                    d["malha_hours"][kind] += self._malha_hours(malha) * spm
        return demand

    # ---- rotina principal --------------------------------------------
    def _compute_resource_plan(self):
        """Bin-packing único: demanda dos sub-records → grupos paralelos →
        frota de validadores/padrões + horas wall-clock."""
        self.ensure_one()
        Line = self.env["afr.qualificacao.resource.plan.line"]

        overridden = self.resource_plan_line_ids.filtered("is_overridden")
        (self.resource_plan_line_ids - overridden).unlink()

        demand = self._resource_demand_by_equipment()
        equipments = list(demand.keys())

        # Agrupa por parallel_group (vazio = singleton).
        groups = OrderedDict()
        solo = 0
        for eq in equipments:
            g = demand[eq]["group"]
            if g:
                groups.setdefault(g, []).append(eq)
            else:
                groups["\x00solo%d" % solo] = [eq]
                solo += 1

        # Validadores: capacidade necessária + janelas por grupo.
        cap_needed = defaultdict(int)
        group_window = {}
        group_qd_kinds = {}
        for gkey, eqs in groups.items():
            gsum = defaultdict(int)
            for eq in eqs:
                for kind, pts in demand[eq]["qd_points"].items():
                    gsum[kind] += pts
            for kind, total in gsum.items():
                cap_needed[kind] = max(cap_needed[kind], total)
            group_window[gkey] = max(
                (demand[eq]["qd_hours"] for eq in eqs), default=0.0
            )
            group_qd_kinds[gkey] = {k for k, v in gsum.items() if v > 0}

        for ov in overridden.filtered(
            lambda l: l.resource_role == "validador" and l.instrument_id
        ):
            for kind, q in self._instrument_capacity(ov.instrument_id).items():
                if kind in cap_needed:
                    cap_needed[kind] = max(0, cap_needed[kind] - q)
        cap_needed = {k: v for k, v in cap_needed.items() if v > 0}

        # Padrões: nº simultâneo por grandeza + horas.
        std_needed = defaultdict(int)
        std_groups = defaultdict(set)
        std_hours = defaultdict(float)
        for gkey, eqs in groups.items():
            gsum = defaultdict(int)
            for eq in eqs:
                for kind, simul in demand[eq]["malha_simul"].items():
                    gsum[kind] += simul
                for kind, h in demand[eq]["malha_hours"].items():
                    std_hours[kind] += h
                    std_groups[kind].add(gkey)
            for kind, total in gsum.items():
                std_needed[kind] = max(std_needed[kind], total)
        for ov in overridden.filtered(
            lambda l: l.resource_role == "padrao" and l.sensor_kind_id
        ):
            k = ov.sensor_kind_id
            if k in std_needed:
                std_needed[k] = max(0, std_needed[k] - 1)
        std_needed = {k: v for k, v in std_needed.items() if v > 0}

        vals_list = []
        validator_equips = [eq for eq in equipments if demand[eq]["qd_points"]]

        # --- validadores ---
        if cap_needed:
            instruments = self._available_instruments("validador")
            chosen, remaining = self._bin_pack_validators(
                instruments, cap_needed
            )
            for instr in chosen:
                cap = self._instrument_capacity(instr)
                served = [g for g in groups if group_qd_kinds[g] & set(cap)]
                hours = sum(
                    group_window[g] + instr.setup_hours for g in served
                )
                used = {
                    k: min(cap.get(k, 0), cap_needed.get(k, 0))
                    for k in cap_needed if cap.get(k, 0) > 0
                }
                vals_list.append({
                    "os_id": self.id,
                    "resource_role": "validador",
                    "instrument_id": instr.id,
                    "equipment_ids": [(6, 0, [e.id for e in validator_equips])],
                    "channels_used": sum(used.values()),
                    "channels_capacity": sum(cap.values()),
                    "coverage_summary": ", ".join(
                        "%s×%d" % (k.name, used[k]) for k in used
                    ),
                    "hours_resource_usage": hours,
                })
            leftover = {k: v for k, v in remaining.items() if v > 0}
            if leftover:
                vals_list.append({
                    "os_id": self.id,
                    "resource_role": "validador",
                    "equipment_ids": [(6, 0, [e.id for e in validator_equips])],
                    "channels_used": sum(leftover.values()),
                    "coverage_summary": ", ".join(
                        "%s×%d" % (k.name, v) for k, v in leftover.items()
                    ),
                    "note": _("Sem instrumento validador disponível p/ a demanda."),
                })

        # equipamentos com ciclo QD mas sem snapshot (template ausente)
        for eq in equipments:
            if demand[eq]["has_qd"] and not demand[eq]["qd_points"]:
                vals_list.append({
                    "os_id": self.id,
                    "resource_role": "validador",
                    "equipment_ids": [(6, 0, [eq.id])],
                    "note": _(
                        "Equipamento %s sem pontos QD (snapshot ausente)."
                    ) % (eq.display_name or eq.id),
                })

        # --- padrões ---
        for kind, n in std_needed.items():
            instruments = self._available_instruments("padrao", kind)
            chosen, acc = [], 0
            for instr in instruments:
                if acc >= n:
                    break
                chosen.append(instr)
                acc += max(1, self._instrument_capacity(instr).get(kind, 0))
            ngroups = len(std_groups[kind])
            per = std_hours[kind] / n if n else 0.0
            equips_kind = [
                eq for eq in equipments if kind in demand[eq]["malha_hours"]
            ]
            for i in range(n):
                instr = chosen[i] if i < len(chosen) else False
                hours = per + (instr.setup_hours if instr else 0.0) * ngroups
                vals = {
                    "os_id": self.id,
                    "resource_role": "padrao",
                    "sensor_kind_id": kind.id,
                    "equipment_ids": [(6, 0, [e.id for e in equips_kind])],
                    "coverage_summary": kind.name,
                    "hours_resource_usage": hours,
                }
                if instr:
                    vals["instrument_id"] = instr.id
                else:
                    vals["note"] = _(
                        "Sem instrumento padrão disponível p/ %s."
                    ) % kind.name
                vals_list.append(vals)

        if vals_list:
            Line.create(vals_list)
