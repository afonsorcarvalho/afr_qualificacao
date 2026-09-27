"""P5 — revisão por IA (OpenRouter) com requests.post mockado."""
import io
import logging
from unittest.mock import MagicMock, patch

import requests
from reportlab.pdfgen import canvas

from odoo.tests import tagged

from ..models import relatorio_ai
from ..models.relatorio_ai import (
    CODIGO_IA,
    CODIGO_INDISPONIVEL,
    DEFAULT_MODEL,
    MAX_CHUNK_CHARS,
    OPENROUTER_URL,
    parse_ai_json,
    pdf_to_text,
    truncate,
)
from .common_relatorio import RelatorioTestCommon, make_pdf

POST = "odoo.addons.afr_qualificacao.models.relatorio_ai.requests.post"
NOW = "odoo.addons.afr_qualificacao.models.relatorio_ai._now"

VALID = '{"achados": [{"gravidade": "alerta", "onde": "Capa", "trecho": "TAG AC-99", "explicacao": "TAG diverge do cartão."}]}'


def _resp(content):
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {"choices": [{"message": {"content": content}}]}
    return m


def _pdf_pages(*texts):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for text in texts:
        c.drawString(72, 720, text)
        c.showPage()
    c.save()
    return buf.getvalue()


class _Clock:
    """Relógio falso: `post` avança `step` segundos a cada chamada."""

    def __init__(self, step, content=VALID):
        self.t = 1000.0
        self.step = step
        self.content = content

    def now(self):
        return self.t

    def post(self, *args, **kwargs):
        self.t += self.step
        return _resp(self.content)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRelatorioAiPure(RelatorioTestCommon):

    def test_parse_json_puro(self):
        self.assertEqual(len(parse_ai_json(VALID)), 1)

    def test_parse_json_com_cerca(self):
        self.assertEqual(len(parse_ai_json("Segue:\n```json\n%s\n```\nFim." % VALID)), 1)

    def test_parse_json_com_texto_em_volta(self):
        self.assertEqual(len(parse_ai_json("Resultado: %s obrigado" % VALID)), 1)

    def test_parse_lixo(self):
        with self.assertRaises(ValueError):
            parse_ai_json("não encontrei nada de errado")
        with self.assertRaises(ValueError):
            parse_ai_json('{"resultado": []}')

    def test_truncate(self):
        self.assertEqual(truncate("abc"), "abc")
        long_text = "x" * (MAX_CHUNK_CHARS * 3)
        self.assertEqual(len(truncate(long_text)), MAX_CHUNK_CHARS)
        self.assertIn("truncado", truncate(long_text))

    def test_pdf_to_text_para_no_limite(self):
        """Ruling 1.14: a extração para quando o texto atinge o limite."""
        data = _pdf_pages("Pagina um " + "a" * 60, "Pagina dois", "Pagina tres")
        self.assertIn("Pagina tres", pdf_to_text(data))
        curto = pdf_to_text(data, limit=20)
        self.assertIn("Pagina um", curto)
        self.assertNotIn("Pagina dois", curto)
        self.assertNotIn("Pagina tres", curto)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRelatorioAi(RelatorioTestCommon):

    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()
        self.icp.set_param(relatorio_ai.PARAM_ENABLED, "True")
        self.icp.set_param(relatorio_ai.PARAM_API_KEY, "sk-test")
        self.AI = self.env["afr.relatorio.ai"]

    def test_desligada_nao_chama(self):
        self.icp.set_param(relatorio_ai.PARAM_ENABLED, False)
        with patch(POST) as post:
            self.assertEqual(self.AI.review(self.rel), [])
        post.assert_not_called()

    def test_sem_chave_vira_indisponivel_sem_chamar(self):
        self.icp.set_param(relatorio_ai.PARAM_API_KEY, False)
        with patch(POST) as post:
            out = self.AI.review(self.rel)
        post.assert_not_called()
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])
        self.assertEqual(out[0]["gravidade"], "info")

    def test_json_valido(self):
        with patch(POST, return_value=_resp(VALID)) as post:
            out = self.AI.review(self.rel)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["codigo"], CODIGO_IA)
        self.assertEqual(out[0]["gravidade"], "alerta")
        self.assertTrue(out[0]["mensagem"].startswith("IA — verificar"))
        args, kwargs = post.call_args
        self.assertEqual(args[0], OPENROUTER_URL)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(kwargs["json"]["model"], DEFAULT_MODEL)
        self.assertEqual(kwargs["timeout"], 60)
        user_msg = kwargs["json"]["messages"][1]["content"]
        self.assertIn(self.rel.name, user_msg)  # cartão de identidade

    def test_json_com_cerca(self):
        with patch(POST, return_value=_resp("```json\n%s\n```" % VALID)):
            out = self.AI.review(self.rel)
        self.assertEqual([f["codigo"] for f in out], [CODIGO_IA])

    def test_lixo_vira_indisponivel(self):
        with patch(POST, return_value=_resp("Tudo certo, nada a apontar.")):
            out = self.AI.review(self.rel)
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])
        self.assertEqual(out[0]["gravidade"], "info")

    def test_timeout_interrompe_e_vira_indisponivel(self):
        self._anexo(code="dados", pdfs=[make_pdf("Ciclo 1 dados")])
        with patch(POST, side_effect=requests.Timeout("lento")) as post:
            out = self.AI.review(self.rel)
        self.assertEqual(post.call_count, 1)  # não tenta o 2º trecho
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])

    def test_connection_error_vira_indisponivel(self):
        with patch(POST, side_effect=requests.ConnectionError("offline")):
            out = self.AI.review(self.rel)
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])

    def test_erro_http_nao_vaza_chave(self):
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError(
            "401 Client Error: Unauthorized for url: %s" % OPENROUTER_URL)
        with patch(POST, return_value=resp), \
                self.assertLogs(relatorio_ai._logger.name, level="WARNING") as logs:
            out = self.AI.review(self.rel)
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])
        self.assertNotIn("sk-test", "\n".join(logs.output))
        self.assertNotIn("sk-test", out[0]["mensagem"])

    def test_gravidade_bloqueia_da_ia_vira_alerta(self):
        content = '{"achados": [{"gravidade": "bloqueia", "onde": "x", "trecho": "y", "explicacao": "z"}, {"gravidade": "info", "onde": "a", "trecho": "b", "explicacao": "c"}]}'
        with patch(POST, return_value=_resp(content)):
            out = self.AI.review(self.rel)
        self.assertEqual(sorted(f["gravidade"] for f in out), ["alerta", "info"])

    def test_onde_repetido_nao_colide(self):
        """`_run_verificacao` deduplica por (origem, codigo, onde)."""
        content = '{"achados": [{"gravidade": "alerta", "onde": "Tabela 1", "trecho": "a", "explicacao": "x"}, {"gravidade": "alerta", "onde": "Tabela 1", "trecho": "b", "explicacao": "y"}]}'
        with patch(POST, return_value=_resp(content)):
            out = self.AI.review(self.rel)
        self.assertEqual(len({f["onde"] for f in out}), 2)

    def test_chunk_truncado(self):
        self._block("<p>%s</p>" % ("palavra " * 5000), title="Longo")
        chunks = self.AI._build_chunks(self.rel)
        self.assertTrue(all(len(c["text"]) <= MAX_CHUNK_CHARS for c in chunks))

    def test_corpo_usa_blocos_renderizados(self):
        """Ruling 1.4/1.6: bloco excluído não vai para a IA."""
        self._block("<p>Texto incluido</p>", title="Incluido")
        self._block("<p>Texto excluido</p>", title="Excluido", included=False)
        body = self.AI._build_chunks(self.rel)[0]["text"]
        self.assertIn("Texto incluido", body)
        self.assertNotIn("Texto excluido", body)

    def test_chunk_por_anexo_com_texto_do_pdf(self):
        self._anexo(code="dados", title="Dados do validador", pdfs=[make_pdf("Ciclo 1 dados")])
        chunks = self.AI._build_chunks(self.rel)
        self.assertEqual(len(chunks), 2)
        self.assertIn("Ciclo 1", chunks[1]["text"])
        with patch(POST, return_value=_resp('{"achados": []}')) as post:
            self.assertEqual(self.AI.review(self.rel), [])
        self.assertEqual(post.call_count, 2)

    def test_orcamento_reduz_timeout_da_chamada_seguinte(self):
        """Ruling 1.14: timeout de cada chamada = min(timeout, restante)."""
        self._anexo(code="dados", pdfs=[make_pdf("Ciclo 1 dados")])
        clock = _Clock(step=20, content='{"achados": []}')
        with patch(NOW, side_effect=clock.now), \
                patch(POST, side_effect=clock.post) as post:
            self.assertEqual(self.AI.review(self.rel), [])
        self.assertEqual([c.kwargs["timeout"] for c in post.call_args_list], [60, 40])

    def test_orcamento_esgotado_pula_trechos(self):
        self._anexo(code="dados", title="Dados do validador",
                    pdfs=[make_pdf("Ciclo 1 dados")])
        self._anexo(code="ib", title="Leitura IB", pdfs=[make_pdf("Leitura 1")])
        clock = _Clock(step=58)
        with patch(NOW, side_effect=clock.now), \
                patch(POST, side_effect=clock.post) as post:
            out = self.AI.review(self.rel)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(sorted(f["codigo"] for f in out), [CODIGO_IA, CODIGO_INDISPONIVEL])
        indisp = [f for f in out if f["codigo"] == CODIGO_INDISPONIVEL][0]
        self.assertEqual(indisp["gravidade"], "info")
        self.assertIn("Dados do validador", indisp["mensagem"])
        self.assertIn("Leitura IB", indisp["mensagem"])

    def test_resposta_invalida_e_orcamento_dao_um_so_indisponivel(self):
        self._anexo(code="dados", title="Dados do validador",
                    pdfs=[make_pdf("Ciclo 1 dados")])
        clock = _Clock(step=58, content="nada a apontar")
        with patch(NOW, side_effect=clock.now), patch(POST, side_effect=clock.post):
            out = self.AI.review(self.rel)
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])

    def test_falha_ao_montar_trechos_vira_indisponivel(self):
        with patch.object(type(self.AI), "_build_chunks", side_effect=RuntimeError("boom")), \
                patch(POST) as post:
            out = self.AI.review(self.rel)
        post.assert_not_called()
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])

    def test_verificar_grava_achado_de_ia(self):
        with patch(POST, return_value=_resp(VALID)):
            self.rel.action_verificar()
        ia = self.rel.achado_ids.filtered(lambda a: a.origem == "ia")
        self.assertEqual(ia.mapped("codigo"), [CODIGO_IA])

    def test_settings_gravam_parametros(self):
        self.env["res.config.settings"].create({
            "afr_ai_enabled": True,
            "afr_ai_model": "provedor/modelo-teste",
            "afr_ai_timeout": 30,
        }).execute()
        self.assertEqual(self.icp.get_param(relatorio_ai.PARAM_MODEL), "provedor/modelo-teste")
        self.assertEqual(self.icp.get_param(relatorio_ai.PARAM_TIMEOUT), "30")
        self.assertTrue(self.AI._is_enabled())
