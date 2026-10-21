# -*- coding: utf-8 -*-
"""Template de cotação por cliente — Task 1: model, resolver, constraint."""
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "client_config_template", "post_install", "-at_install")
class TestClientConfigTemplate(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tpl = cls.env["afr.qualificacao.config.template"]
        cls.cat = cls.env["engc.equipment.category"].create({"name": "Test-CT-Cat"})
        cls.cat2 = cls.env["engc.equipment.category"].create({"name": "Test-CT-Cat2"})
        cls.company2 = cls.env["res.company"].create({"name": "Outra Empresa CT"})
        cls.equip = cls.env["engc.equipment"].create({
            "client_id": cls.partner.id, "category_id": cls.cat.id,
            "model": "EqCT", "serial_number": "TSN-CT-1",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id, "marca_id": cls.marca.id,
        })
        cls.child = cls.env["res.partner"].create({
            "name": "Contato CT", "parent_id": cls.partner.id, "type": "contact",
        })

    def _tpl(self, name, **kw):
        vals = {"name": name, "equipment_category_id": self.cat.id,
                "company_id": self.company.id}
        vals.update(kw)
        return self.Tpl.create(vals)

    def test_order_client_then_category_then_none(self):
        none_tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.partner, self.company)
        self.assertFalse(none_tpl)
        self.assertEqual(origin, "none")
        cat_hi = self._tpl("cat-hi", sequence=20)
        cat_lo = self._tpl("cat-lo", sequence=5)
        tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.partner, self.company)
        self.assertEqual((tpl, origin), (cat_lo, "categoria"))
        self.assertNotEqual(tpl, cat_hi)
        client = self._tpl("client", partner_id=self.partner.id, sequence=99)
        tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.partner, self.company)
        self.assertEqual((tpl, origin), (client, "cliente"))

    def test_client_template_of_other_category_ignored(self):
        self._tpl("client-other", partner_id=self.partner.id,
                  equipment_category_id=self.cat2.id)
        tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.partner, self.company)
        self.assertEqual(origin, "none")

    def test_child_contact_resolves_commercial_partner(self):
        client = self._tpl("client", partner_id=self.partner.id)
        tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.child, self.company)
        self.assertEqual((tpl, origin), (client, "cliente"))

    def test_other_company_ignored(self):
        self._tpl("client-c2", partner_id=self.partner.id,
                  company_id=self.company2.id)
        self._tpl("cat-c2", company_id=self.company2.id)
        tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.partner, self.company)
        self.assertEqual(origin, "none")
        tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.partner, self.company2)
        self.assertEqual(origin, "cliente")

    def test_archived_ignored_by_resolver_and_not_blocking(self):
        old = self._tpl("old", partner_id=self.partner.id)
        old.active = False
        tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.partner, self.company)
        self.assertEqual(origin, "none")
        new = self._tpl("new", partner_id=self.partner.id)
        tpl, origin = self.Tpl._resolve_for_equipment(
            self.equip, self.partner, self.company)
        self.assertEqual((tpl, origin), (new, "cliente"))
        # reativar o antigo viola a unicidade
        with self.assertRaises(ValidationError):
            old.active = True

    def test_duplicate_active_raises(self):
        self._tpl("a", partner_id=self.partner.id)
        with self.assertRaises(ValidationError):
            self._tpl("b", partner_id=self.partner.id)

    def test_duplicate_allowed_other_company_or_category(self):
        self._tpl("a", partner_id=self.partner.id)
        self._tpl("b", partner_id=self.partner.id, company_id=self.company2.id)
        self._tpl("c", partner_id=self.partner.id,
                  equipment_category_id=self.cat2.id)

    def test_category_templates_not_constrained(self):
        self._tpl("a")
        self._tpl("b")

    def test_company_required(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.Tpl.create({"name": "x", "company_id": False})

    def test_client_template_requires_category(self):
        with self.assertRaises(ValidationError):
            self._tpl("nocat", partner_id=self.partner.id,
                      equipment_category_id=False)
        self._tpl("generic-nocat", equipment_category_id=False)

    def test_partner_delete_restricted(self):
        p = self.env["res.partner"].create({"name": "Del CT", "is_company": True})
        self._tpl("client", partner_id=p.id)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                p.unlink()

    def test_partner_inverse_and_domain(self):
        t = self._tpl("client", partner_id=self.partner.id)
        self.assertEqual(self.partner.afr_config_template_ids, t)
        self.assertEqual(
            self.child.commercial_partner_id.afr_config_template_ids, t)
