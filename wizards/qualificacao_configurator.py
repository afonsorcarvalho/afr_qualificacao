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

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang


# F8.4/F8.7 — passos do configurador guiado, em ordem.
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
            "res_model": "afr.qualificacao.configurator",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

    def _go_to_step(self, target):
        """Move o wizard para `target` e reabre o modal."""
        self.step = target
        return self._reopen()

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
            }))

            # QI/QS via type.config (single line, sem ciclos)
            for flag, qtype in (
                ("do_qi", "installation"),
                ("do_qs", "software"),
            ):
                if not eq_line[flag]:
                    continue
                cfg = TypeConfig.get_config_for(qtype, so.company_id)
                if not cfg:
                    raise UserError(_(
                        "Sem configuração de produto para tipo %s na empresa %s. "
                        "Cadastre em Qualificações → Configurações → Tipos."
                    ) % (qtype, so.company_id.display_name))
                vals = {
                    "order_id": so.id,
                    "product_id": cfg.service_product_id.id,
                    "product_uom_qty": 1.0,
                    # QI/QS não são cycle-based: 1 "estudo". qualif_cycle_qty=1
                    # mantém o cálculo de horas (horas × qualif_cycle_qty) válido.
                    "qualif_cycle_qty": 1,
                    "is_qualificacao_managed": True,
                    "qualification_type": qtype,
                    "equipment_id": equip.id,
                }
                if cfg.default_unit_price:
                    vals["price_unit"] = cfg.default_unit_price
                if cfg.estimated_hours:
                    vals["estimated_hours"] = cfg.estimated_hours
                if qtype == "installation":
                    vals["part"] = "01"
                    # Preço da Parte 01 = preço do variante Parte=01 (price_extra),
                    # sobrescreve o default_unit_price setado acima.
                    vals["price_unit"] = cfg.service_product_id.lst_price
                    if eq_line.qi_part01_declined:
                        vals["part01_declined"] = True
                        vals["product_uom_qty"] = 0.0  # não soma ao total
                new_lines.append((0, 0, vals))

            # QO Parte 01 (Verificações) — 1 execução por equipamento.
            if eq_line.do_qo_part01:
                cfg = TypeConfig.get_config_for("operational", so.company_id)
                if not cfg:
                    raise UserError(_(
                        "Sem configuração de produto para QO (operational) na "
                        "empresa %s."
                    ) % so.company_id.display_name)
                qo_p1_vals = {
                    "order_id": so.id,
                    "product_id": cfg.service_product_id.id,
                    "product_uom_qty": 1.0,
                    "qualif_cycle_qty": 1,
                    "is_qualificacao_managed": True,
                    "qualification_type": "operational",
                    "equipment_id": equip.id,
                    "part": "01",
                    "price_unit": cfg.service_product_id.lst_price,
                }
                if cfg.estimated_hours:
                    qo_p1_vals["estimated_hours"] = cfg.estimated_hours
                if eq_line.qo_part01_declined:
                    qo_p1_vals["part01_declined"] = True
                    qo_p1_vals["product_uom_qty"] = 0.0
                new_lines.append((0, 0, qo_p1_vals))

            # QO — cycle-based: 1 linha por ciclo QO declarado.
            # product_uom_qty = HORAS (nº ciclos × horas/ciclo, UdM em horas);
            # qualif_cycle_qty preserva o nº de ciclos (explosão + proposta).
            for qo in eq_line.qo_line_ids:
                hours = qo.estimated_hours or qo.cycle_type_id.estimated_hours or 0.0
                base_name = (
                    qo.description
                    or qo.cycle_type_id.product_id.name
                    or qo.cycle_type_id.name
                )
                qo_vals = {
                    "order_id": so.id,
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
                if qo.unit_price:
                    qo_vals["price_unit"] = qo.unit_price
                if hours:
                    qo_vals["estimated_hours"] = hours
                qo_vals["temperature"] = qo.temperature or qo.cycle_type_id.temperature or False
                qo_vals["duration"] = qo.duration or qo.cycle_type_id.duration or False
                qo_vals["load_type"] = qo.load_type or qo.cycle_type_id.load_type or False
                new_lines.append((0, 0, qo_vals))

            # QD — 1 linha por cycle_type
            for qd in eq_line.qd_line_ids:
                hours = qd.estimated_hours or qd.cycle_type_id.estimated_hours or 0.0
                base_name = (
                    qd.description
                    or qd.cycle_type_id.product_id.name
                    or qd.cycle_type_id.name
                )
                qd_vals = {
                    "order_id": so.id,
                    "product_id": qd.cycle_type_id.product_id.id,
                    "product_uom_qty": qd.qty * hours,
                    "qualif_cycle_qty": qd.qty,
                    "name": _("%s — %d ciclo(s)") % (base_name, qd.qty),
                    "is_qualificacao_managed": True,
                    "qualification_type": "performance",
                    "equipment_id": equip.id,
                    "cycle_type_id": qd.cycle_type_id.id,
                }
                if qd.unit_price:
                    qd_vals["price_unit"] = qd.unit_price
                if hours:
                    qd_vals["estimated_hours"] = hours
                qd_vals["temperature"] = qd.temperature or qd.cycle_type_id.temperature or False
                qd_vals["duration"] = qd.duration or qd.cycle_type_id.duration or False
                qd_vals["load_type"] = qd.load_type or qd.cycle_type_id.load_type or False
                new_lines.append((0, 0, qd_vals))

            # Calib — 1 linha por malha_type
            for c in eq_line.calib_line_ids:
                hours = c.estimated_hours or c.malha_type_id.estimated_hours or 0.0
                base_name = (
                    c.description
                    or c.malha_type_id.product_id.name
                    or c.malha_type_id.name
                )
                c_vals = {
                    "order_id": so.id,
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
                if c.unit_price:
                    c_vals["price_unit"] = c.unit_price
                if hours:
                    c_vals["estimated_hours"] = hours
                new_lines.append((0, 0, c_vals))

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
        template = self.env["afr.qualificacao.config.template"].create({
            "name": _("Template do orçamento %s") % self.sale_order_id.name,
            "equipment_category_id": base.equipment_category_id.id,
            "do_qi": base.do_qi,
            "do_qo": base.do_qo,
            "do_qs": base.do_qs,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": l.cycle_type_id.id, "qty": l.qty})
                for l in base.qd_line_ids
            ],
            "calib_line_ids": [
                (0, 0, {"malha_type_id": l.malha_type_id.id, "qty": l.qty})
                for l in base.calib_line_ids
            ],
        })
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

    @api.onchange("config_template_id")
    def _onchange_config_template(self):
        """Aplica o pacote do template à linha (preço/escopo — modelo híbrido)."""
        tpl = self.config_template_id
        if not tpl:
            return
        self.do_qi = tpl.do_qi
        self.do_qo = tpl.do_qo
        self.do_qs = tpl.do_qs
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

    @api.depends(
        "do_qi", "do_qs",
        "qo_line_ids.subtotal",
        "qd_line_ids.subtotal", "calib_line_ids.subtotal",
        "equipment_id",
    )
    def _compute_subtotal(self):
        TypeConfig = self.env["afr.qualificacao.type.config"]
        for el in self:
            total = 0.0
            # QI/QS via type.config (boolean)
            for flag, qtype in (
                ("do_qi", "installation"),
                ("do_qs", "software"),
            ):
                if not el[flag]:
                    continue
                cfg = TypeConfig.get_config_for(qtype, el.wizard_id.company_id)
                if cfg:
                    total += cfg.default_unit_price or (
                        cfg.service_product_id.list_price if cfg.service_product_id else 0.0
                    )
            total += sum(el.qo_line_ids.mapped("subtotal"))
            total += sum(el.qd_line_ids.mapped("subtotal"))
            total += sum(el.calib_line_ids.mapped("subtotal"))
            el.subtotal = total

    @api.depends(
        "do_qi", "do_qs", "work_hours_per_day",
        "qo_line_ids.estimated_hours", "qo_line_ids.qty",
        "qd_line_ids.estimated_hours", "qd_line_ids.qty",
        "calib_line_ids.estimated_hours", "calib_line_ids.qty",
    )
    def _compute_estimated_totals(self):
        TypeConfig = self.env["afr.qualificacao.type.config"]
        for el in self:
            hours = 0.0
            for flag, qtype in (("do_qi", "installation"), ("do_qs", "software")):
                if not el[flag]:
                    continue
                cfg = TypeConfig.get_config_for(qtype, el.wizard_id.company_id)
                if cfg:
                    hours += cfg.estimated_hours or 0.0
            for line in el.qo_line_ids:
                h = line.estimated_hours or line.cycle_type_id.estimated_hours
                hours += (h or 0.0) * (line.qty or 0)
            for line in el.qd_line_ids:
                h = line.estimated_hours or line.cycle_type_id.estimated_hours
                hours += (h or 0.0) * (line.qty or 0)
            for line in el.calib_line_ids:
                h = line.estimated_hours or line.malha_type_id.estimated_hours
                hours += (h or 0.0) * (line.qty or 0)
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
