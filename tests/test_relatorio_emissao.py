"""P4 — emissão, revisão, aprovações, verificação pública e portal do Relatório Final."""
from odoo.exceptions import UserError
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
