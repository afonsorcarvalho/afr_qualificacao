# Relatório Final — layout do PDF estilo manual (LabQuali) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PDF do Relatório Final com o visual do manual AFR-ETO (capa limpa com faixa, cabeçalho com seção atual, títulos numerados grandes, tabelas com filetes, caixas) nas cores LabQuali, sem alterar conteúdo nem pipeline.

**Architecture:** Três camadas independentes: (1) função pura `section_labels` + `cover_page_index` calculados em `_stage_body` a partir dos marcadores/layout já existentes e repassados ao carimbo pelo `st`; (2) `_overlay_page` redesenhado com modo capa e modo interno; (3) CSS/markup do corpo QWeb. Validação visual final gerando minuta real.

**Tech Stack:** Odoo 16, QWeb + wkhtmltopdf 0.12 (sem flex/grid), reportlab 3.5 (overlay), PyPDF2 1.26, pdfminer.

**Spec:** `docs/superpowers/specs/2026-09-28-relatorio-pdf-layout-manual-design.md` (ler inteira antes de cada task).

## Global Constraints

- Paleta: navy `#0A3D62`, orange `#F86A30`, slate `#5A7184`, light `#EEF2F5`, texto `#212529`, filete de linha de tabela `#C9D3DC`, aviso `#C0392B` / fundo `#FBECEC`.
- Fonte: Helvetica (reportlab) / `Arial, Helvetica, sans-serif` (QWeb). Nada de Inter.
- Paginação: `"Página %d de %d"` global; capa não tem número.
- Paperformat `paperformat_relatorio_final` inalterado (35/25/20/20 mm); constantes `MARGIN_TOP/BOTTOM/SIDE` inalteradas.
- Invariantes de marcador: `.rq-mark` (`color:#ffffff; font-size:1pt; line-height:1pt; position:absolute`) é 1º filho do container que quebra página; classes `rq-page-break`, `rq-anexo-sep`, `rq-toc-page`, atributos `data-rq-block`/`data-rq-anexo` mantidos.
- **Nunca** pôr `text-transform` (ou qualquer coisa que altere glifos) num elemento que CONTENHA um `.rq-mark` (ex.: `.rq-block`, `.rq-anexo-sep`, `.rq-page`). `MARKER_RE` é case-sensitive (`bloco|anexo` e o code do anexo): marcador em caixa alta some em silêncio (anexos vão pro fim, sumário em branco). Caixa alta só em elementos-folha de título/rótulo.
- `stamp_pdf(content, header, watermark)` continua funcionando com o dict `header` antigo (sem as chaves novas).
- Versão final do manifest: `16.0.8.5.0` (bump na Task 3).
- Commits: de dentro de `addons/afr_qualificacao` (submodule), `git add` com paths explícitos, **sem push**. Mensagens em inglês, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Testes: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http` (containers `odoo_engenapp-web-1`/`db-1` estão de pé). Suíte do relatório: `--test-tags afr_relatorio_final`.
- **Não** reiniciar nem dar `-u` no `odoo_engenapp-web-qualificacao-1` nas Tasks 1–3 (usuário pode estar usando). Só na Task 4.

## Review Focus

- Relatório sem bloco `capa` (ou capa não sendo o 1º bloco): nenhuma página vira "capa"; todas recebem cabeçalho e "Página X de Y".
- Anexo sem separador no corpo (vai para o fim, `trailing`): páginas dele recebem o label `ANEXO n`, não o da última seção do corpo.
- Título de seção longo: label no cabeçalho truncado (não invade o subtítulo); título nulo/`show_title=False`: bloco não vira seção.
- Pipeline em faixas (`page_offset`): o label/capa usam o índice FINAL da página (`offset + idx`), não o índice local da faixa.
- `st` antigo (job enfileirado antes do deploy, sem `section_labels`): carimbo não quebra — usa `""` e `cover_page_index=None`.

---

### Task 1: Seção por página e capa no pipeline

**Files:**
- Modify: `models/relatorio_pdf.py` (nova função pura após `compute_layout`; `_stage_body`; `_stage_stamp`)
- Modify: `models/relatorio_texto.py` (métodos `_rq_fmt_number` e `_report_section_entries`, perto de `_report_index_entries` ~l.347)
- Test: `tests/test_relatorio_pdf.py`

**Interfaces:**
- Produces:
  - `rp.section_labels(page_map, sections, total) -> list[str]` — `page_map` = `layout["page_map"]` (`{key: nº final 1-based}`), `sections` = `[(key, label)]` ordenado, `total` = nº de páginas finais. Retorna `total` strings, índice 0-based.
  - `rp.cover_page_index(page_map, first_block_key) -> int|None`.
  - `relatorio._rq_fmt_number(number) -> str` (`"4"`→`"04"`, `"4.1"`→`"4.1"`, `""`→`""`).
  - `relatorio._report_section_entries() -> list[(key, label)]`.
  - `st["section_labels"]` (list[str]), `st["cover_page_index"]` (int|None); `header["section_labels"]`, `header["cover_page_index"]` repassados em `_stage_stamp`.

- [ ] **Step 1: Testes que falham** — adicionar em `TestRelatorioPdfCore`:

```python
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
```

  e em `TestRelatorioBuild` (fixture: capa, índice, objetivo, conclusão+assinaturas, anexos — ver `tests/relatorio_fakes.py:256`):

```python
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
```

  (Se a FakeCorpo / fixture exigir outra forma de excluir a capa, adaptar mantendo o objetivo do teste.)

  e em `test_relatorio_model.py` (ou onde houver fixture de relatório com blocos; usar a mesma do `TestRelatorioBuild` se for mais simples) um teste de `_rq_fmt_number`:

```python
    def test_rq_fmt_number(self):
        rel = self.rel
        self.assertEqual(rel._rq_fmt_number("4"), "04")
        self.assertEqual(rel._rq_fmt_number("12"), "12")
        self.assertEqual(rel._rq_fmt_number("4.1"), "4.1")
        self.assertEqual(rel._rq_fmt_number(""), "")
```

  (Ajustar o índice `[4]` ao layout real da fixture se o separador do Anexo 1 não for a página final 5: conferir `test_build_places_annex_pages_after_their_separator`, que põe "ANEXO 1: Resultados" em `pages[4]`.)

- [ ] **Step 2: Rodar e ver falhar** — `--test-tags /afr_qualificacao:TestRelatorioPdfCore,/afr_qualificacao:TestRelatorioBuild` → FAIL (`section_labels` inexistente).

- [ ] **Step 3: Implementar**

  Em `models/relatorio_pdf.py`, após `compute_layout`:

```python
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
```

  Em `models/relatorio_texto.py`, logo após `_report_index_entries`:

```python
    def _rq_fmt_number(self, number):
        """Número de bloco para exibição: nível 1 com 2 dígitos ('4' → '04')."""
        number = number or ""
        return number.zfill(2) if number.isdigit() else number

    def _report_section_entries(self):
        """[(marcador, rótulo)] das seções do cabeçalho: blocos de nível 1
        titulados (exceto capa) e anexos incluídos, na ordem do documento."""
        self.ensure_one()
        numbers = self._block_numbering()
        entries = []
        for blk in self._body_blocks():
            if blk.parent_id or blk.block_kind == "capa" or not blk.show_title:
                continue
            title = (blk.title or blk.display_label or "").upper()
            if not title:
                continue
            number = self._rq_fmt_number(numbers.get(blk.id, ""))
            entries.append(("bloco:%d" % blk.id, ("%s %s" % (number, title)).strip()))
        for anexo in self._anexos_included():
            entries.append(("anexo:%s" % anexo.code, "ANEXO %s" % anexo.numero))
        return entries
```

  Em `_stage_body`, no `st.update(...)` final, acrescentar (antes de `phase="stamp"` ou junto):

```python
        first = relatorio._body_blocks()[:1]
        st.update(
            section_labels=section_labels(
                layout["page_map"], relatorio._report_section_entries(), len(final)),
            cover_page_index=cover_page_index(
                layout["page_map"],
                "bloco:%d" % first.id if first and first.block_kind == "capa" else None),
        )
```

  Em `_stage_stamp`, trocar o `header.update(...)` por:

```python
        header.update(
            page_offset=start, page_total=st["total"],
            section_labels=st.get("section_labels") or [],
            cover_page_index=st.get("cover_page_index"),
        )
```

  (O `page_map` mapeia bloco → página FINAL já com anexos intercalados; `len(final) == layout["total"]`.)

- [ ] **Step 4: Rodar e ver passar** — mesmas tags + `--test-tags afr_relatorio_final` inteira → PASS, sem regressão.

- [ ] **Step 5: Commit** (de `addons/afr_qualificacao`)

```bash
git add models/relatorio_pdf.py models/relatorio_texto.py tests/test_relatorio_pdf.py <arquivo do teste _rq_fmt_number>
git commit -m "feat(relatorio): map each final page to its section for the stamp header"
```

---

### Task 2: Carimbo redesenhado (capa + cabeçalho/rodapé internos)

**Files:**
- Modify: `models/relatorio_pdf.py` (`_overlay_page`, `stamp_pdf`, `_header`; constantes de cor)
- Test: `tests/test_relatorio_pdf.py`

**Interfaces:**
- Consumes: `header["section_labels"]` (list[str], índice = página final 0-based), `header["cover_page_index"]` (int|None) — Task 1.
- Produces: `header` ganha `company_name`, `code`, `subtitle`; `_overlay_page(header, page_no, total, watermark, with_qr, section="", cover=False)`.

- [ ] **Step 1: Testes que falham** — em `TestRelatorioPdfCore`:

```python
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
```

  Se `squash_keep_space` não existir, usar `" ".join(text.split())`. Ajustar `test_build_stamps_pagina_x_de_y_on_every_page` e `test_stamp_page_x_de_y_and_header_on_every_page` só no necessário: no build real a página 1 (capa) não tem "Página"/código — iterar de `start=2` sobre `pages[1:]` e afirmar à parte que a capa tem a linha de propriedade. O teste com `HEADER` puro (sem `cover_page_index`) deve continuar passando **sem alteração** (todas as páginas internas).

- [ ] **Step 2: Rodar e ver falhar** — `--test-tags /afr_qualificacao:TestRelatorioPdfCore` → FAIL.

- [ ] **Step 3: Implementar**

  Constantes (topo do módulo, após `WATERMARK_TEXT`):

```python
NAVY = (0x0A / 255.0, 0x3D / 255.0, 0x62 / 255.0)
ORANGE = (0xF8 / 255.0, 0x6A / 255.0, 0x30 / 255.0)
SLATE = (0x5A / 255.0, 0x71 / 255.0, 0x84 / 255.0)
SECTION_MAX = 45
PROPERTY_TEXT = "Este relatório só pode ser reproduzido integralmente, sem alterações."
```

  `stamp_pdf`: calcular por página `labels = header.get("section_labels") or []`, `cover_idx = header.get("cover_page_index")` e chamar
  `_overlay_page(header, number + 1, total, watermark, with_qr=..., section=labels[number] if number < len(labels) else "", cover=(cover_idx is not None and number == cover_idx))`. QR nunca na capa.

  `_overlay_page` — estrutura (manter o bloco de marca d'água e o do QR existentes):

```python
def _property_line(header):
    company = header.get("company_name") or ""
    email = header.get("footer") or ""
    who = " · ".join(p for p in (company, email) if p)
    return ("Documento emitido por %s. %s" % (who, PROPERTY_TEXT)) if who else PROPERTY_TEXT


def _truncate(c, text, font, size, width):
    if c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _overlay_page(header, page_no, total, watermark, with_qr, section="", cover=False):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    right = A4_W - MARGIN_SIDE
    if cover:
        c.setFillColorRGB(*NAVY)
        c.rect(0, A4_H - 12 * mm, A4_W, 12 * mm, stroke=0, fill=1)
        c.setFillColorRGB(*ORANGE)
        c.rect(0, A4_H - 13 * mm, A4_W, 1 * mm, stroke=0, fill=1)
        c.setStrokeColorRGB(*SLATE)
        c.setLineWidth(0.3)
        c.line(MARGIN_SIDE, 14 * mm, right, 14 * mm)
        c.setFillColorRGB(*SLATE)
        c.setFont("Helvetica", 6.5)
        c.drawString(MARGIN_SIDE, 10 * mm, _property_line(header))
    else:
        top = A4_H - 10 * mm
        logo_w = 0
        logo = header.get("logo")
        if logo:
            try:
                c.drawImage(ImageReader(io.BytesIO(logo)), MARGIN_SIDE, top - 14 * mm,
                            width=30 * mm, height=12 * mm, preserveAspectRatio=True,
                            anchor="w", mask="auto")
                logo_w = 33 * mm
            except Exception:  # logo SVG/corrompido: cabeçalho segue sem logo
                pass
        x = MARGIN_SIDE + logo_w
        c.setFillColorRGB(*NAVY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, top - 6 * mm, "RELATÓRIO DE QUALIFICAÇÃO TÉRMICA")
        c.setFillColorRGB(*SLATE)
        c.setFont("Helvetica", 7)
        c.drawString(x, top - 10 * mm, header.get("subtitle") or header.get("title") or "")
        # c.drawString(x, top - 13.5 * mm, header.get("equipment") or "")  -> ver nota
        if section:
            num, _sp, name = section.partition(" ")
            if not (num[:1].isdigit()):
                num, name = "", section
            name = _truncate(c, name, "Helvetica-Bold", 8, 60 * mm)
            c.setFont("Helvetica-Bold", 8)
            c.setFillColorRGB(*NAVY)
            c.drawRightString(right, top - 6 * mm, name)
            if num:
                c.setFillColorRGB(*ORANGE)
                c.drawRightString(right - c.stringWidth(name, "Helvetica-Bold", 8) - 2 * mm,
                                  top - 6 * mm, num)
        c.setStrokeColorRGB(*NAVY)
        c.setLineWidth(0.8)
        c.line(MARGIN_SIDE, top - 16 * mm, right, top - 16 * mm)
        # Rodapé
        c.setStrokeColorRGB(*SLATE)
        c.setLineWidth(0.3)
        c.line(MARGIN_SIDE, 20 * mm, right, 20 * mm)
        c.setFillColorRGB(*SLATE)
        c.setFont("Helvetica", 7.5)
        c.drawString(MARGIN_SIDE, 15 * mm, header.get("title") or "")
        c.drawCentredString(A4_W / 2.0, 15 * mm, "%s · %s" % (
            header.get("revision") or "", header.get("date") or ""))
        qr_size = 16 * mm
        page_label_right = right - (qr_size + 3 * mm if with_qr else 0)
        c.setFillColorRGB(*NAVY)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(page_label_right, 15 * mm, "Página %d de %d" % (page_no, total))
        c.setFillColorRGB(*SLATE)
        c.setFont("Helvetica", 6)
        c.drawString(MARGIN_SIDE, 10 * mm, _property_line(header))
        if with_qr and header.get("verify_url"):
            ...  # bloco do QR existente, inalterado (canto inferior direito, y=3 mm)
    if watermark:
        ...  # bloco existente inalterado
    c.showPage()
    c.save()
    return PdfFileReader(io.BytesIO(buf.getvalue())).getPage(0)
```

  **Subtítulo (TAG não pode sumir):** o `equipment.display_name` real tem ~100 caracteres; truncar a linha inteira cortaria o "TAG:". Regra: `_header` fornece `subtitle_prefix = "<código> · TAG: <tag>"` e `equipment_name = equipment.name`; o overlay desenha `subtitle_prefix + " · " + _truncate(equipment_name, ...)` truncando **só** o nome do equipamento para caber em `right - x - 65 * mm` (seção à direita ocupa ≤ 60 mm). Sem `subtitle_prefix` (dict `HEADER` dos testes antigos): desenhar `title` e, na linha de baixo (`top - 13.5 * mm`, 7 pt), `equipment` truncado — `HEADER["equipment"]` é curto e contém `TAG: AC-01`, que os testes procuram. Remover a linha comentada do esboço acima.

  `_header`: acrescentar

```python
            "company_name": company.name or "",
            "subtitle_prefix": "%s · TAG: %s" % (relatorio.name or "", equipment.tag or "—"),
            "equipment_name": equipment.name or "",
```

  (manter `title`, `equipment`, `revision`, `date`, `footer`, `verify_url`, `qr_page_index`). Teste extra: `_header` do relatório com `equipment.name` de 150 caracteres → página carimbada contém `"TAG: "` + tag e `"…"`.

- [ ] **Step 4: Rodar e ver passar** — `--test-tags afr_relatorio_final` → PASS. Rasterizar uma página interna e a capa geradas por um script rápido no container para olhar (opcional nesta task; obrigatório na Task 4):
  `docker exec odoo_engenapp-web-1 pdftocairo -png -r 60 /tmp/x.pdf /tmp/x`.

- [ ] **Step 5: Commit**

```bash
git add models/relatorio_pdf.py tests/test_relatorio_pdf.py
git commit -m "feat(relatorio): manual-style stamp with clean cover and section header"
```

---

### Task 3: Corpo QWeb no estilo do manual + bump de versão

**Files:**
- Modify: `reports/relatorio_corpo_templates.xml` (CSS `rq_styles`, `rq_block_capa`, `rq_block_indice`, `rq_block` título, `rq_anexo`, `rq-doc-header` de protocolo/laudo)
- Modify: `__manifest__.py` (`"version": "16.0.8.5.0"`)
- Modify: `models/relatorio_pdf.py` (`_date_label`, `_body_render_data`/`_render_body_and_markers` com `watermark` → `cover_date` no `data`)
- Test: `tests/test_relatorio_corpo_report.py`, `tests/test_relatorio_pdf.py`

**Interfaces:**
- Consumes: `doc._rq_fmt_number(number)` (Task 1).
- Produces: classes CSS `.rq-box-warn`, `.rq-box-info`, `.rq-box-label`, `blockquote` estilizado em `.rq-body`.

- [ ] **Step 1: Testes que falham** — em `test_relatorio_corpo_report.py` (reusar o helper que renderiza o HTML do corpo nos testes existentes, ex. o que produz `html` na l.59):

```python
    def test_level1_title_zero_padded_and_toc_uses_same_number(self):
        html = <html do corpo, como nos testes vizinhos>
        self.assertRegex(html, r'class="rq-title-num">0\d<')
        self.assertIn('class="rq-toc-num">0', html)

    def test_styles_define_manual_palette_and_boxes(self):
        html = <html do corpo>
        for token in ("#0A3D62", "#F86A30", ".rq-box-warn", ".rq-box-info", "blockquote"):
            self.assertIn(token, html)

    def test_cover_has_identification_table(self):
        html = <html do corpo>
        for label in ("Código", "Revisão", "Emitente", "Cliente"):
            self.assertIn(label, html)
```

  Manter verdes (sem afrouxar) os testes de marcador (`rq-mark` position:absolute, `rq-page-break`, `rq-anexo-sep`, `rq-toc-page`). Os asserts de texto `"Anexo 1: Protocolo de Qualificação Térmica"` / `"Anexo 2 — Resultados dos Valores Coletados"` podem ser atualizados para a nova forma se o texto mudar — preferir manter `Anexo N — Título` no sumário (vem de `_report_index_entries`, não mexer) e, no separador, manter a string `Anexo N: Título` em algum elemento (ex. atributo `title`/texto de apoio) só se natural; senão atualizar o assert para a nova marcação.

- [ ] **Step 2: Rodar e ver falhar** — `--test-tags /afr_qualificacao:<classe de test_relatorio_corpo_report>` → FAIL.

- [ ] **Step 3: Implementar**

  CSS (substituir o conteúdo de `rq_styles`; manter `.rq-mark` e `.rq-page-break` idênticos):

```css
.rq-page { color: #212529; font-size: 11px; line-height: 1.45; font-family: Arial, Helvetica, sans-serif; }
.rq-mark { color: #ffffff; font-size: 1pt; line-height: 1pt; position: absolute; }
.rq-page-break { page-break-before: always; }
.rq-title { margin: 18px 0 8px 0; color: #0A3D62; page-break-after: avoid; }
.rq-title-l1 { font-size: 17px; font-weight: bold; text-transform: uppercase; padding-bottom: 5px; border-bottom: 1px solid #C9D3DC; }
.rq-title-l1 .rq-title-num { color: #F86A30; font-size: 24px; margin-right: 12px; }
.rq-title-child { font-size: 12.5px; font-weight: bold; margin: 12px 0 5px 0; }
.rq-title-child .rq-title-num { margin-right: 8px; }
.rq-body { text-align: justify; }
.rq-body blockquote, .rq-box-info { margin: 8px 0; padding: 6px 10px; border-left: 3px solid #F86A30; background: #EEF2F5; }
.rq-box-info { border-left-color: #0A3D62; }
.rq-box-warn { margin: 8px 0; padding: 6px 10px; border-left: 3px solid #C0392B; background: #FBECEC; font-weight: bold; }
.rq-box-label { display: block; color: #C0392B; font-size: 9.5px; font-weight: bold; text-transform: uppercase; }
.rq-subtitle { color: #0A3D62; font-weight: bold; font-size: 12px; margin: 14px 0 5px 0; page-break-after: avoid; }
.rq-table { width: 100%; border-collapse: collapse; margin: 4px 0 12px 0; }
.rq-table th, .rq-table td { border: none; border-bottom: 0.5px solid #C9D3DC; padding: 3px 6px; vertical-align: top; text-align: left; }
.rq-table thead th { color: #0A3D62; font-weight: bold; border-bottom: 1px solid #0A3D62; }
.rq-table tbody tr th, .rq-table > tr > th { color: #5A7184; font-size: 9px; font-weight: normal; text-transform: uppercase; }
.rq-table tr { page-break-inside: avoid; }
.rq-cover { padding-top: 40px; }
.rq-cover-logo img { max-width: 60mm; max-height: 30mm; }
.rq-cover-title { font-size: 28px; font-weight: bold; color: #0A3D62; margin: 110px 0 0 0; padding-bottom: 8px; border-bottom: 2px solid #F86A30; text-transform: uppercase; }
.rq-cover-subtitle { font-size: 13px; color: #5A7184; margin: 10px 0 70px 0; }
.rq-cover-meta { width: 75%; border-top: 1px solid #0A3D62; }
.rq-cover-meta td { font-weight: bold; color: #212529; }
.rq-toc { width: 100%; border-collapse: collapse; }
.rq-toc-row td { height: 18px; padding: 0 4px; border-bottom: 1px dotted #C9D3DC; }
.rq-toc-l1 td { font-weight: bold; color: #0A3D62; }
.rq-toc-num { width: 50px; color: #F86A30; }
.rq-toc-child .rq-toc-title { padding-left: 16px; }
.rq-toc-child .rq-toc-num { color: #5A7184; }
.rq-toc-page-cell { width: 50px; text-align: right; }
.rq-anexo-sep { page-break-before: always; page-break-after: always; padding-top: 230px; }
.rq-anexo-eyebrow { color: #5A7184; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; }
.rq-anexo-num { color: #F86A30; font-size: 64px; font-weight: bold; line-height: 1; }
.rq-anexo-title { color: #0A3D62; font-size: 20px; font-weight: bold; text-transform: uppercase; margin-top: 8px; }
.rq-anexo-rule { width: 60px; border-top: 3px solid #F86A30; margin: 12px 0; }
.rq-doc-header { margin-bottom: 12px; padding-bottom: 6px; border-bottom: 2px solid #F86A30; }
.rq-doc-title { font-size: 17px; font-weight: bold; color: #0A3D62; text-transform: uppercase; }
.rq-doc-number { font-size: 11px; color: #5A7184; }
```

  `rq_block` — título:

```xml
<div t-if="block.show_title and block.block_kind != 'capa' and (block.title or blk_num)"
     t-attf-class="rq-title #{'rq-title-child' if block.parent_id else 'rq-title-l1'}">
    <t t-if="blk_num"><span class="rq-title-num" t-esc="doc._rq_fmt_number(blk_num)"/></t><span t-esc="block.title or ''"/>
</div>
```

  `rq_block_indice`: linha com `t-attf-class="rq-toc-row #{'rq-toc-child' if entry['child'] else 'rq-toc-l1'}"` e `<td class="rq-toc-num" t-esc="doc._rq_fmt_number(entry['number'])"/>` (o `span.rq-toc-page` fica igual).

  `rq_block_capa`:

```xml
<div class="rq-cover">
    <div class="rq-cover-logo" t-if="doc.company_id.logo">
        <img t-att-src="image_data_uri(doc.company_id.logo)" alt="logo"/>
    </div>
    <div class="rq-cover-title">Relatório de Qualificação Térmica</div>
    <div class="rq-cover-subtitle">
        <t t-esc="doc.equipment_id.name or ''"/><t t-if="doc.partner_id"> — <t t-esc="doc.partner_id.name"/></t>
    </div>
    <table class="rq-table rq-cover-meta">
        <tr><th style="width:38%;">Código</th><td t-esc="doc.name"/></tr>
        <tr><th>Revisão</th><td t-esc="doc.revision_label"/></tr>
        <tr><th>Data de emissão</th><td t-esc="cover_date or ''"/></tr>
        <tr><th>Equipamento</th><td t-esc="doc.equipment_id.name or ''"/></tr>
        <tr><th>Nº de série / TAG</th><td><t t-esc="doc.equipment_id.serial_number or '—'"/> / <t t-esc="doc.equipment_id.tag or '—'"/></td></tr>
        <tr><th>Cliente</th><td t-esc="doc.partner_id.name or ''"/></tr>
        <tr><th>Emitente</th><td t-esc="doc.company_id.name or ''"/></tr>
        <tr><th>Período dos ensaios</th>
            <td><t t-esc="doc._fmt_date(doc.data_inicio_ensaios)"/> a <t t-esc="doc._fmt_date(doc.data_fim_ensaios)"/></td></tr>
    </table>
</div>
```

  **Data da capa = mesma regra do carimbo, via `data` do report** (fato fixado P3 #1: variáveis do template só por `data`, nunca por contexto). Uma minuta Rev.01 feita depois da emissão Rev.00 tem de mostrar "MINUTA", não a data da Rev.00. Em `models/relatorio_pdf.py`:
  - extrair de `_header` um helper `_date_label(self, relatorio, watermark)` (watermark → `_("MINUTA")`; senão `rq_emission_date` do contexto do relatório ou `current_emissao_id.issued_at`, formatado `%d/%m/%Y` com `context_timestamp`) e usar em `_header`;
  - `_body_render_data(self, relatorio, page_map, watermark=False)` → `{"with_markers": True, "page_map": dict(page_map), "cover_date": self._date_label(relatorio, watermark)}`;
  - `_render_body_and_markers(self, relatorio, page_map, watermark=False)` repassa; `_stage_body` chama com `watermark=st["watermark"]`; conferir outros chamadores (`grep -n _render_body_and_markers`) e o caminho não-enfileirado `_build`.
  - Atualizar o assert exato de `test_body_render_data_goes_in_report_data` (acrescentar `"cover_date"`).
  - Testes novos (em `TestRelatorioBuild`/`TestRelatorioStagedBuild`, reusando fixtures de emissão existentes em `test_relatorio_pdf.py`/`test_relatorio_emissao.py`): (a) minuta de relatório que JÁ tem emissão vigente → `_body_render_data(rel, {}, watermark=True)["cover_date"] == "MINUTA"`; (b) com `rel.with_context(rq_emission_date=<datetime>)` e `watermark=False` → data formatada daquela emissão.

  (Se `image_data_uri` não estiver disponível no contexto QWeb do report, usar `'data:image/png;base64,%s' % doc.company_id.logo.decode()`.)

  `rq_anexo` separador (marcadores idênticos, primeiro filho):

```xml
<div class="rq-anexo-sep" t-att-data-rq-anexo="anexo.code"><span t-if="markers" class="rq-mark" t-esc="'@@RQ:anexo:%s@@' % anexo.code"/><span t-if="markers and sep" class="rq-mark" t-esc="'@@RQ:bloco:%s@@' % sep.id"/>
    <div class="rq-anexo-eyebrow">Anexo</div>
    <div class="rq-anexo-num" t-esc="anexo.numero"/>
    <div class="rq-anexo-title" t-esc="anexo.title or ''"/>
    <div class="rq-anexo-rule"/>
    <div t-if="sep and sep.body" class="rq-body" t-out="doc._render_block_body(sep)"/>
</div>
```

  Atenção: `tests/relatorio_fakes.py` e `test_build_places_annex_pages_after_their_separator` usam um corpo FALSO (não este template) — não dependem desta marcação. Já `test_relatorio_corpo_report.py` l.93/103 procura `"Anexo 1: Protocolo…"` no HTML real: atualizar esses asserts para a nova forma (`rq-anexo-num">1<` + título).

  Protocolo/laudo: trocar `<div class="rq-subtitle">1. Identificação do Cliente</div>` etc. — manter texto; o estilo novo já vem do CSS. Nada mais.

  Manifest: `"version": "16.0.8.5.0"`.

- [ ] **Step 4: Rodar e ver passar** — `--test-tags afr_relatorio_final` e depois a suíte do módulo `--test-tags /afr_qualificacao` → PASS (registrar nº de testes).

- [ ] **Step 5: Commit**

```bash
git add reports/relatorio_corpo_templates.xml models/relatorio_pdf.py __manifest__.py tests/test_relatorio_corpo_report.py tests/test_relatorio_pdf.py
git commit -m "feat(relatorio): manual-style body layout in LabQuali colors (16.0.8.5.0)"
```

---

### Task 4: Validação visual com minuta real + ajustes finos

**Files:**
- Modify (se preciso): `reports/relatorio_corpo_templates.xml`, `models/relatorio_pdf.py` — só ajustes de medida/cor/espaçamento.

- [ ] **Step 1:** Atualizar o módulo no db de UI: `docker exec odoo_engenapp-web-qualificacao-1 /entrypoint.sh -d qualificacao-dev -u afr_qualificacao --stop-after-init --no-http` e `docker restart odoo_engenapp-web-qualificacao-1`.
- [ ] **Step 2:** Gerar minuta do relatório id 1 pelo caminho real enfileirado: via shell (`/entrypoint.sh odoo shell -d qualificacao-dev --no-http < script.py`) chamar `env['afr.qualificacao.relatorio'].browse(1).action_gerar_minuta()` e `env.cr.commit()` (ver `models/relatorio_build_job.py:572`). **NÃO** chamar `_cron_process` no shell — o cron do web-qualificacao está vivo e dois workers pegariam o mesmo job. Fazer polling (psql no `odoo_engenapp-db-qualificacao-1` ou shell) do estado do job/`minuta_attachment_id` do relatório até concluir (alguns minutos). Copiar o `ir.attachment` novo do filestore (`/var/lib/odoo/filestore/qualificacao-dev/...`).
- [ ] **Step 3:** Rasterizar com `pdftocairo -png -r 70` páginas: capa (1), sumário (2), texto (3–5), protocolo com tabelas, separador de anexo, página de gráfico, assinaturas. Comparar com `.superpowers/handoff-2026-09-28/man-01.png`, `man-02.png`, `big-08.png`. Checar: faixa da capa, nada sobreposto entre cabeçalho e corpo (margem 35 mm), seção correta no cabeçalho de cada página, rodapé legível, pontilhado/numeração do sumário batendo com as páginas, marca d'água.
- [ ] **Step 4:** Ajustar medidas se necessário; se tocar código, rodar `--test-tags afr_relatorio_final` (web-1) de novo.
- [ ] **Step 5:** Commit dos ajustes (se houver) — `fix(relatorio): tune manual-style layout spacing`. Deixar em `scratchpad` a montagem PNG final para o orquestrador mostrar ao usuário.
