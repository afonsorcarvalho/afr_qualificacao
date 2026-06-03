# -*- coding: utf-8 -*-
"""Testes de sequenciamento SO/OS: formato C[YY]-[MM]-NNNN e derivação OS."""
import re

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon

SO_PATTERN = re.compile(r"^C\d{2}-\d{2}-\d{4}$")
OS_PATTERN = re.compile(r"^OS\d{2}-\d{2}-\d{4}$")


@tagged("afr_qualificacao", "sequence_naming", "post_install", "-at_install")
class TestSoOsSequenceNaming(AfrQualificacaoTestCommon):
    """Verifica formato C[YY]-[MM]-NNNN no SO e derivação OS."""

    # ─────────────────────────────────────────────────────────────
    # SO SEQUENCE FORMAT
    # ─────────────────────────────────────────────────────────────
    def test_so_name_matches_pattern(self):
        """SO confirmada recebe nome no formato C[YY]-[MM]-NNNN."""
        so = self._apply(do_qi=True)
        so.action_confirm()
        self.assertRegex(so.name, SO_PATTERN,
                         f"SO name '{so.name}' não bate padrão C[YY]-[MM]-NNNN")

    def test_two_so_sequential(self):
        """Dois SOs gerados têm nomes distintos (sequência incrementa)."""
        so1 = self._apply(do_qi=True)
        so1.action_confirm()
        so2 = self._apply(do_qi=True)
        so2.action_confirm()
        self.assertNotEqual(so1.name, so2.name)

    # ─────────────────────────────────────────────────────────────
    # OS DERIVATION
    # ─────────────────────────────────────────────────────────────
    def test_os_name_derived_from_so(self):
        """OS criada na confirmação tem nome derivado do SO (C→OS)."""
        so = self._apply(do_qi=True)
        so.action_confirm()
        self.assertTrue(so.qualificacao_os_ids, "OS deve existir após confirm")
        os = so.qualificacao_os_ids[0]
        self.assertRegex(os.name, OS_PATTERN,
                         f"OS name '{os.name}' não bate padrão OS[YY]-[MM]-NNNN")
        # Sufixo deve ser idêntico: C26-06-0001 → OS26-06-0001
        self.assertEqual(os.name[2:], so.name[1:],
                         "Sufixo de OS deve coincidir com sufixo de SO")

    def test_os_name_prefix_is_os(self):
        """OS começa com 'OS', não 'C' nem 'QOS'."""
        so = self._apply(do_qi=True)
        so.action_confirm()
        os = so.qualificacao_os_ids[0]
        self.assertTrue(os.name.startswith("OS"),
                        f"OS name deve começar com 'OS', got '{os.name}'")

    def test_direct_os_creation_still_uses_qos_sequence(self):
        """OS criada diretamente (sem SO) ainda recebe prefixo QOS."""
        os_direct = self.env["afr.qualificacao.os"].create({
            "company_id": self.env.company.id,
        })
        self.assertTrue(os_direct.name.startswith("QOS"),
                        f"OS direta deve usar sequência QOS, got '{os_direct.name}'")

    # ─────────────────────────────────────────────────────────────
    # RE-CONFIRM IDEMPOTÊNCIA
    # ─────────────────────────────────────────────────────────────
    def test_reconfirm_reuses_os(self):
        """Reconfirmar SO (cancel+draft+addline+confirm) não cria nova OS."""
        so = self._apply(do_qi=True)
        so.action_confirm()
        self.assertEqual(len(so.qualificacao_os_ids), 1)
        os_name_original = so.qualificacao_os_ids[0].name
        # Cancel e reset para rascunho
        so.action_cancel()
        so.action_draft()
        # Adiciona nova linha QO (nova linha não processada ainda)
        so.write({"order_line": [(0, 0, {
            "product_id": self.product_qo.id,
            "product_uom_qty": 1,
            "price_unit": 1200,
            "equipment_id": self.equip2.id,
            "qualification_type": "operational",
            "is_qualificacao_managed": True,
        })]})
        so.action_confirm()
        self.assertEqual(len(so.qualificacao_os_ids), 1,
                         "Deve existir exactamente 1 OS após re-confirm")
        self.assertEqual(so.qualificacao_os_ids[0].name, os_name_original,
                         "Nome da OS deve ser o mesmo após re-confirm")

    # ─────────────────────────────────────────────────────────────
    # COLLISION GUARD
    # ─────────────────────────────────────────────────────────────
    def test_collision_guard_reuses_orphan_os(self):
        """OS desvinculada com mesmo nome é recuperada, não duplicada."""
        so = self._apply(do_qi=True)
        so.action_confirm()
        os = so.qualificacao_os_ids[0]
        os_name = os.name
        os_id = os.id
        # Desvincular a OS (sem apagar o record)
        so.write({"qualificacao_os_ids": [(3, os.id)]})
        self.assertFalse(so.qualificacao_os_ids)
        # Adiciona linha nova para re-trigger (nova linha não processada)
        so.write({"order_line": [(0, 0, {
            "product_id": self.product_qo.id,
            "product_uom_qty": 1,
            "price_unit": 1200,
            "equipment_id": self.equip2.id,
            "qualification_type": "operational",
            "is_qualificacao_managed": True,
        })]})
        so.action_confirm()
        self.assertEqual(len(so.qualificacao_os_ids), 1)
        self.assertEqual(so.qualificacao_os_ids[0].name, os_name,
                         "OS orfã deve ser reutilizada pelo nome")
        self.assertEqual(so.qualificacao_os_ids[0].id, os_id,
                         "Deve ser o mesmo record, não um novo")

    # ─────────────────────────────────────────────────────────────
    # UNIQUE CONSTRAINT
    # ─────────────────────────────────────────────────────────────
    def test_os_name_unique_per_company(self):
        """Criar segunda OS com mesmo nome+empresa levanta exceção."""
        so = self._apply(do_qi=True)
        so.action_confirm()
        os = so.qualificacao_os_ids[0]
        with self.assertRaises(Exception):
            self.env["afr.qualificacao.os"].create({
                "name": os.name,
                "company_id": self.env.company.id,
            })
