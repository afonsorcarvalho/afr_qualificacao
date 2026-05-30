"""16.0.4.20.0 — separação billing(horas) × contagem(ciclos).

A linha SO passa a faturar em HORAS (product_uom_qty = nº ciclos ×
horas/ciclo), enquanto o nº de ciclos vive em qualif_cycle_qty (dirige a
explosão em afr.qualificacao.cycle/malha = coletas + exibição na proposta).
"""

from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestHoursVsCycles(AfrQualificacaoTestCommon):

    def _apply(self, qd_qty, calib_qty):
        # horas/ciclo ≠ 1 para provar que qty=horas e não nº de ciclos
        self.cycle_cmax.estimated_hours = 2.0
        self.malha_temp.estimated_hours = 4.0
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": qd_qty})],
            "calib_line_ids": [(0, 0, {"malha_type_id": self.malha_temp.id, "qty": calib_qty})],
        })]
        wiz.action_apply()
        return so

    def test_qty_is_hours_cycle_qty_is_cycles(self):
        so = self._apply(qd_qty=3, calib_qty=2)
        qd_line = so.order_line.filtered(lambda l: l.qualification_type == "performance")
        calib_line = so.order_line.filtered(lambda l: l.qualification_type == "calibration")
        # product_uom_qty = HORAS (ciclos × horas/ciclo)
        self.assertEqual(qd_line.product_uom_qty, 6.0)   # 3 × 2h
        self.assertEqual(calib_line.product_uom_qty, 8.0)  # 2 × 4h
        # qualif_cycle_qty = nº de ciclos/malhas
        self.assertEqual(qd_line.qualif_cycle_qty, 3)
        self.assertEqual(calib_line.qualif_cycle_qty, 2)

    def test_description_shows_cycle_count(self):
        so = self._apply(qd_qty=3, calib_qty=2)
        qd_line = so.order_line.filtered(lambda l: l.qualification_type == "performance")
        self.assertIn("3 ciclo(s)", qd_line.name)

    def test_explosion_uses_cycle_qty_not_hours(self):
        so = self._apply(qd_qty=3, calib_qty=2)
        so.action_confirm()
        qd = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "performance")
        calib = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "calibration")
        # explode por nº de ciclos (3), NÃO por horas (6)
        self.assertEqual(len(qd.cycle_ids), 3)
        self.assertEqual(len(calib.malha_ids), 2)

    def test_estimated_hours_aggregate_uses_cycle_qty(self):
        so = self._apply(qd_qty=3, calib_qty=2)
        # 3×2h (QD) + 2×4h (calib) = 14h
        self.assertEqual(so._qualif_estimated_hours(self.equip1), 14.0)

    def test_reload_preserves_description_and_template(self):
        """Reabrir configurador restaura description, unit_price e config_template_id."""
        # Criar pacote de teste
        tpl = self.env["afr.qualificacao.config.template"].create({
            "name": "Pacote Teste Reload",
            "equipment_category_id": self.category.id,
            "do_qi": True,
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id,
                "qty": 2,
                "description": "Ciclo Custom Editado",
            })],
        })
        self.cycle_cmax.estimated_hours = 2.0

        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz1 = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz1.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "config_template_id": tpl.id,
            "qd_line_ids": [(0, 0, {
                "cycle_type_id": self.cycle_cmax.id,
                "qty": 2,
                "description": "Ciclo Custom Editado",
                "unit_price": 150.0,
                "estimated_hours": 2.0,
            })],
        })]
        wiz1.action_apply()

        # Reabrir → novo wizard carrega de linhas existentes
        wiz2 = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz2._load_from_existing_lines()

        eq = wiz2.equipment_line_ids
        self.assertEqual(len(eq), 1)
        qd_line = eq.qd_line_ids
        self.assertEqual(len(qd_line), 1)
        # description restaurada (sem sufixo "— N ciclo(s)")
        self.assertEqual(qd_line.description, "Ciclo Custom Editado")
        # unit_price restaurado
        self.assertEqual(qd_line.unit_price, 150.0)
        # config_template_id restaurado
        self.assertEqual(eq.config_template_id, tpl)

    def test_proposal_summary_shows_cycle_count(self):
        so = self._apply(qd_qty=3, calib_qty=2)
        summary = so._qualif_equipment_summary()
        cycle_items = [
            item
            for equip in summary
            for t in equip["types"]
            for item in t["items"]
            if item.get("subtype") == "cycle_type"
        ]
        self.assertTrue(cycle_items)
        # proposta mostra nº de ciclos (3), não horas (6)
        self.assertEqual(cycle_items[0]["qty"], 3)
