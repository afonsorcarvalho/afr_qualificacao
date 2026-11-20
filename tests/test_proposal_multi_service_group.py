"""Testes da Task 7 — bloco `service_group`, normas, horas e títulos.

O capítulo de uma família de serviço (tabela dos serviços cotados com
subtotal e relação das unidades identificadas) tem três renderizações —
PDF, portal e snapshot HTML — alimentadas por
`sale.order._service_group_table(group)`. Cobre também normas, horas,
cronograma e a expressão de títulos usada nos textos do template.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common_servico import AfrServicoTestCommon

CHAPTER_CALIB = "Calibração de Instrumentos"


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestProposalMultiServiceGroup(AfrServicoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("sale.action_report_saleorder")
        cls.standard = cls.env["afr.qualificacao.standard"].create({
            "code": "TEST-STD-7", "name": "Norma de Teste 7",
        })

    # -- helpers -----------------------------------------------------------

    def _template(self, group, **line_extra):
        tpl = self.env["afr.proposal.template"].create({
            "name": "Tpl Grupo Teste",
        })
        vals = {
            "template_id": tpl.id,
            "sequence": 10,
            "block_kind": "service_group",
            "service_group_id": group.id,
            "applies_when": "service_group",
        }
        vals.update(line_extra)
        self.env["afr.proposal.template.line"].create(vals)
        return tpl

    def _calib_order(self, qty=8, price=None):
        order = self._make_order()
        self._add_service(order, self.svc_seladora, qty, unit_price=price)
        return order

    def _mixed_order(self):
        order = self._make_order()
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": order.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
        })
        wiz.action_apply()
        self._add_service(order, self.svc_seladora, 2)
        self._add_service(order, self.svc_nr13, 1)
        return order

    def _block(self, order, group):
        return order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "service_group"
            and b.service_group_id == group
        )

    def _render(self, order):
        html, _ctype = self.report._render_qweb_html(
            self.report.report_name, order.ids
        )
        return html.decode() if isinstance(html, bytes) else html

    # -- tabela ------------------------------------------------------------

    def test_table_rows_and_subtotal(self):
        order = self._make_order()
        self._add_service(order, self.svc_seladora, 8)
        self._add_service(order, self.svc_incubadora, 3)
        table = order._service_group_table(self.group_calib)
        self.assertEqual(table["group"], self.group_calib)
        self.assertEqual(len(table["rows"]), 2)
        self.assertEqual([r["item"] for r in table["rows"]], [1, 2])
        self.assertEqual(table["subtotal"], 1500.0)
        self.assertEqual(table["hours"], 7.0)
        self.assertTrue(table["days_label"])
        seladora = table["rows"][0]
        self.assertIn("QPC-008", seladora["procedure"])
        self.assertEqual(seladora["qty"], 8)
        self.assertEqual(seladora["price_unit"], 120.0)
        self.assertEqual(seladora["subtotal"], 960.0)
        self.assertEqual(table["rows"][1]["procedure"], "")

    def test_units_only_identified(self):
        order = self._calib_order(qty=3)
        order._service_sync_units(force=True)
        line = order._service_lines()[0]
        self.assertEqual(len(line.service_unit_ids), 3)
        self.assertEqual(order._service_group_table(self.group_calib)["units"],
                         self.env["afr.servico.unidade"])
        line.service_unit_ids[0].tag = "TAG-001"
        table = order._service_group_table(self.group_calib)
        self.assertEqual(len(table["units"]), 1)
        self.assertEqual(table["units"].tag, "TAG-001")

    # -- renderizações -----------------------------------------------------

    def test_render_pdf(self):
        order = self._calib_order(qty=3, price=111.0)
        order.proposal_template_id = self._template(self.group_calib)
        order._seed_proposal_blocks()
        self.assertTrue(self._block(order, self.group_calib))
        html = self._render(order)
        self.assertIn(CHAPTER_CALIB, html)
        self.assertIn("Test Calibração Seladora", html)
        self.assertIn("QPC-008", html)
        self.assertRegex(html, r"333[.,]00")
        self.assertIn("Subtotal " + CHAPTER_CALIB, html)
        self.assertIn("Valor Unitário", html)
        self.assertNotIn("Relação de", html)

        order._service_sync_units(force=True)
        order._service_lines()[0].service_unit_ids[0].tag = "TAG-001"
        html = self._render(order)
        self.assertIn("Relação de instrumentos", html)
        self.assertIn("TAG-001", html)

    def test_render_absent_group_empty(self):
        order = self._calib_order()
        order.proposal_template_id = self._template(
            self.group_nr13, applies_when="always",
        )
        order._seed_proposal_blocks()
        block = self._block(order, self.group_nr13)
        self.assertTrue(block)
        self.assertIn(block, order._proposal_visible_blocks())
        html = self._render(order)
        # O capítulo vazio não imprime tabela nem subtotal (o título ainda
        # consta no índice, que lista todo bloco visível).
        self.assertNotIn("Subtotal NR-13", html)
        self.assertNotIn("Valor Unitário", html)

    def test_render_portal(self):
        order = self._calib_order(qty=3, price=111.0)
        order.proposal_template_id = self._template(self.group_calib)
        order._seed_proposal_blocks()
        order._service_sync_units(force=True)
        order._service_lines()[0].service_unit_ids[0].tag = "TAG-001"
        html = str(self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": order},
        ))
        self.assertIn("Test Calibração Seladora", html)
        self.assertRegex(html, r"333[.,]00")
        self.assertIn("TAG-001", html)

    def test_snapshot_html(self):
        order = self._calib_order(qty=3, price=111.0)
        order.proposal_template_id = self._template(self.group_calib)
        order._seed_proposal_blocks()
        block = self._block(order, self.group_calib)
        html = str(block._snapshot_html())
        self.assertIn("Test Calibração Seladora", html)
        self.assertRegex(html, r"333[.,]00")
        self.assertIn("QPC-008", html)

    # -- constraint --------------------------------------------------------

    def test_service_group_kind_requires_group(self):
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Sem Grupo"})
        with self.assertRaises(ValidationError):
            self.env["afr.proposal.template.line"].create({
                "template_id": tpl.id, "block_kind": "service_group",
            })
        order = self._calib_order()
        with self.assertRaises(ValidationError):
            self.env["afr.proposal.block"].create({
                "sale_order_id": order.id, "block_kind": "service_group",
            })

    # -- normas, horas, cronograma, títulos --------------------------------

    def test_standards_include_services(self):
        self.svc_seladora.standard_ids = self.standard
        order = self._calib_order()
        self.assertIn(self.standard, order.qualif_standard_ids)

    def test_estimated_hours_include_services(self):
        order = self._mixed_order()
        qualif_hours = sum(
            order._qualif_estimated_hours(eq)
            for eq in order.order_line.mapped("equipment_id")
        )
        service_hours = 2 * 0.5 + 8.0
        self.assertEqual(
            order._qualif_estimated_hours(), qualif_hours + service_hours)
        # Por equipamento, não soma serviço.
        order2 = self._make_order()
        self._add_service(order2, self.svc_seladora, 8)
        self._add_service(order2, self.svc_incubadora, 3)
        self.assertEqual(order2._qualif_estimated_hours(), 7.0)
        self.assertEqual(
            order2._qualif_estimated_hours(self.equip1), 0.0)

    def test_schedule_rows_include_service_groups(self):
        order = self._mixed_order()
        rows = order._qualif_schedule_rows()
        labels = [r.get("label") for r in rows]
        self.assertEqual(labels[-2:], [CHAPTER_CALIB, "NR-13"])
        calib = rows[-2]
        self.assertFalse(calib["equipment"])
        self.assertEqual(calib["hours"], 1.0)
        self.assertEqual(calib["work_hours_per_day"], 8.0)
        self.assertEqual(calib["days"], 1.0 / 8.0)

    def test_render_schedule_block_with_service_rows(self):
        order = self._make_order()
        self._add_service(order, self.svc_seladora, 8)
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Cron"})
        self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id, "sequence": 10, "block_kind": "schedule",
        })
        order.proposal_template_id = tpl
        order._seed_proposal_blocks()
        html = self._render(order)
        self.assertIn("Dias úteis", html)
        self.assertIn(CHAPTER_CALIB, html)
        block = order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "schedule")
        self.assertIn(CHAPTER_CALIB, str(block._snapshot_html()))

    def test_service_titles(self):
        self.assertEqual(
            self._mixed_order()._proposal_service_titles(),
            "Qualificação Térmica, Calibração de Instrumentos e NR-13",
        )
        self.assertEqual(
            self._calib_order()._proposal_service_titles(),
            CHAPTER_CALIB,
        )
        self.assertEqual(self._make_order()._proposal_service_titles(), "")

    def test_title_expression_renders(self):
        order = self._calib_order()
        html = order._render_proposal_block_body(
            "<p>{{ doc._proposal_service_titles() }}</p>")
        self.assertIn(CHAPTER_CALIB, html)
