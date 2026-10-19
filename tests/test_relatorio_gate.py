"""P5 — achado (model), verificação/carry-over, gate de emissão, snapshot."""
import json

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common_relatorio import RelatorioTestCommon
from .relatorio_fakes import FakeCorpo, run_build_jobs


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

    def test_unlink_restrito_a_su(self):
        """Item 8 (P5 final fix wave): o Gestor tem unlink=1 na ACL de
        afr.relatorio.achado (convenção de CRUD completo dos demais
        modelos), mas apagar um achado manualmente contornaria o gate —
        ex.: um alerta de IA pendente que simplesmente desaparece sem
        decisão. Só a varredura interna (sudo) remove achados; a ACL
        continua igual (item mantém a permissão ampla, o model é que
        restringe)."""
        a = self._mk_achado()
        with self.assertRaises(AccessError):
            a.with_user(self.user_manager).unlink()
        self.assertTrue(a.exists())

    def test_has_blocking_e_resumo(self):
        self.assertFalse(self.rel.has_blocking)
        self._mk_achado(gravidade="bloqueia", mensagem="Falta certificado depois")
        self._mk_achado(gravidade="alerta", mensagem="Ambiente vazio")
        self._refresh()
        self.assertTrue(self.rel.has_blocking)
        self.assertIn("Falta certificado depois", self.rel.blocking_summary)
        self.assertNotIn("Ambiente vazio", self.rel.blocking_summary)
        self.assertEqual(self.rel.achado_pendente_count, 2)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestVerificar(RelatorioTestCommon):

    def test_verificar_exige_rascunho(self):
        self.rel.state = "issued"
        with self.assertRaises(UserError):
            self.rel.action_verificar()

    def test_verificar_exige_permissao_de_escrita(self):
        """Item 3 (P5 final fix wave): action_verificar não escreve no
        relatório diretamente (só cria achados via sudo internamente), então
        sem um check explícito um Técnico (leitura apenas na ACL do
        relatório) conseguiria disparar a varredura por RPC."""
        with self.assertRaises(AccessError):
            self.rel.with_user(self.user_technician).action_verificar()

    def test_verificar_grava_achados_de_regra(self):
        self.rel.action_verificar()
        a = self._achado("CERT_DEPOIS_AUSENTE")
        self.assertEqual(len(a), 1)
        self.assertEqual(a.origem, "regra")
        self.assertEqual(a.decisao, "pendente")
        self.assertTrue(self.rel.has_blocking)

    def test_pendente_some_quando_corrigido(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self.assertTrue(self._achado("AMBIENTE_VAZIO"))
        self.rel.write({"amb_umidade": "45 %UR"})
        self.rel.action_verificar()
        self.assertFalse(self._achado("AMBIENTE_VAZIO"))
        self.assertFalse(self.rel.has_blocking)

    def test_decisao_carregada_quando_repete(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        a = self._achado("AMBIENTE_VAZIO")
        a.write({"decisao": "descartado", "motivo": "Sala sem higrômetro."})
        self.rel.action_verificar()
        b = self._achado("AMBIENTE_VAZIO")
        self.assertEqual(b.id, a.id)
        self.assertEqual(b.decisao, "descartado")
        self.assertEqual(b.motivo, "Sala sem higrômetro.")

    def test_procede_carregado_quando_repete(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._achado("AMBIENTE_VAZIO").write({"decisao": "procede"})
        self.rel.action_verificar()
        self.assertEqual(self._achado("AMBIENTE_VAZIO").decisao, "procede")

    def test_decidido_apagado_quando_nao_repete(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._achado("AMBIENTE_VAZIO").write({"decisao": "descartado", "motivo": "x"})
        self.rel.write({"amb_umidade": "45 %UR"})
        self.rel.action_verificar()
        self.assertFalse(self._achado("AMBIENTE_VAZIO"))

    def test_verificar_como_usuario(self):
        # Ruling 1.8: um ciclo com sale_order_line_id — o Usuário não tem
        # acesso a sale.order.line, mas cycle_counts() lê via sudo(); a
        # varredura completa (chamada pelo botão) não pode falhar por isso.
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qd_cmax.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 1,
            "equipment_id": self.equip1.id,
        })
        self._cycle(state="passed", seq=1, sale_order_line_id=line.id)
        self.os.sale_order_id = so
        # Confirma a premissa da ruling: sem o sudo() de cycle_counts(), o
        # Usuário realmente não teria como ler a linha de venda.
        with self.assertRaises(AccessError):
            line.with_user(self.user_qualif).read(["qualif_cycle_qty"])

        self.rel.with_user(self.user_qualif).action_verificar()
        self.assertTrue(self._achado("CERT_DEPOIS_AUSENTE"))
        # regra que quebra (ex.: ACL faltando p/ o grupo user) vira bloqueio
        # com o próprio código — não pode passar por achado legítimo
        self._refresh()
        self.assertFalse(self.rel.achado_ids.filtered(
            lambda a: a.mensagem.startswith("Falha ao executar a regra")))

    def test_skip_ai_preserva_achados_de_ia(self):
        ia = self._mk_achado(origem="ia", codigo="IA_ACHADO", onde="Corpo: capa")
        self.rel.with_context(afr_skip_ai=True).action_verificar()
        self.assertTrue(ia.exists())
        self.rel.action_verificar()  # sem skip: IA (desligada) recria só o que vier
        self.assertFalse(ia.exists())

    def test_criacao_ignora_contexto_default_injetado(self):
        """Ruling 1.12: contexto default_* injetado pelo cliente RPC (ex.:
        default_decidido_por/default_decidido_em/default_motivo/
        default_decisao) não pode ser honrado — a criação do achado sempre
        grava decidido_por/decidido_em/motivo=False (achado novo) e
        decisao='pendente', mesmo vindo de um Usuário comum."""
        rel_user = self.rel.with_user(self.user_qualif).with_context(
            default_decidido_por=self.env.ref("base.user_admin").id,
            default_decidido_em="2026-01-01 00:00:00",
            default_motivo="Motivo forjado",
            default_decisao="procede",
        )
        rel_user.action_verificar()
        a = self._achado("CERT_DEPOIS_AUSENTE")
        self.assertTrue(a)
        self.assertEqual(a.decisao, "pendente")
        self.assertFalse(a.decidido_por)
        self.assertFalse(a.decidido_em)
        self.assertFalse(a.motivo)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestGateEmissao(RelatorioTestCommon):

    def _emit(self):
        # mesmo mock dos testes de P4: _render_qweb_pdf devolve HTML em modo teste;
        # action_emitir só enfileira — o job roda em linha aqui (emenda P4)
        with FakeCorpo().patch(self.env):
            result = self.rel.action_emitir()
            run_build_jobs(self.env)
        return result

    def test_gate_bloqueia_com_bloqueio_pendente(self):
        self._approve_internal()
        problems = self.rel._check_emission_gate()
        self.assertTrue(any("CERT_DEPOIS_AUSENTE" in p for p in problems))
        self.assertFalse(any("Falha ao executar a regra" in p for p in problems))
        # Item 7 (P5 final fix wave): o código bloqueante precisa aparecer
        # na mensagem que o usuário efetivamente vê (UserError de
        # action_emitir), não só na lista interna de `problems`.
        with self.assertRaises(UserError) as cm:
            self._emit()
        self.assertIn("CERT_DEPOIS_AUSENTE", str(cm.exception))
        self.assertEqual(self.rel.state, "draft")

    def test_alerta_de_regra_precisa_de_decisao(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self._approve_internal()
        problems = self.rel._check_emission_gate()
        self.assertTrue(any("AMBIENTE_VAZIO" in p for p in problems))
        self.assertFalse(any("Falha ao executar a regra" in p for p in problems))
        self._achado("AMBIENTE_VAZIO").write(
            {"decisao": "descartado", "motivo": "Sala sem higrômetro."})
        self.assertFalse(any("AMBIENTE_VAZIO" in p for p in self.rel._check_emission_gate()))

    def test_alerta_de_ia_pendente_bloqueia_ate_decidir(self):
        self._make_clean()
        self._approve_internal()
        ia = self._mk_achado(origem="ia", codigo="IA_ACHADO", gravidade="alerta",
                             onde="Corpo do relatório: capa")
        problems = self.rel._check_emission_gate()
        self.assertTrue(ia.exists())  # re-verificação na emissão não apaga IA
        self.assertTrue(any("IA_ACHADO" in p for p in problems))
        ia.write({"decisao": "descartado", "motivo": "TAG conferida na plaqueta."})
        self.assertEqual(self.rel._check_emission_gate(), [])
        self.assertEqual(ia.decisao, "descartado")

    def test_info_de_ia_nao_bloqueia(self):
        self._make_clean()
        self._approve_internal()
        ia = self._mk_achado(origem="ia", codigo="IA_ACHADO", gravidade="info",
                             onde="Corpo do relatório: grafia")
        indisp = self._mk_achado(origem="ia", codigo="IA_INDISPONIVEL", gravidade="info",
                                 onde="IA")
        self.assertEqual(self.rel._check_emission_gate(), [])
        self.assertTrue(ia.exists() and indisp.exists())

    def test_aprovacao_interna_nao_duplica_mensagem_do_super(self):
        self._make_clean()
        problems = self.rel._check_emission_gate()
        self.assertFalse(any("APROVACAO_INTERNA" in p for p in problems))
        self.assertTrue(problems)  # vêm do super() de P4

    def test_decisao_pelo_form_nao_zera_aprovacoes(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._approve_internal()
        a = self._achado("AMBIENTE_VAZIO")
        self.rel.write({"achado_ids": [(1, a.id, {"decisao": "descartado", "motivo": "Sem higrômetro."})]})
        self._refresh()
        internas = self.rel.aprovacao_ids.filtered(lambda x: x.papel in ("elaborador", "emissor"))
        self.assertTrue(all(x.approved_at for x in internas))

    def test_emissao_grava_scan_snapshot(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._achado("AMBIENTE_VAZIO").write(
            {"decisao": "descartado", "motivo": "Sala sem higrômetro; registrado em ata."})
        self._approve_internal()
        self._emit()
        self._refresh()
        self.assertEqual(self.rel.state, "issued")
        snap = json.loads(self.rel.current_emissao_id.scan_snapshot)
        item = [s for s in snap if s["codigo"] == "AMBIENTE_VAZIO"]
        self.assertEqual(len(item), 1)
        self.assertEqual(item[0]["decisao"], "descartado")
        self.assertEqual(item[0]["motivo"], "Sala sem higrômetro; registrado em ata.")
        self.assertTrue(item[0]["decidido_por"])

    def test_verificar_bloqueado_fora_de_rascunho(self):
        self._make_clean()
        self._approve_internal()
        self._emit()
        with self.assertRaises(UserError):
            self.rel.action_verificar()

    def test_revisar_reseta_decisao_de_alerta(self):
        """Item 2 (P5 final fix wave): decisões de achado `alerta` (regra ou
        IA) não podem sobreviver a Revisar — mesmo princípio da spec §4.6
        ("aprovar uma revisão não aprova a próxima"). Sem o reset, o
        achado ficava `descartado` para sempre e a Rev.01 conseguia ser
        emitida sem ninguém olhar de novo para o alerta na revisão nova."""
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._achado("AMBIENTE_VAZIO").write(
            {"decisao": "descartado", "motivo": "Sala sem higrômetro."})
        self._approve_internal()
        self._emit()
        self._refresh()
        self.assertEqual(self.rel.state, "issued")

        self.rel.action_revisar()
        self._refresh()
        a = self._achado("AMBIENTE_VAZIO")
        self.assertTrue(a)
        self.assertEqual(a.decisao, "pendente")
        self.assertFalse(a.motivo)
        self.assertFalse(a.decidido_por)
        self.assertFalse(a.decidido_em)

        # Sem decidir de novo, a Rev.01 não pode ser emitida (amb_umidade
        # continua vazia — o alerta AMBIENTE_VAZIO volta na re-verificação
        # do gate, agora pendente).
        self._approve_internal()
        with self.assertRaises(UserError):
            self._emit()
        self.assertEqual(self.rel.state, "draft")
