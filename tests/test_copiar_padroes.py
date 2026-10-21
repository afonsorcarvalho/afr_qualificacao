# -*- coding: utf-8 -*-
"""Task 8 — copiar padrões (templates de cotação) de outro cliente."""
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import AfrQualificacaoTestCommon

WIZ = "afr.qualificacao.copiar.padroes.wizard"


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestCopiarPadroes(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref(
            "afr_qualificacao.group_afr_qualificacao_manager")
        Tpl = cls.env["afr.qualificacao.config.template"]
        cls.cat2 = cls.env["engc.equipment.category"].create(
            {"name": "Estufa T8"})
        cls.src = cls.env["res.partner"].create(
            {"name": "Origem T8", "is_company": True})
        cls.dst = cls.env["res.partner"].create(
            {"name": "Destino T8", "is_company": True})
        cls.s1 = Tpl.create({
            "name": "S1", "partner_id": cls.src.id,
            "equipment_category_id": cls.category.id,
            "company_id": cls.company.id, "price_base": 1000.0,
            "estimated_days": 5.0, "do_qo": True,
            "qo_line_ids": [(0, 0, {"cycle_type_id": cls.cycle_cmax.id})]})
        cls.s2 = Tpl.create({
            "name": "S2", "partner_id": cls.src.id,
            "equipment_category_id": cls.cat2.id,
            "company_id": cls.company.id, "price_base": 400.0,
            "estimated_days": 2.0})
        cls.company2 = cls.env["res.company"].create({"name": "Outra Emp T8"})
        cls.s_co2 = Tpl.create({
            "name": "S3", "partner_id": cls.src.id,
            "equipment_category_id": cls.category.id,
            "company_id": cls.company2.id, "price_base": 77.0})

    def _wiz(self, user=None):
        Wiz = self.env[WIZ]
        if user:
            Wiz = Wiz.with_user(user)
        return Wiz.with_context(default_partner_id=self.dst.id).create(
            {"partner_id": self.dst.id, "source_partner_id": self.src.id})

    def _dst_tpls(self):
        return self.env["afr.qualificacao.config.template"].search(
            [("partner_id", "=", self.dst.id)])

    def test_lines_only_current_company(self):
        wiz = self._wiz()
        self.assertEqual(wiz.line_ids.template_id, self.s1 | self.s2)

    def test_copy_creates_templates(self):
        self._wiz().action_copy()
        tpls = self._dst_tpls()
        self.assertEqual(len(tpls), 2)
        t1 = tpls.filtered(lambda t: t.equipment_category_id == self.category)
        self.assertEqual(t1.price_base, 1000.0)
        self.assertEqual(t1.estimated_days, 5.0)
        self.assertTrue(t1.do_qo)
        self.assertEqual(t1.qo_line_ids.cycle_type_id, self.cycle_cmax)
        self.assertNotEqual(t1.qo_line_ids, self.s1.qo_line_ids)
        self.assertEqual(t1.company_id, self.company)

    def test_source_untouched(self):
        self._wiz().action_copy()
        self.assertEqual(self.s1.partner_id, self.src)
        self.assertEqual(self.s1.price_base, 1000.0)
        self.assertEqual(len(self.s1.qo_line_ids), 1)

    def test_other_company_ignored(self):
        self._wiz().action_copy()
        self.assertFalse(self._dst_tpls().filtered(
            lambda t: t.price_base == 77.0))

    def test_unchecked_not_copied(self):
        wiz = self._wiz()
        wiz.line_ids.filtered(lambda l: l.template_id == self.s2).copiar = False
        wiz.action_copy()
        self.assertEqual(self._dst_tpls().equipment_category_id, self.category)

    def test_replace_existing(self):
        old = self.env["afr.qualificacao.config.template"].create({
            "name": "Antigo", "partner_id": self.dst.id,
            "equipment_category_id": self.category.id,
            "company_id": self.company.id, "price_base": 10.0,
            "estimated_days": 1.0, "do_qi": True,
            "qo_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id}),
                            (0, 0, {"cycle_type_id": self.cycle_cmax.id})]})
        wiz = self._wiz()
        line = wiz.line_ids.filtered(lambda l: l.template_id == self.s1)
        self.assertEqual(line.existente_id, old)
        self.assertIn("10", line.aviso)
        self.assertIn("1", line.aviso)
        wiz.action_copy()
        tpls = self._dst_tpls()
        self.assertEqual(len(tpls), 2)  # não duplicou
        self.assertTrue(old.exists())
        self.assertEqual(old.price_base, 1000.0)
        self.assertEqual(old.estimated_days, 5.0)
        self.assertTrue(old.do_qo)
        self.assertFalse(old.do_qi)
        self.assertEqual(len(old.qo_line_ids), 1)

    def test_same_partner_blocked(self):
        with self.assertRaisesRegex(UserError, "diferente"):
            self.env[WIZ].with_context(default_partner_id=self.dst.id).create(
                {"partner_id": self.dst.id,
                 "source_partner_id": self.dst.id}).action_copy()

    def test_non_manager_blocked(self):
        user = self.env["res.users"].create({
            "name": "Tec T8", "login": "tec_copiar_t8",
            "groups_id": [(6, 0, [
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
                self.env.ref("base.group_user").id])]})
        wiz = self._wiz()
        with self.assertRaisesRegex(UserError, "Apenas gestores"):
            wiz.with_user(user).action_copy()
        with self.assertRaisesRegex(UserError, "Apenas gestores"):
            self.dst.with_user(user).action_afr_copiar_padroes_wizard()
        self.assertFalse(self._dst_tpls())

    def test_partner_action(self):
        act = self.dst.action_afr_copiar_padroes_wizard()
        self.assertEqual(act["res_model"], WIZ)
        self.assertEqual(act["context"]["default_partner_id"], self.dst.id)

    def test_form_flow(self):
        """Pelo form (como o navegador): escolher a origem preenche a lista."""
        f = Form(self.env[WIZ].with_context(default_partner_id=self.dst.id))
        f.source_partner_id = self.src
        wiz = f.save()
        self.assertEqual(wiz.line_ids.template_id, self.s1 | self.s2)
        wiz.action_copy()
        self.assertEqual(len(self._dst_tpls()), 2)
