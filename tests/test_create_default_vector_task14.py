# -*- coding: utf-8 -*-
"""Task 14 — fecho do vetor de DEFAULTS no `create()` (revisão adversarial
posterior à Task 13).

A Task 13 guardou o `create()` inspecionando o `vals_list` RECEBIDO. Mas o
Odoo aplica defaults DEPOIS do override, dentro do próprio
`super().create()` (`BaseModel.create` → `_prepare_create_values` →
`_add_missing_default_values` → `default_get`), e `default_get` honra
`context['default_<field>']` e linhas de `ir.default` para QUALQUER campo,
inclusive os readonly. `self.env.su` não é a única fuga — dois vetores
RPC-alcançáveis (grupo `group_afr_qualificacao_user`, `env.su == False`)
sobrevivem ao guard da Task 13:

Achado 1 (CRÍTICO) — vetor de contexto: `Q.with_context(
default_state='approved', default_certificate_token=..., ...).create(...)`
nasce aprovada com certificado forjado, sem nenhum desses campos no
`vals` — o guard pré-`super()` fica cego porque olha só o `vals` recebido.
Mesmo truque em `afr.qualificacao.os` com `default_state='approved'`.

Achado 2 (CRÍTICO) — vetor `ir.default`, sem tocar em contexto nenhum: o
grupo Usuário tem `create`/`write` completo em `ir.default` (base concede a
Internal User), então o atacante grava `ir.default.set('afr.qualificacao',
'state', 'approved')` uma vez, e todo `create({...})` seguinte (bare, sem
contexto) já nasce aprovado.

Correção: guard pós-`super().create()` sobre os valores EFETIVOS dos
registros criados (`record.state`/`record.certificate_*`), agnóstico ao
vetor — cobre contexto, `ir.default`, ou qualquer default futuro. O
pré-check da Task 13 é mantido (erro mais claro no caso comum de vals
explícito), mas quem realmente fecha o buraco é o pós-check.
"""
from datetime import datetime

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


def _tecnico_fixture(cls, suffix):
    employee = cls.env["hr.employee"].create({"name": "Téc %s" % suffix})
    user = cls.env["res.users"].create({
        "name": "Téc %s" % suffix,
        "login": "tecnico.%s.task14.test" % suffix,
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_user").id,
            cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
        ])],
    })
    employee.user_id = user.id
    return employee, user


def _usuario_fixture(cls, suffix):
    """Grupo Usuário: NÃO Gestor, mas com `create=1` em ambos os modelos —
    é o ator dos dois vetores desta task (não o Técnico puro, create=0)."""
    return cls.env["res.users"].create({
        "name": "Usuário %s" % suffix,
        "login": "usuario.%s.task14.test" % suffix,
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_user").id,
            cls.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
        ])],
    })


def _manager_fixture(cls, suffix):
    return cls.env["res.users"].create({
        "name": "Gestor %s" % suffix,
        "login": "gestor.%s.task14.test" % suffix,
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_user").id,
            cls.env.ref("afr_qualificacao.group_afr_qualificacao_manager").id,
        ])],
    })


@tagged("afr_qualificacao", "task14_security", "post_install", "-at_install")
class TestContextVectorForgery(AfrQualificacaoTestCommon):
    """Achado 1 (CRÍTICO) — `with_context(default_<field>=...)` bypassando o
    guard de `create()` em ambos os modelos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "c14ctx")
        cls.user_usuario = _usuario_fixture(cls, "c14ctx")
        cls.user_manager = _manager_fixture(cls, "c14ctx")

    def _make_os(self, **overrides):
        vals = {
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    def test_usuario_nao_forja_certificado_via_default_context(self):
        """Reproduz o vetor de contexto da revisão adversarial: nenhum campo
        de certificado/state no `vals` — todos entram via
        `context['default_<field>']`, que `default_get` aplica dentro do
        `super().create()`, depois do guard pré-check já ter passado."""
        os_propria = self._make_os()
        Qualif = self.env["afr.qualificacao"].with_user(self.user_usuario)
        with self.assertRaisesRegex(UserError, "[Cc]ertificado"):
            # `cr.savepoint()` reproduz a fronteira de rollback de uma
            # chamada RPC real — sem ela, o INSERT feito dentro do
            # `super().create()` (antes do raise pós-check) fica visível
            # para buscas dentro desta mesma transação de teste.
            with self.cr.savepoint():
                Qualif.with_context(
                    default_state="approved",
                    default_certificate_token="f" * 32,
                    default_certificate_hash="a" * 64,
                    default_certificate_issued_at=fields.Datetime.now(),
                ).create({
                    "name": "Qualif Forjada C14 Contexto",
                    "equipment_id": self.equip1.id,
                    "qualification_type": "installation",
                    "company_id": self.company.id,
                    "os_id": os_propria.id,
                })
        self.assertFalse(
            self.env["afr.qualificacao"].search(
                [("name", "=", "Qualif Forjada C14 Contexto")]
            ),
            "nenhum registro com os valores forjados pode sobreviver ao rollback",
        )

    def test_usuario_nao_forja_state_via_default_context_isolado(self):
        """Mesmo vetor, sem os campos de certificado — prova que o guard de
        `state` sozinho (sem o de certificado) também é vals-independente."""
        os_propria = self._make_os()
        Qualif = self.env["afr.qualificacao"].with_user(self.user_usuario)
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            with self.cr.savepoint():
                Qualif.with_context(default_state="approved").create({
                    "name": "Qualif Forjada C14 State Ctx",
                    "equipment_id": self.equip1.id,
                    "qualification_type": "installation",
                    "company_id": self.company.id,
                    "os_id": os_propria.id,
                })
        self.assertFalse(
            self.env["afr.qualificacao"].search(
                [("name", "=", "Qualif Forjada C14 State Ctx")]
            ),
        )

    def test_usuario_nao_forja_os_ja_approved_via_default_context(self):
        """Mesmo vetor na OS: `default_state='approved'` no contexto, sem o
        campo no `vals`."""
        Os = self.env["afr.qualificacao.os"].with_user(self.user_usuario)
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            with self.cr.savepoint():
                Os.with_context(default_state="approved").create({
                    "tecnico_default_id": self.employee_tecnico.id,
                    "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
                    "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
                })
        self.assertFalse(
            self.env["afr.qualificacao.os"].search(
                [("tecnico_default_id", "=", self.employee_tecnico.id),
                 ("state", "=", "approved")]
            ),
        )


@tagged("afr_qualificacao", "task14_security", "post_install", "-at_install")
class TestIrDefaultVectorForgery(AfrQualificacaoTestCommon):
    """Achado 2 (CRÍTICO) — `ir.default` gravado pelo próprio atacante, sem
    manipular contexto nenhum: `create({...})` bare já nasce forjado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "c14ird")
        cls.user_usuario = _usuario_fixture(cls, "c14ird")

    def _make_os(self, **overrides):
        vals = {
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    def test_usuario_nao_forja_state_via_ir_default_proprio(self):
        os_propria = self._make_os()
        Qualif = self.env["afr.qualificacao"].with_user(self.user_usuario)
        # Internal User tem create/write completo em ir.default
        # (access_ir_default_group_user, base/security/ir.model.access.csv)
        # — o atacante grava o próprio default, sem sudo, sem contexto.
        self.env["ir.default"].with_user(self.user_usuario).set(
            "afr.qualificacao", "state", "approved", user_id=True
        )
        # Confirma que o vetor está de fato armado ANTES do guard entrar em
        # jogo — sem isto, um `ir.default.set` que não "pegasse" (cache,
        # escopo errado) daria um GREEN falso que não prova nada.
        self.assertEqual(
            Qualif.default_get(["state"])["state"], "approved",
            "pré-condição do teste: ir.default precisa estar realmente ativo",
        )
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            with self.cr.savepoint():
                Qualif.create({
                    "name": "Qualif Forjada C14 IrDefault State",
                    "equipment_id": self.equip1.id,
                    "qualification_type": "installation",
                    "company_id": self.company.id,
                    "os_id": os_propria.id,
                })
        self.assertFalse(
            self.env["afr.qualificacao"].search(
                [("name", "=", "Qualif Forjada C14 IrDefault State")]
            ),
        )

    def test_usuario_nao_forja_certificado_via_ir_default_proprio(self):
        os_propria = self._make_os()
        Qualif = self.env["afr.qualificacao"].with_user(self.user_usuario)
        self.env["ir.default"].with_user(self.user_usuario).set(
            "afr.qualificacao", "certificate_token", "f" * 32, user_id=True
        )
        self.assertEqual(
            Qualif.default_get(["certificate_token"])["certificate_token"],
            "f" * 32,
            "pré-condição do teste: ir.default precisa estar realmente ativo",
        )
        with self.assertRaisesRegex(UserError, "[Cc]ertificado"):
            with self.cr.savepoint():
                Qualif.create({
                    "name": "Qualif Forjada C14 IrDefault Cert",
                    "equipment_id": self.equip1.id,
                    "qualification_type": "installation",
                    "company_id": self.company.id,
                    "os_id": os_propria.id,
                })
        self.assertFalse(
            self.env["afr.qualificacao"].search(
                [("name", "=", "Qualif Forjada C14 IrDefault Cert")]
            ),
        )


@tagged("afr_qualificacao", "task14_security", "post_install", "-at_install")
class TestBatchCreateGuard(AfrQualificacaoTestCommon):
    """Regressão de cobertura: um loop que só inspecionasse `vals_list[0]`
    (armadilha comum de refactor) passaria a suíte inteira de hoje — nenhum
    teste anterior faz `create()` em lote."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "c14batch")
        cls.user_usuario = _usuario_fixture(cls, "c14batch")

    def test_segundo_item_do_lote_com_state_explicito_e_bloqueado_no_pre_check(self):
        """`state` explícito no 2º dict — já capturado pelo pré-check da
        Task 13 (que já iterava `vals_list` inteiro). Cobertura de
        regressão: garante que o pré-check nunca regrida para só olhar
        `vals_list[0]`."""
        os_propria = self.env["afr.qualificacao.os"].create({
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        })
        Qualif = self.env["afr.qualificacao"].with_user(self.user_usuario)
        vals_ok = {
            "name": "Qualif C14 Lote OK",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_propria.id,
        }
        vals_violacao = {
            "name": "Qualif C14 Lote Violacao",
            "equipment_id": self.equip2.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_propria.id,
            "state": "approved",
        }
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            with self.cr.savepoint():
                Qualif.create([vals_ok, vals_violacao])
        self.assertFalse(
            self.env["afr.qualificacao"].search(
                [("name", "in", ["Qualif C14 Lote OK", "Qualif C14 Lote Violacao"])]
            ),
            "nem o item válido do lote pode sobreviver — create() em lote é atômico",
        )

    def test_segundo_item_do_lote_via_default_context_e_bloqueado_no_pos_check(self):
        """Exercita de verdade o PÓS-check em lote (o alvo real desta task):
        `default_state='approved'` no contexto vale para o lote inteiro, mas
        o 1º dict sobrescreve explicitamente com `state='draft'` (não viola
        nada) e só o 2º dict herda o default forjado. Um pós-check que só
        olhasse `records[0]` (ou parasse no primeiro OK) deixaria passar —
        este teste quebra nesse cenário."""
        os_propria = self.env["afr.qualificacao.os"].create({
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        })
        Qualif = self.env["afr.qualificacao"].with_user(self.user_usuario)
        vals_ok = {
            "name": "Qualif C14 Lote Ctx OK",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_propria.id,
            "state": "draft",  # sobrescreve o default do contexto — item OK
        }
        vals_herda_default = {
            "name": "Qualif C14 Lote Ctx Violacao",
            "equipment_id": self.equip2.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_propria.id,
            # sem "state" — herda default_state='approved' do contexto
        }
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            with self.cr.savepoint():
                Qualif.with_context(default_state="approved").create(
                    [vals_ok, vals_herda_default]
                )
        self.assertFalse(
            self.env["afr.qualificacao"].search(
                [("name", "in", [
                    "Qualif C14 Lote Ctx OK", "Qualif C14 Lote Ctx Violacao",
                ])]
            ),
            "lote inteiro (inclusive o 1º item, que era válido) não sobrevive "
            "ao rollback — create() em lote é atômico",
        )


@tagged("afr_qualificacao", "task14_security", "post_install", "-at_install")
class TestDuplicateResetsStateAfterCopyFalse(AfrQualificacaoTestCommon):
    """Minor (achado da mesma revisão): `state` era `copy=True` em ambos os
    modelos. Como o novo guard de `create()` olha os valores EFETIVOS do
    registro (inclusive os vindos de `copy_data()`), um não-Gestor usando
    "Duplicar" num registro `approved`/`done` caía no guard manager-only —
    mensagem que não faz sentido pra quem só clicou em Duplicar, e um
    over-tightening real (nada nesta base depende de `state` sobreviver a um
    `copy()`; grep confirma nenhum outro uso de `.copy()`/`action_duplicate`
    nestes dois modelos). Fix: `copy=False` em `state` — o duplicado nasce
    sempre em `draft` (default do campo), o guard nunca entra em jogo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico, cls.user_tecnico = _tecnico_fixture(cls, "c14dup")
        cls.user_usuario = _usuario_fixture(cls, "c14dup")
        cls.user_manager = _manager_fixture(cls, "c14dup")

    def test_usuario_duplica_qualif_approved_sem_guard_e_nasce_draft(self):
        os_propria = self.env["afr.qualificacao.os"].create({
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        })
        qualif = self.env["afr.qualificacao"].create({
            "name": "Qualif C14 Original Approved",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_propria.id,
        })
        qualif.with_user(self.user_manager).action_mark_approved()
        self.assertEqual(qualif.state, "approved")
        self.assertTrue(qualif.certificate_token)

        dup = qualif.with_user(self.user_usuario).copy()
        self.assertEqual(
            dup.state, "draft",
            "copy=False em state faz o duplicado nascer em rascunho, sem "
            "acionar o guard manager-only de create()",
        )
        self.assertFalse(dup.certificate_token)
        self.assertFalse(dup.certificate_hash)
        self.assertFalse(dup.certificate_issued_at)

    def test_usuario_duplica_os_done_sem_guard_e_nasce_draft_com_nome_novo(self):
        os_propria = self.env["afr.qualificacao.os"].create({
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        })
        os_propria.write({"state": "done"})  # env su neste setUp — monta o fixture direto
        nome_original = os_propria.name
        self.assertNotEqual(nome_original, "Novo")

        dup = os_propria.with_user(self.user_usuario).copy()
        self.assertEqual(
            dup.state, "draft",
            "copy=False em state faz a OS duplicada nascer em rascunho, sem "
            "acionar o guard manager-only de create()",
        )
        self.assertTrue(dup.name)
        self.assertNotEqual(dup.name, "Novo")
        self.assertNotEqual(
            dup.name, nome_original,
            "name já era copy=False — nova sequência atribuída no create() da cópia",
        )
