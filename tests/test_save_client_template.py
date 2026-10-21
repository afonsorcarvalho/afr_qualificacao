# -*- coding: utf-8 -*-
"""Template de cotação por cliente — Task 4: "Gravar como padrão deste
cliente" na linha de equipamento do configurador."""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestSaveClientTemplate(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tpl = cls.env["afr.qualificacao.config.template"]

    def _line(self, so=None, **kw):
        so = so or self.env["sale.order"].create(
            {"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id})
        vals = {
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "do_qi": False, "do_qo": False, "do_qs": False,
            "work_hours_per_day": 4.0,
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id, "qty": 2,
                "unit_price": 100.0, "estimated_hours": 4.0})],
            "calib_line_ids": [(0, 0, {
                "malha_type_id": self.malha_temp.id, "qty": 3,
                "unit_price": 10.0, "estimated_hours": 1.0})],
        }
        vals.update(kw)
        return self.env["afr.qualificacao.configurator.equipment"].create(vals)

    def _user(self, manager):
        grp = "afr_qualificacao.group_afr_qualificacao_" + (
            "manager" if manager else "user")
        return self.env["res.users"].create({
            "name": "U %s" % grp, "login": "u_%s_%s" % (grp[-7:], manager),
            "groups_id": [(6, 0, [self.env.ref(grp).id,
                                  self.env.ref("base.group_user").id])],
        })

    def test_non_manager_blocked(self):
        line = self._line().with_user(self._user(False))
        with self.assertRaisesRegex(UserError, "Apenas gestores"):
            line.action_save_as_client_default()
        self.assertFalse(self._client_tpls())

    def test_manager_allowed(self):
        line = self._line().with_user(self._user(True))
        res = line.action_save_as_client_default()
        self.assertEqual(res["tag"], "display_notification")
        self.assertEqual(len(self._client_tpls()), 1)

    def test_confirm_non_manager_blocked(self):
        old = self.Tpl.create({
            "name": "old", "partner_id": self.partner.id,
            "equipment_category_id": self.category.id,
            "company_id": self.company.id})
        act = self._line().action_save_as_client_default()
        confirm = self.env[act["res_model"]].browse(act["res_id"])
        with self.assertRaisesRegex(UserError, "Apenas gestores"):
            confirm.with_user(self._user(False)).action_confirm()
        self.assertEqual(old.price_base, 0.0)

    def test_confirm_saves_displayed_values(self):
        old = self.Tpl.create({
            "name": "old", "partner_id": self.partner.id,
            "equipment_category_id": self.category.id,
            "company_id": self.company.id})
        line = self._line()
        act = line.action_save_as_client_default()
        confirm = self.env[act["res_model"]].browse(act["res_id"])
        self.assertAlmostEqual(confirm.new_price, 830.0, 2)
        line.qd_line_ids.unit_price = 999.0  # muda após abrir
        confirm.action_confirm()
        self.assertAlmostEqual(old.price_base, 830.0, 2)

    def test_confirm_stale_template_raises(self):
        old = self.Tpl.create({
            "name": "old", "partner_id": self.partner.id,
            "equipment_category_id": self.category.id,
            "company_id": self.company.id})
        act = self._line().action_save_as_client_default()
        confirm = self.env[act["res_model"]].browse(act["res_id"])
        old.active = False
        with self.assertRaises(UserError):
            confirm.action_confirm()

    def test_qd_points_only_from_same_category(self):
        other = self.env["engc.equipment.category"].create({"name": "Outra"})
        kind = self.env["afr.qualificacao.sensor.kind"].search([], limit=1)
        if not kind:
            return
        src = self.Tpl.create({
            "name": "src", "equipment_category_id": other.id,
            "company_id": self.company.id,
            "qd_point_ids": [(0, 0, {"sensor_kind_id": kind.id, "points": 5})]})
        self._line(config_template_id=src.id).action_save_as_client_default()
        self.assertFalse(self._client_tpls().qd_point_ids)

    def test_zero_price_flagged(self):
        line = self._line(qd_line_ids=[(5, 0, 0)], calib_line_ids=[(5, 0, 0)])
        res = line.action_save_as_client_default()
        self.assertIn("sem preço combinado", res["params"]["message"])

    def _client_tpls(self):
        return self.Tpl.search([
            ("partner_id", "=", self.partner.id),
            ("equipment_category_id", "=", self.category.id)])

    def test_creates_client_default(self):
        line = self._line()
        res = line.action_save_as_client_default()
        tpl = self._client_tpls()
        self.assertEqual(len(tpl), 1)
        self.assertEqual(tpl.company_id, line.wizard_id.company_id)
        self.assertEqual(tpl.qd_line_ids.cycle_type_id, self.cycle_cmax)
        self.assertEqual(tpl.qd_line_ids.qty, 2)
        self.assertEqual(tpl.calib_line_ids.malha_type_id, self.malha_temp)
        self.assertEqual(tpl.work_hours_per_day, 4.0)
        self.assertEqual(res["type"], "ir.actions.client")
        self.assertEqual(res["tag"], "display_notification")
        msg = res["params"]["message"]
        self.assertIn(self.category.name, msg)
        self.assertIn(self.partner.name, msg)
        self.assertTrue(msg.startswith("Padrão de"))

    def test_price_and_days_from_wizard_total(self):
        line = self._line()
        line.action_save_as_client_default()
        tpl = self._client_tpls()
        # 100*2*4 + 10*3*1 = 830 ; horas 8+3 = 11 ; 11/4 = 2.75 dias
        self.assertAlmostEqual(tpl.price_base, 830.0, 2)
        self.assertAlmostEqual(tpl.estimated_days, 2.75, 2)

    def test_price_and_days_from_section_targets(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        sec = self.env["sale.order.line"].create({
            "order_id": so.id, "display_type": "line_section",
            "name": "Eq", "equipment_id": self.equip1.id,
            "is_qualificacao_managed": True,
            "equipment_target_price": 5000.0, "equipment_target_days": 7.0,
        })
        self.assertTrue(sec)
        line = self._line(so=so)
        line.action_save_as_client_default()
        tpl = self._client_tpls()
        self.assertEqual(tpl.price_base, 5000.0)
        self.assertEqual(tpl.estimated_days, 7.0)

    def test_existing_asks_confirmation_then_updates_without_duplicate(self):
        old = self.Tpl.create({
            "name": "old", "partner_id": self.partner.id,
            "equipment_category_id": self.category.id,
            "company_id": self.company.id, "price_base": 1.0,
            "estimated_days": 1.0,
            "calib_line_ids": [(0, 0, {"malha_type_id": self.malha_press.id,
                                       "qty": 9})],
        })
        line = self._line()
        act = line.action_save_as_client_default()
        self.assertEqual(act["res_model"],
                         "afr.qualificacao.client.default.confirm")
        self.assertEqual(old.price_base, 1.0)  # nada gravado ainda
        confirm = self.env[act["res_model"]].browse(act["res_id"])
        self.assertIn(self.category.name, confirm.message)
        self.assertEqual(confirm.old_price, 1.0)
        self.assertAlmostEqual(confirm.new_price, 830.0, 2)
        res = confirm.action_confirm()
        self.assertEqual(res["tag"], "display_notification")
        self.assertEqual(self._client_tpls(), old)
        self.assertAlmostEqual(old.price_base, 830.0, 2)
        self.assertAlmostEqual(old.estimated_days, 2.75, 2)
        self.assertEqual(old.calib_line_ids.malha_type_id, self.malha_temp)
        self.assertEqual(len(old.calib_line_ids), 1)

    def test_archived_default_not_replaced(self):
        old = self.Tpl.create({
            "name": "old", "partner_id": self.partner.id,
            "equipment_category_id": self.category.id,
            "company_id": self.company.id, "active": False})
        res = self._line().action_save_as_client_default()
        self.assertEqual(res["tag"], "display_notification")
        self.assertEqual(len(self._client_tpls()), 1)
        self.assertTrue(old not in self._client_tpls())

    def test_requires_category(self):
        # category_id é NOT NULL no equipamento; a guarda cobre linha sem
        # equipamento/categoria resolvida.
        line = self._line().new({"wizard_id": self._line().wizard_id.id})
        with self.assertRaises(UserError):
            line.action_save_as_client_default()
        self.assertFalse(self._client_tpls())

    def test_save_as_template_still_copies_scope(self):
        line = self._line(do_qo=True)
        res = line.wizard_id.action_save_as_template()
        tpl = self.Tpl.browse(res["res_id"])
        self.assertEqual(tpl.qd_line_ids.qty, 2)
        self.assertEqual(tpl.calib_line_ids.qty, 3)
        self.assertFalse(tpl.partner_id)
