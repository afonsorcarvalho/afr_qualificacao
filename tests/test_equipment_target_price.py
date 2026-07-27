# -*- coding: utf-8 -*-
"""Rateio de preço final por equipamento — camada ORM."""

from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestEquipmentTargetPrice(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _section(self, so, equip):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": equip.display_name,
            "is_qualificacao_managed": True,
            "equipment_id": equip.id,
        })

    def _cycle_line(self, so, equip, qty_cycles, hours, price):
        """Linha de ciclo: product_uom_qty = horas = nº ciclos × horas/ciclo."""
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo",
            "is_qualificacao_managed": True,
            "qualification_type": "performance",
            "equipment_id": equip.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": qty_cycles,
            "estimated_hours": hours,
            "product_uom_qty": qty_cycles * hours,
            "price_unit": price,
        })

    def test_base_excludes_section_and_optional(self):
        so = self._so()
        section = self._section(so, self.equip1)
        firme = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        opcional = self._cycle_line(so, self.equip1, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True,
                        "optional_accepted": True})
        base = section._rateio_base_lines()
        self.assertIn(firme, base)
        self.assertNotIn(opcional, base)
        self.assertNotIn(section, base)

    def test_base_excludes_declined_part01(self):
        so = self._so()
        section = self._section(so, self.equip1)
        firme = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        declinada = self._cycle_line(so, self.equip1, 1, 1.0, 900.0)
        declinada.write({"part": "01", "part01_declined": True,
                         "product_uom_qty": 0.0})
        base = section._rateio_base_lines()
        self.assertEqual(base, firme)

    def test_state_none_without_target(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self.assertEqual(section.equipment_target_state, "none")
        self.assertEqual(section.equipment_target_delta, 0.0)

    def test_state_drift_and_delta(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)  # 7,5h × 200 = 1500
        section.equipment_target_price = 1200.0
        self.assertEqual(section.equipment_target_state, "drift")
        self.assertEqual(section.equipment_target_delta, 300.0)

    def test_state_ok_when_matching(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        section.equipment_target_price = 1500.0
        self.assertEqual(section.equipment_target_state, "ok")
        self.assertEqual(section.equipment_target_delta, 0.0)

    def test_equipment_subtotal_excludes_optionals(self):
        """equipment_subtotal alinhado com a base do rateio."""
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        opcional = self._cycle_line(so, self.equip1, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True,
                        "optional_accepted": True})
        self.assertEqual(section.equipment_subtotal, 1500.0)

    def test_apply_exact_with_unit_line(self):
        """Alvo redondo com linha qty=1 na base: soma bate exatamente."""
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)   # 7,5h
        self._cycle_line(so, self.equip1, 3, 4.1, 300.0)   # 12,3h
        self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.product_qs.id,
            "name": "QS", "is_qualificacao_managed": True,
            "qualification_type": "software", "equipment_id": self.equip1.id,
            "qualif_cycle_qty": 1, "estimated_hours": 1.0,
            "product_uom_qty": 1.0, "price_unit": 800.0,
        })
        section.equipment_target_price = 10000.0
        section._apply_equipment_target()
        self.assertEqual(
            sum(section._rateio_base_lines().mapped("price_subtotal")),
            10000.0)
        self.assertEqual(section.equipment_target_state, "ok")

    def test_apply_only_fractional_lines(self):
        """Sem linha qty=1: a busca combinada precisa fechar."""
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self._cycle_line(so, self.equip1, 3, 4.1, 300.0)
        section.equipment_target_price = 10000.0
        section._apply_equipment_target()
        self.assertEqual(
            sum(section._rateio_base_lines().mapped("price_subtotal")),
            10000.0)

    def test_apply_is_idempotent(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self._cycle_line(so, self.equip1, 3, 4.1, 300.0)
        section.equipment_target_price = 10000.0
        section._apply_equipment_target()
        first = section._rateio_base_lines().mapped("price_unit")
        section._apply_equipment_target()
        self.assertEqual(section._rateio_base_lines().mapped("price_unit"),
                         first)

    def test_apply_preserves_mix(self):
        """Proporção entre linhas mantida: 1000 e 3000 viram 2000 e 6000."""
        so = self._so()
        section = self._section(so, self.equip1)
        a = self._cycle_line(so, self.equip1, 1, 1.0, 1000.0)
        b = self._cycle_line(so, self.equip1, 1, 1.0, 3000.0)
        section.equipment_target_price = 8000.0
        section._apply_equipment_target()
        self.assertEqual(a.price_subtotal, 2000.0)
        self.assertEqual(b.price_subtotal, 6000.0)

    def test_apply_does_not_touch_excluded_lines(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        declinada = self._cycle_line(so, self.equip1, 1, 1.0, 900.0)
        declinada.write({"part": "01", "part01_declined": True,
                         "product_uom_qty": 0.0})
        opcional = self._cycle_line(so, self.equip1, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True,
                        "optional_accepted": True})
        section.equipment_target_price = 3000.0
        section._apply_equipment_target()
        self.assertEqual(declinada.price_unit, 900.0)
        self.assertEqual(opcional.price_unit, 500.0)
        self.assertEqual(section.price_unit, 0.0)

    def test_apply_raises_when_base_is_free(self):
        from odoo.exceptions import UserError
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 0.0)
        section.equipment_target_price = 1000.0
        with self.assertRaises(UserError):
            section._apply_equipment_target()

    def test_apply_raises_when_base_is_empty(self):
        from odoo.exceptions import UserError
        so = self._so()
        section = self._section(so, self.equip1)
        section.equipment_target_price = 1000.0
        with self.assertRaises(UserError):
            section._apply_equipment_target()

    def test_zero_target_clears_without_touching_prices(self):
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        section.equipment_target_price = 0.0
        section._apply_equipment_target()
        self.assertEqual(linha.price_unit, 200.0)
        self.assertEqual(section.equipment_target_state, "none")

    def test_drift_after_editing_cycles(self):
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        section.equipment_target_price = 3000.0
        section._apply_equipment_target()
        self.assertEqual(section.equipment_target_state, "ok")
        linha.write({"qualif_cycle_qty": 4, "product_uom_qty": 4 * 2.5})
        self.assertEqual(section.equipment_target_state, "drift")
        self.assertEqual(section.equipment_target_delta, 1000.0)

    def test_inexact_posts_message_and_stays_drift(self):
        """Alvo inatingível: grava a melhor aproximação, avisa, fica drift."""
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 1, 3.0, 100.0)  # grade R$ 0,03
        section.equipment_target_price = 1000.01
        section._apply_equipment_target()
        self.assertEqual(section.equipment_target_state, "drift")
        self.assertTrue(any(
            "arredondamento" in (m.body or "")
            for m in so.message_ids))
