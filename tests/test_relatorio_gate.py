"""P5 — achado (model), verificação/carry-over, gate de emissão, snapshot."""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common_relatorio import RelatorioTestCommon


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestAchadoModel(RelatorioTestCommon):

    def test_usuario_nao_cria_achado_fora_da_varredura(self):
        Achado = self.env["afr.relatorio.achado"].with_user(self.user_qualif)
        with self.assertRaises(AccessError):
            Achado.create({
                "relatorio_id": self.rel.id, "origem": "regra", "codigo": "X",
                "gravidade": "alerta", "mensagem": "forjado", "onde": "X",
                "decisao": "descartado", "motivo": "plantado",
            })

    def test_contexto_scan_nao_autoriza_usuario(self):
        """SCAN_CTX vem do cliente RPC — não pode abrir o guard."""
        Achado = self.env["afr.relatorio.achado"].with_user(
            self.user_qualif).with_context(afr_scan_internal=True)
        with self.assertRaises(AccessError):
            Achado.create({
                "relatorio_id": self.rel.id, "origem": "regra", "codigo": "X",
                "gravidade": "alerta", "mensagem": "forjado", "onde": "X",
            })
        a = self._mk_achado().with_user(self.user_qualif).with_context(
            afr_scan_internal=True)
        with self.assertRaises(AccessError):
            a.write({"decidido_por": self.env.ref("base.user_admin").id})

    def test_descartado_exige_motivo(self):
        a = self._mk_achado()
        with self.assertRaises(ValidationError):
            a.write({"decisao": "descartado", "motivo": "   "})

    def test_decisao_carimba_e_limpa(self):
        a = self._mk_achado()
        a.write({"decisao": "descartado", "motivo": "Falso positivo conferido."})
        self.assertEqual(a.decidido_por, self.env.user)
        self.assertTrue(a.decidido_em)
        a.write({"decisao": "pendente"})
        self.assertFalse(a.decidido_por)
        self.assertFalse(a.decidido_em)

    def test_bloqueia_nao_aceita_decisao(self):
        a = self._mk_achado(gravidade="bloqueia")
        with self.assertRaises(ValidationError):
            a.write({"decisao": "procede"})

    def test_usuario_so_grava_decisao_e_motivo(self):
        a = self._mk_achado().with_user(self.user_qualif)
        a.write({"decisao": "descartado", "motivo": "Conferido em campo."})
        self.assertEqual(a.decisao, "descartado")
        with self.assertRaises(AccessError):
            a.write({"gravidade": "info"})

    def test_has_blocking_e_resumo(self):
        self.assertFalse(self.rel.has_blocking)
        self._mk_achado(gravidade="bloqueia", mensagem="Falta certificado depois")
        self._mk_achado(gravidade="alerta", mensagem="Ambiente vazio")
        self._refresh()
        self.assertTrue(self.rel.has_blocking)
        self.assertIn("Falta certificado depois", self.rel.blocking_summary)
        self.assertNotIn("Ambiente vazio", self.rel.blocking_summary)
        self.assertEqual(self.rel.achado_pendente_count, 2)
