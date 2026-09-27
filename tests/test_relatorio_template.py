"""P3 — template/blocos/anexos/aprovações do Relatório Final."""

from types import SimpleNamespace

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.afr_qualificacao.hooks import _seed_relatorio_templates
from odoo.addons.afr_qualificacao.models._numbering import hierarchical_numbering

from .common import AfrQualificacaoTestCommon


def _make_relatorio(env, equip):
    """Cria um `afr.qualificacao.relatorio` real e mínimo (OS + 1 qualif QI
    + `action_generate_relatorios()`) — usado pelos testes de fix round 1
    que precisam de um relatório de verdade (aprovações exigem `relatorio_id`).
    """
    os = env["afr.qualificacao.os"].create({})
    env["afr.qualificacao"].create({
        "name": "RF-p3fix-%s" % os.id, "equipment_id": equip.id,
        "qualification_type": "installation", "os_id": os.id,
        "company_id": os.company_id.id,
    })
    return os.action_generate_relatorios()[0]


def _rec(rid, seq, parent=None, show=True):
    return SimpleNamespace(id=rid, sequence=seq, parent_id=parent, show_number=show)


class _FakeNewId:
    """Imita odoo.models.NewId: não é int, expõe `origin`."""

    def __init__(self, origin):
        self.origin = origin

    def __hash__(self):
        return id(self)


class TestHierarchicalNumbering(TransactionCase):

    def _tree(self):
        a = _rec(1, 10)
        b = _rec(2, 20, show=False)
        c = _rec(3, 30, parent=a)
        g = _rec(7, 35, parent=b)
        d = _rec(4, 40, parent=a, show=False)
        e = _rec(5, 50, parent=c)
        f = _rec(6, 60)
        return [f, e, d, g, c, b, a]  # fora de ordem de propósito

    def test_nesting_hidden_and_orphan_child(self):
        numbers = hierarchical_numbering(self._tree())
        self.assertEqual(numbers, {
            1: "1", 2: "", 3: "1.1", 7: "1", 4: "", 5: "1.1.1", 6: "2",
        })

    def test_ties_broken_by_id(self):
        x = _rec(9, 10)
        y = _rec(8, 10)
        self.assertEqual(hierarchical_numbering([x, y]), {8: "1", 9: "2"})

    def test_newid_sorted_by_origin(self):
        nid = _FakeNewId(origin=3)
        late = SimpleNamespace(id=nid, sequence=10, parent_id=None, show_number=True)
        early = _rec(2, 10)
        numbers = hierarchical_numbering([late, early])
        self.assertEqual(numbers[2], "1")
        self.assertEqual(numbers[nid], "2")

    def test_empty(self):
        self.assertEqual(hierarchical_numbering([]), {})


class TestNumberingParity(AfrQualificacaoTestCommon):
    """Cotação (template + blocos) mantém exatamente a numeração antiga."""

    def _build_template(self):
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Numeração"})
        Line = self.env["afr.proposal.template.line"]

        def mk(seq, parent=False, show=True):
            return Line.create({
                "template_id": tpl.id, "sequence": seq, "block_kind": "schedule",
                "parent_id": parent.id if parent else False, "show_number": show,
            })
        a = mk(10)
        b = mk(20, show=False)
        c = mk(30, parent=a)
        g = mk(35, parent=b)
        d = mk(40, parent=a, show=False)
        e = mk(50, parent=c)
        f = mk(60)
        return tpl, dict(a=a, b=b, c=c, g=g, d=d, e=e, f=f)

    def test_template_line_display_number(self):
        tpl, L = self._build_template()
        got = {k: v.display_number for k, v in L.items()}
        self.assertEqual(got, {
            "a": "1", "b": "", "c": "1.1", "g": "1", "d": "", "e": "1.1.1", "f": "2",
        })

    def test_sale_order_numbering_with_excluded_block(self):
        tpl, L = self._build_template()
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id, "proposal_template_id": tpl.id,
        })
        so.action_reload_proposal_blocks()
        by_seq = {b.sequence: b for b in so.proposal_block_ids}
        numbers = so._proposal_block_numbering()
        self.assertEqual(numbers[by_seq[50].id], "1.1.1")
        self.assertEqual(numbers[by_seq[60].id], "2")
        # Excluir o bloco raiz A: comportamento legado preservado
        by_seq[10].included = False
        numbers = so._proposal_block_numbering()
        self.assertNotIn(by_seq[10].id, numbers)
        self.assertEqual(numbers[by_seq[30].id], "1")
        self.assertEqual(numbers[by_seq[35].id], "1")
        self.assertEqual(numbers[by_seq[40].id], "")
        self.assertEqual(numbers[by_seq[50].id], "1.1")
        self.assertEqual(numbers[by_seq[60].id], "1")
        self.assertEqual(numbers[by_seq[20].id], "")


class TestSectionDocumentType(TransactionCase):
    """P3 Task 2 — document_type na biblioteca de seções + filtro na cotação."""

    def test_default_is_proposal(self):
        sec = self.env["afr.proposal.section"].create({"name": "Sec X"})
        self.assertEqual(sec.document_type, "proposal")

    def test_existing_seed_sections_are_proposal(self):
        sec = self.env.ref("afr_qualificacao.proposal_section_objetivo")
        self.assertEqual(sec.document_type, "proposal")

    def test_quote_line_domain_only_offers_proposal_sections(self):
        field = self.env["afr.proposal.template.line"]._fields["section_id"]
        self.assertEqual(field.domain, [("document_type", "=", "proposal")])

    def test_quote_section_action_filters_proposal(self):
        action = self.env.ref("afr_qualificacao.action_proposal_section")
        self.assertIn("document_type", action.domain or "")
        self.assertIn("proposal", action.domain or "")

    def test_quote_views_filter_section_by_document_type(self):
        arch = self.env.ref("afr_qualificacao.view_proposal_template_form").arch_db
        self.assertIn("('document_type', '=', 'proposal')", arch)

    def test_block_section_domain_only_offers_proposal_sections(self):
        """Ruling 3.4: afr.proposal.block.section_id também filtra por
        document_type='proposal' — um relatório não pode ser montado com
        seção de tipo 'report' pela aba de blocos da cotação."""
        field = self.env["afr.proposal.block"]._fields["section_id"]
        self.assertEqual(field.domain, [("document_type", "=", "proposal")])


class TestRelatorioTemplateModels(AfrQualificacaoTestCommon):

    def setUp(self):
        super().setUp()
        self.section = self.env["afr.proposal.section"].create({
            "name": "Objetivo RQ", "document_type": "report", "body": "<p>x</p>",
        })
        self.tpl = self.env["afr.relatorio.template"].create({
            "name": "Tpl Teste", "code": "RQT-TESTE",
        })

    def test_line_section_domain_is_report(self):
        field = self.env["afr.relatorio.template.line"]._fields["section_id"]
        self.assertEqual(field.domain, [("document_type", "=", "report")])

    def test_block_kinds(self):
        from odoo.addons.afr_qualificacao.models.relatorio_template import REPORT_BLOCK_KINDS
        self.assertEqual(
            [k for k, _l in REPORT_BLOCK_KINDS],
            ["static", "capa", "indice", "protocolo", "laudo_micro",
             "assinaturas", "anexo_separador"],
        )

    def test_static_line_requires_section(self):
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.template.line"].create({
                "template_id": self.tpl.id, "block_kind": "static",
            })

    def test_separator_line_requires_anexo_code(self):
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.template.line"].create({
                "template_id": self.tpl.id, "block_kind": "anexo_separador",
            })

    def test_template_line_display_number(self):
        Line = self.env["afr.relatorio.template.line"]
        root = Line.create({"template_id": self.tpl.id, "sequence": 10,
                            "block_kind": "static", "section_id": self.section.id})
        child = Line.create({"template_id": self.tpl.id, "sequence": 20,
                             "block_kind": "static", "section_id": self.section.id,
                             "parent_id": root.id})
        capa = Line.create({"template_id": self.tpl.id, "sequence": 5,
                            "block_kind": "capa", "show_number": False})
        self.assertEqual((capa.display_number, root.display_number, child.display_number),
                         ("", "1", "1.1"))

    def test_separator_line_excluded_from_numbering(self):
        """Achado 3 (fix round 1): anexo_separador não conta na numeração do
        texto — como `_body_blocks()` já exclui blocos com `anexo_code`."""
        Line = self.env["afr.relatorio.template.line"]
        root = Line.create({"template_id": self.tpl.id, "sequence": 10,
                            "block_kind": "static", "section_id": self.section.id})
        separator = Line.create({"template_id": self.tpl.id, "sequence": 15,
                                 "block_kind": "anexo_separador", "anexo_code": "dados"})
        second = Line.create({"template_id": self.tpl.id, "sequence": 20,
                              "block_kind": "static", "section_id": self.section.id})
        self.assertEqual(
            (root.display_number, separator.display_number, second.display_number),
            ("1", "", "2"),
        )

    def test_anexo_line_code_unique_per_template(self):
        """Achado 4 (fix round 1)."""
        self.env["afr.relatorio.template.anexo.line"].create({
            "template_id": self.tpl.id, "code": "dados", "title": "Dados",
        })
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["afr.relatorio.template.anexo.line"].create({
                "template_id": self.tpl.id, "code": "dados", "title": "Dados de novo",
            })

    def test_anexo_code_format_rejected_across_models(self):
        """Achado 3 (findings review P3 final): P4 casa marcadores com o
        regex `[A-Za-z0-9_-]+` — código de anexo fora disso (espaço, acento,
        pontuação) quebraria o localizador de página. Vale nos 4 lugares
        onde um código de anexo é gravado."""
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.template.anexo.line"].create({
                "template_id": self.tpl.id, "code": "código errado", "title": "X",
            })
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.template.line"].create({
                "template_id": self.tpl.id, "block_kind": "anexo_separador",
                "anexo_code": "tem espaço",
            })
        rel = _make_relatorio(self.env, self.equip1)
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.anexo"].create({
                "relatorio_id": rel.id, "code": "acentuação", "title": "Y",
            })
        blk = self.env["afr.relatorio.block"].create({
            "relatorio_id": rel.id, "sequence": 10, "block_kind": "static",
        })
        with self.assertRaises(ValidationError):
            blk.write({"anexo_code": "código com espaço"})

    def test_template_line_parent_cycle_rejected(self):
        """Achado 6 (fix round 1)."""
        Line = self.env["afr.relatorio.template.line"]
        a = Line.create({"template_id": self.tpl.id, "sequence": 10,
                         "block_kind": "static", "section_id": self.section.id})
        b = Line.create({"template_id": self.tpl.id, "sequence": 20,
                         "block_kind": "static", "section_id": self.section.id,
                         "parent_id": a.id})
        with self.assertRaises(ValidationError):
            a.parent_id = b.id

    def test_client_approval_gets_token(self):
        """Achado 7 (fix round 1): confere o token de verdade, não só a
        selection de `papel`."""
        field = self.env["afr.relatorio.aprovacao"]._fields["papel"]
        self.assertEqual([k for k, _l in field.selection],
                         ["elaborador", "emissor", "executor", "cliente"])

        rel = _make_relatorio(self.env, self.equip1)
        aprov_cliente = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "cliente",
        })
        aprov_elaborador = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "elaborador",
        })
        self.assertTrue(aprov_cliente.sudo().access_token)
        self.assertFalse(aprov_elaborador.sudo().access_token)


class TestRelatorioAprovacaoGuard(AfrQualificacaoTestCommon):
    """Fix round 1 — achados 1, 2 e 4 (metade `afr.relatorio.anexo`): guard de
    escrita e visibilidade dos campos de controle da aprovação
    (approved_at/ip/access_token), e unicidade de `code` por relatório."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_usuario = cls.env["res.users"].create({
            "name": "Usuário RQ P3Fix",
            "login": "usuario.rqp3fix.test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
            ])],
        })
        cls.user_tecnico = cls.env["res.users"].create({
            "name": "Técnico RQ P3Fix",
            "login": "tecnico.rqp3fix.test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        cls.user_manager = cls.env["res.users"].create({
            "name": "Gestor RQ P3Fix",
            "login": "gestor.rqp3fix.test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("afr_qualificacao.group_afr_qualificacao_manager").id,
            ])],
        })

    # ───────── achado 1: write() guard dos campos de controle ─────────

    def test_user_group_cannot_write_approval_control_fields(self):
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "elaborador",
        })
        with self.assertRaises(AccessError):
            aprov.with_user(self.user_usuario).write({"approved_at": "2026-09-26 12:00:00"})
        with self.assertRaises(AccessError):
            aprov.with_user(self.user_usuario).write({"ip": "10.0.0.1"})
        with self.assertRaises(AccessError):
            aprov.with_user(self.user_usuario).write({"access_token": "forjado"})

    def test_sudo_can_write_approval_control_fields(self):
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "elaborador",
        })
        aprov.sudo().write({"approved_at": "2026-09-26 12:00:00", "ip": "10.0.0.1"})
        self.assertTrue(aprov.sudo().approved_at)
        self.assertEqual(aprov.sudo().ip, "10.0.0.1")

    def test_changing_approver_on_approved_line_clears_approval(self):
        """O grupo Usuário reatribui responsável/papel — cenário real do
        escritório reorganizando quem assina — numa linha já aprovada."""
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "elaborador",
        })
        aprov.sudo().write({"approved_at": "2026-09-26 12:00:00", "ip": "10.0.0.1"})
        aprov.with_user(self.user_usuario).write({"user_id": self.user_manager.id})
        self.assertFalse(aprov.sudo().approved_at)
        self.assertFalse(aprov.sudo().ip)

        aprov2 = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "emissor",
        })
        aprov2.sudo().write({"approved_at": "2026-09-26 12:00:00", "ip": "10.0.0.1"})
        aprov2.with_user(self.user_usuario).write({"papel": "executor"})
        self.assertFalse(aprov2.sudo().approved_at)
        self.assertFalse(aprov2.sudo().ip)

    def test_rewriting_same_user_id_keeps_approval(self):
        """Regravar o mesmo valor não é "trocar" — a aprovação sobrevive."""
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "elaborador",
            "user_id": self.user_manager.id,
        })
        aprov.sudo().write({"approved_at": "2026-09-26 12:00:00", "ip": "10.0.0.1"})
        aprov.with_user(self.user_usuario).write({"user_id": self.user_manager.id})
        self.assertTrue(aprov.sudo().approved_at)

    def test_sudo_approving_with_user_id_does_not_self_invalidate(self):
        """Um fluxo interno (sudo) que grava `user_id` e `approved_at` juntos
        (aprovar em nome de outro papel, por exemplo) não deve se
        autoinvalidar — só a troca feita SEM `approved_at` no mesmo `vals`
        conta como "trocar o responsável de uma linha já aprovada"."""
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "elaborador",
        })
        aprov.sudo().write({
            "user_id": self.user_manager.id,
            "approved_at": "2026-09-26 12:00:00",
            "ip": "10.0.0.1",
        })
        self.assertTrue(aprov.sudo().approved_at)

    # ───────── findings review P3 (final), achado 1: nome_exibicao/registro/
    # partner_id também invalidam elaborador/emissor/cliente; executor
    # aprovado rejeita a troca (sem caminho de reaprovação) ─────────

    def test_changing_nome_exibicao_on_approved_elaborador_clears_approval(self):
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "elaborador", "nome_exibicao": "Fulano",
        })
        aprov.sudo().write({"approved_at": "2026-09-26 12:00:00", "ip": "10.0.0.1"})
        aprov.with_user(self.user_usuario).write({"nome_exibicao": "Beltrano"})
        self.assertFalse(aprov.sudo().approved_at)
        self.assertFalse(aprov.sudo().ip)

    def test_changing_nome_exibicao_on_approved_executor_as_user_raises(self):
        """Executor não tem caminho de reaprovação: a linha aprovada
        (assinatura já coletada no relatório diário) não pode ter o nome
        trocado por um usuário comum — nem invalidando nem silenciosamente."""
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].sudo().create({
            "relatorio_id": rel.id, "papel": "executor", "nome_exibicao": "Técnico X",
            "approved_at": "2026-09-26 12:00:00",
        })
        with self.assertRaises(AccessError):
            aprov.with_user(self.user_usuario).write({"nome_exibicao": "Outro Nome"})
        self.assertEqual(aprov.sudo().nome_exibicao, "Técnico X")
        self.assertTrue(aprov.sudo().approved_at)

    def test_sudo_can_change_identity_fields_on_approved_executor(self):
        """Caminho interno (sudo, P4) não é afetado pela rejeição do
        achado — essa é só para escrita direta de usuário comum (b). Grava
        nome_exibicao junto com approved_at (padrão do fluxo de aprovação da
        P4): a aprovação não se autoinvalida (exemção existente)."""
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].sudo().create({
            "relatorio_id": rel.id, "papel": "executor", "nome_exibicao": "Técnico X",
            "approved_at": "2026-09-26 12:00:00",
        })
        aprov.sudo().write({
            "nome_exibicao": "Reaprovado",
            "approved_at": "2026-09-26 13:00:00",
        })
        self.assertEqual(aprov.sudo().nome_exibicao, "Reaprovado")
        self.assertTrue(aprov.sudo().approved_at)

        # Sudo trocando só o nome (sem approved_at) não é BLOQUEADO (não é a
        # rejeição do achado, que só vale para chamador não-su) — mas invalida
        # a aprovação como qualquer troca de identidade sem reaprovação junto.
        aprov.sudo().write({"nome_exibicao": "Outro Nome Via Sudo"})
        self.assertFalse(aprov.sudo().approved_at)

    # ───────── fix round 2, achado 1: create() guard dos campos de controle ─────────

    def test_non_sudo_create_with_approved_at_raises(self):
        rel = _make_relatorio(self.env, self.equip1)
        with self.assertRaises(AccessError):
            self.env["afr.relatorio.aprovacao"].with_user(self.user_usuario).create({
                "relatorio_id": rel.id, "papel": "elaborador",
                "approved_at": "2026-09-26 12:00:00",
            })

    def test_non_sudo_create_with_ip_raises(self):
        rel = _make_relatorio(self.env, self.equip1)
        with self.assertRaises(AccessError):
            self.env["afr.relatorio.aprovacao"].with_user(self.user_usuario).create({
                "relatorio_id": rel.id, "papel": "elaborador", "ip": "10.0.0.1",
            })

    def test_non_sudo_create_ignores_caller_supplied_access_token(self):
        """Achado 1 (round 2): o token é sempre gerado no servidor para
        `papel='cliente'` — um valor "escolhido" pelo chamador não-sudo é
        descartado, nunca aceito."""
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].with_user(self.user_usuario).create({
            "relatorio_id": rel.id, "papel": "cliente", "partner_id": self.partner.id,
            "access_token": "token-escolhido-pelo-atacante",
        })
        self.assertTrue(aprov.sudo().access_token)
        self.assertNotEqual(aprov.sudo().access_token, "token-escolhido-pelo-atacante")

    def test_sudo_create_with_approved_at_works(self):
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].sudo().create({
            "relatorio_id": rel.id, "papel": "elaborador",
            "approved_at": "2026-09-26 12:00:00", "ip": "10.0.0.1",
        })
        self.assertTrue(aprov.sudo().approved_at)
        self.assertEqual(aprov.sudo().ip, "10.0.0.1")

    def test_non_sudo_create_default_context_approved_at_raises(self):
        """Task 13/14 já mordeu nisto uma vez: o guard só olha o `vals`
        RECEBIDO — `default_<campo>` no contexto é aplicado DENTRO do
        `super().create()`, depois do pré-check. Sem um pós-check, o vetor
        `with_context(default_approved_at=...)` nascia a linha já aprovada
        mesmo sem o campo no `vals`."""
        rel = _make_relatorio(self.env, self.equip1)
        with self.assertRaises(AccessError):
            self.env["afr.relatorio.aprovacao"].with_user(self.user_usuario).with_context(
                default_approved_at="2026-09-26 12:00:00"
            ).create({"relatorio_id": rel.id, "papel": "elaborador"})

    def test_non_sudo_create_default_context_ip_raises(self):
        rel = _make_relatorio(self.env, self.equip1)
        with self.assertRaises(AccessError):
            self.env["afr.relatorio.aprovacao"].with_user(self.user_usuario).with_context(
                default_ip="10.0.0.1"
            ).create({"relatorio_id": rel.id, "papel": "elaborador"})

    def test_non_sudo_create_default_context_access_token_ignored_for_non_cliente(self):
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].with_user(self.user_usuario).with_context(
            default_access_token="escolhido-via-contexto"
        ).create({"relatorio_id": rel.id, "papel": "elaborador"})
        self.assertFalse(aprov.sudo().access_token)

    # ───────── achado 2: access_token restrito ao Gestor ─────────

    def test_access_token_denied_to_user_and_technician(self):
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "cliente", "partner_id": self.partner.id,
        })
        # Fix round 4 do P4 Task 9 (ruling R2): o campo não é mais armazenado;
        # read() segue barrado pelo `groups=`, e o acesso por atributo (que no
        # Odoo 16 não checa `groups=` em campo computado) devolve False.
        for user in (self.user_usuario, self.user_tecnico):
            with self.assertRaises(AccessError):
                aprov.with_user(user).read(["access_token"])
            self.assertFalse(aprov.with_user(user).access_token)
        self.assertTrue(aprov.sudo().access_token)

    def test_access_token_readable_by_manager_and_sudo(self):
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "cliente", "partner_id": self.partner.id,
        })
        self.assertTrue(aprov.with_user(self.user_manager).access_token)
        self.assertTrue(aprov.sudo().access_token)

    def test_user_group_can_create_client_approval_with_token(self):
        """O grupo Usuário cria aprovações no fluxo normal (`_apply_template`
        roda como o técnico/office user que aperta "Recarregar template" —
        ACL `access_relatorio_aprovacao_user` tem `create=1`). `create()` não
        passa por `check_field_access_rights` (só `write()`/`read()` fazem),
        então injetar `access_token` no `vals` dentro do próprio `create()`
        não é bloqueado pelo `groups=` do achado 2 mesmo para quem não é
        Gestor."""
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].with_user(self.user_usuario).create({
            "relatorio_id": rel.id, "papel": "cliente", "partner_id": self.partner.id,
        })
        self.assertTrue(aprov.sudo().access_token)

    # ───────── achado 4 (metade anexo): unicidade de code por relatório ─────────

    def test_anexo_code_unique_per_relatorio(self):
        rel = _make_relatorio(self.env, self.equip1)
        self.env["afr.relatorio.anexo"].create({
            "relatorio_id": rel.id, "code": "dados", "title": "Dados",
        })
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["afr.relatorio.anexo"].create({
                "relatorio_id": rel.id, "code": "dados", "title": "Dados de novo",
            })

    # ───────── achado 6 (afr.relatorio.block): ciclo via _check_recursion ─────────

    def test_block_parent_cycle_rejected(self):
        rel = _make_relatorio(self.env, self.equip1)
        Block = self.env["afr.relatorio.block"]
        a = Block.create({"relatorio_id": rel.id, "sequence": 10, "block_kind": "static"})
        b = Block.create({"relatorio_id": rel.id, "sequence": 20, "block_kind": "static",
                          "parent_id": a.id})
        with self.assertRaises(ValidationError):
            a.parent_id = b.id


class TestRelatorioSeeds(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_relatorio_templates(cls.env)
        cls.hosp = cls.env.ref("afr_qualificacao.relatorio_template_hosp")
        cls.ind = cls.env.ref("afr_qualificacao.relatorio_template_ind")

    def test_codes_and_category(self):
        self.assertEqual((self.hosp.code, self.ind.code), ("RQT-HOSP", "RQT-IND"))
        self.assertIn(self.env.ref("afr_qualificacao.cat_autoclave_vapor"),
                      self.hosp.equipment_category_ids)

    def test_hosp_anexos_order(self):
        codes = self.hosp.anexo_line_ids.sorted(lambda l: (l.sequence, l.id)).mapped("code")
        self.assertEqual(codes, ["protocolo", "dados", "graficos", "micro", "f0",
                                 "malhas", "validador", "padroes"])
        dados = self.hosp.anexo_line_ids.filtered(lambda l: l.code == "dados")
        self.assertEqual(dados.slot_kind, "collect_section")
        self.assertIn("qd_penetracao_ciclo1", dados.collect_sections)
        validador = self.hosp.anexo_line_ids.filtered(lambda l: l.code == "validador")
        self.assertEqual((validador.slot_kind, validador.cert_roles),
                         ("instrument_certs", "antes,depois"))

    def test_ind_anexos_order(self):
        codes = self.ind.anexo_line_ids.sorted(lambda l: (l.sequence, l.id)).mapped("code")
        self.assertEqual(codes, ["protocolo", "protocolo_cliente", "dados", "graficos",
                                 "impressoes", "micro", "f0", "malhas", "validador",
                                 "padroes"])
        micro = self.ind.anexo_line_ids.filtered(lambda l: l.code == "micro")
        self.assertEqual(micro.slot_kind, "upload")

    def test_sections_are_report_and_use_tokens(self):
        crit = self.env.ref("afr_qualificacao.rqt_sec_criterios")
        self.assertEqual(crit.document_type, "report")
        self.assertIn("criterio['tolerancia']", str(crit.body))
        self.assertIn("anexo('protocolo')",
                      str(self.env.ref("afr_qualificacao.rqt_sec_objetivo").body))

    def test_hosp_lines_have_kinds_and_bloco_links(self):
        kinds = set(self.hosp.line_ids.mapped("block_kind"))
        self.assertTrue({"capa", "indice", "static", "protocolo", "laudo_micro",
                         "assinaturas", "anexo_separador"} <= kinds)
        proto = self.hosp.line_ids.filtered(lambda l: l.block_kind == "protocolo")
        self.assertEqual(proto.anexo_code, "protocolo")
        self.assertFalse(self.ind.line_ids.filtered(lambda l: l.block_kind == "laudo_micro"))

    def test_checklist_seeded(self):
        self.assertGreaterEqual(len(self.hosp.checklist_line_ids), 10)
        self.assertGreater(len(self.ind.checklist_line_ids), len(self.hosp.checklist_line_ids))

    def test_seed_is_idempotent(self):
        before = (len(self.hosp.line_ids), len(self.hosp.anexo_line_ids),
                  len(self.hosp.checklist_line_ids))
        _seed_relatorio_templates(self.env)
        _seed_relatorio_templates(self.env)
        Tpl = self.env["afr.relatorio.template"].with_context(active_test=False)
        self.assertEqual(Tpl.search_count([("code", "=", "RQT-HOSP")]), 1)
        self.assertEqual(Tpl.search_count([("code", "=", "RQT-IND")]), 1)
        self.assertEqual((len(self.hosp.line_ids), len(self.hosp.anexo_line_ids),
                          len(self.hosp.checklist_line_ids)), before)

    def test_quote_does_not_see_report_sections(self):
        sec = self.env.ref("afr_qualificacao.rqt_sec_objetivo")
        found = self.env["afr.proposal.section"].search([("document_type", "=", "proposal")])
        self.assertNotIn(sec, found)


class RelatorioTemplateFixture(AfrQualificacaoTestCommon):
    """Fixture sem testes (reusada por Apply e Tokens): OS + técnico com
    relatório diário assinado + relatório final com RQT-HOSP aplicado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_relatorio_templates(cls.env)
        cls.hosp = cls.env.ref("afr_qualificacao.relatorio_template_hosp")

    def setUp(self):
        super().setUp()
        so = self._apply(do_qi=True, qo_cycles=1)
        self.os = self._confirm_and_generate_os(so)
        self.employee = self.env["hr.employee"].create({"name": "Técnico Teste"})
        self.daily = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": self.os.id,
            "descricao": "Dia 1",
            "data_inicio": "2026-09-01 08:00:00",
            "data_fim": "2026-09-01 17:00:00",
            "tecnico_ids": [(6, 0, self.employee.ids)],
            "signature_technician_date": "2026-09-01 17:05:00",
        })
        self.os.action_generate_relatorios_open()
        self.rel = self.os.relatorio_final_ids.filtered(
            lambda r: r.equipment_id == self.equip1)
        self.rel.template_id = self.hosp
        self.rel.action_reload_template()


class TestRelatorioApplyTemplate(RelatorioTemplateFixture):

    def test_generate_applies_template(self):
        self.assertTrue(self.rel.block_ids)
        self.assertEqual(len(self.rel.block_ids), len(self.hosp.line_ids))
        self.assertEqual(len(self.rel.anexo_ids), len(self.hosp.anexo_line_ids))
        self.assertEqual(len(self.rel.checklist_ids), len(self.hosp.checklist_line_ids))

    def test_programmatic_generate_only_suggests_template(self):
        """Compatibilidade com P1: action_generate_relatorios() (recordset)
        não semeia nada; só o template é sugerido no create()."""
        so2 = self._apply(do_qi=True)
        os2 = self._confirm_and_generate_os(so2)
        rels2 = os2.action_generate_relatorios()
        self.assertTrue(rels2)
        self.assertTrue(all(r.template_id for r in rels2))
        self.assertFalse(rels2.mapped("block_ids"))
        self.assertFalse(rels2.mapped("checklist_ids"))
        self.assertFalse(rels2.mapped("aprovacao_ids"))

    def test_block_hierarchy_copied(self):
        qi = self.rel.block_ids.filtered(lambda b: b.title == "Qualificação de Instalação (QI)")
        self.assertEqual(qi.parent_id.title, "Procedimento de Qualificação")
        self.assertIn("{{", str(qi.parent_id.body))  # corpo copiado da seção

    def test_bloco_anexo_linked_to_content_block(self):
        proto = self.rel.anexo_ids.filtered(lambda a: a.code == "protocolo")
        self.assertEqual(proto.block_id.block_kind, "protocolo")
        micro = self.rel.anexo_ids.filtered(lambda a: a.code == "micro")
        self.assertEqual(micro.block_id.block_kind, "laudo_micro")
        dados = self.rel.anexo_ids.filtered(lambda a: a.code == "dados")
        self.assertFalse(dados.block_id)

    def test_default_approvals(self):
        ap = self.rel.aprovacao_ids
        self.assertEqual(ap.sorted("sequence").mapped("papel"),
                         ["elaborador", "emissor", "executor", "cliente"])
        executor = ap.filtered(lambda a: a.papel == "executor")
        self.assertEqual(executor.nome_exibicao, "Técnico Teste")
        self.assertTrue(executor.approved_at)
        cliente = ap.filtered(lambda a: a.papel == "cliente")
        self.assertEqual(cliente.partner_id, self.rel.partner_id)
        self.assertEqual(cliente.nome_exibicao, self.rel.partner_id.name)
        self.assertEqual(len(cliente.access_token or ""), 32)

    def test_default_approvals_created_via_sudo_for_plain_user(self):
        """T3 guard: `afr.relatorio.aprovacao.create()` rejeita `approved_at`
        vindo de um chamador não-`env.su` (Task 3). `_apply_default_aprovacoes()`
        roda dentro do wrapper de UI `action_generate_relatorios_open()`, que um
        usuário do grupo Usuário (não Gestor) pode disparar — sem `sudo()` na
        criação da aprovação do executor, este fluxo estouraria `AccessError`.

        Usa uma OS nova (não `self.os`, cujas aprovações já existem — reaplicar
        seria pulado pela idempotência e o teste não provaria nada).
        """
        user = self.env["res.users"].create({
            "name": "Usuário RQ P3 Task5",
            "login": "usuario.rqp3task5.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
            ])],
        })
        so2 = self._apply(do_qi=True)
        os2 = self._confirm_and_generate_os(so2)
        employee2 = self.env["hr.employee"].create({"name": "Técnico Teste 2"})
        self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os2.id,
            "descricao": "Dia 1",
            "data_inicio": "2026-09-01 08:00:00",
            "data_fim": "2026-09-01 17:00:00",
            "tecnico_ids": [(6, 0, employee2.ids)],
            "signature_technician_date": "2026-09-01 17:05:00",
        })
        os2.with_user(user).action_generate_relatorios_open()
        rel2 = os2.relatorio_final_ids
        executor = rel2.aprovacao_ids.filtered(lambda a: a.papel == "executor")
        self.assertTrue(executor.approved_at)
        cliente = rel2.aprovacao_ids.filtered(lambda a: a.papel == "cliente")
        self.assertEqual(len(cliente.sudo().access_token or ""), 32)

    def test_default_approvals_ignore_forged_context_defaults(self):
        """Fix round 1: `.sudo()` bypasses `afr.relatorio.aprovacao.create()`'s
        guard entirely (gated on `not self.env.su`) — but Odoo still fills any
        field ABSENT from `vals` from `context['default_<field>']` inside
        `super().create()`, regardless of su. The elaborador/emissor vals
        carried no `user_id`/`approved_at`/`ip` key, so an RPC caller of
        `action_generate_relatorios_open()` with
        `context={"default_approved_at": ..., "default_user_id": <other uid>,
        "default_ip": ...}` got those roles born pre-approved and attributed
        to an arbitrary user — forging the internal-approval gate P4 relies
        on. `_apply_default_aprovacoes()` must call `.sudo().with_context(
        clean_context(self.env.context))` AND set approved_at/ip/user_id
        explicitly in every vals dict so no field is ever "missing" for the
        context-default mechanism to fill.
        """
        other_user = self.env["res.users"].create({
            "name": "Outro Usuário (forjado)",
            "login": "outro.forjado.task5fix1.test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        user = self.env["res.users"].create({
            "name": "Usuário RQ P3 Task5 Fix1",
            "login": "usuario.rqp3task5fix1.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
            ])],
        })
        so2 = self._apply(do_qi=True)
        os2 = self._confirm_and_generate_os(so2)
        employee2 = self.env["hr.employee"].create({"name": "Técnico Teste Fix1"})
        self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os2.id,
            "descricao": "Dia 1",
            "data_inicio": "2026-09-01 08:00:00",
            "data_fim": "2026-09-01 17:00:00",
            "tecnico_ids": [(6, 0, employee2.ids)],
            "signature_technician_date": "2026-09-01 17:05:00",
        })
        forged_ctx = {
            "default_approved_at": "2000-01-01 00:00:00",
            "default_user_id": other_user.id,
            "default_ip": "6.6.6.6",
        }
        os2.with_user(user).with_context(**forged_ctx).action_generate_relatorios_open()
        rel2 = os2.relatorio_final_ids
        ap = rel2.aprovacao_ids
        for papel in ("elaborador", "emissor"):
            row = ap.filtered(lambda a, p=papel: a.papel == p)
            self.assertFalse(row.approved_at, papel)
            self.assertFalse(row.user_id, papel)
            self.assertFalse(row.sudo().ip, papel)
        executor = ap.filtered(lambda a: a.papel == "executor")
        self.assertNotEqual(executor.user_id.id, other_user.id)
        self.assertTrue(executor.approved_at)
        self.assertNotEqual(executor.approved_at, fields.Datetime.to_datetime("2000-01-01 00:00:00"))
        self.assertFalse(executor.sudo().ip)
        cliente = ap.filtered(lambda a: a.papel == "cliente")
        self.assertFalse(cliente.sudo().ip)
        self.assertNotEqual(cliente.user_id.id, other_user.id)

    def test_apply_template_is_idempotent(self):
        counts = (len(self.rel.block_ids), len(self.rel.anexo_ids),
                  len(self.rel.checklist_ids), len(self.rel.aprovacao_ids))
        self.rel._apply_template()
        self.os.action_generate_relatorios_open()
        self.assertEqual((len(self.rel.block_ids), len(self.rel.anexo_ids),
                          len(self.rel.checklist_ids), len(self.rel.aprovacao_ids)), counts)

    def test_reload_blocked_outside_draft(self):
        self.rel.write({"state": "issued"})
        with self.assertRaises(UserError):
            self.rel.action_reload_template()

    def test_generate_relatorios_open_skips_non_draft_report(self):
        """Achado 2 (findings review P3 final): a P4 vai travar create()
        fora do estado 'draft' — o botão "Gerar relatórios finais" não pode
        chamar `_apply_template()` num relatório já emitido, senão o botão
        falha pra toda a OS. Relatório 'issued' sem blocos permanece
        intocado, sem erro."""
        so2 = self._apply(do_qi=True)
        os2 = self._confirm_and_generate_os(so2)
        rel2 = os2.action_generate_relatorios().filtered(
            lambda r: r.equipment_id == self.equip1)
        rel2.write({"state": "issued"})
        os2.action_generate_relatorios_open()
        self.assertFalse(rel2.block_ids)
        self.assertFalse(rel2.anexo_ids)
        self.assertFalse(rel2.checklist_ids)
        self.assertFalse(rel2.aprovacao_ids)

    def test_reload_without_template_raises(self):
        """Ruling 1.7: template_id vazio levanta UserError ANTES de apagar
        blocos/anexos já existentes (não pode destruir dados sem template
        para reaplicar)."""
        self.rel.template_id = False
        blocks_before = self.rel.block_ids
        anexos_before = self.rel.anexo_ids
        with self.assertRaises(UserError):
            self.rel.action_reload_template()
        self.assertEqual(self.rel.block_ids, blocks_before)
        self.assertEqual(self.rel.anexo_ids, anexos_before)

    def test_reload_discards_block_edits(self):
        blk = self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")
        blk.body = "<p>editado</p>"
        self.rel.action_reload_template()
        blk = self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")
        self.assertNotIn("editado", str(blk.body))

    def test_reload_with_another_template_keeps_checklist_and_approvals(self):
        """Ruling 1.9: recarregar com outro template mantém checklist e
        aprovações (só blocos/anexos são descartados e reaplicados)."""
        checklist_before = self.rel.checklist_ids
        approvals_before = self.rel.aprovacao_ids
        other = self.env["afr.relatorio.template"].create({
            "name": "Tpl Outro", "code": "RQT-OUTRO", "sequence": 50,
        })
        self.rel.template_id = other
        self.rel.action_reload_template()
        self.assertEqual(self.rel.checklist_ids, checklist_before)
        self.assertEqual(self.rel.aprovacao_ids, approvals_before)

    def test_anexo_numbering_skips_excluded(self):
        num = {a.code: a.numero for a in self.rel.anexo_ids}
        self.assertEqual((num["protocolo"], num["dados"], num["graficos"], num["micro"]),
                         (1, 2, 3, 4))
        self.rel.anexo_ids.filtered(lambda a: a.code == "dados").included = False
        self.assertEqual(self.rel._anexo_number("dados"), "")
        self.assertEqual(self.rel._anexo_number("graficos"), "2")
        self.assertEqual(self.rel._anexo_number("micro"), "3")
        self.assertEqual(self.rel._anexo_number("nao_existe"), "")

    def test_block_numbering_ignores_anexo_blocks(self):
        numbers = self.rel._block_numbering()
        anexo_blocks = self.rel.block_ids.filtered("anexo_code")
        self.assertTrue(anexo_blocks)
        for blk in anexo_blocks:
            self.assertNotIn(blk.id, numbers)
        objetivo = self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")
        self.assertEqual(numbers[objetivo.id], "1")
        qi = self.rel.block_ids.filtered(lambda b: b.title == "Qualificação de Instalação (QI)")
        self.assertEqual(numbers[qi.id], "4.1")

    def test_suggest_template_by_category_then_sequence(self):
        tpl = self.env["afr.relatorio.template"].create({
            "name": "Tpl Categoria", "code": "RQT-CAT", "sequence": 99,
            "equipment_category_ids": [(6, 0, self.category.ids)],
        })
        self.assertEqual(self.rel._suggest_template(), tpl)
        tpl.equipment_category_ids = [(5, 0, 0)]
        lowest = self.env["afr.relatorio.template"].search(
            [("company_id", "in", [self.rel.company_id.id, False])],
            order="sequence, id", limit=1)
        self.assertEqual(self.rel._suggest_template(), lowest)


class TestRelatorioTokens(RelatorioTemplateFixture):
    """Reusa a fixture da Task 5 (relatório com RQT-HOSP aplicado)."""

    def _objetivo(self):
        return self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")

    def test_render_tokens_criterio_and_anexo(self):
        blk = self._objetivo()
        blk.body = ("<p>T={{ criterio['tolerancia'] }};A={{ anexo('micro') }};"
                    "S={{ equipment.serial_number }}</p>")
        self.assertIn("anexo('micro')", str(blk.body))  # sanitizer preserva aspas
        self.rel.tolerancia_acima = 4.0
        html = str(self.rel._render_block_body(blk))
        self.assertIn("T=4;A=4;S=TSN-001", html)
        self.rel.anexo_ids.filtered(lambda a: a.code == "micro").included = False
        html = str(self.rel._render_block_body(blk))
        self.assertIn("T=4;A=;S=TSN-001", html)

    def test_criterio_values(self):
        self.rel.write({"tolerancia_acima": 3.0, "criterio_f0_fator": 12.0})
        self.assertEqual(self.rel._criterio_values()["valor_d"], "")
        self.env["afr.relatorio.indicador"].create({
            "relatorio_id": self.rel.id, "tipo": "biologico", "valor_d": 1.5,
        })
        crit = self.rel._criterio_values()
        self.assertEqual(crit, {"tolerancia": "3", "f0_fator": "12",
                                "valor_d": "1,5", "f0_minimo": "18"})

    def test_token_context_keys(self):
        ctx = self.rel._token_context()
        self.assertEqual(set(ctx), {"relatorio", "os", "partner", "equipment",
                                    "company", "criterio", "anexo"})
        self.assertEqual(ctx["anexo"]("protocolo"), "1")

    def test_seeded_bodies_render_without_braces(self):
        for blk in self.rel.block_ids.filtered("body"):
            self.assertNotIn("{{", str(self.rel._render_block_body(blk)), blk.title)

    def test_bad_token_falls_back_to_raw_body(self):
        blk = self._objetivo()
        blk.body = "<p>{{ relatorio.campo_que_nao_existe }}</p>"
        html = str(self.rel._render_block_body(blk))
        self.assertIn("{{", html)

    def test_empty_body(self):
        blk = self._objetivo()
        blk.body = False
        self.assertEqual(str(self.rel._render_block_body(blk)), "")

    def test_render_as_plain_user(self):
        user = self.env["res.users"].create({
            "name": "Usuário RQ", "login": "usuario_rq_p3",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
            ])],
        })
        blk = self._objetivo()
        blk.body = "<p>T={{ criterio['tolerancia'] }};A={{ anexo('dados') }}</p>"
        html = str(self.rel.with_user(user)._render_block_body(blk.with_user(user)))
        self.assertIn("T=3;A=2", html)
