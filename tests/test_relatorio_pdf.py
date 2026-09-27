"""P4 — montagem do PDF do Relatório Final (núcleo + anexos + build)."""
import io

from PyPDF2 import PdfFileReader, PdfFileWriter
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from PIL import Image

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.afr_qualificacao.models import relatorio_pdf as rp

from .relatorio_fakes import encrypt_pdf, make_pdf, make_png, pdf_pages_text, squash

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
