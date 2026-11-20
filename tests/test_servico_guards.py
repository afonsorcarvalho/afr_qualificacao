"""Guardas das linhas e unidades de serviço: número do item imutável,
quantidade inteira, redução pelo configurador, desconto geral em cotação
mista e numeração da cópia.
"""

from contextlib import contextmanager

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common_servico import AfrServicoTestCommon


@tagged("post_install", "-at_install")
class TestServicoGuards(AfrServicoTestCommon):

    @contextmanager
    def _raises(self, exception, text):
        """`assertRaises` do Odoo (com savepoint) + trecho da mensagem."""
        with self.assertRaises(exception) as caught:
            yield
        self.assertIn(text, str(caught.exception))

    def _wizard(self, order):
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": order.id,
        })
        wiz._load_from_existing_lines()
        return wiz

    def _mixed_order(self, sel_qty=3):
        order = self._make_order()
        wiz = self._wizard(order)
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id, "do_qi": True,
        })]
        self.env["afr.qualificacao.configurator.service"].create({
            "wizard_id": wiz.id, "service_id": self.svc_seladora.id,
            "qty": sel_qty, "unit_price": 120.0, "estimated_hours": 0.5,
        })
        wiz.action_apply()
        return order

    def _confirmed(self, qty=3):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, qty)
        order.action_confirm()
        return order, line

    # -- M3: número do item -------------------------------------------------

    def test_item_number_cannot_change(self):
        _order, line = self._confirmed()
        unit = line.service_unit_ids.filtered(lambda u: u.item_number == 2)
        with self._raises(UserError, "não pode ser alterado"):
            unit.write({"item_number": 9})
        with self._raises(UserError, "não pode ser alterado"):
            unit.write({"item_number": 0})
        self.assertEqual(unit.item_number, 2)
        # Mesmo valor e outros campos continuam editáveis.
        unit.write({"item_number": 2, "tag": "TAG-001"})
        self.assertEqual(unit.tag, "TAG-001")

    def test_item_number_not_set_by_hand(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        Unit = self.env["afr.servico.unidade"]
        with self.assertRaises(UserError):
            Unit.create({"line_id": line.id, "item_number": 7})
        unit = Unit.create({"line_id": line.id})
        with self.assertRaises(UserError):
            unit.write({"item_number": 7})
        self.assertEqual(unit.item_number, 0)
        order.action_confirm()
        self.assertEqual(
            sorted(line.service_unit_ids.mapped("item_number")), [1, 2])

    def test_numbered_unit_cannot_change_line(self):
        order, line = self._confirmed()
        other = self._add_service(order, self.svc_incubadora, 2)
        unit = line.service_unit_ids[:1]
        self.assertTrue(unit.item_number)
        with self._raises(UserError, "não pode mudar de linha"):
            unit.write({"line_id": other.id})
        self.assertEqual(unit.line_id, line)

    def test_unnumbered_unit_can_change_line(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        other = self._add_service(order, self.svc_incubadora, 2)
        unit = self.env["afr.servico.unidade"].create({"line_id": line.id})
        unit.write({"line_id": other.id})
        self.assertEqual(unit.line_id, other)

    def test_internal_numbering_still_works(self):
        order, line = self._confirmed(qty=2)
        line.product_uom_qty = 4
        self.assertEqual(
            sorted(line.service_unit_ids.mapped("item_number")), [1, 2, 3, 4])

    # -- M4: quantidade inteira --------------------------------------------

    def test_fractional_qty_blocked(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        with self._raises(ValidationError, "número inteiro"):
            line.write({"product_uom_qty": 2.5})
        with self._raises(ValidationError, "número inteiro"):
            self._add_service(order, self.svc_incubadora, 1.5)

    def test_negative_qty_blocked(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        with self._raises(ValidationError, "número inteiro"):
            line.write({"product_uom_qty": -1})
        line.write({"product_uom_qty": 0})
        self.assertEqual(line.product_uom_qty, 0)

    def test_fractional_qty_allowed_on_other_lines(self):
        order = self._make_order()
        line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.svc_seladora.product_id.id,
            "product_uom_qty": 2.5,
        })
        self.assertEqual(line.product_uom_qty, 2.5)

    # -- configurador: reduzir abaixo das identificadas ----------------------

    def test_wizard_reduce_below_identified_changes_nothing(self):
        order = self._mixed_order(sel_qty=3)
        line = order._service_lines()
        Unit = self.env["afr.servico.unidade"]
        Unit.create([
            {"line_id": line.id, "tag": "TAG-001"},
            {"line_id": line.id, "tag": "TAG-002"},
        ])
        qualif_before = order.order_line.filtered(
            "is_qualificacao_managed").ids
        units_before = line.service_unit_ids.ids
        total_before = order.amount_untaxed

        wiz = self._wizard(order)
        wiz.service_line_ids.qty = 1
        with self._raises(UserError, "identificada"):
            wiz.action_apply()

        self.env.invalidate_all()
        self.assertEqual(line.product_uom_qty, 3)
        self.assertEqual(line.service_unit_ids.ids, units_before)
        self.assertEqual(
            sorted(line.service_unit_ids.mapped("tag")),
            ["TAG-001", "TAG-002"])
        self.assertEqual(
            order.order_line.filtered("is_qualificacao_managed").ids,
            qualif_before)
        self.assertEqual(order.amount_untaxed, total_before)

    # -- sale.order.write: remoção de unidade --------------------------------

    def test_order_write_only_unit_removal(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        unit = self.env["afr.servico.unidade"].create({
            "line_id": line.id, "tag": "TAG-001",
        })
        self.assertTrue(order.write({"service_unit_ids": [(2, unit.id)]}))
        self.assertFalse(unit.exists())

    # -- M11 (b): desconto geral percentual em cotação mista -----------------

    def test_percent_discount_on_mixed_quote(self):
        order = self._mixed_order(sel_qty=3)
        services_total = sum(order._service_lines().mapped("price_subtotal"))
        self.assertEqual(services_total, 360.0)
        base = order._qualif_discount_base()
        self.assertGreater(base, 0)
        before = order.amount_untaxed

        order.write({"qualif_discount_type": "percent",
                     "qualif_discount_value": 10.0})

        disc = round(base * 0.10, 2)
        disc_line = order.order_line.filtered("is_qualif_discount_line")
        self.assertAlmostEqual(disc_line.price_subtotal, -disc, places=2)
        self.assertAlmostEqual(order.amount_untaxed, before - disc, places=2)
        # Serviços não entram na base do desconto.
        self.assertEqual(
            sum(order._service_lines().mapped("price_subtotal")), 360.0)
        totals = order._qualif_proposal_totals()
        self.assertAlmostEqual(totals["discount_amount"], disc, places=2)
        self.assertAlmostEqual(totals["residual"], 0.0, places=2)
        rows = order._qualif_total_rows()
        self.assertAlmostEqual(
            sum(value for _label, value in rows), order.amount_untaxed,
            places=2)
        labels = [label for label, _value in rows]
        self.assertIn("Calibração de Instrumentos", labels)
        self.assertIn("Descontos", labels)

    # -- M11 (c): cópia reinicia a numeração ---------------------------------

    def test_copy_restarts_numbering(self):
        order, line = self._confirmed(qty=3)
        self.assertEqual(order.service_unit_last_number, 3)
        copy = order.copy()
        self.assertEqual(copy.service_unit_last_number, 0)
        self.assertFalse(copy.service_unit_ids)
        copy.action_confirm()
        self.assertEqual(
            sorted(copy.service_unit_ids.mapped("item_number")), [1, 2, 3])
        self.assertEqual(copy.service_unit_last_number, 3)
