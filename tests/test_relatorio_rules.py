"""P5 — regras determinísticas da varredura: positivo + negativo por regra."""
from datetime import timedelta
from unittest.mock import patch

from odoo.tests import tagged

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
            out = run_rules(self.rel)
        broken = [f for f in out if f["codigo"] == "CERT_ANTES_AUSENTE"]
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0]["gravidade"], "bloqueia")
        self.assertIn("falha simulada", broken[0]["mensagem"])
        # as demais regras continuaram rodando
        self.assertTrue(any(f["codigo"] == "CERT_DEPOIS_AUSENTE" for f in out))
