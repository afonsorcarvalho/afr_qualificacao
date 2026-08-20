# -*- coding: utf-8 -*-
"""Escopo por equipamento como tabela única — camada de agregação."""

from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestScopeLinesAndHours(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _section(self, so, equip, work_hours=8.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": equip.display_name,
            "is_qualificacao_managed": True,
            "equipment_id": equip.id,
            "work_hours_per_day": work_hours,
        })

    def _cycle_line(self, so, equip, qtype, part, qty, hours, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo",
            "is_qualificacao_managed": True,
            "qualification_type": qtype,
            "part": part,
            "equipment_id": equip.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": qty,
            "estimated_hours": hours,
            "product_uom_qty": qty * hours,
            "price_unit": price,
        })

    def test_scope_lines_match_rateio_base(self):
        """O conjunto do escopo é exatamente o do rateio."""
        so = self._so()
        section = self._section(so, self.equip1)
        firme = self._cycle_line(so, self.equip1, "performance", False, 3, 2.0, 200.0)
        opcional = self._cycle_line(so, self.equip1, "performance", False, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True, "optional_accepted": True})
        declinada = self._cycle_line(so, self.equip1, "installation", "01", 1, 1.0, 900.0)
        declinada.write({"part01_declined": True, "product_uom_qty": 0.0})

        scope = so._qualif_scope_lines(self.equip1)
        self.assertEqual(scope, section._rateio_base_lines())
        self.assertIn(firme, scope)
        self.assertNotIn(opcional, scope)
        self.assertNotIn(declinada, scope)
        self.assertNotIn(section, scope)

    def test_scope_lines_filter_by_type_and_part(self):
        so = self._so()
        self._section(so, self.equip1)
        qo2 = self._cycle_line(so, self.equip1, "operational", "02", 2, 1.0, 100.0)
        qd = self._cycle_line(so, self.equip1, "performance", False, 3, 1.0, 200.0)

        self.assertEqual(so._qualif_scope_lines(self.equip1, "operational", "02"), qo2)
        self.assertEqual(so._qualif_scope_lines(self.equip1, "performance", None), qd)
        self.assertFalse(so._qualif_scope_lines(self.equip1, "operational", "01"))

    def test_group_hours_uses_qualif_cycle_qty(self):
        so = self._so()
        self._section(so, self.equip1)
        lines = self._cycle_line(so, self.equip1, "performance", False, 3, 2.5, 200.0)
        self.assertEqual(so._qualif_group_hours(lines), 7.5)

    def test_days_round_up_to_next_half(self):
        so = self._so()
        self._section(so, self.equip1, work_hours=8.0)
        self.assertEqual(so._qualif_days_from_hours(4.0, self.equip1), 0.5)
        self.assertEqual(so._qualif_days_from_hours(4.1, self.equip1), 1.0)
        self.assertEqual(so._qualif_days_from_hours(8.0, self.equip1), 1.0)
        self.assertEqual(so._qualif_days_from_hours(25.6, self.equip1), 3.5)
        self.assertEqual(so._qualif_days_from_hours(0.0, self.equip1), 0.0)

    def test_days_respect_work_hours_per_day(self):
        so = self._so()
        self._section(so, self.equip1, work_hours=4.0)
        self.assertEqual(so._qualif_days_from_hours(4.0, self.equip1), 1.0)


@tagged("post_install", "-at_install")
class TestScopeRef(AfrQualificacaoTestCommon):

    def _so_with_blocks(self):
        """SO com 2 blocos numerados: SEC-QI (nº 1) e SEC-QO (nº 2)."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        Block = self.env["afr.proposal.block"]
        self.sec_qi = self.env.ref("afr_qualificacao.proposal_section_qi")
        self.sec_qo = self.env.ref("afr_qualificacao.proposal_section_qo")
        self.blk_qi = Block.create({
            "sale_order_id": so.id, "block_kind": "static",
            "section_id": self.sec_qi.id, "sequence": 10, "included": True,
        })
        self.blk_qo = Block.create({
            "sale_order_id": so.id, "block_kind": "static",
            "section_id": self.sec_qo.id, "sequence": 20, "included": True,
        })
        return so

    def test_ref_cites_block_number(self):
        so = self._so_with_blocks()
        ref = so._qualif_scope_ref("installation")
        self.assertIn("Conforme item 1", ref)
        self.assertIn(self.sec_qi.name, ref)

    def test_ref_second_block_gets_number_two(self):
        so = self._so_with_blocks()
        self.assertIn("Conforme item 2", so._qualif_scope_ref("operational"))

    def test_ref_without_block_degrades_to_topic_name(self):
        so = self._so_with_blocks()
        ref = so._qualif_scope_ref("performance")
        self.assertNotIn("Conforme item", ref)
        self.assertIn("Qualificação de Desempenho", ref)

    def test_ref_without_number_degrades(self):
        """show_number=False → numbering devolve '' → sem 'Conforme item'."""
        so = self._so_with_blocks()
        self.blk_qi.show_number = False
        ref = so._qualif_scope_ref("installation")
        self.assertNotIn("Conforme item", ref)
        self.assertIn(self.sec_qi.name, ref)

    def test_ref_unknown_type_never_returns_falsy(self):
        so = self._so_with_blocks()
        self.assertTrue(so._qualif_scope_ref(False))
        self.assertTrue(so._qualif_scope_ref("inexistente"))
