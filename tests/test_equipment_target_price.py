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
        # price_unit incluído no mesmo write: o compute nativo de price_unit
        # (core, não a flag is_rateio_priced — esta linha nunca é rateada)
        # depende de product_uom_qty e resetaria pro list_price do produto
        # se o valor não viesse explícito nesta mesma chamada.
        declinada.write({"part": "01", "part01_declined": True,
                         "product_uom_qty": 0.0,
                         "price_unit": declinada.price_unit})
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

    def test_apply_raises_when_line_has_discount(self):
        """Rateio não suporta desconto por linha: quebraria a proporção
        entre linhas (price_subtotal = price_unit × qty × (1-discount/100))
        e o helper de rateio não sabe disso."""
        from odoo.exceptions import UserError
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        linha.discount = 10.0
        section.equipment_target_price = 1000.0
        with self.assertRaises(UserError):
            section._apply_equipment_target()

    def test_frozen_line_keeps_price_unit_on_qty_change(self):
        """Linha com is_rateio_priced=True não sofre o recompute nativo de
        price_unit (core) ao ter product_uom_qty editado."""
        so = self._so()
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        linha.write({"is_rateio_priced": True})
        linha.write({"product_uom_qty": 10.0})
        self.assertEqual(linha.price_unit, 200.0)

    def test_managed_line_without_flag_reprices_on_qty_change(self):
        """Linha managed que NUNCA foi rateada (sem is_rateio_priced)
        continua repreçando pela pricelist ao mudar qty — 'Atualizar
        Preços' do pedido precisa continuar funcionando nela."""
        so = self._so()
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        linha.write({"product_uom_qty": 10.0})
        self.assertEqual(linha.price_unit, self.product_qd_cmax.list_price)

    def test_non_managed_line_reprices_on_qty_change(self):
        """Linha comum (sem is_qualificacao_managed) nunca ganha a flag —
        segue repreçando pela pricelist normalmente."""
        so = self._so()
        linha = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.product_qd_cmax.id,
            "name": "Linha avulsa", "product_uom_qty": 1.0,
            "price_unit": 999.0,
        })
        linha.write({"product_uom_qty": 5.0})
        self.assertEqual(linha.price_unit, self.product_qd_cmax.list_price)

    def test_equipment_target_ids_lists_only_sections(self):
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self.assertIn(section, so.equipment_target_ids)
        self.assertNotIn(linha, so.equipment_target_ids)

    def test_apply_all_processes_every_drifted_equipment(self):
        so = self._so()
        s1 = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        s2 = self._section(so, self.equip2)
        self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo eq2", "is_qualificacao_managed": True,
            "qualification_type": "performance", "equipment_id": self.equip2.id,
            "cycle_type_id": self.cycle_cmax.id, "qualif_cycle_qty": 2,
            "estimated_hours": 1.0, "product_uom_qty": 2.0,
            "price_unit": 300.0,
        })
        # 3000.0 (não 2000.0 como no brief): com uma única linha de 7,5h na
        # base, o subtotal só alcança múltiplos exatos de R$0,075 (qty × 0,01
        # de grão do price_unit) — 2000.0 não é múltiplo de 0,075 e portanto
        # NUNCA fecha exato (ver price_allocation.py, docstring do módulo).
        # 3000.0 = 400.00 × 7.5, exato.
        s1.equipment_target_price = 3000.0
        s2.equipment_target_price = 900.0
        so.action_apply_all_equipment_targets()
        self.assertEqual(s1.equipment_target_state, "ok")
        self.assertEqual(s2.equipment_target_state, "ok")

    def test_apply_all_skips_sections_without_target(self):
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        so.action_apply_all_equipment_targets()   # sem alvo: não faz nada
        self.assertEqual(linha.price_unit, 200.0)

    def test_new_line_gets_pricelist_price_even_with_flag(self):
        """Linha nova (sem id persistido) nunca é congelada: mesmo com
        is_rateio_priced=True já no create e sem price_unit explícito, ela
        recebe o preço da pricelist normalmente (_origin.id é falso)."""
        so = self._so()
        linha = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.cycle_cmax.product_id.id,
            "name": "Nova linha", "product_uom_qty": 2.0,
            "is_qualificacao_managed": True, "is_rateio_priced": True,
            "qualification_type": "performance", "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
        })
        self.assertEqual(linha.price_unit, self.product_qd_cmax.list_price)
