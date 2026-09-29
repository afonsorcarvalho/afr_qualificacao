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
