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

    @api.depends("equipment_line_ids.subtotal")
    def _compute_total_estimated(self):
        for wiz in self:
            wiz.total_estimated = sum(wiz.equipment_line_ids.mapped("subtotal"))

    # ------------------------------------------------------------------
    # Carrega matriz a partir de linhas SO existentes (idempotência)
    # ------------------------------------------------------------------
    def _load_from_existing_lines(self):
        """Lê linhas SO managed, agrupa por equipment_id, popula equipment_line_ids."""
        self.ensure_one()
        managed = self.sale_order_id.order_line.filtered("is_qualificacao_managed")
        if not managed:
            return
        by_equip = defaultdict(lambda: {
            "qi": False, "qo": False, "qs": False, "qd": [], "calib": [],
        })
        for line in managed:
            bucket = by_equip[line.equipment_id]
            qt = line.qualification_type
            if qt == "installation":
                bucket["qi"] = True
            elif qt == "operational":
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
                eq_line.do_qi or eq_line.do_qo or eq_line.do_qs
                or eq_line.qd_line_ids or eq_line.calib_line_ids
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

            # QI/QO/QS via type.config
            for flag, qtype in (
                ("do_qi", "installation"),
                ("do_qo", "operational"),
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
                new_lines.append((0, 0, vals))

            # QD — 1 linha por cycle_type
            for qd in eq_line.qd_line_ids:
                new_lines.append((0, 0, {
                    "order_id": so.id,
                    "product_id": qd.cycle_type_id.product_id.id,
                    "product_uom_qty": qd.qty,
                    "is_qualificacao_managed": True,
                    "qualification_type": "performance",
                    "equipment_id": equip.id,
                    "cycle_type_id": qd.cycle_type_id.id,
                }))

            # Calib — 1 linha por malha_type
            for c in eq_line.calib_line_ids:
                new_lines.append((0, 0, {
                    "order_id": so.id,
                    "product_id": c.malha_type_id.product_id.id,
                    "product_uom_qty": c.qty,
                    "is_qualificacao_managed": True,
                    "qualification_type": "calibration",
                    "equipment_id": equip.id,
                    "malha_type_id": c.malha_type_id.id,
                }))

        so.write({"order_line": new_lines})
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

    @api.depends(
        "do_qi", "do_qo", "do_qs",
        "qd_line_ids.subtotal", "calib_line_ids.subtotal",
        "equipment_id",
    )
    def _compute_subtotal(self):
        TypeConfig = self.env["afr.qualificacao.type.config"]
        for el in self:
            total = 0.0
            for flag, qtype in (
                ("do_qi", "installation"),
                ("do_qo", "operational"),
                ("do_qs", "software"),
            ):
                if not el[flag]:
                    continue
                cfg = TypeConfig.get_config_for(qtype, el.wizard_id.company_id)
                if cfg:
                    total += cfg.default_unit_price or (
                        cfg.service_product_id.list_price if cfg.service_product_id else 0.0
                    )
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
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": l.cycle_type_id.id, "qty": l.qty})
                for l in self.qd_line_ids
            ],
            "calib_line_ids": [
                (0, 0, {"malha_type_id": l.malha_type_id.id, "qty": l.qty})
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
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="equipment_line_id.currency_id",
        readonly=True,
    )

    @api.depends("cycle_type_id.product_id.list_price", "qty")
    def _compute_subtotal(self):
        for line in self:
            price = line.cycle_type_id.product_id.list_price if line.cycle_type_id else 0.0
            line.subtotal = price * (line.qty or 0)

    @api.constrains("qty")
    def _check_qty_positive(self):
        for line in self:
            if line.qty < 1:
                raise ValidationError(_("Quantidade de ciclos deve ser ≥ 1."))


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
    qty = fields.Integer(string="Quantidade", default=1, required=True)
    subtotal = fields.Monetary(
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="equipment_line_id.currency_id",
        readonly=True,
    )

    @api.depends("malha_type_id.product_id.list_price", "qty")
    def _compute_subtotal(self):
        for line in self:
            price = line.malha_type_id.product_id.list_price if line.malha_type_id else 0.0
            line.subtotal = price * (line.qty or 0)

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
                "qd_line_ids": [
                    (0, 0, {"cycle_type_id": l.cycle_type_id.id, "qty": l.qty})
                    for l in self.qd_line_ids
                ],
                "calib_line_ids": [
                    (0, 0, {"malha_type_id": l.malha_type_id.id, "qty": l.qty})
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
    qty = fields.Integer(string="Quantidade", default=1, required=True)


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
    qty = fields.Integer(string="Quantidade", default=1, required=True)
