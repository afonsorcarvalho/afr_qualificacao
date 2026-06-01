"""F-seed — Garante que o post_init cria type.config p/ QI/QO/QS.

Sem afr.qualificacao.type.config para 'installation'/'operational'/'software', o
configurador (action_apply) levanta UserError. O hook _install_qi_qs_type_config
semeia o mínimo viável (produto serviço preço 0 + config por empresa) para
fresh-installs/deploys funcionarem. Estes testes validam criação numa empresa
"limpa" e idempotência (chamar de novo não duplica nem quebra a constraint
unique(qualification_type, company_id)).
"""

from odoo.tests.common import TransactionCase

from ..hooks import _install_qi_qs_type_config, PARTE_01_NAME


class TestQiQsSeed(TransactionCase):

    def setUp(self):
        super().setUp()
        # Empresa "limpa" sem nenhuma type.config — simula fresh-install.
        self.fresh_company = self.env["res.company"].create({
            "name": "Empresa Seed Test",
        })
        self.TypeConfig = self.env["afr.qualificacao.type.config"]

    def _configs(self, company):
        return self.TypeConfig.with_context(active_test=False).search([
            ("company_id", "=", company.id),
            ("qualification_type", "in", ("installation", "operational", "software")),
        ])

    def test_creates_qi_qs_for_fresh_company(self):
        self.assertFalse(
            self._configs(self.fresh_company),
            "empresa nova não deveria ter type.config antes do seed",
        )
        _install_qi_qs_type_config(self.env)

        cfgs = self._configs(self.fresh_company)
        self.assertEqual(len(cfgs), 3, "esperado QI + QO + QS")
        types = set(cfgs.mapped("qualification_type"))
        self.assertEqual(types, {"installation", "operational", "software"})
        for cfg in cfgs:
            self.assertTrue(cfg.service_product_id, "config precisa de produto")
            self.assertEqual(cfg.service_product_id.type, "service")
            self.assertTrue(cfg.service_product_id.sale_ok)

    def test_idempotent_no_duplicates(self):
        _install_qi_qs_type_config(self.env)
        first = self._configs(self.fresh_company)
        self.assertEqual(len(first), 3)

        # Segunda chamada não deve duplicar nem violar a constraint unique.
        _install_qi_qs_type_config(self.env)
        second = self._configs(self.fresh_company)
        self.assertEqual(second, first, "seed não deve recriar/duplicar")

    def test_preserves_existing_config(self):
        # Empresa com config manual pré-existente (produto QI SEM atributo Parte,
        # como numa DB pré-16.0.5.9.0). O seed preserva o registro, o TEMPLATE e
        # o preço, mas repoint para a variante Parte 01 desse mesmo template
        # (necessário p/ o price_extra das partes funcionar).
        manual_template = self.env["product.template"].create({
            "name": "QI Manual", "type": "service",
            "detailed_type": "service", "sale_ok": True,
        })
        manual_product = manual_template.product_variant_id
        manual = self.TypeConfig.create({
            "qualification_type": "installation",
            "company_id": self.fresh_company.id,
            "service_product_id": manual_product.id,
            "default_unit_price": 999.0,
        })
        _install_qi_qs_type_config(self.env)

        cfgs = self._configs(self.fresh_company)
        # QI manual preservada (mesmo registro + mesmo template + mesmo preço)
        # mas repointada p/ variante Parte 01; + QO + QS criadas.
        self.assertEqual(len(cfgs), 3)
        qi = cfgs.filtered(lambda c: c.qualification_type == "installation")
        self.assertEqual(qi, manual, "mesmo registro de config (não recriado)")
        # Template preservado (atributo anexado ao produto configurado).
        self.assertEqual(qi.service_product_id.product_tmpl_id, manual_template)
        # Repointado p/ a variante Parte 01 desse template.
        self.assertIn(
            PARTE_01_NAME,
            qi.service_product_id.product_template_variant_value_ids.mapped("name"),
        )
        self.assertAlmostEqual(qi.default_unit_price, 999.0, places=2)
