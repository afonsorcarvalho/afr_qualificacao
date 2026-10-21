# -*- coding: utf-8 -*-
"""Task 5 — reajuste dos preços combinados (índice BCB / % / valor),
histórico e atividade de aniversário."""
from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import AfrQualificacaoTestCommon
from ..models import bcb_index

GET = "odoo.addons.afr_qualificacao.models.bcb_index._http_get_json"


def _serie(values):
    return [{"data": "01/%02d/2025" % (i + 1), "valor": "%s" % v}
            for i, v in enumerate(values)]


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestReajuste(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref(
            "afr_qualificacao.group_afr_qualificacao_manager")
        Tpl = cls.env["afr.qualificacao.config.template"]
        cls.cat2 = cls.env["engc.equipment.category"].create(
            {"name": "Estufa T5"})
        cls.t1 = Tpl.create({
            "name": "A", "partner_id": cls.partner.id,
            "equipment_category_id": cls.category.id,
            "company_id": cls.company.id, "price_base": 1000.0})
        cls.t2 = Tpl.create({
            "name": "B", "partner_id": cls.partner.id,
            "equipment_category_id": cls.cat2.id,
            "company_id": cls.company.id, "price_base": 333.33})
        cls.other = cls.env["res.partner"].create(
            {"name": "Outro", "is_company": True})
        cls.t_other = Tpl.create({
            "name": "C", "partner_id": cls.other.id,
            "equipment_category_id": cls.category.id,
            "company_id": cls.company.id, "price_base": 500.0})
        cls.company2 = cls.env["res.company"].create({"name": "Outra Emp T5"})
        cls.t_co2 = Tpl.create({
            "name": "D", "partner_id": cls.partner.id,
            "equipment_category_id": cls.category.id,
            "company_id": cls.company2.id, "price_base": 900.0})
        cls.t_generic = Tpl.create({
            "name": "G", "equipment_category_id": cls.category.id,
            "company_id": cls.company.id, "price_base": 700.0})

    def _wiz(self, **kw):
        vals = {"partner_id": self.partner.id}
        vals.update(kw)
        return self.env["afr.qualificacao.reajuste.wizard"].with_context(
            default_partner_id=self.partner.id).create(vals)

    # --- BCB -------------------------------------------------------------
    def test_accumulated_math_and_period(self):
        with patch(GET, return_value=_serie([1.0] * 12)) as m:
            pct = bcb_index.accumulated_12m(433, date(2026, 3, 15))
        self.assertAlmostEqual(pct, (1.01 ** 12 - 1) * 100, places=6)
        url = m.call_args[0][0]
        self.assertIn("bcdata.sgs.433", url)
        self.assertIn("dataInicial=01/03/2025", url)
        self.assertIn("dataFinal=28/02/2026", url)

    def test_accumulated_incomplete_raises(self):
        with patch(GET, return_value=_serie([0.5] * 11)):
            with self.assertRaises(UserError):
                bcb_index.accumulated_12m(433, date(2026, 3, 1))

    def test_bcb_failure_manual_mode(self):
        with patch(GET, side_effect=UserError("Falha de rede")):
            wiz = self._wiz(tipo="indice", indice="ipca")
            wiz._fetch_index()
        self.assertTrue(wiz.bcb_aviso)
        self.assertEqual(wiz.percentual, 0.0)
        wiz.percentual = 10.0
        wiz.action_confirm()
        self.assertAlmostEqual(self.t1.price_base, 1100.0)

    # --- aplicação -------------------------------------------------------
    def test_index_application(self):
        with patch(GET, return_value=_serie([1.0] * 12)):
            wiz = self._wiz(tipo="indice", indice="igpm")
            wiz._fetch_index()
        self.assertFalse(wiz.bcb_aviso)
        self.assertAlmostEqual(wiz.percentual, 12.682503, places=5)
        wiz.action_confirm()
        self.assertAlmostEqual(self.t1.price_base, 1126.83)
        hist = self.partner.afr_reajuste_ids
        self.assertEqual(hist.indice, "igpm")
        self.assertTrue(hist.periodo)

    def test_percent_application_and_preview(self):
        wiz = self._wiz(tipo="percentual", percentual=5.0)
        preview = {l.template_id: l.depois for l in wiz.line_ids}
        self.assertEqual(set(preview), {self.t1, self.t2})
        self.assertAlmostEqual(preview[self.t2], 350.0)
        wiz.action_confirm()
        self.assertAlmostEqual(self.t1.price_base, 1050.0)
        self.assertAlmostEqual(self.t2.price_base, 350.0)
        for tpl, dep in preview.items():
            self.assertAlmostEqual(tpl.price_base, dep)

    def test_value_application_history_and_isolation(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.env[
                "product.product"].create({"name": "P"}).id,
                "price_unit": 77.0})]})
        wiz = self._wiz(tipo="valor", valor=100.0)
        wiz.action_confirm()
        self.assertAlmostEqual(self.t1.price_base, 1100.0)
        self.assertAlmostEqual(self.t2.price_base, 433.33)
        self.assertEqual(self.t_other.price_base, 500.0)
        self.assertEqual(self.t_generic.price_base, 700.0)
        self.assertEqual(self.t_co2.price_base, 900.0)
        self.assertEqual(so.order_line.price_unit, 77.0)
        hist = self.partner.afr_reajuste_ids
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist.tipo, "valor")
        self.assertEqual(hist.user_id, self.env.user)
        rows = {l.template_id: (l.valor_antigo, l.valor_novo)
                for l in hist.line_ids}
        self.assertEqual(rows[self.t1], (1000.0, 1100.0))
        self.assertEqual(len(rows), 2)
        self.assertIn("Reajuste", self.partner.message_ids[0].body)

    def test_non_manager_blocked(self):
        user = self.env["res.users"].create({
            "name": "Tec", "login": "tec_reajuste",
            "groups_id": [(6, 0, [
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
                self.env.ref("base.group_user").id])]})
        wiz = self._wiz(tipo="percentual", percentual=5.0)
        with self.assertRaisesRegex(UserError, "Apenas gestores"):
            wiz.with_user(user).action_confirm()
        self.assertEqual(self.t1.price_base, 1000.0)

    def test_form_view_save_and_confirm(self):
        """Pelo form (como o navegador): salvar o wizard não pode falhar
        por causa das linhas da prévia."""
        with patch(GET, return_value=_serie([1.0] * 12)):
            f = Form(self.env["afr.qualificacao.reajuste.wizard"].with_context(
                default_partner_id=self.partner.id))
            f.tipo = "percentual"
            f.percentual = 10.0
            wiz = f.save()
        self.assertEqual(wiz.line_ids.template_id, self.t1 | self.t2)
        wiz.action_confirm()
        self.assertAlmostEqual(self.t1.price_base, 1100.0)

    def test_manager_user_confirm(self):
        """Gestor sem superusuário consegue aplicar (caminho de ACL real)."""
        user = self.env["res.users"].create({
            "name": "Gestor T5", "login": "gestor_reajuste",
            "email": "gestor.t5@example.com",
            "company_id": self.company.id,
            "company_ids": [(6, 0, [self.company.id])],
            "groups_id": [(6, 0, [
                self.env.ref("afr_qualificacao.group_afr_qualificacao_manager").id,
                self.env.ref("base.group_user").id])]})
        wiz = self.env["afr.qualificacao.reajuste.wizard"].with_user(
            user).with_company(self.company).with_context(
            default_partner_id=self.partner.id).create(
            {"partner_id": self.partner.id, "tipo": "percentual",
             "percentual": 10.0})
        wiz.action_confirm()
        self.assertAlmostEqual(self.t1.price_base, 1100.0)
        hist = self.partner.afr_reajuste_ids
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist.user_id, user)
        self.assertEqual(self.partner.message_ids[0].author_id,
                         user.partner_id)

    # --- cron ------------------------------------------------------------
    def test_cron_activity_once(self):
        today = fields.Date.context_today(self.env.user)
        self.partner.afr_reajuste_data = today.replace(year=today.year - 1)
        self.other.afr_reajuste_data = date(2020, 1, 1) if (
            today.month, today.day) != (1, 1) else date(2020, 1, 2)
        Partner = self.env["res.partner"]
        Partner._cron_afr_reajuste_activity()
        Partner._cron_afr_reajuste_activity()
        acts = self.env["mail.activity"].search([
            ("res_model", "=", "res.partner"),
            ("summary", "=", "Reajustar preços combinados")])
        self.assertEqual(acts.mapped("res_id"), [self.partner.id])
        self.assertEqual(acts.user_id, self.env.ref("base.user_admin"))

    def test_feb29_fires_on_feb28_non_leap(self):
        self.partner.afr_reajuste_data = date(2024, 2, 29)
        P = self.env["res.partner"]
        P._cron_afr_reajuste_activity(today=date(2027, 2, 27))
        P._cron_afr_reajuste_activity(today=date(2027, 2, 28))
        P._cron_afr_reajuste_activity(today=date(2027, 3, 1))
        acts = self.env["mail.activity"].search([
            ("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id),
            ("summary", "=", "Reajustar preços combinados")])
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts.date_deadline, date(2027, 2, 28))

    def test_confirm_restores_cleared_periodo(self):
        with patch(GET, return_value=_serie([1.0] * 12)):
            wiz = self._wiz(tipo="indice", indice="ipca")
            wiz._fetch_index()
        wiz.periodo = False
        wiz.action_confirm()
        self.assertTrue(self.partner.afr_reajuste_ids.periodo)

    def test_ref_date_most_recent_anniversary(self):
        today = fields.Date.context_today(self.env.user)
        wiz = self._wiz(tipo="percentual", percentual=1.0)
        self.partner.afr_reajuste_data = date(2000, today.month, 1)
        self.assertEqual(wiz._ref_date(), today.replace(day=1))
        nxt = today.month % 12 + 1
        if nxt != 1:  # aniversário ainda não chegou neste ano
            self.partner.afr_reajuste_data = date(2000, nxt, 1)
            self.assertEqual(wiz._ref_date(), date(today.year - 1, nxt, 1))
