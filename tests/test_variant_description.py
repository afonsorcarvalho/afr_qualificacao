"""Testes da descrição de venda por variante (product.product)."""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestVariantDescription(TransactionCase):
    """variant_description_sale substitui template; vazia faz fallback."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attr = cls.env["product.attribute"].create({
            "name": "Config Test",
            "create_variant": "always",
        })
        cls.val_a = cls.env["product.attribute.value"].create({
            "name": "Cfg-A", "attribute_id": cls.attr.id,
        })
        cls.val_b = cls.env["product.attribute.value"].create({
            "name": "Cfg-B", "attribute_id": cls.attr.id,
        })
        cls.template = cls.env["product.template"].create({
            "name": "Serviço Calib Test",
            "type": "service",
            "description_sale": "Descrição padrão do template",
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attr.id,
                "value_ids": [(6, 0, [cls.val_a.id, cls.val_b.id])],
            })],
        })
        cls.variant_a = cls.template.product_variant_ids[0]
        cls.variant_b = cls.template.product_variant_ids[1]

    def test_variant_description_overrides_template(self):
        self.variant_a.variant_description_sale = "Texto exclusivo A"
        self.assertEqual(
            self.variant_a.get_product_multiline_description_sale(),
            "Texto exclusivo A",
        )

    def test_empty_variant_falls_back_to_template(self):
        self.variant_b.variant_description_sale = False
        result = self.variant_b.get_product_multiline_description_sale()
        self.assertIn("Descrição padrão do template", result)
        self.assertIn(self.variant_b.display_name, result)

    def test_so_line_uses_variant_description(self):
        self.variant_a.variant_description_sale = "Texto exclusivo A"
        partner = self.env["res.partner"].create({"name": "Cli Var Test"})
        order = self.env["sale.order"].create({"partner_id": partner.id})
        # No Odoo 16, `name` é campo computado (_compute_name) disparado por
        # product_id — basta criar a linha com o produto para refletir a
        # descrição da variante.
        line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.variant_a.id,
        })
        self.assertEqual(line.name, "Texto exclusivo A")
