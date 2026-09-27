"""P4 — montagem do PDF do Relatório Final (núcleo + anexos + build)."""
import base64
import io
from unittest.mock import patch

from PyPDF2 import PdfFileReader, PdfFileWriter
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

    def test_open_pdf_accepts_owner_only_encryption(self):
        reader = rp.open_pdf(encrypt_pdf(make_pdf([["cert"]]), user_pw=""))
        self.assertEqual(reader.getNumPages(), 1)

    def test_open_pdf_rejects_user_password(self):
        with self.assertRaisesRegex(ValueError, "senha"):
            rp.open_pdf(encrypt_pdf(make_pdf([["x"]]), user_pw="segredo"))

    def test_open_pdf_rejects_garbage(self):
        with self.assertRaisesRegex(ValueError, "ilegível"):
            rp.open_pdf(b"nao e pdf")


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
