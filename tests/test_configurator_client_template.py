# -*- coding: utf-8 -*-
"""Template de cotação por cliente — Task 3: auto-aplicação no configurador,
alvos (preço/tempo) vindos do template e segurança do re-apply."""
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestConfiguratorClientTemplate(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tpl = cls.env["afr.qualificacao.config.template"]
        cls.EquipLine = cls.env["afr.qualificacao.configurator.equipment"]

    def _tpl(self, name, **kw):
        vals = {
            "name": name, "equipment_category_id": self.category.id,
            "company_id": self.company.id,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id,
                                    "qty": 2})],
        }
        vals.update(kw)
        return self.Tpl.create(vals)

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _wiz(self, so):
        wiz = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id})
        wiz._load_from_existing_lines()
        return wiz

    def _section(self, so, equip):
        return so.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == equip)

    def _equip_total(self, so, equip):
        return sum(so.order_line.filtered(
            lambda l: not l.display_type and l.equipment_id == equip
        ).mapped("price_subtotal"))

    def _add_with_onchange(self, wiz, equip):
        line = self.EquipLine.new({"wizard_id": wiz.id,
                                   "equipment_id": equip.id})
        line._onchange_equipment_template()
        return line

    # --- onchange ----------------------------------------------------
    def test_onchange_picks_category_then_client(self):
        wiz = self._wiz(self._so())
        cat = self._tpl("cat")
        line = self._add_with_onchange(wiz, self.equip1)
        self.assertEqual(line.config_template_id, cat)
        self.assertEqual(line.template_origin, "categoria")
        self.assertEqual(len(line.qd_line_ids), 1)
        client = self._tpl("cli", partner_id=self.partner.id)
        line = self._add_with_onchange(wiz, self.equip1)
        self.assertEqual(line.config_template_id, client)
        self.assertEqual(line.template_origin, "cliente")

    def test_onchange_keeps_manual_choice(self):
        wiz = self._wiz(self._so())
        self._tpl("cli", partner_id=self.partner.id)
        manual = self._tpl("manual", sequence=50)
        line = self.EquipLine.new({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "config_template_id": manual.id})
        line._onchange_equipment_template()
        self.assertEqual(line.config_template_id, manual)

    def test_onchange_none_without_template(self):
        wiz = self._wiz(self._so())
        line = self._add_with_onchange(wiz, self.equip1)
        self.assertFalse(line.config_template_id)
        self.assertEqual(line.template_origin, "none")

    # --- action_apply: alvos ----------------------------------------
    def _apply_new(self, so, tpl):
        wiz = self._wiz(so)
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "config_template_id": tpl.id,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id,
                                    "qty": 2, "estimated_hours": 4.0})],
        })]
        wiz.action_apply()

    def test_new_equipment_gets_template_targets(self):
        so = self._so()
        tpl = self._tpl("cli", partner_id=self.partner.id,
                        price_base=1234.0, estimated_days=2.0)
        self._apply_new(so, tpl)
        sec = self._section(so, self.equip1)
        self.assertEqual(sec.equipment_target_price, 1234.0)
        self.assertEqual(sec.equipment_target_days, 2.0)
        self.assertAlmostEqual(self._equip_total(so, self.equip1), 1234.0,
                               delta=0.5)  # 1 linha: rateio aproximado
        hours = sum(so.order_line.filtered(
            lambda l: not l.display_type and l.equipment_id == self.equip1
        ).mapped(lambda l: l.estimated_hours * (l.qualif_cycle_qty or 1)))
        self.assertAlmostEqual(hours, 16.0, 2)

    def test_reapply_keeps_user_targets(self):
        so = self._so()
        tpl = self._tpl("cli", partner_id=self.partner.id,
                        price_base=1234.0, estimated_days=2.0)
        self._apply_new(so, tpl)
        sec = self._section(so, self.equip1)
        sec.equipment_target_price = 999.0
        sec.equipment_target_days = 3.0
        sec._apply_equipment_time_target()
        self._wiz(so).action_apply()
        sec = self._section(so, self.equip1)
        self.assertEqual(sec.equipment_target_price, 999.0)
        self.assertEqual(sec.equipment_target_days, 3.0)
        self.assertAlmostEqual(self._equip_total(so, self.equip1), 999.0,
                               delta=0.5)

    def test_reapply_does_not_restore_zeroed_targets(self):
        so = self._so()
        tpl = self._tpl("cli", partner_id=self.partner.id,
                        price_base=1234.0, estimated_days=2.0)
        self._apply_new(so, tpl)
        sec = self._section(so, self.equip1)
        sec.write({"equipment_target_price": 0.0,
                   "equipment_target_days": 0.0})
        wiz = self._wiz(so)
        self.assertEqual(wiz.equipment_line_ids.config_template_id, tpl)
        wiz.action_apply()
        sec = self._section(so, self.equip1)
        self.assertEqual(sec.equipment_target_price, 0.0)
        self.assertEqual(sec.equipment_target_days, 0.0)

    def test_loaded_line_without_template_stays_without(self):
        so = self._so()
        wiz = self._wiz(so)
        wiz.equipment_line_ids = [(0, 0, {"equipment_id": self.equip1.id,
                                          "do_qi": True})]
        wiz.action_apply()
        self._tpl("cli", partner_id=self.partner.id, price_base=500.0)
        wiz2 = self._wiz(so)
        self.assertFalse(wiz2.equipment_line_ids.config_template_id)
        wiz2.action_apply()
        self.assertEqual(
            self._section(so, self.equip1).equipment_target_price, 0.0)

    # --- bulk --------------------------------------------------------
    def _bulk(self, wiz, **kw):
        bulk = self.env["afr.qualificacao.configurator.bulk"].create(dict(
            {"parent_wizard_id": wiz.id,
             "equipment_ids": [(6, 0, [self.equip1.id, self.equip2.id])],
             "do_qs": True}, **kw))
        return bulk

    def test_bulk_uses_partner_template(self):
        tpl = self._tpl("cli", partner_id=self.partner.id)
        wiz = self._wiz(self._so())
        bulk = self._bulk(wiz)
        self.assertTrue(bulk.use_partner_template)
        bulk.action_apply()
        self.assertEqual(len(wiz.equipment_line_ids), 2)
        for line in wiz.equipment_line_ids:
            self.assertEqual(line.config_template_id, tpl)
            self.assertFalse(line.do_qs)
            self.assertEqual(len(line.qd_line_ids), 1)

    def test_bulk_without_option_uses_bulk_scope(self):
        self._tpl("cli", partner_id=self.partner.id)
        wiz = self._wiz(self._so())
        bulk = self._bulk(wiz)
        bulk.use_partner_template = False
        bulk.action_apply()
        for line in wiz.equipment_line_ids:
            self.assertFalse(line.config_template_id)
            self.assertTrue(line.do_qs)
            self.assertFalse(line.qd_line_ids)

    def test_bulk_default_off_without_templates(self):
        wiz = self._wiz(self._so())
        bulk = self._bulk(wiz)
        self.assertFalse(bulk.use_partner_template)
        bulk.action_apply()
        for line in wiz.equipment_line_ids:
            self.assertTrue(line.do_qs)

    # --- fix round 1 -------------------------------------------------
    def test_new_equipment_zero_price_does_not_block_apply(self):
        so = self._so()
        tpl = self._tpl("cli", partner_id=self.partner.id, price_base=800.0)
        wiz = self._wiz(so)
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id, "config_template_id": tpl.id,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id,
                                    "qty": 2, "unit_price": 0.0})],
        })]
        wiz.action_apply()
        sec = self._section(so, self.equip1)
        self.assertEqual(sec.equipment_target_price, 800.0)
        self.assertEqual(sec.equipment_target_state, "drift")
        self.assertEqual(self._equip_total(so, self.equip1), 0.0)

    def test_reapply_unrateable_base_keeps_target_drift(self):
        so = self._so()
        tpl = self._tpl("cli", partner_id=self.partner.id, price_base=800.0)
        self._apply_new(so, tpl)
        so.order_line.filtered(
            lambda l: not l.display_type and l.equipment_id == self.equip1
        ).write({"price_unit": 0.0})
        self._wiz(so).action_apply()
        sec = self._section(so, self.equip1)
        self.assertEqual(sec.equipment_target_price, 800.0)
        self.assertEqual(sec.equipment_target_state, "drift")

    def test_duplicate_equipment_blocked(self):
        from odoo.exceptions import UserError
        wiz = self._wiz(self._so())
        with self.assertRaises(UserError):  # ValidationError herda
            wiz.equipment_line_ids = [
                (0, 0, {"equipment_id": self.equip1.id, "do_qi": True}),
                (0, 0, {"equipment_id": self.equip1.id, "do_qs": True}),
            ]
            wiz.action_apply()

    def test_bulk_skips_equipment_already_in_parent(self):
        wiz = self._wiz(self._so())
        wiz.equipment_line_ids = [(0, 0, {"equipment_id": self.equip1.id,
                                          "do_qi": True})]
        self._bulk(wiz).action_apply()
        self.assertEqual(len(wiz.equipment_line_ids), 2)
        self.assertEqual(len(wiz.equipment_line_ids.mapped("equipment_id")), 2)

    def test_change_equipment_reresolves_other_category(self):
        cat2 = self.env["engc.equipment.category"].create({"name": "Cat3-T"})
        equip3 = self.env["engc.equipment"].create({
            "client_id": self.partner.id, "category_id": cat2.id,
            "model": "M3", "serial_number": "TSN-T3",
            "means_of_aquisition_id": self.means.id,
            "location_id": self.location.id, "marca_id": self.marca.id,
        })
        tpl1 = self._tpl("cli1", partner_id=self.partner.id)
        tpl3 = self._tpl("cli3", partner_id=self.partner.id,
                         equipment_category_id=cat2.id)
        wiz = self._wiz(self._so())
        line = self._add_with_onchange(wiz, self.equip1)
        self.assertEqual(line.config_template_id, tpl1)
        line.equipment_id = equip3
        line._onchange_equipment_template()
        self.assertEqual(line.config_template_id, tpl3)
        # mesma categoria: escolha mantida
        manual = self._tpl("manual", sequence=50)
        line2 = self.EquipLine.new({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "config_template_id": manual.id})
        line2.equipment_id = self.equip2
        line2._onchange_equipment_template()
        self.assertEqual(line2.config_template_id, manual)
