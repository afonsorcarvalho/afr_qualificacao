# -*- coding: utf-8 -*-
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestOptionalWizard(AfrQualificacaoTestCommon):

    def _wizard(self, so):
        return self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id})

    def _svc_optional(self):
        # um afr.proposal.optional do catálogo (cria produto serviço + registro)
        prod = self.env["product.product"].create(
            {"name": "Pasta Opt", "type": "service", "sale_ok": True,
             "list_price": 150.0})
        return self.env["afr.proposal.optional"].create({
            "name": "Pasta impressa", "code": "OPT-T", "kind": "folder",
            "product_id": prod.id, "default_price": 150.0, "default_qty": 1.0})

    def _equip_line(self, wiz):
        return self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id, "do_qi": True})

    def test_wizard_service_optional_generates_line(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        opt = self._svc_optional()
        self.env["afr.qualificacao.configurator.optional"].create({
            "wizard_id": wiz.id, "optional_id": opt.id, "qty": 1.0,
            "unit_price": 150.0, "accepted": False})
        wiz.action_apply()
        line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and not l.qualification_type)
        self.assertEqual(len(line), 1)
        self.assertFalse(line.optional_accepted)
        self.assertEqual(line.product_uom_qty, 0.0)

    def test_wizard_service_optional_accepted_sums(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        opt = self._svc_optional()
        self.env["afr.qualificacao.configurator.optional"].create({
            "wizard_id": wiz.id, "optional_id": opt.id, "qty": 2.0,
            "unit_price": 150.0, "accepted": True})
        wiz.action_apply()
        line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and not l.qualification_type)
        self.assertEqual(line.product_uom_qty, 2.0)
        self.assertEqual(line.price_subtotal, 300.0)

    def test_wizard_qualif_optional_not_accepted(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 2,
            "estimated_hours": 2.0, "accepted": False})
        wiz.action_apply()
        line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.qualification_type)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_uom_qty, 0.0)
        so.action_confirm()
        # A QI do equipamento (do_qi) é esperada; o opcional performance NÃO
        # aceito não deve gerar a sua qualificação.
        self.assertFalse(so.qualificacao_ids.filtered(
            lambda q: q.qualification_type == "performance"))

    def test_wizard_qualif_optional_accepted_generates(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 2,
            "estimated_hours": 2.0, "accepted": True})
        wiz.action_apply()
        line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.qualification_type)
        self.assertEqual(line.product_uom_qty, 4.0)  # 2 ciclos × 2h
        so.action_confirm()
        self.assertTrue(so.qualificacao_ids)

    def test_load_roundtrip_optionals(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        opt = self._svc_optional()
        self.env["afr.qualificacao.configurator.optional"].create({
            "wizard_id": wiz.id, "optional_id": opt.id, "qty": 1.0,
            "unit_price": 150.0, "accepted": False})
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 1,
            "estimated_hours": 2.0, "accepted": False})
        wiz.action_apply()
        wiz2 = self._wizard(so)
        wiz2._load_from_existing_lines()
        self.assertEqual(len(wiz2.optional_service_ids), 1)
        self.assertEqual(len(wiz2.optional_qualif_ids), 1)

    def test_reapply_preserves_optionals(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self._wizard(so)
        self._equip_line(wiz)
        opt = self._svc_optional()
        self.env["afr.qualificacao.configurator.optional"].create({
            "wizard_id": wiz.id, "optional_id": opt.id, "qty": 1.0,
            "unit_price": 150.0, "accepted": True})
        wiz.action_apply()
        n1 = len(so.order_line.filtered("is_proposal_optional"))
        wiz2 = self._wizard(so)
        wiz2._load_from_existing_lines()
        wiz2.action_apply()
        opt2 = so.order_line.filtered("is_proposal_optional")
        n2 = len(opt2)
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 1)
        # estado preservado: aceito + qty faturada intactos após reapply
        self.assertTrue(opt2.optional_accepted)
        self.assertEqual(opt2.product_uom_qty, 1.0)
        self.assertTrue(opt2.optional_id)
