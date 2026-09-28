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
import time

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
    0-based no documento final: página que recebe o QR) e, opcionais,
    `page_offset` (int, 0-based: índice final da 1ª página de `content`) e
    `page_total` (int: nº de páginas do documento final) — o pipeline em
    etapas carimba o documento por faixas. Sem eles, `content` é o
    documento inteiro.
    """
    reader = PdfFileReader(io.BytesIO(content), strict=False)
    count = reader.getNumPages()
    # Pipeline em etapas: o conteúdo pode ser só um PEDAÇO do documento.
    offset = int(header.get("page_offset") or 0)
    total = int(header.get("page_total") or (offset + count))
    qr_index = header.get("qr_page_index")
    writer = PdfFileWriter()
    for idx in range(count):
        number = offset + idx
        page = reader.getPage(idx)
        page.mergePage(_overlay_page(
            header, number + 1, total, watermark,
            with_qr=bool(header.get("verify_url")) and qr_index == number,
        ))
        writer.addPage(page)
    return pdf_bytes(writer)


MAX_PASSES = 3

# Pipeline em etapas (emenda P4): cada fatia cabe no limite de CPU do worker.
CHUNK_PAGES_PARAM = "afr_qualificacao.relatorio_build_chunk_pages"
STEP_CPU_PARAM = "afr_qualificacao.relatorio_build_step_cpu"
# Páginas por fatia; o prazo de CPU (Budget) corta a fatia antes, se preciso.
DEFAULT_CHUNK_PAGES = 12
# Orçamento de CPU por invocação do cron (revisão final P4: 15 s). É checado
# por página, então uma invocação pode passar do orçamento pelo custo de uma
# página (medido: alguns segundos no vetorial pesado).
DEFAULT_STEP_CPU = 15.0
BODY_PAGE_COST = 0.05  # s de CPU estimados p/ carimbar uma página do corpo


class Budget:
    """Limite de UMA unidade: nº de páginas e prazo absoluto de CPU
    (`time.process_time()`). Toda unidade processa ≥ 1 página. `retry`
    (1 = 1ª tentativa) divide `max_pages` por 2^(retry-1): a fatia que
    derrubou o worker volta menor."""

    def __init__(self, max_pages=None, cpu_deadline=None, retry=1):
        if max_pages and retry > 1:
            max_pages = max(1, max_pages >> (retry - 1))
        self.max_pages = max_pages
        self.cpu_deadline = cpu_deadline

    @property
    def unlimited(self):
        return not self.max_pages and self.cpu_deadline is None

    def exhausted(self, done):
        if done < 1:
            return False
        if self.max_pages and done >= self.max_pages:
            return True
        return self.cpu_deadline is not None and time.process_time() >= self.cpu_deadline


UNLIMITED = Budget()


class MemoryStore:
    """Store de blobs do `_build` síncrono (o job usa ir.attachment)."""

    def __init__(self):
        self._blobs = {}

    def put(self, name, data):
        key = "m%d" % (len(self._blobs) + 1)
        self._blobs[key] = data
        return key

    def get(self, key):
        return self._blobs[key]


def stage_progress(st):
    """0–99 para a UI (100 = finalize do job)."""
    phase = st.get("phase")
    if phase == "sources":
        return 2
    if phase == "fit":
        done = sum(a["count"] for a in st["annexes"])
        return 5 + int(40 * min(done / max(st.get("annex_pages") or 1, 1), 1.0))
    if phase == "body":
        return 46
    if phase == "stamp":
        return 50 + int(45 * st["stamp"] / max(st["total"], 1))
    if phase == "concat":
        return 96
    return 99


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


def section_labels(page_map, sections, total):
    """Rótulo de seção de cada página final (0-based).

    Página onde começam seções: a 1ª delas. Página sem início: a última
    seção iniciada antes. Antes da 1ª seção: "".

    :param page_map: `layout["page_map"]` ({marcador: nº final 1-based})
    :param sections: [(marcador, rótulo)] na ordem do documento
    :param total: nº de páginas do documento final
    """
    starts = sorted(
        (page_map[key], order, label)
        for order, (key, label) in enumerate(sections) if key in page_map
    )
    labels, current, pos = [], "", 0
    for page in range(1, total + 1):
        first = None
        while pos < len(starts) and starts[pos][0] <= page:
            if starts[pos][0] == page and first is None:
                first = starts[pos][2]
            current = starts[pos][2]
            pos += 1
        labels.append(current if first is None else first)
    return labels


def cover_page_index(page_map, first_block_key):
    """Índice final (0-based) da capa, se o 1º bloco do corpo for a capa."""
    if not first_block_key or first_block_key not in page_map:
        return None
    return page_map[first_block_key] - 1


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
        # `relatorio.env`: o contexto do registro (token e data da emissão)
        # chega ao `doc` do template.
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
    def _body_render_data(self, relatorio, page_map):
        """`data` do report (fato fixado P3 #1): marcadores + page_map."""
        return {"with_markers": True, "page_map": dict(page_map)}

    @api.model
    def _render_body_and_markers(self, relatorio, page_map):
        """Corpo em PDF + `{marcador: página 0-based}` (caminho dos marcadores)."""
        body = self._render_report(relatorio, self._body_render_data(relatorio, page_map))
        return body, self._find_markers(body)

    @api.model
    def _file_anexos(self, relatorio):
        """Anexos incluídos que intercalam arquivos (ordem de `anexo_ids`).

        `slot_kind='bloco'` fica de fora: o template de P3 já renderiza o
        bloco no corpo, logo após o separador.
        """
        return relatorio._anexos_included().filtered(lambda a: a.slot_kind != "bloco")

    # ------------------------------------------------------------------
    # Pipeline em etapas: sources → fit → body → stamp → concat
    # ------------------------------------------------------------------
    @api.model
    def _build(self, relatorio, watermark=False):
        """Corpo + anexos + índice + carimbo, síncrono: as MESMAS fases do job
        (`afr.relatorio.build.job`), em memória e sem limite. Sem writes no
        banco. :return: `(pdf_bytes, avisos)`."""
        relatorio.ensure_one()
        st, store = self._stage_init(watermark), MemoryStore()
        while st["phase"] != "done":
            self._stage_run(relatorio, st, store, UNLIMITED)
        return store.get(st["final_blob"]), st["warnings"]

    @api.model
    def _stage_init(self, watermark):
        return {
            "phase": "sources", "watermark": bool(watermark), "warnings": [],
            "annexes": [], "annex_pages": 0, "fit": [0, 0, 0], "page_cost": {},
            "final_pages": [], "total": 0, "qr_page_index": None,
            "stamp": 0, "stamped": [], "final_blob": None,
        }

    @api.model
    def _stage_run(self, relatorio, st, store, budget):
        """Executa UMA unidade da fase atual; avança `st["phase"]` ao concluir."""
        relatorio.ensure_one()
        handler = {
            "sources": self._stage_sources, "fit": self._stage_fit,
            "body": self._stage_body, "stamp": self._stage_stamp,
            "concat": self._stage_concat,
        }.get(st["phase"])
        if handler is None:
            raise UserError(_("Etapa de montagem inválida: %s") % st["phase"])
        handler(relatorio, st, store, budget)

    @api.model
    def _stage_sources(self, relatorio, st, store, budget):
        """Arquivos utilizáveis de cada anexo → store. Tudo é RESOLVIDO antes
        do 1º `store.put`: `_raw_files()` pode renderizar o PDF do engc e o
        core pode dar `cr.commit()` (commit_assetsbundle) nesse render."""
        # Import tardio: relatorio_anexo_files importa este módulo.
        from .relatorio_anexo_files import PROBLEM_NO_ACCESS

        resolved = []
        for anexo in self._file_anexos(relatorio):
            label = _("Anexo %s (%s)") % (anexo.numero or "?", anexo.title or anexo.code or "")
            resolved.append((anexo.code or "anexo-%d" % anexo.id, label, anexo._raw_files()))
        annexes, total_pages = [], 0
        for code, label, raw in resolved:
            entry = {"code": code, "label": label, "files": [], "chunks": [], "count": 0}
            if not raw:
                st["warnings"].append(_("%s: nenhum arquivo — só o separador foi incluído.") % label)
            for content, mimetype, caption in raw:
                # `None` = sem permissão de leitura (T3): nunca entra no PDF.
                problem = (PROBLEM_NO_ACCESS if content is None
                           else file_problem(content, mimetype))
                if problem:
                    st["warnings"].append(_("%s: '%s' ignorado — %s.") % (label, caption, problem))
                    continue
                is_pdf = guess_mimetype(content, default=mimetype or "") == "application/pdf"
                pages = open_pdf(content).getNumPages() if is_pdf else 1
                total_pages += pages
                entry["files"].append({"kind": "pdf" if is_pdf else "image",
                                       "caption": caption, "pages": pages, "_content": content})
            annexes.append(entry)
        for entry in annexes:  # writes só agora, depois de toda renderização
            for item in entry["files"]:
                item["blob"] = store.put("src", item.pop("_content"))
        st.update(annexes=annexes, annex_pages=total_pages, fit=[0, 0, 0], phase="fit")

    @api.model
    def _stage_fit(self, relatorio, st, store, budget):
        """Encaixa na área útil as páginas de UM anexo, do cursor até o orçamento."""
        a_idx, f_idx, p_idx = st["fit"]
        annexes = st["annexes"]
        if a_idx < len(annexes):
            entry = annexes[a_idx]
            # keep_alive: PyPDF2 lê os streams de forma preguiçosa até o write.
            writer, keep_alive, tried = PdfFileWriter(), [], 0
            cpu0 = time.process_time()
            while f_idx < len(entry["files"]) and not budget.exhausted(tried):
                item = entry["files"][f_idx]
                content = store.get(item["blob"])
                if item["kind"] == "image":
                    reader = PdfFileReader(io.BytesIO(image_to_pdf(content, item["caption"])))
                    keep_alive.append(reader)
                    writer.addPage(reader.getPage(0))
                    tried += 1
                    f_idx, p_idx = f_idx + 1, 0
                    continue
                reader = open_pdf(content)
                keep_alive.append(reader)
                count = reader.getNumPages()
                while p_idx < count and not budget.exhausted(tried):
                    tried += 1
                    # open_pdf só valida a página 0: uma página seguinte
                    # corrompida (stream/objeto ilegível) é pulada com aviso,
                    # nunca derruba a montagem inteira.
                    try:
                        page = fit_page_to_usable(reader.getPage(p_idx))
                    except Exception as exc:  # zlib.error, PdfReadError, KeyError...
                        st["warnings"].append(_(
                            "%s: '%s', página %d ignorada — página ilegível (%s)."
                        ) % (entry["label"], item["caption"], p_idx + 1, exc))
                    else:
                        writer.addPage(page)
                    p_idx += 1
                if p_idx >= count:
                    f_idx, p_idx = f_idx + 1, 0
            pages = writer.getNumPages()
            if pages:
                key = store.put("fit", pdf_bytes(writer))
                entry["chunks"].append({"blob": key, "pages": pages})
                entry["count"] += pages
                st["page_cost"][key] = (time.process_time() - cpu0) / pages
            if f_idx >= len(entry["files"]):
                a_idx, f_idx, p_idx = a_idx + 1, 0, 0
        st["fit"] = [a_idx, f_idx, p_idx]
        if a_idx >= len(annexes):
            st["phase"] = "body"

    @api.model
    def _stage_body(self, relatorio, st, store, budget):
        """Corpo com marcadores até o índice convergir; ordem final das páginas."""
        codes = [a["code"] for a in st["annexes"]]
        counts = {a["code"]: a["count"] for a in st["annexes"]}
        page_map = {}
        for attempt in range(1, MAX_PASSES + 1):
            body, markers = self._render_body_and_markers(relatorio, page_map)
            body_count = PdfFileReader(io.BytesIO(body), strict=False).getNumPages()
            layout = compute_layout(markers, body_count, counts, codes)
            if layout["page_map"] == page_map:
                break
            if attempt == MAX_PASSES:
                st["warnings"].append(_(
                    "A numeração do índice não estabilizou após %d renderizações; "
                    "confira o índice."
                ) % MAX_PASSES)
                break
            page_map = layout["page_map"]
        for code in layout["trailing"]:
            if counts.get(code):
                st["warnings"].append(_(
                    "Anexo '%s': marcador do separador não encontrado no corpo; "
                    "páginas incluídas no fim do documento."
                ) % code)
        body_key = store.put("body", body)  # depois de TODOS os renders
        annex_refs = {
            a["code"]: [[c["blob"], i] for c in a["chunks"] for i in range(c["pages"])]
            for a in st["annexes"]
        }
        final = []
        for idx in range(body_count):
            final.append([body_key, idx])
            for code in layout["insert_after"].get(idx, []):
                final.extend(annex_refs[code])
        for code in layout["trailing"]:
            final.extend(annex_refs[code])
        first = relatorio._body_blocks()[:1]
        st.update(
            final_pages=final, total=len(final), stamp=0, stamped=[], phase="stamp",
            qr_page_index=self._qr_page_index(relatorio, markers, layout),
            section_labels=section_labels(
                layout["page_map"], relatorio._report_section_entries(), len(final)),
            cover_page_index=cover_page_index(
                layout["page_map"],
                "bloco:%d" % first.id if first and first.block_kind == "capa" else None),
        )

    @api.model
    def _stage_stamp_count(self, st, budget):
        """Quantas páginas carimbar nesta unidade (≥ 1)."""
        remaining = st["total"] - st["stamp"]
        if budget.unlimited:
            return remaining
        cap = min(budget.max_pages or remaining, remaining)
        if budget.cpu_deadline is None:
            return max(cap, 1)
        allowance = 0.8 * max(budget.cpu_deadline - time.process_time(), 0.0)
        count, spent = 0, 0.0
        for blob, _idx in st["final_pages"][st["stamp"]:st["stamp"] + cap]:
            # Carimbar reparseia o content stream: custa ~ o que o fit custou.
            spent += st["page_cost"].get(blob, BODY_PAGE_COST)
            if count and spent > allowance:
                break
            count += 1
        return max(count, 1)

    @api.model
    def _assemble_range(self, refs, store):
        """PDF só com as páginas `refs` ([blob, índice]) na ordem dada."""
        writer, readers = PdfFileWriter(), {}
        for blob, idx in refs:
            reader = readers.get(blob)
            if reader is None:
                reader = readers[blob] = PdfFileReader(io.BytesIO(store.get(blob)), strict=False)
            writer.addPage(reader.getPage(idx))
        return pdf_bytes(writer)

    @api.model
    def _stage_stamp(self, relatorio, st, store, budget):
        """Monta a faixa `[stamp, stamp+n)` a partir das fontes e carimba."""
        start = st["stamp"]
        end = start + self._stage_stamp_count(st, budget)
        content = self._assemble_range(st["final_pages"][start:end], store)
        header = self._header(relatorio, st["watermark"], qr_page_index=st["qr_page_index"])
        header.update(
            page_offset=start, page_total=st["total"],
            section_labels=st.get("section_labels") or [],
            cover_page_index=st.get("cover_page_index"),
        )
        st["stamped"].append(store.put("stamp", self._stamp(content, header, st["watermark"])))
        st["stamp"] = end
        if end >= st["total"]:
            st["phase"] = "concat"

    @api.model
    def _stage_concat(self, relatorio, st, store, budget):
        """Junta as faixas carimbadas (uma só faixa: reaproveita o blob)."""
        stamped = st["stamped"]
        if len(stamped) == 1:
            st["final_blob"] = stamped[0]
        else:
            writer, keep_alive = PdfFileWriter(), []
            for key in stamped:
                reader = PdfFileReader(io.BytesIO(store.get(key)), strict=False)
                keep_alive.append(reader)
                for idx in range(reader.getNumPages()):
                    writer.addPage(reader.getPage(idx))
            st["final_blob"] = store.put("final", pdf_bytes(writer))
        st["phase"] = "done"

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
