"""P5 — regras determinísticas da varredura: positivo + negativo por regra."""
from datetime import timedelta
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
