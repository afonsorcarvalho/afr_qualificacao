from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common_relatorio import RelatorioTestCommon


@tagged("post_install", "-at_install")
class TestRelatorioSnippet(RelatorioTestCommon):

    def test_seed_loaded(self):
        Snip = self.env["afr.relatorio.snippet"]
        self.assertGreaterEqual(Snip.search_count([]), 10)
        cats = set(Snip.search([]).mapped("category"))
        self.assertEqual(cats, {"tabela", "lista", "destaque", "layout"})

    def test_list_filters_inactive_and_orders(self):
        Snip = self.env["afr.relatorio.snippet"]
        inactive = Snip.create({"name": "Z inativo", "category": "lista",
                                "body": "<p>x</p>", "active": False})
        items = Snip.rq_snippet_list()
        self.assertNotIn(inactive.id, [i["id"] for i in items])
        self.assertEqual(set(items[0]), {"id", "name", "category", "body"})
        order = [(i["category"]) for i in items]
        self.assertEqual(order, sorted(order))

    def test_acl(self):
        Snip = self.env["afr.relatorio.snippet"]
        snip = Snip.search([], limit=1)
        with self.assertRaises(AccessError):
            snip.with_user(self.user_qualif).write({"name": "hack"})
        snip.with_user(self.user_manager).write({"name": "ok gestor"})
        self.assertTrue(Snip.with_user(self.user_technician).rq_snippet_list())


@tagged("post_install", "-at_install")
class TestRelatorioEditorBackend(RelatorioTestCommon):

    def setUp(self):
        super().setUp()
        self.rel.write({"tolerancia_acima": 3.0, "criterio_f0_fator": 2.0})
        self.Anexo = self.env["afr.relatorio.anexo"]
        self.anx = self.Anexo.create({"relatorio_id": self.rel.id, "code": "CERT",
                                      "title": "Certificados", "included": True})
        self.anx_off = self.Anexo.create({"relatorio_id": self.rel.id, "code": "OFF",
                                          "title": "Excluído", "included": False})

    def _cat(self):
        return {c["expr"]: c for c in self.rel.rq_variable_catalog()}

    def test_catalog_values_and_groups(self):
        cat = self._cat()
        self.assertEqual(cat["criterio['tolerancia']"]["value"], "3")
        self.assertEqual(cat["criterio['f0_fator']"]["value"], "2")
        self.assertEqual(cat["criterio['valor_d']"]["value"], "")
        self.assertIn("anexo('CERT')", cat)
        self.assertIn("anexo('OFF')", cat)
        self.assertEqual(cat["anexo('OFF')"]["value"], "")
        self.assertTrue(all(c["label"] and c["group"] for c in cat.values()))

    def test_catalog_static_has_no_values_nor_anexos(self):
        items = self.env["afr.qualificacao.relatorio"].rq_variable_catalog_static()
        self.assertTrue(items)
        self.assertTrue(all(i["value"] == "" for i in items))
        self.assertFalse([i for i in items if i["expr"].startswith("anexo(")])

    def test_catalog_all_render(self):
        for c in self.rel.rq_variable_catalog():
            _html, ok = self.rel._render_body_html("<p>{{ %s }}</p>" % c["expr"])
            self.assertTrue(ok, c["expr"])

    def test_preview_resolves_and_reports_missing(self):
        body = ('<p>T <span class="rq-var">{{ criterio[\'tolerancia\'] }}</span> '
                'D <span class="rq-var">{{ criterio[\'valor_d\'] }}</span> '
                'A <span class="rq-var">{{ anexo(\'OFF\') }}</span></p>')
        res = self.rel.rq_preview_block(body)
        self.assertIn(">3<", res["html"])
        self.assertIn("criterio['valor_d']", res["missing"])
        self.assertIn("anexo('OFF')", res["missing"])
        self.assertNotIn("criterio['tolerancia']", res["missing"])

    def test_preview_invalid_expression_does_not_raise(self):
        body = '<p><span class="rq-var">{{ relatorio.nao_existe_xyz }}</span></p>'
        res = self.rel.rq_preview_block(body)
        self.assertIn("relatorio.nao_existe_xyz", res["missing"])
        self.assertIn("nao_existe_xyz", res["html"])

    def test_span_and_bare_render_same_text(self):
        Block = self.env["afr.relatorio.block"]
        old = Block.create({"relatorio_id": self.rel.id, "block_kind": "static",
                            "body": "<p>Tol {{ criterio['tolerancia'] }} C</p>"})
        new = Block.create({"relatorio_id": self.rel.id, "block_kind": "static",
                            "body": '<p>Tol <span class="rq-var">{{ criterio[\'tolerancia\'] }}</span> C</p>'})
        from lxml import html as lh
        t_old = lh.fromstring(str(self.rel._render_block_body(old))).text_content()
        t_new = lh.fromstring(str(self.rel._render_block_body(new))).text_content()
        self.assertEqual(t_old, t_new)
        self.assertIn("Tol 3 C", t_new)

    def test_sanitizer_keeps_rq_var(self):
        Block = self.env["afr.relatorio.block"]
        b = Block.create({"relatorio_id": self.rel.id, "block_kind": "static",
                          "body": '<p><span class="rq-var" data-rq-expr="x" contenteditable="false">{{ os.name }}</span></p>'})
        self.assertIn('<span class="rq-var">{{ os.name }}</span>', str(b.body))

    def test_preview_requires_write_access(self):
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.rel.with_user(self.user_technician).rq_preview_block("<p>x</p>")
        res = self.rel.with_user(self.user_qualif).rq_preview_block("<p>x</p>")
        self.assertIn("x", res["html"])
