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

    def test_upgrade_repoints_existing_installation_to_parte01(self):
        """Simula DB upgradeada de <16.0.5.9.0: já existe um type_config
        'installation' apontando para um produto QI ANTIGO (sem atributo
        Parte / sem variantes). O hook deve:
          1. anexar o atributo Parte ao MESMO template (preserva o produto);
          2. repoint a config para a variante Parte 01 desse template.

        Discriminante: no código antigo (bare `continue`), a config mantém o
        produto plano → 'Parte 01' NÃO está em product_template_variant_value_ids
        → este teste falha. No código novo, passa.
        """
        company = self.env["res.company"].create({"name": "Upgrade Repoint Test"})
        # Produto QI antigo: service, SEM atributo Parte (1 variante única).
        old_tmpl = self.env["product.template"].create({
            "name": "QI Antigo Upgrade",
            "type": "service",
            "detailed_type": "service",
            "list_price": 1234.0,
        })
        old_variant = old_tmpl.product_variant_id
        self.assertEqual(len(old_tmpl.product_variant_ids), 1)
        self.assertNotIn(
            PARTE_01_NAME,
            old_variant.product_template_variant_value_ids.mapped("name"),
        )
        # type_config installation pré-existente apontando para o produto antigo.
        cfg = self.TypeConfig.create({
            "qualification_type": "installation",
            "company_id": company.id,
            "service_product_id": old_variant.id,
            "default_unit_price": 0.0,
            "estimated_hours": 0.0,
        })

        # Executa o hook (idempotente). Deve repoint a config existente.
        _install_qualif_type_configs(self.env)

        cfg.invalidate_recordset()
        repointed = cfg.service_product_id
        part_vals = repointed.product_template_variant_value_ids.mapped("name")
        self.assertIn(
            PARTE_01_NAME, part_vals,
            "config installante existente deve passar a apontar p/ variante Parte 01",
        )
        # Template preservado: a variante Parte 01 pertence ao MESMO template
        # do produto originalmente configurado (não trocado pelo seed).
        self.assertEqual(
            repointed.product_tmpl_id, old_tmpl,
            "deve preservar o template configurado, anexando o atributo a ele",
        )
        # 2 variantes (Parte 01 / Parte 02) foram criadas no template antigo.
        self.assertEqual(len(old_tmpl.product_variant_ids), 2)

        # Idempotente: rodar de novo não muda nada.
        _install_qualif_type_configs(self.env)
        cfg.invalidate_recordset()
        self.assertEqual(cfg.service_product_id, repointed)


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

    def test_qi_part01_line_created(self):
        so = self._apply(do_qi=True, calib=1)
        p01 = so.order_line.filtered(
            lambda l: l.qualification_type == "installation" and l.part == "01"
        )
        self.assertEqual(len(p01), 1)
        self.assertEqual(p01.product_uom_qty, 1.0)

    def test_qi_part01_price_from_variant_not_default_unit_price(self):
        """Guard: o preço da Parte 01 QI vem do lst_price do variante
        (cfg.service_product_id.lst_price), NÃO do cfg.default_unit_price.

        Discriminante: setamos default_unit_price=999.0 com lst_price=1000.0.
        - Código correto (linha ~391: price_unit = lst_price) → 1000.0.
        - Código revertido (price_unit = default_unit_price) → 999.0.
        Assertar ==1000.0 e !=999.0 falha se alguém reverter a linha.
        """
        TC = self.env["afr.qualificacao.type.config"]
        cfg = TC.get_config_for("installation", self.company)
        # Premissa: variante a 1000.0 (vinda da fixture product_qi.list_price).
        self.assertEqual(cfg.service_product_id.lst_price, 1000.0)
        cfg.default_unit_price = 999.0
        self.assertNotEqual(cfg.default_unit_price, cfg.service_product_id.lst_price)

        so = self._apply(do_qi=True, calib=1)
        p01 = so.order_line.filtered(
            lambda l: l.qualification_type == "installation" and l.part == "01"
        )
        self.assertEqual(len(p01), 1)
        self.assertEqual(p01.price_unit, 1000.0)
        self.assertNotEqual(p01.price_unit, 999.0)

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

    def test_full_combo_qi_qo_declined_coherence(self):
        """Cenário combinado num único equip: QI + QO, ambas Parte 01
        declinadas, com Parte 02 (malha QI + ciclo QO) executadas.

        Combo válido: qi_part01_declined exige calib>=1; qo_part01_declined
        exige qo_cycles>=1.
        """
        so = self._apply(
            do_qi=True, qi_part01_declined=True,
            do_qo_part01=True, qo_part01_declined=True,
            qo_cycles=1, calib=1,
        )

        # Exatamente 2 linhas declinadas (QI P01 + QO P01).
        declined = so.order_line.filtered(lambda l: l.part01_declined)
        self.assertEqual(len(declined), 2)
        for l in declined:
            self.assertEqual(l.product_uom_qty, 0.0)
            self.assertEqual(l.part, "01")
            self.assertTrue(l.part01_declined)
        # Uma de cada tipo.
        self.assertEqual(
            set(declined.mapped("qualification_type")),
            {"installation", "operational"},
        )

        # Parte 02: malha QI (com malha_type_id) e ciclo QO (com cycle_type_id).
        malha_p02 = so.order_line.filtered(lambda l: l.malha_type_id)
        cycle_p02 = so.order_line.filtered(
            lambda l: l.cycle_type_id and l.qualification_type == "operational"
        )
        self.assertTrue(malha_p02)
        self.assertTrue(cycle_p02)
        self.assertTrue(all(l.part == "02" for l in malha_p02))
        self.assertTrue(all(l.part == "02" for l in cycle_p02))

        # amount_total = só as linhas não-declinadas (as duas Parte 02);
        # as declinadas (qty=0) contribuem 0.
        non_declined = so.order_line.filtered(lambda l: not l.part01_declined)
        # Calculado a partir dos totais (com imposto) da malha + ciclo (Parte 02),
        # que é o que amount_total soma. As declinadas (qty=0) somam 0.
        parte02 = malha_p02 | cycle_p02
        expected = sum(parte02.mapped("price_total"))
        self.assertGreater(expected, 0.0)
        self.assertEqual(so.amount_total, expected)
        self.assertEqual(so.amount_untaxed, sum(parte02.mapped("price_subtotal")))
        # As linhas Parte 02 (malha + ciclo) são todas não-declinadas e
        # carregam todo o valor: as eventuais demais linhas não-declinadas
        # têm preço 0 (não inflam o total).
        self.assertTrue(parte02.ids)
        self.assertLessEqual(set(parte02.ids), set(non_declined.ids))

        # Helper de declinados reporta exatamente 2.
        self.assertEqual(len(so._qualif_declined_items()), 2)

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


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestReportPartes(AfrQualificacaoTestCommon):
    """Helpers de relatório expõem part/declined/ref_price e excluem
    linhas declinadas do cronograma. Reusa `_apply` do common base."""

    def test_summary_items_have_part_and_declined(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        summary = so._qualif_equipment_summary()
        qi = [t for e in summary for t in e["types"] if t["code"] == "installation"][0]
        p01 = [i for i in qi["items"] if i.get("part") == "01"]
        self.assertTrue(p01)
        self.assertTrue(p01[0]["declined"])
        self.assertGreaterEqual(p01[0]["ref_price"], 0.0)

    def test_declined_items_helper(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        declined = so._qualif_declined_items()
        self.assertEqual(len(declined), 1)
        self.assertEqual(declined[0]["qualification_type"], "installation")

    def test_non_declined_has_no_declined_items(self):
        so = self._apply(do_qi=True, calib=1)
        self.assertEqual(so._qualif_declined_items(), [])

    def test_declined_excluded_from_schedule(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        rows = so._qualif_schedule_rows()
        # nenhuma row vem da linha declinada (qty=0)
        for r in rows:
            self.assertFalse(r.get("declined"))

    def test_declined_part01_contributes_zero_hours(self):
        """Discriminante: linha QI Parte 01 declinada NÃO infla horas.

        Cenário: cfg installation com estimated_hours=8.0; a Parte 01 QI
        é declinada (qty=0); só a malha (Parte 02, estimated_hours=1.0 ×
        qty=1 = 1.0h) deve contar.

        Pré-fix: _qualif_estimated_hours contava a linha declinada via
        fallback cfg.estimated_hours (qualif_cycle_qty=1) → 8.0 + 1.0 = 9.0.
        Pós-fix: linha declinada excluída → 1.0 (só malha).
        """
        TC = self.env["afr.qualificacao.type.config"]
        cfg = TC.get_config_for("installation", self.company)
        cfg.estimated_hours = 8.0  # inflaria as horas se a declinada contasse

        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)

        equip = self.equip1
        # Confirma o setup: existe linha QI Parte 01 declinada neste equip.
        declined = so.order_line.filtered(
            lambda l: l.equipment_id == equip
            and l.qualification_type == "installation"
            and l.part01_declined
        )
        self.assertTrue(declined, "setup: deve haver linha QI Parte 01 declinada")
        # Confirma que a malha (Parte 02) existe e vale 1.0h.
        malha = so.order_line.filtered(
            lambda l: l.equipment_id == equip and l.malha_type_id
        )
        self.assertTrue(malha)

        # Só a malha conta (1.0h); a Parte 01 declinada (8.0h) é excluída.
        self.assertEqual(so._qualif_estimated_hours(equip), 1.0)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRenderPartes(AfrQualificacaoTestCommon):
    def _scope_block(self, so):
        return self.env["afr.proposal.block"].create({
            "sale_order_id": so.id, "block_kind": "equipment_scope",
        })

    def test_scope_html_groups_partes_and_seal(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        block = self._scope_block(so)
        html = str(block._html_equipment_scope(so))
        self.assertIn("PARTE 01", html)
        self.assertIn("PARTE 02", html)
        self.assertIn("NÃO SOLICITADO EXECUÇÃO", html)

    def test_declined_box_present_only_when_declined(self):
        so_decl = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        so_ok = self._apply(do_qi=True, calib=1)
        block_decl = self._scope_block(so_decl)
        block_ok = self._scope_block(so_ok)
        html_decl = str(block_decl._html_declined_items(so_decl))
        html_ok = str(block_ok._html_declined_items(so_ok))
        self.assertIn("Itens Não Solicitados", html_decl)
        self.assertEqual(html_ok.strip(), "")


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestPortalPartes(AfrQualificacaoTestCommon):
    def _render_portal(self, so):
        # garante bloco escopo incluído
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id, "block_kind": "equipment_scope",
            "included": True,
        })
        html = self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": so},
        )
        return str(html)

    def test_portal_groups_partes_and_seal(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        html = self._render_portal(so)
        self.assertIn("PARTE 01", html)
        self.assertIn("NÃO SOLICITADO EXECUÇÃO", html)

    def test_portal_declined_box(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        html = self._render_portal(so)
        self.assertIn("Itens Não Solicitados", html)

    def test_portal_no_box_when_not_declined(self):
        so = self._apply(do_qi=True, calib=1)
        html = self._render_portal(so)
        self.assertNotIn("Itens Não Solicitados", html)
