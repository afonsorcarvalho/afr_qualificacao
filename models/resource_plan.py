"""F10 (16.0.5.0.0) — Plano de recursos metrológicos por OS de qualificação.

Sugere, a partir da OS de Qualificação (afr.qualificacao.os) e dos seus
sub-records reais (ciclos QD, malhas, snapshot de pontos QD), quantos
VALIDADORES (data loggers, por canais) e quantos PADRÕES de calibração (por
grandeza) serão necessários — além das HORAS de utilização de cada recurso
(wall-clock). Serve ao PCP/planejamento de campo.

Modelo `afr.qualificacao.resource.plan.line`: uma linha por recurso sugerido.
A lógica de geração (bin-packing) vive em
`afr.qualificacao.os.action_compute_resource_plan`.
"""

from odoo import api, fields, models


class AfrQualificacaoResourcePlanLine(models.Model):
    """Linha do plano de recursos metrológicos de uma OS de qualificação."""

    _name = "afr.qualificacao.resource.plan.line"
    _description = "Linha de Plano de Recursos Metrológicos"
    _order = "os_id, resource_role, sensor_kind_id, id"

    os_id = fields.Many2one(
        comodel_name="afr.qualificacao.os",
        string="OS de Qualificação",
        required=True,
        ondelete="cascade",
        index=True,
    )
    resource_role = fields.Selection(
        selection=[
            ("validador", "Validador (data logger)"),
            ("padrao", "Padrão de Calibração"),
        ],
        string="Papel",
        required=True,
    )
    instrument_id = fields.Many2one(
        comodel_name="engc.calibration.instruments",
        string="Instrumento Sugerido",
        ondelete="set null",
        help=(
            "Instrumento concreto sugerido pelo algoritmo. Vazio = recurso "
            "genérico (sem ativo disponível que cubra a demanda)."
        ),
    )
    equipment_ids = fields.Many2many(
        comodel_name="engc.equipment",
        relation="afr_resource_plan_equipment_rel",
        column1="plan_line_id",
        column2="equipment_id",
        string="Equipamentos Atendidos",
    )
    sensor_kind_id = fields.Many2one(
        comodel_name="afr.qualificacao.sensor.kind",
        string="Grandeza",
        help=(
            "Grandeza coberta. Para padrão = a grandeza calibrada; para "
            "validador multi-grandeza, ver 'Cobertura'."
        ),
    )
    coverage_summary = fields.Char(
        string="Cobertura",
        help="Resumo da cobertura por grandeza (ex.: 'Temp×12, Press×1').",
    )
    channels_used = fields.Integer(
        string="Canais Usados",
        help="Canais efetivamente alocados deste recurso (papel validador).",
    )
    channels_capacity = fields.Integer(
        string="Canais Disponíveis",
        help="Capacidade total de canais do recurso (papel validador).",
    )
    # UTILIZAÇÃO wall-clock do recurso. DISTINTO das horas FATURADAS na linha
    # do SO (product_uom_qty). NÃO somar nem confundir com aquelas.
    hours_resource_usage = fields.Float(
        string="Horas de Utilização",
        digits="Product Price",
        help=(
            "Horas wall-clock de uso do recurso (janelas dos grupos + setup). "
            "NÃO confundir com as horas FATURADAS na linha do SO."
        ),
    )
    equipment_count = fields.Integer(
        compute="_compute_equipment_count",
        string="Nº Equip.",
    )

    @api.depends("equipment_ids")
    def _compute_equipment_count(self):
        for r in self:
            r.equipment_count = len(r.equipment_ids)
    is_overridden = fields.Boolean(
        string="Ajustado Manualmente",
        help=(
            "Linha editada pelo técnico. Recompute do plano preserva linhas "
            "com este flag (não as apaga nem regenera)."
        ),
    )
    note = fields.Char(string="Observação")

    company_id = fields.Many2one(
        related="os_id.company_id",
        store=True,
        readonly=True,
    )

    def name_get(self):
        result = []
        role_labels = dict(self._fields["resource_role"].selection)
        for r in self:
            base = role_labels.get(r.resource_role, r.resource_role or "")
            if r.instrument_id:
                base = "%s — %s" % (base, r.instrument_id.display_name)
            elif r.sensor_kind_id:
                base = "%s (%s)" % (base, r.sensor_kind_id.name)
            result.append((r.id, base))
        return result
