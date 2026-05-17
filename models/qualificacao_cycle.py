"""Sub-record de ciclo individual dentro de uma qualificação tipo Desempenho (QD).

Uma linha SO "Ciclo Carga Máxima qty=3" gera 3 registros `afr.qualificacao.cycle`
(sequence 1..3), permitindo ao técnico marcar cada ciclo individual como
passed/failed em campo. `qty_delivered` na linha SO = count(state='passed').
"""

from odoo import fields, models


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

    def name_get(self):
        result = []
        for r in self:
            seq = (r.sequence // 10) if r.sequence else 0
            type_name = r.cycle_type_id.name or ""
            label = "%s #%s" % (type_name, seq) if type_name else "Ciclo #%s" % seq
            result.append((r.id, label))
        return result
