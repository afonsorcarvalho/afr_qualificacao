"""Extensão de sale.order para fluxo de qualificação quote-first.

- Botão `Configurar Qualificações` no header abre wizard que gera linhas SO
- Stat buttons mostram qualificações + OSs geradas
- `action_confirm()` override dispara `_create_qualificacoes_from_lines()`
  que materializa engc.os (1/equipamento) + afr.qualificacao (1/equip×tipo)
  + sub-records (cycles/malhas explodidos por qty).
"""

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    qualificacao_ids = fields.One2many(
        comodel_name="afr.qualificacao",
        inverse_name="sale_order_id",
        string="Qualificações",
    )
    qualificacao_count = fields.Integer(
        compute="_compute_qualificacao_count",
        string="Total de Qualificações",
    )
    engc_os_ids = fields.One2many(
        comodel_name="engc.os",
        inverse_name="sale_order_id",
        string="Ordens de Serviço",
    )
    engc_os_count = fields.Integer(
        compute="_compute_engc_os_count",
        string="Total de OSs",
    )

    @api.depends("qualificacao_ids")
    def _compute_qualificacao_count(self):
        for order in self:
            order.qualificacao_count = len(order.qualificacao_ids)

    @api.depends("engc_os_ids")
    def _compute_engc_os_count(self):
        for order in self:
            order.engc_os_count = len(order.engc_os_ids)

    # ------------------------------------------------------------------
    # Configurador (abre wizard)
    # ------------------------------------------------------------------
    def action_open_configurator(self):
        """Abre wizard configurador de qualificações em modal fullscreen."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_(
                "Defina o cliente antes de abrir o configurador de qualificações."
            ))
        if self.state not in ("draft", "sent"):
            raise UserError(_(
                "Configurador disponível apenas em orçamentos (draft/sent)."
            ))
        wizard = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": self.id,
        })
        wizard._load_from_existing_lines()
        return {
            "type": "ir.actions.act_window",
            "name": _("Configurar Qualificações"),
            "res_model": "afr.qualificacao.configurator",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

    def action_view_qualificacoes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Qualificações"),
            "res_model": "afr.qualificacao",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.qualificacao_ids.ids)],
        }

    def action_view_engc_os(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Ordens de Serviço"),
            "res_model": "engc.os",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.engc_os_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Confirm → gera engc.os + afr.qualificacao + sub-records
    # ------------------------------------------------------------------
    def action_confirm(self):
        """Override: após confirmar SO, gera estrutura de qualificações."""
        result = super().action_confirm()
        for order in self:
            order._create_qualificacoes_from_lines()
        return result

    def _create_qualificacoes_from_lines(self):
        """Materializa engc.os + afr.qualificacao + sub-records.

        Agrupamento:
        - 1 engc.os por equipamento (campo logístico, agendamento)
        - 1 afr.qualificacao por (equipamento, qualification_type)
        - Para QD: N afr.qualificacao.cycle por linha SO (qty=N)
        - Para Calib: N afr.qualificacao.malha por linha SO
        - Para QI/QO/QS: sem sub-records (1 linha = 1 qualificação)

        Idempotência: skip se afr_qualificacao_id já populado (evita
        re-gerar em re-confirm).
        """
        self.ensure_one()
        managed = self.order_line.filtered("is_qualificacao_managed")
        if not managed:
            return
        # Skip linhas já processadas
        managed = managed.filtered(lambda l: not l.afr_qualificacao_id)
        if not managed:
            return

        EngcOs = self.env["engc.os"]
        Qualif = self.env["afr.qualificacao"]
        Cycle = self.env["afr.qualificacao.cycle"]
        Malha = self.env["afr.qualificacao.malha"]

        # Agrupa linhas por equipamento
        by_equipment = defaultdict(lambda: self.env["sale.order.line"])
        for line in managed:
            by_equipment[line.equipment_id] |= line

        # Por equipamento: cria engc.os (se ainda não houver pra esse equip+SO)
        for equipment, equip_lines in by_equipment.items():
            existing_os = self.engc_os_ids.filtered(
                lambda o: o.equipment_id == equipment
            )
            engc_os = existing_os[:1] if existing_os else EngcOs.create(
                self._prepare_engc_os_values(equipment)
            )

            # Por (equipment, qualification_type) único: cria afr.qualificacao
            by_type = defaultdict(lambda: self.env["sale.order.line"])
            for line in equip_lines:
                by_type[line.qualification_type] |= line

            for qtype, type_lines in by_type.items():
                qualif = Qualif.create(
                    self._prepare_qualificacao_values(equipment, qtype, engc_os)
                )
                # back-ref nas linhas SO
                type_lines.write({"afr_qualificacao_id": qualif.id})

                # Sub-records explodidos por qty
                if qtype == "performance":
                    for line in type_lines:
                        qty = int(line.product_uom_qty or 0)
                        for seq in range(1, qty + 1):
                            Cycle.create({
                                "qualificacao_id": qualif.id,
                                "cycle_type_id": line.cycle_type_id.id,
                                "sale_order_line_id": line.id,
                                "sequence": seq * 10,
                            })
                elif qtype == "calibration":
                    for line in type_lines:
                        qty = int(line.product_uom_qty or 0)
                        for seq in range(1, qty + 1):
                            Malha.create({
                                "qualificacao_id": qualif.id,
                                "malha_type_id": line.malha_type_id.id,
                                "sale_order_line_id": line.id,
                                "sequence": seq * 10,
                            })
                # QI/QO/QS: sem sub-records

    def _prepare_engc_os_values(self, equipment):
        """Hook: valores para criar engc.os de um equipamento."""
        self.ensure_one()
        now = fields.Datetime.now()
        return {
            "equipment_id": equipment.id,
            "client_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "sale_order_id": self.id,
            "origin": self.name,
            "maintenance_type": "qualification",
            "who_executor": "own",
            "date_request": now,
            "date_scheduled": now,
            "solicitante": self.partner_id.name or self.name,
        }

    def _prepare_qualificacao_values(self, equipment, qualification_type, engc_os):
        """Hook: valores para criar afr.qualificacao."""
        self.ensure_one()
        return {
            "name": _("Q-%s-%s-%s") % (
                self.name,
                equipment.id,
                qualification_type[:3].upper(),
            ),
            "equipment_id": equipment.id,
            "partner_id": self.partner_id.id,
            "qualification_type": qualification_type,
            "company_id": self.company_id.id,
            "sale_order_id": self.id,
            "engc_os_id": engc_os.id,
        }
