"""P4 — emissão, revisão, aprovações, verificação pública e portal do Relatório Final."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon
from .relatorio_fakes import RelatorioFixtureMixin, make_user

MANAGER = "afr_qualificacao.group_afr_qualificacao_manager"
USER = "afr_qualificacao.group_afr_qualificacao_user"
TECH = "afr_qualificacao.group_afr_qualificacao_technician"


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioEmissaoModel(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = make_user(cls.env, "gestor.rq.emissao", MANAGER)
        cls.usuario = make_user(cls.env, "usuario.rq.emissao", USER)

    def setUp(self):
        super().setUp()
        self.rel, _q = self._make_relatorio()
        self.att = self._attachment(b"%PDF-1.4 teste", "r.pdf", "application/pdf")

    def _internal_create(self, **vals):
        base = {
            "relatorio_id": self.rel.id, "revision": 0,
            "pdf_attachment_id": self.att.id, "sha256": "0" * 64,
            "token": "a" * 32,
        }
        base.update(vals)
        return self.env["afr.relatorio.emissao"].sudo().with_context(
            rq_emissao_internal=True
        ).create(base)

    def test_create_without_internal_flag_is_blocked(self):
        with self.assertRaises(UserError):
            self.env["afr.relatorio.emissao"].create({
                "relatorio_id": self.rel.id, "token": "b" * 32,
            })
        with self.assertRaises(UserError):
            self.env["afr.relatorio.emissao"].with_user(self.manager).create({
                "relatorio_id": self.rel.id, "token": "c" * 32,
            })

    def test_internal_create_and_supersede(self):
        emissao = self._internal_create()
        self.assertEqual(emissao.name, "%s Rev.00" % self.rel.name)
        emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": True})
        self.assertTrue(emissao.superseded)

    def test_internal_create_ignores_context_defaults(self):
        """Ruling 5.1: `default_superseded`/`default_token` no contexto não

        podem "vazar" para dentro do registro criado pelo caminho interno —
        o Odoo aplica `context['default_<campo>']` a campos AUSENTES de
        `vals` dentro do próprio `super().create()`, depois do pre-check do
        override (mesmo raciocínio de `relatorio_aprovacao.py::create()`,
        P3). `token` fica de fora de `vals` de propósito, para provar que o
        `default_token` do contexto não o preenche.
        """
        emissao = self.env["afr.relatorio.emissao"].sudo().with_context(
            rq_emissao_internal=True,
            default_superseded=True,
            default_token="z" * 32,
        ).create({
            "relatorio_id": self.rel.id, "revision": 0,
            "pdf_attachment_id": self.att.id, "sha256": "1" * 64,
        })
        self.assertFalse(emissao.superseded)
        self.assertFalse(emissao.token)

    def test_write_is_blocked_even_for_superuser(self):
        emissao = self._internal_create()
        with self.assertRaises(UserError):
            emissao.write({"sha256": "f" * 64})
        with self.assertRaises(UserError):
            emissao.sudo().with_context(rq_emissao_internal=True).write({"sha256": "f" * 64})
        emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": True})
        with self.assertRaises(UserError):
            emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": False})
        with self.assertRaises(UserError):
            emissao.with_user(self.manager).write({"superseded": True})

    def test_unlink_is_blocked(self):
        emissao = self._internal_create()
        with self.assertRaises(UserError):
            emissao.unlink()

    def test_verify_url_prefers_context_token_then_current_emissao(self):
        self.assertFalse(self.rel.verify_url)
        url = self.rel.with_context(rq_emission_token="d" * 32).verify_url
        self.assertIn("/qualificacao/relatorio/verify/" + "d" * 32, url)
        emissao = self._internal_create(token="e" * 32)
        self.rel.write({"current_emissao_id": emissao.id})  # env admin (su)
        self.assertIn("/qualificacao/relatorio/verify/" + "e" * 32, self.rel.verify_url)

    def test_internal_fields_not_writable_by_users(self):
        rel_mgr = self.rel.with_user(self.manager)
        for vals in ({"state": "issued"}, {"revision": 3}):
            with self.assertRaises(UserError):
                rel_mgr.write(vals)
        self.rel.write({"revision": 2})  # su pode (migrações, código interno)
        self.assertEqual(self.rel.revision, 2)

    # ─────────────────────────────────────────────────────────────
    # Fix round 1 — create() de afr.qualificacao.relatorio estava aberto:
    # só o write() guardava _RQ_INTERNAL_FIELDS (state, revision,
    # current_emissao_id). Usuário (create=1 na ACL) conseguia nascer o
    # registro já emitido/revisado, sem passar pela ação Emitir/Revisar.
    # ─────────────────────────────────────────────────────────────
    def _give_equip2_qualif_on(self, os_rec):
        """`afr.qualificacao.relatorio` exige que o equipamento já tenha
        qualificação na OS (guard pré-existente, não relacionado a este fix)
        — sem isto, o `create()` falharia por esse motivo, não pelo guard
        de `_RQ_INTERNAL_FIELDS` que este teste quer exercitar."""
        self.env["afr.qualificacao"].create({
            "name": "Qualif equip2 p/ teste do guard de create",
            "equipment_id": self.equip2.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_rec.id,
        })

    def test_create_with_internal_fields_is_blocked_for_usuario(self):
        other_rel, _q = self._make_relatorio(equipment=self.equip2)
        emissao = self._internal_create(relatorio_id=other_rel.id, token="f" * 32)
        self._give_equip2_qualif_on(self.rel.os_id)
        with self.assertRaises(UserError):
            self.env["afr.qualificacao.relatorio"].with_user(self.usuario).create({
                "os_id": self.rel.os_id.id,
                "equipment_id": self.equip2.id,
                "state": "issued",
                "revision": 5,
                "current_emissao_id": emissao.id,
            })

    def test_create_with_context_default_state_is_blocked_for_usuario(self):
        """Pós-check: o pré-check só vê o `vals` recebido — `context
        ['default_state']` é aplicado pelo ORM DENTRO do `super().create()`,
        depois do pré-check (mesmo raciocínio de `qualificacao.py`
        Task 13/14). Sem `state` no vals, só o pós-check no registro
        efetivo pega isso."""
        self._give_equip2_qualif_on(self.rel.os_id)
        with self.assertRaises(UserError):
            self.env["afr.qualificacao.relatorio"].with_user(
                self.usuario
            ).with_context(default_state="issued").create({
                "os_id": self.rel.os_id.id,
                "equipment_id": self.equip2.id,
            })

    def test_manager_with_internal_context_but_no_sudo_still_blocked(self):
        """O contexto `rq_emissao_internal` por si só não basta — precisa de
        `env.su`. Gestor sem `sudo()` não passa, mesmo com a flag no
        contexto (a única diferença deste teste em relação a
        `test_create_without_internal_flag_is_blocked` é a presença
        explícita da flag)."""
        with self.assertRaises(UserError):
            self.env["afr.relatorio.emissao"].with_user(
                self.manager
            ).with_context(rq_emissao_internal=True).create({
                "relatorio_id": self.rel.id, "token": "g" * 32,
            })

    def test_action_generate_relatorios_still_works_for_usuario(self):
        """Regressão: o guard novo do create() não pode quebrar o caminho
        legítimo (vals sem nenhum campo de `_RQ_INTERNAL_FIELDS`)."""
        self._give_equip2_qualif_on(self.rel.os_id)
        rels = self.rel.os_id.with_user(self.usuario).action_generate_relatorios()
        novo = rels.filtered(lambda r: r.equipment_id == self.equip2)
        self.assertTrue(novo)
        self.assertEqual(novo.state, "draft")
        self.assertEqual(novo.revision, 0)

    def test_current_emissao_must_belong_to_relatorio(self):
        other_rel, _q = self._make_relatorio(equipment=self.equip2)
        other_emissao = self._internal_create(relatorio_id=other_rel.id, token="h" * 32)
        with self.assertRaises(ValidationError):
            self.rel.write({"current_emissao_id": other_emissao.id})
