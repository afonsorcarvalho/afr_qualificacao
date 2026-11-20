"""Passo "Outros serviços" do configurador (cotação multi-serviço)."""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common_servico import AfrServicoTestCommon


@tagged("post_install", "-at_install")
class TestServicoConfigurator(AfrServicoTestCommon):

    def _open_wizard(self, order):
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": order.id,
        })
        wiz._load_from_existing_lines()
        return wiz

    def _wiz_service(self, wiz, service, qty=1, unit_price=None, hours=None):
        vals = {
            "wizard_id": wiz.id,
            "service_id": service.id,
            "qty": qty,
            "unit_price": (
                service._default_unit_price()
                if unit_price is None else unit_price
            ),
            "estimated_hours": (
                service.estimated_hours if hours is None else hours
            ),
        }
        return self.env["afr.qualificacao.configurator.service"].create(vals)

    def _service_lines(self, order):
        return order.order_line.filtered("is_service_managed")

    def test_services_only_quote(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self._wiz_service(wiz, self.svc_seladora, qty=8)
        wiz.action_apply()
        lines = self._service_lines(order)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.service_id, self.svc_seladora)
        self.assertEqual(lines.product_uom_qty, 8)
        self.assertEqual(order.amount_untaxed, 960)
        self.assertFalse(
            order.order_line.filtered("is_qualificacao_managed"))

    def test_empty_wizard_blocks(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        with self.assertRaises(UserError):
            wiz.action_apply()

    def test_next_step_without_equipment(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        wiz.action_next_step()
        self.assertEqual(wiz.step, "servicos")
        wiz.action_next_step()
        self.assertEqual(wiz.step, "opcionais")
        wiz.action_next_step()
        self.assertEqual(wiz.step, "revisao")

    def test_onchange_fills_price_and_hours(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        line = self.env["afr.qualificacao.configurator.service"].new({
            "wizard_id": wiz.id,
            "service_id": self.svc_incubadora.id,
        })
        line._onchange_service_id()
        self.assertEqual(line.unit_price, 180)
        self.assertEqual(line.estimated_hours, 1.0)
        self.assertEqual(line.group_id, self.group_calib)
        line.qty = 3
        self.assertEqual(line.subtotal, 540)

    def test_duplicate_service_blocks(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self._wiz_service(wiz, self.svc_seladora, qty=1)
        self._wiz_service(wiz, self.svc_seladora, qty=2)
        with self.assertRaises(UserError):
            wiz.action_apply()

    def test_zero_qty_blocks(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self._wiz_service(wiz, self.svc_seladora, qty=0)
        with self.assertRaises(UserError):
            wiz.action_apply()

    def test_reapply_preserves_units(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self._wiz_service(wiz, self.svc_seladora, qty=3)
        wiz.action_apply()
        line = self._service_lines(order)
        self.env["afr.servico.unidade"].create({
            "line_id": line.id, "tag": "TAG-001",
        })
        unit = line.service_unit_ids

        wiz2 = self._open_wizard(order)
        self.assertEqual(len(wiz2.service_line_ids), 1)
        self.assertEqual(wiz2.service_line_ids.qty, 3)
        wiz2.action_apply()

        line2 = self._service_lines(order)
        self.assertEqual(line2.id, line.id)
        self.assertEqual(line2.service_unit_ids, unit)
        self.assertEqual(unit.tag, "TAG-001")

    def test_reapply_updates_qty_and_price(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self._wiz_service(wiz, self.svc_seladora, qty=3)
        wiz.action_apply()
        line = self._service_lines(order)

        wiz2 = self._open_wizard(order)
        wiz2.service_line_ids.write({"qty": 5, "unit_price": 100})
        wiz2.action_apply()

        line2 = self._service_lines(order)
        self.assertEqual(line2.id, line.id)
        self.assertEqual(line2.product_uom_qty, 5)
        self.assertEqual(line2.price_unit, 100)

    def test_reapply_removes_dropped_service(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self._wiz_service(wiz, self.svc_seladora, qty=3)
        self._wiz_service(wiz, self.svc_nr13, qty=1)
        wiz.action_apply()
        nr13_line = self._service_lines(order).filtered(
            lambda l: l.service_id == self.svc_nr13)

        wiz2 = self._open_wizard(order)
        wiz2.service_line_ids.filtered(
            lambda s: s.service_id == self.svc_nr13).unlink()
        wiz2.action_apply()

        lines = self._service_lines(order)
        self.assertEqual(lines.service_id, self.svc_seladora)
        self.assertFalse(nr13_line.exists())

    def test_remove_service_with_identified_unit_blocks(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self._wiz_service(wiz, self.svc_seladora, qty=3)
        wiz.action_apply()
        line = self._service_lines(order)
        self.env["afr.servico.unidade"].create({
            "line_id": line.id, "tag": "TAG-001",
        })

        wiz2 = self._open_wizard(order)
        wiz2.service_line_ids.unlink()
        # Sem equipamento nem serviço o apply bloqueia antes; mantém um
        # outro serviço para chegar ao unlink da linha identificada.
        self._wiz_service(wiz2, self.svc_nr13, qty=1)
        with self.assertRaises(UserError):
            wiz2.action_apply()
        self.assertTrue(line.exists())

    def test_service_lines_sequenced_after_qualification(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id, "do_qi": True,
        })]
        self._wiz_service(wiz, self.svc_nr13, qty=1)
        self._wiz_service(wiz, self.svc_incubadora, qty=2)
        self._wiz_service(wiz, self.svc_seladora, qty=3)
        wiz.action_apply()
        qualif_seq = max(
            order.order_line.filtered("is_qualificacao_managed")
            .mapped("sequence"))
        svc = self._service_lines(order)
        self.assertTrue(all(s.sequence > qualif_seq for s in svc))
        # grupo (calibração 10) antes de NR-13 (20); dentro do grupo, ordem
        # do catálogo (sequence, id).
        ordered = svc.sorted(key=lambda l: (l.sequence, l.id))
        self.assertEqual(ordered[-1].service_id, self.svc_nr13)

    def test_mixed_quote_keeps_qualif_behavior(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id, "do_qi": True,
        })]
        self._wiz_service(wiz, self.svc_seladora, qty=2)
        wiz.action_apply()

        qualif = order.order_line.filtered(
            lambda l: l.is_qualificacao_managed and not l.display_type)
        self.assertTrue(qualif)
        self.assertEqual(qualif.qualification_type, "installation")
        self.assertFalse(self._service_lines(order).equipment_id)
        self.assertFalse(self._service_lines(order).qualification_type)
        svc_line = self._service_lines(order)
        self.assertEqual(len(svc_line), 1)
        qualif_ids = qualif.ids

        wiz2 = self._open_wizard(order)
        wiz2.action_apply()
        svc_line2 = self._service_lines(order)
        self.assertEqual(svc_line2.id, svc_line.id)
        new_qualif = order.order_line.filtered(
            lambda l: l.is_qualificacao_managed and not l.display_type)
        self.assertTrue(new_qualif)
        self.assertFalse(set(new_qualif.ids) & set(qualif_ids))

    # -- Task 9: revisão e agrupamento ------------------------------------

    def test_review_services_only(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self._wiz_service(wiz, self.svc_seladora, qty=8)
        self._wiz_service(wiz, self.svc_nr13, qty=1)
        html = wiz.review_summary_html
        self.assertNotIn("Sem equipamentos no escopo", html)
        self.assertIn("Calibração de Instrumentos", html)
        self.assertIn("NR-13", html)
        self.assertEqual(wiz.service_subtotal, 960 + 2400)
        self.assertEqual(wiz.total_estimated, 960 + 2400)

    def test_review_empty_wizard_message(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self.assertIn("Sem equipamentos no escopo", wiz.review_summary_html)
        self.assertEqual(wiz.total_estimated, 0)

    def test_review_total_includes_equipment_and_services(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
        })
        self._wiz_service(wiz, self.svc_seladora, qty=2)
        equipment_total = sum(wiz.equipment_line_ids.mapped("subtotal"))
        self.assertGreater(equipment_total, 0)
        self.assertEqual(wiz.service_subtotal, 240)
        self.assertEqual(wiz.total_estimated, equipment_total + 240)
        self.assertIn("Calibração de Instrumentos", wiz.review_summary_html)

    def test_service_lines_ordered_by_group_then_service(self):
        order = self._make_order()
        wiz = self._open_wizard(order)
        # Criadas fora de ordem: NR-13 (grupo 20) antes da calibração (10).
        self._wiz_service(wiz, self.svc_nr13)
        self._wiz_service(wiz, self.svc_incubadora)
        self._wiz_service(wiz, self.svc_seladora)
        wiz.invalidate_recordset()
        ordered = wiz.service_line_ids.mapped("service_id")
        self.assertEqual(
            [s.group_id for s in ordered],
            [self.group_calib, self.group_calib, self.group_nr13],
        )
        self.assertEqual(ordered[2], self.svc_nr13)
        self.assertEqual(
            ordered[:2],
            (self.svc_seladora | self.svc_incubadora).sorted(
                key=lambda s: (s.sequence, s.name)),
        )
