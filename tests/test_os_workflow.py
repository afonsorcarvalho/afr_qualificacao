# -*- coding: utf-8 -*-
"""Testes do workflow da OS de Qualificação (F1).

Transitions:
    draft → scheduled → in_progress → in_approved → approved → done
    qualquer → cancelled (exceto done)
    cancelled → draft (reset)
"""
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "os_workflow", "post_install", "-at_install")
class TestQualificacaoOsWorkflow(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tecnico = cls.env["hr.employee"].create({"name": "Técnico Teste"})
        cls.approver = cls.env["res.users"].create({
            "name": "Aprovador Teste",
            "login": "aprovador.os.test",
            "groups_id": [(6, 0, [
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_manager").id,
            ])],
        })

    def _make_os(self, **overrides):
        vals = {
            "tecnico_default_id": self.tecnico.id,
            "approver_id": self.approver.id,
            "date_planned_start": datetime.now(),
            "date_planned_end": datetime.now() + timedelta(hours=4),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    # ─────────────────────────────────────────────────────────────
    # SEQUENCE
    # ─────────────────────────────────────────────────────────────
    def test_create_assigns_sequence(self):
        os = self._make_os()
        self.assertTrue(os.name.startswith("QOS"))
        self.assertNotEqual(os.name, "Novo")

    def test_create_two_increments_sequence(self):
        os1 = self._make_os()
        os2 = self._make_os()
        self.assertNotEqual(os1.name, os2.name)

    # ─────────────────────────────────────────────────────────────
    # TRANSITIONS
    # ─────────────────────────────────────────────────────────────
    def test_schedule_requires_qualifs(self):
        os = self._make_os()
        # OS sem qualifs vinculadas → não pode agendar
        with self.assertRaisesRegex(UserError, "sem qualificações"):
            os.action_schedule()

    def test_schedule_requires_planned_dates(self):
        os = self._make_os(
            date_planned_start=False, date_planned_end=False,
        )
        # Adiciona fake qualif vinculada
        self._attach_dummy_qualif(os)
        with self.assertRaisesRegex(UserError, "datas planejadas"):
            os.action_schedule()

    def test_schedule_requires_tecnico_or_responsible(self):
        os = self._make_os(tecnico_default_id=False)
        self._attach_dummy_qualif(os, responsible=False)
        with self.assertRaisesRegex(UserError, "técnico padrão"):
            os.action_schedule()

    def test_schedule_success(self):
        os = self._make_os()
        self._attach_dummy_qualif(os)
        os.action_schedule()
        self.assertEqual(os.state, "scheduled")

    def test_start_execution_advances_state(self):
        os = self._make_os()
        self._attach_dummy_qualif(os)
        os.action_schedule()
        action = os.action_start_execution()
        self.assertEqual(os.state, "in_progress")
        # Retorna action de wizard
        self.assertEqual(action["res_model"], "afr.qualificacao.os.relatorio.wizard")

    def test_request_approval_blocks_when_relatorio_draft(self):
        os = self._make_os()
        self._attach_dummy_qualif(os)
        os.action_schedule()
        os.write({"state": "in_progress"})
        # Cria relatório draft
        self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os.id,
            "data_inicio": datetime.now(),
            "data_fim": datetime.now() + timedelta(hours=1),
            "tecnico_ids": [(6, 0, [self.tecnico.id])],
            "descricao": "Em andamento",
        })
        with self.assertRaisesRegex(UserError, "rascunho"):
            os.action_request_approval()

    def test_request_approval_success(self):
        os = self._make_os()
        self._attach_dummy_qualif(os)
        os.write({"state": "in_progress"})
        os.action_request_approval()
        self.assertEqual(os.state, "in_approved")

    def test_done_requires_signature(self):
        os = self._make_os()
        self._attach_dummy_qualif(os, qualif_state="approved")
        os.write({"state": "approved"})
        with self.assertRaisesRegex(UserError, "ssinatura"):
            os.action_done()

    def test_done_requires_qualifs_approved(self):
        # OS state=approved mas qualif state=draft → deve bloquear done
        os = self._make_os()
        # Assinatura presente (1x1 px transparente PNG)
        os.write({
            "state": "approved",
            "signature_technician": (
                b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
                b"DUlEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
            ),
        })
        self._attach_dummy_qualif(os, qualif_state="draft")
        with self.assertRaisesRegex(UserError, "não aprovadas"):
            os.action_done()

    def test_cancel_blocks_done(self):
        os = self._make_os()
        self._attach_dummy_qualif(os)
        os.write({"state": "done"})
        with self.assertRaisesRegex(UserError, "concluída"):
            os.action_cancel()

    def test_cancel_from_draft(self):
        os = self._make_os()
        os.action_cancel()
        self.assertEqual(os.state, "cancelled")

    def test_reset_to_draft_only_from_cancelled(self):
        os = self._make_os()
        with self.assertRaisesRegex(UserError, "cancelada"):
            os.action_reset_to_draft()

    def test_reset_to_draft_from_cancelled(self):
        os = self._make_os()
        os.action_cancel()
        os.action_reset_to_draft()
        self.assertEqual(os.state, "draft")

    # ─────────────────────────────────────────────────────────────
    # CONSTRAINTS
    # ─────────────────────────────────────────────────────────────
    def test_planned_dates_constraint(self):
        with self.assertRaisesRegex(ValidationError, "início planejado"):
            self._make_os(
                date_planned_start=datetime.now() + timedelta(hours=2),
                date_planned_end=datetime.now(),
            )

    # ─────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────
    def _attach_dummy_qualif(self, os, qualif_state="draft", responsible=True):
        """Cria afr.qualificacao mínima vinculada à OS (sem SO/cycles)."""
        Qualif = self.env["afr.qualificacao"]
        vals = {
            "name": "QualifTest-%s" % os.id,
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "os_id": os.id,
            "company_id": os.company_id.id,
        }
        if responsible:
            vals["responsible_id"] = self.env.uid
        q = Qualif.create(vals)
        if qualif_state != "draft":
            q.write({"state": qualif_state})
        return q
