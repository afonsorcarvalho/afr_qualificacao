# -*- coding: utf-8 -*-
"""Task 12 — fecho da revisão de segurança adversarial (achados 1-4).

Achado 1 (CRÍTICO): o certificado (`certificate_token`/`certificate_hash`/
`certificate_issued_at`) era gravável por write() direto — a ir.rule escopa
QUAIS registros, não QUAIS campos, e o guard de `state` no `write()` de
`afr.qualificacao` ficava mudo quando `state` não vinha no `vals`. Um Técnico
puro, na própria OS, conseguia: (1) escrever um token qualquer; (2) usar
`verify_certificate()` (RPC público, sem guard) como oráculo do hash atual;
(3) escrever esse hash + issued_at; (4) o controller público de verificação
respondia `valid=True` para uma qualificação ainda em `draft`; (5)
`action_print_certificate()` disparava o report oficial só checando o token.

Achado 2 (Importante): `_MANAGER_ONLY_STATES` é blacklist de valor-ALVO, sem
checar o estado ATUAL — um Técnico revertia `approved → in_progress`/`draft`
tanto na OS quanto na qualif, desfazendo uma aprovação do Gestor sem ele.

Achado 3 (Importante): `action_reopen` do relatório afirmava no docstring ter
guard "manager-only via view groups=", mas isso é só UI — o método não tinha
`_check_manager_only` nenhum, e o modelo não tem ir.rule. Qualquer Técnico
reabria qualquer relatório fechado via RPC direto.

Achado 4 (Importante): os guards das Tasks 9/10 (write() overrides,
`_MANAGER_ONLY_STATES`, guards de `action_done`/`action_cancel`/
`action_reset_to_draft`) não tinham cobertura de teste alguma — remover
qualquer um deles mantinha os 386 testes anteriores verdes.
"""
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


def _tecnico_fixture(cls, suffix):
    """Cria par employee/user Técnico puro + devolve (employee, user)."""
    employee = cls.env["hr.employee"].create({"name": "Téc %s" % suffix})
    user = cls.env["res.users"].create({
        "name": "Téc %s" % suffix,
        "login": "tecnico.%s.task12.test" % suffix,
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_user").id,
            cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
        ])],
    })
    employee.user_id = user.id
    return employee, user


def _manager_fixture(cls, suffix):
    return cls.env["res.users"].create({
        "name": "Gestor %s" % suffix,
        "login": "gestor.%s.task12.test" % suffix,
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_user").id,
            cls.env.ref("afr_qualificacao.group_afr_qualificacao_manager").id,
        ])],
    })


@tagged("afr_qualificacao", "task12_security", "post_install", "-at_install")
class TestCertificateForgery(AfrQualificacaoTestCommon):
    """Achado 1 (CRÍTICO) — forja de certificado por write() direto de campo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "cert")
        cls.user_manager = _manager_fixture(cls, "cert")

    def _make_os(self, tecnico_employee, **overrides):
        vals = {
            "tecnico_default_id": tecnico_employee.id if tecnico_employee else False,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    def _make_qualif(self, os_rec, **overrides):
        vals = {
            "name": "Qualif forja test",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_rec.id if os_rec else False,
        }
        vals.update(overrides)
        return self.env["afr.qualificacao"].create(vals)

    def test_tecnico_nao_forja_certificado_via_write_direto(self):
        """Reproduz a cadeia de exploração verificada na revisão de
        segurança: cada passo do write direto tem que ser bloqueado, mesmo
        que `verify_certificate()` (oráculo público) continue disponível."""
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        self.assertEqual(qualif.state, "draft")
        qualif_tec = qualif.with_user(self.user_tecnico)

        # Passo 1 do exploit original: escrever o token direto.
        with self.assertRaisesRegex(UserError, "[Cc]ertificado"):
            qualif_tec.write({"certificate_token": "a" * 32})
        self.assertFalse(qualif.certificate_token)

        # Passo 2 (oráculo): verify_certificate() não tem guard — permanece
        # assim (fora do escopo desta correção) — mas devolve current_hash
        # mesmo com o registro ainda em draft/sem certificado.
        current_hash = qualif_tec.verify_certificate()["current_hash"]
        self.assertTrue(current_hash)

        # Passo 3: escrever hash + issued_at usando o hash "vazado" — bloqueado.
        with self.assertRaisesRegex(UserError, "[Cc]ertificado"):
            qualif_tec.write({
                "certificate_hash": current_hash,
                "certificate_issued_at": fields.Datetime.now(),
            })
        self.assertFalse(qualif.certificate_hash)
        self.assertFalse(qualif.certificate_issued_at)

        # Passo 5: sem certificado emitido, a impressão continua bloqueada.
        with self.assertRaises(UserError):
            qualif_tec.action_print_certificate()

    def test_tecnico_nao_forja_apenas_certificate_hash(self):
        """Cada campo isolado tem que ser rejeitado, não só a combinação."""
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        with self.assertRaisesRegex(UserError, "[Cc]ertificado"):
            qualif.with_user(self.user_tecnico).write({
                "certificate_hash": "b" * 64,
            })
        self.assertFalse(qualif.certificate_hash)

    def test_tecnico_nao_forja_apenas_certificate_issued_at(self):
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        with self.assertRaisesRegex(UserError, "[Cc]ertificado"):
            qualif.with_user(self.user_tecnico).write({
                "certificate_issued_at": fields.Datetime.now(),
            })
        self.assertFalse(qualif.certificate_issued_at)

    def test_write_direto_bloqueado_mesmo_gravando_outro_campo_junto(self):
        """O guard tem que disparar mesmo quando o vals mistura um campo de
        certificado com um campo legítimo — não pode ser contornado
        escondendo o campo sensível dentro de um write "normal"."""
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        with self.assertRaisesRegex(UserError, "[Cc]ertificado"):
            qualif.with_user(self.user_tecnico).write({
                "name": "Nome legítimo",
                "certificate_token": "c" * 32,
            })
        self.assertFalse(qualif.certificate_token)
        # nem o campo legítimo foi gravado — write() inteiro deve abortar
        self.assertNotEqual(qualif.name, "Nome legítimo")

    def test_gestor_emite_certificado_de_verdade_via_action_mark_approved(self):
        """Guarda de regressão do `sudo()` dentro de `_issue_certificate`:
        a emissão legítima (Gestor aprovando) continua funcionando —
        token/hash/issued_at populados — apesar do write() direto estar
        agora bloqueado para todo mundo que não seja `env.su`."""
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        qualif.with_user(self.user_manager).action_mark_approved()
        self.assertEqual(qualif.state, "approved")
        self.assertTrue(qualif.certificate_token)
        self.assertEqual(len(qualif.certificate_token), 32)
        self.assertTrue(qualif.certificate_hash)
        self.assertEqual(len(qualif.certificate_hash), 64)
        self.assertTrue(qualif.certificate_issued_at)

    def test_action_print_certificate_exige_state_approved(self):
        """Endurecimento secundário: mesmo com token válido (emitido
        legitimamente), a impressão exige `state == 'approved'` — cobre o
        cenário do Achado 2 (reversão de estado) onde o token/hash
        continuam no registro após um `approved → in_progress` indevido."""
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        qualif.action_mark_approved()
        self.assertTrue(qualif.certificate_token)
        # Reverte o estado via sudo (simula o cenário pós-Achado-2, sem
        # depender da própria correção do Achado 2 para montar o fixture)
        qualif.write({"state": "in_progress"})
        with self.assertRaises(UserError):
            qualif.action_print_certificate()

    def test_controller_publico_nao_valida_certificado_fora_de_approved(self):
        """Endurecimento secundário no controller público: um registro cujo
        certificado foi emitido mas cujo `state` não é mais `approved` não
        pode responder `valid=True` — neutraliza o oráculo residual.

        `_resolve_public_status` foi extraída como função de módulo
        justamente para ser testável sem montar um contexto HTTP/request
        real (a rota em si só é um wrapper fino em volta dela)."""
        from odoo.addons.afr_qualificacao.controllers.main import (
            _resolve_public_status,
        )
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        qualif.action_mark_approved()
        qualif.write({"state": "in_progress"})
        # `state` faz parte do snapshot — revertê-lo já quebra o hash
        # sozinho (ver `test_certificado_de_qualif_revertida_verifica_como_
        # tampered`). Pra provar o valor incremental do check `state ==
        # 'approved'` (2ª camada de defesa, independente do hash), usa
        # `sudo()` DE PROPÓSITO para contornar o guard do Finding 1 (que
        # bloquearia este write pra qualquer usuário não-su) e forçar o
        # hash a bater com o snapshot ATUAL — simula o único jeito de obter
        # "hash bate, mas state != approved", provando que o check de
        # `state` é uma camada independente, não redundante com o hash.
        fresh_hash = qualif._compute_certificate_hash()
        qualif.sudo().write({"certificate_hash": fresh_hash})

        status, result = _resolve_public_status(qualif)
        self.assertTrue(
            result["valid"], "Hash foi forçado a bater com o snapshot atual"
        )
        self.assertEqual(
            status, "tampered",
            "state != approved deve barrar mesmo com hash batendo",
        )


@tagged("afr_qualificacao", "task12_security", "post_install", "-at_install")
class TestStateReversionGuard(AfrQualificacaoTestCommon):
    """Achado 2 (Importante) — reversão de estado de registros já
    aprovados/concluídos sem envolvimento do Gestor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "revert")
        cls.user_manager = _manager_fixture(cls, "revert")

    def _make_os(self, tecnico_employee, **overrides):
        vals = {
            "tecnico_default_id": tecnico_employee.id if tecnico_employee else False,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    def _make_qualif(self, os_rec, **overrides):
        vals = {
            "name": "Qualif revert test",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_rec.id if os_rec else False,
        }
        vals.update(overrides)
        return self.env["afr.qualificacao"].create(vals)

    # ───────── OS ─────────
    def test_tecnico_nao_reverte_os_approved_para_in_progress(self):
        os_rec = self._make_os(self.employee_tecnico)
        os_rec.write({"state": "approved"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).write({"state": "in_progress"})
        self.assertEqual(os_rec.state, "approved")

    def test_tecnico_nao_reverte_os_done_para_approved(self):
        os_rec = self._make_os(self.employee_tecnico)
        os_rec.write({"state": "done"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).write({"state": "approved"})
        self.assertEqual(os_rec.state, "done")

    def test_manager_pode_reverter_os_approved(self):
        """Guarda contra over-tightening: Gestor continua conseguindo."""
        os_rec = self._make_os(self.employee_tecnico)
        os_rec.write({"state": "approved"})
        os_rec.with_user(self.user_manager).write({"state": "in_progress"})
        self.assertEqual(os_rec.state, "in_progress")

    # ───────── Qualificação ─────────
    def test_tecnico_nao_reverte_qualif_approved_para_in_progress(self):
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        qualif.write({"state": "approved"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            qualif.with_user(self.user_tecnico).write({"state": "in_progress"})
        self.assertEqual(qualif.state, "approved")

    def test_tecnico_nao_reverte_qualif_approved_para_draft(self):
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        qualif.write({"state": "approved"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            qualif.with_user(self.user_tecnico).write({"state": "draft"})
        self.assertEqual(qualif.state, "approved")

    def test_manager_pode_reverter_qualif_approved(self):
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        qualif.write({"state": "approved"})
        qualif.with_user(self.user_manager).write({"state": "in_progress"})
        self.assertEqual(qualif.state, "in_progress")

    def test_certificado_de_qualif_revertida_verifica_como_tampered(self):
        """Fato atenuante documentado no achado: mesmo antes desta correção,
        `state` já fazia parte do `_snapshot_for_hash` — uma reversão (feita
        por sudo/admin para montar o fixture, simulando o mundo pré-fix)
        invalida o hash. A cadeia de certificado segura; o defeito era só de
        workflow/auditoria."""
        os_propria = self._make_os(self.employee_tecnico)
        qualif = self._make_qualif(os_propria)
        qualif.action_mark_approved()
        qualif.write({"state": "in_progress"})  # sudo/admin — simula pós-bypass
        result = qualif.verify_certificate()
        self.assertFalse(result["valid"])


@tagged("afr_qualificacao", "task12_security", "post_install", "-at_install")
class TestRelatorioReopenGuard(AfrQualificacaoTestCommon):
    """Achado 3 (Importante) — `action_reopen` sem guard servidor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "reopen")
        cls.user_manager = _manager_fixture(cls, "reopen")

    def _make_relatorio_done(self):
        os_rec = self.env["afr.qualificacao.os"].create({
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        })
        rel = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os_rec.id,
            "data_inicio": datetime(2026, 7, 1, 8, 0, 0),
            "data_fim": datetime(2026, 7, 1, 12, 0, 0),
            "tecnico_ids": [(6, 0, [self.employee_tecnico.id])],
            "descricao": "Relatório fechado",
        })
        rel.action_done()
        self.assertEqual(rel.state, "done")
        return rel

    def test_tecnico_nao_pode_reabrir_relatorio_de_outra_os(self):
        """Cenário mais grave do achado: nem sequer precisa ser a própria OS
        — o modelo não tem ir.rule nenhuma, então qualquer Técnico atinge
        qualquer relatório fechado do banco."""
        outro_employee, _outro_user = _tecnico_fixture(self, "reopen_outro")
        rel = self._make_relatorio_done()
        self.assertNotEqual(rel.os_id.tecnico_default_id, outro_employee)
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            rel.with_user(self.user_tecnico).action_reopen()
        self.assertEqual(rel.state, "done")

    def test_manager_pode_reabrir_relatorio(self):
        rel = self._make_relatorio_done()
        rel.with_user(self.user_manager).action_reopen()
        self.assertEqual(rel.state, "draft")


@tagged("afr_qualificacao", "task12_security", "post_install", "-at_install")
class TestManagerGuardCoverageGaps(AfrQualificacaoTestCommon):
    """Achado 4 (Importante) — cobertura zero dos guards das Tasks 9/10.

    Cada teste aqui é escrito para quebrar se o guard correspondente for
    removido/enfraquecido — a lacuna que a revisão apontou."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "gap")
        cls.user_manager = _manager_fixture(cls, "gap")

    def _make_os(self, **overrides):
        vals = {
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    PNG_1X1 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
        "h6FO1AAAAABJRU5ErkJggg=="
    )

    def test_tecnico_nao_pode_concluir_os_action_done(self):
        os_rec = self._make_os()
        os_rec.write({
            "state": "approved",
            "signature_technician": self.PNG_1X1,
        })
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).action_done()
        self.assertEqual(os_rec.state, "approved")

    def test_tecnico_nao_pode_cancelar_os_action_cancel(self):
        os_rec = self._make_os()
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).action_cancel()
        self.assertNotEqual(os_rec.state, "cancelled")

    def test_tecnico_nao_pode_resetar_os_para_draft_action_reset_to_draft(self):
        os_rec = self._make_os()
        os_rec.write({"state": "cancelled"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).action_reset_to_draft()
        self.assertEqual(os_rec.state, "cancelled")

    def test_tecnico_nao_pode_escrever_state_cancelled_direto_na_os(self):
        """Exercita `_MANAGER_ONLY_STATES` diretamente via write() — sem
        este teste, esvaziar o frozenset mantinha a suíte inteira verde."""
        os_rec = self._make_os()
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).write({"state": "cancelled"})
        self.assertNotEqual(os_rec.state, "cancelled")

    def test_tecnico_nao_pode_escrever_state_cancelled_direto_na_qualif(self):
        Qualif = self.env["afr.qualificacao"]
        os_rec = self._make_os()
        qualif = Qualif.create({
            "name": "Qualif gap test",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_rec.id,
        })
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            qualif.with_user(self.user_tecnico).write({"state": "cancelled"})
        self.assertNotEqual(qualif.state, "cancelled")

    def test_pwa_action_start_daily_relatorio_continua_funcionando(self):
        """Guarda de regressão da feature inteira: a transição
        `scheduled → in_progress` feita pelo PWA do técnico padrão não pode
        quebrar por causa de nenhum dos guards adicionados nesta task."""
        os_rec = self._make_os()
        os_rec.write({"state": "scheduled"})
        rel_id = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio()
        self.assertEqual(os_rec.state, "in_progress")
        rel = self.env["afr.qualificacao.os.relatorio"].browse(rel_id)
        self.assertTrue(rel.exists())
        self.assertEqual(rel.state, "draft")
