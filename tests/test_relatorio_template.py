"""P3 — template/blocos/anexos/aprovações do Relatório Final."""

from types import SimpleNamespace

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

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

    # ───────── achado 2: access_token restrito ao Gestor ─────────

    def test_access_token_denied_to_user_and_technician(self):
        rel = _make_relatorio(self.env, self.equip1)
        aprov = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": rel.id, "papel": "cliente", "partner_id": self.partner.id,
        })
        with self.assertRaises(AccessError):
            aprov.with_user(self.user_usuario).access_token
        with self.assertRaises(AccessError):
            aprov.with_user(self.user_tecnico).access_token

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
