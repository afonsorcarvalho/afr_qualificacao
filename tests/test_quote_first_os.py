# -*- coding: utf-8 -*-
"""Testes do cutover quote-first 16.0.3.1.0:
SO confirm cria 1 afr.qualificacao.os agregando equipamentos × tipos qualif,
sem mais criar engc.os para SOs de qualificação.
"""
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "quote_first_os", "post_install", "-at_install")
class TestQuoteFirstOs(AfrQualificacaoTestCommon):

    def _confirm_so_with(self, equipment_lines_spec):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, spec) for spec in equipment_lines_spec]
        wiz.action_apply()
        so.action_confirm()
        return so

    # ─────────────────────────────────────────────────────────────
    # 1 OS por SO agregando equipamentos
    # ─────────────────────────────────────────────────────────────
    def test_one_os_per_so_aggregating_two_equips(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True, "do_qo": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])
        self.assertEqual(so.qualificacao_os_count, 1)
        os = so.qualificacao_os_ids
        self.assertEqual(len(os.equipment_ids), 2)
        self.assertEqual(len(os.qualificacao_ids), 3)  # 2 QI + 1 QO

    def test_os_sale_order_id_backref(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        os = so.qualificacao_os_ids
        self.assertEqual(os.sale_order_id, so)

    def test_os_partner_from_qualif(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        os = so.qualificacao_os_ids
        # partner_id é computed do primeiro qualif.partner_id
        self.assertEqual(os.partner_id, self.partner)

    def test_os_starts_draft(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        os = so.qualificacao_os_ids
        self.assertEqual(os.state, "draft")
        # Tecnico default não preenchido (gestor atribui pós-confirm)
        self.assertFalse(os.tecnico_default_id)

    # ─────────────────────────────────────────────────────────────
    # Cutover engc.os NÃO criado
    # ─────────────────────────────────────────────────────────────
    def test_engc_os_not_created_in_cutover(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qo": True},
        ])
        self.assertEqual(so.engc_os_count, 0)
        self.assertEqual(so.qualificacao_os_count, 1)

    # ─────────────────────────────────────────────────────────────
    # Qualifs vinculadas via os_id (não mais engc_os_id)
    # ─────────────────────────────────────────────────────────────
    def test_qualifs_linked_to_os_not_engc_os(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        qualif = so.qualificacao_ids
        self.assertTrue(qualif.os_id)
        self.assertEqual(qualif.os_id, so.qualificacao_os_ids)
        self.assertFalse(qualif.engc_os_id)  # NÃO preenchido (deprecated)

    # ─────────────────────────────────────────────────────────────
    # Cycles/Malhas mantidos (lógica F1 preservada)
    # ─────────────────────────────────────────────────────────────
    def test_cycles_still_exploded_by_qty(self):
        so = self._confirm_so_with([{
            "equipment_id": self.equip1.id,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 4})],
        }])
        qd = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "performance")
        self.assertEqual(qd.cycle_count, 4)
        # Cycles têm os_id via qualif
        self.assertEqual(qd.cycle_ids.mapped("qualificacao_id.os_id"), so.qualificacao_os_ids)

    # ─────────────────────────────────────────────────────────────
    # Idempotência re-confirm
    # ─────────────────────────────────────────────────────────────
    def test_re_confirm_does_not_duplicate_os(self):
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        # Re-chama explosão direta — não deve duplicar
        so._create_qualificacoes_from_lines()
        self.assertEqual(so.qualificacao_os_count, 1)
        self.assertEqual(so.qualificacao_count, 1)

    # ─────────────────────────────────────────────────────────────
    # SO sem linhas managed: nenhuma OS
    # ─────────────────────────────────────────────────────────────
    def test_so_without_qualif_lines_creates_no_os(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product_qi.id, "product_uom_qty": 1,
            })],
        })
        so.action_confirm()
        self.assertEqual(so.qualificacao_os_count, 0)
