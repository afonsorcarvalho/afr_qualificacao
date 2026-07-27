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
from odoo.exceptions import AccessError, UserError
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

    @staticmethod
    def _to_scheduled(os_rec):
        """Leva a OS direto para `scheduled`, pulando `action_schedule()`.

        `action_schedule()` exige qualificacao_ids + técnico/responsável por
        qualif — montar essa árvore de sub-records só pra testar o guard de
        `action_start_daily_relatorio` seria desproporcional (Task 8). Write
        direto do estado é aceitável aqui: o que estes testes exercitam é o
        guard de estado do entrypoint do PWA, não o fluxo de agendamento.
        """
        os_rec.write({"state": "scheduled"})
        return os_rec

    @staticmethod
    def _to_in_progress(os_rec):
        """Leva a OS direto para `in_progress` (sem passar por `scheduled`).

        Usado por testes que precisam que `action_start_daily_relatorio` NÃO
        toque `write()` (a OS já está em `in_progress`, então o `if self.state
        == "scheduled":` do método nunca dispara) — relevante pra Finding 3
        (Task 10): read é global, então qualquer usuário com o grupo Técnico
        pode chamar o entrypoint numa OS alheia já iniciada, sem esbarrar na
        ir.rule de escopo de write (Task 9).
        """
        os_rec.write({"state": "in_progress"})
        return os_rec

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

    def test_duplicar_relatorio_assinado_nao_copia_assinatura(self):
        """`copy=False` nos campos de assinatura: duplicar um relatório
        assinado (Duplicate no form, disponível pro gestor) não pode gerar
        um draft carregando a assinatura/timestamp de outra pessoa — isso
        permitiria `action_done` aceitar um "assinado" que ninguém assinou.
        """
        rel = self._make_relatorio()
        rel.write({
            "signature_technician": self.PNG_1X1,
            "signature_technician_date": datetime(2026, 7, 1, 12, 30, 0),
        })
        copia = rel.copy()
        self.assertFalse(copia.signature_technician)
        self.assertFalse(copia.signature_technician_date)

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
        os_rec = self._to_scheduled(self._make_os())
        rel_id = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio()
        rel = self.env["afr.qualificacao.os.relatorio"].browse(rel_id)
        self.assertTrue(rel.exists())
        self.assertEqual(rel.state, "draft")
        self.assertEqual(rel.os_id, os_rec)
        self.assertIn(self.employee_tecnico, rel.tecnico_ids)
        self.assertFalse(rel.descricao)

    def test_start_daily_e_idempotente(self):
        os_rec = self._to_scheduled(self._make_os()).with_user(self.user_tecnico)
        first = os_rec.action_start_daily_relatorio()
        second = os_rec.action_start_daily_relatorio()
        self.assertEqual(first, second)

    def test_start_daily_reusa_dentro_da_mesma_janela(self):
        os_rec = self._to_scheduled(self._make_os()).with_user(self.user_tecnico)
        janela = self._janela()
        a = os_rec.action_start_daily_relatorio(**janela)
        b = os_rec.action_start_daily_relatorio(**janela)
        self.assertEqual(a, b)

    def test_start_daily_ignora_relatorio_de_outro_dia(self):
        """Draft de ontem não é reaproveitado pela janela de hoje."""
        os_rec = self._to_scheduled(self._make_os())
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
        os_rec = self._to_scheduled(self._make_os())
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
        os_rec = self._to_scheduled(self._make_os())
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

    def test_start_daily_reusa_relatorio_de_ontem_quando_janela_pedida_explicitamente(self):
        """Kwargs `day_start`/`day_end` precisam ser honrados, não ignorados.

        `user_tecnico` não tem `tz` (fallback silencioso vira UTC), então uma
        janela do fallback do dia atual JAMAIS bateria com um relatório
        datado ontem. Este teste só passa se `action_start_daily_relatorio`
        realmente usar a janela explícita recebida — se o `if day_start and
        day_end:` for invertido/removido, o fallback busca "hoje", não acha
        o draft de ontem, cria um novo, e o `assertEqual` abaixo falha.
        """
        os_rec = self._make_os()
        janela_ontem = self._janela(dias_atras=1)
        ontem_na_janela = janela_ontem["day_start"] + timedelta(hours=10)
        antigo = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os_rec.id,
            "data_inicio": ontem_na_janela,
            "data_fim": ontem_na_janela,
            "tecnico_ids": [(6, 0, [self.employee_tecnico.id])],
        })
        self._to_scheduled(os_rec)
        reused = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio(
            **janela_ontem
        )
        self.assertEqual(reused, antigo.id)

    def test_start_daily_sem_employee_erro_claro(self):
        # Task 10 — Finding 3: revertido para grupo Técnico PURO (não mais
        # `group_afr_qualificacao_user`, que era um workaround pra fugir da
        # ir.rule — ver `test_start_daily_puro_tecnico_nao_dono_os_scheduled`
        # logo abaixo, que cobre esse gap diretamente). Pra manter o alvo
        # original deste teste (guard de colaborador ausente, não ACL de dono
        # da OS) sem essa muleta, a OS já nasce `in_progress` — o entrypoint
        # não toca `write()` (o `if self.state == "scheduled":` não dispara),
        # então a ir.rule de escopo de write (Task 9) nunca entra em jogo:
        # read é global, qualquer Técnico pode chamar o método numa OS já
        # iniciada, o que expõe só o guard de `hr.employee` ausente.
        user_sem_emp = self.env["res.users"].create({
            "name": "Sem Employee",
            "login": "sem.employee.pwa.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        os_rec = self._to_in_progress(self._make_os()).with_user(user_sem_emp)
        with self.assertRaisesRegex(UserError, "colaborador"):
            os_rec.action_start_daily_relatorio()

    def test_start_daily_puro_tecnico_nao_dono_os_scheduled_access_error(self):
        """Contrato explícito da Task 10 — Finding 3.

        Um Técnico puro (não `group_afr_qualificacao_user`) que está listado
        em `tecnico_ids` de uma OS mas NÃO é o `tecnico_default_id` dela não
        consegue chamar `action_start_daily_relatorio` enquanto a OS ainda
        está `scheduled` — a transição `scheduled → in_progress` passa por
        `write()`, sujeito à ir.rule `tecnico_default_user_id == uid` (Task
        9). Resultado: `AccessError`, não o `UserError` amigável de
        "colaborador ausente". Isto é reachable de verdade: o front do PWA
        lista OS de outros técnicos por padrão ("só minhas" é opt-in), então
        um técnico pode abrir e tocar numa OS que não é sua.

        Ampliar esse contrato (aceitar qualquer `tecnico_ids`) exigiria trocar
        o domínio da ir.rule pra `tecnico_ids.user_id` — decisão do dono do
        produto, deliberadamente NÃO feita aqui (grupo Técnico não lê
        `hr.employee` no Odoo 16; é por isso que existe o espelho stored
        `tecnico_default_user_id`).
        """
        user_outro_tecnico = self.env["res.users"].create({
            "name": "Outro Técnico Puro",
            "login": "outro.tecnico.puro.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        os_rec = self._to_scheduled(self._make_os())  # dona: employee_tecnico/user_tecnico
        with self.assertRaises(AccessError):
            os_rec.with_user(user_outro_tecnico).action_start_daily_relatorio()

    # ─────────────────────────────────────────────────────────────
    # 5. guard de estado + transição (Task 8) — scheduled/in_progress
    #    aceitos, resto rejeita SEM efeito colateral (nenhum relatório
    #    é criado). A transição em si prova o ACL de write do técnico:
    #    o `write` roda como `self.user_tecnico`, não sudo.
    # ─────────────────────────────────────────────────────────────
    def test_start_daily_scheduled_transiciona_para_in_progress(self):
        os_rec = self._to_scheduled(self._make_os())
        rel_id = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio()
        self.assertEqual(os_rec.state, "in_progress")
        rel = self.env["afr.qualificacao.os.relatorio"].browse(rel_id)
        self.assertTrue(rel.exists())
        self.assertEqual(rel.state, "draft")

    def test_start_daily_in_progress_permanece_in_progress(self):
        os_rec = self._to_scheduled(self._make_os())
        os_rec.write({"state": "in_progress"})
        rel_id = os_rec.with_user(self.user_tecnico).action_start_daily_relatorio()
        self.assertEqual(os_rec.state, "in_progress")
        self.assertTrue(rel_id)

    def test_start_daily_bloqueia_os_done(self):
        os_rec = self._make_os()
        os_rec.write({"state": "done"})
        Relatorio = self.env["afr.qualificacao.os.relatorio"]
        antes = Relatorio.search_count([("os_id", "=", os_rec.id)])
        with self.assertRaisesRegex(UserError, "agendada ou em execução"):
            os_rec.with_user(self.user_tecnico).action_start_daily_relatorio()
        depois = Relatorio.search_count([("os_id", "=", os_rec.id)])
        self.assertEqual(antes, depois)
        self.assertEqual(depois, 0)

    def test_start_daily_bloqueia_os_cancelled(self):
        os_rec = self._make_os()
        os_rec.write({"state": "cancelled"})
        with self.assertRaisesRegex(UserError, "agendada ou em execução"):
            os_rec.with_user(self.user_tecnico).action_start_daily_relatorio()

    def test_start_daily_bloqueia_os_draft(self):
        """Consequência intencional do guard: a home do PWA também lista OS
        em `draft` (domínio do front), mas tocar "Iniciar relatório do dia"
        numa OS que nunca foi agendada agora levanta erro claro, em vez de
        criar relatório silenciosamente contra uma OS sem cronograma."""
        os_rec = self._make_os()
        self.assertEqual(os_rec.state, "draft")
        with self.assertRaisesRegex(UserError, "agendada ou em execução"):
            os_rec.with_user(self.user_tecnico).action_start_daily_relatorio()


@tagged("afr_qualificacao", "pwa_tecnico", "post_install", "-at_install")
class TestPwaTecnicoRpcSecurity(TransactionCase):
    """Fechamento do gap de segurança aberto pelo write ACL do técnico (Task 8).

    O grupo Técnico ganhou `perm_write` em `afr.qualificacao.os` só para
    permitir a transição `scheduled → in_progress` feita pelo próprio PWA em
    `action_start_daily_relatorio`. Isso, sozinho, também deixaria um técnico
    aprovar/concluir/cancelar qualquer OS e reescrever qualquer campo (inclusive
    a assinatura do supervisor) via RPC direto. Esta classe prova que:
      - a `ir.rule` restringe o write do Técnico puro à própria OS
        (`tecnico_default_user_id == uid`);
      - o grupo Usuário/Gestor (que implica Técnico) continua com write global,
        graças à regra permissiva anexada a `group_afr_qualificacao_user`;
      - os guards de método em `action_approve`/`action_done`/`action_cancel`
        bloqueiam quem não é Gestor, mesmo já tendo write na OS;
      - `signature_supervisor` não é gravável por quem não é Gestor.

    Classe separada (em vez de mais testes em `TestPwaTecnicoRpc`) porque o
    fixture aqui precisa de um usuário Gestor que aquela classe não usa —
    manter os dois focos (RPC do PWA vs. segurança do write ACL) em classes
    distintas evita inflar o `setUpClass` de uma classe com fixtures que só a
    outra metade dos testes usa.
    """

    PNG_1X1 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
        "h6FO1AAAAABJRU5ErkJggg=="
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_tecnico = cls.env["hr.employee"].create({"name": "Téc Segurança"})
        cls.user_tecnico = cls.env["res.users"].create({
            "name": "Téc Segurança",
            "login": "tecnico.security.test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        cls.employee_tecnico.user_id = cls.user_tecnico.id
        cls.user_manager = cls.env["res.users"].create({
            "name": "Gestor Segurança",
            "login": "gestor.security.test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_manager").id,
            ])],
        })

    def _make_os(self, **overrides):
        vals = {
            "tecnico_default_id": self.employee_tecnico.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        }
        vals.update(overrides)
        return self.env["afr.qualificacao.os"].create(vals)

    def test_tecnico_nao_pode_aprovar_os(self):
        """action_approve é Gestor-only: técnico com write na própria OS
        ainda assim não pode aprová-la, e o estado não se move."""
        os_rec = self._make_os()
        os_rec.write({"state": "in_approved"})
        with self.assertRaisesRegex(UserError, "[Gg]estor"):
            os_rec.with_user(self.user_tecnico).action_approve()
        self.assertEqual(os_rec.state, "in_approved")

    def test_tecnico_nao_pode_escrever_os_de_outro_tecnico(self):
        """Regra de registro: write do Técnico só na própria OS
        (`tecnico_default_user_id == uid`). OS sem técnico atribuído (ou de
        outro técnico) não bate — write levanta AccessError."""
        os_de_outro = self._make_os(tecnico_default_id=False)
        self.assertFalse(os_de_outro.tecnico_default_user_id)
        with self.assertRaises(AccessError):
            os_de_outro.with_user(self.user_tecnico).write({
                "date_planned_start": datetime(2026, 7, 2, 8, 0, 0),
                "date_planned_end": datetime(2026, 7, 2, 17, 0, 0),
            })

    def test_tecnico_pode_escrever_a_propria_os(self):
        """Regressão do gap original: o técnico continua conseguindo
        escrever a OS onde é `tecnico_default_user_id` — é isso que
        `action_start_daily_relatorio` precisa pra transicionar o estado."""
        os_rec = self._make_os()
        self.assertEqual(os_rec.tecnico_default_user_id, self.user_tecnico)
        os_rec.with_user(self.user_tecnico).write({
            "date_planned_start": datetime(2026, 7, 2, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 2, 17, 0, 0),
        })
        self.assertEqual(
            os_rec.date_planned_start, datetime(2026, 7, 2, 8, 0, 0)
        )

    def test_gestor_pode_escrever_qualquer_os_e_aprovar(self):
        """Regra permissiva anexada a `group_afr_qualificacao_user` (que o
        Gestor herda): sem ela, o Gestor cairia na mesma regra restritiva do
        Técnico (grupos implícitos) e ficaria trancado fora de OS alheias."""
        os_rec = self._make_os()  # tecnico_default_id = employee_tecnico, não gestor
        os_rec.with_user(self.user_manager).write({
            "date_planned_start": datetime(2026, 7, 2, 9, 0, 0),
            "date_planned_end": datetime(2026, 7, 2, 18, 0, 0),
        })
        self.assertEqual(
            os_rec.date_planned_start, datetime(2026, 7, 2, 9, 0, 0)
        )
        os_rec.write({"state": "in_approved"})
        os_rec.with_user(self.user_manager).action_approve()
        self.assertEqual(os_rec.state, "approved")

    def test_tecnico_nao_pode_escrever_assinatura_supervisor(self):
        """`signature_supervisor` é Gestor-only a nível de campo (ORM),
        mesmo numa OS que o técnico pode escrever normalmente.

        Escreve outro campo antes, com sucesso, na mesma OS/mesmo usuário —
        prova que o `AccessError` abaixo vem do campo, não da ir.rule (que
        deixaria passar, já que é a própria OS do técnico)."""
        os_rec = self._make_os()
        os_rec.with_user(self.user_tecnico).write({
            "date_planned_start": datetime(2026, 7, 3, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 3, 17, 0, 0),
        })
        with self.assertRaises(AccessError):
            os_rec.with_user(self.user_tecnico).write({
                "signature_supervisor": self.PNG_1X1,
            })
