# -*- coding: utf-8 -*-
"""Escopo de autorização do grupo Técnico nos registros-filho da OS.

Contexto: a auditoria de 2026-07-27 achou cinco buracos que só não eram
exploráveis porque não existia conta puramente técnica no banco — todo mundo
tinha os três grupos por implicação. Em 2026-09-03 essas contas passaram a
existir (Bloco F do checklist do PWA), então os buracos viraram reais.

O que se prova aqui:
  1. `afr.qualificacao.cycle` e `.malha` tinham write pro Técnico sem `ir.rule`
     nenhuma — um técnico alterava o ciclo de uma qualificação alheia já
     aprovada e o certificado do cliente virava `tampered`.
  2. `afr.qualificacao.collect.item` tinha CRUD completo (com unlink) e
     alcance irrestrito em item de qualquer OS do banco.
  3. `approver_id` era escrevível por não-Gestor e entra no hash do
     certificado — dava pra nomear um gestor que nunca aprovou nada.

O par restritiva-Técnico + permissiva-Usuário é o mesmo padrão já usado em
`afr.qualificacao.os` e `afr.qualificacao`: `ir.rule` de grupos diferentes é
ORed, então sem a permissiva o Gestor (que implica Técnico) cairia na
restritiva e ficaria trancado fora da OS alheia.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "authorization", "post_install", "-at_install")
class TestAuthorizationScope(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"]
        cls.user_tec_dono = Users.create({
            "name": "Téc Dono",
            "login": "tec.dono.scope",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        cls.user_tec_alheio = Users.create({
            "name": "Téc Alheio",
            "login": "tec.alheio.scope",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        cls.user_gestor = Users.create({
            "name": "Gestor Scope",
            "login": "gestor.scope",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_manager").id,
            ])],
        })
        cls.emp_dono = cls.env["hr.employee"].create({
            "name": "Téc Dono", "user_id": cls.user_tec_dono.id,
        })

        cls.os_do_dono = cls.env["afr.qualificacao.os"].create({
            "tecnico_default_id": cls.emp_dono.id,
            "date_planned_start": "2026-07-01 08:00:00",
            "date_planned_end": "2026-07-01 17:00:00",
        })
        cls.qualif = cls.env["afr.qualificacao"].create({
            "name": "Q Scope",
            "equipment_id": cls.equip1.id,
            "qualification_type": "installation",
            "os_id": cls.os_do_dono.id,
            "responsible_id": cls.env.uid,
        })
        cls.cycle = cls.env["afr.qualificacao.cycle"].create({
            "qualificacao_id": cls.qualif.id,
            "cycle_type_id": cls.cycle_cmax.id,
        })
        cls.malha = cls.env["afr.qualificacao.malha"].create({
            "qualificacao_id": cls.qualif.id,
            "malha_type_id": cls.malha_temp.id,
        })
        cls.item = cls.env["afr.qualificacao.collect.item"].create({
            "name": "Item Scope",
            "kind": "foto",
            "required": True,
            "qualif_id": cls.qualif.id,
        })

    # ───────── cycle ─────────
    def test_tecnico_alheio_nao_escreve_cycle(self):
        with self.assertRaises(AccessError):
            self.cycle.with_user(self.user_tec_alheio).write({"notes": "adulterado"})

    def test_tecnico_dono_escreve_cycle(self):
        self.cycle.with_user(self.user_tec_dono).write({"notes": "ajustado em campo"})
        self.assertEqual(self.cycle.notes, "ajustado em campo")

    def test_gestor_escreve_cycle_de_qualquer_os(self):
        self.cycle.with_user(self.user_gestor).write({"notes": "corrigido pelo gestor"})
        self.assertEqual(self.cycle.notes, "corrigido pelo gestor")

    # ───────── malha ─────────
    def test_tecnico_alheio_nao_escreve_malha(self):
        with self.assertRaises(AccessError):
            self.malha.with_user(self.user_tec_alheio).write({"notes": "adulterada"})

    def test_tecnico_dono_escreve_malha(self):
        self.malha.with_user(self.user_tec_dono).write({"notes": "ajustada em campo"})
        self.assertEqual(self.malha.notes, "ajustada em campo")

    def test_gestor_escreve_malha_de_qualquer_os(self):
        self.malha.with_user(self.user_gestor).write({"notes": "corrigida pelo gestor"})
        self.assertEqual(self.malha.notes, "corrigida pelo gestor")

    # ───────── collect.item ─────────
    def test_tecnico_alheio_nao_escreve_item(self):
        with self.assertRaises(AccessError):
            self.item.with_user(self.user_tec_alheio).write({"description": "invadido"})

    def test_tecnico_dono_escreve_item(self):
        self.item.with_user(self.user_tec_dono).write({"description": "coletado ok"})
        self.assertEqual(self.item.description, "coletado ok")

    def test_tecnico_nao_apaga_item(self):
        """Item de coleta é o checklist da OS — apagar evidência não é ação de
        campo, nem na própria OS. O unlink saiu da ACL do Técnico."""
        with self.assertRaises(AccessError):
            self.item.with_user(self.user_tec_dono).unlink()

    def test_gestor_escreve_item_de_qualquer_os(self):
        self.item.with_user(self.user_gestor).write({"description": "revisado"})
        self.assertEqual(self.item.description, "revisado")

    # ───────── approver_id ─────────
    def test_tecnico_nao_grava_approver_na_qualificacao(self):
        with self.assertRaises(UserError):
            self.qualif.with_user(self.user_tec_dono).write({
                "approver_id": self.user_gestor.id,
            })

    def test_tecnico_nao_grava_approver_na_os(self):
        with self.assertRaises(UserError):
            self.os_do_dono.with_user(self.user_tec_dono).write({
                "approver_id": self.user_gestor.id,
            })

    def test_gestor_grava_approver(self):
        self.qualif.with_user(self.user_gestor).write({
            "approver_id": self.user_gestor.id,
        })
        self.assertEqual(self.qualif.approver_id, self.user_gestor)

    # ───────── report do certificado ─────────
    def test_report_certificado_restrito_a_usuario_e_gestor(self):
        """Sem `groups_id` no report, `/report/pdf/...` e o menu Imprimir
        contornavam o gate de `state == 'approved'` de
        `action_print_certificate` — o único controle era a marca d'água."""
        report = self.env.ref(
            "afr_qualificacao.action_report_qualificacao_certificate"
        )
        grupos = report.groups_id
        self.assertTrue(grupos, "report do certificado precisa de groups_id")
        self.assertIn(
            self.env.ref("afr_qualificacao.group_afr_qualificacao_user"),
            grupos,
        )
        self.assertNotIn(
            self.env.ref("afr_qualificacao.group_afr_qualificacao_technician"),
            grupos,
        )
