# -*- coding: utf-8 -*-
"""F4.3 (16.0.3.4.0): cobertura grandeza ↔ instrumento.

- sensor_kind_ids/measurement_unit_ids derivados dos certificados
- requires_instrument default por kind
- coverage_complete computed em collect.item + agregação no qualif
- Gate em action_mark_approved com flag qualif_block_approval_incomplete_coverage
"""
import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


_PNG_BYTES = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00")


@tagged("afr_qualificacao", "coverage", "post_install", "-at_install")
class TestCoverage(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Unidades de medida + grandeza
        Unit = cls.env["engc.calibration.measurement.unit"]
        cls.unit_celsius = Unit.create({
            "name": "Celsius",
            "simbolo": "°C",
            "afr_sensor_kind_id": cls.sensor_temp.id,
        })
        cls.unit_bar = Unit.create({
            "name": "Bar",
            "simbolo": "bar",
            "afr_sensor_kind_id": cls.sensor_press.id,
        })
        cls.unit_unmapped = Unit.create({
            "name": "Volt",
            "simbolo": "V",
            # sem afr_sensor_kind_id → não cobre grandeza
        })

        # Procedimento de calibração
        cls.measurement_procedure = cls.env.ref(
            "engc_os.engc_calibration_measurement_procedure_iso17025",
            raise_if_not_found=False,
        ) or cls.env["engc.calibration.measurement.procedure"].search([], limit=1)
        if not cls.measurement_procedure:
            cls.measurement_procedure = cls.env[
                "engc.calibration.measurement.procedure"
            ].create({"name": "Test Procedure"})

        # Helper para criar instrumento com cobertura
        cls.inst_temp = cls._create_instrument_with_coverage(
            cls, "Termo-Temp", [cls.unit_celsius]
        )
        cls.inst_press = cls._create_instrument_with_coverage(
            cls, "Mano-Press", [cls.unit_bar]
        )
        cls.inst_temp_press = cls._create_instrument_with_coverage(
            cls, "Multi-T-P", [cls.unit_celsius, cls.unit_bar]
        )
        cls.inst_no_coverage = cls.env["engc.calibration.instruments"].create({
            "name": "Sem cobertura",
        })

        # Procedimento.item exigindo TEMP
        cls.proc = cls.env["afr.qualificacao.procedimento"].create({
            "name": "Test Proc",
            "code": "TEST-PROC-001",
        })
        cls.proc_item_temp = cls.env["afr.qualificacao.procedimento.item"].create({
            "procedimento_id": cls.proc.id,
            "name": "Coleta Temperatura",
            "phase": "calibration",
            "kind": "qualificador_data",
            "required": True,
            "target_level": "qualificacao",
            "requires_instrument": True,
            "required_sensor_kind_ids": [(6, 0, [cls.sensor_temp.id])],
        })
        cls.proc_item_temp_press = cls.env["afr.qualificacao.procedimento.item"].create({
            "procedimento_id": cls.proc.id,
            "name": "Coleta T+P",
            "phase": "calibration",
            "kind": "qualificador_data",
            "required": True,
            "target_level": "qualificacao",
            "requires_instrument": True,
            "required_sensor_kind_ids": [
                (6, 0, [cls.sensor_temp.id, cls.sensor_press.id])
            ],
        })
        cls.proc_item_foto = cls.env["afr.qualificacao.procedimento.item"].create({
            "procedimento_id": cls.proc.id,
            "name": "Foto carga",
            "kind": "foto",
            "required": True,
            "target_level": "qualificacao",
            # requires_instrument default False para foto
        })

        # Qualif mínima
        cls.qualif = cls.env["afr.qualificacao"].create({
            "equipment_id": cls.equip1.id,
            "qualification_type": "installation",
        })

    @staticmethod
    def _create_instrument_with_coverage(cls, name, units):
        inst = cls.env["engc.calibration.instruments"].create({"name": name})
        cert = cls.env["engc.calibration.instruments.certificates"].create({
            "instrument_id": inst.id,
            "certificate_number": "C-%s" % name,
            "date_calibration": fields.Date.today() - timedelta(days=30),
            "validate_calibration": fields.Date.today() + timedelta(days=300),
        })
        for u in units:
            cls.env["engc.calibration.instruments.uncertainty.lines"].create({
                "certificate": cert.id,
                "unit_of_measurement": u.id,
                "uncertainty": 0.1,
                "coverage_factor": 2.0,
                "resolution": 0.01,
            })
        return inst

    def _make_collect_item(self, proc_item, instruments=None):
        vals = {
            "qualif_id": self.qualif.id,
            "name": proc_item.name,
            "kind": proc_item.kind,
            "required": proc_item.required,
            "procedimento_item_id": proc_item.id,
        }
        if instruments:
            vals["standard_instrument_ids"] = [(6, 0, instruments.ids)]
        return self.env["afr.qualificacao.collect.item"].create(vals)

    # ---------------- Instrument coverage derivation ----------------

    def test_instrument_sensor_kinds_derived_from_unit(self):
        self.assertIn(self.sensor_temp, self.inst_temp.sensor_kind_ids)
        self.assertEqual(len(self.inst_temp.sensor_kind_ids), 1)

    def test_instrument_multi_sensor_kinds(self):
        kinds = self.inst_temp_press.sensor_kind_ids
        self.assertIn(self.sensor_temp, kinds)
        self.assertIn(self.sensor_press, kinds)

    def test_instrument_no_coverage_when_no_certs(self):
        self.assertFalse(self.inst_no_coverage.sensor_kind_ids)

    def test_instrument_ignores_unit_without_mapping(self):
        inst = self._create_instrument_with_coverage(
            self, "Apenas Volt", [self.unit_unmapped]
        )
        self.assertFalse(inst.sensor_kind_ids)
        self.assertIn(self.unit_unmapped, inst.measurement_unit_ids)

    # ---------------- procedimento.item default by kind ----------------

    def test_default_requires_instrument_foto_false(self):
        item = self.env["afr.qualificacao.procedimento.item"].create({
            "procedimento_id": self.proc.id,
            "name": "F",
            "kind": "foto",
            "target_level": "qualificacao",
        })
        self.assertFalse(item.requires_instrument)

    def test_default_requires_instrument_excel_true(self):
        item = self.env["afr.qualificacao.procedimento.item"].with_context(
            default_kind="excel"
        ).create({
            "procedimento_id": self.proc.id,
            "name": "E",
            "kind": "excel",
            "target_level": "qualificacao",
        })
        self.assertTrue(item.requires_instrument)

    # ---------------- collect.item coverage ----------------

    def test_coverage_complete_when_required_kind_covered(self):
        item = self._make_collect_item(self.proc_item_temp, self.inst_temp)
        self.assertTrue(item.coverage_complete)
        self.assertFalse(item.coverage_warning_text)

    def test_coverage_incomplete_when_missing_kind(self):
        item = self._make_collect_item(self.proc_item_temp_press, self.inst_temp)
        self.assertFalse(item.coverage_complete)
        self.assertIn("Press", item.coverage_warning_text)

    def test_coverage_complete_with_multi_instrument(self):
        item = self._make_collect_item(
            self.proc_item_temp_press,
            self.inst_temp | self.inst_press,
        )
        self.assertTrue(item.coverage_complete)

    def test_coverage_complete_when_not_requires_instrument(self):
        item = self._make_collect_item(self.proc_item_foto)
        self.assertTrue(item.coverage_complete)

    def test_coverage_incomplete_when_requires_but_no_instruments(self):
        item = self._make_collect_item(self.proc_item_temp)
        self.assertFalse(item.coverage_complete)

    # ---------------- qualif aggregation ----------------

    def test_qualif_coverage_aggregation_incomplete(self):
        self._make_collect_item(self.proc_item_temp)  # sem instruments
        self.qualif.invalidate_recordset()
        self.assertFalse(self.qualif.coverage_complete)
        self.assertIn("Coleta Temperatura", self.qualif.coverage_warning_text)

    def test_qualif_coverage_aggregation_complete(self):
        self._make_collect_item(self.proc_item_temp, self.inst_temp)
        self.qualif.invalidate_recordset()
        self.assertTrue(self.qualif.coverage_complete)

    def test_qualif_coverage_ignores_non_required_items(self):
        self._make_collect_item(self.proc_item_temp, self.inst_temp)
        opt = self._make_collect_item(self.proc_item_temp)  # sem instruments
        opt.required = False
        self.qualif.invalidate_recordset()
        self.assertTrue(self.qualif.coverage_complete)

    # ---------------- approval gate ----------------

    def _set_flag(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            "afr_qualificacao.qualif_block_approval_incomplete_coverage",
            "True" if value else "False",
        )

    def test_approval_blocked_when_flag_on_and_incomplete(self):
        self._make_collect_item(self.proc_item_temp_press, self.inst_temp)
        self._set_flag(True)
        with self.assertRaises(ValidationError):
            self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "draft")

    def test_approval_warning_only_when_flag_off(self):
        self._make_collect_item(self.proc_item_temp_press, self.inst_temp)
        self._set_flag(False)
        self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "approved")
        joined = " ".join(self.qualif.message_ids.mapped("body"))
        self.assertIn("cobertura", joined.lower())

    def test_approval_passes_when_complete_and_flag_on(self):
        self._make_collect_item(self.proc_item_temp, self.inst_temp)
        self._set_flag(True)
        self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "approved")

    # ---------------- F4.7: coletas só via relatório ----------------

    def test_collected_without_relatorio_flag(self):
        item = self._make_collect_item(self.proc_item_foto)
        png = _PNG_BYTES
        item.write({"file": png, "filename": "f.png"})
        self.assertEqual(item.state, "collected")
        self.assertFalse(item.relatorio_id)
        self.assertTrue(item.collected_without_relatorio)

    def test_approval_blocked_when_collected_without_relatorio(self):
        item = self._make_collect_item(self.proc_item_foto)
        png = _PNG_BYTES
        item.write({"file": png, "filename": "f.png"})
        self.assertEqual(item.state, "collected")
        with self.assertRaises(ValidationError):
            self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "draft")

    def test_approval_passes_when_collected_with_relatorio(self):
        # Setup mínimo OS + relatorio
        os = self.env["afr.qualificacao.os"].create({
            "partner_id": self.partner.id,
        })
        self.qualif.os_id = os.id
        now = fields.Datetime.now()
        relatorio = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": os.id,
            "descricao": "Test relatorio",
            "data_inicio": now,
            "data_fim": now + timedelta(hours=1),
        })
        item = self._make_collect_item(self.proc_item_foto)
        png = _PNG_BYTES
        item.write({
            "file": png,
            "filename": "f.png",
            "relatorio_id": relatorio.id,
        })
        self.assertTrue(item.relatorio_id)
        self.assertFalse(item.collected_without_relatorio)
        self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "approved")

    def test_approval_passes_when_non_required_collected_without_relatorio(self):
        item = self._make_collect_item(self.proc_item_foto)
        item.required = False
        png = _PNG_BYTES
        item.write({"file": png, "filename": "f.png"})
        self.qualif.action_mark_approved()
        self.assertEqual(self.qualif.state, "approved")

    def test_approval_blocked_via_os_cascade(self):
        """OS.action_approve cascateia em action_mark_approved.
        Gate deve disparar nas qualifs antes do OS marcar approved.
        """
        self._make_collect_item(self.proc_item_temp_press, self.inst_temp)
        os = self.env["afr.qualificacao.os"].create({
            "partner_id": self.partner.id,
            "tecnico_default_id": self.env["hr.employee"].search([], limit=1).id
                                  or self.env["hr.employee"].create({"name": "T"}).id,
        })
        self.qualif.os_id = os.id
        self.qualif.responsible_id = self.env.user.id
        self.qualif.state = "in_progress"
        os.state = "in_approved"
        self._set_flag(True)
        with self.assertRaises(ValidationError):
            os.action_approve()
        self.assertEqual(self.qualif.state, "in_progress")
        self.assertEqual(os.state, "in_approved")
