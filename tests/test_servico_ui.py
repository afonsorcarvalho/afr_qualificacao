"""Telas da cotação multi-serviço: aviso de grupo sem capítulo, progresso
de identificação por linha, aba Unidades e totais de horas do configurador.
"""

from odoo.tests import Form, tagged

from .common_servico import AfrServicoTestCommon

WARNING_HEAD = "não aparecem detalhados na proposta"


@tagged("post_install", "-at_install")
class TestServicoUi(AfrServicoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tpl_multi = cls.env.ref("afr_qualificacao.proposal_template_multi")
        cls.tpl_labquali = cls.env.ref(
            "afr_qualificacao.proposal_template_labquali")
        cls.seeded_calib = cls.env.ref(
            "afr_qualificacao.servico_calib_seladora")
        cls.seeded_vazao = cls.env.ref(
            "afr_qualificacao.servico_vazao_exaustor")

    def _order(self, template, *services):
        order = self._make_order()
        order.proposal_template_id = template
        for service in services:
            self._add_service(order, service, 2)
        order._seed_proposal_blocks()
        return order

    def _wizard(self, order):
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": order.id,
        })
        wiz._load_from_existing_lines()
        return wiz

    # -- I3: aviso de grupo sem capítulo -------------------------------------

    def test_warning_on_template_without_chapter(self):
        order = self._order(self.tpl_labquali, self.seeded_calib)
        group = self.seeded_calib.group_id
        self.assertEqual(order._service_groups_without_chapter(), group)
        self.assertIn(WARNING_HEAD, order.service_chapter_warning)
        self.assertIn(group._chapter_title(), order.service_chapter_warning)

    def test_no_warning_on_multi_template(self):
        order = self._order(
            self.tpl_multi, self.seeded_calib, self.seeded_vazao)
        self.assertFalse(order._service_groups_without_chapter())
        self.assertFalse(order.service_chapter_warning)

    def test_warning_when_chapter_switched_off(self):
        order = self._order(self.tpl_multi, self.seeded_calib)
        self.assertFalse(order.service_chapter_warning)
        group = self.seeded_calib.group_id
        order.proposal_block_ids.filtered(
            lambda b: b.block_kind == "service_group"
            and b.service_group_id == group
        ).included = False
        self.assertIn(group._chapter_title(), order.service_chapter_warning)

    def test_warning_names_two_groups(self):
        order = self._order(
            self.tpl_labquali, self.svc_seladora, self.svc_nr13)
        warning = order.service_chapter_warning
        self.assertIn("Calibração de Instrumentos e NR-13", warning)

    def test_no_warning_without_services(self):
        order = self._order(self.tpl_labquali)
        self.assertFalse(order.service_chapter_warning)

    def test_wizard_review_warns(self):
        order = self._order(self.tpl_labquali, self.seeded_calib)
        wiz = self._wizard(order)
        self.assertIn(WARNING_HEAD, wiz.review_summary_html)

        order2 = self._order(self.tpl_multi, self.seeded_calib)
        wiz2 = self._wizard(order2)
        self.assertNotIn(WARNING_HEAD, wiz2.review_summary_html)

    def test_wizard_review_warns_on_template_choice(self):
        """Cotação sem blocos: compara com o template escolhido no wizard."""
        order = self._make_order()
        order.proposal_template_id = self.tpl_multi
        wiz = self._wizard(order)
        self.env["afr.qualificacao.configurator.service"].create({
            "wizard_id": wiz.id, "service_id": self.seeded_calib.id,
            "qty": 2, "unit_price": 10.0,
        })
        self.assertNotIn(WARNING_HEAD, wiz.review_summary_html)
        wiz.proposal_template_id = self.tpl_labquali
        self.assertIn(WARNING_HEAD, wiz.review_summary_html)

    # -- I6: N/M unidades por linha ----------------------------------------

    def test_unit_progress_per_line(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 8)
        self.assertEqual(line.service_unit_progress, "0/8")
        self.env["afr.servico.unidade"].create({
            "line_id": line.id, "tag": "TAG-001",
        })
        self.assertEqual(line.service_unit_progress, "1/8")
        other = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.svc_nr13.product_id.id,
            "product_uom_qty": 1,
        })
        self.assertFalse(other.service_unit_progress)

    # -- aba Unidades: item em branco e nome curto da linha ----------------

    def test_item_label_blank_until_numbered(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        unit = self.env["afr.servico.unidade"].create({"line_id": line.id})
        self.assertEqual(unit.item_number, 0)
        self.assertEqual(unit.item_label, "")
        order.action_confirm()
        self.assertEqual(unit.item_label, str(unit.item_number))
        self.assertTrue(unit.item_number)

    def test_short_line_name_in_units_context(self):
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 2)
        default = line.name_get()[0][1]
        self.assertIn(order.name, default)
        short = line.with_context(
            afr_service_line_short_name=True).name_get()[0][1]
        self.assertEqual(short, self.svc_seladora.name)

    def test_unit_category_follows_service(self):
        category = self.env["engc.equipment.category"].create({
            "name": "Categoria Teste Seladora",
        })
        self.svc_seladora.equipment_category_id = category
        order = self._make_order()
        line = self._add_service(order, self.svc_seladora, 1)
        unit = self.env["afr.servico.unidade"].create({"line_id": line.id})
        self.assertEqual(unit.service_equipment_category_id, category)

    # -- configurador: horas e dias incluem os serviços ----------------------

    def test_wizard_hours_include_services(self):
        order = self._make_order()
        wiz = self._wizard(order)
        self.env["afr.qualificacao.configurator.service"].create({
            "wizard_id": wiz.id, "service_id": self.svc_nr13.id,
            "qty": 2, "unit_price": 10.0, "estimated_hours": 8.0,
        })
        self.assertEqual(wiz.estimated_hours_total, 16.0)
        self.assertEqual(wiz.estimated_days_total, 2.0)

    def test_wizard_hours_mixed(self):
        order = self._make_order()
        wiz = self._wizard(order)
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip1.id,
            "do_qi": True,
        })
        equip_hours = sum(
            wiz.equipment_line_ids.mapped("estimated_hours_total"))
        equip_days = sum(
            wiz.equipment_line_ids.mapped("estimated_days_total"))
        self.env["afr.qualificacao.configurator.service"].create({
            "wizard_id": wiz.id, "service_id": self.svc_seladora.id,
            "qty": 8, "unit_price": 10.0, "estimated_hours": 0.5,
        })
        self.assertAlmostEqual(wiz.estimated_hours_total, equip_hours + 4.0)
        self.assertAlmostEqual(wiz.estimated_days_total, equip_days + 0.5)

    # -- form ----------------------------------------------------------------

    def test_form_loads_with_new_fields(self):
        order = self._order(self.tpl_labquali, self.svc_seladora)
        with Form(order) as form:
            self.assertIn(WARNING_HEAD, form.service_chapter_warning)
            with form.regular_line_ids.edit(0) as line:
                self.assertEqual(line.service_unit_progress, "0/2")
