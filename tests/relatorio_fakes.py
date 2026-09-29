"""Apoio aos testes do Relatório Final (P4) — NÃO é módulo de teste.

Não registrar em tests/__init__.py. Contém:
- PDFs/imagens sintéticos (reportlab/PIL) — nenhum teste depende de wkhtmltopdf;
- `FakeCorpo`: substitui `ir.actions.report._render_qweb_pdf` e gera o corpo
  a partir dos blocos do relatório, com os mesmos marcadores do template real;
- `RelatorioFixtureMixin`: OS + qualificação + relatório limpo e helpers.
"""
import io
import re
from datetime import datetime
from unittest.mock import patch

from PIL import Image
from PyPDF2 import PdfFileReader, PdfFileWriter
from pdfminer.high_level import extract_text
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_pdf(pages, size=A4, rotate=0):
    """`pages`: list[list[str]] — uma lista de linhas por página.

    Linhas que começam com '@@RQ:' saem em branco, 1pt (como o `.rq-mark`
    do template real). O texto começa abaixo da margem superior reservada.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=size)
    _width, height = size
    for lines in pages:
        y = height - 120
        for line in lines:
            if line.startswith("@@RQ:"):
                c.setFillColorRGB(1, 1, 1)
                c.setFont("Helvetica", 1)
                c.drawString(72, y, line)
                c.setFillColorRGB(0, 0, 0)
                y -= 2
            else:
                c.setFont("Helvetica", 11)
                c.drawString(72, y, line)
                y -= 14
        c.showPage()
    c.save()
    data = buf.getvalue()
    if not rotate:
        return data
    reader = PdfFileReader(io.BytesIO(data))
    writer = PdfFileWriter()
    for i in range(reader.getNumPages()):
        page = reader.getPage(i)
        page.rotateClockwise(rotate)
        writer.addPage(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def encrypt_pdf(data, user_pw="", owner_pw="dono"):
    """Criptografa (RC4 128) — `user_pw=""` = só senha de dono."""
    reader = PdfFileReader(io.BytesIO(data))
    writer = PdfFileWriter()
    for i in range(reader.getNumPages()):
        writer.addPage(reader.getPage(i))
    writer.encrypt(user_pw, owner_pw)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_png(width=400, height=300, color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def pdf_pages_text(data):
    """Texto de cada página (pdfminer separa páginas com form feed)."""
    pages = extract_text(io.BytesIO(data)).split("\x0c")
    count = PdfFileReader(io.BytesIO(data)).getNumPages()
    return pages[:count]


def squash(text):
    """Remove espaços/quebras — texto girado sai 'M I N U T A' no pdfminer."""
    return re.sub(r"\s", "", text)


def make_user(env, login, group_xmlid, email=None):
    """Usuário interno com um grupo do módulo (manager implica user)."""
    return env["res.users"].create({
        "name": login,
        "login": login,
        "email": email or "%s@example.test" % login,
        "groups_id": [(6, 0, [
            env.ref("base.group_user").id,
            env.ref(group_xmlid).id,
        ])],
    })


class FakeCorpo:
    """Renderizador falso de `afr_qualificacao.action_report_relatorio_corpo`.

    Espelha o template de P3 (fato fixado #3) chamando os MESMOS métodos:
    - `rel._body_blocks()` em ordem; `page_break` abre página nova;
    - para cada `rel._anexos_included()`: separador numa página só dele
      (quebra antes e depois) com `@@RQ:anexo:<code>@@` e, se
      `slot_kind == 'bloco'`, o bloco `anexo.block_id` logo depois, no
      próprio corpo;
    - `with_markers` (de `data`) liga os marcadores; `skip_markers` omite
      chaves (simula o pdfminer não achar um marcador);
    - bloco `indice` imprime `IDX <chave>=<página>` de `data["page_map"]`;
    - título começando com "LONGO" ocupa 2 páginas;
    - `grow_each_call=True`: a chamada N insere N páginas depois da 1ª
      (desloca os marcadores — índice que nunca converge).
    Como usa `rel._body_blocks()`/`_anexos_included()` do env do report, o
    filtro por contexto do fallback (Task 6) também vale aqui.
    """

    def __init__(self, grow_each_call=False, skip_markers=()):
        self.calls = []
        self.grow_each_call = grow_each_call
        self.skip_markers = set(skip_markers)

    def patch(self, env):
        fake = self

        def _render_qweb_pdf(report_self, report_ref, res_ids=None, data=None):
            data = dict(data or {})
            fake.calls.append({
                "report_ref": report_ref,
                "res_ids": list(res_ids or []),
                "data": data,
                "context": dict(report_self.env.context),
            })
            rel = report_self.env["afr.qualificacao.relatorio"].browse(res_ids)
            return fake.render(rel, data), "pdf"

        return patch.object(
            type(env["ir.actions.report"]), "_render_qweb_pdf", _render_qweb_pdf
        )

    def render(self, rel, data):
        with_markers = bool(data.get("with_markers"))
        page_map = data.get("page_map") or {}
        pages = []
        state = {"force_new": False}

        def mark(key):
            if with_markers and key not in self.skip_markers:
                return ["@@RQ:%s@@" % key]
            return []

        def emit(lines, new_page):
            if new_page or state["force_new"] or not pages:
                pages.append(list(lines))
            else:
                pages[-1].extend(lines)
            state["force_new"] = False

        def add_block(block, new_page=False):
            lines = mark("bloco:%d" % block.id)
            lines.append("BLOCO %s" % (block.title or block.block_kind))
            if block.block_kind == "indice":
                for key, num in sorted(page_map.items()):
                    lines.append("IDX %s=%s" % (key, num))
            emit(lines, new_page or block.page_break)
            if (block.title or "").startswith("LONGO"):
                pages.append(["continuacao %s" % block.title])

        for block in rel._body_blocks():
            add_block(block)
        for anexo in rel._anexos_included():
            lines = mark("anexo:%s" % anexo.code)
            lines.append("ANEXO %s: %s" % (anexo.numero, anexo.title or ""))
            emit(lines, True)
            state["force_new"] = True  # page-break-after do separador
            if (anexo.slot_kind == "bloco" and anexo.block_id
                    and anexo.block_id.included):
                add_block(anexo.block_id, new_page=True)
        if self.grow_each_call and pages:
            for extra in range(len(self.calls)):
                pages.insert(1, ["pagina extra %d" % extra])
        return make_pdf(pages or [["corpo vazio"]])


class RelatorioFixtureMixin:
    """Para classes que herdam `AfrQualificacaoTestCommon`."""

    def _make_relatorio(self, equipment=None):
        equipment = equipment or self.equip1
        os_rec = self.env["afr.qualificacao.os"].create({
            "partner_id": self.partner.id,
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 1, 17, 0, 0),
        })
        qualif = self.env["afr.qualificacao"].create({
            "name": "Qualif relatório teste",
            "equipment_id": equipment.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_rec.id,
        })
        rel = self.env["afr.qualificacao.relatorio"].create({
            "os_id": os_rec.id,
            "equipment_id": equipment.id,
            "index": 1,
        })
        # Determinístico: descarta o que P3 possa ter semeado no create.
        rel.block_ids.unlink()
        rel.anexo_ids.unlink()
        rel.aprovacao_ids.unlink()
        return rel, qualif

    def _block(self, rel, kind, title, sequence, page_break=False,
               anexo_code=False, included=True):
        return self.env["afr.relatorio.block"].create({
            "relatorio_id": rel.id,
            "block_kind": kind,
            "title": title,
            "body": "<p>%s</p>" % title,
            "sequence": sequence,
            "page_break": page_break,
            "anexo_code": anexo_code,
            "included": included,
        })

    def _attachment(self, content, name, mimetype):
        return self.env["ir.attachment"].create({
            "name": name,
            "raw": content,
            "mimetype": mimetype,
        })

    def _anexo(self, rel, code, title, sequence, slot_kind="upload",
               attachments=None, **extra):
        vals = {
            "relatorio_id": rel.id,
            "code": code,
            "title": title,
            "sequence": sequence,
            "slot_kind": slot_kind,
            "included": True,
            "attachment_ids": [(6, 0, attachments.ids if attachments else [])],
        }
        vals.update(extra)
        return self.env["afr.relatorio.anexo"].create(vals)

    def _standard_layout(self, rel):
        """Corpo de 6 páginas + anexo 'dados' (PDF 2 págs) + 'fotos' (1 PNG).

        Corpo (P3): 1 capa | 2 índice | 3 objetivo | 4 conclusão+assinaturas |
                    5 separador "ANEXO 1: Resultados" | 6 separador "ANEXO 2: Impressões".
        Final:      1 capa | 2 índice | 3 objetivo | 4 conclusão+assinaturas |
                    5 sep dados | 6-7 dados | 8 sep fotos | 9 foto  (9 páginas).
        """
        blocks = {
            "capa": self._block(rel, "capa", "Capa", 10),
            "indice": self._block(rel, "indice", "Índice", 20, page_break=True),
            "objetivo": self._block(rel, "static", "Objetivo", 30, page_break=True),
            "conclusao": self._block(rel, "static", "Conclusao", 50, page_break=True),
            "assinaturas": self._block(rel, "assinaturas", "Assinaturas", 60),
        }
        dados = self._attachment(
            make_pdf([["ANEXO-DADOS p1"], ["ANEXO-DADOS p2"]]), "dados.pdf",
            "application/pdf",
        )
        foto = self._attachment(make_png(), "impressao.png", "image/png")
        anexos = {
            "dados": self._anexo(rel, "dados", "Resultados", 10, attachments=dados),
            "fotos": self._anexo(rel, "fotos", "Impressões", 20, attachments=foto),
        }
        return blocks, anexos


def run_build_jobs(env, until=None, max_units=500, cold=False):
    """Roda EM LINHA (sem cron, sem commit) as unidades dos jobs de montagem.

    O cron não roda em testes. Chamar dentro de `FakeCorpo().patch(env)`.
    `until(job)` → True para parar antes de uma unidade (ex.: fase 'stamp').
    `cold`: cache vazio antes de cada unidade, como no cron de verdade (cada
    unidade roda num worker/transação nova) — computados não armazenados
    são recalculados no recorte que a unidade lê, não no relatório inteiro.
    """
    Job = env["afr.relatorio.build.job"].sudo().with_context(rq_build_inline=True)
    units = 0
    while units < max_units:
        job = Job.search([("state", "in", ("queued", "running"))],
                         order="last_run_at, id", limit=1)
        if not job or (until and until(job)):
            return units
        if cold:
            env.flush_all()
            env.invalidate_all()
        job._rq_run_unit()
        units += 1
    raise AssertionError("Montagem não terminou em %d unidades." % max_units)
