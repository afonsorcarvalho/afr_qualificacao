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
