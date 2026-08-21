"""Testes F8.2 — builder da Proposta LEGO.

Cobre:
- autofill de linha de equipamento a partir de afr.qualificacao.config.template;
- serviços opcionais viram linhas de SO marcadas is_proposal_optional;
- linhas de opcional NÃO geram qualificação no confirm;
- seed de proposal_block_ids a partir do template (idempotente + reload).
"""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestProposalBuilder(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cfg_template = cls.env["afr.qualificacao.config.template"].create({
            "name": "Pacote Autoclave Teste",
            "equipment_category_id": cls.category.id,
            "do_qi": True,
            "do_qo": True,
            "price_base": 2400.0,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": cls.cycle_cmax.id, "qty": 2}),
            ],
        })
        cls.optional = cls.env.ref("afr_qualificacao.proposal_optional_folder")
        cls.proposal_tpl = cls.env.ref(
            "afr_qualificacao.proposal_template_labquali"
        )

    def _new_so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _configurator_for(self, so):
        return self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })

    def _equipment_line(self, wiz, equipment, **kw):
        vals = {"wizard_id": wiz.id, "equipment_id": equipment.id}
        vals.update(kw)
        return self.env["afr.qualificacao.configurator.equipment"].create(vals)

    # --- autofill do template de equipamento ------------------------------

    def test_config_template_autofills_equipment_line(self):
        """Selecionar config.template preenche QI/QO/QS + ciclos."""
        wiz = self._configurator_for(self._new_so())
        eq = self._equipment_line(wiz, self.equip1)
        eq.config_template_id = self.cfg_template
        eq._onchange_config_template()
        self.assertTrue(eq.do_qi)
        self.assertTrue(eq.do_qo)
        self.assertFalse(eq.do_qs)
        self.assertEqual(len(eq.qd_line_ids), 1)
        self.assertEqual(eq.qd_line_ids.cycle_type_id, self.cycle_cmax)
        self.assertEqual(eq.qd_line_ids.qty, 2)

    # --- troca de cliente com equipamentos no escopo ----------------------

    def test_change_partner_warns_on_foreign_equipment(self):
        """F10.3 — trocar cliente com equipamentos de outro cliente no escopo
        retorna aviso (equip1.client_id = self.partner)."""
        so = self._new_so()
        wiz = self._configurator_for(so)
        self._equipment_line(wiz, self.equip1, do_qi=True)
        wiz.action_apply()
        other = self.env["res.partner"].create({"name": "Outro Cliente"})
        so.partner_id = other
        result = so._onchange_partner_id_qualif_equipment_warning()
        self.assertTrue(result and result.get("warning"))
        self.assertIn(self.equip1.display_name, result["warning"]["message"])

    def test_change_partner_no_warning_when_same_client(self):
        """Sem divergência (equipamento é do cliente) → sem aviso."""
        so = self._new_so()
        wiz = self._configurator_for(so)
        self._equipment_line(wiz, self.equip1, do_qi=True)
        wiz.action_apply()
        # equip1.client_id == self.partner == so.partner_id → sem aviso
        self.assertFalse(so._onchange_partner_id_qualif_equipment_warning())

    # --- serviços opcionais -----------------------------------------------

    def test_optional_line_does_not_generate_qualificacao(self):
        """F10.2 — opcionais não vêm mais do configurador (linha avulsa
        manual). A linha is_proposal_optional continua excluída da geração
        de qualificações no confirm."""
        so = self._new_so()
        wiz = self._configurator_for(so)
        self._equipment_line(wiz, self.equip1, do_qi=True)
        wiz.action_apply()
        # Vendedor adiciona o opcional manualmente como linha avulsa.
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.optional.product_id.id,
            "name": self.optional.name,
            "product_uom_qty": 1.0,
            "is_proposal_optional": True,
        })
        self._confirm_and_generate_os(so)
        # Só QI gerou qualificação; a linha opcional foi ignorada.
        self.assertEqual(len(so.qualificacao_ids), 1)
        self.assertEqual(
            so.qualificacao_ids.qualification_type, "installation"
        )

    # --- blocos da proposta -----------------------------------------------

    def test_so_gets_default_proposal_template(self):
        """Nova SO recebe o template de proposta default."""
        so = self._new_so()
        self.assertTrue(so.proposal_template_id)

    def test_seed_proposal_blocks_copies_template_lines(self):
        """_seed_proposal_blocks copia os slots do template em ordem."""
        so = self._new_so()
        so.proposal_template_id = self.proposal_tpl
        so._seed_proposal_blocks()
        self.assertEqual(
            len(so.proposal_block_ids), len(self.proposal_tpl.line_ids)
        )
        first = so.proposal_block_ids.sorted("sequence")[0]
        self.assertEqual(first.block_kind, "static")
        self.assertTrue(first.body)

    def test_seed_proposal_blocks_is_idempotent(self):
        """Semear duas vezes não duplica blocos."""
        so = self._new_so()
        so.proposal_template_id = self.proposal_tpl
        so._seed_proposal_blocks()
        count = len(so.proposal_block_ids)
        so._seed_proposal_blocks()
        self.assertEqual(len(so.proposal_block_ids), count)

    def test_apply_seeds_proposal_blocks(self):
        """action_apply do configurador semeia os blocos da proposta."""
        so = self._new_so()
        so.proposal_template_id = self.proposal_tpl
        wiz = self._configurator_for(so)
        self._equipment_line(wiz, self.equip1, do_qi=True)
        wiz.action_apply()
        self.assertEqual(
            len(so.proposal_block_ids), len(self.proposal_tpl.line_ids)
        )

    def test_seed_uses_template_line_title(self):
        """F8.7 — título definido no slot do template vai para o bloco."""
        so = self._new_so()
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Title"})
        self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id, "sequence": 10,
            "block_kind": "financial", "title": "Investimento",
        })
        so.proposal_template_id = tpl
        so._seed_proposal_blocks()
        self.assertEqual(so.proposal_block_ids[0].title, "Investimento")

    def test_seed_dynamic_block_falls_back_to_kind_label(self):
        """F8.7 — bloco dinâmico sem título recebe o rótulo do tipo."""
        so = self._new_so()
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl NoTitle"})
        self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id, "sequence": 10, "block_kind": "financial",
        })
        so.proposal_template_id = tpl
        so._seed_proposal_blocks()
        self.assertEqual(so.proposal_block_ids[0].title, "Resumo Financeiro")

    def test_seed_copies_page_break_from_template_line(self):
        """F8.6 — page_break do slot do template é copiado para o bloco."""
        so = self._new_so()
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl PB"})
        self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id, "sequence": 10,
            "block_kind": "financial", "page_break": True,
        })
        self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id, "sequence": 20,
            "block_kind": "optionals", "page_break": False,
        })
        so.proposal_template_id = tpl
        so._seed_proposal_blocks()
        blocks = so.proposal_block_ids.sorted("sequence")
        self.assertTrue(blocks[0].page_break)
        self.assertFalse(blocks[1].page_break)

    def test_reload_proposal_blocks_discards_edits(self):
        """action_reload_proposal_blocks recarrega do template."""
        so = self._new_so()
        so.proposal_template_id = self.proposal_tpl
        so._seed_proposal_blocks()
        so.proposal_block_ids[0].title = "EDITADO MANUALMENTE"
        so.action_reload_proposal_blocks()
        self.assertNotIn(
            "EDITADO MANUALMENTE", so.proposal_block_ids.mapped("title")
        )


@tagged("post_install", "-at_install")
class TestFrozenFinancialSummaryPredicate(AfrQualificacaoTestCommon):
    """F1 (fix round 2026-08-21) — predicado usado pela migração 16.0.7.0.0
    para identificar um bloco `financial` congelado em `static` (snapshot
    manual feito ANTES do `UserError` em `action_edit_block` existir).

    Migração não roda nos testes (só num upgrade real de versão, ver
    `TestTemplateCleanup` em test_scope_render.py) — o que dá para testar
    diretamente é o próprio predicado que ela usa,
    `AfrProposalBlock._qualif_is_frozen_financial_summary`, com as 3
    condições cumulativas do critério estreito.
    """

    def _new_so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _block(self, so, **vals):
        vals.setdefault("sale_order_id", so.id)
        return self.env["afr.proposal.block"].create(vals)

    def test_matches_static_titled_resumo_financeiro_with_total_geral_in_body(self):
        """Caso real: id=636, SO C26-08-0018 — as 3 condições batem."""
        so = self._new_so()
        block = self._block(
            so, block_kind="static", title="Resumo Financeiro",
            body="<p>TOTAL GERAL: R$ 10.373,48</p>",
        )
        self.assertTrue(block._qualif_is_frozen_financial_summary())

    def test_does_not_match_static_same_title_without_total_geral_in_body(self):
        """Mesmo título, mas corpo sem a assinatura do totalizador antigo —
        pode ser um bloco de texto livre que o usuário só batizou assim;
        não é seguro apagar."""
        so = self._new_so()
        block = self._block(
            so, block_kind="static", title="Resumo Financeiro",
            body="<p>Ver anexo para detalhes de precificação.</p>",
        )
        self.assertFalse(block._qualif_is_frozen_financial_summary())

    def test_does_not_match_different_title(self):
        """Bloco `static` com "TOTAL GERAL" no body mas título diferente —
        não é um Resumo Financeiro congelado, é outra coisa."""
        so = self._new_so()
        block = self._block(
            so, block_kind="static", title="Observações",
            body="<p>TOTAL GERAL: R$ 10.373,48</p>",
        )
        self.assertFalse(block._qualif_is_frozen_financial_summary())

    def test_does_not_match_non_static_financial_block(self):
        """Bloco `financial` (não convertido para `static`) é tratado à
        parte pela migração (busca direta por `block_kind`), não por este
        predicado — que só reconhece `static`."""
        so = self._new_so()
        block = self._block(so, block_kind="financial")
        self.assertFalse(block._qualif_is_frozen_financial_summary())

    def test_does_not_match_static_without_body(self):
        so = self._new_so()
        block = self._block(
            so, block_kind="static", title="Resumo Financeiro", body=False,
        )
        self.assertFalse(block._qualif_is_frozen_financial_summary())
