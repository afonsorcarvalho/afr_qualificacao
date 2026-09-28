"""P4 — montagem do PDF do Relatório Final (núcleo + anexos + build)."""
import base64
import io
import json
import time
from datetime import datetime
from unittest.mock import patch

from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.generic import NameObject
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from PIL import Image

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.afr_qualificacao.models import relatorio_pdf as rp
from odoo.addons.afr_qualificacao.models.relatorio_anexo_files import (
    PROBLEM_EMPTY,
    PROBLEM_NO_ACCESS,
)

from .common import AfrQualificacaoTestCommon
from .relatorio_fakes import (
    FakeCorpo,
    RelatorioFixtureMixin,
    encrypt_pdf,
    make_pdf,
    make_png,
    make_user,
    pdf_pages_text,
    squash,
)

HEADER = {
    "logo": None,
    "title": "ReQT-OS-T-1",
    "equipment": "Equipamento: Autoclave Teste  TAG: AC-01",
    "revision": "Rev.00",
    "date": "01/07/2026",
    "footer": "contato@empresa.test",
    "verify_url": False,
    "qr_page_index": None,
}


def squash_keep_space(text):
    """Como `squash`, mas preserva espaços (título de seção quebrado em
    glyphs separados pelo pdfminer perde os espaços internos; isto só
    normaliza os espaços em branco, não remove)."""
    return " ".join(text.split())


def _text_boxes(pdf_content):
    boxes = []
    for layout in extract_pages(io.BytesIO(pdf_content)):
        for el in layout:
            if isinstance(el, LTTextContainer):
                boxes.append((el.get_text().strip(), el.bbox))
    return boxes


def _inside_usable(bbox, tol=1.0):
    ux, uy, uw, uh = rp.USABLE
    x0, y0, x1, y1 = bbox
    return (x0 >= ux - tol and y0 >= uy - tol
            and x1 <= ux + uw + tol and y1 <= uy + uh + tol)


def _single_page_pdf(page):
    writer = PdfFileWriter()
    writer.addPage(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _first_page(data):
    return PdfFileReader(io.BytesIO(data)).getPage(0)


def _pdf_with_corrupt_middle_page():
    """PDF de 3 páginas; a do meio tem content stream corrompido (a 0 é boa,
    então open_pdf/file_problem aceitam o arquivo)."""
    reader = PdfFileReader(io.BytesIO(make_pdf([["BOA p1"], ["RUIM p2"], ["BOA p3"]])))
    writer = PdfFileWriter()
    for idx in range(reader.getNumPages()):
        page = reader.getPage(idx)
        if idx == 1:
            stream = page["/Contents"].getObject()
            stream._data = b"\x00lixo que nao e zlib"
            stream[NameObject("/Filter")] = NameObject("/FlateDecode")
        writer.addPage(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioPdfCore(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Pdf = self.env["afr.relatorio.pdf"]

    def test_find_markers_per_page_zero_based(self):
        pdf = make_pdf([
            ["capa", "@@RQ:bloco:7@@"],
            ["texto"],
            ["@@RQ:bloco:9@@", "@@RQ:anexo:dados@@", "ANEXO 1"],
        ])
        self.assertEqual(
            self.Pdf._find_markers(pdf),
            {"bloco:7": 0, "bloco:9": 2, "anexo:dados": 2},
        )

    def test_find_markers_first_occurrence_wins(self):
        pdf = make_pdf([["@@RQ:bloco:1@@"], ["@@RQ:bloco:1@@"]])
        self.assertEqual(self.Pdf._find_markers(pdf), {"bloco:1": 0})

    def test_fit_page_landscape_into_usable_area(self):
        src = _first_page(make_pdf([["PAISAGEM"]], size=(842, 595)))
        out = _single_page_pdf(rp.fit_page_to_usable(src))
        page = _first_page(out)
        self.assertAlmostEqual(float(page.mediaBox.getWidth()), rp.A4_W, places=1)
        self.assertAlmostEqual(float(page.mediaBox.getHeight()), rp.A4_H, places=1)
        boxes = _text_boxes(out)
        self.assertTrue(boxes)
        self.assertTrue(all(_inside_usable(b) for _t, b in boxes), boxes)

    def test_fit_page_rotated_90_is_upright_inside_usable_area(self):
        # Texto no alto-esquerda da página não girada; exibida girada 90°
        # horário, ele fica no lado DIREITO.
        src = _first_page(make_pdf([["GIRADO"]], rotate=90))
        out = _single_page_pdf(rp.fit_page_to_usable(src))
        self.assertFalse(int(_first_page(out).get("/Rotate", 0) or 0))
        boxes = _text_boxes(out)
        self.assertTrue(all(_inside_usable(b) for _t, b in boxes), boxes)
        self.assertGreater(boxes[0][1][0], rp.A4_W / 2)

    def test_fit_page_rotated_270_goes_to_the_left(self):
        src = _first_page(make_pdf([["GIRADO"]], rotate=270))
        out = _single_page_pdf(rp.fit_page_to_usable(src))
        boxes = _text_boxes(out)
        self.assertTrue(all(_inside_usable(b) for _t, b in boxes), boxes)
        self.assertLess(boxes[0][1][2], rp.A4_W / 2)

    def test_image_to_pdf_single_a4_page_with_caption(self):
        pdf = self.Pdf._image_to_pdf(make_png(1200, 400), "Foto da impressão do ciclo 1")
        reader = PdfFileReader(io.BytesIO(pdf))
        self.assertEqual(reader.getNumPages(), 1)
        self.assertAlmostEqual(float(reader.getPage(0).mediaBox.getWidth()), rp.A4_W, places=1)
        self.assertIn("Foto da impressão do ciclo 1", pdf_pages_text(pdf)[0])

    def test_image_to_pdf_accepts_rgba(self):
        buf = io.BytesIO()
        Image.new("RGBA", (300, 300), (0, 0, 255, 128)).save(buf, format="PNG")
        pdf = self.Pdf._image_to_pdf(buf.getvalue(), "rgba")
        self.assertEqual(PdfFileReader(io.BytesIO(pdf)).getNumPages(), 1)

    def test_stamp_page_x_de_y_and_header_on_every_page(self):
        out = self.Pdf._stamp(make_pdf([["um"], ["dois"], ["tres"]]), dict(HEADER), False)
        pages = pdf_pages_text(out)
        self.assertEqual(len(pages), 3)
        for number, text in enumerate(pages, start=1):
            self.assertIn("Página %d de 3" % number, text)
            self.assertIn("ReQT-OS-T-1", text)
            self.assertIn("TAG: AC-01", text)
            self.assertIn("Rev.00", text)
            self.assertIn("contato@empresa.test", text)

    def test_stamp_watermark_only_when_requested(self):
        body = make_pdf([["um"], ["dois"]])
        minuta = self.Pdf._stamp(body, dict(HEADER, date="MINUTA"), True)
        final = self.Pdf._stamp(body, dict(HEADER), False)
        self.assertEqual(squash("".join(pdf_pages_text(minuta))).count("MINUTA—SEMVALIDADE"), 2)
        self.assertNotIn("SEMVALIDADE", squash("".join(pdf_pages_text(final))))

    def test_stamp_qr_only_on_requested_page(self):
        url = "https://exemplo.test/qualificacao/relatorio/verify/" + "a" * 32
        out = self.Pdf._stamp(
            make_pdf([["um"], ["dois"]]),
            dict(HEADER, verify_url=url, qr_page_index=1), False,
        )
        reader = PdfFileReader(io.BytesIO(out))
        size_0 = len(reader.getPage(0).getContents().getData())
        size_1 = len(reader.getPage(1).getContents().getData())
        # QR = centenas de retângulos no content stream da página 2.
        self.assertGreater(size_1, size_0 + 3000)

    def test_stamp_cover_page_has_no_header_or_page_number(self):
        header = dict(HEADER, cover_page_index=0, company_name="Empresa Teste",
                      section_labels=["", "01 OBJETIVO", "ANEXO 1"])
        pages = pdf_pages_text(self.Pdf._stamp(
            make_pdf([["capa"], ["um"], ["dois"]]), header, False))
        self.assertNotIn("Página", pages[0])
        self.assertIn("Empresa Teste", pages[0])  # linha de propriedade
        self.assertIn("Página 2 de 3", pages[1])
        self.assertIn("01 OBJETIVO", squash_keep_space(pages[1]))
        self.assertIn("ANEXO 1", pages[2])

    def test_stamp_section_uses_final_index_with_offset(self):
        header = dict(HEADER, page_offset=2, page_total=4, cover_page_index=0,
                      section_labels=["", "", "02 SEÇÃO B", "03 SEÇÃO C"])
        pages = pdf_pages_text(self.Pdf._stamp(make_pdf([["x"], ["y"]]), header, False))
        self.assertIn("SEÇÃO B", pages[0])
        self.assertIn("SEÇÃO C", pages[1])
        self.assertIn("Página 3 de 4", pages[0])

    def test_stamp_truncates_long_section_label(self):
        label = "01 " + "TÍTULO MUITO LONGO " * 8
        header = dict(HEADER, section_labels=[label])
        text = pdf_pages_text(self.Pdf._stamp(make_pdf([["x"]]), header, False))[0]
        self.assertNotIn(label.strip(), text)
        self.assertIn("…", text)

    def test_stamp_property_line_stops_before_qr(self):
        # Nome de empresa real longo + QR na página de assinaturas: a linha de
        # propriedade (y 10 mm) é cortada antes do QR (x ≥ direita − 16 mm).
        url = "https://exemplo.test/qualificacao/relatorio/verify/" + "a" * 32
        header = dict(HEADER, verify_url=url, qr_page_index=0,
                      company_name="LABQUALI QUALIFICAÇÕES, CALIBRAÇÕES E ENSAIOS TÉRMICOS DO BRASIL LTDA",
                      footer="atendimento.qualificacao.termica@labquali.com.br")
        out = self.Pdf._stamp(make_pdf([["x"]]), header, False)
        lines = []
        for layout in extract_pages(io.BytesIO(out)):
            for el in layout:
                if isinstance(el, LTTextContainer):
                    lines.extend(line for line in el if "Documento emitido" in line.get_text())
        self.assertEqual(len(lines), 1, lines)
        qr_left = rp.A4_W - rp.STAMP_SIDE - rp.QR_SIZE
        self.assertLess(lines[0].bbox[2], qr_left)
        self.assertIn("…", lines[0].get_text())
        # A frase legal nunca pode ser cortada — só o "quem" (empresa/e-mail).
        self.assertTrue(lines[0].get_text().strip().endswith("sem alterações."),
                        lines[0].get_text())

    def test_stamp_property_line_keeps_clause_intact_with_very_long_company_name(self):
        # Nome de empresa absurdo (120 chars): em qualquer página — capa,
        # interna sem QR e página com QR — a frase legal sai inteira; só o
        # "quem" é cortado, e nada invade a área do QR quando `with_qr`.
        url = "https://exemplo.test/qualificacao/relatorio/verify/" + "a" * 32
        long_name = "EMPRESA " + "X" * 112
        self.assertEqual(len(long_name), 120)
        header = dict(HEADER, verify_url=url, qr_page_index=2, cover_page_index=0,
                      company_name=long_name,
                      footer="atendimento.qualificacao.termica@labquali.com.br")
        out = self.Pdf._stamp(
            make_pdf([["capa"], ["interna"], ["assinaturas"]]), header, False)
        qr_left = rp.A4_W - rp.STAMP_SIDE - rp.QR_SIZE
        right_edge = rp.A4_W - rp.STAMP_SIDE
        for page_no, layout in enumerate(extract_pages(io.BytesIO(out))):
            lines = [line for el in layout if isinstance(el, LTTextContainer)
                     for line in el if "Documento emitido" in line.get_text()]
            self.assertEqual(len(lines), 1, (page_no, lines))
            text = lines[0].get_text().strip()
            self.assertTrue(text.endswith("sem alterações."), (page_no, text))
            self.assertIn("…", text)
            limit = qr_left if page_no == 2 else right_edge
            self.assertLessEqual(lines[0].bbox[2], limit + 1.0, (page_no, lines[0].bbox))

    def test_stamp_property_line_shrinks_before_cutting_on_qr_page(self):
        # Linha real (~149 mm a 6 pt) não cabe ao lado do QR (144 mm): o corpo
        # cai para 5,5 pt e a frase legal fica inteira, sem "…".
        header = dict(HEADER, company_name="LABQUALI QUALIFICACOES LTDA",
                      footer="labquali@labquali.com.br")
        c = rp.canvas.Canvas(io.BytesIO())
        text, size = rp.property_line_fit(c, header, 6, True)
        self.assertEqual(size, 5.5)
        self.assertTrue(text.endswith("sem alterações."), text)
        self.assertEqual(rp.property_line_fit(c, header, 6, False)[1], 6)

    def test_stamp_subtitle_identical_across_sections(self):
        header = dict(HEADER, subtitle_prefix="ReQT-OS-T-1 · TAG: AC-01",
                      equipment_name="Autoclave a Gás (ETO) ETO-40 ETO-2023-002 Sercon " * 2,
                      section_labels=["04 PROCEDIMENTO DE QUALIFICAÇÃO", "ANEXO 1"])
        pages = pdf_pages_text(self.Pdf._stamp(make_pdf([["x"], ["y"]]), header, False))
        subs = [next(l for l in p.splitlines() if "TAG: AC-01" in l) for p in pages]
        self.assertEqual(subs[0], subs[1])

    def test_open_pdf_accepts_owner_only_encryption(self):
        reader = rp.open_pdf(encrypt_pdf(make_pdf([["cert"]]), user_pw=""))
        self.assertEqual(reader.getNumPages(), 1)

    def test_open_pdf_rejects_user_password(self):
        with self.assertRaisesRegex(ValueError, "senha"):
            rp.open_pdf(encrypt_pdf(make_pdf([["x"]]), user_pw="segredo"))

    def test_open_pdf_rejects_garbage(self):
        with self.assertRaisesRegex(ValueError, "ilegível"):
            rp.open_pdf(b"nao e pdf")

    def test_section_labels_pure(self):
        page_map = {"bloco:1": 1, "bloco:2": 2, "anexo:a": 4, "bloco:3": 6, "anexo:c": 8}
        sections = [("bloco:2", "SUMÁRIO"), ("anexo:a", "ANEXO 1"),
                    ("bloco:3", "02 CONCLUSÃO"), ("anexo:c", "ANEXO 2"),
                    ("bloco:9", "99 SEM PÁGINA")]
        self.assertEqual(rp.section_labels(page_map, sections, 9), [
            "", "SUMÁRIO", "SUMÁRIO", "ANEXO 1", "ANEXO 1",
            "02 CONCLUSÃO", "02 CONCLUSÃO", "ANEXO 2", "ANEXO 2",
        ])

    def test_section_labels_first_section_starting_on_page_wins(self):
        # Várias seções começam na mesma página: o cabeçalho mostra a 1ª que
        # abre a página; páginas seguintes sem início herdam a última iniciada.
        page_map = {"bloco:1": 2, "bloco:2": 2, "bloco:3": 2, "bloco:4": 4}
        sections = [("bloco:1", "01 A"), ("bloco:2", "02 B"),
                    ("bloco:3", "03 C"), ("bloco:4", "04 D")]
        self.assertEqual(rp.section_labels(page_map, sections, 5),
                         ["", "01 A", "03 C", "04 D", "04 D"])

    def test_section_labels_empty(self):
        self.assertEqual(rp.section_labels({}, [], 3), ["", "", ""])

    def test_cover_page_index(self):
        self.assertEqual(rp.cover_page_index({"bloco:10": 1}, "bloco:10"), 0)
        self.assertIsNone(rp.cover_page_index({"bloco:10": 1}, None))
        self.assertIsNone(rp.cover_page_index({}, "bloco:10"))


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioAnexoFiles(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    def setUp(self):
        super().setUp()
        self.rel, self.qualif = self._make_relatorio()

    def _item(self, name, section, content, sequence=10, cycle=None, qualif=None,
              mimetype="application/pdf"):
        item = self.env["afr.qualificacao.collect.item"].create({
            "name": name,
            "qualif_id": (qualif or self.qualif).id,
            "kind": "foto",
            "required": True,
            "sequence": sequence,
            "cycle_id": cycle.id if cycle else False,
            "file": base64.b64encode(content),
            "filename": name,
            "mimetype": mimetype,
        })
        item.docx_section = section
        return item

    def test_upload_pdf_and_image_resolved_in_attachment_order(self):
        pdf = self._attachment(make_pdf([["p"]]), "grafico.pdf", "application/pdf")
        png = self._attachment(make_png(), "foto.png", "image/png")
        anexo = self._anexo(self.rel, "dados", "Dados", 10, attachments=pdf | png)
        files = anexo._resolve_files()
        self.assertEqual([f[1] for f in files], ["application/pdf", "image/png"])
        self.assertEqual([f[2] for f in files], ["grafico.pdf", "foto.png"])
        self.assertEqual(anexo._check_files(), [])

    def test_upload_without_files_reports_empty(self):
        anexo = self._anexo(self.rel, "dados", "Dados", 10)
        self.assertEqual(anexo._resolve_files(), [])
        self.assertEqual(anexo._check_files(), [PROBLEM_EMPTY])

    def test_unsaved_upload_attachment_readable_via_sudo(self):
        # Fix round 1, finding 2(a): res_id=0 (upload ainda não vinculado,
        # como o widget many2many_binary grava) de OUTRO usuário — o
        # próprio anexo (mesmo res_model/res_id em (0, anexo.id)) precisa
        # continuar legível via sudo, mesmo pra quem não é o autor do
        # upload.
        uploader = make_user(
            self.env, "outro_tecnico_upload",
            "afr_qualificacao.group_afr_qualificacao_technician")
        att = self.env["ir.attachment"].with_user(uploader).create({
            "name": "grafico.pdf",
            "raw": make_pdf([["p"]]),
            "mimetype": "application/pdf",
            "res_model": "afr.relatorio.anexo",
            "res_id": 0,
        })
        anexo = self._anexo(self.rel, "dados", "Dados", 10, attachments=att)
        viewer = make_user(
            self.env, "tecnico_view_a",
            "afr_qualificacao.group_afr_qualificacao_technician")
        files = anexo.with_user(viewer)._resolve_files()
        self.assertEqual([f[2] for f in files], ["grafico.pdf"])
        self.assertEqual(anexo.with_user(viewer)._check_files(), [])

    def test_foreign_attachment_user_cannot_read_is_not_embedded(self):
        # Fix round 1, finding 2(b) (segurança): um ir.attachment de
        # terceiro que o usuário atual não tem direito de ler (criado por
        # outro usuário, sem vínculo com este anexo) NUNCA pode entrar no
        # PDF só porque seu id foi colado em attachment_ids — vira
        # problema listado, não bytes embutidos.
        other_user = make_user(
            self.env, "dono_privado",
            "afr_qualificacao.group_afr_qualificacao_technician")
        foreign_att = self.env["ir.attachment"].with_user(other_user).create({
            "name": "sigiloso.pdf",
            "raw": make_pdf([["segredo"]]),
            "mimetype": "application/pdf",
        })
        anexo = self._anexo(self.rel, "dados", "Dados", 10, attachments=foreign_att)
        viewer = make_user(
            self.env, "tecnico_view_b",
            "afr_qualificacao.group_afr_qualificacao_technician")
        self.assertEqual(anexo.with_user(viewer)._resolve_files(), [])
        problems = anexo.with_user(viewer)._check_files()
        self.assertEqual(len(problems), 1)
        self.assertIn("sigiloso.pdf", problems[0])
        self.assertIn(PROBLEM_NO_ACCESS, problems[0])

    def test_user_password_pdf_is_reported_and_skipped(self):
        ok = self._attachment(make_pdf([["ok"]]), "ok.pdf", "application/pdf")
        enc = self._attachment(
            encrypt_pdf(make_pdf([["x"]]), user_pw="segredo"), "cert.pdf",
            "application/pdf",
        )
        anexo = self._anexo(self.rel, "padroes", "Padrões", 10, attachments=ok | enc)
        self.assertEqual([f[2] for f in anexo._resolve_files()], ["ok.pdf"])
        problems = anexo._check_files()
        self.assertEqual(len(problems), 1)
        self.assertIn("cert.pdf", problems[0])
        self.assertIn("senha", problems[0])

    def test_owner_only_encrypted_pdf_is_usable(self):
        enc = self._attachment(
            encrypt_pdf(make_pdf([["x"]]), user_pw=""), "rbc.pdf", "application/pdf"
        )
        anexo = self._anexo(self.rel, "padroes", "Padrões", 10, attachments=enc)
        self.assertEqual(len(anexo._resolve_files()), 1)
        self.assertEqual(anexo._check_files(), [])

    def test_garbage_pdf_and_unsupported_type_are_reported(self):
        broken = self._attachment(b"%PDF-1.4 lixo", "quebrado.pdf", "application/pdf")
        txt = self._attachment(b"apenas texto", "nota.txt", "text/plain")
        anexo = self._anexo(self.rel, "dados", "Dados", 10, attachments=broken | txt)
        self.assertEqual(anexo._resolve_files(), [])
        problems = anexo._check_files()
        self.assertEqual(len(problems), 2)
        self.assertIn("ilegível", problems[0])
        self.assertIn("não suportado", problems[1])

    def test_collect_section_filters_and_orders_by_cycle_then_sequence(self):
        Cycle = self.env["afr.qualificacao.cycle"]
        c1 = Cycle.create({"qualificacao_id": self.qualif.id,
                           "cycle_type_id": self.cycle_cmax.id, "sequence": 1})
        c2 = Cycle.create({"qualificacao_id": self.qualif.id,
                           "cycle_type_id": self.cycle_cmax.id, "sequence": 2})
        pdf = make_pdf([["p"]])
        self._item("c2 item", "anexos", pdf, sequence=1, cycle=c2)
        self._item("c1 seq20", "anexos", pdf, sequence=20, cycle=c1)
        self._item("sem ciclo", "anexos", pdf, sequence=5)
        self._item("c1 seq10", "qd_carga", pdf, sequence=10, cycle=c1)
        self._item("outra secao", "qi_documentos", pdf)
        pending = self.env["afr.qualificacao.collect.item"].create({
            "name": "pendente", "qualif_id": self.qualif.id, "kind": "foto",
        })
        pending.docx_section = "anexos"
        qualif2 = self.env["afr.qualificacao"].create({
            "name": "Qualif outro equipamento", "equipment_id": self.equip2.id,
            "qualification_type": "installation", "company_id": self.company.id,
            "os_id": self.rel.os_id.id,
        })
        self._item("outro equipamento", "anexos", pdf, qualif=qualif2)
        anexo = self._anexo(self.rel, "dados", "Dados", 10,
                            slot_kind="collect_section",
                            collect_sections="anexos, qd_carga")
        names = [f[2].split(" — ")[-1] for f in anexo._resolve_files()]
        self.assertEqual(names, ["sem ciclo", "c1 seq10", "c1 seq20", "c2 item"])

    def test_cancelled_qualification_of_same_equipment_is_excluded(self):
        # Fix round 1, finding 4 (ruling 1.6): item de coleta de uma
        # qualificação CANCELADA do MESMO equipamento não pode entrar —
        # `rel.qualificacao_ids` já filtra `state != 'cancelled'` (P1); o
        # domínio de `_collect_items` não pode reabrir isso por
        # os_id/equipment_id.
        pdf = make_pdf([["p"]])
        self._item("ativo", "anexos", pdf, sequence=10)
        qualif_cancelada = self.env["afr.qualificacao"].create({
            "name": "Qualif cancelada mesmo equipamento",
            "equipment_id": self.equip1.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": self.rel.os_id.id,
        })
        self._item("cancelada", "anexos", pdf, qualif=qualif_cancelada)
        qualif_cancelada.write({"state": "cancelled"})
        anexo = self._anexo(self.rel, "dados", "Dados", 10,
                            slot_kind="collect_section", collect_sections="anexos")
        names = [f[2] for f in anexo._resolve_files()]
        self.assertEqual(names, ["ativo"])

    def test_attachment_override_replaces_collect_items(self):
        self._item("coleta", "anexos", make_pdf([["p"]]))
        manual = self._attachment(make_pdf([["m"]]), "manual.pdf", "application/pdf")
        anexo = self._anexo(self.rel, "dados", "Dados", 10,
                            slot_kind="collect_section", collect_sections="anexos",
                            attachments=manual)
        self.assertEqual([f[2] for f in anexo._resolve_files()], ["manual.pdf"])

    def test_instrument_certs_passes_roles_from_cert_roles(self):
        seen = []

        def fake(rel_self, roles):
            seen.append(list(roles))
            return [(make_pdf([["cert"]]), "application/pdf", "Certificado do validador")]

        with patch.object(type(self.rel), "_afr_certificate_files", fake):
            a1 = self._anexo(self.rel, "validador", "Validador", 10,
                             slot_kind="instrument_certs", cert_roles="depois, antes")
            a2 = self._anexo(self.rel, "padroes", "Padrões", 20,
                             slot_kind="instrument_certs", cert_roles=False)
            self.assertEqual(len(a1._resolve_files()), 1)
            a2._resolve_files()
        self.assertEqual(seen, [["depois", "antes"], ["antes", "depois", "externo"]])

    def test_malha_certs_uses_p2_helper(self):
        def fake(rel_self):
            return [(make_pdf([["malha"]]), "application/pdf", "Malha temperatura")]

        with patch.object(type(self.rel), "_afr_malha_certificate_files", fake):
            anexo = self._anexo(self.rel, "malhas", "Malhas", 10, slot_kind="malha_certs")
            self.assertEqual([f[2] for f in anexo._resolve_files()], ["Malha temperatura"])

    def test_bloco_slot_has_no_files_its_content_is_in_the_body(self):
        block = self._block(self.rel, "protocolo", "Protocolo PrQT", 90,
                            anexo_code="protocolo")
        anexo = self._anexo(self.rel, "protocolo", "Protocolo", 10,
                            slot_kind="bloco", block_id=block.id)
        fake = FakeCorpo()
        with fake.patch(self.env):
            self.assertEqual(anexo._resolve_files(), [])
            self.assertEqual(anexo._check_files(), [])
        self.assertEqual(fake.calls, [])  # nada é renderizado para o anexo

    def test_bloco_slot_without_included_block_is_empty(self):
        anexo = self._anexo(self.rel, "protocolo", "Protocolo", 10, slot_kind="bloco")
        self.assertEqual(anexo._check_files(), [PROBLEM_EMPTY])
        block = self._block(self.rel, "laudo_micro", "Laudo", 91,
                            anexo_code="micro", included=False)
        anexo2 = self._anexo(self.rel, "micro", "Laudo", 20, slot_kind="bloco",
                             block_id=block.id)
        self.assertEqual(anexo2._check_files(), [PROBLEM_EMPTY])


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioBuild(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    def setUp(self):
        super().setUp()
        self.rel, _q = self._make_relatorio()
        self.blocks, self.anexos = self._standard_layout(self.rel)
        self.Pdf = self.env["afr.relatorio.pdf"]

    def _build(self, rel=None, watermark=False, fake=None):
        fake = fake or FakeCorpo()
        with fake.patch(self.env):
            pdf, warnings = self.Pdf._build(rel or self.rel, watermark=watermark)
        return pdf, warnings, fake

    def test_compute_layout_pure(self):
        layout = rp.compute_layout(
            {"bloco:1": 0, "anexo:a": 1, "bloco:2": 2, "anexo:b": 2},
            3, {"a": 2, "b": 0, "c": 3}, ["a", "b", "c"],
        )
        self.assertEqual(layout["insert_after"], {1: ["a"], 2: ["b"]})
        self.assertEqual(layout["trailing"], ["c"])
        self.assertEqual(layout["body_final"], [1, 2, 5])
        self.assertEqual(layout["page_map"], {
            "bloco:1": 1, "anexo:a": 2, "bloco:2": 5, "anexo:b": 5, "anexo:c": 6,
        })
        self.assertEqual(layout["total"], 8)

    def test_build_places_annex_pages_after_their_separator(self):
        pdf, warnings, _fake = self._build()
        pages = pdf_pages_text(pdf)
        self.assertEqual(len(pages), 9)
        self.assertIn("BLOCO Conclusao", pages[3])
        self.assertIn("BLOCO Assinaturas", pages[3])
        self.assertIn("ANEXO 1: Resultados", pages[4])
        self.assertIn("ANEXO-DADOS p1", pages[5])
        self.assertIn("ANEXO-DADOS p2", pages[6])
        self.assertIn("ANEXO 2: Impressões", pages[7])
        self.assertIn("impressao.png", pages[8])
        self.assertEqual(warnings, [])

    def test_build_stamps_pagina_x_de_y_on_every_page(self):
        pdf, _w, _f = self._build()
        pages = pdf_pages_text(pdf)
        # Página 1 é a capa (1º bloco do fixture): sem "Página"/carimbo de
        # cabeçalho, só a linha de propriedade com o nome da empresa.
        self.assertNotIn("Página", pages[0])
        self.assertIn(self.rel.company_id.name, pages[0])
        for number, text in enumerate(pages[1:], start=2):
            self.assertIn("Página %d de 9" % number, text)
            self.assertIn(self.rel.name, text)

    def test_body_render_data_goes_in_report_data(self):
        # Fato fixado P3 #1: page_map/with_markers/cover_date no `data`, nunca
        # no contexto. Sem emissão vigente nem `rq_emission_date`: cover_date
        # em branco (não é minuta).
        self.assertEqual(
            self.Pdf._body_render_data(self.rel, {"anexo:dados": 5}),
            {"with_markers": True, "page_map": {"anexo:dados": 5}, "cover_date": ""},
        )

    def test_body_render_data_cover_date_is_minuta_when_watermarked(self):
        # Regressão-alvo: uma minuta Rev.01 gerada DEPOIS de uma emissão
        # vigente (Rev.00) tem de mostrar "MINUTA", nunca a data da emissão
        # anterior — por isso a emissão vigente é criada de propósito antes
        # de checar watermark=True.
        att = self._attachment(b"%PDF-1.4 teste", "r.pdf", "application/pdf")
        emissao = self.env["afr.relatorio.emissao"].sudo().with_context(
            rq_emissao_internal=True
        ).create({
            "relatorio_id": self.rel.id, "revision": 0,
            "pdf_attachment_id": att.id, "sha256": "0" * 64, "token": "a" * 32,
            "issued_at": "2026-01-02 12:00:00",
        })
        self.rel.write({"current_emissao_id": emissao.id})
        rel_ctx = self.rel.with_context(tz="UTC")
        # Prova que o fixture está "vivo": sem watermark, a data vem da
        # emissão vigente.
        self.assertEqual(self.Pdf._date_label(rel_ctx, False), "02/01/2026")
        self.assertEqual(
            self.Pdf._body_render_data(rel_ctx, {}, watermark=True)["cover_date"],
            "MINUTA",
        )

    def test_body_render_data_cover_date_follows_emission_context(self):
        rel_ctx = self.rel.with_context(
            tz="UTC", rq_emission_date=datetime(2026, 7, 15, 12, 0, 0))
        self.assertEqual(
            self.Pdf._body_render_data(rel_ctx, {}, watermark=False)["cover_date"],
            "15/07/2026",
        )

    def test_build_second_pass_feeds_index_with_final_numbers(self):
        # Vale para os dois caminhos (marcadores e fallback do Task 6):
        # 1ª chamada com page_map vazio, última com o mapa final.
        pdf, _w, fake = self._build()
        for call in fake.calls:
            self.assertEqual(call["report_ref"], "afr_qualificacao.action_report_relatorio_corpo")
            self.assertEqual(call["res_ids"], self.rel.ids)
            self.assertIn("page_map", call["data"])
            self.assertNotIn("page_map", call["context"])
        self.assertEqual(fake.calls[0]["data"]["page_map"], {})
        page_map = fake.calls[-1]["data"]["page_map"]
        self.assertEqual(page_map["anexo:dados"], 5)
        self.assertEqual(page_map["anexo:fotos"], 8)
        self.assertEqual(page_map["bloco:%d" % self.blocks["conclusao"].id], 4)
        self.assertIn("IDX anexo:fotos=8", pdf_pages_text(pdf)[1])

    def test_build_bloco_annex_comes_from_the_body_once(self):
        proto = self._block(self.rel, "protocolo", "Protocolo PrQT", 90,
                            anexo_code="protocolo")
        self._anexo(self.rel, "protocolo", "Protocolo", 30, slot_kind="bloco",
                    block_id=proto.id)
        pdf, warnings, _fake = self._build()
        pages = pdf_pages_text(pdf)
        # 9 + separador "ANEXO 3: Protocolo" + página do bloco protocolo
        self.assertEqual(len(pages), 11)
        self.assertIn("ANEXO 3: Protocolo", pages[9])
        self.assertIn("BLOCO Protocolo PrQT", pages[10])
        self.assertEqual(sum("BLOCO Protocolo PrQT" in p for p in pages), 1)
        self.assertEqual(warnings, [])

    def test_build_annex_whose_marker_is_missing_goes_to_end_with_warning(self):
        pdf, warnings, _f = self._build(fake=FakeCorpo(skip_markers={"anexo:dados"}))
        pages = pdf_pages_text(pdf)
        self.assertEqual(len(pages), 9)
        self.assertIn("ANEXO-DADOS p1", pages[7])
        self.assertIn("ANEXO-DADOS p2", pages[8])
        self.assertTrue(any("dados" in w and "fim do documento" in w for w in warnings),
                        warnings)

    def test_build_warns_when_index_does_not_converge(self):
        _pdf, warnings, fake = self._build(fake=FakeCorpo(grow_each_call=True))
        self.assertEqual(len(fake.calls), rp.MAX_PASSES)
        self.assertTrue(any("não estabilizou" in w for w in warnings), warnings)

    def test_build_landscape_and_rotated_annex_pages_become_a4_portrait(self):
        landscape = self._attachment(make_pdf([["PAISAGEM"]], size=(842, 595)),
                                     "grafico.pdf", "application/pdf")
        rotated = self._attachment(make_pdf([["GIRADO"]], rotate=90), "curva.pdf",
                                   "application/pdf")
        self.anexos["dados"].attachment_ids = [(6, 0, (landscape | rotated).ids)]
        pdf, _w, _f = self._build()
        reader = PdfFileReader(io.BytesIO(pdf))
        for idx in (5, 6):
            page = reader.getPage(idx)
            self.assertAlmostEqual(float(page.mediaBox.getWidth()), rp.A4_W, places=1)
            self.assertAlmostEqual(float(page.mediaBox.getHeight()), rp.A4_H, places=1)
            self.assertFalse(int(page.get("/Rotate", 0) or 0))

    def test_build_skips_unreadable_file_with_warning(self):
        locked = self._attachment(encrypt_pdf(make_pdf([["x"]]), user_pw="segredo"),
                                  "travado.pdf", "application/pdf")
        self.anexos["fotos"].attachment_ids = [(4, locked.id)]
        pdf, warnings, _f = self._build()
        self.assertEqual(len(pdf_pages_text(pdf)), 9)
        self.assertTrue(any("travado.pdf" in w and "senha" in w for w in warnings), warnings)

    def test_build_skips_corrupt_page_beyond_first_with_warning(self):
        # open_pdf/_check_files só validam a página 0: uma página ≥ 1 com
        # content stream corrompido não pode derrubar o _build() inteiro.
        corrupt = _pdf_with_corrupt_middle_page()
        bad = self._attachment(corrupt, "meio_corrompido.pdf", "application/pdf")
        self.assertIsNone(rp.file_problem(corrupt, "application/pdf"))
        self.anexos["dados"].attachment_ids = [(6, 0, bad.ids)]
        pdf, warnings, _f = self._build()
        pages = pdf_pages_text(pdf)
        # corpo 6 + dados (2 páginas boas; a corrompida sai) + foto = 9
        self.assertEqual(len(pages), 9)
        self.assertIn("BOA p1", pages[5])
        self.assertIn("BOA p3", pages[6])
        self.assertNotIn("RUIM", "".join(pages))
        self.assertTrue(any("meio_corrompido.pdf" in w and "ignorad" in w for w in warnings),
                        warnings)

    def test_build_watermark_only_on_minuta(self):
        minuta, _w, _f = self._build(watermark=True)
        final, _w2, _f2 = self._build(watermark=False)
        self.assertEqual(squash("".join(pdf_pages_text(minuta))).count("MINUTA—SEMVALIDADE"), 9)
        self.assertNotIn("SEMVALIDADE", squash("".join(pdf_pages_text(final))))

    def test_build_qr_goes_on_signature_page_only_when_not_minuta(self):
        seen = []
        original = type(self.Pdf)._stamp

        def spy(pdf_self, content, header, watermark):
            seen.append(dict(header))
            return original(pdf_self, content, header, watermark)

        rel_ctx = self.rel.with_context(rq_emission_token="b" * 32)
        with patch.object(type(self.Pdf), "_stamp", spy):
            self._build(rel=rel_ctx, watermark=False)
            self._build(rel=rel_ctx, watermark=True)
        final_header, minuta_header = seen
        self.assertEqual(final_header["qr_page_index"], 3)  # conclusão+assinaturas
        self.assertIn("/qualificacao/relatorio/verify/" + "b" * 32, final_header["verify_url"])
        self.assertFalse(minuta_header["verify_url"])
        self.assertEqual(minuta_header["date"], "MINUTA")

    def test_header_date_comes_from_relatorio_context(self):
        # Ruling 1.9: a data da emissão em curso vem do contexto do
        # RELATÓRIO (quem chama é action_emitir, com o rel no contexto), não
        # do env do afr.relatorio.pdf — o do Pdf é ignorado.
        rel_ctx = self.rel.with_context(
            tz="UTC", rq_emission_date=datetime(2026, 7, 15, 12, 0, 0))
        self.Pdf = self.Pdf.with_context(rq_emission_date=datetime(2026, 1, 2, 12, 0, 0))
        pdf, _w, _f = self._build(rel=rel_ctx, watermark=False)
        pages = pdf_pages_text(pdf)
        # pages[0] é a capa: sem rodapé/data do carimbo.
        self.assertTrue(all("15/07/2026" in text for text in pages[1:]), pages[1])
        self.assertNotIn("02/01/2026", "".join(pages))
        minuta, _w2, _f2 = self._build(rel=rel_ctx, watermark=True)
        self.assertNotIn("15/07/2026", "".join(pdf_pages_text(minuta)))

    def test_header_truncates_long_equipment_name_but_keeps_tag(self):
        # Nota de resolução: o subtítulo trunca só o nome do equipamento —
        # "TAG: <tag>" nunca pode sumir por causa de um nome de 150 chars.
        self.rel.equipment_id.name = "EQUIPAMENTO " + "X" * 150
        header = self.Pdf._header(self.rel, True)
        pdf = self.Pdf._stamp(make_pdf([["x"]]), header, True)
        text = pdf_pages_text(pdf)[0]
        self.assertIn("TAG: " + (self.rel.equipment_id.tag or "—"), text)
        self.assertIn("…", text)

    def test_public_build_returns_bytes(self):
        fake = FakeCorpo()
        with fake.patch(self.env):
            pdf = self.Pdf.build(self.rel)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_rq_fmt_number(self):
        rel = self.rel
        self.assertEqual(rel._rq_fmt_number("4"), "04")
        self.assertEqual(rel._rq_fmt_number("12"), "12")
        self.assertEqual(rel._rq_fmt_number("4.1"), "4.1")
        self.assertEqual(rel._rq_fmt_number(""), "")

    def test_staged_body_sets_section_labels_and_cover(self):
        with FakeCorpo().patch(self.env):
            st, store = self.Pdf._stage_init(True), rp.MemoryStore()
            while st["phase"] not in ("stamp", "done"):
                self.Pdf._stage_run(self.rel, st, store, rp.UNLIMITED)
        self.assertEqual(len(st["section_labels"]), st["total"])
        self.assertEqual(st["cover_page_index"], 0)
        self.assertEqual(st["section_labels"][0], "")
        self.assertTrue(st["section_labels"][4].startswith("ANEXO 1"), st["section_labels"])
        self.assertTrue(st["section_labels"][-1].startswith("ANEXO 2"), st["section_labels"])
        json.dumps(st)  # continua serializável (stage_json)

    def test_staged_body_without_leading_cover_has_no_cover_page(self):
        # Capa fora da 1ª posição (ou excluída): nenhuma página é "capa".
        self.rel.block_ids.filtered(lambda b: b.block_kind == "capa").included = False
        with FakeCorpo().patch(self.env):
            st, store = self.Pdf._stage_init(True), rp.MemoryStore()
            while st["phase"] not in ("stamp", "done"):
                self.Pdf._stage_run(self.rel, st, store, rp.UNLIMITED)
        self.assertIsNone(st["cover_page_index"])

    def test_stage_stamp_tolerates_legacy_state_without_sections(self):
        # Job enfileirado antes do deploy: `st` sem as chaves novas.
        with FakeCorpo().patch(self.env):
            st, store = self.Pdf._stage_init(True), rp.MemoryStore()
            while st["phase"] not in ("stamp", "done"):
                self.Pdf._stage_run(self.rel, st, store, rp.UNLIMITED)
            st.pop("section_labels"), st.pop("cover_page_index")
            while st["phase"] != "done":
                self.Pdf._stage_run(self.rel, st, store, rp.UNLIMITED)
        self.assertEqual(st["phase"], "done")


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioStagedBuild(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    def setUp(self):
        super().setUp()
        self.rel, _q = self._make_relatorio()
        self.blocks, self.anexos = self._standard_layout(self.rel)
        self.Pdf = self.env["afr.relatorio.pdf"]
        # anexo extra: 4 páginas (paisagem, /Rotate 90, retrato, retrato)
        extra = self._attachment(make_pdf([["X p1"], ["X p2"]], size=(842, 595)),
                                 "paisagem.pdf", "application/pdf")
        rot = self._attachment(make_pdf([["R p1"], ["R p2"]], rotate=90), "rot.pdf",
                               "application/pdf")
        self.anexos["dados"].attachment_ids = [(4, extra.id), (4, rot.id)]

    def _staged(self, rel, watermark, budget_factory):
        """Roda as fases como o job: uma unidade por vez, estado via JSON."""
        st, store, units = self.Pdf._stage_init(watermark), rp.MemoryStore(), 0
        while st["phase"] != "done":
            self.Pdf._stage_run(rel, st, store, budget_factory())
            st = json.loads(json.dumps(st))  # o job persiste o estado assim
            units += 1
        return store.get(st["final_blob"]), st["warnings"], units

    def _same_pdf(self, got, expected):
        self.assertEqual(pdf_pages_text(got), pdf_pages_text(expected))
        a = PdfFileReader(io.BytesIO(got)); b = PdfFileReader(io.BytesIO(expected))
        self.assertEqual(
            [tuple(map(float, a.getPage(i).mediaBox)) for i in range(a.getNumPages())],
            [tuple(map(float, b.getPage(i).mediaBox)) for i in range(b.getNumPages())])

    def test_one_page_units_equal_sync_build_minuta_and_final(self):
        for watermark in (True, False):
            rel = self.rel.with_context(tz="UTC", rq_emission_token="c" * 32,
                                        rq_emission_date=datetime(2026, 7, 15, 12, 0))
            with self.subTest(watermark=watermark), FakeCorpo().patch(self.env):
                expected, exp_w = self.Pdf._build(rel, watermark=watermark)
                got, got_w, units = self._staged(rel, watermark, lambda: rp.Budget(max_pages=1))
            self._same_pdf(got, expected)
            self.assertEqual(got_w, exp_w)
            self.assertGreater(units, 10)  # fatias de 1 página de verdade

    def test_budget_always_progresses_one_page(self):
        past = lambda: rp.Budget(max_pages=50, cpu_deadline=time.process_time() - 1)
        with FakeCorpo().patch(self.env):
            expected, _w = self.Pdf._build(self.rel, watermark=True)
            got, _w2, units = self._staged(self.rel, True, past)
        self._same_pdf(got, expected)
        self.assertGreater(units, 10)

    def test_corrupt_page_skipped_across_chunks(self):
        # mesma construção do test_build_skips_corrupt_page_beyond_first_with_warning
        bad = self._attachment(_pdf_with_corrupt_middle_page(), "meio_corrompido.pdf",
                               "application/pdf")
        self.anexos["dados"].attachment_ids = [(6, 0, bad.ids)]
        with FakeCorpo().patch(self.env):
            expected, exp_w = self.Pdf._build(self.rel, watermark=True)
            got, got_w, _u = self._staged(self.rel, True, lambda: rp.Budget(max_pages=1))
        self._same_pdf(got, expected)
        self.assertEqual(got_w, exp_w)
        self.assertTrue(any("página 2 ignorada" in w for w in got_w), got_w)

    def test_stamp_pdf_honours_offset_and_total(self):
        two = make_pdf([["a"], ["b"]])
        header = {"title": "T", "page_offset": 5, "page_total": 9,
                  "qr_page_index": 6, "verify_url": "https://x/verify/abc"}
        pages = pdf_pages_text(rp.stamp_pdf(two, header, False))
        self.assertIn("Página 6 de 9", pages[0])
        self.assertIn("Página 7 de 9", pages[1])

    def test_budget_retry_halves_page_cap(self):
        self.assertEqual(rp.Budget(max_pages=8, retry=1).max_pages, 8)
        self.assertEqual(rp.Budget(max_pages=8, retry=3).max_pages, 2)
        self.assertEqual(rp.Budget(max_pages=1, retry=5).max_pages, 1)
        self.assertTrue(rp.UNLIMITED.unlimited)

    def test_progress_is_monotonic(self):
        seen = []
        with FakeCorpo().patch(self.env):
            st, store = self.Pdf._stage_init(True), rp.MemoryStore()
            while st["phase"] != "done":
                self.Pdf._stage_run(self.rel, st, store, rp.Budget(max_pages=1))
                seen.append(rp.stage_progress(st))
        self.assertEqual(seen, sorted(seen))
        self.assertLess(seen[-1], 100)  # 100 só no finalize do job
