# -*- coding: utf-8 -*-
"""Task 7: "Gravar como padrão deste cliente" na linha de seção da cotação
(qualquer estado do SO, só gestor)."""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestSaveClientDefaultFromSO(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tpl = cls.env["afr.qualificacao.config.template"]
        cls.env.user.groups_id |= cls.env.ref(
            "afr_qualificacao.group_afr_qualificacao_manager")

    def _wiz_line(self, so):
        wiz = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id})
        return self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "do_qi": False, "do_qo": False, "do_qs": False,
            "work_hours_per_day": 4.0,
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id, "qty": 2,
                "unit_price": 100.0, "estimated_hours": 4.0})],
            "calib_line_ids": [(0, 0, {
                "malha_type_id": self.malha_temp.id, "qty": 3,
                "unit_price": 10.0, "estimated_hours": 1.0})],
        })

    def _so_with_section(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self._wiz_line(so).wizard_id.action_apply()
        sec = so.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == self.equip1)
        self.assertEqual(len(sec), 1)
        return so, sec

    def _client_tpls(self):
        return self.Tpl.search([
            ("partner_id", "=", self.partner.id),
            ("equipment_category_id", "=", self.category.id)])

    def _user(self, manager):
        grp = "afr_qualificacao.group_afr_qualificacao_" + (
            "manager" if manager else "user")
        return self.env["res.users"].create({
            "name": "U %s" % grp, "login": "so_%s_%s" % (grp[-7:], manager),
            "groups_id": [(6, 0, [self.env.ref(grp).id,
                                  self.env.ref("base.group_user").id,
                                  self.env.ref("sales_team.group_sale_salesman_all_leads").id])],
        })

    def _scope(self, tpl):
        return (
            tpl.do_qi, tpl.do_qo, tpl.do_qs, tpl.work_hours_per_day,
            sorted((l.cycle_type_id.id, l.qty, l.estimated_hours)
                   for l in tpl.qd_line_ids),
            sorted((l.cycle_type_id.id, l.qty, l.estimated_hours)
                   for l in tpl.qo_line_ids),
            sorted((l.malha_type_id.id, l.qty, l.estimated_hours)
                   for l in tpl.calib_line_ids),
        )

    def test_confirmed_so_saves_default(self):
        so, sec = self._so_with_section()
        so.write({"state": "sale"})
        sec.equipment_target_price = 4321.0
        sec.equipment_target_days = 3.5
        res = sec.action_save_as_client_default()
        self.assertEqual(res["tag"], "display_notification")
        tpl = self._client_tpls()
        self.assertEqual(len(tpl), 1)
        self.assertEqual(tpl.price_base, 4321.0)
        self.assertEqual(tpl.estimated_days, 3.5)
        self.assertEqual(tpl.qd_line_ids.cycle_type_id, self.cycle_cmax)

    def test_no_targets_uses_section_totals(self):
        so, sec = self._so_with_section()
        sec.action_save_as_client_default()
        tpl = self._client_tpls()
        self.assertAlmostEqual(tpl.price_base, sec.equipment_subtotal, 2)
        self.assertAlmostEqual(
            tpl.estimated_days,
            sec.equipment_current_hours / (sec.work_hours_per_day or 8.0), 2)

    def test_non_manager_blocked(self):
        so, sec = self._so_with_section()
        with self.assertRaisesRegex(UserError, "Apenas gestores"):
            sec.with_user(self._user(False)).action_save_as_client_default()
        self.assertFalse(self._client_tpls())

    def test_non_section_line_rejected(self):
        so, sec = self._so_with_section()
        line = so.order_line.filtered(lambda l: not l.display_type)[:1]
        with self.assertRaises(UserError):
            line.action_save_as_client_default()

    def test_scope_equals_configurator(self):
        so, sec = self._so_with_section()
        line = self._wiz_line(self.env["sale.order"].create(
            {"partner_id": self.partner.id}))
        line.action_save_as_client_default()
        tpl = self._client_tpls()
        scope_cfg = self._scope(tpl)
        tpl.unlink()
        sec.action_save_as_client_default()
        self.assertEqual(self._scope(self._client_tpls()), scope_cfg)

    def test_existing_confirm_returns_to_so(self):
        so, sec = self._so_with_section()
        so.write({"state": "sale"})
        old = self.Tpl.create({
            "name": "old", "partner_id": self.partner.id,
            "equipment_category_id": self.category.id,
            "company_id": self.company.id, "price_base": 1.0})
        sec.equipment_target_price = 900.0
        act = sec.action_save_as_client_default()
        self.assertEqual(act["res_model"],
                         "afr.qualificacao.client.default.confirm")
        confirm = self.env[act["res_model"]].browse(act["res_id"])
        self.assertEqual(confirm.old_price, 1.0)
        self.assertEqual(confirm.new_price, 900.0)
        self.assertEqual(confirm.action_cancel()["type"],
                         "ir.actions.act_window_close")
        res = confirm.action_confirm()
        self.assertEqual(res["params"]["next"]["type"],
                         "ir.actions.act_window_close")
        self.assertEqual(old.price_base, 900.0)
        self.assertEqual(self._client_tpls(), old)
