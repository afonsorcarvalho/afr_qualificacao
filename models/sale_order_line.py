"""Extensão de sale.order.line para suportar fluxo de qualificação quote-first.

Linhas SO geradas pelo wizard configurador carregam metadados técnicos
(equipment_id, qualification_type, cycle_type_id/malha_type_id) que são
usados em SO confirm para gerar `afr.qualificacao` + `engc.os` + sub-records.

`is_qualificacao_managed=True` marca linhas criadas pelo wizard, permitindo
distinguir de linhas manuais (preservadas em re-apply do wizard).
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_qualificacao_managed = fields.Boolean(
        string="Gerenciado por Qualificação",
        default=False,
        copy=False,
        help=(
            "Marca linhas criadas pelo wizard Configurador de Qualificações. "
            "Re-apply do wizard apaga/recria apenas linhas managed (preserva "
            "linhas avulsas adicionadas manualmente)."
        ),
    )
    qualification_type = fields.Selection(
        selection=[
            ("installation", "Instalação (QI)"),
            ("operational", "Operacional (QO)"),
            ("performance", "Desempenho (QD)"),
            ("software", "Software (QS)"),
            ("calibration", "Calibração"),
        ],
        string="Tipo de Qualificação",
        copy=False,
    )
    equipment_id = fields.Many2one(
        comodel_name="engc.equipment",
        string="Equipamento",
        copy=False,
        help="Equipamento associado a esta linha de qualificação.",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo (QD)",
        copy=False,
    )
    malha_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.malha.type",
        string="Tipo de Malha (Calib)",
        copy=False,
    )
    afr_qualificacao_id = fields.Many2one(
        comodel_name="afr.qualificacao",
        string="Qualificação Gerada",
        copy=False,
        ondelete="set null",
        help="Qualificação criada ao confirmar este SO.",
    )
    cycle_ids = fields.One2many(
        comodel_name="afr.qualificacao.cycle",
        inverse_name="sale_order_line_id",
        string="Ciclos Gerados",
    )
    malha_ids = fields.One2many(
        comodel_name="afr.qualificacao.malha",
        inverse_name="sale_order_line_id",
        string="Malhas Geradas",
    )

    @api.constrains(
        "is_qualificacao_managed",
        "qualification_type",
        "equipment_id",
        "cycle_type_id",
        "malha_type_id",
    )
    def _check_qualificacao_consistency(self):
        for line in self:
            if not line.is_qualificacao_managed:
                continue
            if not line.equipment_id:
                raise ValidationError(_(
                    "Linha de qualificação requer equipamento."
                ))
            if not line.qualification_type:
                raise ValidationError(_(
                    "Linha de qualificação requer tipo de qualificação."
                ))
            if line.qualification_type == "performance" and not line.cycle_type_id:
                raise ValidationError(_(
                    "QD (Desempenho) requer Tipo de Ciclo na linha."
                ))
            if line.qualification_type == "calibration" and not line.malha_type_id:
                raise ValidationError(_(
                    "Calibração requer Tipo de Malha na linha."
                ))

    @api.onchange("product_id")
    def _onchange_product_id_clear_qualif_meta(self):
        """Se user troca produto direto na tab Order Lines, limpa metadata.

        Evita estado stale: trocar produto sem passar pelo wizard significa
        que a linha não é mais managed. Limpa flags + tipos + warning.
        """
        warning = None
        if self.is_qualificacao_managed and (
            self.cycle_type_id or self.malha_type_id
        ):
            warning = {
                "title": _("Linha de qualificação modificada"),
                "message": _(
                    "Você trocou o produto de uma linha gerenciada pelo "
                    "configurador. Os metadados de qualificação foram limpos "
                    "e a linha não será mais gerenciada pelo wizard."
                ),
            }
            self.is_qualificacao_managed = False
            self.qualification_type = False
            self.cycle_type_id = False
            self.malha_type_id = False
        if warning:
            return {"warning": warning}
