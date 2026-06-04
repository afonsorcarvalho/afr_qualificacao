# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProcessTypeLabel(TransactionCase):

    def _cat(self, process_type=None):
        vals = {"name": "Cat Teste"}
        if process_type:
            vals["process_type"] = process_type
        return self.env["engc.equipment.category"].create(vals)

    def test_default_esterilizacao(self):
        cat = self._cat()
        self.assertEqual(cat.process_type, "esterilizacao")
        self.assertEqual(cat._qualif_time_label(), "Tempo de Esterilização")

    def test_lavagem(self):
        cat = self._cat("lavagem")
        self.assertEqual(cat._qualif_time_label(), "Tempo de Lavagem")

    def test_desinfeccao(self):
        cat = self._cat("desinfeccao")
        self.assertEqual(cat._qualif_time_label(), "Tempo de Desinfecção")

    def test_monitoramento(self):
        cat = self._cat("monitoramento")
        self.assertEqual(cat._qualif_time_label(), "Tempo de Ciclo")


@tagged("post_install", "-at_install")
class TestCycleSpecsLabel(TransactionCase):

    def test_cycle_specs_time_label(self):
        svc = self.env["product.product"].create(
            {"name": "Svc Ciclo", "type": "service", "sale_ok": True})
        cat = self.env["engc.equipment.category"].create(
            {"name": "Lavadora X", "process_type": "lavagem"})
        marca = self.env["engc.equipment.marca"].create({"name": "M-Lav"})
        equip = self.env["engc.equipment"].create({
            "category_id": cat.id, "marca_id": marca.id,
            "company_id": self.env.company.id, "state": "in_use",
            "model": "M1", "serial_number": "SN-LAV-1",
        })
        cycle = self.env["afr.qualificacao.cycle.type"].create({
            "name": "Ciclo Lav", "equipment_category_id": cat.id,
            "duration": "15 min", "product_id": svc.id,
        })
        so = self.env["sale.order"].create(
            {"partner_id": self.env.user.partner_id.id})
        self.env["sale.order.line"].create({
            "order_id": so.id, "name": "Ciclo Lav",
            "product_id": svc.id,
            "is_qualificacao_managed": True, "equipment_id": equip.id,
            "cycle_type_id": cycle.id, "qualif_cycle_qty": 3,
            "qualification_type": "performance",
        })
        specs = so._qualif_cycle_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["time_label"], "Tempo de Lavagem")
