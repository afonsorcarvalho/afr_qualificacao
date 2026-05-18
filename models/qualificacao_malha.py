"""Sub-record de malha individual dentro de uma qualificação tipo Calibração.

Uma linha SO "Malha Temperatura qty=5" gera 5 registros `afr.qualificacao.malha`
(sequence 1..5), permitindo rastreio individual passed/failed por malha.

Integração engc.calibration (Opção A — manual):
- `engc_calibration_measurement_id` linka manualmente cada malha a uma
  `engc.calibration.measurement` (que contém os pontos de medição com
  cálculo de incerteza/erro/Veff via framework metrológico existente).
- `measurement_point_ids` é O2M related read-only mostrando pontos
  (30°C, 60°C, 90°C...) editados no form da engc.calibration.
"""

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoMalha(models.Model):
    """Malha individual executada em uma qualificação Calibração."""

    _name = "afr.qualificacao.malha"
    _description = "Malha de Calibração"
    _order = "qualificacao_id, malha_type_id, sequence, id"

    qualificacao_id = fields.Many2one(
        comodel_name="afr.qualificacao",
        string="Qualificação",
        required=True,
        ondelete="cascade",
    )
    malha_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.malha.type",
        string="Tipo de Malha",
        required=True,
    )
    sensor_kind_id = fields.Many2one(
        related="malha_type_id.sensor_kind_id",
        store=True,
        readonly=True,
    )
    sale_order_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Linha do Pedido",
        ondelete="set null",
    )
    sequence = fields.Integer(
        default=10,
        help="Ordem da malha dentro do mesmo tipo (1..N para qty=N).",
    )
    sensor_serial = fields.Char(
        string="Nº de Série do Instrumento",
        help="Identificação do instrumento de medição usado nesta malha.",
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pendente"),
            ("collected", "Coletado"),
            ("certified", "Certificado"),
            ("failed", "Reprovado"),
        ],
        default="pending",
        required=True,
        help=(
            "Pendente: aguardando coleta. "
            "Coletado: dados coletados e calibração vinculada. "
            "Certificado: calibração concluída (engc.calibration.state=done). "
            "Reprovado: marcado manualmente após análise."
        ),
    )
    executed_date = fields.Date(string="Data de Execução")
    notes = fields.Text()

    # ------------------------------------------------------------------
    # Integração engc.calibration (Opção A — link manual)
    # ------------------------------------------------------------------
    engc_calibration_measurement_id = fields.Many2one(
        comodel_name="engc.calibration.measurement",
        string="Medição engc.calibration",
        ondelete="set null",
        help=(
            "Link manual com a medição (engc.calibration.measurement) que "
            "contém os pontos de medição e cálculos metrológicos desta malha."
        ),
    )
    measurement_point_ids = fields.One2many(
        related="engc_calibration_measurement_id.measurement_lines",
        string="Pontos de Medição",
        readonly=True,
        help=(
            "Pontos (30°C, 60°C, 90°C...) editados no form da "
            "engc.calibration. Aqui apresentados read-only para conferência."
        ),
    )
    measurement_unit = fields.Char(
        related="engc_calibration_measurement_id.unit_of_measurement.simbolo",
        string="Unidade",
        readonly=True,
    )

    # F4.8 — coletas só via relatório
    relatorio_id = fields.Many2one(
        "afr.qualificacao.os.relatorio",
        string="Relatório que coletou",
        ondelete="set null",
        index=True,
    )
    collected_without_relatorio = fields.Boolean(
        compute="_compute_collected_without_relatorio",
        store=False,
    )

    @api.depends("state", "relatorio_id")
    def _compute_collected_without_relatorio(self):
        for r in self:
            r.collected_without_relatorio = (
                r.state in ("collected", "certified", "failed") and not r.relatorio_id
            )

    @api.onchange("state")
    def _onchange_state_auto_relatorio(self):
        ctx_rel = self.env.context.get("default_relatorio_id")
        for r in self:
            if r.state in ("collected", "certified", "failed"):
                if ctx_rel and not r.relatorio_id:
                    r.relatorio_id = ctx_rel
                if not r.executed_date:
                    r.executed_date = fields.Date.today()
            else:
                r.relatorio_id = False
                r.executed_date = False

    @api.onchange("engc_calibration_measurement_id")
    def _onchange_measurement_auto_collected(self):
        """F4.8: vincular measurement = malha coletada (state=collected)."""
        ctx_rel = self.env.context.get("default_relatorio_id")
        for r in self:
            if r.engc_calibration_measurement_id:
                if r.state == "pending":
                    r.state = "collected"
                if not r.executed_date:
                    r.executed_date = fields.Date.today()
                if ctx_rel and not r.relatorio_id:
                    r.relatorio_id = ctx_rel

    @api.model_create_multi
    def create(self, vals_list):
        ctx_rel = self.env.context.get("default_relatorio_id")
        for vals in vals_list:
            if ctx_rel and vals.get("state") in ("passed", "failed") and not vals.get("relatorio_id"):
                vals["relatorio_id"] = ctx_rel
        return super().create(vals_list)

    def write(self, vals):
        ctx_rel = self.env.context.get("default_relatorio_id")
        # F4.8: vincular measurement = auto state=collected
        if vals.get("engc_calibration_measurement_id") and not vals.get("state"):
            if any(r.state == "pending" for r in self):
                vals["state"] = "collected"
        if vals.get("state") in ("collected", "certified", "failed"):
            if ctx_rel and "relatorio_id" not in vals:
                vals["relatorio_id"] = ctx_rel
            vals.setdefault("executed_date", fields.Date.today())
        if vals.get("state") == "pending":
            vals["relatorio_id"] = False
            vals["executed_date"] = False
        return super().write(vals)

    def action_open_for_collect(self):
        """F4.8: abre form da malha em edit com relatorio pre-setado."""
        self.ensure_one()
        rel_id = self.env.context.get("attach_to_relatorio_id")
        ctx = dict(self.env.context)
        if rel_id:
            ctx["default_relatorio_id"] = rel_id
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": "afr.qualificacao.malha",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": ctx,
        }

    def action_create_engc_calibration(self):
        """F4.8: cria engc.calibration auto-vinculada a esta malha.

        Popula campos required a partir da qualif/OS:
        - client_id ← qualif.partner_id
        - equipment_id ← qualif.equipment_id
        - technician_id ← os.tecnico_default_id
        - instruments_ids ← qualif.standard_instrument_ids (agregado das coletas)
        - measurement_procedure ← primeiro procedure cadastrado
        - environmental_conditions ← placeholder "A definir"

        Se faltam pré-requisitos (técnico, instrumentos, procedimento) levanta
        UserError com orientação.
        """
        self.ensure_one()
        if self.engc_calibration_measurement_id:
            cal = self.engc_calibration_measurement_id.calibration_id
            return {
                "type": "ir.actions.act_window",
                "name": cal.display_name,
                "res_model": "engc.calibration",
                "res_id": cal.id,
                "view_mode": "form",
                "target": "current",
            }
        qualif = self.qualificacao_id
        os = qualif.os_id
        technician_id = os.tecnico_default_id.id if os else False
        if not technician_id:
            raise UserError(_(
                "Defina o Técnico Padrão na OS de Qualificação antes de criar "
                "a calibração."
            ))
        # F4.9 fix: busca instrumentos em ordem de fallback
        # 1. Padrões agregados na própria qualif (collect.items)
        instruments = qualif.standard_instrument_ids
        # 2. Padrões agregados em qualifs irmãs da mesma OS
        if not instruments and os:
            instruments = os.qualificacao_ids.mapped("standard_instrument_ids")
        # 3. Padrões do sistema cobrindo a grandeza desta malha
        if not instruments and self.sensor_kind_id:
            instruments = self.env["engc.calibration.instruments"].search([])
            instruments = instruments.filtered(
                lambda i: self.sensor_kind_id in i.sensor_kind_ids
            )
        if not instruments:
            raise UserError(_(
                "Nenhum Padrão Metrológico disponível. Cadastre instrumentos "
                "em Qualificações → Configurações → Padrões Metrológicos com "
                "certificado cobrindo a grandeza '%s' (mapear unidade → "
                "Grandeza AFR), ou vincule um padrão em alguma coleta desta "
                "qualificação."
            ) % (self.sensor_kind_id.name or "?"))
        procedure = self.env["engc.calibration.measurement.procedure"].search(
            [], limit=1
        )
        if not procedure:
            raise UserError(_(
                "Nenhum Procedimento/Norma de Calibração cadastrado em "
                "engc_os. Cadastre antes de criar a calibração."
            ))
        today = fields.Date.today()
        cal = self.env["engc.calibration"].create({
            "client_id": qualif.partner_id.id,
            "equipment_id": qualif.equipment_id.id,
            "technician_id": technician_id,
            "date_calibration": today,
            "date_next_calibration": today + relativedelta(years=1),
            "measurement_procedure": procedure.id,
            "instruments_ids": [(6, 0, instruments.ids)],
            "environmental_conditions": "A definir",
        })
        rel_id = self.env.context.get("attach_to_relatorio_id")
        if rel_id and not self.relatorio_id:
            self.relatorio_id = rel_id
        # Marca malha como passed e vincula (técnico ajusta no form da cal)
        # NOTA: não cria measurement automaticamente — técnico deve criar
        # pontos de medição no form da engc.calibration e depois vincular
        # manualmente em engc_calibration_measurement_id.
        return {
            "type": "ir.actions.act_window",
            "name": _("Calibração %s") % cal.name,
            "res_model": "engc.calibration",
            "res_id": cal.id,
            "view_mode": "form",
            "target": "current",
        }

    def name_get(self):
        result = []
        for r in self:
            seq = (r.sequence // 10) if r.sequence else 0
            type_name = r.malha_type_id.name or ""
            sensor = r.malha_type_id.sensor_kind_id.name or ""
            if type_name and sensor:
                label = "%s (%s) #%s" % (type_name, sensor, seq)
            elif type_name:
                label = "%s #%s" % (type_name, seq)
            else:
                label = "Malha #%s" % seq
            result.append((r.id, label))
        return result
