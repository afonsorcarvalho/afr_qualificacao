# -*- coding: utf-8 -*-
"""P2 (16.0.8.1.0) — biblioteca de certificados do relatório final.

Cobre: papel do certificado (afr_role), seleção por data no instrumento
(spec §4.4), seleção/arquivos por relatório e certificados de malha (D4).
"""
import base64
import io
from datetime import date, timedelta
from unittest.mock import patch

from PIL import Image

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon

PDF_BYTES = b"%PDF-1.4\n% afr test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
ENGC_REPORT = "engc_os.report_engc_os_calibration_certificate"


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _b64(raw):
    return base64.b64encode(raw)


@tagged("afr_qualificacao", "relatorio_final", "post_install", "-at_install")
class TestRelatorioCertificados(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.inicio = date(2026, 7, 10)
        cls.fim = date(2026, 7, 12)

        Inst = cls.env["engc.calibration.instruments"]
        cls.validador = Inst.create({"name": "Validador Teste", "id_number": "VT-01"})
        cls.padrao = Inst.create({"name": "Padrão Teste", "id_number": "PT-01"})
        cls.Cert = cls.env["engc.calibration.instruments.certificates"]

        cls.employee = cls.env["hr.employee"].create({"name": "Téc Relatório Teste"})
        cls.os = cls.env["afr.qualificacao.os"].create({
            "tecnico_default_id": cls.employee.id,
            "date_planned_start": "2026-07-10 08:00:00",
            "date_planned_end": "2026-07-12 17:00:00",
        })
        # Qualif + malhas ANTES do relatório: não depender da ordem de
        # recompute de qualificacao_ids (P1).
        cls.qualif = cls.env["afr.qualificacao"].create({
            "name": "Q Calib Relatório",
            "equipment_id": cls.equip1.id,
            "qualification_type": "calibration",
            "os_id": cls.os.id,
            "responsible_id": cls.env.uid,
        })
        Malha = cls.env["afr.qualificacao.malha"]
        cls.malha_t = Malha.create({
            "qualificacao_id": cls.qualif.id,
            "malha_type_id": cls.malha_temp.id,
        })
        cls.malha_p = Malha.create({
            "qualificacao_id": cls.qualif.id,
            "malha_type_id": cls.malha_press.id,
        })

        cls.os.resource_plan_line_ids.unlink()
        PlanLine = cls.env["afr.qualificacao.resource.plan.line"]
        cls.line_val = PlanLine.create({
            "os_id": cls.os.id,
            "resource_role": "validador",
            "instrument_id": cls.validador.id,
        })
        cls.line_pad = PlanLine.create({
            "os_id": cls.os.id,
            "resource_role": "padrao",
            "instrument_id": cls.padrao.id,
        })

        cls.rel = cls.env["afr.qualificacao.relatorio"].create({
            "os_id": cls.os.id,
            "equipment_id": cls.equip1.id,
            "index": 1,
            "data_inicio_ensaios": cls.inicio,
            "data_fim_ensaios": cls.fim,
        })

    # ------------------------------------------------------------------ helpers
    def _cert(self, instrument, role, date_cal, validate=None, number=None,
              content=PDF_BYTES, **extra):
        vals = {
            "instrument_id": instrument.id,
            "afr_role": role,
            "date_calibration": date_cal,
            "validate_calibration": validate or (date_cal + timedelta(days=365)),
            "certificate_number": number,
        }
        if content:
            vals["certificate_calibration"] = _b64(content)
        vals.update(extra)
        return self.Cert.create(vals)

    # ------------------------------------------------ Task 1: instrumento
    def test_afr_role_default_externo(self):
        cert = self.Cert.create({
            "instrument_id": self.padrao.id,
            "date_calibration": self.inicio,
        })
        self.assertEqual(cert.afr_role, "externo")

    def test_select_antes_latest_on_or_before_start(self):
        self._cert(self.validador, "antes", self.inicio - timedelta(days=30), number="CERT-TST-A1")
        on_start = self._cert(self.validador, "antes", self.inicio, number="CERT-TST-A2")
        self._cert(self.validador, "antes", self.inicio + timedelta(days=1), number="CERT-TST-A3")
        got = self.validador._afr_select_certificate("antes", self.inicio, self.fim)
        self.assertEqual(got, on_start, "data igual ao início conta como 'antes'")

    def test_select_antes_none_before_start(self):
        self._cert(self.validador, "antes", self.inicio + timedelta(days=1))
        got = self.validador._afr_select_certificate("antes", self.inicio, self.fim)
        self.assertFalse(got)

    def test_select_depois_earliest_on_or_after_end(self):
        self._cert(self.validador, "depois", self.fim - timedelta(days=1), number="CERT-TST-D0")
        self._cert(self.validador, "depois", self.fim + timedelta(days=5), number="CERT-TST-D5")
        on_end = self._cert(self.validador, "depois", self.fim, number="CERT-TST-D1")
        got = self.validador._afr_select_certificate("depois", self.inicio, self.fim)
        self.assertEqual(got, on_end, "data igual ao fim conta como 'depois'")

    def test_select_externo_requires_validity_window(self):
        self._cert(self.padrao, "externo", self.inicio - timedelta(days=100),
                   validate=self.inicio - timedelta(days=1), number="CERT-TST-EXP")
        boundary = self._cert(self.padrao, "externo", self.inicio - timedelta(days=30),
                              validate=self.inicio, number="CERT-TST-OK")
        self._cert(self.padrao, "externo", self.inicio + timedelta(days=1),
                   number="CERT-TST-FUT")
        got = self.padrao._afr_select_certificate("externo", self.inicio, self.fim)
        self.assertEqual(got, boundary, "validade igual ao início ainda vale")

    def test_select_externo_calibrated_on_start_counts(self):
        same_day = self._cert(self.padrao, "externo", self.inicio, number="CERT-TST-SD")
        got = self.padrao._afr_select_certificate("externo", self.inicio, self.fim)
        self.assertEqual(got, same_day)

    def test_select_externo_without_validity_is_ignored(self):
        cert = self._cert(self.padrao, "externo", self.inicio - timedelta(days=5))
        cert.validate_calibration = False
        got = self.padrao._afr_select_certificate("externo", self.inicio, self.fim)
        self.assertFalse(got)

    def test_select_ignores_superseded(self):
        older = self._cert(self.validador, "antes", self.inicio - timedelta(days=20), number="CERT-TST-OLD")
        newer = self._cert(self.validador, "antes", self.inicio - timedelta(days=2), number="CERT-TST-NEW")
        newer.superseded_by_id = older.id
        got = self.validador._afr_select_certificate("antes", self.inicio, self.fim)
        self.assertEqual(got, older)

    def test_select_ignores_other_roles(self):
        self._cert(self.validador, "externo", self.inicio - timedelta(days=1))
        self._cert(self.validador, "depois", self.inicio - timedelta(days=1))
        got = self.validador._afr_select_certificate("antes", self.inicio, self.fim)
        self.assertFalse(got)

    def test_select_missing_dates_returns_empty(self):
        self._cert(self.validador, "antes", self.inicio - timedelta(days=1))
        self._cert(self.validador, "depois", self.fim + timedelta(days=1))
        self._cert(self.padrao, "externo", self.inicio - timedelta(days=1))
        self.assertFalse(self.validador._afr_select_certificate("antes", False, self.fim))
        self.assertFalse(self.validador._afr_select_certificate("depois", self.inicio, False))
        self.assertFalse(self.padrao._afr_select_certificate("externo", None, None))

    def test_select_unknown_role_raises(self):
        with self.assertRaises(ValueError):
            self.validador._afr_select_certificate("durante", self.inicio, self.fim)

    def test_file_content_prefers_binary(self):
        cert = self._cert(self.padrao, "externo", self.inicio)
        self.assertEqual(cert._afr_file_content(), PDF_BYTES)

    def test_file_content_fallback_skips_rows_without_file(self):
        cert = self._cert(self.padrao, "externo", self.inicio, content=None)
        cert.certificate_file_ids = [
            (0, 0, {"name": "Sem arquivo"}),
            (0, 0, {"name": "EN", "file": _b64(b"%PDF-1.4 english"),
                    "filename": "cert_en.pdf"}),
        ]
        self.assertEqual(cert._afr_file_content(), b"%PDF-1.4 english")

    def test_file_content_empty_when_nothing(self):
        cert = self._cert(self.padrao, "externo", self.inicio, content=None)
        self.assertEqual(cert._afr_file_content(), b"")

    def test_instrument_form_shows_afr_role(self):
        form = self.env.ref("engc_os.calibration_instruments_form")
        arch = self.env["engc.calibration.instruments"].get_view(
            form.id, "form")["arch"]
        self.assertIn('name="afr_role"', arch)
