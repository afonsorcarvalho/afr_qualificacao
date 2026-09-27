"""P5 — regras determinísticas da varredura: positivo + negativo por regra."""
import base64
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from ..models import relatorio_rules
from ..models.relatorio_rules import RULES, run_rules
from .common_relatorio import RelatorioTestCommon, make_pdf


class _RulesMixin:
    def _run(self, code, ctx=None):
        self._refresh()
        rel = self.rel.with_context(**ctx) if ctx else self.rel
        return RULES[code](rel)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRelatorioRulesBloqueia(_RulesMixin, RelatorioTestCommon):

    # --- certificados -------------------------------------------------
    def test_cert_depois_sem_validador_no_plano(self):
        out = self._run("CERT_DEPOIS_AUSENTE")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")
        self.assertIn("Nenhum validador", out[0]["mensagem"])

    def test_cert_depois(self):
        v = self._validator()
        self.assertEqual(len(self._run("CERT_DEPOIS_AUSENTE")), 1)
        self._cert(v, "depois", self.D_FIM + timedelta(days=2))
        self.assertEqual(self._run("CERT_DEPOIS_AUSENTE"), [])

    def test_cert_depois_anterior_ao_fim_nao_serve(self):
        v = self._validator()
        self._cert(v, "depois", self.D_FIM - timedelta(days=1))
        self.assertEqual(len(self._run("CERT_DEPOIS_AUSENTE")), 1)

    def test_cert_antes(self):
        v = self._validator()
        self.assertEqual(len(self._run("CERT_ANTES_AUSENTE")), 1)
        self._cert(v, "antes", self.D_INI - timedelta(days=30))
        self.assertEqual(self._run("CERT_ANTES_AUSENTE"), [])

    def test_cert_datas_vazias(self):
        self._validator()
        self.rel.write({"data_inicio_ensaios": False})
        out = self._run("CERT_ANTES_AUSENTE")
        self.assertEqual(len(out), 1)
        self.assertIn("Datas", out[0]["mensagem"])
        self.assertEqual(self._run("CERT_DEPOIS_AUSENTE"), [])
        self.assertEqual(self._run("PADRAO_VENCIDO"), [])

    def test_padrao_vencido(self):
        p = self._padrao()
        self._cert(p, "externo", self.D_INI - timedelta(days=400), self.D_INI - timedelta(days=1))
        out = self._run("PADRAO_VENCIDO")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")
        self._cert(p, "externo", self.D_INI - timedelta(days=10), self.D_FIM + timedelta(days=300))
        self.assertEqual(self._run("PADRAO_VENCIDO"), [])

    # --- indicadores biológicos -------------------------------------------
    def test_ib_sem_leitura(self):
        c = self._cycle()
        self._cycle(cycle_type=self.cycle_qo_test, seq=2)  # sem carga: ignorado
        out = self._run("IB_SEM_LEITURA")
        self.assertEqual(len(out), 1)
        self.assertIn("[#%d]" % c.id, out[0]["onde"])
        self.env["afr.relatorio.leitura.ib"].create({
            "relatorio_id": self.rel.id, "cycle_id": c.id,
            "resultado": "negativo", "data_leitura": self.D_FIM,
        })
        self.assertEqual(self._run("IB_SEM_LEITURA"), [])

    def test_ib_vencido(self):
        ind = self.env["afr.relatorio.indicador"].create({
            "relatorio_id": self.rel.id, "tipo": "biologico", "lote": "L-TESTE",
            "validade": self.D_FIM - timedelta(days=1),
        })
        out = self._run("IB_VENCIDO")
        self.assertEqual(len(out), 1)
        self.assertIn("L-TESTE", out[0]["mensagem"])
        ind.validade = self.D_FIM
        self.assertEqual(self._run("IB_VENCIDO"), [])

    # --- anexos -------------------------------------------------------------
    def test_anexo_vazio(self):
        a = self._anexo(code="dados")
        out = self._run("ANEXO_VAZIO")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")
        a.included = False
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    # Ruling 1.3 (P5 T2): a regra roda _check_files() em TODO anexo incluído,
    # inclusive slot_kind='bloco' — cujo _check_files() (P4) devolve
    # PROBLEM_EMPTY quando o block_id está ausente/excluído. Substitui o
    # teste único do brief ("ignora slot bloco") por dois: com e sem bloco.
    def test_anexo_vazio_bloco_sem_bloco_vinculado(self):
        self._anexo(code="protocolo", title="Protocolo", slot_kind="bloco")
        out = self._run("ANEXO_VAZIO")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")

    def test_anexo_vazio_bloco_com_bloco_vinculado(self):
        block = self._block("<p>Conteúdo</p>", title="Protocolo")
        anexo = self._anexo(code="protocolo", title="Protocolo", slot_kind="bloco")
        anexo.block_id = block.id
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    def test_anexo_ilegivel(self):
        self._anexo(code="dados", pdfs=[make_pdf("ok"), b"%PDF-1.4 lixo corrompido"])
        out = self._run("ANEXO_ILEGIVEL")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    def test_anexo_todo_ilegivel_e_ilegivel_nao_vazio(self):
        self._anexo(code="dados", pdfs=[b"%PDF-1.4 lixo corrompido"])
        self.assertEqual(len(self._run("ANEXO_ILEGIVEL")), 1)
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    def test_anexo_legivel_sem_achado(self):
        self._anexo(code="dados", pdfs=[make_pdf("ok")])
        self.assertEqual(self._run("ANEXO_ILEGIVEL"), [])
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    # --- tokens -------------------------------------------------------------
    def test_token_nao_resolvido(self):
        self._block("<p>Valor: {{ relatorio.name</p>", title="Objetivo")
        out = self._run("TOKEN_NAO_RESOLVIDO")
        self.assertEqual(len(out), 1)
        self.assertIn("Objetivo", out[0]["onde"])

    def test_token_resolvido(self):
        self._block("<p>Nº {{ relatorio.name }}</p>", title="Objetivo")
        self.assertEqual(self._run("TOKEN_NAO_RESOLVIDO"), [])

    def test_token_nao_resolvido_ignora_capa_e_indice(self):
        """Fix round 1, achado 1: `reports/relatorio_corpo_templates.xml`
        (`rq_block`) só chama `doc._render_block_body(block)` para
        `block_kind not in ('capa', 'indice', 'anexo_separador')` — capa e
        índice têm sub-template próprio (`rq_block_capa`/`rq_block_indice`)
        e nunca passam pelo render de `{{ }}`. Um '{{' cru no body de uma
        capa/índice nunca aparece no PDF; `rendered_blocks()` precisa
        excluir os dois, senão a regra acusa um bloqueio falso."""
        self._block("<p>{{ relatorio.name</p>", title="Capa", kind="capa")
        self._block("<p>{{ relatorio.name</p>", title="Índice", kind="indice")
        self.assertEqual(self._run("TOKEN_NAO_RESOLVIDO"), [])

    def test_token_nao_resolvido_erro_de_render_isola_e_loga(self):
        """Fix round 1, achado 2: erro de render de UM bloco não pode
        deixar o cursor num estado ruim pros blocos seguintes (savepoint
        por bloco, no mesmo padrão de `run_rules`) nem passar em silêncio
        (log). Precisa ser um erro de BANCO (divisão por zero), não um
        `RuntimeError` comum: este último nunca aborta a transação do
        Postgres, então o teste passaria com ou sem o savepoint por bloco.
        Com o erro de banco, sem o savepoint a transação fica "aborted" e o
        render do `late_block` (depois do `boom_block` na ordem de
        `_body_blocks()`, mesma `sequence`, id maior) também falharia — o
        que prova que o savepoint recupera o cursor entre um bloco e o
        seguinte."""
        ok_block = self._block("<p>Nº {{ relatorio.name }}</p>", title="Ok")
        boom_block = self._block("<p>Boom</p>", title="Boom")
        late_block = self._block("<p>{{ relatorio.name</p>", title="Depois do boom")
        original = type(self.rel)._render_block_body

        def fake_render(rel_self, block):
            if block.id == boom_block.id:
                rel_self.env.cr.execute("SELECT 1/0")
                return ""
            return original(rel_self, block)

        with patch.object(type(self.rel), "_render_block_body", fake_render), \
                mute_logger("odoo.sql_db"):
            with self.assertLogs(relatorio_rules.__name__, level="ERROR") as cm:
                out = run_rules(self.rel)

        self.assertTrue(any(str(boom_block.id) in msg for msg in cm.output))
        boom_onde = "Bloco: %s" % relatorio_rules.block_label(boom_block)
        boom_findings = [
            f for f in out
            if f["codigo"] == "TOKEN_NAO_RESOLVIDO" and f["onde"] == boom_onde
        ]
        self.assertEqual(len(boom_findings), 1)
        self.assertIn("division by zero", boom_findings[0]["mensagem"].lower())

        # o savepoint recupera o cursor: o bloco seguinte é avaliado
        # normalmente (achado de token não resolvido DELE MESMO, não um
        # "erro ao renderizar" causado pela transação abortada do bloco
        # anterior).
        late_onde = "Bloco: %s" % relatorio_rules.block_label(late_block)
        late_findings = [f for f in out if f["onde"] == late_onde]
        self.assertEqual(len(late_findings), 1)
        self.assertIn("Token '{{' não resolvido", late_findings[0]["mensagem"])

        ok_onde = "Bloco: %s" % relatorio_rules.block_label(ok_block)
        self.assertFalse([f for f in out if f["onde"] == ok_onde])
        # outras regras do registro seguiram rodando normalmente
        self.assertTrue(any(f["codigo"] == "CERT_DEPOIS_AUSENTE" for f in out))

    def test_anexo_check_files_memoizado_por_run(self):
        """Fix round 1, achado 3: ANEXO_VAZIO e ANEXO_ILEGIVEL percorrem o
        MESMO conjunto de anexos incluídos; sem memoização, cada anexo
        chamava `_check_files()` duas vezes por `run_rules()`."""
        self._anexo(code="dados", pdfs=[make_pdf("ok")])
        Anexo = self.env["afr.relatorio.anexo"]
        original = type(Anexo)._check_files
        calls = []

        def counting(self_anexo):
            calls.append(self_anexo.id)
            return original(self_anexo)

        with patch.object(type(Anexo), "_check_files", counting):
            run_rules(self.rel)
        self.assertEqual(len(calls), 1)

    def test_token_nao_resolvido_ignora_bloco_de_anexo_excluido(self):
        """Ruling 1.4/1.6: a regra só percorre `rendered_blocks(rel)` — um
        bloco de conteúdo de anexo (`slot_kind='bloco'`) só entra quando o
        anexo está incluído. Com `block_ids.filtered("included")` cru (o
        que o brief original propunha) este teste pegaria falso positivo,
        já que o bloco continua `included=True` mesmo com o anexo excluído."""
        block = self._block("<p>{{ relatorio.name</p>", title="Protocolo")
        block.anexo_code = "protocolo"
        anexo = self._anexo(
            code="protocolo", title="Protocolo", slot_kind="bloco", included=False)
        anexo.block_id = block.id
        self.assertEqual(self._run("TOKEN_NAO_RESOLVIDO"), [])
        anexo.included = True
        out = self._run("TOKEN_NAO_RESOLVIDO")
        self.assertEqual(len(out), 1)

    # --- runner -------------------------------------------------------------
    def test_run_rules_regra_quebrada_vira_bloqueio(self):
        def boom(rel):
            raise RuntimeError("falha simulada")

        with patch.dict(relatorio_rules.RULES, {"CERT_ANTES_AUSENTE": boom}):
            with self.assertLogs(relatorio_rules.__name__, level="ERROR") as cm:
                out = run_rules(self.rel)
        self.assertTrue(any("CERT_ANTES_AUSENTE" in msg for msg in cm.output))
        broken = [f for f in out if f["codigo"] == "CERT_ANTES_AUSENTE"]
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0]["gravidade"], "bloqueia")
        self.assertIn("falha simulada", broken[0]["mensagem"])
        # as demais regras continuaram rodando
        self.assertTrue(any(f["codigo"] == "CERT_DEPOIS_AUSENTE" for f in out))


EXPECTED_CODES = {
    "CERT_DEPOIS_AUSENTE", "CERT_ANTES_AUSENTE", "PADRAO_VENCIDO",
    "IB_SEM_LEITURA", "IB_VENCIDO", "ANEXO_VAZIO", "ANEXO_ILEGIVEL",
    "TOKEN_NAO_RESOLVIDO", "ANEXO_REF_EXCLUIDO", "CICLOS_CONTAGEM",
    "CICLO_SEM_DADOS", "CICLO_SEM_JANELA", "DATA_FORA_JANELA",
    "AMBIENTE_VAZIO", "CHECKLIST_REPROVADO", "CANAL_SEM_CERT",
    "APROVACAO_INTERNA",
}


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRelatorioRulesAlerta(_RulesMixin, RelatorioTestCommon):

    def test_registro_completo(self):
        self.assertEqual(set(RULES), EXPECTED_CODES)

    def test_anexo_ref_excluido(self):
        self._block("<p>Ver Anexo {{ anexo('micro') }}.</p>", title="Conclusão")
        out = self._run("ANEXO_REF_EXCLUIDO")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "alerta")
        self.assertIn("micro", out[0]["mensagem"])
        self._anexo(code="micro", title="Laudo microbiológico")
        self.assertEqual(self._run("ANEXO_REF_EXCLUIDO"), [])

    def test_anexo_ref_excluido_com_aspas_escapadas(self):
        self._block("<p>Ver Anexo {{ anexo(&#39;f0&#39;) }}.</p>", title="Resultados")
        out = self._run("ANEXO_REF_EXCLUIDO")
        self.assertEqual(len(out), 1)
        self.assertIn("f0", out[0]["mensagem"])

    def test_ciclos_contagem(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qd_cmax.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 2,
            "equipment_id": self.equip1.id,
        })
        self.os.sale_order_id = so
        self._cycle(state="passed", seq=1, sale_order_line_id=line.id)
        c2 = self._cycle(state="pending", seq=2, sale_order_line_id=line.id)
        out = self._run("CICLOS_CONTAGEM")
        self.assertEqual(len(out), 1)
        self.assertIn("2 contratado(s), 1 executado(s)", out[0]["mensagem"])
        # Fix round 1, minor: onde inclui [#id do cycle_type] (Decisão 10 —
        # chave de carry-over estável quando o rótulo pode se repetir).
        self.assertIn("[#%d]" % self.cycle_cmax.id, out[0]["onde"])
        c2.state = "passed"
        self.assertEqual(self._run("CICLOS_CONTAGEM"), [])

    def test_ciclo_sem_dados(self):
        c = self._cycle()
        self.assertEqual(len(self._run("CICLO_SEM_DADOS")), 1)
        self.env["afr.qualificacao.collect.item"].create({
            "name": "Dados do validador",
            "qualif_id": self.qd.id,
            "cycle_id": c.id,
            "kind": "pdf",
            "state": "collected",
            "file": base64.b64encode(make_pdf("dados")),
            "filename": "dados.pdf",
            "mimetype": "application/pdf",
        })
        self.assertEqual(self._run("CICLO_SEM_DADOS"), [])

    # Ruling 1.9 (P5 T3): a detecção de PDF passa por _afr_resolve_mimetype
    # (mesmo sniff de P2/P4) — o PWA grava application/octet-stream mesmo
    # para PDFs reais, e a regra não pode acusar CICLO_SEM_DADOS nesse caso.
    def test_ciclo_sem_dados_sniffa_mimetype_octet_stream(self):
        c = self._cycle()
        self.env["afr.qualificacao.collect.item"].create({
            "name": "Dados do validador",
            "qualif_id": self.qd.id,
            "cycle_id": c.id,
            "kind": "pdf",
            "state": "collected",
            "file": base64.b64encode(make_pdf("dados")),
            "filename": "dados.dat",
            "mimetype": "application/octet-stream",
        })
        self.assertEqual(self._run("CICLO_SEM_DADOS"), [])

    def test_ciclo_sem_janela(self):
        c = self._cycle()
        self.assertEqual(len(self._run("CICLO_SEM_JANELA")), 1)
        c.write({
            "janela_inicio": datetime(2026, 7, 1, 10, 0),
            "janela_fim": datetime(2026, 7, 1, 10, 30),
        })
        self.assertEqual(self._run("CICLO_SEM_JANELA"), [])

    def test_ciclo_janela_invertida(self):
        # Ruling 1.7/0.3 (P1-A3): a constraint de P1 proíbe janela_fim <
        # janela_inicio na criação; fim == início é o caso extremo que a
        # constraint permite e a regra ainda deve acusar (`<=`).
        self._cycle(janela_inicio=datetime(2026, 7, 1, 11, 0),
                    janela_fim=datetime(2026, 7, 1, 11, 0))
        out = self._run("CICLO_SEM_JANELA")
        self.assertEqual(len(out), 1)
        self.assertIn("anterior", out[0]["mensagem"])

    # Ruling 0.3 (P5 T3): item de coleta collected exige arquivo
    # (`_check_required_has_file`) — o fixture do brief original não
    # anexava file/filename/mimetype e falharia na constraint.
    def _coleta(self, captured_at):
        return self.env["afr.qualificacao.collect.item"].create({
            "name": "Foto do painel",
            "qualif_id": self.qd.id,
            "kind": "foto",
            "state": "collected",
            "captured_at": captured_at,
            "file": base64.b64encode(make_pdf("foto")),
            "filename": "foto.pdf",
            "mimetype": "application/pdf",
        })

    def test_data_fora_janela(self):
        self._coleta(datetime(2025, 7, 2, 12, 0))
        out = self._run("DATA_FORA_JANELA", {"tz": "UTC"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "alerta")

    def test_data_dentro_janela(self):
        self._coleta(datetime(2026, 7, 2, 12, 0))
        self.assertEqual(self._run("DATA_FORA_JANELA", {"tz": "UTC"}), [])

    def test_data_fora_janela_respeita_fuso(self):
        # 01:30 UTC de 04/07 = 22:30 de 03/07 em Brasília (último dia de ensaio)
        self._coleta(datetime(2026, 7, 4, 1, 30))
        self.assertEqual(self._run("DATA_FORA_JANELA", {"tz": "America/Sao_Paulo"}), [])
        self.assertEqual(len(self._run("DATA_FORA_JANELA", {"tz": "UTC"})), 1)

    def test_ambiente_vazio(self):
        self.assertEqual(self._run("AMBIENTE_VAZIO"), [])
        self.rel.write({"amb_umidade": " "})
        out = self._run("AMBIENTE_VAZIO")
        self.assertEqual(len(out), 1)
        self.assertIn("Umidade", out[0]["onde"])

    def test_checklist_reprovado(self):
        Check = self.env["afr.relatorio.checklist"]
        Check.create({"relatorio_id": self.rel.id, "grupo": "Instalações elétricas",
                      "descricao": "Aterramento", "status": "aprovado", "sequence": 1})
        self.assertEqual(self._run("CHECKLIST_REPROVADO"), [])
        Check.create({"relatorio_id": self.rel.id, "grupo": "Instalações elétricas",
                      "descricao": "Disjuntor dedicado", "status": "reprovado",
                      "comentario": "Compartilhado", "sequence": 2})
        out = self._run("CHECKLIST_REPROVADO")
        self.assertEqual(len(out), 1)
        self.assertIn("Disjuntor dedicado", out[0]["mensagem"])

    def test_canal_sem_cert(self):
        self._validator(channels=28)
        c = self._cycle()
        Pos = self.env["afr.relatorio.sensor.pos"]
        Pos.create({"cycle_id": c.id, "canal": "CH012", "posicao": "Centro", "sequence": 1})
        self.assertEqual(self._run("CANAL_SEM_CERT"), [])
        pos030 = Pos.create({"cycle_id": c.id, "canal": "CH030", "posicao": "Dreno", "sequence": 2})
        out = self._run("CANAL_SEM_CERT")
        self.assertEqual(len(out), 1)
        self.assertIn("CH030", out[0]["mensagem"])
        # Fix round 1, minor: onde inclui [#id do sensor.pos] (Decisão 10).
        self.assertIn("[#%d]" % pos030.id, out[0]["onde"])

    def test_canal_sem_validador_silencioso(self):
        c = self._cycle()
        self.env["afr.relatorio.sensor.pos"].create(
            {"cycle_id": c.id, "canal": "CH099", "posicao": "Topo", "sequence": 1})
        self.assertEqual(self._run("CANAL_SEM_CERT"), [])

    def test_aprovacao_interna_so_na_emissao(self):
        self.assertEqual(self._run("APROVACAO_INTERNA"), [])
        out = self._run("APROVACAO_INTERNA", {relatorio_rules.EMISSION_CTX: True})
        self.assertTrue(out)
        self.assertTrue(all(f["gravidade"] == "bloqueia" for f in out))
        self._approve_internal()
        self.assertEqual(self._run("APROVACAO_INTERNA", {relatorio_rules.EMISSION_CTX: True}), [])

    def test_aprovacao_interna_espelha_o_gate(self):
        """Fix round 1: a review encontrou uma divergência entre a regra e o
        gate (`_check_emission_gate` → `_rq_internal_approval_problems()`,
        P4) — uma linha aprovada cujo usuário foi removido depois
        (`user_id` esvaziado, `approved_at` intacto) fazia o gate bloquear
        mas a regra antiga (que só olhava `not approved_at` por papel)
        ficava em silêncio. A regra agora DERIVA do mesmo método do gate,
        então as duas nunca podem discordar — testado comparando as
        mensagens, não só a contagem.

        Cobre num único cenário (papel elaborador com duas linhas):
        - uma linha pendente COM usuário designado ("ainda não aprovou");
        - uma linha SEM usuário designado ("sem usuário designado");
        e (papel emissor):
        - uma linha JÁ aprovada cujo `user_id` foi esvaziado via SQL direto
          — bypassando o `write()` do model, que auto-invalida
          `approved_at` sempre que um campo de identidade muda numa linha
          já aprovada (`_IDENTITY_FIELDS`/`changed.sudo().write(...)` em
          `models/relatorio_aprovacao.py`); não há caminho pelo ORM para
          chegar a "aprovado + sem usuário" — só um FK `ondelete` do
          usuário (fora do form) ou, aqui, SQL cru reproduzem o estado.
        """
        Aprov = self.env["afr.relatorio.aprovacao"]
        elab_pendente = Aprov.create({
            "relatorio_id": self.rel.id, "papel": "elaborador", "sequence": 1,
            "user_id": self.user_qualif.id,
        })
        elab_sem_usuario = Aprov.create({
            "relatorio_id": self.rel.id, "papel": "elaborador", "sequence": 2,
        })
        emissor_orfao = Aprov.create({
            "relatorio_id": self.rel.id, "papel": "emissor", "sequence": 3,
            "user_id": self.user_qualif.id,
        })
        emissor_orfao.sudo().write({
            "approved_at": datetime.now(), "ip": "127.0.0.1",
        })
        # SQL direto: simula o usuário removido depois da aprovação sem
        # passar pelo write() do model (que zeraria approved_at de volta).
        self.env.cr.execute(
            "UPDATE afr_relatorio_aprovacao SET user_id = NULL WHERE id = %s",
            (emissor_orfao.id,),
        )
        emissor_orfao.invalidate_recordset()
        self._refresh()

        gate_problems = self.rel._rq_internal_approval_problems()
        # As três situações realmente geraram problema no gate (senão o
        # teste não prova nada sobre a divergência).
        self.assertEqual(len(gate_problems), 3)
        self.assertTrue(any("sem usuário designado" in m for m in gate_problems))
        self.assertTrue(any("ainda não aprovou" in m for m in gate_problems))

        out = self._run("APROVACAO_INTERNA", {relatorio_rules.EMISSION_CTX: True})
        self.assertEqual(len(out), len(gate_problems))
        self.assertEqual([f["mensagem"] for f in out], gate_problems)
        self.assertTrue(all(f["gravidade"] == "bloqueia" for f in out))
        # onde estável por papel + [#id da linha] quando o papel repete
        # (Decisão 10 — elaborador tem duas linhas problemáticas aqui).
        self.assertIn("[#%d]" % elab_pendente.id, out[0]["onde"])
        self.assertIn("[#%d]" % elab_sem_usuario.id, out[1]["onde"])
        self.assertIn("[#%d]" % emissor_orfao.id, out[2]["onde"])
