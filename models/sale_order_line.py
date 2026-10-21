"""Extensão de sale.order.line para suportar fluxo de qualificação quote-first.

Linhas SO geradas pelo wizard configurador carregam metadados técnicos
(equipment_id, qualification_type, cycle_type_id/malha_type_id) que são
usados em SO confirm para gerar `afr.qualificacao` + `engc.os` + sub-records.

`is_qualificacao_managed=True` marca linhas criadas pelo wizard, permitindo
distinguir de linhas manuais (preservadas em re-apply do wizard).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero, float_round
from odoo.tools.misc import formatLang

from .price_allocation import allocate_target
from .time_allocation import allocate_hours


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
    # Specs de ciclo override por linha (proposta lê daqui; fallback cycle_type).
    # Só exibição na tabela de ciclos — não afeta QO/QD nem preço.
    temperature = fields.Char(
        string="Temperatura",
        copy=True,
        help="Override da temperatura do ciclo nesta proposta. Vazio = usa cycle_type.",
    )
    duration = fields.Char(
        string="Tempo",
        copy=True,
        help="Override do tempo do ciclo nesta proposta. Vazio = usa cycle_type.",
    )
    load_type = fields.Selection(
        selection=[
            ("vazio", "Câmara Vazia"),
            ("sem_carga", "Sem Carga"),
            ("com_carga", "Com Carga"),
        ],
        string="Tipo de Carga",
        copy=True,
        help="Override do tipo de carga exibido na proposta. Vazio = usa cycle_type.",
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

    optional_accepted = fields.Boolean(
        string="Opcional Aceito",
        default=False,
        copy=True,
        help="Opcional autorizado pelo cliente. Quando aceito, soma ao total, "
             "vai à fatura e — se for qualificação — volta ao pool de linhas "
             "pendentes da cotação (equipamentos_sem_os_ids); a geração da "
             "afr.qualificacao/OS continua manual, pelo wizard de geração de OS.",
    )
    optional_qty = fields.Float(
        string="Qtd. do Opcional",
        default=1.0,
        copy=True,
        help="Quantidade pretendida do opcional. Guardada enquanto não aceito "
             "(product_uom_qty fica 0); aplicada quando aceito.",
    )
    optional_id = fields.Many2one(
        comodel_name="afr.proposal.optional",
        string="Catálogo Opcional",
        copy=True,
        help="Item de catálogo que originou esta linha opcional de serviço. "
             "Permite repopular o configurador sem re-busca por produto.",
    )
    optional_ref_subtotal = fields.Monetary(
        string="Subtotal Referência",
        compute="_compute_optional_ref_subtotal",
        currency_field="currency_id",
        help="Preço de referência do opcional (preço unit. × qtd pretendida), "
             "mostrado na proposta mesmo quando ainda não aceito.",
    )

    @api.depends("is_proposal_optional", "price_unit", "optional_qty",
                 "qualif_cycle_qty", "estimated_hours", "cycle_type_id",
                 "malha_type_id")
    def _compute_optional_ref_subtotal(self):
        for line in self:
            if line.is_proposal_optional:
                line.optional_ref_subtotal = (
                    line.price_unit * line._optional_full_qty())
            else:
                line.optional_ref_subtotal = 0.0

    @api.onchange("optional_accepted", "optional_qty", "is_proposal_optional")
    def _onchange_optional_sync_qty(self):
        """Linha opcional: aplica a qty efetiva conforme aceite/tipo."""
        for line in self:
            if line.is_proposal_optional:
                line.product_uom_qty = line._optional_target_qty()

    def _optional_full_qty(self):
        """Qty de uma linha opcional SE aceita (ignora o estado aceito):
        ciclo/malha → qualif_cycle_qty × estimated_hours; serviço → optional_qty."""
        self.ensure_one()
        if self.cycle_type_id or self.malha_type_id:
            return (self.qualif_cycle_qty or 0) * (self.estimated_hours or 0.0)
        return self.optional_qty

    def _optional_target_qty(self):
        """Qty efetiva: 0 se não aceito, senão a qty cheia."""
        self.ensure_one()
        return self._optional_full_qty() if self.optional_accepted else 0.0

    def _sync_optional_qty(self):
        """Aplica a regra de qty dos opcionais (chamável fora de onchange)."""
        for line in self:
            if not line.is_proposal_optional:
                continue
            target = line._optional_target_qty()
            if line.product_uom_qty != target:
                line.product_uom_qty = target
        return True

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
        string="Base do Rateio",
        currency_field="currency_id",
        help=(
            "Em linhas de section (display_type='line_section'), soma dos "
            "subtotais das linhas elegíveis ao rateio do mesmo equipment_id "
            "(managed, qty>0, não opcionais, não declinadas). Em demais "
            "linhas, 0."
        ),
    )
    equipment_target_price = fields.Monetary(
        string="Preço-Alvo",
        currency_field="currency_id",
        copy=True,
        help=(
            "Preço final fechado do equipamento (sem impostos). Ao ratear, "
            "os price_unit das linhas do equipamento são recalculados para "
            "que a soma dos subtotais bata neste valor."
        ),
    )
    equipment_target_delta = fields.Monetary(
        compute="_compute_equipment_target_delta",
        string="Desvio",
        currency_field="currency_id",
        help="equipment_subtotal − equipment_target_price. 0 se não há alvo.",
    )
    equipment_target_state = fields.Selection(
        selection=[
            ("none", "Sem alvo"),
            ("ok", "No alvo"),
            ("drift", "Desviado"),
        ],
        compute="_compute_equipment_target_delta",
        string="Situação do Alvo",
    )
    equipment_target_days = fields.Float(
        string="Tempo combinado (dias)",
        digits=(16, 2),
        copy=True,
        help=(
            "Tempo total combinado para o equipamento, em dias de jornada. "
            "Ao aplicar, as horas das linhas são redistribuídas "
            "proporcionalmente (em passos de 0,25 h)."
        ),
    )
    equipment_target_hours = fields.Float(
        compute="_compute_equipment_time_state",
        string="Horas combinadas",
        help="Tempo combinado (dias) × jornada (h/dia).",
    )
    equipment_current_hours = fields.Float(
        compute="_compute_equipment_time_state",
        string="Horas atuais",
    )
    equipment_time_state = fields.Selection(
        selection=[
            ("none", "Sem tempo combinado"),
            ("ok", "No tempo"),
            ("drift", "Diferente do combinado"),
        ],
        compute="_compute_equipment_time_state",
        string="Situação do Tempo",
    )
    is_rateio_priced = fields.Boolean(
        string="Preço Rateado",
        default=False,
        copy=True,
        help=(
            "True quando o price_unit desta linha foi calculado por "
            "_apply_equipment_target (rateio de preço-alvo por "
            "equipamento). Só linhas com esta flag têm o price_unit "
            "congelado contra o recompute nativo do core disparado por "
            "mudança de quantidade (ver _compute_price_unit); demais "
            "linhas — mesmo managed — continuam repreçando normalmente "
            "pela pricelist, inclusive via 'Atualizar Preços' do pedido. "
            "Sem caminho de reset além do re-apply do wizard configurador "
            "(que apaga e recria as linhas managed do zero) — por isso "
            "trocar o produto de uma linha já rateada mantém o price_unit "
            "antigo (calculado para o produto anterior) até um novo rateio "
            "ou re-apply do wizard."
        ),
    )

    @api.depends("product_id", "product_uom", "product_uom_qty")
    def _compute_price_unit(self):
        """Congela price_unit só nas linhas que o rateio precificou.

        O compute nativo do core (sale/models/sale_order_line.py) recalcula
        price_unit a partir do pricelist sempre que product_uom_qty muda —
        mesmo em linha existente, mesmo com price_unit setado manualmente
        (o core só protege esse valor quando qty_invoiced > 0). Sem esta
        guarda, qualquer edição de nº de ciclos/horas depois de aplicar o
        rateio de preço-alvo reseta o price_unit rateado de volta ao preço
        de tabela do produto.

        Escopo deliberadamente estreito: só `is_rateio_priced=True`, não
        toda linha `is_qualificacao_managed`. Um congelamento mais amplo
        quebraria "Atualizar Preços" (sale_order._recompute_prices, que
        chama este compute diretamente) para qualquer linha managed que
        nunca passou pelo rateio.

        `l._origin.id` (não `l.id`) porque durante onchange o registro é
        embrulhado num NewId com origin — precisa do id real por trás para
        distinguir "linha existente sendo editada" de "linha nova" (linha
        nova sempre reprecifica pela pricelist, mesmo com a flag setada).

        Nota: este congelamento cobre só `price_unit`. `discount` NÃO é
        protegido — "Atualizar Preços" (sale/models/sale_order.py,
        _recompute_prices) zera `discount` e chama `_compute_discount`
        incondicionalmente antes de chegar aqui. Hoje inerte na prática
        (nenhuma pricelist do banco é `discount_policy='with_discount'` e
        ninguém está no grupo `sale.group_discount_per_so_line`), mas é
        frágil por sorte — uma pricelist with_discount reintroduziria
        desconto numa linha rateada.
        """
        frozen = self.filtered(
            lambda l: l._origin.id and l.is_rateio_priced
        )
        super(SaleOrderLine, self - frozen)._compute_price_unit()

    def _rateio_base_lines(self):
        """Linhas elegíveis ao rateio do equipamento desta section.

        Fora: sections/notas, opcionais (aceitos ou não), Parte 01 declinada,
        linhas não-managed e linhas com qty 0.
        """
        self.ensure_one()
        if not self.equipment_id:
            return self.env["sale.order.line"]
        return self.order_id.order_line.filtered(
            lambda l: l.equipment_id == self.equipment_id
            and l.is_qualificacao_managed
            and not l.display_type
            and not l.is_proposal_optional
            and not l.part01_declined
            and l.product_uom_qty > 0
        )

    # Os paths regular_line_ids.* são necessários porque as abas do form
    # editam por datapoints OWL distintos de order_line (mesmo motivo
    # documentado em _compute_qualif_subtotals_html).
    @api.depends(
        "display_type",
        "equipment_id",
        "order_id.order_line.equipment_id",
        "order_id.order_line.display_type",
        "order_id.order_line.price_subtotal",
        "order_id.order_line.is_proposal_optional",
        "order_id.order_line.part01_declined",
        "order_id.order_line.product_uom_qty",
        "order_id.regular_line_ids.price_subtotal",
    )
    def _compute_equipment_subtotal(self):
        for line in self:
            if line.display_type != "line_section" or not line.equipment_id:
                line.equipment_subtotal = 0.0
                continue
            line.equipment_subtotal = sum(
                line._rateio_base_lines().mapped("price_subtotal")
            )

    @api.depends("equipment_subtotal", "equipment_target_price",
                 "display_type", "equipment_id")
    def _compute_equipment_target_delta(self):
        for line in self:
            if line.display_type != "line_section" or not line.equipment_id \
                    or not line.equipment_target_price:
                line.equipment_target_delta = 0.0
                line.equipment_target_state = "none"
                continue
            delta = line.equipment_subtotal - line.equipment_target_price
            line.equipment_target_delta = delta
            # Tolerância = erro máximo de arredondamento do rateio (price_unit
            # com 2 casas × qty fracionária): Σ 0,005 × qty, mínimo 0,01.
            tol = max(0.01, sum(
                0.005 * abs(l.product_uom_qty)
                for l in line._rateio_base_lines()))
            same = float_compare(abs(delta), tol, precision_digits=4) <= 0
            line.equipment_target_state = "ok" if same else "drift"

    def _check_equipment_target_base(self, base):
        """Pré-condições do rateio de preço (levanta antes de qualquer write)."""
        self.ensure_one()
        if not base:
            raise UserError(_(
                "Nenhuma linha elegível ao rateio para %s. Gere as linhas de "
                "qualificação antes de definir o preço-alvo."
            ) % (self.equipment_id.display_name or _("equipamento")))
        if float_is_zero(sum(base.mapped("price_subtotal")),
                          precision_digits=2):
            raise UserError(_(
                "As linhas de %s estão com preço zerado — defina os preços "
                "base antes de ratear."
            ) % (self.equipment_id.display_name or _("equipamento")))
        if any(not float_is_zero(l.discount, precision_digits=2)
               for l in base):
            raise UserError(_(
                "As linhas de %s têm desconto por linha — o rateio não "
                "suporta desconto (o preço rateado já é o preço final). "
                "Zere o desconto das linhas do equipamento antes de definir "
                "o preço-alvo."
            ) % (self.equipment_id.display_name or _("equipamento")))

    def _apply_equipment_target(self):
        """Ratea equipment_target_price entre as linhas do equipamento.

        Um único write, seguido de uma releitura de price_subtotal — quem
        arredonda de verdade é o compute_all do Odoo, não a aritmética local.
        Devolve dict(exact=bool, achieved=float) para a camada de UI.
        """
        self.ensure_one()
        target = self.equipment_target_price
        if float_is_zero(target, precision_digits=2) or target < 0:
            # target<=0 (ou sub-centavo, que a UI já arredonda pra 0.00 mas
            # que pode chegar aqui sem passar por essa conversão): não é um
            # alvo válido para o rateio proporcional. Limpa o campo só no
            # caso negativo — 0.0 já é "sem alvo" por si (equipment_target_
            # state computa "none"); nunca mexe em price_unit das linhas.
            if target < 0:
                self.equipment_target_price = 0.0
            return {"exact": True, "achieved": 0.0}

        base = self._rateio_base_lines()
        self._check_equipment_target_base(base)

        pairs = [(l.product_uom_qty, l.price_subtotal) for l in base]
        result = allocate_target(target, pairs)

        for line, price_unit in zip(base, result["price_units"]):
            line.write({"price_unit": price_unit, "is_rateio_priced": True})

        # Verificação sobre o que o ORM realmente computou.
        base.invalidate_recordset(["price_subtotal"])
        achieved = sum(base.mapped("price_subtotal"))
        diff = float_round(target - achieved, precision_digits=2,
                           rounding_method="HALF-UP")
        exact = float_is_zero(diff, precision_digits=2)
        if not exact:
            self.order_id.message_post(body=_(
                "Rateio de %(equip)s fechou em %(achieved)s — %(diff)s de "
                "diferença para o alvo %(target)s (limite de arredondamento: "
                "o preço unitário tem 2 casas e as horas são fracionárias)."
            ) % {
                "equip": self.equipment_id.display_name or "",
                "achieved": formatLang(self.env, achieved,
                                       currency_obj=self.currency_id),
                "diff": formatLang(self.env, diff,
                                   currency_obj=self.currency_id),
                "target": formatLang(self.env, target,
                                     currency_obj=self.currency_id),
            })
        return {"exact": exact, "achieved": achieved}

    def action_apply_equipment_target(self):
        """Botão 'Ratear' da linha na aba Preços por Equipamento."""
        self.ensure_one()
        res = self._apply_equipment_target()
        if res["exact"]:
            return True
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning",
                "title": _("Rateio aproximado"),
                "message": _(
                    "Fechou em %s — o alvo não é atingível com 2 casas no "
                    "preço unitário. Veja o histórico do pedido."
                ) % formatLang(self.env, res["achieved"],
                               currency_obj=self.currency_id),
                "sticky": False,
            },
        }

    @staticmethod
    def _time_weight(line):
        """Horas atuais da linha = nº ciclos × horas/ciclo (ciclos ≥ 1).

        Em ciclo/malha a qty já é essa conta (UdM horas) e é a fonte exata:
        `estimated_hours` tem 2 casas e, com ciclos > 1, horas/ciclo
        derivadas (ex.: 9,25 / 3) arredondam — multiplicar de volta erraria.
        """
        if line.cycle_type_id or line.malha_type_id:
            return line.product_uom_qty or 0.0
        return (line.qualif_cycle_qty or 1) * (line.estimated_hours or 0.0)

    @api.depends(
        "display_type", "equipment_id", "equipment_target_days",
        "work_hours_per_day",
        "order_id.order_line.equipment_id",
        "order_id.order_line.estimated_hours",
        "order_id.order_line.qualif_cycle_qty",
        "order_id.order_line.cycle_type_id",
        "order_id.order_line.malha_type_id",
        "order_id.order_line.product_uom_qty",
        "order_id.order_line.is_proposal_optional",
        "order_id.order_line.part01_declined",
        "order_id.regular_line_ids.estimated_hours",
    )
    def _compute_equipment_time_state(self):
        for line in self:
            if line.display_type != "line_section" or not line.equipment_id:
                line.equipment_target_hours = 0.0
                line.equipment_current_hours = 0.0
                line.equipment_time_state = "none"
                continue
            current = sum(self._time_weight(l)
                          for l in line._rateio_base_lines())
            target = line.equipment_target_days * (
                line.work_hours_per_day or 8.0)
            line.equipment_current_hours = current
            line.equipment_target_hours = target
            if float_is_zero(target, precision_digits=2):
                line.equipment_time_state = "none"
            elif float_compare(current, target, precision_digits=2) == 0:
                line.equipment_time_state = "ok"
            else:
                line.equipment_time_state = "drift"

    def _apply_equipment_time_target(self):
        """Ratea o tempo combinado entre as linhas do equipamento.

        Tempo primeiro, depois preço: com preço combinado, re-rateia o preço
        sobre as novas horas e o total do equipamento continua igual ao alvo.
        Sem preço combinado, o preço por hora é mantido (o total acompanha
        as horas). Linhas de ciclo/malha têm qty = horas; QI/QS (qty fixa)
        só têm as horas estimadas ajustadas.
        """
        self.ensure_one()
        if self.equipment_target_days <= 0:
            if self.equipment_target_days < 0:
                self.equipment_target_days = 0.0
            return {"exact": True, "achieved": 0.0}
        base = self._rateio_base_lines()
        if not base:
            raise UserError(_(
                "Nenhuma linha elegível para %s. Gere as linhas de "
                "qualificação antes de definir o tempo combinado."
            ) % (self.equipment_id.display_name or _("equipamento")))
        if self.equipment_target_price > 0:
            # Valida o rateio de preço ANTES de mexer nas horas: um erro
            # depois do write deixaria a section meio aplicada.
            self._check_equipment_target_base(base)
        target = self.equipment_target_days * (self.work_hours_per_day or 8.0)
        hours = allocate_hours(target, [self._time_weight(l) for l in base])
        for line, h in zip(base, hours):
            vals = {"estimated_hours": h / (line.qualif_cycle_qty or 1)}
            if line.cycle_type_id or line.malha_type_id:
                vals["product_uom_qty"] = h
                # Mantém o preço/hora (o compute nativo reprecificaria
                # pela pricelist ao mudar a qty).
                vals["price_unit"] = line.price_unit
            line.write(vals)
        if self.equipment_target_price:
            return self._apply_equipment_target()
        return {"exact": True, "achieved": 0.0}

    def action_save_as_client_default(self):
        """Botão "Tornar padrão cliente" na seção do equipamento.

        Funciona em qualquer estado da cotação. O escopo é reconstruído das
        linhas managed pela mesma leitura do configurador
        (`_load_from_existing_lines`); preço = preço combinado ou total atual
        da seção; dias = tempo combinado ou horas atuais / jornada.
        """
        self.ensure_one()
        Equip = self.env["afr.qualificacao.configurator.equipment"]
        Equip._check_client_default_manager()
        if (self.display_type != "line_section" or not self.equipment_id
                or not self.is_qualificacao_managed):
            raise UserError(_(
                "Use este botão na linha de seção de um equipamento."))
        wizard = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": self.order_id.id})
        wizard._load_from_existing_lines()
        eq_line = wizard.equipment_line_ids.filtered(
            lambda l: l.equipment_id == self.equipment_id)[:1]
        if not eq_line:
            raise UserError(_(
                "Nenhuma linha de qualificação para %s.")
                % self.equipment_id.display_name)
        hpd = self.work_hours_per_day or 8.0
        eq_line.work_hours_per_day = hpd
        price = self.equipment_target_price or self.equipment_subtotal
        days = self.equipment_target_days or (
            self.equipment_current_hours / hpd)
        return eq_line._save_client_default_flow(
            price=price, days=days, return_to_so=True)

    def action_apply_equipment_time_target(self):
        """Botão 'Aplicar tempo' da linha na aba Preços por Equipamento."""
        self.ensure_one()
        res = self._apply_equipment_time_target()
        if res["exact"]:
            return True
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning",
                "title": _("Rateio aproximado"),
                "message": _(
                    "Tempo aplicado; o preço fechou em %s — veja o "
                    "histórico do pedido."
                ) % formatLang(self.env, res["achieved"],
                               currency_obj=self.currency_id),
                "sticky": False,
            },
        }

    # ------------------------------------------------------------------
    # Task 11 — aplicação automática dos alvos ao gravar na própria linha
    # ------------------------------------------------------------------
    _TARGET_KEYS = ("equipment_target_price", "equipment_target_days")
    _NO_AUTOAPPLY = "afr_no_target_autoapply"

    equipment_target_issue = fields.Char(
        string="Motivo",
        copy=False,
        readonly=True,
        help="Por que o preço/tempo combinado não pôde ser aplicado.",
    )
    equipment_apply_state = fields.Selection(
        selection=[
            ("none", "Sem alvo"),
            ("ok", "Aplicado"),
            ("drift", "Diferente"),
            ("issue", "Não aplicado"),
        ],
        compute="_compute_equipment_apply_state",
        string="Situação",
    )

    @api.depends("equipment_target_state", "equipment_time_state",
                 "equipment_target_issue")
    def _compute_equipment_apply_state(self):
        for line in self:
            states = {line.equipment_target_state, line.equipment_time_state}
            if states == {"none"}:
                line.equipment_apply_state = "none"
            elif line.equipment_target_issue:
                line.equipment_apply_state = "issue"
            elif "drift" in states:
                line.equipment_apply_state = "drift"
            else:
                line.equipment_apply_state = "ok"

    def write(self, vals):
        res = super().write(vals)
        if (not self.env.context.get(self._NO_AUTOAPPLY)
                and any(k in vals for k in self._TARGET_KEYS)):
            for section in self.filtered(
                lambda l: l.display_type == "line_section"
                and l.equipment_id
                and l.order_id.state in ("draft", "sent")
            ):
                section._auto_apply_equipment_targets()
        return res

    def _auto_apply_equipment_targets(self):
        """Tempo (se houver) e depois preço; nunca levanta.

        Falha de pré-condição (desconto, base zerada/vazia) mantém o alvo
        digitado, desfaz qualquer write parcial (savepoint) e grava o motivo
        em `equipment_target_issue`. Sucesso limpa o motivo.
        """
        self.ensure_one()
        sec = self.with_context(**{self._NO_AUTOAPPLY: True})
        issue = False
        res = {"exact": True, "achieved": 0.0}
        if sec.equipment_target_days > 0 or sec.equipment_target_price > 0:
            try:
                with self.env.cr.savepoint():
                    if sec.equipment_target_days > 0:
                        res = sec._apply_equipment_time_target()
                    else:
                        res = sec._apply_equipment_target()
            except UserError as err:
                self.env.invalidate_all()
                issue = err.args[0] if err.args else str(err)
        if (sec.equipment_target_issue or False) != issue:
            sec.equipment_target_issue = issue
        return res if not issue else None

    def action_reapply_equipment_targets(self):
        """Botão "Reaplicar" da coluna Situação."""
        self.ensure_one()
        # Sempre True: o form recarrega e mostra a Situação/Motivo.
        self._auto_apply_equipment_targets()
        return True


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
        "part01_declined",
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
            # Opcional de SERVIÇO (sem qualification_type) — não é linha de
            # qualificação, pula consistência. Opcional de QUALIFICAÇÃO
            # (com qualification_type) segue as regras normais abaixo.
            if line.is_proposal_optional and not line.qualification_type:
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
