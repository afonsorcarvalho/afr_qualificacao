"""P3 — template/blocos/anexos/aprovações do Relatório Final."""

from types import SimpleNamespace

from odoo.tests.common import TransactionCase

from odoo.addons.afr_qualificacao.models._numbering import hierarchical_numbering

from .common import AfrQualificacaoTestCommon


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
