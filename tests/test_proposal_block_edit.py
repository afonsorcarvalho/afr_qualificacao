"""Testes F8.5 — botão Editar bloco + snapshot de bloco dinâmico.

Cobre:
- editar bloco static abre o editor sem alterar o bloco;
- editar bloco dinâmico faz snapshot — conteúdo auto vira HTML e o bloco
  passa a ser static;
- o snapshot reflete os dados da cotação (ex. temperatura do ciclo).
"""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestProposalBlockEdit(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # F8.8 — cycle_specs removido do seed default; injeta a linha aqui
        # pra cobrir test_snapshot_cycle_specs_reflects_temperature.
        tpl = cls.env.ref("afr_qualificacao.proposal_template_labquali")
        if not tpl.line_ids.filtered(lambda l: l.block_kind == "cycle_specs"):
            cls.env["afr.proposal.template.line"].create({
                "template_id": tpl.id,
                "sequence": 75,
                "block_kind": "cycle_specs",
                "title": "Tabela de Ciclos",
            })

    def _built_so(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        so.proposal_template_id = self.env.ref(
            "afr_qualificacao.proposal_template_labquali"
        )
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 1}),
            ],
        })
        wiz.action_apply()
        return so

    def _block(self, so, kind):
        return so.proposal_block_ids.filtered(
            lambda b: b.block_kind == kind
        )[0]

    def test_edit_static_block_keeps_static(self):
        """Editar bloco static abre o editor sem converter nada."""
        so = self._built_so()
        block = self._block(so, "static")
        body_before = block.body
        action = block.action_edit_block()
        self.assertEqual(block.block_kind, "static")
        self.assertEqual(block.body, body_before)
        self.assertEqual(action["res_model"], "afr.proposal.block")
        self.assertEqual(action["target"], "new")

    def test_edit_equipment_scope_snapshots_to_static(self):
        """Editar bloco dinâmico congela o conteúdo e vira static."""
        so = self._built_so()
        block = self._block(so, "equipment_scope")
        self.assertFalse(block.body)
        block.action_edit_block()
        self.assertEqual(block.block_kind, "static")
        self.assertTrue(block.body)
        # F8.10 — subtotal por equip removido do escopo; snapshot tem
        # cabeçalho de equipamento e lista de tipos.
        self.assertIn("<h4>", str(block.body))
        # título vem do template (pode ter sido editado pelo cliente);
        # snapshot apenas garante que existe um título não-vazio.
        self.assertTrue(block.title)

    def test_snapshot_cycle_specs_reflects_temperature(self):
        """Snapshot do bloco de ciclos traz a temperatura do tipo de ciclo."""
        self.cycle_cmax.temperature = "134°C"
        so = self._built_so()
        block = self._block(so, "cycle_specs")
        block.action_edit_block()
        self.assertEqual(block.block_kind, "static")
        self.assertIn("134°C", str(block.body))

    def test_snapshotted_block_renders_in_report(self):
        """Bloco dinâmico após snapshot é renderizado como texto no PDF."""
        so = self._built_so()
        self._block(so, "financial").action_edit_block()
        report = self.env.ref("sale.action_report_saleorder")
        html, _ctype = report._render_qweb_html(report.report_name, so.ids)
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn("TOTAL GERAL", html)
