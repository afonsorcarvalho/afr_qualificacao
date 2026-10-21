# -*- coding: utf-8 -*-
"""Task 13 — totais do configurador == seção da cotação após action_apply;
padrão do cliente preserva as flags de Parte 01."""
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestWizardSoParity(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref(
            "afr_qualificacao.group_afr_qualificacao_manager")
        TC = cls.env["afr.qualificacao.type.config"]
        for qt, hours in (("installation", 1.5), ("operational", 2.25)):
            cfg = TC.get_config_for(qt, cls.company)
            cfg.estimated_hours = hours
            # default_unit_price diverge do lst_price do produto: o apply usa
            # o lst_price (variante Parte 01), o wizard precisa usar o mesmo.
            cfg.default_unit_price = 333.0

    def _wiz_line(self, so=None, **kw):
        so = so or self.env["sale.order"].create(
            {"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id})
        vals = {
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "do_qi": True, "do_qo_part01": True, "work_hours_per_day": 8.0,
            "qo_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_qo_test.id, "qty": 3,
                "unit_price": 50.0, "estimated_hours": 2.0})],
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id, "qty": 2,
                "unit_price": 100.0, "estimated_hours": 4.0})],
            "calib_line_ids": [(0, 0, {
                "malha_type_id": self.malha_temp.id, "qty": 3,
                "unit_price": 10.0, "estimated_hours": 1.0})],
        }
        vals.update(kw)
        return self.env["afr.qualificacao.configurator.equipment"].create(vals)

    def _section(self, so):
        return so.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == self.equip1)

    def _assert_parity(self, line):
        subtotal, hours = line.subtotal, line.estimated_hours_total
        so = line.wizard_id.sale_order_id
        line.wizard_id.action_apply()
        sec = self._section(so)
        self.assertAlmostEqual(subtotal, sec.equipment_subtotal, 2)
        self.assertAlmostEqual(hours, sec.equipment_current_hours, 2)
        return so, sec

    def test_parity_full_scope(self):
        line = self._wiz_line()
        so, sec = self._assert_parity(line)
        # QI P01 1000 + QO P01 1200 + 300 + 800 + 30
        self.assertAlmostEqual(sec.equipment_subtotal, 3330.0, 2)
        # 1.5 + 2.25 + 6 + 8 + 3
        self.assertAlmostEqual(sec.equipment_current_hours, 20.75, 2)

    def test_parity_declined_part01(self):
        line = self._wiz_line(qi_part01_declined=True,
                              qo_part01_declined=True)
        so, sec = self._assert_parity(line)
        self.assertAlmostEqual(sec.equipment_subtotal, 1130.0, 2)
        self.assertAlmostEqual(sec.equipment_current_hours, 17.0, 2)

    def test_parity_with_qs(self):
        self._assert_parity(self._wiz_line(do_qs=True))

    def test_client_default_roundtrip_keeps_qo_part01(self):
        line = self._wiz_line(qi_part01_declined=True)
        line.action_save_as_client_default()
        tpl = self.env["afr.qualificacao.config.template"].search([
            ("partner_id", "=", self.partner.id),
            ("equipment_category_id", "=", self.category.id)])
        self.assertTrue(tpl.do_qo_part01)
        self.assertTrue(tpl.qi_part01_declined)
        self.assertFalse(tpl.qo_part01_declined)
        self.assertAlmostEqual(tpl.price_base, line.subtotal, 2)

        so2 = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz2 = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so2.id})
        new = self.env["afr.qualificacao.configurator.equipment"].new(
            {"wizard_id": wiz2.id, "equipment_id": self.equip1.id})
        new._onchange_equipment_template()
        self.assertEqual(new.config_template_id, tpl)
        self.assertTrue(new.do_qo_part01)
        self.assertTrue(new.qi_part01_declined)
        # O wizard projeta o rateio do preço/tempo combinados do template.
        self.assertAlmostEqual(new.subtotal, tpl.price_base, 2)
        # A seção guarda os dias com 2 casas (19,25 h / 8 = 2,41 dias).
        self.assertAlmostEqual(new.estimated_hours_total,
                               round(tpl.estimated_days, 2) * 8.0, 2)
        wiz2.equipment_line_ids = [(0, 0, new._convert_to_write(
            new._cache))]
        wiz2.action_apply()

        def sig(so):
            return sorted(
                (l.product_id.id, l.qualification_type, l.part or "",
                 l.part01_declined, l.qualif_cycle_qty)
                for l in so.order_line if not l.display_type)
        so1 = line.wizard_id.sale_order_id
        line.wizard_id.action_apply()
        self.assertEqual(sig(so1), sig(so2))
        self.assertTrue(so2.order_line.filtered(
            lambda l: l.qualification_type == "operational"
            and l.part == "01" and not l.part01_declined))
        sec2 = self._section(so2)
        self.assertAlmostEqual(sec2.equipment_subtotal, new.subtotal, 2)
        self.assertAlmostEqual(sec2.equipment_current_hours,
                               new.estimated_hours_total, 2)

    def _reload(self, so):
        wiz = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id})
        if not wiz.equipment_line_ids:
            wiz._load_from_existing_lines()
        return wiz.equipment_line_ids

    def test_reload_with_targets_matches_section(self):
        line = self._wiz_line()
        so = line.wizard_id.sale_order_id
        line.wizard_id.action_apply()
        sec = self._section(so)
        sec.write({"equipment_target_price": 2900.0,
                   "equipment_target_days": 2.0})
        self.assertAlmostEqual(sec.equipment_subtotal, 2900.0, 2)
        self.assertAlmostEqual(sec.equipment_current_hours, 16.0, 2)
        el = self._reload(so)
        self.assertAlmostEqual(el.subtotal, 2900.0, 2)
        self.assertAlmostEqual(el.estimated_hours_total, 16.0, 2)
        # Reaplicar a partir do wizard recarregado mantém a seção.
        el.wizard_id.action_apply()
        sec = self._section(so)
        self.assertAlmostEqual(sec.equipment_subtotal, el.subtotal, 2)
        self.assertAlmostEqual(sec.equipment_current_hours,
                               el.estimated_hours_total, 2)

    def test_unrateable_base_shows_base_totals(self):
        # Base com preço zero: o rateio não aplica, a seção fica no base.
        line = self._wiz_line(do_qi=False, do_qo_part01=False,
                              qd_line_ids=[], calib_line_ids=[])
        line.qo_line_ids.unit_price = 0.0
        so = line.wizard_id.sale_order_id
        line.wizard_id.action_apply()
        sec = self._section(so)
        sec.write({"equipment_target_price": 500.0,
                   "equipment_target_days": 3.0})
        el = self._reload(so)
        self.assertAlmostEqual(el.subtotal, sec.equipment_subtotal, 2)
        self.assertAlmostEqual(el.estimated_hours_total,
                               sec.equipment_current_hours, 2)
        self.assertAlmostEqual(el.estimated_hours_total, 6.0, 2)

    def _onchange_line(self, tpl):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id})
        line = self.env["afr.qualificacao.configurator.equipment"].new({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "qi_part01_declined": True, "do_qo_part01": False,
            "qo_part01_declined": False})
        line.config_template_id = tpl
        line._onchange_config_template()
        return line

    def _flag_tpl(self, **kw):
        vals = {"name": "t", "equipment_category_id": self.category.id,
                "company_id": self.company.id, "do_qi": True,
                "qi_part01_declined": False, "do_qo_part01": True,
                "qo_part01_declined": True}
        vals.update(kw)
        return self.env["afr.qualificacao.config.template"].create(vals)

    def test_client_template_applies_part01_flags(self):
        line = self._onchange_line(self._flag_tpl(partner_id=self.partner.id))
        self.assertFalse(line.qi_part01_declined)
        self.assertTrue(line.do_qo_part01)
        self.assertTrue(line.qo_part01_declined)

    def test_category_template_keeps_part01_flags(self):
        line = self._onchange_line(self._flag_tpl())
        self.assertTrue(line.qi_part01_declined)
        self.assertFalse(line.do_qo_part01)
        self.assertFalse(line.qo_part01_declined)

    def test_client_default_rounds_days(self):
        # 19,25 h / 8 = 2,40625 → grava 2,41 (precisão da seção).
        line = self._wiz_line(do_qi=False, do_qo_part01=False,
                              qo_line_ids=[], calib_line_ids=[],
                              qd_line_ids=[(0, 0, {
                                  "cycle_type_id": self.cycle_cmax.id,
                                  "qty": 1, "unit_price": 10.0,
                                  "estimated_hours": 19.25})])
        line.action_save_as_client_default()
        tpl = self.env["afr.qualificacao.config.template"].search([
            ("partner_id", "=", self.partner.id),
            ("equipment_category_id", "=", self.category.id)])
        self.assertEqual(tpl.estimated_days, 2.41)
