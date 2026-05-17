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

from odoo import fields, models


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
            ("passed", "Aprovado"),
            ("failed", "Reprovado"),
        ],
        default="pending",
        required=True,
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
