"""Catálogo de serviços (afr.servico / afr.servico.grupo)."""

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common_servico import AfrServicoTestCommon


@tagged("post_install", "-at_install")
class TestServicoCatalog(AfrServicoTestCommon):

    def test_default_unit_price_from_product(self):
        self.assertEqual(self.svc_seladora._default_unit_price(), 120)

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
