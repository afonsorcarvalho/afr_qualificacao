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
from .common import AfrQualificacaoTestCommon


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


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestPartFields(TransactionCase):
    def _mk_order(self):
        partner = self.env["res.partner"].create({"name": "Cli Parte"})
        return self.env["sale.order"].create({"partner_id": partner.id})

    def test_declined_line_excluded_from_total(self):
        so = self._mk_order()
        prod = self.env["product.product"].create({
            "name": "Verif QI", "type": "service", "list_price": 1000.0,
        })
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": prod.id,
            "product_uom_qty": 0.0, "price_unit": 1000.0,
            "part": "01", "part01_declined": True,
            "is_qualificacao_managed": True,
        })
        self.assertEqual(line.price_subtotal, 0.0)
        self.assertEqual(so.amount_total, 0.0)
        self.assertEqual(line.price_unit, 1000.0)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestConfiguratorParte(TransactionCase):
    def test_equipment_line_has_parte_fields(self):
        eq_model = self.env["afr.qualificacao.configurator.equipment"]
        fields_ = eq_model.fields_get()
        for fname in ("qi_part01_declined", "do_qo_part01", "qo_part01_declined"):
            self.assertIn(fname, fields_)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestApplyPartes(AfrQualificacaoTestCommon):
    """action_apply: gera Parte 01 (QI/QO), tag Parte 02, validação de declínio."""

    def _apply(self, do_qi=False, qi_part01_declined=False,
               do_qo_part01=False, qo_part01_declined=False,
               calib=0, qo_cycles=0):
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

    def test_qi_part01_line_created(self):
        so = self._apply(do_qi=True, calib=1)
        p01 = so.order_line.filtered(
            lambda l: l.qualification_type == "installation" and l.part == "01"
        )
        self.assertEqual(len(p01), 1)
        self.assertEqual(p01.product_uom_qty, 1.0)

    def test_qi_part01_declined_zero_qty(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        p01 = so.order_line.filtered(lambda l: l.part == "01" and l.part01_declined)
        self.assertEqual(p01.product_uom_qty, 0.0)

    def test_qo_part01_line_created_once(self):
        so = self._apply(do_qo_part01=True, qo_cycles=1)
        p01 = so.order_line.filtered(
            lambda l: l.qualification_type == "operational" and l.part == "01"
        )
        self.assertEqual(len(p01), 1)

    def test_malha_tagged_part02(self):
        so = self._apply(do_qi=True, calib=1)
        malha = so.order_line.filtered(lambda l: l.malha_type_id)
        self.assertTrue(malha)
        self.assertTrue(all(l.part == "02" for l in malha))

    def test_qo_cycle_tagged_part02(self):
        so = self._apply(do_qo_part01=True, qo_cycles=1)
        cyc = so.order_line.filtered(
            lambda l: l.cycle_type_id and l.qualification_type == "operational"
        )
        self.assertTrue(cyc)
        self.assertTrue(all(l.part == "02" for l in cyc))

    def test_decline_qi_part01_without_part02_raises(self):
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self._apply(do_qi=True, qi_part01_declined=True, calib=0)

    def test_reload_preserves_decline(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz._load_from_existing_lines()
        eq = wiz.equipment_line_ids[:1]
        self.assertTrue(eq.qi_part01_declined)

    def test_reload_preserves_qo_part01(self):
        so = self._apply(do_qo_part01=True, qo_part01_declined=True, qo_cycles=1)
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz._load_from_existing_lines()
        eq = wiz.equipment_line_ids[:1]
        self.assertTrue(eq.do_qo_part01)
        self.assertTrue(eq.qo_part01_declined)

    def test_confirm_declined_qi_skips_installation_qualif(self):
        """Linha QI Parte 01 declinada (qty=0) NÃO gera qualificação; a
        malha (Parte 02) gera normalmente."""
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        so.action_confirm()
        qi_line = so.order_line.filtered(
            lambda l: l.part == "01" and l.part01_declined
        )
        self.assertTrue(qi_line)
        self.assertFalse(qi_line.afr_qualificacao_id)
        calib_line = so.order_line.filtered(lambda l: l.malha_type_id)
        self.assertTrue(calib_line.afr_qualificacao_id)
        self.assertEqual(
            calib_line.afr_qualificacao_id.qualification_type, "calibration"
        )
