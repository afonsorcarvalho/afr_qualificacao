"""Testes do configurador guiado.

F10.2 — fluxo reduzido a 2 etapas: Escopo → Revisão. Blocos da proposta
editados no form do SO; serviços opcionais adicionados manualmente. Os blocos
são semeados no Aplicar.
"""

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestConfiguratorSteps(AfrQualificacaoTestCommon):

    def _wizard(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        return self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })

    def _add_equipment(self, wiz):
        return self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
        })

    def test_wizard_starts_on_escopo(self):
        self.assertEqual(self._wizard().step, "escopo")

    def test_next_step_advances_to_revisao(self):
        """F10.2 — Escopo avança direto para Revisão (2 etapas)."""
        wiz = self._wizard()
        self._add_equipment(wiz)
        wiz.action_next_step()
        self.assertEqual(wiz.step, "revisao")

    def test_next_from_escopo_requires_equipment(self):
        """Avançar do escopo sem equipamento é bloqueado."""
        wiz = self._wizard()
        with self.assertRaises(UserError):
            wiz.action_next_step()

    def test_prev_step_goes_back(self):
        wiz = self._wizard()
        wiz.step = "revisao"
        wiz.action_prev_step()
        self.assertEqual(wiz.step, "escopo")

    def test_full_flow_to_apply_seeds_blocks(self):
        """Fluxo escopo → revisão → aplicar; Aplicar semeia os blocos."""
        wiz = self._wizard()
        self._add_equipment(wiz)
        wiz.action_next_step()   # → revisão
        self.assertEqual(wiz.step, "revisao")
        wiz.action_apply()
        self.assertTrue(
            wiz.sale_order_id.order_line.filtered("is_qualificacao_managed")
        )
        # blocos semeados no Aplicar (template default da empresa)
        self.assertTrue(wiz.sale_order_id.proposal_block_ids)
