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
