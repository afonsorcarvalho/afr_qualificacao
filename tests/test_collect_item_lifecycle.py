# -*- coding: utf-8 -*-
"""Testes do ciclo de vida do collect.item (F3): pending → collected/skipped."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "collect_item", "post_install", "-at_install")
class TestCollectItemLifecycle(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # OS + qualif manual (sem procedimento)
        cls.os = cls.env["afr.qualificacao.os"].create({
            "tecnico_default_id": cls.env["hr.employee"].create({"name": "Téc Coleta"}).id,
            "date_planned_start": "2026-06-01 08:00:00",
            "date_planned_end": "2026-06-01 17:00:00",
        })
        cls.qualif = cls.env["afr.qualificacao"].create({
            "name": "QualifTestCollect",
            "equipment_id": cls.equip1.id,
            "qualification_type": "installation",
            "os_id": cls.os.id,
            "responsible_id": cls.env.uid,
        })

    def _make_item(self, **kw):
        vals = {
            "name": "TestItem",
            "kind": "foto",
            "required": True,
            "qualif_id": self.qualif.id,
        }
        vals.update(kw)
        return self.env["afr.qualificacao.collect.item"].create(vals)

    # ─────────────────────────────────────────────────────────────
    # CREATE pending
    # ─────────────────────────────────────────────────────────────
    def test_create_default_pending(self):
        item = self._make_item()
        self.assertEqual(item.state, "pending")
        self.assertFalse(item.file)
        self.assertFalse(item.captured_at)
        self.assertFalse(item.captured_by)

    def test_related_os_id_stored(self):
        item = self._make_item()
        self.assertEqual(item.os_id, self.os)
        self.assertEqual(item.equipment_id, self.equip1)

    # ─────────────────────────────────────────────────────────────
    # Upload (write file) auto-marca collected
    # ─────────────────────────────────────────────────────────────
    def test_write_file_auto_marks_collected(self):
        item = self._make_item()
        # PNG transparente 1x1 base64
        png = (b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
               b"DUlEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC")
        item.write({"file": png, "filename": "test.png"})
        self.assertEqual(item.state, "collected")
        self.assertTrue(item.captured_at)
        self.assertEqual(item.captured_by, self.env.user)

    # ─────────────────────────────────────────────────────────────
    # Constraint: collected sem file falha
    # ─────────────────────────────────────────────────────────────
    def test_collected_without_file_raises(self):
        item = self._make_item()
        with self.assertRaises(ValidationError):
            item.write({"state": "collected"})

    # ─────────────────────────────────────────────────────────────
    # Skip
    # ─────────────────────────────────────────────────────────────
    def test_action_skip(self):
        item = self._make_item()
        item.action_mark_skipped()
        self.assertEqual(item.state, "skipped")

    # ─────────────────────────────────────────────────────────────
    # Reset pending (limpa arquivo)
    # ─────────────────────────────────────────────────────────────
    def test_action_reset_pending(self):
        item = self._make_item()
        png = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
        item.write({"file": png, "filename": "test.png"})
        self.assertEqual(item.state, "collected")
        item.action_reset_pending()
        self.assertEqual(item.state, "pending")
        self.assertFalse(item.file)
        self.assertFalse(item.captured_at)

    # ─────────────────────────────────────────────────────────────
    # Counts agregados em qualif e OS
    # ─────────────────────────────────────────────────────────────
    def test_qualif_pending_count(self):
        self._make_item(required=True)
        self._make_item(required=True, name="X2")
        self._make_item(required=False, name="X3")
        self.qualif.invalidate_recordset()
        self.assertEqual(self.qualif.collect_pending_count, 2)  # apenas required

    def test_os_collect_counts(self):
        self._make_item(required=True)
        item2 = self._make_item(required=True, name="X2")
        png = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
        item2.write({"file": png, "filename": "x2.png"})
        self.os.invalidate_recordset()
        self.assertEqual(self.os.collect_total_count, 2)
        self.assertEqual(self.os.collect_collected_count, 1)
        self.assertEqual(self.os.collect_pending_count, 1)
