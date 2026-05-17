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
        for r in self:
            if r.file and r.state == "pending":
                r.state = "collected"
                r.captured_at = fields.Datetime.now()
                r.captured_by = self.env.user

    @api.constrains("state", "file", "required")
    def _check_required_has_file(self):
        for r in self:
            if r.state == "collected" and not r.file:
                raise ValidationError(
                    _("Item '%s' marcado como coletado precisa ter arquivo anexado.")
                    % r.name
                )

    def write(self, vals):
        # Se file preenchido via write e estava pending, marca collected
        if vals.get("file") and not vals.get("state"):
            for r in self:
                if r.state == "pending":
                    vals.setdefault("captured_at", fields.Datetime.now())
                    vals.setdefault("captured_by", self.env.user.id)
                    if not vals.get("state"):
                        vals["state"] = "collected"
                    break  # vals applied to all in self
        return super().write(vals)

    def action_mark_skipped(self):
        for r in self:
            r.write({"state": "skipped"})
        return True

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
