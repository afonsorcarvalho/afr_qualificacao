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

    # ------------------------------------------------ Task 2: relatório
    def _by_key(self, selection):
        return {(s["instrument"].id, s["role"]): s for s in selection}

    def test_selection_shape_and_order(self):
        sel = self.rel._afr_certificate_selection()
        self.assertEqual(
            [(s["instrument"], s["resource_role"], s["role"]) for s in sel],
            [
                (self.validador, "validador", "antes"),
                (self.validador, "validador", "depois"),
                (self.padrao, "padrao", "externo"),
            ],
        )
        for s in sel:
            self.assertEqual(set(s), {"instrument", "resource_role", "role", "certificate"})
            self.assertFalse(s["certificate"], "sem certificados cadastrados → vazio")

    def test_selection_picks_certificates_by_date(self):
        antes = self._cert(self.validador, "antes", self.inicio, number="CERT-TST-A")
        depois = self._cert(self.validador, "depois", self.fim, number="CERT-TST-D")
        externo = self._cert(self.padrao, "externo", self.inicio - timedelta(days=10),
                             number="CERT-TST-E")
        by = self._by_key(self.rel._afr_certificate_selection())
        self.assertEqual(by[(self.validador.id, "antes")]["certificate"], antes)
        self.assertEqual(by[(self.validador.id, "depois")]["certificate"], depois)
        self.assertEqual(by[(self.padrao.id, "externo")]["certificate"], externo)

    def test_selection_skips_lines_without_instrument(self):
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "padrao",
        })
        self.assertEqual(len(self.rel._afr_certificate_selection()), 3)

    def test_selection_dedupes_instrument(self):
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "validador",
            "instrument_id": self.validador.id,
        })
        self.assertEqual(len(self.rel._afr_certificate_selection()), 3)

    def test_selection_instrument_with_both_roles(self):
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "padrao",
            "instrument_id": self.validador.id,
        })
        sel = self.rel._afr_certificate_selection()
        roles_validador = [s["role"] for s in sel if s["instrument"] == self.validador]
        self.assertEqual(roles_validador, ["antes", "depois", "externo"])
        self.assertEqual(len(sel), 4)

    def test_selection_without_dates_all_empty(self):
        self._cert(self.validador, "antes", self.inicio - timedelta(days=1))
        self._cert(self.validador, "depois", self.fim + timedelta(days=1))
        self._cert(self.padrao, "externo", self.inicio - timedelta(days=1))
        self.rel.write({"data_inicio_ensaios": False, "data_fim_ensaios": False})
        sel = self.rel._afr_certificate_selection()
        self.assertEqual(len(sel), 3)
        self.assertFalse(any(s["certificate"] for s in sel))

    def test_selection_excludes_instrument_of_other_equipment(self):
        outro = self.env["engc.calibration.instruments"].create(
            {"name": "Validador Outro Equip", "id_number": "VT-02"})
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "validador",
            "instrument_id": outro.id,
            "equipment_ids": [(6, 0, [self.equip2.id])],
        })
        sel = self.rel._afr_certificate_selection()
        self.assertNotIn(outro, [s["instrument"] for s in sel])
        self.assertEqual(len(sel), 3)

    def test_selection_includes_line_for_this_equipment(self):
        proprio = self.env["engc.calibration.instruments"].create(
            {"name": "Padrão Deste Equip", "id_number": "PT-02"})
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "padrao",
            "instrument_id": proprio.id,
            "equipment_ids": [(6, 0, [self.equip1.id, self.equip2.id])],
        })
        sel = self.rel._afr_certificate_selection()
        self.assertIn(proprio, [s["instrument"] for s in sel])
        self.assertEqual(len(sel), 4)

    def test_selection_includes_line_with_empty_equipment_ids(self):
        # line_val/line_pad do setUpClass não têm equipment_ids → entram.
        self.assertFalse(self.line_val.equipment_ids)
        self.assertFalse(self.line_pad.equipment_ids)
        sel = self.rel._afr_certificate_selection()
        self.assertEqual({s["instrument"] for s in sel}, {self.validador, self.padrao})

    def test_selection_empty_plan(self):
        self.os.resource_plan_line_ids.unlink()
        self.assertEqual(self.rel._afr_certificate_selection(), [])

    def test_files_filter_by_roles(self):
        self._cert(self.validador, "antes", self.inicio, number="CERT-TST-A")
        depois = self._cert(self.validador, "depois", self.fim, number="CERT-TST-D",
                            content=None)
        depois.certificate_file_ids = [
            (0, 0, {"name": "EN", "file": _b64(b"%PDF-1.4 depois")}),
        ]
        self._cert(self.padrao, "externo", self.inicio, number="CERT-TST-E")

        files = self.rel._afr_certificate_files(["antes", "depois"])
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0][0], PDF_BYTES)
        self.assertEqual(files[0][1], "application/pdf")
        self.assertIn("CERT-TST-A", files[0][2])
        self.assertIn("Validador Teste", files[0][2])
        self.assertIn("Antes da campanha", files[0][2])
        self.assertEqual(files[1][0], b"%PDF-1.4 depois")
        self.assertIn("Depois da campanha", files[1][2])

        ext = self.rel._afr_certificate_files(["externo"])
        self.assertEqual(len(ext), 1)
        self.assertIn("CERT-TST-E", ext[0][2])
        self.assertIn("Padrão Teste", ext[0][2])

    def test_files_image_mimetype(self):
        self._cert(self.padrao, "externo", self.inicio, number="CERT-TST-IMG",
                   content=_png_bytes())
        files = self.rel._afr_certificate_files(["externo"])
        self.assertEqual(files[0][1], "image/png")

    def test_files_skip_certificate_without_any_file(self):
        self._cert(self.padrao, "externo", self.inicio, number="CERT-TST-NF",
                   content=None)
        self.assertEqual(self.rel._afr_certificate_files(["externo"]), [])
        # antes/depois ausentes também não geram tupla
        self.assertEqual(self.rel._afr_certificate_files(["antes", "depois"]), [])

    def test_files_caption_without_number(self):
        self._cert(self.padrao, "externo", self.inicio, number=False)
        files = self.rel._afr_certificate_files(["externo"])
        self.assertTrue(files[0][2].startswith("Certificado s/nº — Padrão Teste"))
        self.assertNotIn("False", files[0][2])

    # ------------------------------------------------ Task 3: malhas
    def _engc_calibration(self):
        # Obrigatórios do engc_os: client_id, equipment_id, technician_id,
        # date_calibration, measurement_procedure (M2O required) e
        # instruments_ids (M2M required; o domínio do instrumento da medição
        # sai daqui).
        procedure = self.env["engc.calibration.measurement.procedure"].create({
            "codigo": "PROC-TST",
            "description": "Procedimento Teste",
        })
        return self.env["engc.calibration"].create({
            "client_id": self.partner.id,
            "equipment_id": self.equip1.id,
            "technician_id": self.employee.id,
            "date_calibration": self.inicio,
            "measurement_procedure": procedure.id,
            "instruments_ids": [(6, 0, [self.padrao.id])],
        })

    def _link_malha(self, malha, calibration):
        meas = self.env["engc.calibration.measurement"].create({
            "calibration_id": calibration.id,
            "instrument_id": self.padrao.id,
        })
        malha.engc_calibration_measurement_id = meas.id
        return meas

    def _item(self, malha, name, content, mimetype, sequence=10):
        vals = {
            "qualif_id": self.qualif.id,
            "malha_id": malha.id,
            "name": name,
            "kind": "pdf",
            "sequence": sequence,
            "mimetype": mimetype,
        }
        if content:
            vals["file"] = _b64(content)
        return self.env["afr.qualificacao.collect.item"].create(vals)

    def _patch_report(self):
        Report = type(self.env["ir.actions.report"])
        return patch.object(
            Report, "_render_qweb_pdf",
            return_value=(b"%PDF-1.4 engc-cert", "pdf"),
        )

    def test_engc_report_xmlid_exists(self):
        report = self.env.ref(ENGC_REPORT)
        self.assertEqual(report.model, "engc.calibration")

    def test_malha_collect_item_ids_inverse(self):
        item = self._item(self.malha_t, "Cert malha T", PDF_BYTES, "application/pdf")
        self.assertIn(item, self.malha_t.collect_item_ids)
        self.assertNotIn(item, self.malha_p.collect_item_ids)

    def test_malha_files_from_engc_calibration(self):
        cal = self._engc_calibration()
        self._link_malha(self.malha_t, cal)
        with self._patch_report() as render:
            files = self.rel._afr_malha_certificate_files()
        render.assert_called_once()
        self.assertEqual(render.call_args.args, (ENGC_REPORT, [cal.id]))
        self.assertEqual(len(files), 1, "malha_p sem calibração e sem arquivo → nada")
        content, mimetype, caption = files[0]
        self.assertEqual(content, b"%PDF-1.4 engc-cert")
        self.assertEqual(mimetype, "application/pdf")
        self.assertIn(cal.name, caption)
        self.assertIn(self.malha_t.display_name, caption)

    def test_malha_same_calibration_rendered_once(self):
        cal = self._engc_calibration()
        self._link_malha(self.malha_t, cal)
        self._link_malha(self.malha_p, cal)
        with self._patch_report() as render:
            files = self.rel._afr_malha_certificate_files()
        render.assert_called_once()
        self.assertEqual(len(files), 1)

    def test_malha_engc_wins_over_collect_items(self):
        cal = self._engc_calibration()
        self._link_malha(self.malha_t, cal)
        self._item(self.malha_t, "PDF anexado", PDF_BYTES, "application/pdf")
        with self._patch_report():
            files = self.rel._afr_malha_certificate_files()
        self.assertEqual([f[0] for f in files], [b"%PDF-1.4 engc-cert"])

    def test_malha_files_fallback_collect_items(self):
        png = _png_bytes()
        self._item(self.malha_t, "Foto certificado", png, "image/png", sequence=20)
        self._item(self.malha_t, "PDF certificado", PDF_BYTES, "application/pdf", sequence=10)
        self._item(self.malha_t, "Planilha", b"a;b\n1;2\n", "text/csv", sequence=5)
        self._item(self.malha_t, "Pendente", None, "application/pdf", sequence=1)
        with self._patch_report() as render:
            files = self.rel._afr_malha_certificate_files()
        render.assert_not_called()
        self.assertEqual([f[1] for f in files], ["application/pdf", "image/png"])
        self.assertEqual(files[0][0], PDF_BYTES)
        self.assertEqual(files[1][0], png)
        self.assertIn("PDF certificado", files[0][2])
        self.assertIn(self.malha_t.display_name, files[0][2])

    def test_malha_files_guess_mimetype_when_missing(self):
        self._item(self.malha_p, "Sem mimetype", PDF_BYTES, False)
        with self._patch_report():
            files = self.rel._afr_malha_certificate_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][1], "application/pdf")

    def test_malha_files_sniffs_octet_stream(self):
        # PWA grava mimetype 'application/octet-stream' (untrustworthy);
        # o conteúdo real é PDF e deve ser reconhecido pela sniff dos bytes.
        self._item(self.malha_p, "PWA sem mimetype confiável", PDF_BYTES,
                   "application/octet-stream")
        with self._patch_report():
            files = self.rel._afr_malha_certificate_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][0], PDF_BYTES)
        self.assertEqual(files[0][1], "application/pdf")

    def test_malha_files_empty_without_malhas_data(self):
        with self._patch_report() as render:
            self.assertEqual(self.rel._afr_malha_certificate_files(), [])
        render.assert_not_called()
