# -*- coding: utf-8 -*-
"""Task 13 — fecho do guard "meio instalado" encontrado pela revisão
adversarial seguinte à Task 12: os guards de `write()` (Task 10/12) não têm
equivalente em `create()`.

Achado 1 (CRÍTICO): `afr.qualificacao` não tem override de `create()`. O
grupo Usuário (`group_afr_qualificacao_user`, `create=1` em
`ir.model.access.csv`) — que o Técnico puro NÃO tem (`create=0`) — conseguia
`create({..., 'state': 'approved', 'certificate_token': ..., 'certificate_hash':
..., 'certificate_issued_at': ...})` e forjar um certificado que o endpoint
público `/qualificacao/verify/<token>` validava como genuíno, sem nunca
passar por `_issue_certificate`/`action_mark_approved`.

Achado 2 (CRÍTICO): `create({'state': 'approved'})` pula `_MANAGER_ONLY_STATES`
inteiramente em ambos os modelos — nasce já aprovada/concluída/cancelada sem
o Gestor.

Achado 3 (Importante): `_STATE_LOCKED_ONCE_REACHED` não cobria `rejected`
(qualif) nem `cancelled` (OS/qualif), e `action_start()` não tinha nenhuma
precondição de estado — um Técnico desfazia uma reprovação/cancelamento do
Gestor via `write()` direto ou via `action_start()`.
"""
from datetime import datetime

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


def _tecnico_fixture(cls, suffix):
    """Cria par employee/user Técnico puro (create=0 em ambos os modelos)."""
    employee = cls.env["hr.employee"].create({"name": "Téc %s" % suffix})
    user = cls.env["res.users"].create({
        "name": "Téc %s" % suffix,
        "login": "tecnico.%s.task13.test" % suffix,
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_user").id,
            cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
        ])],
    })
    employee.user_id = user.id
    return employee, user


def _usuario_fixture(cls, suffix):
    """Cria user no grupo Usuário — NÃO Gestor, mas com `create=1` em
    `afr.qualificacao`/`afr.qualificacao.os` (ir.model.access.csv linhas
    2/41). É o ator dos Achados 1/2: quem cria os registros no fluxo normal
    (wizards/OS), diferente do Técnico puro (create=0)."""
    return cls.env["res.users"].create({
        "name": "Usuário %s" % suffix,
        "login": "usuario.%s.task13.test" % suffix,
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_user").id,
            cls.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
        ])],
    })


def _manager_fixture(cls, suffix):
    return cls.env["res.users"].create({
        "name": "Gestor %s" % suffix,
        "login": "gestor.%s.task13.test" % suffix,
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_user").id,
            cls.env.ref("afr_qualificacao.group_afr_qualificacao_manager").id,
        ])],
    })


@tagged("afr_qualificacao", "task13_security", "post_install", "-at_install")
class TestCreateCertificateForgery(AfrQualificacaoTestCommon):
    """Achado 1 (CRÍTICO) — forja de certificado via create() direto."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "c13cert")
        cls.user_usuario = _usuario_fixture(cls, "c13cert")
        cls.user_manager = _manager_fixture(cls, "c13cert")

    def _make_os(self, **overrides):
        vals = {
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    def test_usuario_nao_forja_certificado_via_create(self):
        """Reproduz o probe da revisão: create() direto com state=approved
        + campos do certificado, feito por um Usuário (create=1, não Gestor).
        Sem o guard, isso nascia com certificado válido no oráculo público."""
        os_propria = self._make_os()
        Qualif = self.env["afr.qualificacao"].with_user(self.user_usuario)
        with self.assertRaisesRegex(UserError, "[Cc]ertificado"):
            Qualif.create({
                "name": "Qualif Forjada C13",
                "equipment_id": self.equip1.id,
                "qualification_type": "installation",
                "company_id": self.company.id,
                "os_id": os_propria.id,
                "state": "approved",
                "certificate_token": "f" * 32,
                "certificate_hash": "a" * 64,
                "certificate_issued_at": fields.Datetime.now(),
            })
        self.assertFalse(
            self.env["afr.qualificacao"].search(
                [("name", "=", "Qualif Forjada C13")]
            ),
            "nenhum registro com os valores forjados pode existir após o raise",
        )

    def test_gestor_emite_certificado_de_verdade_via_action_mark_approved(self):
        """Regressão do caminho legítimo (sudo() em `_issue_certificate`):
        precisa continuar funcionando depois do novo guard de `create()`."""
        os_propria = self._make_os()
        qualif = self.env["afr.qualificacao"].create({
            "name": "Qualif C13 Emissão",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_propria.id,
        })
        qualif.with_user(self.user_manager).action_mark_approved()
        self.assertEqual(qualif.state, "approved")
        self.assertTrue(qualif.certificate_token)
        self.assertTrue(qualif.certificate_hash)
        self.assertTrue(qualif.certificate_issued_at)


@tagged("afr_qualificacao", "task13_security", "post_install", "-at_install")
class TestCreateManagerOnlyState(AfrQualificacaoTestCommon):
    """Achado 2 (CRÍTICO) — create() pulando _MANAGER_ONLY_STATES."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "c13state")
        cls.user_usuario = _usuario_fixture(cls, "c13state")
        cls.user_manager = _manager_fixture(cls, "c13state")

    def _os_vals(self, **overrides):
        vals = {
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return vals

    def _qualif_vals(self, os_rec, **overrides):
        vals = {
            "name": "Qualif C13 State",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_rec.id,
        }
        vals.update(overrides)
        return vals

    # ───────── Usuário não-Gestor NÃO consegue nascer em estado manager-only ─────────
    def test_usuario_nao_cria_os_ja_approved(self):
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            self.env["afr.qualificacao.os"].with_user(self.user_usuario).create(
                self._os_vals(state="approved")
            )

    def test_usuario_nao_cria_qualif_ja_approved(self):
        os_rec = self.env["afr.qualificacao.os"].create(self._os_vals())
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            self.env["afr.qualificacao"].with_user(self.user_usuario).create(
                self._qualif_vals(os_rec, state="approved")
            )

    # ───────── Guarda contra over-tightening: draft normal continua ok ─────────
    def test_usuario_cria_os_draft_normal(self):
        os_rec = self.env["afr.qualificacao.os"].with_user(self.user_usuario).create(
            self._os_vals()
        )
        self.assertEqual(os_rec.state, "draft")

    def test_usuario_cria_qualif_draft_normal(self):
        os_rec = self.env["afr.qualificacao.os"].create(self._os_vals())
        qualif = self.env["afr.qualificacao"].with_user(self.user_usuario).create(
            self._qualif_vals(os_rec)
        )
        self.assertEqual(qualif.state, "draft")

    # ───────── Gestor continua conseguindo criar em estado manager-only ─────────
    def test_gestor_cria_os_ja_cancelled(self):
        os_rec = self.env["afr.qualificacao.os"].with_user(self.user_manager).create(
            self._os_vals(state="cancelled")
        )
        self.assertEqual(os_rec.state, "cancelled")

    def test_gestor_cria_qualif_ja_approved_sem_campos_certificado(self):
        """Sem campos de certificado: o guard de campo (Achado 1) não entra
        em jogo, só o de `state` — que o Gestor pode passar."""
        os_rec = self.env["afr.qualificacao.os"].create(self._os_vals())
        qualif = self.env["afr.qualificacao"].with_user(self.user_manager).create(
            self._qualif_vals(os_rec, state="approved")
        )
        self.assertEqual(qualif.state, "approved")

    # ───────── Regressão: sequence da OS continua sendo atribuída ─────────
    def test_sequence_os_continua_atribuida_apos_guard(self):
        os_rec = self.env["afr.qualificacao.os"].create(self._os_vals())
        self.assertTrue(os_rec.name)
        self.assertNotEqual(os_rec.name, "Novo")


@tagged("afr_qualificacao", "task13_security", "post_install", "-at_install")
class TestStateLockGapsAndActionStart(AfrQualificacaoTestCommon):
    """Achado 3 (Importante) — lock set incompleto + action_start() sem
    precondição de estado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "c13lock")
        cls.user_manager = _manager_fixture(cls, "c13lock")

    def _make_os(self, **overrides):
        vals = {
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    def _make_qualif(self, os_rec, **overrides):
        vals = {
            "name": "Qualif C13 Lock",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_rec.id,
        }
        vals.update(overrides)
        return self.env["afr.qualificacao"].create(vals)

    # ───────── OS cancelled trava (novo) ─────────
    def test_tecnico_nao_reverte_os_cancelled_para_scheduled(self):
        os_rec = self._make_os()
        os_rec.write({"state": "cancelled"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).write({"state": "scheduled"})
        self.assertEqual(os_rec.state, "cancelled")

    def test_tecnico_nao_reverte_os_cancelled_para_in_progress(self):
        os_rec = self._make_os()
        os_rec.write({"state": "cancelled"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).write({"state": "in_progress"})
        self.assertEqual(os_rec.state, "cancelled")

    # ───────── Qualif rejected trava (novo) ─────────
    def test_tecnico_nao_reverte_qualif_rejected_para_in_progress(self):
        os_propria = self._make_os()
        qualif = self._make_qualif(os_propria)
        qualif.write({"state": "rejected"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            qualif.with_user(self.user_tecnico).write({"state": "in_progress"})
        self.assertEqual(qualif.state, "rejected")

    # ───────── action_start() precisa de state == draft ─────────
    def test_tecnico_nao_reinicia_qualif_rejected_via_action_start(self):
        os_propria = self._make_os()
        qualif = self._make_qualif(os_propria)
        qualif.write({"state": "rejected"})
        with self.assertRaisesRegex(UserError, "rascunho"):
            qualif.with_user(self.user_tecnico).action_start()
        self.assertEqual(qualif.state, "rejected")

    def test_tecnico_nao_reinicia_qualif_cancelled_via_action_start(self):
        os_propria = self._make_os()
        qualif = self._make_qualif(os_propria)
        qualif.write({"state": "cancelled"})
        with self.assertRaisesRegex(UserError, "rascunho"):
            qualif.with_user(self.user_tecnico).action_start()
        self.assertEqual(qualif.state, "cancelled")

    def test_qualif_draft_ainda_inicia_via_action_start(self):
        """Guarda contra over-tightening: draft → in_progress continua ok."""
        os_propria = self._make_os()
        qualif = self._make_qualif(os_propria)
        qualif.with_user(self.user_tecnico).action_start()
        self.assertEqual(qualif.state, "in_progress")

    # ───────── Regressão: caminho PWA continua intacto ─────────
    def test_pwa_action_start_daily_relatorio_continua_funcionando(self):
        os_rec = self._make_os()
        os_rec.write({"state": "scheduled"})
        rel_id = os_rec.with_user(
            self.user_tecnico
        ).action_start_daily_relatorio()
        self.assertEqual(os_rec.state, "in_progress")
        rel = self.env["afr.qualificacao.os.relatorio"].browse(rel_id)
        self.assertTrue(rel.exists())
        self.assertEqual(rel.state, "draft")
