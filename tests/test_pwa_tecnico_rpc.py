# -*- coding: utf-8 -*-
"""Testes da superfície RPC consumida pelo PWA Técnico de Campo.

Cobre os 4 pontos de adequação (16.0.6.4.0):
  1. `tecnico_default_user_id` — espelho stored p/ filtro "só minhas" sem ACL de hr
  2. `descricao` opcional no relatório draft (PWA preenche só no fechamento)
  3. `signature_technician` / `signature_technician_date` no relatório
  4. `action_start_daily_relatorio` — entrypoint idempotente do relatório do dia
"""
import base64
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("afr_qualificacao", "pwa_tecnico", "post_install", "-at_install")
class TestPwaTecnicoRpc(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_tecnico = cls.env["res.users"].create({
            "name": "Téc PWA",
            "login": "tecnico.pwa.test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        cls.employee_tecnico = cls.env["hr.employee"].create({
            "name": "Téc PWA",
            "user_id": cls.user_tecnico.id,
        })
        cls.employee_outro = cls.env["hr.employee"].create({"name": "Outro Téc"})

    def _make_os(self, **overrides):
        vals = {
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    def _make_relatorio(self, os_rec=None, **overrides):
        vals = {
            "os_id": (os_rec or self._make_os()).id,
            "data_inicio": datetime(2026, 7, 1, 8, 0, 0),
            "data_fim": datetime(2026, 7, 1, 12, 0, 0),
            "tecnico_ids": [(6, 0, [self.employee_tecnico.id])],
            "descricao": "Teste",
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os.relatorio"].create(vals)

    @staticmethod
    def _janela(dias_atras=0):
        """Janela de 1 dia ancorada no AGORA real, em UTC.

        Precisa ser relativa ao agora porque `action_start_daily_relatorio`
        grava `data_inicio = fields.Datetime.now()` — janelas com datas fixas
        nunca conteriam o registro criado, e os testes de idempotência
        passariam/falhariam por motivo errado.
        """
        inicio_hoje = fields.Datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        inicio = inicio_hoje - timedelta(days=dias_atras)
        return {"day_start": inicio, "day_end": inicio + timedelta(days=1)}

    # ─────────────────────────────────────────────────────────────
    # 1. tecnico_default_user_id (espelho p/ filtro "só minhas")
    # ─────────────────────────────────────────────────────────────
    def test_tecnico_default_user_id_espelha_user_do_employee(self):
        os_rec = self._make_os()
        self.assertEqual(os_rec.tecnico_default_user_id, self.user_tecnico)

    def test_tecnico_default_user_id_vazio_se_employee_sem_user(self):
        os_rec = self._make_os(tecnico_default_id=self.employee_outro.id)
        self.assertFalse(os_rec.tecnico_default_user_id)

    def test_search_por_tecnico_default_user_id(self):
        os_mine = self._make_os()
        os_outro = self._make_os(tecnico_default_id=self.employee_outro.id)
        found = self.env["afr.qualificacao.os"].search([
            ("tecnico_default_user_id", "=", self.user_tecnico.id),
        ])
        self.assertIn(os_mine, found)
        self.assertNotIn(os_outro, found)

    def test_tecnico_pode_filtrar_so_minhas_sem_acesso_a_hr_employee(self):
        """Regressão do gap: técnico não lê hr.employee no Odoo 16.

        O domain antigo `tecnico_default_id.user_id` sub-busca hr.employee e
        estoura/retorna vazio pro técnico. O campo espelho é coluna da própria OS.
        """
        os_mine = self._make_os()
        self._make_os(tecnico_default_id=self.employee_outro.id)
        as_tecnico = self.env["afr.qualificacao.os"].with_user(self.user_tecnico)
        rows = as_tecnico.search_read(
            [("tecnico_default_user_id", "=", self.user_tecnico.id)],
            ["name", "tecnico_default_user_id"],
        )
        self.assertEqual([r["id"] for r in rows], [os_mine.id])

    # ─────────────────────────────────────────────────────────────
    # 2. descricao opcional no draft
    # ─────────────────────────────────────────────────────────────
    def test_cria_relatorio_draft_sem_descricao(self):
        rel = self._make_relatorio(descricao=False)
        self.assertEqual(rel.state, "draft")
        self.assertFalse(rel.descricao)

    def test_action_done_ainda_exige_descricao(self):
        rel = self._make_relatorio(descricao=False)
        with self.assertRaises(UserError):
            rel.action_done()

    def test_action_done_passa_com_descricao_preenchida_depois(self):
        rel = self._make_relatorio(descricao=False)
        rel.write({"descricao": "Ciclo vazio da QD AC-01 concluído."})
        rel.action_done()
        self.assertEqual(rel.state, "done")

    # ─────────────────────────────────────────────────────────────
    # 3. assinatura do técnico no relatório
    # ─────────────────────────────────────────────────────────────
    # PNG 1x1 válido — fields.Image valida o binário, não aceita lixo.
    PNG_1X1 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
        "h6FO1AAAAABJRU5ErkJggg=="
    )

    def test_relatorio_aceita_assinatura_do_tecnico(self):
        rel = self._make_relatorio()
        assinado_em = datetime(2026, 7, 1, 12, 30, 0)
        rel.write({
            "signature_technician": self.PNG_1X1,
            "signature_technician_date": assinado_em,
        })
        self.assertTrue(rel.signature_technician)
        self.assertEqual(rel.signature_technician_date, assinado_em)
        # round-trip: o binário volta decodificável
        base64.b64decode(rel.signature_technician)

    def test_assinatura_vazia_por_default(self):
        rel = self._make_relatorio()
        self.assertFalse(rel.signature_technician)
        self.assertFalse(rel.signature_technician_date)

    def test_fluxo_pwa_finalizar_write_depois_action_done(self):
        """Espelha exatamente a sequência de 2 RPCs do front (Task 6).

        `data_fim` é required=True e continua assim (a Task 2 só relaxou
        `descricao`), então o relatório nasce com data_fim == data_inicio —
        mesmo padrão do wizard oficial (`wizards/relatorio_wizard.py:70`) e do
        `action_start_daily_relatorio` (Task 4) — e o fechamento grava o real.
        """
        rel = self._make_relatorio(
            descricao=False,
            data_inicio=datetime(2026, 7, 1, 8, 0, 0),
            data_fim=datetime(2026, 7, 1, 8, 0, 0),
        )
        rel.write({
            "data_fim": datetime(2026, 7, 1, 12, 0, 0),
            "descricao": "Coletas do turno concluídas.",
            "signature_technician": self.PNG_1X1,
            "signature_technician_date": datetime(2026, 7, 1, 12, 0, 0),
        })
        rel.action_done()
        self.assertEqual(rel.state, "done")
        self.assertGreater(rel.time_execution, 0)

    def test_write_so_assinatura_carimba_data_automaticamente(self):
        """Sem override, a data ficaria inatingível pela UI padrão do Odoo
        (backoffice desenha a assinatura em `draft`, mas não tem como
        preencher a data — o campo é readonly=True). O `write()` carimba
        `fields.Datetime.now()` quando a assinatura vem sozinha."""
        rel = self._make_relatorio()
        antes = fields.Datetime.now()
        rel.write({"signature_technician": self.PNG_1X1})
        depois = fields.Datetime.now()
        self.assertTrue(rel.signature_technician_date)
        self.assertGreaterEqual(rel.signature_technician_date, antes)
        self.assertLessEqual(rel.signature_technician_date, depois)

    def test_write_assinatura_com_data_preserva_timestamp_do_cliente(self):
        """Guard do write(): quando o PWA manda os dois campos juntos (fluxo
        real), o timestamp do dispositivo no momento da assinatura não pode
        ser sobrescrito pelo `now()` do servidor."""
        rel = self._make_relatorio()
        assinado_em = datetime(2026, 7, 1, 12, 30, 0)
        rel.write({
            "signature_technician": self.PNG_1X1,
            "signature_technician_date": assinado_em,
        })
        self.assertEqual(rel.signature_technician_date, assinado_em)

    def test_write_limpar_assinatura_limpa_data_junto(self):
        """Regressão do guard por chave: `write({"signature_technician": False})`
        (reassinatura/clear) não pode carimbar `now()` — a data acompanha o
        clear, porque data de assinatura sem assinatura não faz sentido."""
        rel = self._make_relatorio()
        rel.write({
            "signature_technician": self.PNG_1X1,
            "signature_technician_date": datetime(2026, 7, 1, 12, 30, 0),
        })
        self.assertTrue(rel.signature_technician)

        rel.write({"signature_technician": False})
        self.assertFalse(rel.signature_technician)
        self.assertFalse(rel.signature_technician_date)

    # ─────────────────────────────────────────────────────────────
    # 4. action_start_daily_relatorio (idempotente)
    # ─────────────────────────────────────────────────────────────
    def test_start_daily_cria_relatorio_draft(self):
        os_rec = self._make_os()
        rel_id = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio()
        rel = self.env["afr.qualificacao.os.relatorio"].browse(rel_id)
        self.assertTrue(rel.exists())
        self.assertEqual(rel.state, "draft")
        self.assertEqual(rel.os_id, os_rec)
        self.assertIn(self.employee_tecnico, rel.tecnico_ids)
        self.assertFalse(rel.descricao)

    def test_start_daily_e_idempotente(self):
        os_rec = self._make_os().with_user(self.user_tecnico)
        first = os_rec.action_start_daily_relatorio()
        second = os_rec.action_start_daily_relatorio()
        self.assertEqual(first, second)

    def test_start_daily_reusa_dentro_da_mesma_janela(self):
        os_rec = self._make_os().with_user(self.user_tecnico)
        janela = self._janela()
        a = os_rec.action_start_daily_relatorio(**janela)
        b = os_rec.action_start_daily_relatorio(**janela)
        self.assertEqual(a, b)

    def test_start_daily_ignora_relatorio_de_outro_dia(self):
        """Draft de ontem não é reaproveitado pela janela de hoje."""
        os_rec = self._make_os()
        ontem = fields.Datetime.now() - timedelta(days=1)
        antigo = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os_rec.id,
            "data_inicio": ontem,
            "data_fim": ontem,
            "tecnico_ids": [(6, 0, [self.employee_tecnico.id])],
        })
        novo = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio(
            **self._janela()
        )
        self.assertNotEqual(novo, antigo.id)

    def test_start_daily_nao_reusa_relatorio_de_outro_tecnico(self):
        os_rec = self._make_os()
        agora = fields.Datetime.now()
        alheio = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os_rec.id,
            "data_inicio": agora,
            "data_fim": agora,
            "tecnico_ids": [(6, 0, [self.employee_outro.id])],
        })
        meu = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio(
            **self._janela()
        )
        self.assertNotEqual(meu, alheio.id)

    def test_start_daily_nao_reusa_relatorio_fechado(self):
        os_rec = self._make_os()
        agora = fields.Datetime.now()
        fechado = self._make_relatorio(
            os_rec=os_rec,
            data_inicio=agora,
            data_fim=agora + timedelta(hours=4),
            descricao="Fechado antes",
        )
        fechado.action_done()
        self.assertEqual(fechado.state, "done")
        novo = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio(
            **self._janela()
        )
        self.assertNotEqual(novo, fechado.id)

    def test_start_daily_sem_employee_erro_claro(self):
        user_sem_emp = self.env["res.users"].create({
            "name": "Sem Employee",
            "login": "sem.employee.pwa.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        os_rec = self._make_os().with_user(user_sem_emp)
        with self.assertRaises(UserError):
            os_rec.action_start_daily_relatorio()
