"""Montagem do PDF do Relatório Final (spec §6).

Funções puras (testáveis sem registry) + AbstractModel `afr.relatorio.pdf`,
que as expõe e orquestra: render do corpo com marcadores, intercalação dos
anexos, re-render com `page_map` e carimbo (cabeçalho, rodapé, QR, marca
d'água). Bibliotecas: PyPDF2 1.26 (API antiga), reportlab 3.5, pdfminer.six
20200726 e Pillow (efetivo no container: 11.3.0 do venv, que sombreia a 8.1.2
do sistema; `ImageOps.exif_transpose` existe em ambas).
"""
import base64
import io
import re

from PIL import Image, ImageOps
from PyPDF2.pdf import PageObject
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.pdf import PdfFileReader, PdfFileWriter

MARKER_RE = re.compile(r"@@RQ:(bloco|anexo):([A-Za-z0-9_\-]+)@@")
A4_W, A4_H = A4
# Topo/rodapé iguais ao paperformat_relatorio_final (P3: 35/25 mm) — o carimbo
# vive nelas. Lateral MENOR de propósito (paperformat usa 20 mm): páginas de
# anexo (gráficos) ganham largura; o carimbo também usa esta margem lateral.
MARGIN_TOP = 35 * mm
MARGIN_BOTTOM = 25 * mm
MARGIN_SIDE = 12 * mm
# (x, y, largura, altura) da área útil onde páginas de anexo são encaixadas.
USABLE = (
    MARGIN_SIDE,
    MARGIN_BOTTOM,
    A4_W - 2 * MARGIN_SIDE,
    A4_H - MARGIN_TOP - MARGIN_BOTTOM,
)
WATERMARK_TEXT = "MINUTA — SEM VALIDADE"
IMAGE_MIMETYPES = frozenset({
    "image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff", "image/webp",
})

REPORT_CORPO = "afr_qualificacao.action_report_relatorio_corpo"


def file_problem(content, mimetype=None):
    """`None` se o arquivo é utilizável na montagem; senão o motivo em pt-BR."""
    if not content:
        return "arquivo vazio"
    detected = guess_mimetype(content, default=mimetype or "application/octet-stream")
    if detected == "application/pdf":
        try:
            open_pdf(content)
        except ValueError as exc:
            return str(exc)
        return None
    if detected in IMAGE_MIMETYPES:
        try:
            Image.open(io.BytesIO(content)).verify()
        except Exception as exc:  # PIL levanta vários tipos
            return "imagem ilegível (%s)" % exc
        return None
    return "tipo de arquivo não suportado (%s)" % detected


def pdf_bytes(writer):
    """Serializa um PdfFileWriter."""
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def open_pdf(content):
    """Abre um PDF para leitura ou levanta ValueError com o motivo (pt-BR).

    PDF criptografado só com senha de dono (comum em certificados de
    terceiros) abre com senha vazia; senha de usuário ou algoritmo não
    suportado pelo PyPDF2 1.26 vira ValueError — nunca outra exceção.
    """
    try:
        reader = PdfFileReader(io.BytesIO(content), strict=False)
        if reader.isEncrypted:
            try:
                ok = reader.decrypt("")
            except NotImplementedError:
                # TODO(4.10): PyPDF2 1.26 não decodifica AES (V4/V5,
                # comum em certificados gerados por ferramentas recentes);
                # cai aqui mesmo quando a senha de dono está correta.
                # Fallback futuro: `pdftocairo` (poppler) para reabrir/
                # re-renderizar esses PDFs antes de montar o relatório.
                raise ValueError("PDF com criptografia não suportada")
            if not ok:
                raise ValueError("PDF protegido por senha")
        if reader.getNumPages() < 1:
            raise ValueError("PDF sem páginas")
        reader.getPage(0)
    except ValueError:
        raise
    except Exception as exc:  # PdfReadError, KeyError, struct.error, ...
        raise ValueError("PDF ilegível (%s)" % exc)
    return reader


def find_markers(content):
    """Mapa `"bloco:<id>"`/`"anexo:<code>"` → índice 0-based da página.

    Primeira ocorrência vence (um marcador repetido não desloca a posição).
    """
    found = {}
    for idx, layout in enumerate(extract_pages(io.BytesIO(content))):
        text = "".join(
            el.get_text() for el in layout if isinstance(el, LTTextContainer)
        )
        for kind, key in MARKER_RE.findall(text):
            found.setdefault("%s:%s" % (kind, key), idx)
    return found


def _matmul(m1, m2):
    """Compõe matrizes PDF [a b c d e f]: aplica m1 e depois m2."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return [
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    ]


def fit_page_to_usable(page):
    """Nova página A4 com `page` encaixada (escala ≤ 1) na área útil.

    Considera CropBox e `/Rotate` (90/180/270): o conteúdo é girado para a
    orientação de leitura e a página resultante não tem `/Rotate`, então o
    carimbo aplicado depois cai sempre no lugar certo.
    """
    box = page.cropBox
    llx = float(box.getLowerLeft_x())
    lly = float(box.getLowerLeft_y())
    width = float(box.getWidth())
    height = float(box.getHeight())
    rotate = int(page.get("/Rotate", 0) or 0) % 360
    matrix = [1, 0, 0, 1, -llx, -lly]
    if rotate == 90:
        matrix = _matmul(matrix, [0, -1, 1, 0, 0, width])
        shown_w, shown_h = height, width
    elif rotate == 180:
        matrix = _matmul(matrix, [-1, 0, 0, -1, width, height])
        shown_w, shown_h = width, height
    elif rotate == 270:
        matrix = _matmul(matrix, [0, 1, -1, 0, height, 0])
        shown_w, shown_h = height, width
    else:
        shown_w, shown_h = width, height
    ux, uy, uw, uh = USABLE
    scale = min(uw / shown_w, uh / shown_h, 1.0)
    tx = ux + (uw - shown_w * scale) / 2.0
    ty = uy + (uh - shown_h * scale) / 2.0
    matrix = _matmul(matrix, [scale, 0, 0, scale, tx, ty])
    blank = PageObject.createBlankPage(None, A4_W, A4_H)
    blank.mergeTransformedPage(page, matrix)
    return blank


def image_to_pdf(content, caption):
    """Uma página A4: imagem encaixada na área útil + legenda embaixo.

    Respeita a orientação EXIF (fotos de celular). A página já sai dentro da
    área útil — não passar por `fit_page_to_usable` de novo.
    """
    img = Image.open(io.BytesIO(content))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    ux, uy, uw, uh = USABLE
    caption_h = 10 * mm
    avail_h = uh - caption_h
    img_w, img_h = img.size
    scale = min(uw / img_w, avail_h / img_h)
    width, height = img_w * scale, img_h * scale
    x = ux + (uw - width) / 2.0
    y = uy + caption_h + (avail_h - height) / 2.0
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(img), x, y, width=width, height=height)
    c.setFont("Helvetica", 9)
    c.drawCentredString(A4_W / 2.0, uy + 3 * mm, (caption or "")[:160])
    c.showPage()
    c.save()
    return buf.getvalue()


def _overlay_page(header, page_no, total, watermark, with_qr):
    """Página A4 transparente com cabeçalho/rodapé (e QR / marca d'água)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    top = A4_H - 10 * mm
    logo = header.get("logo")
    if logo:
        try:
            c.drawImage(
                ImageReader(io.BytesIO(logo)), MARGIN_SIDE, top - 16 * mm,
                width=40 * mm, height=16 * mm, preserveAspectRatio=True,
                anchor="w", mask="auto",
            )
        except Exception:  # logo SVG/corrompido: cabeçalho segue sem logo
            pass
    right = A4_W - MARGIN_SIDE
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(right, top - 4 * mm, header.get("title") or "")
    c.setFont("Helvetica", 8)
    c.drawRightString(right, top - 9 * mm, header.get("equipment") or "")
    c.drawRightString(
        right, top - 13 * mm,
        "%s   %s" % (header.get("revision") or "", header.get("date") or ""),
    )
    c.setLineWidth(0.5)
    c.line(MARGIN_SIDE, top - 18 * mm, right, top - 18 * mm)
    c.line(MARGIN_SIDE, 20 * mm, right, 20 * mm)
    c.drawString(MARGIN_SIDE, 12 * mm, header.get("footer") or "")
    qr_size = 16 * mm
    page_label_right = right - (qr_size + 3 * mm if with_qr else 0)
    c.drawRightString(page_label_right, 12 * mm, "Página %d de %d" % (page_no, total))
    if with_qr and header.get("verify_url"):
        widget = QrCodeWidget(header["verify_url"])
        x0, y0, x1, y1 = widget.getBounds()
        drawing = Drawing(
            qr_size, qr_size,
            transform=[qr_size / (x1 - x0), 0, 0, qr_size / (y1 - y0), 0, 0],
        )
        drawing.add(widget)
        renderPDF.draw(drawing, c, right - qr_size, 3 * mm)
    if watermark:
        c.saveState()
        c.setFillColorRGB(0.8, 0.1, 0.1)
        c.setFillAlpha(0.18)
        c.setFont("Helvetica-Bold", 48)
        c.translate(A4_W / 2.0, A4_H / 2.0)
        c.rotate(45)
        c.drawCentredString(0, 0, WATERMARK_TEXT)
        c.restoreState()
    c.showPage()
    c.save()
    return PdfFileReader(io.BytesIO(buf.getvalue())).getPage(0)


def stamp_pdf(content, header, watermark):
    """Carimba todas as páginas: "Página X de Y", cabeçalho, QR, marca d'água.

    `header`: dict com `logo` (bytes|None), `title`, `equipment`, `revision`,
    `date`, `footer`, `verify_url` (str|False), `qr_page_index` (int|None,
    0-based: página que recebe o QR).
    """
    reader = PdfFileReader(io.BytesIO(content), strict=False)
    total = reader.getNumPages()
    qr_index = header.get("qr_page_index")
    writer = PdfFileWriter()
    for idx in range(total):
        page = reader.getPage(idx)
        page.mergePage(_overlay_page(
            header, idx + 1, total, watermark,
            with_qr=bool(header.get("verify_url")) and qr_index == idx,
        ))
        writer.addPage(page)
    return pdf_bytes(writer)


MAX_PASSES = 3


def compute_layout(markers, body_count, annex_counts, codes):
    """Onde cada anexo entra e o número final (1-based) de cada marcador.

    :param markers: `{"bloco:<id>"|"anexo:<code>": índice 0-based no corpo}`
    :param body_count: nº de páginas do corpo renderizado
    :param annex_counts: `{code: nº de páginas do anexo}`
    :param codes: codes dos anexos incluídos, na ordem de `sequence`
    :return: dict com `insert_after` ({índice do corpo: [codes]}),
        `trailing` ([codes] sem separador no corpo → fim do documento),
        `body_final` (nº final de cada página do corpo), `page_map`
        ({marcador: nº final}) e `total`.
    """
    insert_after, trailing = {}, []
    for code in codes:
        idx = markers.get("anexo:%s" % code)
        if idx is None or idx >= body_count:
            trailing.append(code)
        else:
            insert_after.setdefault(idx, []).append(code)
    body_final, offset = [], 0
    for idx in range(body_count):
        body_final.append(idx + 1 + offset)
        offset += sum(annex_counts.get(code, 0) for code in insert_after.get(idx, []))
    page_map = {
        key: body_final[idx] for key, idx in markers.items() if idx < body_count
    }
    next_page = body_count + offset + 1
    for code in trailing:
        if annex_counts.get(code):
            page_map["anexo:%s" % code] = next_page
            next_page += annex_counts[code]
    return {
        "insert_after": insert_after,
        "trailing": trailing,
        "body_final": body_final,
        "page_map": page_map,
        "total": next_page - 1,
    }


class AfrRelatorioPdf(models.AbstractModel):
    _name = "afr.relatorio.pdf"
    _description = "Montagem do PDF do Relatório Final"

    @api.model
    def _find_markers(self, pdf_content):
        return find_markers(pdf_content)

    @api.model
    def _image_to_pdf(self, content, caption):
        return image_to_pdf(content, caption)

    @api.model
    def _stamp(self, pdf_content, header, watermark):
        return stamp_pdf(pdf_content, header, watermark)

    @api.model
    def _render_report(self, relatorio, data):
        """Renderiza o corpo QWeb (P3) em PDF de verdade.

        `force_report_rendering`: em modo teste o Odoo devolveria HTML; os
        testes fazem patch de `_render_qweb_pdf`, então isto só importa
        quando algum teste esquece o patch (falha alta, não PDF inválido).
        As chaves de `data` viram variáveis do template (`with_markers`,
        `page_map` — fato fixado P3 #1; nunca por contexto).
        """
        relatorio.ensure_one()
        # `relatorio.env`: o contexto do registro (token da emissão, filtro de
        # pedaços do fallback) chega ao `doc` do template.
        content, fmt = relatorio.env["ir.actions.report"].with_context(
            force_report_rendering=True
        )._render_qweb_pdf(REPORT_CORPO, res_ids=relatorio.ids, data=dict(data))
        if fmt != "pdf":
            raise UserError(_(
                "A renderização do relatório não gerou PDF (formato '%s')."
            ) % fmt)
        return content

    # ------------------------------------------------------------------
    # Montagem (spec §6)
    # ------------------------------------------------------------------
    @api.model
    def build(self, relatorio, watermark=False):
        """PDF final em bytes (minuta se `watermark`). Avisos: `_build`."""
        return self._build(relatorio, watermark=watermark)[0]

    @api.model
    def _build(self, relatorio, watermark=False):
        """Corpo + anexos intercalados + índice + carimbo.

        Sem efeitos colaterais no banco (nenhum write): quem emite chama
        isto ANTES de gravar o estado da emissão — a 1ª renderização sem
        assets em cache faz `cr.commit()` (`commit_assetsbundle` do core).

        :return: `(pdf_bytes, avisos)` — avisos são textos pt-BR sobre
            arquivos ignorados, anexos sem separador e índice que não
            estabilizou (P5 pode transformá-los em achados).
        """
        relatorio.ensure_one()
        warnings = []
        codes, annex_data, annex_counts = [], {}, {}
        for anexo in self._file_anexos(relatorio):
            code = anexo.code or "anexo-%d" % anexo.id
            data, count = self._annex_pdf(anexo, warnings)
            codes.append(code)
            annex_data[code] = data
            annex_counts[code] = count

        page_map = {}
        for attempt in range(1, MAX_PASSES + 1):
            body, markers = self._render_body_and_markers(relatorio, page_map)
            body_count = PdfFileReader(io.BytesIO(body), strict=False).getNumPages()
            layout = compute_layout(markers, body_count, annex_counts, codes)
            if layout["page_map"] == page_map:
                break
            if attempt == MAX_PASSES:
                warnings.append(_(
                    "A numeração do índice não estabilizou após %d renderizações; "
                    "confira o índice."
                ) % MAX_PASSES)
                break
            page_map = layout["page_map"]

        for code in layout["trailing"]:
            if annex_counts.get(code):
                warnings.append(_(
                    "Anexo '%s': marcador do separador não encontrado no corpo; "
                    "páginas incluídas no fim do documento."
                ) % code)
        merged = self._assemble(body, body_count, layout, annex_data)
        header = self._header(
            relatorio, watermark,
            qr_page_index=self._qr_page_index(relatorio, markers, layout),
        )
        return self._stamp(merged, header, watermark), warnings

    @api.model
    def _body_render_data(self, relatorio, page_map):
        """`data` do report (fato fixado P3 #1): marcadores + page_map."""
        return {"with_markers": True, "page_map": dict(page_map)}

    @api.model
    def _render_body_and_markers(self, relatorio, page_map):
        """Corpo em PDF + `{marcador: página 0-based}` (caminho dos marcadores).

        O Task 6 (fallback) sobrescreveria só este método.
        """
        body = self._render_report(relatorio, self._body_render_data(relatorio, page_map))
        return body, self._find_markers(body)

    @api.model
    def _file_anexos(self, relatorio):
        """Anexos incluídos que intercalam arquivos (ordem de `anexo_ids`).

        `slot_kind='bloco'` fica de fora: o template de P3 já renderiza o
        bloco no corpo, logo após o separador.
        """
        return relatorio._anexos_included().filtered(lambda a: a.slot_kind != "bloco")

    @api.model
    def _annex_pdf(self, anexo, warnings):
        """`(pdf_bytes, nº de páginas)` do anexo, páginas prontas para carimbo."""
        # Import tardio: relatorio_anexo_files importa este módulo.
        from .relatorio_anexo_files import PROBLEM_NO_ACCESS

        label = _("Anexo %s (%s)") % (anexo.numero or "?", anexo.title or anexo.code or "")
        raw = anexo._raw_files()
        if not raw:
            warnings.append(_("%s: nenhum arquivo — só o separador foi incluído.") % label)
            return b"", 0
        writer = PdfFileWriter()
        keep_alive = []  # PyPDF2 lê os streams de forma preguiçosa até o write
        for content, mimetype, caption in raw:
            # `None` = sem permissão de leitura (T3): nunca entra no PDF.
            problem = (PROBLEM_NO_ACCESS if content is None
                       else file_problem(content, mimetype))
            if problem:
                warnings.append(_("%s: '%s' ignorado — %s.") % (label, caption, problem))
                continue
            if guess_mimetype(content, default=mimetype or "") == "application/pdf":
                reader = open_pdf(content)
                keep_alive.append(reader)
                for idx in range(reader.getNumPages()):
                    writer.addPage(fit_page_to_usable(reader.getPage(idx)))
            else:
                img_reader = PdfFileReader(io.BytesIO(image_to_pdf(content, caption)))
                keep_alive.append(img_reader)
                writer.addPage(img_reader.getPage(0))
        count = writer.getNumPages()
        return (pdf_bytes(writer) if count else b""), count

    @api.model
    def _assemble(self, body, body_count, layout, annex_data):
        """Intercala as páginas dos anexos depois da página do separador."""
        writer = PdfFileWriter()
        body_reader = PdfFileReader(io.BytesIO(body), strict=False)
        keep_alive = [body_reader]

        def add_annex(code):
            data = annex_data.get(code)
            if not data:
                return
            reader = PdfFileReader(io.BytesIO(data), strict=False)
            keep_alive.append(reader)
            for idx in range(reader.getNumPages()):
                writer.addPage(reader.getPage(idx))

        for idx in range(body_count):
            writer.addPage(body_reader.getPage(idx))
            for code in layout["insert_after"].get(idx, []):
                add_annex(code)
        for code in layout["trailing"]:
            add_annex(code)
        return pdf_bytes(writer)

    @api.model
    def _qr_page_index(self, relatorio, markers, layout):
        """Página final (0-based) do 1º bloco `assinaturas` incluído.

        Sem esse bloco (ou marcador não achado): última página do corpo.
        """
        body_final = layout["body_final"]
        if not body_final:
            return None
        signature = relatorio._body_blocks().filtered(
            lambda b: b.block_kind == "assinaturas"
        )[:1]
        idx = markers.get("bloco:%d" % signature.id) if signature else None
        if idx is None or idx >= len(body_final):
            idx = len(body_final) - 1
        return body_final[idx] - 1

    @api.model
    def _header(self, relatorio, watermark, qr_page_index=None):
        """Dados do carimbo (ver `stamp_pdf`).

        Data: `rq_emission_date` do contexto do RELATÓRIO (ruling 1.9 —
        emissão em curso, ainda sem registro) ou a da emissão vigente.
        """
        company = (relatorio.company_id or self.env.company).with_context(bin_size=False)
        equipment = relatorio.equipment_id
        if watermark:
            date_label = _("MINUTA")
            verify_url = False
        else:
            issued = (relatorio.env.context.get("rq_emission_date")
                      or relatorio.current_emissao_id.issued_at)
            date_label = fields.Datetime.context_timestamp(
                relatorio, fields.Datetime.to_datetime(issued)
            ).strftime("%d/%m/%Y") if issued else ""
            verify_url = relatorio.verify_url or False
        return {
            "logo": base64.b64decode(company.logo) if company.logo else None,
            "title": relatorio.name or "",
            "equipment": _("Equipamento: %s  TAG: %s") % (
                equipment.display_name or "", equipment.tag or "—"),
            "revision": relatorio.revision_label or "",
            "date": date_label,
            "footer": company.email or "",
            "verify_url": verify_url,
            "qr_page_index": qr_page_index,
        }
