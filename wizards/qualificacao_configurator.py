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

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# F8.4/F8.7 — passos do configurador guiado, em ordem.
_STEP_ORDER = ["escopo", "blocos", "opcionais", "revisao"]


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
    total_estimated = fields.Monetary(
        compute="_compute_total_estimated",
        currency_field="currency_id",
        string="Total Estimado",
    )
    # F8.2 — serviços opcionais incluídos como linhas extra na cotação
    optional_ids = fields.Many2many(
        comodel_name="afr.proposal.optional",
        string="Serviços Opcionais",
        help=(
            "Opcionais (pasta impressa, viagem, diária adicional) gerados "
            "como linhas extra do pedido — fora do escopo de qualificação."
        ),
    )
    # F8.4 — configurador guiado multi-step
    step = fields.Selection(
        selection=[
            ("escopo", "1. Escopo"),
            ("blocos", "2. Blocos da Proposta"),
            ("opcionais", "3. Opcionais"),
            ("revisao", "4. Revisão"),
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
    proposal_block_ids = fields.One2many(
        related="sale_order_id.proposal_block_ids",
        readonly=False,
        string="Blocos da Proposta",
    )
    block_count = fields.Integer(
        compute="_compute_review_counts",
        string="Blocos",
    )
    equipment_count = fields.Integer(
        compute="_compute_review_counts",
        string="Equipamentos",
    )
    optional_count = fields.Integer(
        compute="_compute_review_counts",
        string="Opcionais",
    )

    @api.depends("equipment_line_ids.subtotal")
    def _compute_total_estimated(self):
        for wiz in self:
            wiz.total_estimated = sum(wiz.equipment_line_ids.mapped("subtotal"))

    @api.depends("proposal_block_ids", "equipment_line_ids", "optional_ids")
    def _compute_review_counts(self):
        for wiz in self:
            wiz.block_count = len(wiz.proposal_block_ids)
            wiz.equipment_count = len(wiz.equipment_line_ids)
            wiz.optional_count = len(wiz.optional_ids)

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
        if target == "blocos":
            self._ensure_blocks_seeded()
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

    def _ensure_blocks_seeded(self):
        """Garante que a SO tem blocos para a etapa 'Blocos' (idempotente)."""
        self.ensure_one()
        so = self.sale_order_id
        if (
            self.proposal_template_id
            and so.proposal_template_id != self.proposal_template_id
        ):
            so.proposal_template_id = self.proposal_template_id
        if not so.proposal_block_ids:
            so._seed_proposal_blocks()

    # ------------------------------------------------------------------
    # Carrega matriz a partir de linhas SO existentes (idempotência)
    # ------------------------------------------------------------------
    def _load_from_existing_lines(self):
        """Lê linhas SO managed, agrupa por equipment_id, popula equipment_line_ids.

        Carrega também os serviços opcionais existentes de volta em
        `optional_ids` (idempotência ao reabrir o configurador).
        """
        self.ensure_one()
        # F8.4 — herda o template de proposta da SO
        self.proposal_template_id = self.sale_order_id.proposal_template_id
        so_lines = self.sale_order_id.order_line
        # Opcionais existentes → optional_ids
        opt_lines = so_lines.filtered("is_proposal_optional")
        if opt_lines:
            opts = self.env["afr.proposal.optional"].search(
                [("product_id", "in", opt_lines.mapped("product_id").ids)]
            )
            if opts:
                self.optional_ids = [(6, 0, opts.ids)]
        # Equipamentos managed (exclui linhas de opcionais)
        managed = so_lines.filtered(
            lambda l: l.is_qualificacao_managed and not l.is_proposal_optional
        )
        if not managed:
            return
        by_equip = defaultdict(lambda: {
            "qi": False, "qo": False, "qs": False,
            "qo_cycles": [], "qd": [], "calib": [],
        })
        for line in managed:
            bucket = by_equip[line.equipment_id]
            qt = line.qualification_type
            if qt == "installation":
                bucket["qi"] = True
            elif qt == "operational":
                if line.cycle_type_id:
                    # F8.8 — QO cycle-based
                    bucket["qo_cycles"].append({
                        "cycle_type_id": line.cycle_type_id.id,
                        "qty": int(line.product_uom_qty or 1),
                    })
                else:
                    # QO boolean (linha única type.config)
                    bucket["qo"] = True
            elif qt == "software":
                bucket["qs"] = True
            elif qt == "performance":
                bucket["qd"].append({
                    "cycle_type_id": line.cycle_type_id.id,
                    "qty": int(line.product_uom_qty or 1),
                })
            elif qt == "calibration":
                bucket["calib"].append({
                    "malha_type_id": line.malha_type_id.id,
                    "qty": int(line.product_uom_qty or 1),
                })

        cmds = []
        for equip, b in by_equip.items():
            cmds.append((0, 0, {
                "equipment_id": equip.id,
                "do_qi": b["qi"],
                "do_qo": b["qo"],
                "do_qs": b["qs"],
                "qo_line_ids": [(0, 0, x) for x in b["qo_cycles"]],
                "qd_line_ids": [(0, 0, x) for x in b["qd"]],
                "calib_line_ids": [(0, 0, x) for x in b["calib"]],
            }))
        if cmds:
            self.equipment_line_ids = cmds

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
                or eq_line.qo_line_ids or eq_line.qd_line_ids
                or eq_line.calib_line_ids
            ):
                raise UserError(_(
                    "Equipamento %s sem qualificações selecionadas."
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
                "product_uom_qty": 0,
                "price_unit": 0,
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
                    "is_qualificacao_managed": True,
                    "qualification_type": qtype,
                    "equipment_id": equip.id,
                }
                if cfg.default_unit_price:
                    vals["price_unit"] = cfg.default_unit_price
                if cfg.estimated_hours:
                    vals["estimated_hours"] = cfg.estimated_hours
                new_lines.append((0, 0, vals))

            # QO — cycle-based: 1 linha por ciclo QO declarado.
            for qo in eq_line.qo_line_ids:
                qo_vals = {
                    "order_id": so.id,
                    "product_id": qo.cycle_type_id.product_id.id,
                    "product_uom_qty": qo.qty,
                    "is_qualificacao_managed": True,
                    "qualification_type": "operational",
                    "equipment_id": equip.id,
                    "cycle_type_id": qo.cycle_type_id.id,
                }
                if qo.description:
                    qo_vals["name"] = qo.description
                if qo.unit_price:
                    qo_vals["price_unit"] = qo.unit_price
                hours = qo.estimated_hours or qo.cycle_type_id.estimated_hours
                if hours:
                    qo_vals["estimated_hours"] = hours
                new_lines.append((0, 0, qo_vals))

            # QD — 1 linha por cycle_type
            for qd in eq_line.qd_line_ids:
                qd_vals = {
                    "order_id": so.id,
                    "product_id": qd.cycle_type_id.product_id.id,
                    "product_uom_qty": qd.qty,
                    "is_qualificacao_managed": True,
                    "qualification_type": "performance",
                    "equipment_id": equip.id,
                    "cycle_type_id": qd.cycle_type_id.id,
                }
                if qd.description:
                    qd_vals["name"] = qd.description
                if qd.unit_price:
                    qd_vals["price_unit"] = qd.unit_price
                hours = qd.estimated_hours or qd.cycle_type_id.estimated_hours
                if hours:
                    qd_vals["estimated_hours"] = hours
                new_lines.append((0, 0, qd_vals))

            # Calib — 1 linha por malha_type
            for c in eq_line.calib_line_ids:
                c_vals = {
                    "order_id": so.id,
                    "product_id": c.malha_type_id.product_id.id,
                    "product_uom_qty": c.qty,
                    "is_qualificacao_managed": True,
                    "qualification_type": "calibration",
                    "equipment_id": equip.id,
                    "malha_type_id": c.malha_type_id.id,
                }
                if c.description:
                    c_vals["name"] = c.description
                if c.unit_price:
                    c_vals["price_unit"] = c.unit_price
                hours = c.estimated_hours or c.malha_type_id.estimated_hours
                if hours:
                    c_vals["estimated_hours"] = hours
                new_lines.append((0, 0, c_vals))

        # Serviços opcionais → linhas managed marcadas is_proposal_optional
        # (apagadas/recriadas no re-apply junto das demais linhas managed,
        # mas excluídas da geração de qualificações no confirm do SO).
        for opt in self.optional_ids:
            price = opt.default_price or (
                opt.product_id.list_price if opt.product_id else 0.0
            )
            new_lines.append((0, 0, {
                "order_id": so.id,
                "product_id": opt.product_id.id,
                "name": opt.name,
                "product_uom_qty": opt.default_qty or 1.0,
                "price_unit": price,
                "is_qualificacao_managed": True,
                "is_proposal_optional": True,
            }))

        so.write({"order_line": new_lines})
        # F8.2/F8.4 — aplica o template e semeia blocos (idempotente —
        # preserva blocos já montados/editados na etapa "Blocos").
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
                })
                for l in self.qo_line_ids
            ],
            "qd_line_ids": [
                (0, 0, {
                    "cycle_type_id": l.cycle_type_id.id, "qty": l.qty,
                    "description": l.description, "unit_price": l.unit_price,
                    "estimated_hours": l.estimated_hours,
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
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="equipment_line_id.currency_id",
        readonly=True,
    )

    @api.depends("unit_price", "qty")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.unit_price or 0.0) * (line.qty or 0)

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
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="equipment_line_id.currency_id",
        readonly=True,
    )

    @api.depends("unit_price", "qty")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.unit_price or 0.0) * (line.qty or 0)

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

    @api.depends("unit_price", "qty")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.unit_price or 0.0) * (line.qty or 0)

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
                "qo_line_ids": [
                    (0, 0, {
                        "cycle_type_id": l.cycle_type_id.id, "qty": l.qty,
                        "description": l.description, "unit_price": l.unit_price,
                    })
                    for l in self.qo_line_ids
                ],
                "qd_line_ids": [
                    (0, 0, {
                        "cycle_type_id": l.cycle_type_id.id, "qty": l.qty,
                        "description": l.description, "unit_price": l.unit_price,
                    })
                    for l in self.qd_line_ids
                ],
                "calib_line_ids": [
                    (0, 0, {
                        "malha_type_id": l.malha_type_id.id, "qty": l.qty,
                        "description": l.description, "unit_price": l.unit_price,
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
