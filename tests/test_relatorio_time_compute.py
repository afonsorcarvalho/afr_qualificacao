# -*- coding: utf-8 -*-
"""Testes do cálculo de tempo do relatório parcial e agregação na OS (F1)."""
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("afr_qualificacao", "os_relatorio", "post_install", "-at_install")
class TestRelatorioTimeCompute(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tecnico = cls.env["hr.employee"].create({"name": "Téc Tempo"})
        cls.os = cls.env["afr.qualificacao.os"].create({
            "tecnico_default_id": cls.tecnico.id,
            "date_planned_start": datetime(2026, 6, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 6, 1, 17, 0, 0),
        })

    def _make_relatorio(self, h_start, h_end, descricao="Teste", state="draft"):
        r = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": self.os.id,
            "data_inicio": datetime(2026, 6, 1, h_start, 0, 0),
            "data_fim": datetime(2026, 6, 1, h_end, 0, 0),
            "tecnico_ids": [(6, 0, [self.tecnico.id])],
            "descricao": descricao,
        })
        if state != "draft":
            r.write({"state": state})
        return r

    # ─────────────────────────────────────────────────────────────
    # COMPUTED time_execution
    # ─────────────────────────────────────────────────────────────
    def test_time_execution_basic(self):
        r = self._make_relatorio(8, 12)
        self.assertEqual(r.time_execution, 4.0)

    def test_time_execution_zero_when_invalid(self):
        r = self._make_relatorio(8, 9)
        # Modificar para dates invalid → constraint deveria pegar antes
        self.assertEqual(r.time_execution, 1.0)

    def test_constraint_data_fim_before_inicio(self):
        with self.assertRaises(ValidationError):
            self.env["afr.qualificacao.os.relatorio"].create({
                "os_id": self.os.id,
                "data_inicio": datetime(2026, 6, 1, 12, 0, 0),
                "data_fim": datetime(2026, 6, 1, 11, 0, 0),
                "tecnico_ids": [(6, 0, [self.tecnico.id])],
                "descricao": "Inválido",
            })

    # ─────────────────────────────────────────────────────────────
    # AGGREGATION na OS
    # ─────────────────────────────────────────────────────────────
    def test_os_date_actual_min_max(self):
        self._make_relatorio(8, 10)
        self._make_relatorio(13, 17)
        self.os.invalidate_recordset()
        self.assertEqual(self.os.date_actual_start.hour, 8)
        self.assertEqual(self.os.date_actual_end.hour, 17)

    def test_os_duration_actual_sums(self):
        self._make_relatorio(8, 10)   # 2h
        self._make_relatorio(13, 17)  # 4h
        self.os.invalidate_recordset()
        self.assertEqual(self.os.duration_actual, 6.0)

    def test_cancelled_relatorios_excluded(self):
        self._make_relatorio(8, 10)
        self._make_relatorio(13, 17, state="cancel")
        self.os.invalidate_recordset()
        self.assertEqual(self.os.duration_actual, 2.0)
        self.assertEqual(self.os.date_actual_end.hour, 10)

    def test_relatorio_count_compute(self):
        self._make_relatorio(8, 10)
        self._make_relatorio(13, 17)
        self.os.invalidate_recordset()
        self.assertEqual(self.os.relatorio_count, 2)

    # ─────────────────────────────────────────────────────────────
    # WORKFLOW relatório
    # ─────────────────────────────────────────────────────────────
    def test_action_done_requires_descricao(self):
        r = self._make_relatorio(8, 10, descricao="")
        # constraint passes (empty string accepted at create), action_done blocks
        r.write({"descricao": ""})
        with self.assertRaisesRegex(UserError, "obrigatória"):
            r.action_done()

    def test_action_done_requires_positive_time(self):
        r = self._make_relatorio(8, 9)
        r.write({"data_fim": r.data_inicio})  # 0h
        with self.assertRaisesRegex(UserError, "> 0"):
            r.action_done()

    def test_action_done_success(self):
        r = self._make_relatorio(8, 12)
        r.action_done()
        self.assertEqual(r.state, "done")

    def test_action_cancel(self):
        r = self._make_relatorio(8, 12)
        r.action_cancel()
        self.assertEqual(r.state, "cancel")

    def test_action_reopen_from_done(self):
        r = self._make_relatorio(8, 12)
        r.action_done()
        r.action_reopen()
        self.assertEqual(r.state, "draft")

    # ─────────────────────────────────────────────────────────────
    # SEQUENCE
    # ─────────────────────────────────────────────────────────────
    def test_create_assigns_sequence(self):
        r = self._make_relatorio(8, 9)
        self.assertTrue(r.name.startswith("RQOS"))
