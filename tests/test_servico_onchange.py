"""Linhas de serviço em contexto de onchange (registros virtuais, `NewId`).

No form da cotação, o onchange trabalha com cópias virtuais das linhas e dos
blocos: `line.id` é um `NewId`, que não se compara com `<`. Toda chave de
ordenação que desempata por id precisa usar `_origin.id` (ou 0).
"""

from odoo.tests import Form, tagged

from .common_servico import AfrServicoTestCommon


@tagged("post_install", "-at_install")
class TestServicoOnchange(AfrServicoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Mesmo grupo e mesma `sequence` (default 10): só o id desempata.
        assert cls.svc_seladora.group_id == cls.svc_incubadora.group_id
        assert cls.svc_seladora.sequence == cls.svc_incubadora.sequence
        cls.tpl_multi = cls.env.ref("afr_qualificacao.proposal_template_multi")

    def _tied_order(self):
        order = self._make_order()
        order.proposal_template_id = self.tpl_multi
        order._seed_proposal_blocks()
        # Bloco do grupo de teste, para `is_applicable`/`hidden_reason`
        # chamarem `_service_groups()`.
        self.env["afr.proposal.block"].create({
            "sale_order_id": order.id,
            "sequence": 5,
            "block_kind": "service_group",
            "applies_when": "service_group",
            "service_group_id": self.group_calib.id,
            "title": "Calibração (teste)",
        })
        self._add_service(order, self.svc_seladora, 2)
        self._add_service(order, self.svc_incubadora, 3)
        return order

    def test_virtual_lines_sort_without_type_error(self):
        """`_service_lines()` sobre linhas virtuais (sem origem) não quebra."""
        order = self.env["sale.order"].new({
            "partner_id": self.partner.id,
            "order_line": [
                (0, 0, self.env["sale.order.line"]._service_line_vals(
                    self.svc_seladora, 2)),
                (0, 0, self.env["sale.order.line"]._service_line_vals(
                    self.svc_incubadora, 3)),
            ],
        })
        lines = order._service_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(order._service_groups(), self.group_calib)
        self.assertEqual(
            order.service_units_summary, "0 de 5 unidades identificadas")

    def test_onchange_copy_of_saved_order(self):
        """Cópia virtual (`new(origin=...)`) da cotação gravada."""
        order = self._tied_order()
        virtual = order.new(origin=order)
        self.assertEqual(
            virtual._service_lines().mapped("service_id"),
            order._service_lines().mapped("service_id"))
        self.assertEqual(
            virtual.service_units_summary, "0 de 5 unidades identificadas")

    def test_form_edit_quantity(self):
        """Editar a quantidade pelo form roda o onchange da cotação, que lê
        os campos dos blocos (`is_applicable`, `hidden_reason`,
        `display_number`) sobre linhas virtuais — sem `TypeError`."""
        order = self._tied_order()
        with Form(order) as form:
            with form.regular_line_ids.edit(0) as line:
                line.product_uom_qty = 4
        order.invalidate_recordset()
        self.assertEqual(
            order.service_units_summary, "0 de 7 unidades identificadas")
        block = order.proposal_block_ids.filtered(
            lambda b: b.title == "Calibração (teste)")
        self.assertTrue(block.is_applicable)
        self.assertFalse(block.hidden_reason)
        self.assertTrue(block.display_number)
