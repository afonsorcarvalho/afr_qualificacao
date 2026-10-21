"""Wizard configurador de qualificações em sale.order (quote-first).

Fluxo: comercial clica `Configurar Qualificações` no SO → wizard fullscreen
abre com matriz equipamento × tipo. Apply gera linhas SO marcadas
`is_qualificacao_managed=True` com metadata técnica.

Atalhos:
- Duplicar equipamento (copia config trocando equipment_id)
- Adicionar múltiplos (wizard intermediário .bulk com M2M)
- Template salvo (afr.qualificacao.config.template)

Estratégia Apply: recria-do-zero (apaga linhas managed + recria; linhas
manuais avulsas preservadas).
"""

import re
from collections import defaultdict

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_round
from odoo.tools.misc import formatLang

from ..models.price_allocation import allocate_target
from ..models.time_allocation import allocate_hours


# F8.4/F8.7 — passos do configurador guiado, em ordem.
_logger = logging.getLogger(__name__)

_STEP_ORDER = ["escopo", "opcionais", "revisao"]


class AfrQualificacaoConfigurator(models.TransientModel):
    _name = "afr.qualificacao.configurator"
    _description = "Configurador de Qualificações"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env.context.get("active_id"),
    )
    partner_id = fields.Many2one(
        related="sale_order_id.partner_id",
        readonly=True,
    )
    company_id = fields.Many2one(
        related="sale_order_id.company_id",
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="sale_order_id.currency_id",
        readonly=True,
    )
    equipment_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.configurator.equipment",
        inverse_name="wizard_id",
        string="Equipamentos",
    )
    # Espelho só-leitura das linhas na etapa Revisão: lá as linhas já estão
    # gravadas (a troca de etapa salva o wizard), então o botão de linha
    # "Tornar padrão cliente" funciona — na etapa Escopo a linha
    # recém-criada é virtual e o Odoo bloqueia botões de linha.
    review_equipment_line_ids = fields.Many2many(
        comodel_name="afr.qualificacao.configurator.equipment",
        compute="_compute_review_equipment_line_ids",
        string="Equipamentos (revisão)",
    )
    optional_service_ids = fields.One2many(
        "afr.qualificacao.configurator.optional", "wizard_id",
        string="Serviços Opcionais")
    optional_qualif_ids = fields.One2many(
        "afr.qualificacao.configurator.optional.qualif", "wizard_id",
        string="Qualificações Opcionais")
    total_estimated = fields.Monetary(
        compute="_compute_total_estimated",
        currency_field="currency_id",
        string="Total Estimado",
    )
    estimated_hours_total = fields.Float(
        string="Horas (Total)",
        compute="_compute_wizard_estimated_totals",
        digits="Product Price",
    )
    estimated_days_total = fields.Float(
        string="Dias Úteis (Total)",
        compute="_compute_wizard_estimated_totals",
        digits=(8, 1),
    )
    # F8.4 — configurador guiado multi-step (F10.2: reduzido a Escopo→Revisão;
    # blocos editados no form do SO; opcionais adicionados manualmente).
    step = fields.Selection(
        selection=[
            ("escopo", "1. Escopo"),
            ("opcionais", "2. Opcionais"),
            ("revisao", "3. Revisão"),
        ],
        default="escopo",
        required=True,
        string="Etapa",
    )
    proposal_template_id = fields.Many2one(
        comodel_name="afr.proposal.template",
        string="Template de Proposta",
        help="Define os blocos de texto da proposta. Aplicado ao pedido.",
    )
    equipment_count = fields.Integer(
        compute="_compute_review_counts",
        string="Equipamentos",
    )
    # F10.2 — resumo read-only da Revisão (HTML). NÃO reutilizar o o2m
    # equipment_line_ids na Revisão: duplicar o campo na mesma view quebra a
    # tree editável do Escopo (some o "adicionar equipamento").
    review_summary_html = fields.Html(
        compute="_compute_review_summary_html",
        string="Resumo",
        sanitize=False,
    )

    @api.depends(
        "equipment_line_ids.equipment_id",
        "equipment_line_ids.estimated_hours_total",
        "equipment_line_ids.subtotal",
    )
    def _compute_review_summary_html(self):
        for wiz in self:
            rows = []
            for el in wiz.equipment_line_ids:
                value = formatLang(
                    self.env, el.subtotal or 0.0,
                    currency_obj=wiz.currency_id,
                )
                hours = formatLang(self.env, el.estimated_hours_total or 0.0, digits=2)
                rows.append(
                    '<tr><td style="padding:4px 12px;">%s</td>'
                    '<td style="padding:4px 12px;text-align:right;">%s h</td>'
                    '<td style="padding:4px 12px;text-align:right;">%s</td></tr>'
                    % (el.equipment_id.display_name or "", hours, value)
                )
            if not rows:
                wiz.review_summary_html = (
                    '<p class="text-muted">Sem equipamentos no escopo.</p>'
                )
                continue
            wiz.review_summary_html = (
                '<table style="border-collapse:collapse;width:100%%;'
                'border:1px solid #ddd;font-size:13px;">'
                '<thead><tr style="background:#f4f4f4;border-bottom:1px solid #ccc;">'
                '<th style="padding:6px 12px;text-align:left;">Equipamento</th>'
                '<th style="padding:6px 12px;text-align:right;">Horas</th>'
                '<th style="padding:6px 12px;text-align:right;">Subtotal</th>'
                '</tr></thead><tbody>%s</tbody></table>'
            ) % "".join(rows)

    optional_summary_html = fields.Html(
        compute="_compute_optional_summary_html",
        string="Resumo Opcionais",
        sanitize=False,
    )

    @api.depends(
        "optional_service_ids.accepted", "optional_service_ids.qty",
        "optional_service_ids.unit_price",
        "optional_qualif_ids.accepted", "optional_qualif_ids.qty",
        "optional_qualif_ids.estimated_hours",
        "optional_qualif_ids.cycle_type_id", "optional_qualif_ids.malha_type_id",
    )
    def _compute_optional_summary_html(self):
        for wiz in self:
            rows = []
            total = 0.0
            for opt in wiz.optional_service_ids.filtered("accepted"):
                sub = (opt.unit_price or 0.0) * (opt.qty or 0.0)
                total += sub
                rows.append(
                    '<tr><td style="padding:4px 12px;">%s</td>'
                    '<td style="padding:4px 12px;text-align:right;">%s</td>'
                    '<td style="padding:4px 12px;text-align:right;">%s</td></tr>'
                    % (opt.optional_id.name or "",
                       formatLang(self.env, opt.qty or 0.0, digits=2),
                       formatLang(self.env, sub, currency_obj=wiz.currency_id))
                )
            for oq in wiz.optional_qualif_ids.filtered("accepted"):
                prod = (oq.cycle_type_id.product_id
                        or oq.malha_type_id.product_id)
                hours = (oq.qty or 0) * (oq.estimated_hours or 0.0)
                sub = hours * (prod.list_price if prod else 0.0)
                total += sub
                name = (oq.cycle_type_id.name or oq.malha_type_id.name or "?")
                rows.append(
                    '<tr><td style="padding:4px 12px;">%s (opcional)</td>'
                    '<td style="padding:4px 12px;text-align:right;">%d</td>'
                    '<td style="padding:4px 12px;text-align:right;">%s</td></tr>'
                    % (name, oq.qty or 1,
                       formatLang(self.env, sub, currency_obj=wiz.currency_id))
                )
            if not rows:
                wiz.optional_summary_html = ""
                continue
            rows.append(
                '<tr style="border-top:2px solid #333;">'
                '<td style="padding:6px 12px;font-weight:bold;">TOTAL OPCIONAIS</td>'
                '<td></td>'
                '<td style="padding:6px 12px;text-align:right;font-weight:bold;">%s</td>'
                '</tr>' % formatLang(self.env, total, currency_obj=wiz.currency_id)
            )
            wiz.optional_summary_html = (
                '<table style="border-collapse:collapse;width:100%%;'
                'border:1px solid #ddd;font-size:13px;">'
                '<thead><tr style="background:#f9f9f9;border-bottom:1px solid #ccc;">'
                '<th style="padding:6px 12px;text-align:left;">Opcional Selecionado</th>'
                '<th style="padding:6px 12px;text-align:right;">Qtd</th>'
                '<th style="padding:6px 12px;text-align:right;">Subtotal</th>'
                '</tr></thead><tbody>%s</tbody></table>'
            ) % "".join(rows)

    @api.depends("equipment_line_ids.subtotal")
    def _compute_total_estimated(self):
        for wiz in self:
            wiz.total_estimated = sum(wiz.equipment_line_ids.mapped("subtotal"))

    @api.depends(
        "equipment_line_ids.estimated_hours_total",
        "equipment_line_ids.estimated_days_total",
    )
    def _compute_wizard_estimated_totals(self):
        for wiz in self:
            wiz.estimated_hours_total = sum(
                wiz.equipment_line_ids.mapped("estimated_hours_total")
            )
            wiz.estimated_days_total = sum(
                wiz.equipment_line_ids.mapped("estimated_days_total")
            )

    @api.depends("equipment_line_ids")
    def _compute_review_counts(self):
        for wiz in self:
            wiz.equipment_count = len(wiz.equipment_line_ids)

    # ------------------------------------------------------------------
    # F8.4 — navegação guiada entre etapas
    # ------------------------------------------------------------------
    def _reopen(self):
        """Reabre o próprio wizard no mesmo registro.

        Botão `type=object` num modal que retorna False/None FECHA o modal.
        Para a navegação manter o wizard aberto, os métodos de etapa
        precisam retornar esta ação de reabertura (mesmo res_id — o
        TransientModel preserva os dados na transação).
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Configurar Qualificações"),
            "res_model": "afr.qualificacao.configurator",
            "res_id": self.id,
            "view_mode": "form",
            # `views` explícito: a ação também é usada como `next` de uma
            # notificação, que o cliente executa sem pré-processar no servidor.
            "views": [(False, "form")],
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

    def _go_to_step(self, target):
        """Move o wizard para `target` e reabre o modal."""
        self.step = target
        return self._reopen()

    @api.depends("equipment_line_ids")
    def _compute_review_equipment_line_ids(self):
        for wiz in self:
            wiz.review_equipment_line_ids = wiz.equipment_line_ids

    def action_next_step(self):
        """Avança uma etapa (valida o escopo ao sair da primeira)."""
        self.ensure_one()
        if self.step == "escopo" and not self.equipment_line_ids:
            raise UserError(_("Adicione ao menos 1 equipamento antes de avançar."))
        idx = _STEP_ORDER.index(self.step)
        if idx < len(_STEP_ORDER) - 1:
            return self._go_to_step(_STEP_ORDER[idx + 1])
        return self._reopen()

    def action_prev_step(self):
        """Volta uma etapa."""
        self.ensure_one()
        idx = _STEP_ORDER.index(self.step)
        if idx > 0:
            return self._go_to_step(_STEP_ORDER[idx - 1])
        return self._reopen()

    # ------------------------------------------------------------------
    # Carrega matriz a partir de linhas SO existentes (idempotência)
    # ------------------------------------------------------------------
    def _load_from_existing_lines(self):
        """Lê linhas SO managed, agrupa por equipment_id, popula equipment_line_ids."""
        self.ensure_one()
        # F8.4 — herda o template de proposta da SO
        self.proposal_template_id = self.sale_order_id.proposal_template_id
        so_lines = self.sale_order_id.order_line
        # Equipamentos managed (exclui linhas de opcionais avulsas)
        managed = so_lines.filtered(
            lambda l: l.is_qualificacao_managed and not l.is_proposal_optional
        )
        if not managed:
            return

        # Padrão: sufixo adicionado pelo action_apply ("— N ciclo(s)/malha(s)")
        _SUFFIX = re.compile(r'\s+—\s+\d+\s+(?:ciclo|malha)\(s\)$')

        def _base_name(line_name):
            """Remove sufixo de ciclo/malha do nome para restaurar a descrição editada."""
            if not line_name:
                return False
            return _SUFFIX.sub('', line_name) or False

        # Primeira passagem: captura config_template_id das linhas-seção por equip.
        equip_template_map = {}
        for line in managed:
            if line.display_type == 'line_section' and line.config_template_id:
                equip_template_map[line.equipment_id] = line.config_template_id

        by_equip = defaultdict(lambda: {
            "qi": False, "qo": False, "qs": False,
            "qi_part01_declined": False,
            "do_qo_part01": False, "qo_part01_declined": False,
            "qo_cycles": [], "qd": [], "calib": [],
        })
        for line in managed:
            if line.display_type:
                continue  # seção/nota — skip
            bucket = by_equip[line.equipment_id]
            qt = line.qualification_type
            if qt == "installation":
                bucket["qi"] = True
                if line.part01_declined:
                    bucket["qi_part01_declined"] = True
            elif qt == "operational":
                if line.cycle_type_id:
                    # F8.8 — QO cycle-based (Parte 02)
                    bucket["qo_cycles"].append({
                        "cycle_type_id": line.cycle_type_id.id,
                        "qty": line.qualif_cycle_qty or 1,
                        "estimated_hours": line.estimated_hours,
                        "description": _base_name(line.name),
                        "unit_price": line.price_unit,
                        "temperature": line.temperature,
                        "duration": line.duration,
                        "load_type": line.load_type,
                    })
                elif line.part == "01":
                    # QO Parte 01 (Verificações)
                    bucket["do_qo_part01"] = True
                    if line.part01_declined:
                        bucket["qo_part01_declined"] = True
                else:
                    # QO boolean legado (linha única type.config)
                    bucket["qo"] = True
            elif qt == "software":
                bucket["qs"] = True
            elif qt == "performance":
                bucket["qd"].append({
                    "cycle_type_id": line.cycle_type_id.id,
                    "qty": line.qualif_cycle_qty or 1,
                    "estimated_hours": line.estimated_hours,
                    "description": _base_name(line.name),
                    "unit_price": line.price_unit,
                    "temperature": line.temperature,
                    "duration": line.duration,
                    "load_type": line.load_type,
                })
            elif qt == "calibration":
                bucket["calib"].append({
                    "malha_type_id": line.malha_type_id.id,
                    "qty": line.qualif_cycle_qty or 1,
                    "estimated_hours": line.estimated_hours,
                    "description": _base_name(line.name),
                    "unit_price": line.price_unit,
                })

        cmds = []
        for equip, b in by_equip.items():
            cmds.append((0, 0, {
                "equipment_id": equip.id,
                "do_qi": b["qi"],
                "do_qo": b["qo"],
                "do_qs": b["qs"],
                "qi_part01_declined": b["qi_part01_declined"],
                "do_qo_part01": b["do_qo_part01"],
                "qo_part01_declined": b["qo_part01_declined"],
                "config_template_id": equip_template_map.get(equip, False) and equip_template_map[equip].id,
                "qo_line_ids": [(0, 0, x) for x in b["qo_cycles"]],
                "qd_line_ids": [(0, 0, x) for x in b["qd"]],
                "calib_line_ids": [(0, 0, x) for x in b["calib"]],
            }))
        if cmds:
            self.equipment_line_ids = cmds

        # Opcionais existentes → repopula as duas secções do step Opcionais.
        opt_lines = so_lines.filtered("is_proposal_optional")
        svc_cmds, qualif_cmds = [], []
        for line in opt_lines:
            if line.qualification_type:
                qualif_cmds.append((0, 0, {
                    "equipment_id": line.equipment_id.id,
                    "qualification_type": line.qualification_type,
                    "cycle_type_id": line.cycle_type_id.id or False,
                    "malha_type_id": line.malha_type_id.id or False,
                    "qty": line.qualif_cycle_qty or 1,
                    "estimated_hours": line.estimated_hours,
                    "accepted": line.optional_accepted,
                }))
            else:
                opt_catalog = line.optional_id or self.env[
                    "afr.proposal.optional"].search(
                    [("product_id", "=", line.product_id.id)], limit=1)
                if opt_catalog:
                    svc_cmds.append((0, 0, {
                        "optional_id": opt_catalog.id,
                        "qty": line.optional_qty or line.product_uom_qty or 1.0,
                        "unit_price": line.price_unit,
                        "accepted": line.optional_accepted,
                    }))
        if svc_cmds:
            self.optional_service_ids = svc_cmds
        if qualif_cmds:
            self.optional_qualif_ids = qualif_cmds

    # ------------------------------------------------------------------
    # Apply — recria-do-zero
    # ------------------------------------------------------------------
    def action_apply(self):
        """Apaga linhas managed do SO e recria conforme matriz do wizard."""
        self.ensure_one()
        if not self.equipment_line_ids:
            raise UserError(_("Adicione ao menos 1 equipamento."))
        vistos = set()
        for eq_line in self.equipment_line_ids:
            if eq_line.equipment_id.id in vistos:
                raise UserError(_(
                    "O equipamento %s aparece mais de uma vez no configurador."
                ) % eq_line.equipment_id.display_name)
            vistos.add(eq_line.equipment_id.id)
        # valida cada linha equipment tem ao menos 1 qualif
        for eq_line in self.equipment_line_ids:
            if not (
                eq_line.do_qi or eq_line.do_qs
                or eq_line.do_qo_part01
                or eq_line.qo_line_ids or eq_line.qd_line_ids
                or eq_line.calib_line_ids
            ):
                raise UserError(_(
                    "Equipamento %s sem qualificações selecionadas."
                ) % (eq_line.equipment_id.display_name or "?"))
            if eq_line.qi_part01_declined and not eq_line.calib_line_ids:
                raise UserError(_(
                    "Equipamento %s: Parte 01 da QI declinada exige ao menos "
                    "uma malha (Parte 02). Não há contratação só da Parte 01."
                ) % (eq_line.equipment_id.display_name or "?"))
            if eq_line.qo_part01_declined and not eq_line.qo_line_ids:
                raise UserError(_(
                    "Equipamento %s: Parte 01 da QO declinada exige ao menos "
                    "um ciclo (Parte 02)."
                ) % (eq_line.equipment_id.display_name or "?"))

        so = self.sale_order_id
        # Alvos de rateio vivem nas sections managed, que o unlink abaixo
        # apaga. Capturar antes e regravar nas sections novas — mecanismo
        # diferente de config_template_id: aqui é leitura ao vivo das linhas
        # existentes dentro do próprio action_apply; config_template_id é
        # cacheado antes, em _load_from_existing_lines (equip_template_map).
        alvos = {el.equipment_id.id: el._apply_targets()
                 for el in self.equipment_line_ids}
        alvos_por_equip = {k: v[0] for k, v in alvos.items()}
        dias_por_equip = {k: v[1] for k, v in alvos.items()}
        so.order_line.filtered("is_qualificacao_managed").unlink()

        TypeConfig = self.env["afr.qualificacao.type.config"]
        new_lines = []

        for eq_line in self.equipment_line_ids:
            equip = eq_line.equipment_id

            # Section header por equipamento — Odoo renderiza em bold no
            # tree do SO e calcula subtotal por section nativamente. Marca
            # is_qualificacao_managed pra ser apagada em re-apply.
            section_label = equip.display_name or _("Equipamento")
            if equip.serial_number:
                section_label += " — S/N: %s" % equip.serial_number
            new_lines.append((0, 0, {
                "order_id": so.id,
                "display_type": "line_section",
                "name": section_label,
                "is_qualificacao_managed": True,
                "equipment_id": equip.id,
                "config_template_id": eq_line.config_template_id.id if eq_line.config_template_id else False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "work_hours_per_day": eq_line.work_hours_per_day or 8.0,
                "equipment_target_price": alvos_por_equip.get(equip.id, 0.0),
                "equipment_target_days": dias_por_equip.get(equip.id, 0.0),
            }))

            new_lines += [
                (0, 0, dict(v, order_id=so.id))
                for v in eq_line._so_line_vals(so.company_id)
            ]

        for opt in self.optional_service_ids:
            price = opt.unit_price or opt.optional_id.product_id.list_price
            new_lines.append((0, 0, {
                "order_id": so.id,
                "product_id": opt.optional_id.product_id.id,
                "name": opt.optional_id.name,
                "is_qualificacao_managed": True,
                "is_proposal_optional": True,
                "optional_accepted": opt.accepted,
                "optional_qty": opt.qty,
                "optional_id": opt.optional_id.id,
                "price_unit": price,
                "product_uom_qty": opt.qty if opt.accepted else 0.0,
            }))

        for oq in self.optional_qualif_ids:
            ct = oq.cycle_type_id
            mt = oq.malha_type_id
            product = (ct.product_id if ct else mt.product_id if mt else False)
            if not product:
                raise UserError(_(
                    "Qualificação opcional de %s requer Tipo de Ciclo ou "
                    "Tipo de Malha."
                ) % (oq.equipment_id.display_name or "?"))
            hours = oq.estimated_hours or (
                ct.estimated_hours if ct else mt.estimated_hours if mt else 0.0)
            base_name = (ct.name if ct else mt.name if mt else _("Opcional"))
            qty_hours = (oq.qty or 1) * hours
            vals = {
                "order_id": so.id,
                "product_id": product.id,
                "name": _("%s — %d (opcional)") % (base_name, oq.qty or 1),
                "is_qualificacao_managed": True,
                "is_proposal_optional": True,
                "optional_accepted": oq.accepted,
                "optional_qty": oq.qty or 1,
                "qualification_type": oq.qualification_type,
                "equipment_id": oq.equipment_id.id,
                "qualif_cycle_qty": oq.qty or 1,
                "estimated_hours": hours,
                "product_uom_qty": qty_hours if oq.accepted else 0.0,
            }
            if ct:
                vals["cycle_type_id"] = ct.id
            if mt:
                vals["malha_type_id"] = mt.id
            if oq.qualification_type in ("operational", "calibration"):
                vals["part"] = "02"
            new_lines.append((0, 0, vals))

        so.write({"order_line": new_lines})
        # Reaplica os alvos (tempo antes do preço — o rateio de tempo já
        # reencadeia o de preço quando há preço combinado).
        for section in so.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and l.display_type == "line_section"
            and (l.equipment_target_days > 0 or l.equipment_target_price > 0)
        ):
            # Nunca bloqueia o apply: base não rateável (preço zerado,
            # desconto, sem linhas) → mantém o alvo gravado e registra o
            # motivo (equipment_target_issue); o user resolve na cotação.
            section._auto_apply_equipment_targets()
        # F8.2 — aplica o template e semeia blocos da proposta (idempotente —
        # preserva blocos já montados/editados no form do SO).
        if self.proposal_template_id:
            so.proposal_template_id = self.proposal_template_id
        so._seed_proposal_blocks()
        return {"type": "ir.actions.act_window_close"}

    # ------------------------------------------------------------------
    # Atalhos
    # ------------------------------------------------------------------
    def action_add_multiple_equipments(self):
        """Abre wizard bulk para adicionar N equipamentos com mesma config."""
        self.ensure_one()
        bulk = self.env["afr.qualificacao.configurator.bulk"].create({
            "parent_wizard_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Adicionar Vários Equipamentos"),
            "res_model": "afr.qualificacao.configurator.bulk",
            "res_id": bulk.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_save_as_template(self):
        """Salva matriz atual como template reusável."""
        self.ensure_one()
        if not self.equipment_line_ids:
            raise UserError(_("Sem equipamentos para salvar como template."))
        # Pega primeira equip_line como base (template é genérico — sem equip_id)
        base = self.equipment_line_ids[0]
        vals = base._template_scope_vals()
        vals.update({
            "name": _("Template do orçamento %s") % self.sale_order_id.name,
            "equipment_category_id": base.equipment_category_id.id,
        })
        template = self.env["afr.qualificacao.config.template"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "name": _("Template Salvo"),
            "res_model": "afr.qualificacao.config.template",
            "res_id": template.id,
            "view_mode": "form",
            "target": "current",
        }


class AfrQualificacaoConfiguratorEquipment(models.TransientModel):
    _name = "afr.qualificacao.configurator.equipment"
    _description = "Equipamento no Configurador"

    wizard_id = fields.Many2one(
        comodel_name="afr.qualificacao.configurator",
        required=True,
        ondelete="cascade",
    )
    equipment_id = fields.Many2one(
        comodel_name="engc.equipment",
        string="Equipamento",
        required=True,
    )
    equipment_category_id = fields.Many2one(
        related="equipment_id.category_id",
        readonly=True,
    )
    do_qi = fields.Boolean(string="QI")
    do_qo = fields.Boolean(string="QO")
    do_qs = fields.Boolean(string="QS")
    qo_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.configurator.qo.line",
        inverse_name="equipment_line_id",
        string="Ciclos QO (sem carga)",
    )
    qd_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.configurator.qd.line",
        inverse_name="equipment_line_id",
        string="Ciclos QD",
    )
    calib_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.configurator.calib.line",
        inverse_name="equipment_line_id",
        string="Malhas Calibração",
    )
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="wizard_id.currency_id",
        readonly=True,
    )
    estimated_hours_total = fields.Float(
        string="Horas Totais",
        compute="_compute_estimated_totals",
        digits="Product Price",
    )
    estimated_days_total = fields.Float(
        string="Dias Úteis",
        compute="_compute_estimated_totals",
        digits=(8, 1),
        help="Horas estimadas / jornada (1 dia útil = jornada h/dia).",
    )
    work_hours_per_day = fields.Float(
        string="Jornada (h/dia)",
        default=8.0,
        help="Horas úteis/dia deste equipamento (puxada do template, editável).",
    )
    qi_part01_declined = fields.Boolean(
        string="QI Parte 01 não solicitada",
        help="Cliente não solicitou execução das verificações (Parte 01) da QI.",
    )
    do_qo_part01 = fields.Boolean(
        string="QO Parte 01 (Verificações)",
        help="Verificações da QO (Parte 01), 1 execução por equipamento.",
    )
    qo_part01_declined = fields.Boolean(
        string="QO Parte 01 não solicitada",
        help="Cliente não solicitou execução das verificações (Parte 01) da QO.",
    )
    # F8.2 — template de equipamento: autofill QI/QO/QS + ciclos + malhas
    config_template_id = fields.Many2one(
        comodel_name="afr.qualificacao.config.template",
        string="Template de Equipamento",
        help=(
            "Selecione um pacote pré-cadastrado para preencher QI/QO/QS, "
            "ciclos e malhas automaticamente. Editável depois."
        ),
    )

    template_origin = fields.Selection(
        selection=[
            ("cliente", "Padrão do cliente"),
            ("categoria", "Padrão da categoria"),
            ("none", "Sem padrão"),
        ],
        string="Origem do pacote",
        compute="_compute_template_origin",
    )

    @api.depends("config_template_id", "config_template_id.partner_id")
    def _compute_template_origin(self):
        for line in self:
            tpl = line.config_template_id
            if not tpl:
                line.template_origin = "none"
            elif tpl.partner_id:
                line.template_origin = "cliente"
            else:
                line.template_origin = "categoria"

    @api.onchange("equipment_id")
    def _onchange_equipment_template(self):
        """Sem pacote escolhido: usa o padrão do cliente/categoria."""
        if not self.equipment_id:
            return
        tpl_cat = self.config_template_id.equipment_category_id
        if tpl_cat and tpl_cat != self.equipment_id.category_id:
            # Pacote de outra categoria (ex.: equipamento trocado) — re-resolve.
            self.config_template_id = False
        if self.config_template_id:
            return
        wiz = self.wizard_id
        tpl, _origin = self.env[
            "afr.qualificacao.config.template"
        ]._resolve_for_equipment(
            self.equipment_id, wiz.partner_id, wiz.company_id or None)
        if tpl:
            self.config_template_id = tpl
            self._onchange_config_template()

    @api.onchange("config_template_id")
    def _onchange_config_template(self):
        """Aplica o pacote do template à linha (preço/escopo — modelo híbrido)."""
        tpl = self.config_template_id
        if not tpl:
            return
        self.do_qi = tpl.do_qi
        self.do_qo = tpl.do_qo
        self.do_qs = tpl.do_qs
        self.qi_part01_declined = tpl.qi_part01_declined
        self.do_qo_part01 = tpl.do_qo_part01
        self.qo_part01_declined = tpl.qo_part01_declined
        self.work_hours_per_day = tpl.work_hours_per_day or 8.0
        self.qo_line_ids = [(5, 0, 0)] + [
            (0, 0, {
                "cycle_type_id": line.cycle_type_id.id,
                "qty": line.qty,
                "description": (
                    line.description
                    or line.cycle_type_id.product_id.name
                    or False
                ),
                "unit_price": (
                    line.cycle_type_id.default_unit_price
                    or line.cycle_type_id.product_id.list_price
                    or 0.0
                ),
                "estimated_hours": (
                    line.estimated_hours
                    or line.cycle_type_id.estimated_hours
                    or 0.0
                ),
                "temperature": line.temperature or line.cycle_type_id.temperature,
                "duration": line.duration or line.cycle_type_id.duration,
                "load_type": line.load_type or line.cycle_type_id.load_type,
            })
            for line in tpl.qo_line_ids
        ]
        self.qd_line_ids = [(5, 0, 0)] + [
            (0, 0, {
                "cycle_type_id": line.cycle_type_id.id,
                "qty": line.qty,
                "description": (
                    line.description
                    or line.cycle_type_id.product_id.name
                    or False
                ),
                "unit_price": (
                    line.cycle_type_id.default_unit_price
                    or line.cycle_type_id.product_id.list_price
                    or 0.0
                ),
                "estimated_hours": (
                    line.estimated_hours
                    or line.cycle_type_id.estimated_hours
                    or 0.0
                ),
                "temperature": line.temperature or line.cycle_type_id.temperature,
                "duration": line.duration or line.cycle_type_id.duration,
                "load_type": line.load_type or line.cycle_type_id.load_type,
            })
            for line in tpl.qd_line_ids
        ]
        self.calib_line_ids = [(5, 0, 0)] + [
            (0, 0, {
                "malha_type_id": line.malha_type_id.id,
                "qty": line.qty,
                "description": (
                    line.description
                    or line.malha_type_id.product_id.name
                    or False
                ),
                "unit_price": (
                    line.malha_type_id.default_unit_price
                    or line.malha_type_id.product_id.list_price
                    or 0.0
                ),
                "estimated_hours": (
                    line.estimated_hours
                    or line.malha_type_id.estimated_hours
                    or 0.0
                ),
            })
            for line in tpl.calib_line_ids
        ]

    def _so_line_vals(self, company):
        """Vals das linhas de SO (sem seção/order_id) que `action_apply` cria
        para este equipamento. Fonte única: os totais do configurador
        (`_compute_subtotal`/`_compute_estimated_totals`) somam exatamente
        estas linhas, como a seção da cotação faz."""
        self.ensure_one()
        TypeConfig = self.env["afr.qualificacao.type.config"]
        equip = self.equipment_id
        new_lines = []
        # QI/QS via type.config (single line, sem ciclos)
        for flag, qtype in (
            ("do_qi", "installation"),
            ("do_qs", "software"),
        ):
            if not self[flag]:
                continue
            cfg = TypeConfig.get_config_for(qtype, company)
            if not cfg:
                raise UserError(_(
                    "Sem configuração de produto para tipo %s na empresa %s. "
                    "Cadastre em Qualificações → Configurações → Tipos."
                ) % (qtype, company.display_name))
            vals = {
                "product_id": cfg.service_product_id.id,
                "product_uom_qty": 1.0,
                # QI/QS não são cycle-based: 1 "estudo". qualif_cycle_qty=1
                # mantém o cálculo de horas (horas × qualif_cycle_qty) válido.
                "qualif_cycle_qty": 1,
                "is_qualificacao_managed": True,
                "qualification_type": qtype,
                "equipment_id": equip.id,
            }
            vals["price_unit"] = cfg._quote_unit_price(
                part01=(qtype == "installation"))
            if cfg.estimated_hours:
                vals["estimated_hours"] = cfg.estimated_hours
            if qtype == "installation":
                vals["part"] = "01"
                if self.qi_part01_declined:
                    vals["part01_declined"] = True
                    vals["product_uom_qty"] = 0.0  # não soma ao total
            new_lines.append(vals)

        # QO Parte 01 (Verificações) — 1 execução por equipamento.
        if self.do_qo_part01:
            cfg = TypeConfig.get_config_for("operational", company)
            if not cfg:
                raise UserError(_(
                    "Sem configuração de produto para QO (operational) na "
                    "empresa %s."
                ) % company.display_name)
            qo_p1_vals = {
                "product_id": cfg.service_product_id.id,
                "product_uom_qty": 1.0,
                "qualif_cycle_qty": 1,
                "is_qualificacao_managed": True,
                "qualification_type": "operational",
                "equipment_id": equip.id,
                "part": "01",
                "price_unit": cfg._quote_unit_price(part01=True),
            }
            if cfg.estimated_hours:
                qo_p1_vals["estimated_hours"] = cfg.estimated_hours
            if self.qo_part01_declined:
                qo_p1_vals["part01_declined"] = True
                qo_p1_vals["product_uom_qty"] = 0.0
            new_lines.append(qo_p1_vals)

        # QO — cycle-based: 1 linha por ciclo QO declarado.
        # product_uom_qty = HORAS (nº ciclos × horas/ciclo, UdM em horas);
        # qualif_cycle_qty preserva o nº de ciclos (explosão + proposta).
        for qo in self.qo_line_ids:
            hours = qo.estimated_hours or qo.cycle_type_id.estimated_hours or 0.0
            base_name = (
                qo.description
                or qo.cycle_type_id.product_id.name
                or qo.cycle_type_id.name
            )
            qo_vals = {
                "product_id": qo.cycle_type_id.product_id.id,
                "product_uom_qty": qo.qty * hours,
                "qualif_cycle_qty": qo.qty,
                "name": _("%s — %d ciclo(s)") % (base_name, qo.qty),
                "is_qualificacao_managed": True,
                "qualification_type": "operational",
                "equipment_id": equip.id,
                "cycle_type_id": qo.cycle_type_id.id,
                "part": "02",
            }
            # Sempre propaga o preço do wizard (autoritativo — pré-preenchido
            # por onchange/reload). Guard `if unit_price` impedia zerar.
            qo_vals["price_unit"] = qo.unit_price
            if hours:
                qo_vals["estimated_hours"] = hours
            qo_vals["temperature"] = qo.temperature or qo.cycle_type_id.temperature or False
            qo_vals["duration"] = qo.duration or qo.cycle_type_id.duration or False
            qo_vals["load_type"] = qo.load_type or qo.cycle_type_id.load_type or False
            new_lines.append(qo_vals)

        # QD — 1 linha por cycle_type
        for qd in self.qd_line_ids:
            hours = qd.estimated_hours or qd.cycle_type_id.estimated_hours or 0.0
            base_name = (
                qd.description
                or qd.cycle_type_id.product_id.name
                or qd.cycle_type_id.name
            )
            qd_vals = {
                "product_id": qd.cycle_type_id.product_id.id,
                "product_uom_qty": qd.qty * hours,
                "qualif_cycle_qty": qd.qty,
                "name": _("%s — %d ciclo(s)") % (base_name, qd.qty),
                "is_qualificacao_managed": True,
                "qualification_type": "performance",
                "equipment_id": equip.id,
                "cycle_type_id": qd.cycle_type_id.id,
            }
            # Sempre propaga (ver QO acima).
            qd_vals["price_unit"] = qd.unit_price
            if hours:
                qd_vals["estimated_hours"] = hours
            qd_vals["temperature"] = qd.temperature or qd.cycle_type_id.temperature or False
            qd_vals["duration"] = qd.duration or qd.cycle_type_id.duration or False
            qd_vals["load_type"] = qd.load_type or qd.cycle_type_id.load_type or False
            new_lines.append(qd_vals)

        # Calib — 1 linha por malha_type
        for c in self.calib_line_ids:
            hours = c.estimated_hours or c.malha_type_id.estimated_hours or 0.0
            base_name = (
                c.description
                or c.malha_type_id.product_id.name
                or c.malha_type_id.name
            )
            c_vals = {
                "product_id": c.malha_type_id.product_id.id,
                "product_uom_qty": c.qty * hours,
                "qualif_cycle_qty": c.qty,
                "name": _("%s — %d malha(s)") % (base_name, c.qty),
                "is_qualificacao_managed": True,
                "qualification_type": "calibration",
                "equipment_id": equip.id,
                "malha_type_id": c.malha_type_id.id,
                "part": "02",
            }
            # Sempre propaga (ver QO acima).
            c_vals["price_unit"] = c.unit_price
            if hours:
                c_vals["estimated_hours"] = hours
            new_lines.append(c_vals)

        return new_lines

    @staticmethod
    def _vals_totals(vals_list):
        """(preço, horas) como `_rateio_base_lines`/`_time_weight` contam."""
        price = hours = 0.0
        for v in vals_list:
            qty = v.get("product_uom_qty") or 0.0
            if v.get("part01_declined") or qty <= 0:
                continue
            price += (v.get("price_unit") or 0.0) * qty
            if v.get("cycle_type_id") or v.get("malha_type_id"):
                hours += qty
            else:
                hours += (v.get("qualif_cycle_qty") or 1) * (
                    v.get("estimated_hours") or 0.0)
        return price, hours

    _TOTALS_DEPENDS = (
        "do_qi", "do_qs", "do_qo_part01",
        "qi_part01_declined", "qo_part01_declined",
        "equipment_id", "work_hours_per_day", "config_template_id",
        "wizard_id.sale_order_id",
        "qo_line_ids.unit_price", "qo_line_ids.qty",
        "qo_line_ids.estimated_hours", "qo_line_ids.cycle_type_id",
        "qd_line_ids.unit_price", "qd_line_ids.qty",
        "qd_line_ids.estimated_hours", "qd_line_ids.cycle_type_id",
        "calib_line_ids.unit_price", "calib_line_ids.qty",
        "calib_line_ids.estimated_hours", "calib_line_ids.malha_type_id",
    )

    def _apply_targets(self):
        """(preço, dias) combinados que a seção receberá no `action_apply`.

        Alvos vivos da seção atual na cotação (mantidos em re-apply); para
        equipamento que entra pela 1ª vez, os do template.
        """
        self.ensure_one()
        so = self.wizard_id.sale_order_id
        eid = self.equipment_id.id
        secs = so.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id.id == eid)
        price = (secs.filtered("equipment_target_price")[-1:]
                 .equipment_target_price or 0.0)
        days = (secs.filtered("equipment_target_days")[-1:]
                .equipment_target_days or 0.0)
        tpl = self.config_template_id
        if tpl and not secs.filtered("is_qualificacao_managed"):
            if tpl.price_base > 0 and not price:
                price = tpl.price_base
            if tpl.estimated_days > 0 and not days:
                days = tpl.estimated_days
        # A seção grava com digits=(16, 2): projeta o valor arredondado.
        return price, float_round(days, precision_digits=2)

    @classmethod
    def _base_vals(cls, vals_list):
        """Linhas que entram no rateio (espelha `_rateio_base_lines`)."""
        return [v for v in vals_list
                if not v.get("part01_declined")
                and (v.get("product_uom_qty") or 0.0) > 0]

    def _project_targets(self, vals_list, price_t, days_t):
        """Projeta o rateio automático da seção (tempo, depois preço) sobre
        as vals — mesma regra de `_auto_apply_equipment_targets`: se a
        pré-condição falha, nada é aplicado (savepoint) e fica o base."""
        base = [dict(v) for v in self._base_vals(vals_list)]
        if not base or (price_t <= 0 and days_t <= 0):
            return self._vals_totals(vals_list)

        def _sub(v):
            return (v.get("price_unit") or 0.0) * (
                v.get("product_uom_qty") or 0.0)

        if price_t > 0 and float_is_zero(sum(_sub(v) for v in base),
                                         precision_digits=2):
            return self._vals_totals(vals_list)
        if days_t > 0:
            target = days_t * (self.work_hours_per_day or 8.0)
            weights = [self._vals_totals([v])[1] for v in base]
            for v, h in zip(base, allocate_hours(target, weights)):
                v["estimated_hours"] = h / (v.get("qualif_cycle_qty") or 1)
                if v.get("cycle_type_id") or v.get("malha_type_id"):
                    v["product_uom_qty"] = h
        if price_t <= 0:
            return self._vals_totals(base)
        hours = self._vals_totals(base)[1]
        base = self._base_vals(base)
        res = allocate_target(
            price_t, [(v["product_uom_qty"], _sub(v)) for v in base])
        return res["achieved"], hours

    def _apply_totals(self):
        """(preço, horas) que a seção terá após o `action_apply`: soma das
        linhas que ele cria, com o rateio automático do preço/tempo
        combinados — mesma conta de `equipment_subtotal` /
        `equipment_current_hours`. Sem type.config o apply levanta erro;
        aqui só não soma."""
        self.ensure_one()
        try:
            vals = self._so_line_vals(
                self.wizard_id.company_id or self.env.company)
        except UserError:
            return 0.0, 0.0
        return self._project_targets(vals, *self._apply_targets())

    @api.depends(*_TOTALS_DEPENDS)
    def _compute_subtotal(self):
        for el in self:
            el.subtotal = el._apply_totals()[0]

    @api.depends(*_TOTALS_DEPENDS)
    def _compute_estimated_totals(self):
        for el in self:
            hours = el._apply_totals()[1]
            el.estimated_hours_total = hours
            el.estimated_days_total = (
                hours / (el.work_hours_per_day or 8.0) if hours else 0.0
            )

    @api.constrains("wizard_id", "equipment_id")
    def _check_unique_equipment(self):
        for el in self:
            if not el.equipment_id:
                continue
            duplicates = self.search([
                ("wizard_id", "=", el.wizard_id.id),
                ("equipment_id", "=", el.equipment_id.id),
                ("id", "!=", el.id),
            ])
            if duplicates:
                raise ValidationError(_(
                    "Equipamento %s já adicionado neste configurador."
                ) % el.equipment_id.display_name)

    # ------------------------------------------------------------------
    # Escopo -> template (compartilhado por "Salvar como Template" e
    # "Tornar padrão cliente")
    # ------------------------------------------------------------------
    def _template_scope_vals(self):
        """Valores de `config.template` que espelham o escopo desta linha."""
        self.ensure_one()

        def _cycle_cmds(lines):
            return [(0, 0, {
                "cycle_type_id": l.cycle_type_id.id, "qty": l.qty,
                "description": l.description,
                "estimated_hours": l.estimated_hours,
                "temperature": l.temperature, "duration": l.duration,
                "load_type": l.load_type,
            }) for l in lines]

        return {
            "do_qi": self.do_qi, "do_qo": self.do_qo, "do_qs": self.do_qs,
            "qi_part01_declined": self.qi_part01_declined,
            "do_qo_part01": self.do_qo_part01,
            "qo_part01_declined": self.qo_part01_declined,
            "work_hours_per_day": self.work_hours_per_day or 8.0,
            "qo_line_ids": _cycle_cmds(self.qo_line_ids),
            "qd_line_ids": _cycle_cmds(self.qd_line_ids),
            "calib_line_ids": [(0, 0, {
                "malha_type_id": l.malha_type_id.id, "qty": l.qty,
                "description": l.description,
                "estimated_hours": l.estimated_hours,
            }) for l in self.calib_line_ids],
        }

    def _client_default_targets(self):
        """(preço combinado, dias combinados) a gravar no padrão do cliente.

        Preço/tempo combinados da seção do equipamento na cotação, se houver
        (alvo > 0); senão o total atual calculado no configurador
        (`subtotal`; dias = `estimated_hours_total` / jornada da linha).
        """
        self.ensure_one()
        section = self.wizard_id.sale_order_id.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.is_qualificacao_managed
            and l.equipment_id == self.equipment_id)[:1]
        price = section.equipment_target_price or self.subtotal
        # Não usa `estimated_days_total` (arredondado a 1 casa no campo).
        days = section.equipment_target_days or (
            self.estimated_hours_total / (self.work_hours_per_day or 8.0))
        return price, days

    def _client_default_context(self):
        """Valida e devolve (cliente comercial, categoria, empresa, existente)."""
        self.ensure_one()
        category = self.equipment_id.category_id
        if not category:
            raise UserError(_(
                "O equipamento %s não tem categoria. Defina a categoria do "
                "equipamento para gravar o padrão deste cliente."
            ) % (self.equipment_id.display_name or "?"))
        partner = self.wizard_id.partner_id.commercial_partner_id
        if not partner:
            raise UserError(_("A cotação não tem cliente."))
        company = self.wizard_id.company_id or self.env.company
        existing = self.env["afr.qualificacao.config.template"].search([
            ("partner_id", "=", partner.id),
            ("equipment_category_id", "=", category.id),
            ("company_id", "=", company.id),
        ], limit=1)
        return partner, category, company, existing

    def _check_client_default_manager(self):
        if not self.env.user.has_group(
                "afr_qualificacao.group_afr_qualificacao_manager"):
            raise UserError(_(
                "Apenas gestores podem gravar o padrão do cliente."))

    def _write_client_default(self, template=None, price=None, days=None):
        """Cria ou atualiza o padrão do cliente a partir desta linha.

        `template`/`price`/`days` (confirmação): grava exatamente o que foi
        exibido, no template exibido; o escopo vem sempre da linha viva.
        """
        self.ensure_one()
        self._check_client_default_manager()
        partner, category, company, existing = self._client_default_context()
        if template is not None:
            if not template.exists() or existing != template:
                raise UserError(_(
                    "O padrão deste cliente mudou desde que a confirmação "
                    "foi aberta. Feche e clique em \"Tornar padrão "
                    "cliente\" novamente."))
        if price is None:
            price, days = self._client_default_targets()
        vals = self._template_scope_vals()
        vals.update({"price_base": price, "estimated_days": days})
        if existing:
            for fname in ("qo_line_ids", "qd_line_ids", "calib_line_ids"):
                vals[fname] = [(5, 0, 0)] + vals[fname]
            existing.write(vals)
            tpl = existing
        else:
            src = self.config_template_id
            if src.equipment_category_id != category:
                src = src.browse()
            vals.update({
                "name": _("Padrão de %(cat)s — %(partner)s") % {
                    "cat": category.name, "partner": partner.name},
                "partner_id": partner.id,
                "equipment_category_id": category.id,
                "company_id": company.id,
                "qd_point_ids": [(0, 0, {
                    "sensor_kind_id": p.sensor_kind_id.id, "points": p.points,
                }) for p in src.qd_point_ids],
            })
            tpl = self.env["afr.qualificacao.config.template"].create(vals)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Padrão salvo"),
                "message": _("Padrão de %(cat)s salvo para %(partner)s") % {
                    "cat": category.name, "partner": partner.name}
                + ("" if price else _(" (sem preço combinado)")),
                "type": "success",
                "sticky": False,
            },
        }, tpl

    def action_save_as_client_default(self):
        """Botão "Tornar padrão cliente"."""
        self.ensure_one()
        return self._save_client_default_flow()

    def _save_client_default_flow(self, price=None, days=None,
                                  return_to_so=False):
        """Grava direto ou abre a confirmação (padrão já existente).

        `price`/`days` None → `_client_default_targets()`. `return_to_so`:
        chamado da linha de seção da cotação — a confirmação fecha em vez
        de reabrir o configurador.
        """
        self.ensure_one()
        self._check_client_default_manager()
        partner, category, _company, existing = self._client_default_context()
        if price is None:
            price, days = self._client_default_targets()
        if not existing:
            return self._write_client_default(price=price, days=days)[0]
        confirm = self.env["afr.qualificacao.client.default.confirm"].create({
            "return_to_so": return_to_so,
            "equipment_line_id": self.id,
            "template_id": existing.id,
            "partner_id": partner.id,
            "category_id": category.id,
            "old_price": existing.price_base,
            "old_days": existing.estimated_days,
            "new_price": price,
            "new_days": days,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Substituir o padrão deste cliente?"),
            "res_model": confirm._name,
            "res_id": confirm.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_duplicate(self):
        """Copia linha para nova com mesmo do_qi/qo/qs + sub-lines, equip vazio."""
        self.ensure_one()
        self.copy({
            "equipment_id": False,
            "qo_line_ids": [
                (0, 0, {
                    "cycle_type_id": l.cycle_type_id.id, "qty": l.qty,
                    "description": l.description, "unit_price": l.unit_price,
                    "estimated_hours": l.estimated_hours,
                    "temperature": l.temperature, "duration": l.duration,
                    "load_type": l.load_type,
                })
                for l in self.qo_line_ids
            ],
            "qd_line_ids": [
                (0, 0, {
                    "cycle_type_id": l.cycle_type_id.id, "qty": l.qty,
                    "description": l.description, "unit_price": l.unit_price,
                    "estimated_hours": l.estimated_hours,
                    "temperature": l.temperature, "duration": l.duration,
                    "load_type": l.load_type,
                })
                for l in self.qd_line_ids
            ],
            "calib_line_ids": [
                (0, 0, {
                    "malha_type_id": l.malha_type_id.id, "qty": l.qty,
                    "description": l.description, "unit_price": l.unit_price,
                    "estimated_hours": l.estimated_hours,
                })
                for l in self.calib_line_ids
            ],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "afr.qualificacao.configurator",
            "res_id": self.wizard_id.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }


class AfrQualificacaoConfiguratorQdLine(models.TransientModel):
    _name = "afr.qualificacao.configurator.qd.line"
    _description = "Linha de Ciclo QD no Configurador"

    equipment_line_id = fields.Many2one(
        comodel_name="afr.qualificacao.configurator.equipment",
        required=True,
        ondelete="cascade",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo",
        required=True,
    )
    description = fields.Char(string="Descrição")
    unit_price = fields.Monetary(
        string="Preço Unitário",
        currency_field="currency_id",
    )
    estimated_hours = fields.Float(
        string="Horas",
        digits="Product Price",
    )
    temperature = fields.Char(string="Temperatura")
    duration = fields.Char(string="Tempo")
    load_type = fields.Selection(
        selection=[
            ("vazio", "Câmara Vazia"),
            ("sem_carga", "Sem Carga"),
            ("com_carga", "Com Carga"),
        ],
        string="Tipo de Carga",
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="equipment_line_id.currency_id",
        readonly=True,
    )

    @api.depends("unit_price", "qty", "estimated_hours", "cycle_type_id.estimated_hours")
    def _compute_subtotal(self):
        # Preço por hora: subtotal = taxa × (nº ciclos × horas/ciclo).
        # Alinha com a linha SO nativa (product_uom_qty=horas × price_unit=taxa).
        for line in self:
            hours = line.estimated_hours or line.cycle_type_id.estimated_hours or 0.0
            line.subtotal = (line.unit_price or 0.0) * (line.qty or 0) * hours

    @api.onchange("cycle_type_id")
    def _onchange_cycle_type_defaults(self):
        for line in self:
            prod = line.cycle_type_id.product_id
            if prod:
                if not line.description:
                    line.description = prod.name
                if not line.unit_price:
                    line.unit_price = line.cycle_type_id.default_unit_price or prod.list_price
                if not line.estimated_hours:
                    line.estimated_hours = line.cycle_type_id.estimated_hours
                if not line.temperature:
                    line.temperature = line.cycle_type_id.temperature
                if not line.duration:
                    line.duration = line.cycle_type_id.duration
                if not line.load_type:
                    line.load_type = line.cycle_type_id.load_type

    @api.model_create_multi
    def create(self, vals_list):
        # Rede de segurança: linhas criadas via API (helpers/bulk) não disparam
        # o onchange — popula unit_price do tipo quando a chave está AUSENTE.
        # `unit_price=0` explícito é respeitado (chave presente) e propaga 0.
        for vals in vals_list:
            if "unit_price" not in vals and vals.get("cycle_type_id"):
                ct = self.env["afr.qualificacao.cycle.type"].browse(
                    vals["cycle_type_id"])
                vals["unit_price"] = (
                    ct.default_unit_price or ct.product_id.list_price)
        return super().create(vals_list)

    @api.constrains("qty")
    def _check_qty_positive(self):
        for line in self:
            if line.qty < 1:
                raise ValidationError(_("Quantidade de ciclos deve ser ≥ 1."))


class AfrQualificacaoConfiguratorQoLine(models.TransientModel):
    """F8.8 — linha de ciclo QO (sem carga) no configurador, espelho do QdLine."""

    _name = "afr.qualificacao.configurator.qo.line"
    _description = "Linha de Ciclo QO no Configurador"

    equipment_line_id = fields.Many2one(
        comodel_name="afr.qualificacao.configurator.equipment",
        required=True,
        ondelete="cascade",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo",
        required=True,
        domain=[("load_type", "in", ["vazio", "sem_carga"])],
    )
    description = fields.Char(string="Descrição")
    unit_price = fields.Monetary(
        string="Preço Unitário",
        currency_field="currency_id",
    )
    estimated_hours = fields.Float(
        string="Horas",
        digits="Product Price",
    )
    temperature = fields.Char(string="Temperatura")
    duration = fields.Char(string="Tempo")
    load_type = fields.Selection(
        selection=[
            ("vazio", "Câmara Vazia"),
            ("sem_carga", "Sem Carga"),
            ("com_carga", "Com Carga"),
        ],
        string="Tipo de Carga",
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="equipment_line_id.currency_id",
        readonly=True,
    )

    @api.depends("unit_price", "qty", "estimated_hours", "cycle_type_id.estimated_hours")
    def _compute_subtotal(self):
        # Preço por hora: subtotal = taxa × (nº ciclos × horas/ciclo).
        # Alinha com a linha SO nativa (product_uom_qty=horas × price_unit=taxa).
        for line in self:
            hours = line.estimated_hours or line.cycle_type_id.estimated_hours or 0.0
            line.subtotal = (line.unit_price or 0.0) * (line.qty or 0) * hours

    @api.onchange("cycle_type_id")
    def _onchange_cycle_type_defaults(self):
        for line in self:
            prod = line.cycle_type_id.product_id
            if prod:
                if not line.description:
                    line.description = prod.name
                if not line.unit_price:
                    line.unit_price = line.cycle_type_id.default_unit_price or prod.list_price
                if not line.estimated_hours:
                    line.estimated_hours = line.cycle_type_id.estimated_hours
                if not line.temperature:
                    line.temperature = line.cycle_type_id.temperature
                if not line.duration:
                    line.duration = line.cycle_type_id.duration
                if not line.load_type:
                    line.load_type = line.cycle_type_id.load_type

    @api.model_create_multi
    def create(self, vals_list):
        # Rede de segurança: ver Qd.create — popula unit_price do tipo quando
        # a chave está AUSENTE (0 explícito é respeitado e propaga 0).
        for vals in vals_list:
            if "unit_price" not in vals and vals.get("cycle_type_id"):
                ct = self.env["afr.qualificacao.cycle.type"].browse(
                    vals["cycle_type_id"])
                vals["unit_price"] = (
                    ct.default_unit_price or ct.product_id.list_price)
        return super().create(vals_list)

    @api.constrains("qty")
    def _check_qty_positive(self):
        for line in self:
            if line.qty < 1:
                raise ValidationError(_("Quantidade de ciclos QO deve ser ≥ 1."))


class AfrQualificacaoConfiguratorCalibLine(models.TransientModel):
    _name = "afr.qualificacao.configurator.calib.line"
    _description = "Linha de Malha Calibração no Configurador"

    equipment_line_id = fields.Many2one(
        comodel_name="afr.qualificacao.configurator.equipment",
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
        readonly=True,
    )
    description = fields.Char(string="Descrição")
    unit_price = fields.Monetary(
        string="Preço Unitário",
        currency_field="currency_id",
    )
    estimated_hours = fields.Float(
        string="Horas",
        digits="Product Price",
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="equipment_line_id.currency_id",
        readonly=True,
    )

    @api.depends("unit_price", "qty", "estimated_hours", "malha_type_id.estimated_hours")
    def _compute_subtotal(self):
        # Preço por hora: subtotal = taxa × (nº malhas × horas/malha).
        # Alinha com a linha SO nativa (product_uom_qty=horas × price_unit=taxa).
        for line in self:
            hours = line.estimated_hours or line.malha_type_id.estimated_hours or 0.0
            line.subtotal = (line.unit_price or 0.0) * (line.qty or 0) * hours

    @api.onchange("malha_type_id")
    def _onchange_malha_type_defaults(self):
        for line in self:
            prod = line.malha_type_id.product_id
            if prod:
                if not line.description:
                    line.description = prod.name
                if not line.unit_price:
                    line.unit_price = line.malha_type_id.default_unit_price or prod.list_price
                if not line.estimated_hours:
                    line.estimated_hours = line.malha_type_id.estimated_hours

    @api.model_create_multi
    def create(self, vals_list):
        # Rede de segurança: ver Qd.create — popula unit_price do tipo de malha
        # quando a chave está AUSENTE (0 explícito é respeitado e propaga 0).
        for vals in vals_list:
            if "unit_price" not in vals and vals.get("malha_type_id"):
                mt = self.env["afr.qualificacao.malha.type"].browse(
                    vals["malha_type_id"])
                vals["unit_price"] = (
                    mt.default_unit_price or mt.product_id.list_price)
        return super().create(vals_list)

    @api.constrains("qty")
    def _check_qty_positive(self):
        for line in self:
            if line.qty < 1:
                raise ValidationError(_("Quantidade de malhas deve ser ≥ 1."))


class AfrQualificacaoConfiguratorBulk(models.TransientModel):
    """Wizard intermediário: adiciona N equipamentos ao parent com mesma config."""

    _name = "afr.qualificacao.configurator.bulk"
    _description = "Adicionar Vários Equipamentos ao Configurador"

    parent_wizard_id = fields.Many2one(
        comodel_name="afr.qualificacao.configurator",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        related="parent_wizard_id.partner_id",
        readonly=True,
    )
    equipment_ids = fields.Many2many(
        comodel_name="engc.equipment",
        string="Equipamentos",
        required=True,
        help="Selecione equipamentos do cliente para aplicar a mesma config.",
    )
    do_qi = fields.Boolean(string="QI")
    do_qo = fields.Boolean(string="QO")
    do_qs = fields.Boolean(string="QS")
    qo_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.configurator.bulk.qo",
        inverse_name="bulk_id",
        string="Ciclos QO",
    )
    qd_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.configurator.bulk.qd",
        inverse_name="bulk_id",
        string="Ciclos QD",
    )
    calib_line_ids = fields.One2many(
        comodel_name="afr.qualificacao.configurator.bulk.calib",
        inverse_name="bulk_id",
        string="Malhas Calibração",
    )
    use_partner_template = fields.Boolean(
        string="Usar padrão do cliente/categoria",
        compute="_compute_use_partner_template",
        store=True,
        readonly=False,
        help=(
            "Equipamento com pacote padrão (do cliente ou da categoria) "
            "recebe esse pacote; os demais recebem a configuração abaixo."
        ),
    )

    def _resolve_template(self, equip):
        wiz = self.parent_wizard_id
        tpl, _origin = self.env[
            "afr.qualificacao.config.template"
        ]._resolve_for_equipment(equip, wiz.partner_id, wiz.company_id or None)
        return tpl

    @api.depends("equipment_ids")
    def _compute_use_partner_template(self):
        for bulk in self:
            bulk.use_partner_template = any(
                bulk._resolve_template(e) for e in bulk.equipment_ids)

    def action_apply(self):
        """Cria N equipment_lines no parent_wizard com mesma config."""
        self.ensure_one()
        if not self.equipment_ids:
            raise UserError(_("Selecione ao menos 1 equipamento."))
        EquipLine = self.env["afr.qualificacao.configurator.equipment"]
        # já existentes no parent: evita duplicar
        existing_ids = self.parent_wizard_id.equipment_line_ids.mapped(
            "equipment_id"
        ).ids
        for equip in self.equipment_ids:
            if equip.id in existing_ids:
                continue
            tpl = self.use_partner_template and self._resolve_template(equip)
            if tpl:
                line = EquipLine.create({
                    "wizard_id": self.parent_wizard_id.id,
                    "equipment_id": equip.id,
                    "config_template_id": tpl.id,
                })
                line._onchange_config_template()
                continue
            EquipLine.create({
                "wizard_id": self.parent_wizard_id.id,
                "equipment_id": equip.id,
                "do_qi": self.do_qi,
                "do_qo": self.do_qo,
                "do_qs": self.do_qs,
                "work_hours_per_day": 8.0,
                "qo_line_ids": [
                    (0, 0, {
                        "cycle_type_id": l.cycle_type_id.id, "qty": l.qty,
                        "description": l.description, "unit_price": l.unit_price,
                        "estimated_hours": l.estimated_hours,
                        "temperature": l.temperature, "duration": l.duration,
                        "load_type": l.load_type,
                    })
                    for l in self.qo_line_ids
                ],
                "qd_line_ids": [
                    (0, 0, {
                        "cycle_type_id": l.cycle_type_id.id, "qty": l.qty,
                        "description": l.description, "unit_price": l.unit_price,
                        "estimated_hours": l.estimated_hours,
                        "temperature": l.temperature, "duration": l.duration,
                        "load_type": l.load_type,
                    })
                    for l in self.qd_line_ids
                ],
                "calib_line_ids": [
                    (0, 0, {
                        "malha_type_id": l.malha_type_id.id, "qty": l.qty,
                        "description": l.description, "unit_price": l.unit_price,
                        "estimated_hours": l.estimated_hours,
                    })
                    for l in self.calib_line_ids
                ],
            })
        return {
            "type": "ir.actions.act_window",
            "res_model": "afr.qualificacao.configurator",
            "res_id": self.parent_wizard_id.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }


class AfrQualificacaoConfiguratorBulkQo(models.TransientModel):
    _name = "afr.qualificacao.configurator.bulk.qo"
    _description = "Bulk QO Line"

    bulk_id = fields.Many2one(
        comodel_name="afr.qualificacao.configurator.bulk",
        required=True,
        ondelete="cascade",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo",
        required=True,
        domain=[("load_type", "in", ["vazio", "sem_carga"])],
    )
    description = fields.Char(string="Descrição")
    unit_price = fields.Float(string="Preço Unitário")
    estimated_hours = fields.Float(
        string="Horas",
        digits="Product Price",
    )
    temperature = fields.Char(string="Temperatura")
    duration = fields.Char(string="Tempo")
    load_type = fields.Selection(
        selection=[
            ("vazio", "Câmara Vazia"),
            ("sem_carga", "Sem Carga"),
            ("com_carga", "Com Carga"),
        ],
        string="Tipo de Carga",
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)

    @api.onchange("cycle_type_id")
    def _onchange_cycle_type_defaults(self):
        for line in self:
            prod = line.cycle_type_id.product_id
            if prod:
                if not line.description:
                    line.description = prod.name
                if not line.unit_price:
                    line.unit_price = line.cycle_type_id.default_unit_price or prod.list_price
                if not line.estimated_hours:
                    line.estimated_hours = line.cycle_type_id.estimated_hours
                if not line.temperature:
                    line.temperature = line.cycle_type_id.temperature
                if not line.duration:
                    line.duration = line.cycle_type_id.duration
                if not line.load_type:
                    line.load_type = line.cycle_type_id.load_type


class AfrQualificacaoConfiguratorBulkQd(models.TransientModel):
    _name = "afr.qualificacao.configurator.bulk.qd"
    _description = "Bulk QD Line"

    bulk_id = fields.Many2one(
        comodel_name="afr.qualificacao.configurator.bulk",
        required=True,
        ondelete="cascade",
    )
    cycle_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.cycle.type",
        string="Tipo de Ciclo",
        required=True,
    )
    description = fields.Char(string="Descrição")
    unit_price = fields.Float(string="Preço Unitário")
    estimated_hours = fields.Float(
        string="Horas",
        digits="Product Price",
    )
    temperature = fields.Char(string="Temperatura")
    duration = fields.Char(string="Tempo")
    load_type = fields.Selection(
        selection=[
            ("vazio", "Câmara Vazia"),
            ("sem_carga", "Sem Carga"),
            ("com_carga", "Com Carga"),
        ],
        string="Tipo de Carga",
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)

    @api.onchange("cycle_type_id")
    def _onchange_cycle_type_defaults(self):
        for line in self:
            prod = line.cycle_type_id.product_id
            if prod:
                if not line.description:
                    line.description = prod.name
                if not line.unit_price:
                    line.unit_price = line.cycle_type_id.default_unit_price or prod.list_price
                if not line.estimated_hours:
                    line.estimated_hours = line.cycle_type_id.estimated_hours
                if not line.temperature:
                    line.temperature = line.cycle_type_id.temperature
                if not line.duration:
                    line.duration = line.cycle_type_id.duration
                if not line.load_type:
                    line.load_type = line.cycle_type_id.load_type


class AfrQualificacaoConfiguratorBulkCalib(models.TransientModel):
    _name = "afr.qualificacao.configurator.bulk.calib"
    _description = "Bulk Calib Line"

    bulk_id = fields.Many2one(
        comodel_name="afr.qualificacao.configurator.bulk",
        required=True,
        ondelete="cascade",
    )
    malha_type_id = fields.Many2one(
        comodel_name="afr.qualificacao.malha.type",
        string="Tipo de Malha",
        required=True,
    )
    description = fields.Char(string="Descrição")
    unit_price = fields.Float(string="Preço Unitário")
    estimated_hours = fields.Float(
        string="Horas",
        digits="Product Price",
    )
    qty = fields.Integer(string="Quantidade", default=1, required=True)

    @api.onchange("malha_type_id")
    def _onchange_malha_type_defaults(self):
        for line in self:
            prod = line.malha_type_id.product_id
            if prod:
                if not line.description:
                    line.description = prod.name
                if not line.unit_price:
                    line.unit_price = line.malha_type_id.default_unit_price or prod.list_price
                if not line.estimated_hours:
                    line.estimated_hours = line.malha_type_id.estimated_hours


class AfrQualificacaoConfiguratorOptional(models.TransientModel):
    _name = "afr.qualificacao.configurator.optional"
    _description = "Serviço opcional do configurador"

    wizard_id = fields.Many2one("afr.qualificacao.configurator",
                                required=True, ondelete="cascade")
    optional_id = fields.Many2one("afr.proposal.optional",
                                  string="Serviço Opcional", required=True)
    qty = fields.Float(string="Qtd", default=1.0)
    unit_price = fields.Monetary(string="Preço Unit.")
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    accepted = fields.Boolean(string="Aceito", default=False)

    @api.onchange("optional_id")
    def _onchange_optional_id(self):
        for line in self:
            if line.optional_id:
                line.qty = line.optional_id.default_qty or 1.0
                line.unit_price = (line.optional_id.default_price
                                   or line.optional_id.product_id.list_price)


class AfrQualificacaoConfiguratorOptionalQualif(models.TransientModel):
    _name = "afr.qualificacao.configurator.optional.qualif"
    _description = "Qualificação opcional do configurador"

    wizard_id = fields.Many2one("afr.qualificacao.configurator",
                                required=True, ondelete="cascade")
    equipment_id = fields.Many2one("engc.equipment", string="Equipamento",
                                   required=True)
    qualification_type = fields.Selection([
        ("performance", "QD (Desempenho)"),
        ("calibration", "Calibração"),
        ("operational", "QO (Operação)"),
    ], string="Tipo", required=True, default="performance")
    cycle_type_id = fields.Many2one("afr.qualificacao.cycle.type",
                                    string="Tipo de Ciclo")
    malha_type_id = fields.Many2one("afr.qualificacao.malha.type",
                                    string="Tipo de Malha")
    qty = fields.Integer(string="Nº Ciclos/Malhas", default=1)
    estimated_hours = fields.Float(string="Horas/Ciclo")
    accepted = fields.Boolean(string="Aceito", default=False)

    @api.onchange("cycle_type_id")
    def _onchange_cycle_type_id(self):
        for line in self:
            if line.cycle_type_id:
                line.estimated_hours = line.cycle_type_id.estimated_hours

    @api.onchange("malha_type_id")
    def _onchange_malha_type_id(self):
        for line in self:
            if line.malha_type_id:
                line.estimated_hours = line.malha_type_id.estimated_hours
