"""Testa propagação qty_delivered ao aprovar qualif (com cycles/malhas passed)."""

from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestQtyDeliveredPropagation(AfrQualificacaoTestCommon):

    def _setup_confirmed_so(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "do_qi": True,
            "qd_line_ids": [(0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 3})],
            "calib_line_ids": [(0, 0, {"malha_type_id": self.malha_temp.id, "qty": 5})],
        })]
        wiz.action_apply()
        so.action_confirm()
        return so

    def test_approve_qi_propagates_qty_delivered_1(self):
        so = self._setup_confirmed_so()
        qi = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "installation")
        qi.action_mark_approved()
        qi_line = so.order_line.filtered(lambda l: l.qualification_type == "installation")
        self.assertEqual(qi_line.qty_delivered, 1.0)
        self.assertEqual(qi_line.invoice_status, "to invoice")

    def test_approve_qd_propagates_passed_cycles(self):
        so = self._setup_confirmed_so()
        qd = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "performance")
        # 2 de 3 passed
        qd.cycle_ids[:2].state = "passed"
        qd.action_mark_approved()
        qd_line = so.order_line.filtered(lambda l: l.qualification_type == "performance")
        self.assertEqual(qd_line.qty_delivered, 2.0)

    def test_approve_calib_propagates_passed_malhas(self):
        so = self._setup_confirmed_so()
        calib = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "calibration")
        # todos 5 passed
        calib.malha_ids.write({"state": "passed"})
        calib.action_mark_approved()
        calib_line = so.order_line.filtered(lambda l: l.qualification_type == "calibration")
        self.assertEqual(calib_line.qty_delivered, 5.0)
        self.assertEqual(calib_line.invoice_status, "to invoice")

    def test_qualif_invoice_status_compute(self):
        so = self._setup_confirmed_so()
        qi = so.qualificacao_ids.filtered(lambda q: q.qualification_type == "installation")
        # antes do approve: invoice_status='no' (qty_delivered=0)
        self.assertEqual(qi.invoice_status, "no")
        qi.action_mark_approved()
        self.assertEqual(qi.invoice_status, "to invoice")
