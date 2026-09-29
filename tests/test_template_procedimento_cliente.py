# -*- coding: utf-8 -*-
"""Testes do resolvedor de procedimento por cliente/equipamento (Task 1).

Cobre: afr.qualificacao.procedimento._resolve_for_equipment (equipamento >
cliente > categoria > genérico > vazio), resolve_for(category) mantido (só
padrão da categoria/genérico), constraint de is_default único por
(categoria, empresa), constraint de procedimento do cliente único por
categoria, constraint de procedimento do equipamento restrito à categoria.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "procedimento", "post_install", "-at_install")
class TestProcedimentoResolver(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Category = cls.env["engc.equipment.category"]
        cls.catA = Category.create({"name": "Test-Resolver-CatA"})
        cls.catB = Category.create({"name": "Test-Resolver-CatB"})
        cls.catC = Category.create({"name": "Test-Resolver-CatC"})

        Proc = cls.env["afr.qualificacao.procedimento"]
        cls.pA_def = Proc.create({
            "name": "pA_def", "equipment_category_id": cls.catA.id, "is_default": True,
        })
        cls.pA_alt = Proc.create({
            "name": "pA_alt", "equipment_category_id": cls.catA.id,
        })
        cls.pB_def = Proc.create({
            "name": "pB_def", "equipment_category_id": cls.catB.id, "is_default": True,
        })
        cls.pGen = Proc.create({"name": "pGen", "is_default": True})

        Equipment = cls.env["engc.equipment"]
        cls.equipA = Equipment.create({
            "client_id": cls.partner.id, "category_id": cls.catA.id,
            "model": "EqA", "serial_number": "TSN-RES-A",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id, "marca_id": cls.marca.id,
        })
        cls.equipB = Equipment.create({
            "client_id": cls.partner.id, "category_id": cls.catB.id,
            "model": "EqB", "serial_number": "TSN-RES-B",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id, "marca_id": cls.marca.id,
        })
        cls.equipC = Equipment.create({
            "client_id": cls.partner.id, "category_id": cls.catC.id,
            "model": "EqC", "serial_number": "TSN-RES-C",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id, "marca_id": cls.marca.id,
        })

        cls.child_contact = cls.env["res.partner"].create({
            "name": "Contato Filho Test", "parent_id": cls.partner.id,
        })

    def _resolve(self, equipment, partner):
        return self.env["afr.qualificacao.procedimento"]._resolve_for_equipment(
            equipment, partner
        )

    # ── resolução por equipamento/cliente/categoria/genérico ──────────

    def test_category_default_when_nothing_else_set(self):
        proc, origem = self._resolve(self.equipA, self.partner)
        self.assertEqual(proc, self.pA_def)
        self.assertEqual(origem, "categoria")

    def test_equipment_explicit_procedimento_wins(self):
        self.equipA.afr_procedimento_id = self.pA_alt.id
        proc, origem = self._resolve(self.equipA, self.partner)
        self.assertEqual(proc, self.pA_alt)
        self.assertEqual(origem, "equipamento")

    def test_client_procedimento_used_for_matching_category(self):
        self.partner.afr_procedimento_ids = [(6, 0, [self.pA_alt.id])]
        proc, origem = self._resolve(self.equipA, self.partner)
        self.assertEqual(proc, self.pA_alt)
        self.assertEqual(origem, "cliente")

    def test_client_procedimento_other_category_falls_back_to_category_default(self):
        self.partner.afr_procedimento_ids = [(6, 0, [self.pA_alt.id])]
        proc, origem = self._resolve(self.equipB, self.partner)
        self.assertEqual(proc, self.pB_def)
        self.assertEqual(origem, "categoria")

    def test_generic_default_used_when_no_category_procedimento(self):
        proc, origem = self._resolve(self.equipC, self.partner)
        self.assertEqual(proc, self.pGen)
        self.assertEqual(origem, "generico")

    def test_empty_when_no_generic_available(self):
        self.pGen.active = False
        proc, origem = self._resolve(self.equipC, self.partner)
        self.assertFalse(proc)
        self.assertFalse(origem)
        self.pGen.active = True

    def test_child_contact_uses_commercial_partner(self):
        self.partner.afr_procedimento_ids = [(6, 0, [self.pA_alt.id])]
        proc, origem = self._resolve(self.equipA, self.child_contact)
        self.assertEqual(proc, self.pA_alt)
        self.assertEqual(origem, "cliente")

    # ── constraints ─────────────────────────────────────────────────

    def test_two_is_default_same_category_same_company_raises(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        with self.assertRaises(ValidationError):
            Proc.create({
                "name": "pA_def duplicado",
                "equipment_category_id": self.catA.id,
                "is_default": True,
            })

    def test_two_is_default_same_category_different_company_ok(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        company2 = self.env["res.company"].create({"name": "Test Empresa 2"})
        proc2 = Proc.create({
            "name": "pA_def empresa2",
            "equipment_category_id": self.catA.id,
            "is_default": True,
            "company_id": company2.id,
        })
        self.assertTrue(proc2)

    def test_partner_two_procedimentos_same_category_raises(self):
        with self.assertRaises(ValidationError):
            self.partner.afr_procedimento_ids = [
                (6, 0, [self.pA_def.id, self.pA_alt.id])
            ]

    def test_equipment_procedimento_of_other_category_raises(self):
        with self.assertRaises(ValidationError):
            self.equipA.afr_procedimento_id = self.pB_def.id

    def test_equipment_generic_procedimento_allowed_any_category(self):
        self.equipA.afr_procedimento_id = self.pGen.id
        self.assertEqual(self.equipA.afr_procedimento_id, self.pGen)

    # ── resolve_for(category) mantido (assinatura + comportamento) ────

    def test_resolve_for_returns_category_default(self):
        rec = self.env["afr.qualificacao.procedimento"].resolve_for(self.catA)
        self.assertEqual(rec, self.pA_def)

    def test_resolve_for_falls_back_to_oldest_generic_when_no_generic_default(self):
        self.pGen.is_default = False
        other_cat = self.env["engc.equipment.category"].create({
            "name": "Test-Resolver-CatSemProc",
        })
        rec = self.env["afr.qualificacao.procedimento"].resolve_for(other_cat)
        self.assertEqual(rec, self.pGen)
        self.pGen.is_default = True
