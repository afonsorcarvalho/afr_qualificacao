"""Teste atributo 'Parte' seedado + variantes QI/QO.

Valida que:
1. O atributo 'Parte' existe com create_variant='always' e valores 01/02.
2. Os produtos QI e QO têm 2 variantes (Parte 01 / Parte 02).
3. Os type_config installation e operational (empresa fresh) apontam para
   o variante Parte 01.

Usa empresa isolada p/ garantir determinismo: o hook _install_qualif_type_configs
só cria type_configs ausentes — ao passar uma empresa nova, sempre cria do zero.
"""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged

from ..hooks import _install_qualif_type_configs, PARTE_01_NAME


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestPartesCatalog(TransactionCase):

    def setUp(self):
        super().setUp()
        # Empresa sem nenhum type.config — garante que o hook cria tudo do zero.
        self.fresh_company = self.env["res.company"].create({
            "name": "Empresa Partes Test",
        })
        # Garante type_configs para a empresa fresh (inclui installation/operational).
        _install_qualif_type_configs(self.env)
        self.TypeConfig = self.env["afr.qualificacao.type.config"]

    def test_parte_attribute_seeded(self):
        attr = self.env.ref("afr_qualificacao.product_attribute_parte")
        self.assertEqual(attr.create_variant, "always")
        vals = attr.value_ids.mapped("name")
        self.assertIn(PARTE_01_NAME, vals)
        self.assertIn("Parte 02", vals)

    def test_qi_qo_products_have_parte_variants(self):
        for qtype in ("installation", "operational"):
            cfg = self.TypeConfig.with_context(active_test=False).search([
                ("qualification_type", "=", qtype),
                ("company_id", "=", self.fresh_company.id),
            ], limit=1)
            self.assertTrue(cfg, "type_config p/ %s deve existir na empresa fresh" % qtype)
            variant = cfg.service_product_id
            part_vals = variant.product_template_variant_value_ids.mapped("name")
            self.assertIn(PARTE_01_NAME, part_vals)
            self.assertEqual(len(variant.product_tmpl_id.product_variant_ids), 2)

        # QS (software) tem variante única (sem atributo Parte) — valida que é service.
        qs_cfg = self.TypeConfig.with_context(active_test=False).search([
            ("qualification_type", "=", "software"),
            ("company_id", "=", self.fresh_company.id),
        ], limit=1)
        self.assertTrue(qs_cfg, "type_config p/ software deve existir na empresa fresh")
        self.assertEqual(qs_cfg.service_product_id.type, "service")
