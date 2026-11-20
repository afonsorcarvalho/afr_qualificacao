"""Testes da Task 5 — blocos condicionais da proposta (applies_when).

Um mesmo template tem um capítulo por família de serviço; o documento se
adapta ao que foi cotado. Cobre visibilidade, herança do pai, numeração,
seed, constraint e o PDF.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common_servico import AfrServicoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestProposalMultiConditions(AfrServicoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Section = cls.env["afr.proposal.section"]
        Line = cls.env["afr.proposal.template.line"]

        def _section(code, title):
            return Section.create({
                "code": code,
                "name": title,
                "category": "objetivo",
                "body": "<p>Corpo %s</p>" % title,
            })

        cls.sec = {
            key: _section("TCOND-%s" % key, "Titulo%s" % key)
            for key in ("A", "B", "B1", "C", "D")
        }
        cls.tpl = cls.env["afr.proposal.template"].create({
            "name": "Tpl Condicional Teste",
        })

        def _line(key, seq, **extra):
            vals = {
                "template_id": cls.tpl.id,
                "sequence": seq,
                "block_kind": "static",
                "section_id": cls.sec[key].id,
            }
            vals.update(extra)
            return Line.create(vals)

        cls.line_a = _line("A", 10)
        cls.line_b = _line("B", 20, applies_when="qualification")
        cls.line_b1 = _line("B1", 30, parent_id=cls.line_b.id)
        cls.line_c = _line(
            "C", 40, applies_when="service_group",
            service_group_id=cls.group_calib.id,
        )
        cls.line_d = _line(
            "D", 50, applies_when="service_group",
            service_group_id=cls.group_nr13.id,
        )
        cls.report = cls.env.ref("sale.action_report_saleorder")

    # -- helpers -----------------------------------------------------------

    def _services_order(self):
        order = self._make_order()
        self._add_service(order, self.svc_seladora, 2)
        order.proposal_template_id = self.tpl
        order._seed_proposal_blocks()
        return order

    def _qualif_order(self):
        order = self._make_order()
        order.proposal_template_id = self.tpl
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": order.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 1}),
            ],
        })
        wiz.action_apply()
        return order

    def _block(self, order, key):
        return order.proposal_block_ids.filtered(
            lambda b: b.section_id == self.sec[key]
        )

    def _titles(self, order):
        return order._proposal_visible_blocks().mapped("title")

    def _render(self, order):
        html, _ctype = self.report._render_qweb_html(
            self.report.report_name, order.ids
        )
        return html.decode() if isinstance(html, bytes) else html

    # -- testes ------------------------------------------------------------

    def test_services_only_hides_qualification(self):
        order = self._services_order()
        self.assertEqual(
            self._titles(order), ["TituloA", "TituloC"],
        )

    def test_child_follows_parent(self):
        order = self._services_order()
        b1 = self._block(order, "B1")
        self.assertEqual(b1.applies_when, "always")
        self.assertTrue(b1.parent_id)
        self.assertFalse(b1.parent_id._is_applicable())
        self.assertFalse(b1._is_applicable())
        self.assertNotIn(b1, order._proposal_visible_blocks())

    def test_numbering_skips_hidden(self):
        order = self._services_order()
        numbers = order._proposal_block_numbering()
        self.assertEqual(numbers[self._block(order, "A").id], "1")
        self.assertEqual(numbers[self._block(order, "C").id], "2")
        self.assertNotIn(self._block(order, "B").id, numbers)

    def test_qualification_only(self):
        order = self._qualif_order()
        self.assertEqual(
            self._titles(order), ["TituloA", "TituloB", "TituloB1"],
        )

    def test_included_false_still_hidden(self):
        order = self._services_order()
        self._block(order, "C").included = False
        self.assertEqual(self._titles(order), ["TituloA"])

    def test_service_group_requires_group(self):
        with self.assertRaises(ValidationError):
            self.env["afr.proposal.template.line"].create({
                "template_id": self.tpl.id,
                "block_kind": "static",
                "section_id": self.sec["A"].id,
                "applies_when": "service_group",
            })
        order = self._services_order()
        with self.assertRaises(ValidationError):
            self._block(order, "A").applies_when = "service_group"

    def test_seed_copies_condition(self):
        order = self._services_order()
        block_c = self._block(order, "C")
        self.assertEqual(block_c.applies_when, "service_group")
        self.assertEqual(block_c.service_group_id, self.group_calib)
        self.assertEqual(self._block(order, "B").applies_when, "qualification")
        self.assertFalse(self._block(order, "B").service_group_id)
        self.assertEqual(self._block(order, "A").applies_when, "always")

    def test_is_applicable_computed_field(self):
        order = self._services_order()
        self.assertTrue(self._block(order, "C").is_applicable)
        self.assertFalse(self._block(order, "D").is_applicable)
        self.assertFalse(self._block(order, "B1").is_applicable)

    def test_pdf_omits_hidden_block(self):
        order = self._services_order()
        html = self._render(order)
        self.assertIn("TituloC", html)
        self.assertNotIn("TituloB", html)
        self.assertNotIn("TituloD", html)

    # -- Task 9: motivo e numeração --------------------------------------

    def test_hidden_reason(self):
        order = self._services_order()
        self.assertFalse(self._block(order, "A").hidden_reason)
        self.assertFalse(self._block(order, "C").hidden_reason)
        self.assertEqual(
            self._block(order, "B").hidden_reason,
            "Sem qualificação na cotação",
        )
        self.assertEqual(
            self._block(order, "D").hidden_reason,
            "Sem serviço do grupo %s" % self.group_nr13.name,
        )
        self.assertEqual(
            self._block(order, "B1").hidden_reason, "Bloco pai oculto")

    def test_hidden_reason_clears_when_condition_holds(self):
        order = self._qualif_order()
        for key in ("A", "B", "B1"):
            self.assertFalse(self._block(order, key).hidden_reason)
        self.assertEqual(
            self._block(order, "C").hidden_reason,
            "Sem serviço do grupo %s" % self.group_calib.name,
        )

    def test_display_number_follows_condition(self):
        order = self._services_order()
        block_c = self._block(order, "C")
        self.assertEqual(block_c.display_number, "2")
        # Entra qualificação: B (2) e B1 (2.1) passam a existir e C vira 3.
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": order.id,
        })
        wiz._load_from_existing_lines()
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 1}),
            ],
        })
        wiz.action_apply()
        self.assertTrue(order.has_qualif_lines)
        self.assertEqual(block_c.display_number, "3")
