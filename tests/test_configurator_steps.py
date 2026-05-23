"""Testes F8.4 — configurador guiado multi-step.

Cobre navegação entre etapas (escopo → opcionais → blocos → revisão),
validação ao avançar, seed de blocos ao entrar na etapa Blocos e o
fluxo completo até Aplicar.
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

    def test_next_step_advances(self):
        """F8.7 — Escopo avança para Blocos (Blocos antes de Opcionais)."""
        wiz = self._wizard()
        self._add_equipment(wiz)
        wiz.action_next_step()
        self.assertEqual(wiz.step, "blocos")

    def test_step_order_blocos_before_opcionais(self):
        """F8.7 — ordem: escopo → blocos → opcionais → revisão."""
        wiz = self._wizard()
        self._add_equipment(wiz)
        wiz.action_next_step()
        wiz.action_next_step()
        self.assertEqual(wiz.step, "opcionais")

    def test_next_from_escopo_requires_equipment(self):
        """Avançar do escopo sem equipamento é bloqueado."""
        wiz = self._wizard()
        with self.assertRaises(UserError):
            wiz.action_next_step()

    def test_prev_step_goes_back(self):
        wiz = self._wizard()
        wiz.step = "opcionais"
        wiz.action_prev_step()
        self.assertEqual(wiz.step, "blocos")

    def test_entering_blocos_seeds_blocks(self):
        """Ir para a etapa Blocos semeia os blocos da proposta."""
        wiz = self._wizard()
        self._add_equipment(wiz)
        self.assertFalse(wiz.sale_order_id.proposal_block_ids)
        wiz._go_to_step("blocos")
        self.assertEqual(wiz.step, "blocos")
        self.assertTrue(wiz.sale_order_id.proposal_block_ids)

    def test_full_flow_to_apply(self):
        """Fluxo escopo → opcionais → blocos → revisão → aplicar."""
        wiz = self._wizard()
        self._add_equipment(wiz)
        wiz.action_next_step()   # → opcionais
        wiz.action_next_step()   # → blocos (semeia)
        wiz.action_next_step()   # → revisão
        self.assertEqual(wiz.step, "revisao")
        self.assertTrue(wiz.sale_order_id.proposal_block_ids)
        wiz.action_apply()
        self.assertTrue(
            wiz.sale_order_id.order_line.filtered("is_qualificacao_managed")
        )
