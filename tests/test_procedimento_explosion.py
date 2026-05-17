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
        # Procedimento QD genérico (sem category) — fallback
        cls.proc_qd_generic = Proc.create({
            "name": "QD Genérico",
            "applicable_qualification_type": "performance",
            "item_ids": [
                (0, 0, {
                    "name": "Doc procedimento", "kind": "pdf",
                    "target_level": "qualificacao", "sequence": 10,
                }),
                (0, 0, {
                    "name": "Foto carga", "kind": "foto",
                    "target_level": "cycle", "sequence": 20,
                }),
            ],
        })
        # Procedimento QD específico para categoria autoclave — match preferencial
        cls.proc_qd_autoclave = Proc.create({
            "name": "QD Autoclave",
            "applicable_qualification_type": "performance",
            "equipment_category_id": cls.category.id,
            "item_ids": [
                (0, 0, {
                    "name": "Foto carga autoclave", "kind": "foto",
                    "target_level": "cycle", "sequence": 10,
                }),
                (0, 0, {
                    "name": "Dados qualificador térmico", "kind": "qualificador_data",
                    "target_level": "qualificacao", "sequence": 20,
                }),
                (0, 0, {
                    "name": "Indicador biológico", "kind": "foto",
                    "target_level": "cycle", "sequence": 30,
                }),
            ],
        })
        # Procedimento Calib
        cls.proc_calib = Proc.create({
            "name": "Calib Padrão",
            "applicable_qualification_type": "calibration",
            "item_ids": [
                (0, 0, {
                    "name": "Foto sensor in loco", "kind": "foto",
                    "target_level": "malha", "sequence": 10,
                }),
            ],
        })
        # Procedimento QI
        cls.proc_qi = Proc.create({
            "name": "QI Padrão",
            "applicable_qualification_type": "installation",
            "item_ids": [
                (0, 0, {
                    "name": "Foto plaqueta", "kind": "foto",
                    "target_level": "qualificacao", "sequence": 10,
                }),
                (0, 0, {
                    "name": "NF cópia", "kind": "pdf",
                    "target_level": "qualificacao", "sequence": 20,
                }),
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
    # resolve_for: match preferencial (type+category) > só type
    # ─────────────────────────────────────────────────────────────
    def test_resolve_prefers_category_match(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        rec = Proc.resolve_for("performance", self.category)
        self.assertEqual(rec, self.proc_qd_autoclave)

    def test_resolve_fallback_generic_when_no_category(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        other_cat = self.env["engc.equipment.category"].create({"name": "OutraCat"})
        rec = Proc.resolve_for("performance", other_cat)
        self.assertEqual(rec, self.proc_qd_generic)

    def test_resolve_returns_empty_when_no_match(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        # software type não tem procedimento
        rec = Proc.resolve_for("software", self.category)
        self.assertFalse(rec)

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
