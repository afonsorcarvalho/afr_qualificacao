"""Setup compartilhado dos testes do fluxo quote-first."""

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class AfrQualificacaoTestCommon(TransactionCase):
    """Fixtures: cliente + 2 equips + 2 cycle_types + 4 malha_types + 3 type.configs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Categoria de equipamento
        cls.category = cls.env["engc.equipment.category"].create({
            "name": "Test-Autoclave",
        })

        # Helpers básicos engc_os
        cls.means = cls.env["engc.equipment.means.of.aquisition"].search([], limit=1)
        if not cls.means:
            cls.means = cls.env["engc.equipment.means.of.aquisition"].create({"name": "Compra"})
        cls.location = cls.env["engc.equipment.location"].search([], limit=1)
        if not cls.location:
            cls.location = cls.env["engc.equipment.location"].create({"name": "Sala T"})
        cls.marca = cls.env["engc.equipment.marca"].search([], limit=1)
        if not cls.marca:
            cls.marca = cls.env["engc.equipment.marca"].create({"name": "MarcaT"})

        # Produtos serviço
        Product = cls.env["product.product"]
        cls.product_qi = Product.create({
            "name": "Test QI", "type": "service",
            "invoice_policy": "delivery", "list_price": 1000,
        })
        cls.product_qo = Product.create({
            "name": "Test QO", "type": "service",
            "invoice_policy": "delivery", "list_price": 1200,
        })
        cls.product_qs = Product.create({
            "name": "Test QS", "type": "service",
            "invoice_policy": "delivery", "list_price": 800,
        })
        cls.product_qd_cmax = Product.create({
            "name": "Test Ciclo CMax", "type": "service",
            "invoice_policy": "delivery", "list_price": 700,
        })
        cls.product_qd_cmin = Product.create({
            "name": "Test Ciclo CMin", "type": "service",
            "invoice_policy": "delivery", "list_price": 500,
        })
        cls.product_malha_temp = Product.create({
            "name": "Test Malha Temp", "type": "service",
            "invoice_policy": "delivery", "list_price": 400,
        })
        cls.product_malha_press = Product.create({
            "name": "Test Malha Press", "type": "service",
            "invoice_policy": "delivery", "list_price": 450,
        })

        # Catálogo técnico
        cls.sensor_temp = cls.env["afr.qualificacao.sensor.kind"].search(
            [("code", "=", "TEMP")], limit=1
        )
        cls.sensor_press = cls.env["afr.qualificacao.sensor.kind"].search(
            [("code", "=", "PRESS")], limit=1
        )
        # estimated_hours=1.0 nas fixtures → product_uom_qty (= horas =
        # qty × 1) mantém paridade numérica com o nº de ciclos nos testes
        # legados. Testes que exercitam horas≠ciclos sobrescrevem (ver
        # test_estimated_hours e test_hours_vs_cycles).
        cls.cycle_cmax = cls.env["afr.qualificacao.cycle.type"].create({
            "name": "Test Carga Max", "code": "TQD-CMAX",
            "product_id": cls.product_qd_cmax.id,
            "estimated_hours": 1.0,
            "equipment_category_id": cls.category.id,
        })
        cls.cycle_cmin = cls.env["afr.qualificacao.cycle.type"].create({
            "name": "Test Carga Min", "code": "TQD-CMIN",
            "product_id": cls.product_qd_cmin.id,
            "estimated_hours": 1.0,
            "equipment_category_id": cls.category.id,
        })
        # F8.12 — cycle_type QO (sem carga) usado nos tests que antes usavam
        # do_qo=True (fallback removido na F8.12).
        cls.cycle_qo_test = cls.env["afr.qualificacao.cycle.type"].create({
            "name": "Test QO Sem Carga", "code": "TQO-TEST",
            "product_id": cls.product_qo.id,
            "load_type": "sem_carga",
            "estimated_hours": 1.0,
            "equipment_category_id": cls.category.id,
        })
        cls.malha_temp = cls.env["afr.qualificacao.malha.type"].create({
            "name": "Test Malha T", "code": "TMLH-T",
            "product_id": cls.product_malha_temp.id,
            "sensor_kind_id": cls.sensor_temp.id,
            "estimated_hours": 1.0,
            "equipment_category_id": cls.category.id,
        })
        cls.malha_press = cls.env["afr.qualificacao.malha.type"].create({
            "name": "Test Malha P", "code": "TMLH-P",
            "product_id": cls.product_malha_press.id,
            "estimated_hours": 1.0,
            "sensor_kind_id": cls.sensor_press.id,
        })

        # Type configs QI/QO/QS
        TC = cls.env["afr.qualificacao.type.config"]
        for qt, prod in (
            ("installation", cls.product_qi),
            ("operational", cls.product_qo),
            ("software", cls.product_qs),
        ):
            existing = TC.search([("qualification_type", "=", qt), ("company_id", "=", cls.company.id)], limit=1)
            if existing:
                existing.service_product_id = prod.id
                existing.default_unit_price = prod.list_price
            else:
                TC.create({
                    "qualification_type": qt,
                    "service_product_id": prod.id,
                    "default_unit_price": prod.list_price,
                    "company_id": cls.company.id,
                })

        # Cliente + equips
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Hospital", "customer_rank": 1,
        })
        cls.equip1 = cls.env["engc.equipment"].create({
            "client_id": cls.partner.id,
            "category_id": cls.category.id,
            "model": "TestModel1", "serial_number": "TSN-001",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id,
            "marca_id": cls.marca.id,
        })
        cls.equip2 = cls.env["engc.equipment"].create({
            "client_id": cls.partner.id,
            "category_id": cls.category.id,
            "model": "TestModel2", "serial_number": "TSN-002",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id,
            "marca_id": cls.marca.id,
        })

    def _apply(self, do_qi=False, qi_part01_declined=False,
               do_qo_part01=False, qo_part01_declined=False,
               calib=0, qo_cycles=0):
        """Cria SO + wizard configurador com 1 equipment line e aplica.

        Helper compartilhado pelos testes de Partes (TestApplyPartes,
        TestReportPartes). Retorna o sale.order com as linhas geradas.
        """
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        eq_vals = {
            "equipment_id": self.equip1.id,
            "do_qi": do_qi,
            "qi_part01_declined": qi_part01_declined,
            "do_qo_part01": do_qo_part01,
            "qo_part01_declined": qo_part01_declined,
        }
        if calib:
            eq_vals["calib_line_ids"] = [
                (0, 0, {"malha_type_id": self.malha_temp.id, "qty": 1})
                for _ in range(calib)
            ]
        if qo_cycles:
            eq_vals["qo_line_ids"] = [
                (0, 0, {"cycle_type_id": self.cycle_qo_test.id, "qty": 1})
                for _ in range(qo_cycles)
            ]
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        wiz.equipment_line_ids = [(0, 0, eq_vals)]
        wiz.action_apply()
        return so

    def _get_relatorio(self, os):
        """F4.8: cria/cacheia um relatorio dummy para a OS, usado em tests
        que precisam materializar cycles/malhas como passed/failed (gate
        em action_mark_approved exige relatorio_id vinculado).
        """
        if not hasattr(self, "_relatorio_cache"):
            self._relatorio_cache = {}
        if os.id in self._relatorio_cache:
            return self._relatorio_cache[os.id]
        now = fields.Datetime.now()
        rel = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os.id,
            "descricao": "Test relatório",
            "data_inicio": now,
            "data_fim": now + timedelta(hours=1),
        })
        self._relatorio_cache[os.id] = rel
        return rel
