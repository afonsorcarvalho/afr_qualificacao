# -*- coding: utf-8 -*-
"""Contadores "hoje" do Histórico do PWA, calculados no servidor.

Antes o PWA montava a janela do dia com o relógio do aparelho
(`todayRangeOdoo` em `pwa/lib/odoo/tecnico.ts`) e comparava contra
`captured_at`/`signature_technician_date`, que o servidor carimba. Celular com
relógio torto ⇒ contadores errados. Aqui a janela é decidida pelo servidor, no
fuso do usuário logado — mesmo critério de `_janela_do_dia`.
"""
from datetime import datetime, timedelta

import pytz

from odoo import fields
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "pwa_tecnico", "post_install", "-at_install")
class TestPwaHistoricoHoje(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_tecnico = cls.env["res.users"].create({
            "name": "Téc Histórico",
            "login": "tecnico.historico.test",
            "tz": "America/Sao_Paulo",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        cls.employee = cls.env["hr.employee"].create({
            "name": "Téc Histórico",
            "user_id": cls.user_tecnico.id,
        })
        cls.outro_user = cls.env["res.users"].create({
            "name": "Outro Téc Histórico",
            "login": "outro.historico.test",
            "tz": "America/Sao_Paulo",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        # `engc.equipment` exige `category_id` (NOT NULL no banco); o common
        # do addon já cria categoria + equipamentos prontos.
        cls.equipment = cls.equip1

    # ───────── helpers ─────────
    def _make_os(self):
        return self.env["afr.qualificacao.os"].create({
            "tecnico_default_id": self.employee.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        })

    def _make_item(self, os_rec, captured_at, captured_by):
        """Item já coletado, com `captured_at`/`captured_by` forçados.

        O write direto é intencional: os dois campos são carimbados pelo
        servidor no fluxo real, e o que este teste exercita é a janela que
        os lê, não quem os escreve.
        """
        qualif = self.env["afr.qualificacao"].create({
            "name": "Q Histórico",
            "equipment_id": self.equipment.id,
            "qualification_type": "installation",
            "os_id": os_rec.id,
            "responsible_id": self.env.uid,
        })
        item = self.env["afr.qualificacao.collect.item"].create({
            "name": "Item Histórico",
            "kind": "foto",
            "required": True,
            "qualif_id": qualif.id,
            "file": b"UE5H",
            "filename": "hist.png",
        })
        item.write({"captured_at": captured_at, "captured_by": captured_by.id})
        return item

    def _make_relatorio_fechado(self, os_rec, assinado_em, criado_por):
        rel = self.env["afr.qualificacao.os.relatorio"].with_user(criado_por).create({
            "os_id": os_rec.id,
            "data_inicio": fields.Datetime.now() - timedelta(hours=2),
            "data_fim": fields.Datetime.now(),
            "tecnico_ids": [(6, 0, [self.employee.id])],
            "descricao": "Turno de teste",
        })
        rel.write({"state": "done", "signature_technician_date": assinado_em})
        return rel

    def _resumo(self):
        return (
            self.env["afr.qualificacao.os.relatorio"]
            .with_user(self.user_tecnico)
            .action_historico_hoje()
        )

    @staticmethod
    def _meia_noite_local_em_utc(user):
        """UTC naive da meia-noite de hoje no fuso do usuário.

        Em UTC-3 isso é 03:00 UTC de hoje — ou seja, a fronteira local do dia
        cai *depois* da meia-noite UTC. É essa diferença que os testes de
        fuso exploram.
        """
        tz = pytz.timezone(user.tz)
        agora_local = datetime.now(tz)
        local = tz.localize(
            datetime.combine(agora_local.date(), datetime.min.time())
        )
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    # ───────── contagem de coletas ─────────
    def test_conta_coleta_de_hoje_do_proprio_usuario(self):
        os_rec = self._make_os()
        self._make_item(os_rec, fields.Datetime.now(), self.user_tecnico)
        self.assertEqual(self._resumo()["hoje_coletas"], 1)

    def test_ignora_coleta_de_ontem(self):
        os_rec = self._make_os()
        self._make_item(
            os_rec,
            fields.Datetime.now() - timedelta(days=1),
            self.user_tecnico,
        )
        self.assertEqual(self._resumo()["hoje_coletas"], 0)

    def test_ignora_coleta_de_outro_tecnico(self):
        os_rec = self._make_os()
        self._make_item(os_rec, fields.Datetime.now(), self.outro_user)
        self.assertEqual(self._resumo()["hoje_coletas"], 0)

    def test_conta_oss_distintas_nao_coletas(self):
        os_a, os_b = self._make_os(), self._make_os()
        self._make_item(os_a, fields.Datetime.now(), self.user_tecnico)
        self._make_item(os_a, fields.Datetime.now(), self.user_tecnico)
        self._make_item(os_b, fields.Datetime.now(), self.user_tecnico)
        resumo = self._resumo()
        self.assertEqual(resumo["hoje_coletas"], 3)
        self.assertEqual(resumo["hoje_oss"], 2)

    # ───────── janela no fuso do usuário ─────────
    def test_janela_usa_fuso_do_usuario_nao_meia_noite_utc(self):
        """Instante que é "hoje" em UTC mas "ontem" no fuso do técnico.

        Em UTC-3 a meia-noite local é 03:00 UTC; uma hora antes disso (02:00
        UTC de hoje) ainda é 23:00 de ontem pro técnico. Uma janela ingênua
        (meia-noite UTC) contaria essa coleta como de hoje — é justamente o
        que este teste impede.
        """
        os_rec = self._make_os()
        uma_hora_antes = self._meia_noite_local_em_utc(self.user_tecnico) - timedelta(
            hours=1
        )
        self._make_item(os_rec, uma_hora_antes, self.user_tecnico)
        self.assertEqual(self._resumo()["hoje_coletas"], 0)

    def test_conta_coleta_logo_apos_a_meia_noite_local(self):
        """Contraparte do teste acima: uma hora DEPOIS da meia-noite local
        conta, provando que a janela abre na fronteira local e não em outra."""
        os_rec = self._make_os()
        uma_hora_depois = self._meia_noite_local_em_utc(self.user_tecnico) + timedelta(
            hours=1
        )
        self._make_item(os_rec, uma_hora_depois, self.user_tecnico)
        self.assertEqual(self._resumo()["hoje_coletas"], 1)

    # ───────── relatórios fechados ─────────
    def test_conta_relatorio_fechado_hoje(self):
        os_rec = self._make_os()
        self._make_relatorio_fechado(
            os_rec, fields.Datetime.now(), self.user_tecnico
        )
        self.assertEqual(self._resumo()["hoje_relatorios_fechados"], 1)

    def test_ignora_relatorio_fechado_ontem(self):
        os_rec = self._make_os()
        self._make_relatorio_fechado(
            os_rec, fields.Datetime.now() - timedelta(days=1), self.user_tecnico
        )
        self.assertEqual(self._resumo()["hoje_relatorios_fechados"], 0)

    def test_ignora_relatorio_de_outro_usuario(self):
        os_rec = self._make_os()
        self._make_relatorio_fechado(
            os_rec, fields.Datetime.now(), self.outro_user
        )
        self.assertEqual(self._resumo()["hoje_relatorios_fechados"], 0)

    # ───────── contrato do retorno ─────────
    def test_retorno_tem_as_tres_chaves_zeradas_sem_dado(self):
        self.assertEqual(
            self._resumo(),
            {"hoje_coletas": 0, "hoje_oss": 0, "hoje_relatorios_fechados": 0},
        )
