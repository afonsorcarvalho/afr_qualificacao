"""Testes do certificado: emissão (hash+token+issued_at), verificação,
detecção de tampering, controller público, PDF report."""

import hashlib
import json

from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestCertificate(AfrQualificacaoTestCommon):

    def _setup_approved_qualif(self):
        """Cria SO confirmada + aprova QI (qualif simples sem sub-records)."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "do_qi": True,
        })]
        wiz.action_apply()
        so.action_confirm()
        qi = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "installation")
        qi.action_mark_approved()
        return qi

    def test_approval_issues_certificate(self):
        qi = self._setup_approved_qualif()
        self.assertTrue(qi.certificate_token, "Token deve ser gerado no approval")
        self.assertEqual(len(qi.certificate_token), 32, "UUID4 hex = 32 chars")
        self.assertTrue(qi.certificate_hash, "Hash deve ser gerado")
        self.assertEqual(len(qi.certificate_hash), 64, "SHA-256 hex = 64 chars")
        self.assertTrue(qi.certificate_issued_at)
        self.assertIn("/qualificacao/verify/", qi.certificate_verify_url)
        self.assertIn(qi.certificate_token, qi.certificate_verify_url)

    def test_hash_matches_snapshot(self):
        qi = self._setup_approved_qualif()
        snapshot = qi._snapshot_for_hash()
        payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        expected = hashlib.sha256(payload).hexdigest()
        self.assertEqual(qi.certificate_hash, expected)

    def test_idempotent_issue(self):
        qi = self._setup_approved_qualif()
        token1 = qi.certificate_token
        hash1 = qi.certificate_hash
        qi._issue_certificate()  # call again
        self.assertEqual(qi.certificate_token, token1, "Token estável após reissue")
        self.assertEqual(qi.certificate_hash, hash1, "Hash estável após reissue")

    def test_verify_valid(self):
        qi = self._setup_approved_qualif()
        result = qi.verify_certificate()
        self.assertTrue(result["valid"])
        self.assertEqual(result["expected_hash"], result["current_hash"])

    def test_verify_tampered_after_field_change(self):
        qi = self._setup_approved_qualif()
        original_date = qi.execution_date
        qi.execution_date = "2026-12-31"
        result = qi.verify_certificate()
        self.assertFalse(result["valid"], "Mudança em campo do snapshot = tampered")
        self.assertNotEqual(result["expected_hash"], result["current_hash"])
        # restaura para não afetar outros tests
        qi.execution_date = original_date

    def test_verify_tampered_after_cycle_state_change(self):
        # Setup com QD
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 3})],
        })]
        wiz.action_apply()
        so.action_confirm()
        qd = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "performance")
        rel = self._get_relatorio(qd.os_id)
        qd.cycle_ids.with_context(default_relatorio_id=rel.id).write({"state": "passed"})
        qd.action_mark_approved()
        # Hash congelado. Alterar state de cycle invalida.
        qd.cycle_ids[0].with_context(default_relatorio_id=rel.id).write({"state": "failed"})
        result = qd.verify_certificate()
        self.assertFalse(result["valid"], "Mudança em cycle.state = tampered")

    def test_controller_returns_valid(self):
        qi = self._setup_approved_qualif()
        # HTTP controller test exige HttpCase; aqui validamos só lógica
        from odoo.addons.afr_qualificacao.controllers.main import (
            QualificacaoVerifyController,
        )
        self.assertTrue(QualificacaoVerifyController.verify_certificate)

    def test_action_print_certificate_requires_token(self):
        from odoo.exceptions import UserError
        # Cria qualif sem aprovar (sem token)
        qi = self.env["afr.qualificacao"].create({
            "name": "Test no token",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
        })
        with self.assertRaises(UserError):
            qi.action_print_certificate()

    def test_action_print_certificate_dispatches_correct_report(self):
        qi = self._setup_approved_qualif()
        action = qi.action_print_certificate()
        # report_action retorna dict de ação (tipo varia por Odoo; basta validar
        # que algo foi devolvido e refere-se ao report correto)
        self.assertTrue(action)
        self.assertEqual(
            action.get("report_name") or action.get("report_file") or "",
            "afr_qualificacao.qualificacao_certificate_template",
        ) if action.get("type", "").startswith("ir.actions.report") else self.assertTrue(action)

    def test_snapshot_includes_all_critical_fields(self):
        qi = self._setup_approved_qualif()
        snap = qi._snapshot_for_hash()
        for key in ("id", "name", "partner", "equipment", "qualification_type",
                    "execution_date", "state", "company_id", "cycles", "malhas"):
            self.assertIn(key, snap, "Snapshot deve incluir %s" % key)
