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

    # Metadados qualif: copy=True para preservar configuração ao duplicar SO
    # (user pede que duplicação carregue equipamento+tipo+ciclo/malha). Apenas
    # `afr_qualificacao_id` permanece copy=False — qualificação é criada no
    # confirm do novo SO, não herdada do original.
    is_qualificacao_managed = fields.Boolean(
        string="Gerenciado por Qualificação",
        default=False,
        copy=True,
        help=(
            "Marca linhas criadas pelo wizard Configurador de Qualificações. "
            "Re-apply do wizard apaga/recria apenas linhas managed (preserva "
            "linhas avulsas adicionadas manualmente)."
        ),
    )
    is_proposal_optional = fields.Boolean(
        string="Serviço Opcional da Proposta",
        default=False,
        copy=True,
        help=(
            "Marca linhas de serviços opcionais (pasta, viagem, diária) "
            "geradas pelo configurador. São linhas managed para fins de "
            "re-apply, mas NÃO geram qualificação no confirm do SO."
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
        copy=True,
    )
    equipment_id = fields.Many2one(
        comodel_name="engc.equipment",
        string="Equipamento",
        copy=True,
        help="Equipamento associado a esta linha de qualificação.",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo (QD)",
        copy=True,
    )
    malha_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.malha.type",
        string="Tipo de Malha (Calib)",
        copy=True,
    )
    estimated_hours = fields.Float(
        string="Horas Estimadas",
        digits="Product Price",
        copy=True,
        help=(
            "Horas estimadas por execução desta linha (override do "
            "cycle_type/malha_type/type_config). Usado pelo cronograma."
        ),
    )
    work_hours_per_day = fields.Float(
        string="Jornada (h/dia)",
        default=8.0,
        help=(
            "Horas úteis/dia do equipamento (congelado da proposta; usado "
            "no cronograma). Editável."
        ),
    )
    qualif_cycle_qty = fields.Integer(
        string="Nº de Ciclos",
        copy=True,
        help=(
            "Número de ciclos/malhas a executar nesta linha. Dirige a "
            "explosão em afr.qualificacao.cycle/malha (coletas) e a "
            "quantidade exibida na proposta. NÃO confundir com "
            "product_uom_qty, que agora representa as HORAS faturadas "
            "(= qualif_cycle_qty × estimated_hours)."
        ),
    )
    part = fields.Selection(
        selection=[("01", "Parte 01"), ("02", "Parte 02")],
        string="Parte",
        copy=True,
        help=(
            "Parte da qualificação (QI/QO). Parte 01 = verificações "
            "(declinável); Parte 02 = calibrações (QI) / ciclos (QO)."
        ),
    )
    part01_declined = fields.Boolean(
        string="Parte 01 Não Solicitada",
        default=False,
        copy=True,
        help=(
            "Cliente não solicitou execução da Parte 01. A linha aparece na "
            "proposta com preço de referência e selo 'NÃO SOLICITADO "
            "EXECUÇÃO', mas não soma ao total (product_uom_qty=0)."
        ),
    )

    @api.onchange("qualif_cycle_qty", "estimated_hours")
    def _onchange_qualif_cycle_qty_hours(self):
        """Mantém product_uom_qty = nº ciclos × horas/ciclo (UdM em horas).

        Só atua em linhas de ciclo/malha (cycle_type_id/malha_type_id). Permite
        ao vendedor editar nº de ciclos OU horas/ciclo no SO e refletir as horas
        faturadas. Linhas QI/QS (sem ciclo) não são tocadas.
        """
        for line in self:
            if not (line.cycle_type_id or line.malha_type_id):
                continue
            if line.qualif_cycle_qty and line.estimated_hours:
                line.product_uom_qty = line.qualif_cycle_qty * line.estimated_hours
    afr_qualificacao_id = fields.Many2one(
        comodel_name="afr.qualificacao",
        string="Qualificação Gerada",
        copy=False,
        ondelete="set null",
        help="Qualificação criada ao confirmar este SO.",
    )
    equipment_subtotal = fields.Monetary(
        compute="_compute_equipment_subtotal",
        string="Subtotal Equipamento",
        currency_field="currency_id",
        help=(
            "Em linhas de section (display_type='line_section'), retorna soma "
            "de price_subtotal de TODAS linhas de produto do mesmo "
            "equipment_id no mesmo SO. Em demais linhas, 0. Visível no tree "
            "do SO p/ leitura rápida do escopo por equipamento."
        ),
    )

    @api.depends(
        "display_type",
        "equipment_id",
        "order_id.order_line.equipment_id",
        "order_id.order_line.display_type",
        "order_id.order_line.price_subtotal",
    )
    def _compute_equipment_subtotal(self):
        for line in self:
            if line.display_type != "line_section" or not line.equipment_id:
                line.equipment_subtotal = 0.0
                continue
            siblings = line.order_id.order_line.filtered(
                lambda l: l.equipment_id == line.equipment_id
                and not l.display_type
            )
            line.equipment_subtotal = sum(siblings.mapped("price_subtotal"))
    config_template_id = fields.Many2one(
        comodel_name="afr.qualificacao.config.template",
        string="Pacote Aplicado",
        copy=True,
        help=(
            "Pacote de equipamento usado ao gerar esta seção. Persiste o "
            "template escolhido para restaurá-lo ao reabrir o configurador."
        ),
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
        "is_proposal_optional",
        "qualification_type",
        "equipment_id",
        "cycle_type_id",
        "malha_type_id",
    )
    def _check_qualificacao_consistency(self):
        for line in self:
            if not line.is_qualificacao_managed:
                continue
            # Section/note (display_type set) — pular consistência: são
            # apenas linhas visuais geradas pelo wizard p/ agrupar
            # equipamentos no SO. Não geram qualificação.
            if line.display_type:
                continue
            # Serviço opcional (F8.2): linha managed sem equipamento/tipo —
            # não é linha de qualificação, pular consistência.
            if line.is_proposal_optional:
                continue
            # Parte 01 declinada: linha de referência (qty=0, não gera
            # qualificação), pular consistência.
            if line.part01_declined:
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
