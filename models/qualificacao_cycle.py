"""Sub-record de ciclo individual dentro de uma qualificação tipo Desempenho (QD).

Uma linha SO "Ciclo Carga Máxima qty=3" gera 3 registros `afr.qualificacao.cycle`
(sequence 1..3), permitindo ao técnico marcar cada ciclo individual como
passed/failed em campo. `qty_delivered` na linha SO = count(state='passed').
"""

from odoo import _, api, fields, models


class AfrQualificacaoCycle(models.Model):
    """Ciclo individual executado em uma qualificação QD."""

    _name = "afr.qualificacao.cycle"
    _description = "Ciclo de Qualificação QD"
    _order = "qualificacao_id, cycle_type_id, sequence, id"

    qualificacao_id = fields.Many2one(
        comodel_name="afr.qualificacao",
        string="Qualificação",
        required=True,
        ondelete="cascade",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo",
        required=True,
    )
    sale_order_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Linha do Pedido",
        ondelete="set null",
        help="Linha SO que originou este ciclo (rastreio comercial).",
    )
    sequence = fields.Integer(
        default=10,
        help="Ordem do ciclo dentro do mesmo tipo (1..N para qty=N).",
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pendente"),
            ("passed", "Aprovado"),
            ("failed", "Reprovado"),
        ],
        default="pending",
        required=True,
    )
    executed_date = fields.Date(string="Data de Execução")
    notes = fields.Text()

    # F4.9 — agregação de coletas: cycle = wrapper de collect.items via cycle_id
    collect_item_ids = fields.One2many(
        "afr.qualificacao.collect.item",
        "cycle_id",
        string="Coletas do Ciclo",
    )
    collects_total = fields.Integer(
        compute="_compute_collect_progress",
        store=True,
    )
    collects_done = fields.Integer(
        compute="_compute_collect_progress",
        store=True,
    )
    collects_progress = fields.Char(
        compute="_compute_collect_progress",
        store=True,
        string="Progresso",
        help="Coletas required collected / total required do ciclo.",
    )
    collects_complete = fields.Boolean(
        compute="_compute_collect_progress",
        store=True,
        string="Todas coletas feitas",
    )

    @api.depends(
        "collect_item_ids.state",
        "collect_item_ids.required",
    )
    def _compute_collect_progress(self):
        for r in self:
            required_items = r.collect_item_ids.filtered("required")
            total = len(required_items)
            done = len(required_items.filtered(lambda c: c.state == "collected"))
            r.collects_total = total
            r.collects_done = done
            r.collects_progress = "%d/%d" % (done, total)
            r.collects_complete = total > 0 and done == total

    def _sync_state_from_collects(self):
        """F4.9: ajusta cycle.state e relatorio_id baseado nas coletas.

        - Todas required collected → state=passed (se pending) + relatorio do último
        - Alguma required pending → state=pending + limpa relatorio
        - state=failed permanece (técnico marcou manual, não sobrescreve)
        """
        for r in self:
            if r.state == "failed":
                continue  # respeita decisão manual
            required_items = r.collect_item_ids.filtered("required")
            if not required_items:
                continue
            done = required_items.filtered(lambda c: c.state == "collected")
            if len(done) == len(required_items):
                if r.state == "pending":
                    last_rel = done.sorted("captured_at", reverse=True).mapped("relatorio_id")
                    rel = last_rel[:1]
                    vals = {"state": "passed"}
                    if rel and not r.relatorio_id:
                        vals["relatorio_id"] = rel.id
                    if not r.executed_date:
                        vals["executed_date"] = fields.Date.today()
                    r.write(vals)
            else:
                if r.state == "passed":
                    r.write({
                        "state": "pending",
                        "relatorio_id": False,
                        "executed_date": False,
                    })

    # F4.8 — coletas só via relatório
    relatorio_id = fields.Many2one(
        "afr.qualificacao.os.relatorio",
        string="Relatório que coletou",
        ondelete="set null",
        index=True,
        help="Relatório no qual este ciclo foi materializado (state≠pending).",
    )
    collected_without_relatorio = fields.Boolean(
        compute="_compute_collected_without_relatorio",
        store=False,
    )

    @api.depends("state", "relatorio_id")
    def _compute_collected_without_relatorio(self):
        for r in self:
            r.collected_without_relatorio = (
                r.state in ("passed", "failed") and not r.relatorio_id
            )

    @api.onchange("state")
    def _onchange_state_auto_relatorio(self):
        ctx_rel = self.env.context.get("default_relatorio_id")
        for r in self:
            if r.state in ("passed", "failed"):
                if ctx_rel and not r.relatorio_id:
                    r.relatorio_id = ctx_rel
                if not r.executed_date:
                    r.executed_date = fields.Date.today()
            else:
                # pending: limpa vínculo
                r.relatorio_id = False
                r.executed_date = False

    def action_open_for_collect(self):
        """F4.8: abre form do ciclo em edit com relatorio pre-setado."""
        self.ensure_one()
        rel_id = self.env.context.get("attach_to_relatorio_id")
        ctx = dict(self.env.context)
        if rel_id:
            ctx["default_relatorio_id"] = rel_id
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": "afr.qualificacao.cycle",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": ctx,
        }

    @api.model_create_multi
    def create(self, vals_list):
        ctx_rel = self.env.context.get("default_relatorio_id")
        for vals in vals_list:
            if ctx_rel and vals.get("state") in ("passed", "failed") and not vals.get("relatorio_id"):
                vals["relatorio_id"] = ctx_rel
        return super().create(vals_list)

    def write(self, vals):
        ctx_rel = self.env.context.get("default_relatorio_id")
        if vals.get("state") in ("passed", "failed"):
            if ctx_rel and "relatorio_id" not in vals:
                vals["relatorio_id"] = ctx_rel
            vals.setdefault("executed_date", fields.Date.today())
        if vals.get("state") == "pending":
            vals["relatorio_id"] = False
            vals["executed_date"] = False
        return super().write(vals)

    def name_get(self):
        result = []
        for r in self:
            seq = (r.sequence // 10) if r.sequence else 0
            type_name = r.cycle_type_id.name or ""
            label = "%s #%s" % (type_name, seq) if type_name else "Ciclo #%s" % seq
            result.append((r.id, label))
        return result
