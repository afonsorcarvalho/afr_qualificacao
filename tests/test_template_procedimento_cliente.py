# -*- coding: utf-8 -*-
"""Testes do resolvedor de procedimento por cliente/equipamento (Task 1).

Cobre: afr.qualificacao.procedimento._resolve_for_equipment (equipamento >
cliente > categoria > genérico > vazio), resolve_for(category) mantido (só
padrão da categoria/genérico), constraint de is_default único por
(categoria, empresa), constraint de procedimento do cliente único por
categoria, constraint de procedimento do equipamento restrito à categoria.
"""
import re

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

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

    def test_resolve_for_equipment_uses_explicit_company(self):
        """Task 3 (ruling): `company` explícito escopa categoria e cliente —
        a materialização passa a empresa da cotação/OS, não `env.company`
        (sob cron/sudo/multi-company as duas podem divergir)."""
        company_b = self.env["res.company"].create({"name": "Test Empresa B ProcRes"})
        self.assertNotEqual(self.env.company, company_b)
        Proc = self.env["afr.qualificacao.procedimento"]
        pA_b = Proc.create({
            "name": "pA_b", "equipment_category_id": self.catA.id,
            "is_default": True, "company_id": company_b.id,
        })
        pA_b_cli = Proc.create({
            "name": "pA_b_cli", "equipment_category_id": self.catA.id,
            "company_id": company_b.id,
        })

        # Sem company → env.company (A): padrão da categoria na empresa A.
        proc, origem = Proc._resolve_for_equipment(self.equipA, self.partner)
        self.assertEqual((proc, origem), (self.pA_def, "categoria"))

        # company_b → padrão da categoria na empresa B.
        proc, origem = Proc._resolve_for_equipment(
            self.equipA, self.partner, company=company_b
        )
        self.assertEqual((proc, origem), (pA_b, "categoria"))

        # Procedimento do cliente só vale na empresa dele.
        self.partner.afr_procedimento_ids = [(6, 0, [pA_b_cli.id])]
        proc, origem = Proc._resolve_for_equipment(
            self.equipA, self.partner, company=company_b
        )
        self.assertEqual((proc, origem), (pA_b_cli, "cliente"))
        proc, origem = Proc._resolve_for_equipment(self.equipA, self.partner)
        self.assertEqual((proc, origem), (self.pA_def, "categoria"))


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
        `template_id` vazio, e sem blocos (sem template, `_apply_template`
        não tem o que aplicar). Pelo caminho de UI
        (`action_generate_relatorios_open()`) o botão abre o wizard de
        template em vez de criar (Task 4).
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
        # Caminho de UI (Task 4, decisão 8): sem template resolvido o botão
        # pergunta (wizard) e não cria nada.
        action = other_os.action_generate_relatorios_open()
        self.assertEqual(action["res_model"], "afr.qualificacao.relatorio.template.wizard")
        self.assertFalse(other_os.relatorio_final_ids)
        # Caminho programático: cria sem template e sem blocos.
        other_os.action_generate_relatorios()
        other_os.relatorio_final_ids._apply_template()
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

    def test_category_match_uses_os_company_not_env_company(self):
        """Fix round 1: o passo de categoria deve resolver dentro da empresa
        da OS, não de `self.env.company` — sob cron/sudo/multi-company as
        duas podem divergir, e resolver pela empresa errada acharia vazio em
        silêncio."""
        company_b = self.env["res.company"].create({"name": "Test Empresa B TplRes"})
        self.assertNotEqual(self.env.company, company_b)
        tpl_b = self.env["afr.relatorio.template"].create({
            "name": "Tpl Resolver Empresa B", "code": "TPLRES-COMPB", "sequence": 5,
            "company_id": company_b.id,
            "equipment_category_ids": [(6, 0, self.cat_tpl.ids)],
        })

        # 1) _resolve_template direto, empresa passada explicitamente.
        tpl, origem = self.env["afr.qualificacao.relatorio"]._resolve_template(
            self.equip_tpl, self.env["res.partner"], self.env["afr.qualificacao"],
            company_b,
        )
        self.assertEqual(tpl, tpl_b)
        self.assertEqual(origem, "categoria")

        # 2) fluxo completo: OS na empresa B, env.company continua sendo a
        # empresa default (A) — create() deve resolver via `os.company_id`,
        # não `self.env.company`.
        os_b = self.env["afr.qualificacao.os"].create({"company_id": company_b.id})
        self.env["afr.qualificacao"].create({
            "name": "RF-tplres-compb-%s" % os_b.id,
            "equipment_id": self.equip_tpl.id,
            "qualification_type": "installation",
            "os_id": os_b.id,
            "company_id": company_b.id,
        })
        rel = self.env["afr.qualificacao.relatorio"].create({
            "os_id": os_b.id,
            "equipment_id": self.equip_tpl.id,
        })
        self.assertEqual(rel.template_id, tpl_b)


@tagged("afr_qualificacao", "procedimento", "post_install", "-at_install")
class TestGenerateOsWizardLines(AfrQualificacaoTestCommon):
    """Task 3: wizard Gerar OS com uma linha por equipamento (incluir,
    procedimento, template, origem), materialização gravando as escolhas e
    `save_as_default` (design decisão 7)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Proc = cls.env["afr.qualificacao.procedimento"]
        cls.p_def = Proc.create({
            "name": "pWiz_def", "equipment_category_id": cls.category.id,
            "is_default": True,
        })
        cls.p_alt = Proc.create({
            "name": "pWiz_alt", "equipment_category_id": cls.category.id,
        })
        Item = cls.env["afr.qualificacao.procedimento.item"]
        for proc in (cls.p_def, cls.p_alt):
            for phase in ("installation", "performance"):
                Item.create({
                    "procedimento_id": proc.id, "phase": phase,
                    "name": "%s-%s" % (proc.name, phase),
                    "kind": "foto", "target_level": "qualificacao",
                })
        cls.other_category = cls.env["engc.equipment.category"].create({
            "name": "Test-Wiz-OutraCat",
        })
        cls.p_other_cat = Proc.create({
            "name": "pWiz_outra", "equipment_category_id": cls.other_category.id,
        })
        Template = cls.env["afr.relatorio.template"]
        cls.t_a = Template.create({"name": "Tpl Wiz A", "code": "TPLWIZ-A"})
        cls.t_b = Template.create({"name": "Tpl Wiz B", "code": "TPLWIZ-B"})

    # ── helpers ───────────────────────────────────────────────────────

    def _so_confirmada(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [
            (0, 0, {"equipment_id": self.equip1.id, "do_qi": True}),
            (0, 0, {"equipment_id": self.equip2.id, "do_qi": True}),
        ]
        wiz.action_apply()
        so.action_confirm()
        return so

    def _wizard(self, so):
        """Abre o wizard como a action da cotação abre (default_sale_order_id)."""
        return self.env["afr.qualificacao.os.generate.wizard"].with_context(
            default_sale_order_id=so.id
        ).create({})

    def _line(self, wiz, equipment):
        return wiz.line_ids.filtered(lambda l: l.equipment_id == equipment)

    def _gerar(self, wiz):
        action = wiz.action_generate()
        return self.env["afr.qualificacao.os"].browse(action.get("res_id"))

    def _collect_procs(self, qualif):
        return qualif.collect_item_ids.mapped("procedimento_item_id.procedimento_id")

    # ── pré-preenchimento ────────────────────────────────────────────

    def test_default_get_creates_line_per_pending_equipment_prefilled(self):
        self.equip1.afr_procedimento_id = self.p_alt
        self.partner.afr_relatorio_template_id = self.t_b
        so = self._so_confirmada()
        wiz = self._wizard(so)

        self.assertEqual(wiz.line_ids.mapped("equipment_id"), self.equip1 | self.equip2)
        self.assertTrue(all(wiz.line_ids.mapped("include")))
        l1, l2 = self._line(wiz, self.equip1), self._line(wiz, self.equip2)
        self.assertEqual((l1.procedimento_id, l1.procedimento_origem), (self.p_alt, "equipamento"))
        self.assertEqual((l2.procedimento_id, l2.procedimento_origem), (self.p_def, "categoria"))
        self.assertEqual((l1.relatorio_template_id, l1.template_origem), (self.t_b, "cliente"))
        self.assertEqual(l1.category_id, self.category)
        self.assertFalse(wiz.save_as_default)

    # ── validação ────────────────────────────────────────────────────

    def test_included_line_without_procedimento_raises_listing_equipment(self):
        so = self._so_confirmada()
        wiz = self._wizard(so)
        self._line(wiz, self.equip2).procedimento_id = False
        with self.assertRaisesRegex(UserError, re.escape(self.equip2.display_name)):
            wiz.action_generate()
        self.assertFalse(so.qualificacao_os_ids)

    def test_excluded_line_without_procedimento_does_not_block_nor_generate(self):
        so = self._so_confirmada()
        wiz = self._wizard(so)
        l2 = self._line(wiz, self.equip2)
        l2.write({"include": False, "procedimento_id": False})
        os = self._gerar(wiz)
        self.assertEqual(os.equipment_ids, self.equip1)
        self.assertEqual(so.equipamentos_sem_os_ids, self.equip2)

    def test_all_lines_excluded_raises(self):
        so = self._so_confirmada()
        wiz = self._wizard(so)
        wiz.line_ids.write({"include": False})
        with self.assertRaisesRegex(UserError, "Selecione ao menos um equipamento"):
            wiz.action_generate()

    def test_procedimento_of_other_category_raises(self):
        so = self._so_confirmada()
        wiz = self._wizard(so)
        self._line(wiz, self.equip1).procedimento_id = self.p_other_cat
        with self.assertRaisesRegex(UserError, "pWiz_outra"):
            wiz.action_generate()
        self.assertFalse(so.qualificacao_os_ids)

    # ── materialização com a escolha ─────────────────────────────────

    def test_generation_writes_choices_and_explodes_chosen_procedimento(self):
        so = self._so_confirmada()
        wiz = self._wizard(so)
        self._line(wiz, self.equip1).write({
            "procedimento_id": self.p_alt.id, "relatorio_template_id": self.t_a.id,
        })
        os = self._gerar(wiz)

        q1 = os.qualificacao_ids.filtered(lambda q: q.equipment_id == self.equip1)
        q2 = os.qualificacao_ids.filtered(lambda q: q.equipment_id == self.equip2)
        self.assertEqual(q1.procedimento_id, self.p_alt)
        self.assertEqual(q1.relatorio_template_id, self.t_a)
        self.assertEqual(self._collect_procs(q1), self.p_alt)
        self.assertEqual(q2.procedimento_id, self.p_def)
        self.assertEqual(self._collect_procs(q2), self.p_def)

    def test_existing_open_os_route_uses_and_writes_choice(self):
        """Review Focus 5: equipamento que já tem OS aberta nesta cotação
        (opcional aceito depois) — a linha nova cai na OS existente COM o
        procedimento/template escolhidos no wizard."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        conf = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        conf.equipment_line_ids = [(0, 0, {"equipment_id": self.equip1.id, "do_qi": True})]
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": conf.id, "equipment_id": self.equip1.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 1,
            "estimated_hours": 1.0, "accepted": False,
        })
        conf.action_apply()
        so.action_confirm()

        wiz = self._wizard(so)
        self._line(wiz, self.equip1).relatorio_template_id = self.t_b
        os1 = self._gerar(wiz)

        so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.equipment_id == self.equip1
        ).optional_accepted = True
        self.assertEqual(so.equipamentos_sem_os_ids, self.equip1)

        wiz2 = self._wizard(so)
        line = self._line(wiz2, self.equip1)
        # Template já gravado na qualificação da OS existente ⇒ "Definido na OS".
        self.assertEqual((line.relatorio_template_id, line.template_origem), (self.t_b, "qualificacao"))
        line.write({"procedimento_id": self.p_alt.id, "relatorio_template_id": self.t_a.id})
        os2 = self._gerar(wiz2)

        self.assertEqual(os2, os1)
        qd = os1.qualificacao_ids.filtered(lambda q: q.qualification_type == "performance")
        self.assertTrue(qd)
        self.assertEqual(qd.procedimento_id, self.p_alt)
        self.assertEqual(qd.relatorio_template_id, self.t_a)
        self.assertEqual(self._collect_procs(qd), self.p_alt)

        # Fix round 1: template escolhido sincroniza TODAS as qualificações
        # não-canceladas do equipamento na OS (senão `_resolve_template`
        # pegaria a primeira, com o template antigo); procedimento não.
        equip_qualifs = os1.qualificacao_ids.filtered(
            lambda q: q.equipment_id == self.equip1
        )
        self.assertEqual(len(equip_qualifs), 2)
        self.assertEqual(equip_qualifs.mapped("relatorio_template_id"), self.t_a)
        qi = equip_qualifs.filtered(lambda q: q.qualification_type == "installation")
        self.assertEqual(qi.procedimento_id, self.p_def)
        tpl, origem = self.env["afr.qualificacao.relatorio"]._resolve_template(
            self.equip1, so.partner_id, equip_qualifs, company=so.company_id
        )
        self.assertEqual((tpl, origem), (self.t_a, "qualificacao"))

    def test_existing_os_route_empty_template_choice_keeps_siblings(self):
        """Escolha de template vazia na rota OS existente não apaga o
        template já gravado nas qualificações irmãs."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        conf = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        conf.equipment_line_ids = [(0, 0, {"equipment_id": self.equip1.id, "do_qi": True})]
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": conf.id, "equipment_id": self.equip1.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 1,
            "estimated_hours": 1.0, "accepted": False,
        })
        conf.action_apply()
        so.action_confirm()
        wiz = self._wizard(so)
        self._line(wiz, self.equip1).relatorio_template_id = self.t_b
        os1 = self._gerar(wiz)
        so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.equipment_id == self.equip1
        ).optional_accepted = True
        wiz2 = self._wizard(so)
        self._line(wiz2, self.equip1).relatorio_template_id = False
        self._gerar(wiz2)
        qi = os1.qualificacao_ids.filtered(lambda q: q.qualification_type == "installation")
        self.assertEqual(qi.relatorio_template_id, self.t_b)

    # ── origem na UI (onchange + rótulo "—") ─────────────────────────

    def test_onchange_origem_follows_manual_choice(self):
        self.partner.afr_relatorio_template_id = self.t_b
        so = self._so_confirmada()
        form = Form(self.env["afr.qualificacao.os.generate.wizard"].with_context(
            default_sale_order_id=so.id
        ))
        idx = None
        for i in range(len(form.line_ids)):
            with form.line_ids.edit(i) as probe:
                if probe.equipment_id == self.equip1:
                    idx = i
        self.assertIsNotNone(idx)
        with form.line_ids.edit(idx) as line:
            self.assertEqual(line.procedimento_origem, "categoria")
            self.assertEqual(line.procedimento_origem_label, "Categoria")
            line.procedimento_id = self.p_alt
            self.assertFalse(line.procedimento_origem)
            self.assertEqual(line.procedimento_origem_label, "—")
            line.procedimento_id = self.p_def
            self.assertEqual(line.procedimento_origem, "categoria")

            self.assertEqual(line.template_origem, "cliente")
            line.relatorio_template_id = self.t_a
            self.assertFalse(line.template_origem)
            self.assertEqual(line.template_origem_label, "—")
            line.relatorio_template_id = self.t_b
            self.assertEqual(line.template_origem, "cliente")
            self.assertEqual(line.template_origem_label, "Cliente")

    def test_procedimento_without_company_accepted(self):
        """Procedimento sem empresa passa na validação (domain alinhado)."""
        p_noco = self.env["afr.qualificacao.procedimento"].create({
            "name": "pWiz_sem_empresa", "equipment_category_id": self.category.id,
            "company_id": False,
        })
        so = self._so_confirmada()
        wiz = self._wizard(so)
        self._line(wiz, self.equip1).procedimento_id = p_noco
        os = self._gerar(wiz)
        q1 = os.qualificacao_ids.filtered(lambda q: q.equipment_id == self.equip1)
        self.assertEqual(q1.procedimento_id, p_noco)

    # ── salvar como padrão ───────────────────────────────────────────

    def test_save_as_default_writes_equipment_and_commercial_partner(self):
        child = self.env["res.partner"].create({
            "name": "Contato Wiz", "parent_id": self.partner.id,
        })
        so = self._so_confirmada()
        so.partner_id = child
        wiz = self._wizard(so)
        wiz.save_as_default = True
        wiz.line_ids.write({"relatorio_template_id": self.t_a.id})
        self._line(wiz, self.equip1).procedimento_id = self.p_alt
        self._gerar(wiz)
        self.assertEqual(self.equip1.afr_procedimento_id, self.p_alt)
        self.assertEqual(self.equip2.afr_procedimento_id, self.p_def)
        self.assertEqual(self.partner.afr_relatorio_template_id, self.t_a)
        self.assertFalse(child.afr_relatorio_template_id)

    def test_without_save_as_default_nothing_is_written(self):
        so = self._so_confirmada()
        wiz = self._wizard(so)
        wiz.line_ids.write({"relatorio_template_id": self.t_a.id})
        self._line(wiz, self.equip1).procedimento_id = self.p_alt
        self._gerar(wiz)
        self.assertFalse(self.equip1.afr_procedimento_id)
        self.assertFalse(self.partner.afr_relatorio_template_id)

    def test_save_as_default_with_conflicting_templates_raises(self):
        so = self._so_confirmada()
        wiz = self._wizard(so)
        wiz.save_as_default = True
        self._line(wiz, self.equip1).relatorio_template_id = self.t_a
        self._line(wiz, self.equip2).relatorio_template_id = self.t_b
        with self.assertRaisesRegex(UserError, "template"):
            wiz.action_generate()
        self.assertFalse(so.qualificacao_os_ids)
        self.assertFalse(self.partner.afr_relatorio_template_id)

    # ── caminho sem wizard (PWA/API/testes) ──────────────────────────

    def test_materialize_without_choices_uses_resolver(self):
        self.equip1.afr_procedimento_id = self.p_alt
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        conf = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        conf.equipment_line_ids = [
            (0, 0, {"equipment_id": self.equip1.id, "do_qi": True}),
            (0, 0, {"equipment_id": self.equip2.id, "do_qi": True}),
        ]
        conf.action_apply()
        os = self._confirm_and_generate_os(so)
        q1 = os.qualificacao_ids.filtered(lambda q: q.equipment_id == self.equip1)
        q2 = os.qualificacao_ids.filtered(lambda q: q.equipment_id == self.equip2)
        self.assertEqual(q1.procedimento_id, self.p_alt)
        self.assertEqual(self._collect_procs(q1), self.p_alt)
        self.assertEqual(q2.procedimento_id, self.p_def)
        self.assertEqual(self._collect_procs(q2), self.p_def)
        # Sem escolha explícita, o template fica para o Relatório resolver.
        self.assertFalse(q1.relatorio_template_id)


@tagged("afr_qualificacao", "relatorio", "post_install", "-at_install")
class TestRelatorioTemplateWizard(AfrQualificacaoTestCommon):
    """Task 4: "Gerar relatórios finais" pergunta o template quando algum
    equipamento sem relatório não resolve (design decisão 8), e o wizard
    "Aplicar procedimento" usa a regra 5 e grava `procedimento_id`
    (decisão 9)."""

    WIZ = "afr.qualificacao.relatorio.template.wizard"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Template = cls.env["afr.relatorio.template"]
        cls.t_a = Template.create({"name": "Tpl RelWiz A", "code": "TPLRELWIZ-A"})
        cls.t_b = Template.create({"name": "Tpl RelWiz B", "code": "TPLRELWIZ-B"})
        Proc = cls.env["afr.qualificacao.procedimento"]
        cls.p_def = Proc.create({
            "name": "pRelWiz_def", "equipment_category_id": cls.category.id,
            "is_default": True,
        })
        cls.p_cli = Proc.create({
            "name": "pRelWiz_cli", "equipment_category_id": cls.category.id,
        })
        cls.p_eq = Proc.create({
            "name": "pRelWiz_eq", "equipment_category_id": cls.category.id,
        })
        cls.p_gen = Proc.create({"name": "pRelWiz_gen"})
        other_cat = cls.env["engc.equipment.category"].create({
            "name": "Test-RelWiz-OutraCat",
        })
        cls.p_other_cat = Proc.create({
            "name": "pRelWiz_outra", "equipment_category_id": other_cat.id,
        })

    # ── helpers ───────────────────────────────────────────────────────

    def _os(self, equipments=None):
        equipments = equipments or (self.equip1 | self.equip2)
        os = self.env["afr.qualificacao.os"].create({})
        for equip in equipments:
            self.env["afr.qualificacao"].create({
                "name": "RF-relwiz-%s-%s" % (os.id, equip.id),
                "equipment_id": equip.id,
                "qualification_type": "installation",
                "os_id": os.id,
                "company_id": os.company_id.id,
            })
        return os

    def _open_wizard(self, action):
        self.assertEqual(action.get("res_model"), self.WIZ)
        return self.env[self.WIZ].with_context(**action.get("context", {})).create({})

    def _line(self, wiz, equipment):
        return wiz.line_ids.filtered(lambda l: l.equipment_id == equipment)

    # ── botão ────────────────────────────────────────────────────────

    def test_all_resolved_generates_directly(self):
        self.partner.afr_relatorio_template_id = self.t_a
        os = self._os()
        action = os.action_generate_relatorios_open()
        self.assertEqual(action["res_model"], "afr.qualificacao.relatorio")
        self.assertEqual(len(os.relatorio_final_ids), 2)
        self.assertEqual(os.relatorio_final_ids.mapped("template_id"), self.t_a)

    def test_missing_template_opens_wizard_without_creating(self):
        os = self._os()
        action = os.action_generate_relatorios_open()
        self.assertEqual(action["res_model"], self.WIZ)
        self.assertEqual(action["target"], "new")
        self.assertFalse(os.relatorio_final_ids)

    def test_wizard_lines_prefilled_with_origin(self):
        os = self._os()
        q2 = os.qualificacao_ids.filtered(lambda q: q.equipment_id == self.equip2)
        q2.relatorio_template_id = self.t_b
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        self.assertEqual(wiz.os_id, os)
        l1, l2 = self._line(wiz, self.equip1), self._line(wiz, self.equip2)
        self.assertEqual((l1.relatorio_template_id, l1.origem, l1.origem_label),
                         (self.env["afr.relatorio.template"], False, "—"))
        self.assertTrue(l1.pending)
        self.assertEqual((l2.relatorio_template_id, l2.origem, l2.origem_label),
                         (self.t_b, "qualificacao", "Definido na OS"))
        self.assertFalse(l2.pending)
        self.assertFalse(wiz.save_as_default)

    def test_existing_relatorio_equipment_not_in_wizard(self):
        os = self._os()
        self.partner.afr_relatorio_template_id = self.t_a
        os.action_generate_relatorios()  # relatórios de equip1 e equip2
        equip3 = self.equip1.copy({"serial_number": "TSN-RELWIZ-3"})
        self.partner.afr_relatorio_template_id = False
        self.env["afr.qualificacao"].create({
            "name": "RF-relwiz-e3-%s" % os.id, "equipment_id": equip3.id,
            "qualification_type": "installation", "os_id": os.id,
            "company_id": os.company_id.id,
        })
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        self.assertEqual(wiz.line_ids.mapped("equipment_id"), equip3)

    def test_confirm_generates_with_chosen_template(self):
        os = self._os()
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        wiz.line_ids.relatorio_template_id = self.t_b
        action = wiz.action_confirm()
        self.assertEqual(action["res_model"], "afr.qualificacao.relatorio")
        self.assertEqual(len(os.relatorio_final_ids), 2)
        self.assertEqual(os.relatorio_final_ids.mapped("template_id"), self.t_b)
        self.assertEqual(os.qualificacao_ids.mapped("relatorio_template_id"), self.t_b)
        # _apply_template rodou (aprovações padrão semeadas)
        self.assertTrue(all(r.aprovacao_ids for r in os.relatorio_final_ids))
        self.assertFalse(self.partner.afr_relatorio_template_id)

    def test_form_roundtrip_confirm(self):
        """Caminho do client web (Form): `pending`/equipamento/template
        sobrevivem ao save; linha resolvida é readonly; confirmar gera."""
        os = self._os()
        q2 = os.qualificacao_ids.filtered(lambda q: q.equipment_id == self.equip2)
        q1 = os.qualificacao_ids - q2
        q2.relatorio_template_id = self.t_b
        Wiz = self.env[self.WIZ].with_context(default_os_id=os.id)
        # Ordem das linhas = ordem do default_get (sem abrir a linha
        # pendente: sair dela vazia falharia no `required`).
        order = [cmd[2]["equipment_id"] for cmd in Wiz.default_get(["os_id", "line_ids"])["line_ids"]]
        idx = {self.env["engc.equipment"].browse(e): i for i, e in enumerate(order)}
        f = Form(Wiz)
        with f.line_ids.edit(idx[self.equip2]) as line:
            with self.assertRaises(AssertionError):
                line.relatorio_template_id = self.t_a
        with f.line_ids.edit(idx[self.equip1]) as line:
            line.relatorio_template_id = self.t_a
        wiz = f.save()
        self.assertEqual(wiz.line_ids.filtered("pending").equipment_id, self.equip1)
        action = wiz.action_confirm()
        self.assertEqual(action["res_model"], "afr.qualificacao.relatorio")
        self.assertEqual(len(os.relatorio_final_ids), 2)
        self.assertEqual(q1.relatorio_template_id, self.t_a)
        self.assertEqual(q2.relatorio_template_id, self.t_b)

    def test_confirm_does_not_touch_resolved_lines(self):
        """Linha resolvida (cliente/categoria) é informativa: a origem não é
        congelada na qualificação."""
        os = self._os()
        q2 = os.qualificacao_ids.filtered(lambda q: q.equipment_id == self.equip2)
        q1 = os.qualificacao_ids - q2
        q2.relatorio_template_id = self.t_b
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        self._line(wiz, self.equip1).relatorio_template_id = self.t_a
        wiz.action_confirm()
        self.assertEqual(q1.relatorio_template_id, self.t_a)
        self.assertEqual(q2.relatorio_template_id, self.t_b)
        rel2 = os.relatorio_final_ids.filtered(lambda r: r.equipment_id == self.equip2)
        self.assertEqual(rel2.template_id, self.t_b)

    def test_save_as_default_writes_commercial_partner(self):
        company = self.env["res.partner"].create({"name": "RelWiz Holding", "is_company": True})
        self.partner.parent_id = company
        os = self._os()
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        wiz.line_ids.relatorio_template_id = self.t_a
        wiz.save_as_default = True
        wiz.action_confirm()
        self.assertEqual(company.afr_relatorio_template_id, self.t_a)
        self.assertFalse(self.partner.afr_relatorio_template_id)

    def test_save_as_default_conflicting_templates_raises(self):
        os = self._os()
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        self._line(wiz, self.equip1).relatorio_template_id = self.t_a
        self._line(wiz, self.equip2).relatorio_template_id = self.t_b
        wiz.save_as_default = True
        with self.assertRaisesRegex(UserError, "template"):
            wiz.action_confirm()
        self.assertFalse(os.relatorio_final_ids)
        self.assertFalse(os.qualificacao_ids.mapped("relatorio_template_id"))
        self.assertFalse(self.partner.afr_relatorio_template_id)

    def test_line_without_template_raises(self):
        os = self._os()
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        self._line(wiz, self.equip1).relatorio_template_id = self.t_a
        with self.assertRaisesRegex(UserError, re.escape(self.equip2.display_name)):
            wiz.action_confirm()
        self.assertFalse(os.relatorio_final_ids)
        self.assertFalse(os.qualificacao_ids.mapped("relatorio_template_id"))

    def test_template_other_company_raises(self):
        other_company = self.env["res.company"].create({"name": "RelWiz Outra Empresa"})
        t_other = self.env["afr.relatorio.template"].create({
            "name": "Tpl RelWiz Outra", "code": "TPLRELWIZ-OUT",
            "company_id": other_company.id,
        })
        os = self._os()
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        wiz.line_ids.relatorio_template_id = t_other
        with self.assertRaises(UserError):
            wiz.action_confirm()
        self.assertFalse(os.relatorio_final_ids)

    def test_confirm_ignores_forged_default_context(self):
        """O wizard roda no contexto do botão: `default_*` não pode vazar
        para relatório/blocos/aprovações (defesa P3 Task 5)."""
        other_user = self.env["res.users"].create({
            "name": "Outro RelWiz", "login": "outro.relwiz.test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        os = self._os()
        wiz = self._open_wizard(os.action_generate_relatorios_open())
        wiz.line_ids.relatorio_template_id = self.t_a
        wiz.with_context(
            default_approved_at="2000-01-01 00:00:00",
            default_user_id=other_user.id,
            default_state="issued",
        ).action_confirm()
        self.assertEqual(len(os.relatorio_final_ids), 2)
        self.assertEqual(set(os.relatorio_final_ids.mapped("state")), {"draft"})
        for ap in os.relatorio_final_ids.mapped("aprovacao_ids").filtered(
                lambda a: a.papel in ("elaborador", "emissor")):
            self.assertFalse(ap.approved_at)
            self.assertFalse(ap.user_id)

    # ── Aplicar procedimento (decisão 9) ─────────────────────────────

    def _apply_wizard(self, os):
        return self.env["afr.qualificacao.os.apply.procedimento.wizard"].with_context(
            default_os_id=os.id
        ).create({})

    def test_apply_default_follows_rule_5(self):
        self.equip1.afr_procedimento_id = self.p_eq
        self.partner.afr_procedimento_ids = [(6, 0, self.p_cli.ids)]
        os = self._os()
        wiz = self._apply_wizard(os)
        l1 = wiz.line_ids.filtered(lambda l: l.equipment_id == self.equip1)
        l2 = wiz.line_ids.filtered(lambda l: l.equipment_id == self.equip2)
        self.assertEqual(l1.procedimento_id, self.p_eq)
        self.assertEqual(l2.procedimento_id, self.p_cli)
        self.partner.afr_procedimento_ids = [(5, 0, 0)]
        wiz2 = self._apply_wizard(os)
        l2b = wiz2.line_ids.filtered(lambda l: l.equipment_id == self.equip2)
        self.assertEqual(l2b.procedimento_id, self.p_def)

    def test_apply_records_procedimento_on_qualificacao(self):
        os = self._os()
        wiz = self._apply_wizard(os)
        wiz.line_ids.procedimento_id = self.p_gen
        wiz.action_apply()
        self.assertEqual(os.qualificacao_ids.mapped("procedimento_id"), self.p_gen)

    def test_apply_rejects_procedimento_other_company(self):
        other_company = self.env["res.company"].create({"name": "RelWiz Outra Empresa P"})
        p_other = self.env["afr.qualificacao.procedimento"].create({
            "name": "pRelWiz_outra_empresa", "company_id": other_company.id,
        })
        os = self._os(self.equip1)
        wiz = self._apply_wizard(os)
        wiz.line_ids.procedimento_id = p_other
        with self.assertRaises(UserError):
            wiz.action_apply()
        self.assertFalse(os.qualificacao_ids.procedimento_id)
