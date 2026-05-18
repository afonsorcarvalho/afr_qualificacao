# -*- coding: utf-8 -*-
"""Item de Coleta (afr.qualificacao.collect.item) — checklist + anexo unificados.

Pendente (state=pending) = expectativa de coleta. Coletado (state=collected
+ file preenchido) = anexo materializado.

Hierarquia:
    qualif_id (required) — qualificação alvo
    cycle_id (opcional) — quando item explode por ciclo (target_level=cycle)
    malha_id (opcional) — quando item explode por malha (target_level=malha)
    relatorio_id (opcional) — sessão que coletou o item
    os_id (related) — denormalizado para search rápido
    equipment_id (related) — denormalizado
    procedimento_item_id (opcional) — origem do template
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .qualificacao_procedimento import KIND_SELECTION


class AfrQualificacaoCollectItem(models.Model):
    _name = "afr.qualificacao.collect.item"
    _description = "Item de Coleta (Checklist + Anexo)"
    _inherit = ["mail.thread"]
    _order = "qualif_id, sequence, id"

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        KIND_SELECTION,
        required=True,
        default="foto",
        string="Tipo de mídia",
    )
    required = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("pending", "Pendente"),
            ("collected", "Coletado"),
            ("skipped", "Pulado"),
        ],
        default="pending",
        required=True,
        tracking=True,
    )
    description = fields.Text()
    instruction = fields.Text(help="Instrução herdada do procedimento.item.")

    # Origem (template)
    procedimento_item_id = fields.Many2one(
        "afr.qualificacao.procedimento.item",
        string="Item do procedimento",
        ondelete="set null",
        index=True,
    )

    # Hierarquia
    qualif_id = fields.Many2one(
        "afr.qualificacao",
        required=True,
        ondelete="cascade",
        index=True,
        string="Qualificação",
    )
    cycle_id = fields.Many2one(
        "afr.qualificacao.cycle",
        ondelete="cascade",
        index=True,
        string="Ciclo (QD)",
    )
    malha_id = fields.Many2one(
        "afr.qualificacao.malha",
        ondelete="cascade",
        index=True,
        string="Malha (Calib)",
    )
    relatorio_id = fields.Many2one(
        "afr.qualificacao.os.relatorio",
        ondelete="set null",
        index=True,
        string="Relatório que coletou",
    )

    # Denormalizado (related stored para search/filtros)
    os_id = fields.Many2one(
        "afr.qualificacao.os",
        related="qualif_id.os_id",
        store=True,
        readonly=True,
        index=True,
    )
    equipment_id = fields.Many2one(
        "engc.equipment",
        related="qualif_id.equipment_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="qualif_id.company_id",
        store=True,
        readonly=True,
    )

    # Conteúdo (preenchido ao coletar)
    file = fields.Binary(attachment=True, string="Arquivo")
    filename = fields.Char()
    mimetype = fields.Char()
    captured_at = fields.Datetime(readonly=True)
    captured_by = fields.Many2one("res.users", readonly=True)

    # F4 (16.0.3.3.0): padrões metrológicos usados nesta coleta
    standard_instrument_ids = fields.Many2many(
        "engc.calibration.instruments",
        "afr_qualif_collect_item_instrument_rel",
        "collect_item_id",
        "instrument_id",
        string="Padrões Metrológicos",
        help=(
            "Instrumentos padrão (engc.calibration.instruments) utilizados "
            "para gerar este item de coleta. Cada instrumento traz "
            "certificados de calibração com data de validade."
        ),
    )
    standards_all_valid = fields.Boolean(
        compute="_compute_standards_validity",
        string="Padrões com certificado válido",
        store=False,
    )
    standards_warning_text = fields.Text(
        compute="_compute_standards_validity",
        string="Padrões sem certificado válido",
        store=False,
    )

    # F4.3 (16.0.3.4.0): exigência e cobertura de grandezas
    requires_instrument = fields.Boolean(
        related="procedimento_item_id.requires_instrument",
        store=True,
        readonly=True,
        string="Requer padrão",
    )
    required_sensor_kind_ids = fields.Many2many(
        "afr.qualificacao.sensor.kind",
        related="procedimento_item_id.required_sensor_kind_ids",
        readonly=True,
        string="Grandezas requeridas",
    )

    # F6.1 (16.0.3.5.0) — herdado do procedimento.item; editável caso a explosão
    # tenha vindo de procedimento legado sem docx_section setado.
    # Selection inferida do related (não declarar para evitar warning Odoo).
    docx_section = fields.Selection(
        related="procedimento_item_id.docx_section",
        store=True,
        readonly=False,
        string="Seção no relatório DOCX",
        help=(
            "Tabela do relatório DOCX onde esta coleta será listada. "
            "Herdado de procedimento.item.docx_section; pode ser ajustado."
        ),
    )
    coverage_complete = fields.Boolean(
        compute="_compute_coverage",
        store=False,
        string="Cobertura completa",
    )
    coverage_warning_text = fields.Text(
        compute="_compute_coverage",
        store=False,
        string="Grandezas sem padrão",
    )
    missing_sensor_kind_ids = fields.Many2many(
        "afr.qualificacao.sensor.kind",
        compute="_compute_coverage",
        store=False,
        string="Grandezas faltantes",
    )

    # F4.7 (16.0.3.4.0): coletas só devem ocorrer via relatório.
    collected_without_relatorio = fields.Boolean(
        compute="_compute_collected_without_relatorio",
        store=False,
        string="Coletado sem relatório",
    )

    @api.depends("state", "relatorio_id")
    def _compute_collected_without_relatorio(self):
        for r in self:
            r.collected_without_relatorio = (
                r.state == "collected" and not r.relatorio_id
            )

    @api.depends(
        "requires_instrument",
        "required_sensor_kind_ids",
        "standard_instrument_ids",
        "standard_instrument_ids.certificate_ids.uncertainty_lines.unit_of_measurement.afr_sensor_kind_id",
    )
    def _compute_coverage(self):
        for r in self:
            if not r.requires_instrument:
                r.coverage_complete = True
                r.coverage_warning_text = ""
                r.missing_sensor_kind_ids = False
                continue
            required = r.required_sensor_kind_ids
            if not required:
                # Requer instrumento mas sem grandezas específicas → exige >=1 padrão
                has_any = bool(r.standard_instrument_ids)
                r.coverage_complete = has_any
                r.coverage_warning_text = (
                    "" if has_any else _("Nenhum padrão metrológico selecionado.")
                )
                r.missing_sensor_kind_ids = False
                continue
            covered = r.standard_instrument_ids.mapped("sensor_kind_ids")
            missing = required - covered
            r.coverage_complete = not missing
            r.missing_sensor_kind_ids = missing
            r.coverage_warning_text = (
                ", ".join(missing.mapped("name")) if missing else ""
            )

    @api.depends(
        "standard_instrument_ids",
        "standard_instrument_ids.certificate_ids.validate_calibration",
    )
    def _compute_standards_validity(self):
        today = fields.Date.today()
        for r in self:
            invalid = []
            for inst in r.standard_instrument_ids:
                has_valid = any(
                    c.validate_calibration and c.validate_calibration >= today
                    for c in inst.certificate_ids
                )
                if not has_valid:
                    invalid.append(
                        inst.display_name
                        or inst.name
                        or inst.id_number
                        or _("Instrumento #%s") % inst.id
                    )
            r.standards_all_valid = not invalid
            r.standards_warning_text = ", ".join(invalid)

    @api.onchange("file")
    def _onchange_file_set_collected(self):
        ctx_relatorio = self.env.context.get("default_relatorio_id")
        for r in self:
            if r.file:
                if r.state == "pending":
                    r.state = "collected"
                    r.captured_at = fields.Datetime.now()
                    r.captured_by = self.env.user
                # Auto-link relatório do contexto (vindo da tab "Coletas Pendentes")
                if ctx_relatorio and not r.relatorio_id:
                    r.relatorio_id = ctx_relatorio
            else:
                # File removido: volta pending + limpa vínculo
                if r.state == "collected":
                    r.state = "pending"
                    r.captured_at = False
                    r.captured_by = False
                    r.relatorio_id = False

    @api.constrains("state", "file", "required")
    def _check_required_has_file(self):
        for r in self:
            if r.state == "collected" and not r.file:
                raise ValidationError(
                    _("Item '%s' marcado como coletado precisa ter arquivo anexado.")
                    % r.name
                )

    @api.model_create_multi
    def create(self, vals_list):
        ctx_rel = self.env.context.get("default_relatorio_id")
        for vals in vals_list:
            # Auto-link relatorio do context se vindo da tab Pendentes
            if vals.get("file") and not vals.get("relatorio_id") and ctx_rel:
                vals["relatorio_id"] = ctx_rel
            # Garante state + captured quando file vem preenchido na criação
            if vals.get("file"):
                vals.setdefault("state", "collected")
            if vals.get("state") == "collected":
                vals.setdefault("captured_at", fields.Datetime.now())
                vals.setdefault("captured_by", self.env.user.id)
        records = super().create(vals_list)
        # F4.9: trigger cycle sync para items criados já com cycle_id
        cycles = records.mapped("cycle_id")
        if cycles:
            cycles._sync_state_from_collects()
        return records

    def write(self, vals):
        ctx_rel = self.env.context.get("default_relatorio_id")

        # Auto-link relatorio do context (tab Coletas Pendentes do relatório)
        if vals.get("file") and not vals.get("relatorio_id") and ctx_rel:
            vals["relatorio_id"] = ctx_rel

        # File preenchido em registro pending → marca collected
        if vals.get("file") and not vals.get("state"):
            if any(r.state == "pending" for r in self):
                vals["state"] = "collected"

        # State vira collected (ou já é) → garante captured_at/by preenchidos
        becoming_collected = vals.get("state") == "collected" or (
            vals.get("file") and any(r.state == "collected" for r in self)
        )
        if becoming_collected:
            vals.setdefault("captured_at", fields.Datetime.now())
            vals.setdefault("captured_by", self.env.user.id)

        # File removido (vals["file"] is False explicitly): reverte tudo
        if "file" in vals and not vals.get("file"):
            vals["state"] = "pending"
            vals["captured_at"] = False
            vals["captured_by"] = False
            vals["relatorio_id"] = False

        res = super().write(vals)
        # F4.9: propagar mudança para cycle pai (auto-sync state baseado em coletas)
        if any(k in vals for k in ("state", "required", "cycle_id")):
            cycles = self.mapped("cycle_id")
            if cycles:
                cycles._sync_state_from_collects()
        return res

    def action_mark_skipped(self):
        for r in self:
            r.write({"state": "skipped"})
        return True

    def action_open_for_collect(self):
        """F4.7: abre form do collect.item em modo edit com relatorio
        pre-setado via context (vindo de `attach_to_relatorio_id`).
        Usado pelo botão 'Coletar' inline na tree pendentes do relatório.
        """
        self.ensure_one()
        rel_id = self.env.context.get("attach_to_relatorio_id")
        ctx = dict(self.env.context)
        if rel_id:
            ctx["default_relatorio_id"] = rel_id
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "afr.qualificacao.collect.item",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": ctx,
        }

    def action_reset_pending(self):
        for r in self:
            r.write({
                "state": "pending",
                "file": False,
                "filename": False,
                "captured_at": False,
                "captured_by": False,
            })
        return True
