# -*- coding: utf-8 -*-
from odoo.tests.common import Form, tagged
from odoo.tools.misc import formatLang
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestCotacaoFormRefactor(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _svc(self, price=100.0):
        return self.env["product.product"].create({
            "name": "Svc", "type": "service", "sale_ok": True,
            "list_price": price,
        })

    def _line(self, so, optional=False, price=100.0, qty=1.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self._svc(price).id,
            "name": "L",
            "is_proposal_optional": optional,
            "optional_qty": qty if optional else 0.0,
            "product_uom_qty": qty,
            "price_unit": price,
        })

    def test_regular_line_ids_excludes_optional(self):
        so = self._so()
        reg = self._line(so, optional=False)
        opt = self._line(so, optional=True)
        self.assertIn(reg, so.regular_line_ids)
        self.assertNotIn(opt, so.regular_line_ids)

    def test_optional_line_ids_only_optional(self):
        so = self._so()
        reg = self._line(so, optional=False)
        opt = self._line(so, optional=True)
        self.assertIn(opt, so.optional_line_ids)
        self.assertNotIn(reg, so.optional_line_ids)

    def test_optional_context_default_flag(self):
        # Simula o default_get usado pela aba Opcionais (context na view).
        Line = self.env["sale.order.line"].with_context(
            default_is_proposal_optional=True)
        vals = Line.default_get(["is_proposal_optional"])
        self.assertTrue(vals.get("is_proposal_optional"))

    def test_amount_total_with_split_lines(self):
        so = self._so()
        self._line(so, optional=False, price=100.0, qty=2.0)   # 200
        self._line(so, optional=True, price=50.0, qty=1.0)     # opcional
        # order_line (padrão) enxerga ambos os registros.
        self.assertEqual(len(so.order_line), 2)
        self.assertEqual(
            len(so.regular_line_ids) + len(so.optional_line_ids),
            len(so.order_line),
        )

    def test_qualif_tecnico_html_empty_without_qualif(self):
        so = self._so()
        self._line(so, optional=False)  # linha comum, sem equipment
        self.assertFalse(so.qualif_tecnico_html)

    def test_qualif_tecnico_html_has_cards_with_qualif(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo CMax",
            "is_qualificacao_managed": True,
            "qualification_type": "performance",
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 1,
            "price_unit": 700.0,
        })
        html = so.qualif_tecnico_html
        self.assertTrue(html)
        self.assertIn(self.equip1.display_name, html)
        self.assertIn("<div", html)
        self.assertIn("Ciclo CMax", html)

    def _cycle_line(self, so, name, qtype, cycle, qty, hours,
                    temp="80ºC", dur="10 min", load="com_carga"):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": cycle.product_id.id,
            "name": name,
            "is_qualificacao_managed": True,
            "qualification_type": qtype,
            "equipment_id": self.equip1.id,
            "cycle_type_id": cycle.id,
            "qualif_cycle_qty": qty,
            "estimated_hours": hours,
            "temperature": temp,
            "duration": dur,
            "load_type": load,
            "product_uom_qty": qty * hours,
            "price_unit": 100.0,
        })

    def test_tecnico_html_has_scope_and_cycle_table(self):
        so = self._so()
        self._cycle_line(so, "Carga Mista 134", "performance",
                         self.cycle_cmax, qty=3, hours=2.0)
        html = so.qualif_tecnico_html
        self.assertIn("ESCOPO", html)
        self.assertIn("TABELA DE CICLOS", html)
        self.assertIn("Temperatura", html)
        self.assertIn("Carga", html)
        self.assertIn("80ºC", html)
        self.assertIn("TEMPO DE EXECUÇÃO", html)
        self.assertIn("TEMPO TOTAL DE EXECUÇÃO DA PROPOSTA", html)

    def test_tecnico_html_empty_without_qualif_v2(self):
        so = self._so()
        self._line(so, optional=False)
        self.assertFalse(so.qualif_tecnico_html)

    def _equip_line(self, so, price=700.0, qty=1.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo CMax",
            "is_qualificacao_managed": True,
            "qualification_type": "performance",
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": int(qty),
            "price_unit": price,
            "product_uom_qty": qty,
        })

    def test_grand_total_present_equip_only(self):
        so = self._so()
        self._equip_line(so, price=700.0, qty=1.0)
        equip_total = sum(s["subtotal"] for s in so._qualif_equipment_summary())
        expected = formatLang(self.env, equip_total, currency_obj=so.currency_id)
        html = so.qualif_subtotals_html
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)
        self.assertIn(expected, html)
        # Regressão: anexar o banner (Markup) NÃO pode escapar as tabelas
        # de equipamento/opcionais que vêm antes (str+Markup → __radd__).
        self.assertIn("<table", html)
        self.assertNotIn("&lt;table", html)

    def test_grand_total_includes_accepted_optional(self):
        so = self._so()
        self._equip_line(so, price=700.0, qty=1.0)
        self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc(50.0).id,
            "name": "Opc Aceito", "is_proposal_optional": True,
            "optional_accepted": True, "optional_qty": 1.0, "price_unit": 50.0,
        })
        equip_total = sum(s["subtotal"] for s in so._qualif_equipment_summary())
        opt_total = sum(so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.optional_accepted
        ).mapped("price_subtotal"))
        expected = formatLang(self.env, equip_total + opt_total,
                              currency_obj=so.currency_id)
        self.assertIn(expected, so.qualif_subtotals_html)

    def test_optional_accept_persists_qty_and_updates_total_live(self):
        """Aceitar opcional na aba Opcionais persiste product_uom_qty
        (subtotal != 0) e recomputa o resumo financeiro AO VIVO no form.

        Regressão de dois bugs: (1) product_uom_qty setado por onchange não
        persistia por estar ausente da tree → opcional aceito salvava com
        subtotal 0; (2) qualif_subtotals_html dependia só de order_line e não
        recomputava ao togglar via optional_line_ids (datapoint OWL distinto).
        """
        so = self._so()
        self._equip_line(so, price=700.0, qty=1.0)  # managed → has_qualif_lines
        opt = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc(150.0).id,
            "name": "Opc", "is_proposal_optional": True,
            "optional_accepted": False, "optional_qty": 1.0,
            "price_unit": 150.0, "product_uom_qty": 0.0,
        })
        view = "afr_qualificacao.view_sale_order_form_inherit_qualificacao"
        f = Form(so, view=view)
        self.assertNotIn("Subtotais de Opcionais", f.qualif_subtotals_html or "")
        with f.optional_line_ids.edit(0) as line:
            line.optional_accepted = True
        # Reatividade live: a seção de opcionais aceitos aparece sem salvar.
        self.assertIn("Subtotais de Opcionais", f.qualif_subtotals_html or "")
        f.save()
        # Persistência: qty e subtotal corretos (não 0).
        self.assertEqual(opt.product_uom_qty, 1.0)
        self.assertEqual(opt.price_subtotal, 150.0)
