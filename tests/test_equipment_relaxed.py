# -*- coding: utf-8 -*-
"""Task 9 (16.0.9.1.0) — equipamento do cliente com regras relaxadas."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEquipmentRelaxed(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Equip = cls.env["engc.equipment"]
        cls.partner = cls.env["res.partner"].create({"name": "Cliente Equip T9", "is_company": True})
        cls.contact = cls.env["res.partner"].create({"name": "Contato T9", "parent_id": cls.partner.id})
        cls.categ = cls.env["engc.equipment.category"].create({"name": "AutoclaveT9"})
        cls.marca = cls.env["engc.equipment.marca"].create({"name": "MarcaT9"})

    def test_create_with_only_category(self):
        eq = self.Equip.create({"category_id": self.categ.id, "client_id": self.partner.id})
        self.assertEqual(eq.name, "AutoclaveT9")
        self.assertFalse(eq.marca_id)

    def test_repeated_serial_same_brand_allowed(self):
        vals = {"category_id": self.categ.id, "marca_id": self.marca.id, "serial_number": "S1", "model": "M"}
        a = self.Equip.create(vals)
        b = self.Equip.create(vals)
        self.env.flush_all()
        self.assertNotEqual(a, b)

    def test_name_partial_parts(self):
        eq = self.Equip.create({"category_id": self.categ.id, "marca_id": self.marca.id, "serial_number": "X9"})
        self.assertEqual(eq.name, "AutoclaveT9 X9 MarcaT9")

    def test_name_fallback_tag_then_id(self):
        eq = self.Equip.new({"tag": "TAG-01"})
        eq._compute_name()
        self.assertEqual(eq.name, "TAG-01")
        eq2 = self.Equip.new({})
        eq2._compute_name()
        self.assertEqual(eq2.name, "Novo equipamento")

    def test_partner_action_editable_list(self):
        action = self.contact.action_view_afr_equipments()
        self.assertEqual(action["domain"], [("client_id", "child_of", self.partner.id)])
        self.assertEqual(action["context"]["default_client_id"], self.partner.id)
        view = self.env.ref("afr_qualificacao.view_engc_equipment_client_editable_tree")
        self.assertEqual(action["views"][0], (view.id, "tree"))
        arch = view.arch
        self.assertIn('editable="bottom"', arch)
        for f in ("tag", "category_id", "marca_id", "model", "serial_number", "location_id", "apelido"):
            self.assertIn('name="%s"' % f, arch)

    def test_constraint_is_noop_check(self):
        self.env.cr.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'engc_equipment_serial_marca_company_id_no_uniq'"
        )
        self.assertEqual([r[0] for r in self.env.cr.fetchall()], ["CHECK (true)"])

    def test_count_and_list_include_child_contacts(self):
        a = self.Equip.create({"category_id": self.categ.id, "client_id": self.partner.id})
        b = self.Equip.create({"category_id": self.categ.id, "client_id": self.contact.id})
        for p in (self.partner, self.contact):
            p.invalidate_recordset(["afr_equipment_count"])
            self.assertEqual(p.afr_equipment_count, 2)
            found = self.Equip.search(p.action_view_afr_equipments()["domain"])
            self.assertEqual(found, a | b)
            self.assertEqual(p.action_view_afr_equipments()["context"]["default_client_id"], self.partner.id)
