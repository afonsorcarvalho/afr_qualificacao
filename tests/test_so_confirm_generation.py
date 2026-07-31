"""Confirm da SO NÃO materializa mais nada — geração é manual via wizard.

Cutover 16.0.6.13.0: a OS de qualificação passou a ser gerada por grupo de
equipamentos, depois da confirmação, pelo wizard
`afr.qualificacao.os.generate.wizard`.
"""

from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestSoConfirmGeneration(AfrQualificacaoTestCommon):

    def _build_so_with_lines(self, equipment_lines_spec):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, spec) for spec in equipment_lines_spec]
        wiz.action_apply()
        return so

    def test_confirm_nao_cria_os_nem_qualificacao(self):
        so = self._build_so_with_lines([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])
        so.action_confirm()
        self.assertEqual(so.qualificacao_os_count, 0)
        self.assertEqual(so.qualificacao_count, 0)
        self.assertEqual(so.engc_os_count, 0)

    def test_confirm_deixa_equipamentos_pendentes(self):
        so = self._build_so_with_lines([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])
        so.action_confirm()
        self.assertEqual(
            set(so._pending_qualif_lines().mapped("equipment_id").ids),
            {self.equip1.id, self.equip2.id},
        )

    def test_geracao_explicita_produz_estrutura_completa(self):
        """O que o confirm fazia antes, agora o helper faz."""
        so = self._build_so_with_lines([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])
        os = self._confirm_and_generate_os(so)
        self.assertEqual(so.qualificacao_os_count, 1)
        self.assertEqual(set(os.equipment_ids.ids), {self.equip1.id, self.equip2.id})
        self.assertEqual(so.engc_os_count, 0)
