"""F-seed — Garante que o post_init cria type.config p/ QI/QS.

Sem afr.qualificacao.type.config para 'installation'/'software', o
configurador (action_apply) levanta UserError. O hook _install_qi_qs_type_config
semeia o mínimo viável (produto serviço preço 0 + config por empresa) para
fresh-installs/deploys funcionarem. Estes testes validam criação numa empresa
"limpa" e idempotência (chamar de novo não duplica nem quebra a constraint
unique(qualification_type, company_id)).
"""

from odoo.tests.common import TransactionCase

from ..hooks import _install_qi_qs_type_config


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
            ("qualification_type", "in", ("installation", "software")),
        ])

    def test_creates_qi_qs_for_fresh_company(self):
        self.assertFalse(
            self._configs(self.fresh_company),
            "empresa nova não deveria ter type.config antes do seed",
        )
        _install_qi_qs_type_config(self.env)

        cfgs = self._configs(self.fresh_company)
        self.assertEqual(len(cfgs), 2, "esperado QI + QS")
        types = set(cfgs.mapped("qualification_type"))
        self.assertEqual(types, {"installation", "software"})
        for cfg in cfgs:
            self.assertTrue(cfg.service_product_id, "config precisa de produto")
            self.assertEqual(cfg.service_product_id.type, "service")
            self.assertTrue(cfg.service_product_id.sale_ok)

    def test_idempotent_no_duplicates(self):
        _install_qi_qs_type_config(self.env)
        first = self._configs(self.fresh_company)
        self.assertEqual(len(first), 2)

        # Segunda chamada não deve duplicar nem violar a constraint unique.
        _install_qi_qs_type_config(self.env)
        second = self._configs(self.fresh_company)
        self.assertEqual(second, first, "seed não deve recriar/duplicar")

    def test_preserves_existing_config(self):
        # Empresa com config manual pré-existente: seed não toca nela.
        manual_product = self.env["product.product"].create({
            "name": "QI Manual", "type": "service",
            "detailed_type": "service", "sale_ok": True,
        })
        manual = self.TypeConfig.create({
            "qualification_type": "installation",
            "company_id": self.fresh_company.id,
            "service_product_id": manual_product.id,
            "default_unit_price": 999.0,
        })
        _install_qi_qs_type_config(self.env)

        cfgs = self._configs(self.fresh_company)
        # QI manual preservada (mesmo registro, mesmo produto/preço) + QS criada.
        self.assertEqual(len(cfgs), 2)
        qi = cfgs.filtered(lambda c: c.qualification_type == "installation")
        self.assertEqual(qi, manual)
        self.assertEqual(qi.service_product_id, manual_product)
        self.assertAlmostEqual(qi.default_unit_price, 999.0, places=2)
