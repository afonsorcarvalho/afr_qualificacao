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
        so.action_confirm()
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
