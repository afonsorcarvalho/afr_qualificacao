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


@tagged("afr_qualificacao", "relatorio", "post_install", "-at_install")
class TestTemplateResolver(AfrQualificacaoTestCommon):
    """Testes de `afr.qualificacao.relatorio._resolve_template` (Task 2):
    qualificação (template gravado na OS) > cliente > categoria > vazio.
    Sem fallback silencioso pela "menor sequence" (decisão 6 do design)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat_tpl = cls.env["engc.equipment.category"].create({
            "name": "Test-TplResolver-Cat",
        })
        Template = cls.env["afr.relatorio.template"]
        cls.t_hosp = Template.create({
            "name": "Tpl Resolver Hosp", "code": "TPLRES-HOSP", "sequence": 10,
            "equipment_category_ids": [(6, 0, cls.cat_tpl.ids)],
        })
        cls.t_ind = Template.create({
            "name": "Tpl Resolver Ind", "code": "TPLRES-IND", "sequence": 20,
        })

        cls.equip_tpl = cls.env["engc.equipment"].create({
            "client_id": cls.partner.id, "category_id": cls.cat_tpl.id,
            "model": "EqTplRes", "serial_number": "TSN-RES-TPL",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id, "marca_id": cls.marca.id,
        })

        cls.os_tpl = cls.env["afr.qualificacao.os"].create({})
        cls.qualif_tpl = cls.env["afr.qualificacao"].create({
            "name": "RF-tplres-%s" % cls.os_tpl.id,
            "equipment_id": cls.equip_tpl.id,
            "qualification_type": "installation",
            "os_id": cls.os_tpl.id,
            "company_id": cls.os_tpl.company_id.id,
        })

    def _resolve(self, equipment=None, partner=None, qualificacoes=None):
        Relatorio = self.env["afr.qualificacao.relatorio"]
        return Relatorio._resolve_template(
            equipment if equipment is not None else self.equip_tpl,
            partner if partner is not None else self.partner,
            qualificacoes if qualificacoes is not None else self.qualif_tpl,
        )

    def test_qualificacao_template_wins_over_client_template(self):
        self.qualif_tpl.relatorio_template_id = self.t_ind
        self.partner.afr_relatorio_template_id = self.t_hosp
        tpl, origem = self._resolve()
        self.assertEqual(tpl, self.t_ind)
        self.assertEqual(origem, "qualificacao")

    def test_client_template_used_when_no_qualificacao_template(self):
        self.partner.afr_relatorio_template_id = self.t_ind
        tpl, origem = self._resolve()
        self.assertEqual(tpl, self.t_ind)
        self.assertEqual(origem, "cliente")

    def test_category_template_used_when_no_qualificacao_or_client(self):
        tpl, origem = self._resolve()
        self.assertEqual(tpl, self.t_hosp)
        self.assertEqual(origem, "categoria")

    def test_empty_when_nothing_resolves(self):
        self.t_hosp.equipment_category_ids = [(5, 0, 0)]
        tpl, origem = self._resolve()
        self.assertFalse(tpl)
        self.assertFalse(origem)
        self.t_hosp.equipment_category_ids = [(6, 0, self.cat_tpl.ids)]

    def test_relatorio_created_without_matching_template_has_no_template_and_no_blocks(self):
        """Sem fallback silencioso: equipamento sem match nasce com
        `template_id` vazio, e sem blocos — inclusive pelo caminho de UI
        (`action_generate_relatorios_open()`, que chama `_apply_template()`
        em seguida; sem template, `_apply_template` não tem o que aplicar).
        'Recarregar template' levanta `UserError` nesse estado — ver
        `test_reload_without_template_raises`."""
        other_cat = self.env["engc.equipment.category"].create({
            "name": "Test-TplResolver-CatSemMatch",
        })
        equip_no_match = self.env["engc.equipment"].create({
            "client_id": self.partner.id, "category_id": other_cat.id,
            "model": "EqSemMatch", "serial_number": "TSN-RES-NOMATCH",
            "means_of_aquisition_id": self.means.id,
            "location_id": self.location.id, "marca_id": self.marca.id,
        })
        other_os = self.env["afr.qualificacao.os"].create({})
        self.env["afr.qualificacao"].create({
            "name": "RF-tplres-nomatch-%s" % other_os.id,
            "equipment_id": equip_no_match.id,
            "qualification_type": "installation",
            "os_id": other_os.id,
            "company_id": other_os.company_id.id,
        })
        other_os.action_generate_relatorios_open()
        rel = other_os.relatorio_final_ids.filtered(
            lambda r: r.equipment_id == equip_no_match)
        self.assertTrue(rel)
        self.assertFalse(rel.template_id)
        self.assertFalse(rel.block_ids)

    def test_default_template_id_context_still_wins(self):
        """`default_template_id` no contexto continua vencendo mesmo quando
        a qualificação/cliente/categoria resolveriam outro template."""
        other_os = self.env["afr.qualificacao.os"].create({})
        self.env["afr.qualificacao"].create({
            "name": "RF-tplres-ctxdef-%s" % other_os.id,
            "equipment_id": self.equip_tpl.id,
            "qualification_type": "installation",
            "os_id": other_os.id,
            "company_id": other_os.company_id.id,
        })
        rel = self.env["afr.qualificacao.relatorio"].with_context(
            default_template_id=self.t_ind.id
        ).create({
            "os_id": other_os.id,
            "equipment_id": self.equip_tpl.id,
        })
        self.assertEqual(rel.template_id, self.t_ind)
