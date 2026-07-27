# -*- coding: utf-8 -*-
"""Testes puros do helper de rateio (sem ORM — TransactionCase desnecessário)."""

from odoo.tests.common import TransactionCase, tagged

from ..models.price_allocation import allocate_target, subtotal_for


@tagged("post_install", "-at_install")
class TestPriceAllocation(TransactionCase):

    def _achieved(self, lines, price_units):
        return sum(
            subtotal_for(qty, pu)
            for (qty, _sub), pu in zip(lines, price_units)
        )

    def test_half_up_rounding(self):
        """subtotal_for usa HALF-UP, não banker's rounding do Python."""
        # round(0.075, 2) do Python dá 0.07; a moeda do Odoo dá 0.08.
        self.assertEqual(subtotal_for(7.5, 0.01), 0.08)

    def test_exact_with_unit_line(self):
        """Linha qty=1 tem grade de R$ 0,01 — fecha exato sempre."""
        lines = [(7.5, 1500.0), (12.3, 2000.0), (1.0, 1000.0)]
        res = allocate_target(10000.0, lines)
        self.assertTrue(res["exact"])
        self.assertEqual(res["achieved"], 10000.0)
        self.assertEqual(self._achieved(lines, res["price_units"]), 10000.0)

    def test_exact_only_fractional_lines(self):
        """Sem linha qty=1: a busca combinada precisa fechar."""
        lines = [(7.5, 1500.0), (12.3, 2000.0)]
        res = allocate_target(10000.0, lines)
        self.assertTrue(res["exact"])
        self.assertEqual(self._achieved(lines, res["price_units"]), 10000.0)

    def test_proportion_preserved(self):
        """Dobrar o alvo dobra cada price_unit (mix preservado)."""
        lines = [(1.0, 1000.0), (1.0, 3000.0)]
        res = allocate_target(8000.0, lines)
        self.assertEqual(res["price_units"], [2000.0, 6000.0])

    def test_degenerate_tiny_target(self):
        """Alvo minúsculo com linha longa: sem preço negativo, sem resíduo perdido."""
        lines = [(100.0, 10000.0), (1.0, 100.0)]
        res = allocate_target(10.0, lines)
        self.assertTrue(all(pu >= 0.0 for pu in res["price_units"]))
        self.assertEqual(self._achieved(lines, res["price_units"]),
                         res["achieved"])

    def test_idempotent(self):
        """Rodar sobre o resultado anterior não muda nada."""
        lines = [(7.5, 1500.0), (12.3, 2000.0), (1.0, 1000.0)]
        first = allocate_target(10000.0, lines)
        relines = [
            (qty, subtotal_for(qty, pu))
            for (qty, _s), pu in zip(lines, first["price_units"])
        ]
        second = allocate_target(10000.0, relines)
        self.assertEqual(second["price_units"], first["price_units"])

    def test_reports_inexact_without_crashing(self):
        """Alvo inatingível: devolve exact=False com a melhor aproximação."""
        # Uma única linha de 3h: grade de R$ 0,03. Alvo em 0,01 é inatingível.
        lines = [(3.0, 300.0)]
        res = allocate_target(1000.01, lines)
        self.assertFalse(res["exact"])
        self.assertLess(abs(res["achieved"] - 1000.01), 0.03)
