# -*- coding: utf-8 -*-
"""Testes da explosão de procedimento em collect.items no SO confirm (F3)."""
import base64

from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "procedimento", "post_install", "-at_install")
class TestProcedimentoExplosion(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Proc = cls.env["afr.qualificacao.procedimento"]
        # 1 procedimento por categoria — itens de TODAS as fases (QI + QD + Calib)
        cls.proc_category = Proc.create({
            "name": "Procedimento Autoclave",
            "equipment_category_id": cls.category.id,
            # is_default: resolve_for/_resolve_for_equipment (16.0.8.9.0) só
            # devolvem o procedimento marcado como padrão da categoria.
            "is_default": True,
            "item_ids": [
                # QI
                (0, 0, {"name": "Foto plaqueta", "kind": "foto",
                        "phase": "installation", "target_level": "qualificacao",
                        "sequence": 10}),
                (0, 0, {"name": "NF cópia", "kind": "pdf",
                        "phase": "installation", "target_level": "qualificacao",
                        "sequence": 20}),
                # QD
                (0, 0, {"name": "Foto carga autoclave", "kind": "foto",
                        "phase": "performance", "target_level": "cycle",
                        "sequence": 30}),
                (0, 0, {"name": "Dados qualificador térmico", "kind": "qualificador_data",
                        "phase": "performance", "target_level": "qualificacao",
                        "sequence": 40}),
                (0, 0, {"name": "Indicador biológico", "kind": "foto",
                        "phase": "performance", "target_level": "cycle",
                        "sequence": 50}),
                # Calibração
                (0, 0, {"name": "Foto sensor in loco", "kind": "foto",
                        "phase": "calibration", "target_level": "malha",
                        "sequence": 60}),
            ],
        })
        # Procedimento fallback (sem categoria) — itens QD
        cls.proc_fallback = Proc.create({
            "name": "Procedimento Genérico (fallback)",
            # is_default: papel de "padrão genérico" da empresa (16.0.8.9.0).
            "is_default": True,
            "item_ids": [
                (0, 0, {"name": "Doc procedimento", "kind": "pdf",
                        "phase": "performance", "target_level": "qualificacao",
                        "sequence": 10}),
                (0, 0, {"name": "Foto carga", "kind": "foto",
                        "phase": "performance", "target_level": "cycle",
                        "sequence": 20}),
            ],
        })

    def _confirm_so_with(self, equipment_lines_spec):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, spec) for spec in equipment_lines_spec]
        wiz.action_apply()
        self._confirm_and_generate_os(so)
        return so

    # ─────────────────────────────────────────────────────────────
    # resolve_for: categoria > fallback (categoria vazia)
    # ─────────────────────────────────────────────────────────────
    def test_resolve_prefers_category_match(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        rec = Proc.resolve_for(self.category)
        self.assertEqual(rec, self.proc_category)

    def test_resolve_fallback_when_category_has_no_proc(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        other_cat = self.env["engc.equipment.category"].create({"name": "OutraCat"})
        rec = Proc.resolve_for(other_cat)
        self.assertEqual(rec, self.proc_fallback)

    def test_resolve_empty_when_no_category_and_no_fallback(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        self.proc_fallback.active = False  # sem fallback disponível
        other_cat = self.env["engc.equipment.category"].create({"name": "SemProc"})
        rec = Proc.resolve_for(other_cat)
        self.assertFalse(rec)
        self.proc_fallback.active = True

    # ─────────────────────────────────────────────────────────────
    # Explosão por target_level
    # ─────────────────────────────────────────────────────────────
    def test_explosion_qi_target_qualificacao(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        qualif = so.qualificacao_ids
        # proc_category tem 2 items QI target=qualificacao → 2 collect.items
        self.assertEqual(len(qualif.collect_item_ids), 2)
        names = qualif.collect_item_ids.mapped("name")
        self.assertIn("Foto plaqueta", names)
        self.assertIn("NF cópia", names)

    def test_explosion_qd_cycle_explodes_per_cycle(self):
        so = self._confirm_so_with([{
            "equipment_id": self.equip1.id,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 3})],
        }])
        qd = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "performance")
        # proc_category (fase QD): 2 items cycle + 1 qualificacao = 2*3 + 1 = 7
        self.assertEqual(len(qd.collect_item_ids), 7)
        cycle_items = qd.collect_item_ids.filtered(lambda c: c.cycle_id)
        self.assertEqual(len(cycle_items), 6)  # 2 items × 3 cycles
        qualif_items = qd.collect_item_ids.filtered(lambda c: not c.cycle_id and not c.malha_id)
        self.assertEqual(len(qualif_items), 1)

    def test_explosion_calib_malha_explodes_per_malha(self):
        so = self._confirm_so_with([{
            "equipment_id": self.equip1.id,
            "calib_line_ids": [(0, 0, {"malha_type_id": self.malha_temp.id, "qty": 4})],
        }])
        calib = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "calibration")
        self.assertEqual(len(calib.collect_item_ids), 4)  # 1 item × 4 malhas
        self.assertTrue(all(c.malha_id for c in calib.collect_item_ids))

    # ─────────────────────────────────────────────────────────────
    # Counts agregados na OS
    # ─────────────────────────────────────────────────────────────
    def test_os_collect_counts_aggregated(self):
        so = self._confirm_so_with([{
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 2})],
        }])
        os = so.qualificacao_os_ids
        # QI: 2 items + QD: 1 qualif + 2 items × 2 cycles = 2+1+4 = 7
        self.assertEqual(os.collect_total_count, 7)
        self.assertEqual(os.collect_pending_count, 7)  # all pending required
        self.assertEqual(os.collect_collected_count, 0)

    # ─────────────────────────────────────────────────────────────
    # SO sem procedimento aplicável: explosão skip
    # ─────────────────────────────────────────────────────────────
    def test_so_with_qs_no_proc_no_explosion(self):
        # QS não tem procedimento configurado
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qs": True},
        ])
        qualif = so.qualificacao_ids
        self.assertEqual(qualif.qualification_type, "software")
        self.assertEqual(len(qualif.collect_item_ids), 0)

    # ─────────────────────────────────────────────────────────────
    # Wizard "Aplicar Procedimento": filtra itens pela fase da qualif
    # ─────────────────────────────────────────────────────────────
    def test_wizard_apply_filters_by_phase(self):
        # confirma SO com 1 qualif QI (proc_category auto-explode os itens QI)
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        qualif = so.qualificacao_ids
        os = so.qualificacao_os_ids
        # limpa coletas auto-explodidas no confirm p/ isolar o efeito do wizard
        qualif.collect_item_ids.unlink()
        Wizard = self.env["afr.qualificacao.os.apply.procedimento.wizard"]
        wiz = Wizard.with_context(default_os_id=os.id).create({})
        line = wiz.line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.qualificacao_id, qualif)
        # default_get já resolveu o procedimento da categoria do equipamento
        self.assertEqual(line.procedimento_id, self.proc_category)
        wiz.action_apply()
        names = qualif.collect_item_ids.mapped("name")
        # proc_category tem QI(2) + QD(3) + Calib(1); qualif QI recebe só os 2 QI
        self.assertEqual(len(qualif.collect_item_ids), 2)
        self.assertIn("Foto plaqueta", names)
        self.assertNotIn("Dados qualificador térmico", names)  # item QD fica de fora

    def test_wizard_form_save_keeps_qualificacao_id(self):
        """Regressão: qualificacao_id é readonly na tree — sem force_save="1"
        no XML, o client web descarta o valor no save e o create() da linha
        falha (required). Form() reproduz o mesmo caminho do client."""
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        qualif = so.qualificacao_ids
        os = so.qualificacao_os_ids
        Wizard = self.env["afr.qualificacao.os.apply.procedimento.wizard"]
        with Form(Wizard.with_context(default_os_id=os.id)) as f:
            pass
        wiz = f.save()
        self.assertEqual(wiz.line_ids.qualificacao_id, qualif)

    # ─────────────────────────────────────────────────────────────
    # OS mista: categorias diferentes → procedimento default por linha
    # ─────────────────────────────────────────────────────────────
    def _make_mixed_os(self):
        """OS com 2 qualifs de categorias diferentes (fora do fluxo SO/
        configurador, que restringe cycle/malha types por categoria — aqui
        só interessa exercitar o wizard sobre afr.qualificacao.os)."""
        category2 = self.env["engc.equipment.category"].create({"name": "Test-Seladora"})
        equip3 = self.env["engc.equipment"].create({
            "client_id": self.partner.id,
            "category_id": category2.id,
            "model": "TestModel3", "serial_number": "TSN-003",
            "means_of_aquisition_id": self.means.id,
            "location_id": self.location.id,
            "marca_id": self.marca.id,
        })
        os = self.env["afr.qualificacao.os"].create({})
        qualif1 = self.env["afr.qualificacao"].create({
            "name": "Qualif mista 1 (categoria específica)",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os.id,
        })
        qualif2 = self.env["afr.qualificacao"].create({
            "name": "Qualif mista 2 (fallback)",
            "equipment_id": equip3.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os.id,
        })
        return os, qualif1, qualif2, category2, equip3

    def test_wizard_default_lines_resolve_procedimento_per_qualif_mixed_os(self):
        os, qualif1, qualif2, _category2, _equip3 = self._make_mixed_os()
        Wizard = self.env["afr.qualificacao.os.apply.procedimento.wizard"]
        wiz = Wizard.with_context(default_os_id=os.id).create({})
        self.assertEqual(len(wiz.line_ids), 2)
        line1 = wiz.line_ids.filtered(lambda l: l.qualificacao_id == qualif1)
        line2 = wiz.line_ids.filtered(lambda l: l.qualificacao_id == qualif2)
        # qualif1: equipamento da categoria com procedimento específico
        self.assertEqual(line1.procedimento_id, self.proc_category)
        # qualif2: categoria sem procedimento específico → fallback genérico
        self.assertEqual(line2.procedimento_id, self.proc_fallback)

    def test_wizard_action_apply_rejects_procedimento_of_other_category(self):
        """Domain do campo só protege a UI — server-side tem que validar
        de novo, senão dá pra forçar via RPC um procedimento de categoria
        errada (ex: aplicar protocolo de autoclave numa seladora)."""
        os, _qualif1, qualif2, _category2, _equip3 = self._make_mixed_os()
        Wizard = self.env["afr.qualificacao.os.apply.procedimento.wizard"]
        wiz = Wizard.with_context(default_os_id=os.id).create({})
        line2 = wiz.line_ids.filtered(lambda l: l.qualificacao_id == qualif2)
        # força um procedimento específico de OUTRA categoria (o domain do
        # campo impediria isso na UI, mas o servidor tem que barrar também)
        line2.procedimento_id = self.proc_category.id
        with self.assertRaises(UserError):
            wiz.action_apply()

    def test_wizard_action_apply_rejects_selected_line_without_procedimento(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        qualif = so.qualificacao_ids
        os = so.qualificacao_os_ids
        qualif.collect_item_ids.unlink()
        Wizard = self.env["afr.qualificacao.os.apply.procedimento.wizard"]
        wiz = Wizard.with_context(default_os_id=os.id).create({})
        wiz.line_ids.procedimento_id = False
        with self.assertRaises(UserError):
            wiz.action_apply()

    # ─────────────────────────────────────────────────────────────
    # overwrite_existing: troca de procedimento sem duplicar / sem apagar coletado
    # ─────────────────────────────────────────────────────────────
    def test_wizard_overwrite_switches_procedure_leaves_only_new_set(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        qualif = so.qualificacao_ids
        os = so.qualificacao_os_ids
        qualif.collect_item_ids.unlink()
        Wizard = self.env["afr.qualificacao.os.apply.procedimento.wizard"]

        # 1ª aplicação: proc_category (2 itens QI)
        wiz1 = Wizard.with_context(default_os_id=os.id).create({})
        wiz1.action_apply()
        self.assertEqual(len(qualif.collect_item_ids), 2)

        # procedimento QI alternativo (genérico, categoria vazia — não colide
        # com proc_fallback: unique(equipment_category_id, company_id) trata
        # NULL como distinto entre si no Postgres)
        proc_qi_alt = self.env["afr.qualificacao.procedimento"].create({
            "name": "Procedimento QI Alternativo",
            "item_ids": [
                (0, 0, {"name": "Assinatura termo", "kind": "pdf",
                        "phase": "installation", "target_level": "qualificacao",
                        "sequence": 10}),
            ],
        })

        # 2ª aplicação com overwrite: troca de procedimento, sem duplicar
        wiz2 = Wizard.with_context(default_os_id=os.id).create({
            "overwrite_existing": True,
        })
        wiz2.line_ids.procedimento_id = proc_qi_alt.id
        wiz2.action_apply()
        self.assertEqual(qualif.collect_item_ids.mapped("name"), ["Assinatura termo"])

    def test_wizard_overwrite_refuses_when_collected(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        qualif = so.qualificacao_ids
        os = so.qualificacao_os_ids
        qualif.collect_item_ids.unlink()
        Wizard = self.env["afr.qualificacao.os.apply.procedimento.wizard"]

        wiz1 = Wizard.with_context(default_os_id=os.id).create({})
        wiz1.action_apply()
        items = qualif.collect_item_ids
        self.assertEqual(len(items), 2)
        # marca um item como coletado (write com file dispara state=collected)
        items[0].write({"file": base64.b64encode(b"conteudo-fake")})
        self.assertEqual(items[0].state, "collected")

        proc_qi_alt = self.env["afr.qualificacao.procedimento"].create({
            "name": "Procedimento QI Alternativo 2",
            "item_ids": [
                (0, 0, {"name": "Outro doc", "kind": "pdf",
                        "phase": "installation", "target_level": "qualificacao",
                        "sequence": 10}),
            ],
        })
        wiz2 = Wizard.with_context(default_os_id=os.id).create({
            "overwrite_existing": True,
        })
        wiz2.line_ids.procedimento_id = proc_qi_alt.id
        with self.assertRaises(UserError):
            wiz2.action_apply()
        # nada foi apagado
        self.assertEqual(len(qualif.collect_item_ids), 2)

    # ─────────────────────────────────────────────────────────────
    # Nome do collect.item ciclo/malha = display_name do ciclo/malha
    # ─────────────────────────────────────────────────────────────
    def test_explosion_name_is_malha_display_name(self):
        so = self._confirm_so_with([{
            "equipment_id": self.equip1.id,
            "calib_line_ids": [(0, 0, {"malha_type_id": self.malha_temp.id, "qty": 1})],
        }])
        calib = so.qualificacao_ids.filtered(
            lambda q: q.qualification_type == "calibration")
        items = calib.collect_item_ids.filtered(lambda c: c.malha_id)
        self.assertTrue(items)
        for ci in items:
            self.assertEqual(ci.name, ci.malha_id.display_name)

    def test_explosion_name_is_cycle_display_name(self):
        so = self._confirm_so_with([{
            "equipment_id": self.equip1.id,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 1})],
        }])
        qd = so.qualificacao_ids.filtered(
            lambda q: q.qualification_type == "performance")
        items = qd.collect_item_ids.filtered(lambda c: c.cycle_id)
        self.assertTrue(items)
        for ci in items:
            self.assertEqual(ci.name, ci.cycle_id.display_name)

