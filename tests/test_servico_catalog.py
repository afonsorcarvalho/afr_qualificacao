"""Catálogo de serviços (afr.servico / afr.servico.grupo)."""

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common_servico import AfrServicoTestCommon


@tagged("post_install", "-at_install")
class TestServicoCatalog(AfrServicoTestCommon):

    def test_default_unit_price_from_product(self):
        self.assertEqual(self.svc_seladora._default_unit_price(), 120)

    def test_default_unit_price_own_field_wins(self):
        """Preço do serviço prevalece; vazio volta ao preço do produto."""
        self.svc_seladora.default_unit_price = 150
        self.assertEqual(self.svc_seladora._default_unit_price(), 150)
        line = self.env["sale.order.line"]._service_line_vals(
            self.svc_seladora, 2)
        self.assertEqual(line["price_unit"], 150)
        self.svc_seladora.default_unit_price = 0
        self.assertEqual(self.svc_seladora._default_unit_price(), 120)

    def test_list_view_shows_price(self):
        arch = self.env["afr.servico"].get_view(
            self.env.ref("afr_qualificacao.view_servico_tree").id, "tree")["arch"]
        self.assertIn('name="default_unit_price"', arch)

    def test_chapter_title_falls_back_to_name(self):
        self.assertFalse(self.group_nr13.chapter_title)
        self.assertEqual(self.group_nr13._chapter_title(), "NR-13")
        self.group_nr13.chapter_title = "Inspeção de Vasos de Pressão"
        self.assertEqual(
            self.group_nr13._chapter_title(), "Inspeção de Vasos de Pressão"
        )

    def test_product_must_be_service(self):
        consu = self.env["product.product"].create({
            "name": "Test Consumível", "type": "consu",
        })
        with self.assertRaises(ValidationError):
            self.env["afr.servico"].create({
                "name": "Test Serviço Inválido",
                "group_id": self.group_calib.id,
                "product_id": consu.id,
            })

    def test_seed_loaded(self):
        ref = self.env.ref
        self.assertEqual(
            ref("afr_qualificacao.servico_calib_seladora").group_id,
            ref("afr_qualificacao.servico_grupo_calibracao"),
        )
        for xmlid in (
            "servico_calib_sensor_ambiente", "servico_calib_camara_fria",
            "servico_calib_estufa", "servico_calib_incubadora_ib",
            "servico_calib_seladora", "servico_nr13_inspecao",
            "servico_vazao_exaustor",
        ):
            self.assertTrue(
                ref("afr_qualificacao.%s" % xmlid).exists(), xmlid
            )

    def test_salesman_reads_but_cannot_write(self):
        user = self.env["res.users"].create({
            "name": "Test Vendedor",
            "login": "test_servico_salesman",
            "groups_id": [(6, 0, [self.env.ref("sales_team.group_sale_salesman").id])],
        })
        svc = self.svc_seladora.with_user(user)
        self.assertEqual(svc.name, "Test Calibração Seladora")
        with self.assertRaises(AccessError):
            svc.write({"name": "Outro"})
