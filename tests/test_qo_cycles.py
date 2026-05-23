"""Testes F8.8 — ciclos QO (sem carga) por equipamento.

Cobre:
- wizard com qo_line_ids gera SO lines qualification_type='operational'
  com cycle_type_id;
- confirm SO explode afr.qualificacao.cycle para QO (mesmo padrão do QD);
- helper `_qualif_cycle_rows_for(equip, 'qo')` retorna as linhas;
- bloco Equipment Scope renderiza tabela QO inline no PDF;
- fallback: do_qo=True sem qo_line_ids continua gerando 1 linha type.config.
"""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestQoCycles(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # cycle_types QO (sem carga) — usa product_qo de common.py
        cls.cycle_qo_bowie = cls.env["afr.qualificacao.cycle.type"].create({
            "name": "Bowie Dick Teste",
            "code": "TQO-BWD",
            "product_id": cls.product_qo.id,
            "temperature": "134°C",
            "duration": "3.5 min",
            "load_type": "sem_carga",
        })
        cls.cycle_qo_sensiveis = cls.env["afr.qualificacao.cycle.type"].create({
            "name": "Sensíveis Vazio Teste",
            "code": "TQO-SEN",
            "product_id": cls.product_qo.id,
            "temperature": "121°C",
            "duration": "20 min",
            "load_type": "sem_carga",
        })

    def _wizard_with_qo(self, *, qo_lines, do_qo=False):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qo": do_qo,
            "qo_line_ids": [
                (0, 0, {"cycle_type_id": ct.id, "qty": qty})
                for ct, qty in qo_lines
            ],
        })
        return so, wiz

    def test_apply_creates_operational_lines_with_cycle_type(self):
        """qo_line_ids gera 1 linha SO operational com cycle_type por ciclo."""
        so, wiz = self._wizard_with_qo(qo_lines=[
            (self.cycle_qo_bowie, 3),
            (self.cycle_qo_sensiveis, 3),
        ])
        wiz.action_apply()
        qo_lines = so.order_line.filtered(
            lambda l: l.qualification_type == "operational"
            and l.cycle_type_id
        )
        self.assertEqual(len(qo_lines), 2)
        self.assertEqual(
            sorted(qo_lines.mapped("cycle_type_id.id")),
            sorted([self.cycle_qo_bowie.id, self.cycle_qo_sensiveis.id]),
        )
        self.assertEqual(
            sum(int(l.product_uom_qty) for l in qo_lines), 6,
        )

    def test_qo_no_cycles_no_lines(self):
        """F8.12 — sem qo_line_ids nada é gerado (fallback type.config removido)."""
        # equipment line sem QO precisa de outra qualif pra passar action_apply
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        self.env["afr.qualificacao.configurator.equipment"].create({
            "wizard_id": wiz.id,
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qo_line_ids": [],
        })
        wiz.action_apply()
        qo_lines = so.order_line.filtered(
            lambda l: l.qualification_type == "operational"
        )
        self.assertFalse(qo_lines, "Sem qo_line_ids, nenhuma linha QO deve ser criada.")

    def test_confirm_explodes_qo_cycles(self):
        """confirm SO gera afr.qualificacao.cycle pra cada execução QO."""
        so, wiz = self._wizard_with_qo(qo_lines=[
            (self.cycle_qo_bowie, 3),
        ])
        wiz.action_apply()
        so.action_confirm()
        qo_qualif = so.qualificacao_ids.filtered(
            lambda q: q.qualification_type == "operational"
        )
        self.assertEqual(len(qo_qualif), 1)
        self.assertEqual(len(qo_qualif.cycle_ids), 3)
        self.assertEqual(
            qo_qualif.cycle_ids[0].cycle_type_id, self.cycle_qo_bowie,
        )

    def test_helper_returns_qo_rows(self):
        """_qualif_cycle_rows_for(equip, 'qo') retorna linhas com specs."""
        so, wiz = self._wizard_with_qo(qo_lines=[
            (self.cycle_qo_bowie, 3),
        ])
        wiz.action_apply()
        rows = so._qualif_cycle_rows_for(self.equip1, "qo")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["qty"], 3)
        self.assertEqual(rows[0]["temperature"], "134°C")
        self.assertEqual(rows[0]["duration"], "3.5 min")

    def test_report_renders_qo_table_inline_in_equipment_scope(self):
        """Bloco Equipment Scope renderiza tabela QO inline com temperatura."""
        so, wiz = self._wizard_with_qo(qo_lines=[
            (self.cycle_qo_bowie, 3),
        ])
        # garante template/blocos
        so.proposal_template_id = self.env.ref(
            "afr_qualificacao.proposal_template_labquali"
        )
        wiz.action_apply()
        report = self.env.ref("sale.action_report_saleorder")
        html, _ctype = report._render_qweb_html(report.report_name, so.ids)
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn("Ciclos sem carga", html)
        self.assertIn("134°C", html)
        self.assertIn("Bowie Dick Teste", html)
