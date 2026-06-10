# -*- coding: utf-8 -*-
"""Testes da explosão de procedimento em collect.items no SO confirm (F3)."""
from odoo.tests import tagged

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
        so.action_confirm()
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
        # proc_qi tem 2 items target=qualificacao → 2 collect.items
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
        # proc_qd_autoclave: 2 items cycle + 1 qualificacao = 2*3 + 1 = 7
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
