# -*- coding: utf-8 -*-
"""Testes F4 (16.0.3.3.0): padrões metrológicos M2M em collect.item + agregação em qualif."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "standards", "post_install", "-at_install")
class TestStandardInstruments(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Inst = cls.env["engc.calibration.instruments"]
        cls.inst_valid = Inst.create({"name": "Termo-1 (válido)", "id_number": "T1"})
        cls.inst_expired = Inst.create({"name": "Termo-2 (expirado)", "id_number": "T2"})
        cls.inst_no_cert = Inst.create({"name": "Termo-3 (sem cert)", "id_number": "T3"})

        today = fields.Date.today()
        Cert = cls.env["engc.calibration.instruments.certificates"]
        Cert.create({
            "instrument_id": cls.inst_valid.id,
            "certificate_number": "CRT-VAL-001",
            "date_calibration": today - timedelta(days=30),
            "validate_calibration": today + timedelta(days=180),
        })
        Cert.create({
            "instrument_id": cls.inst_expired.id,
            "certificate_number": "CRT-EXP-001",
            "date_calibration": today - timedelta(days=400),
            "validate_calibration": today - timedelta(days=30),
        })

        # Qualif mínima para os testes
        cls.qualif = cls.env["afr.qualificacao"].create({
            "equipment_id": cls.equip1.id,
            "qualification_type": "installation",
        })

    def _make_collect_item(self, instruments=None, name="Item-X"):
        vals = {
            "qualif_id": self.qualif.id,
            "name": name,
            "kind": "foto",
            "required": True,
        }
        if instruments:
            vals["standard_instrument_ids"] = [(6, 0, instruments.ids)]
        return self.env["afr.qualificacao.collect.item"].create(vals)

    # ------------------------- collect.item ---------------------------

    def test_collect_item_no_standards_is_valid(self):
        item = self._make_collect_item()
        self.assertTrue(item.standards_all_valid)
        self.assertFalse(item.standards_warning_text)

    def test_collect_item_valid_certificate(self):
        item = self._make_collect_item(self.inst_valid)
        self.assertTrue(item.standards_all_valid)
        self.assertFalse(item.standards_warning_text)

    def test_collect_item_expired_certificate(self):
        item = self._make_collect_item(self.inst_expired)
        self.assertFalse(item.standards_all_valid)
        self.assertIn("Termo-2", item.standards_warning_text)

    def test_collect_item_instrument_without_cert(self):
        item = self._make_collect_item(self.inst_no_cert)
        self.assertFalse(item.standards_all_valid)
        self.assertIn("Termo-3", item.standards_warning_text)

    def test_collect_item_mixed_lists_only_invalid(self):
        item = self._make_collect_item(self.inst_valid | self.inst_expired)
        self.assertFalse(item.standards_all_valid)
        self.assertIn("Termo-2", item.standards_warning_text)
        self.assertNotIn("Termo-1", item.standards_warning_text)

    # ------------------------- qualif aggregation ---------------------

    def test_qualif_aggregates_union_of_items(self):
        self._make_collect_item(self.inst_valid, name="A")
        self._make_collect_item(self.inst_expired, name="B")
        self.qualif.invalidate_recordset()
        self.assertEqual(self.qualif.standard_instrument_count, 2)
        self.assertIn(self.inst_valid, self.qualif.standard_instrument_ids)
        self.assertIn(self.inst_expired, self.qualif.standard_instrument_ids)

    def test_qualif_validity_aggregation(self):
        self._make_collect_item(self.inst_valid, name="A")
        self.qualif.invalidate_recordset()
        self.assertTrue(self.qualif.standards_all_valid)

        self._make_collect_item(self.inst_expired, name="B")
        self.qualif.invalidate_recordset()
        self.assertFalse(self.qualif.standards_all_valid)
        self.assertIn("Termo-2", self.qualif.standards_warning_text)

    # ------------------------- gate em action_mark_approved -----------

    def _set_block_flag(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            "afr_qualificacao.qualif_block_approval_expired_standards",
            "True" if value else "False",
        )

    def test_approval_blocked_when_flag_true_and_expired(self):
        self._make_collect_item(self.inst_expired)
        self._set_block_flag(True)
        with self.assertRaises(ValidationError):
            self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "draft")

    def test_approval_warning_only_when_flag_false_and_expired(self):
        self._make_collect_item(self.inst_expired)
        self._set_block_flag(False)
        self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "approved")
        # mensagem registrada no chatter
        messages = self.qualif.message_ids.mapped("body")
        joined = " ".join(messages)
        self.assertIn("Termo-2", joined)

    def test_approval_passes_with_all_valid_standards(self):
        self._make_collect_item(self.inst_valid)
        self._set_block_flag(True)
        self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "approved")

    def test_approval_passes_with_no_standards(self):
        self._make_collect_item()  # sem standards
        self._set_block_flag(True)
        self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "approved")
