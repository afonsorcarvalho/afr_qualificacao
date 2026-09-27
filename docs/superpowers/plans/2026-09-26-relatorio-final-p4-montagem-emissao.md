# Relatório Final — P4: Montagem do PDF, minuta, emissão, revisão, verificação pública, portal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Emenda "Fila + etapas" (2026-09-26):** a montagem do PDF roda num job (`afr.relatorio.build.job` + cron, pipeline `_stage_init`/`_stage_run`); ver `.superpowers/sdd/2026-09-26-relatorio-final-p4-montagem-emissao/amendment-async-build.md` (fora do versionamento). O **Task 6 não foi executado** (o spike do Task 1 passou) e o **Task 8 foi substituído pelos Tasks 8A/8B/8R** da emenda; o texto original desses tasks fica como histórico.

**Goal:** Transformar o `afr.qualificacao.relatorio` (P1–P3) em um PDF único e numerado (corpo QWeb + anexos intercalados + carimbo "Página X de Y" + QR), com minuta com marca d'água, emissão imutável com SHA-256 e token, revisão Rev.N+1, página pública de verificação e aprovação do cliente pelo portal.

**Architecture:** Um AbstractModel `afr.relatorio.pdf` concentra a montagem: renderiza o corpo (`action_report_relatorio_corpo` de P3) com marcadores invisíveis, localiza as páginas com pdfminer, intercala as páginas de `afr.relatorio.anexo._resolve_files()` normalizadas para a área útil A4, re-renderiza o corpo com `page_map` para o índice e carimba cabeçalho/rodapé/QR/marca d'água com reportlab. A emissão (`afr.relatorio.emissao`) é imutável como os campos `_CERTIFICATE_FIELDS` de `afr.qualificacao`; edição editorial em `draft` zera aprovações internas e é bloqueada fora de `draft`. Controllers públicos seguem o padrão de `controllers/main.py` (lógica em funções de módulo testáveis sem HTTP).

**Tech Stack:** Odoo 16.0, PyPDF2 1.26.0 (API antiga), reportlab 3.5.59 (`reportlab.graphics.barcode.qr`), pdfminer.six 20200726, Pillow 8.1.2, wkhtmltopdf 0.12.6.1 (patched qt), QWeb, `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-09-26-relatorio-final-qualificacao-design.md` (§4.5, §4.6, §4.7, §6, §8, §12). Índice + contrato: `docs/superpowers/plans/2026-09-26-relatorio-final-00-indice.md` (nomes **vinculantes**).

## Global Constraints

- Odoo **16.0**. `afr_qualificacao` é git submodule em `addons/afr_qualificacao/`; trabalhar na branch `feat/relatorio-final` **dentro do submodule** (criada em P1).
- Commits sempre de dentro de `addons/afr_qualificacao/`, via agente `git-commit-push` (haiku), paths relativos ao submodule. **Não** fazer push nem bump do pointer no monorepo sem o usuário pedir. Mensagens em inglês, Conventional Commits.
- Testes via agente `test-runner` (sonnet) quando rodado pelo orquestrador. Comando base: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http` (`-u` obrigatório quando tocar XML; `--no-http` obrigatório). Falhas pré-existentes conhecidas: `TestResourcePlan.test_fleet_single_logger_two_temp_standards`, `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`, `TestProposalReport.test_render_schedule_block`.
- Novos testes que precisam de SO/OS/equipamento herdam de `tests/common.py::AfrQualificacaoTestCommon`; registrar cada novo arquivo de teste em `tests/__init__.py`.
- Todo novo model: entrada em `models/__init__.py`, ACL em `security/ir.model.access.csv` (technician: read; user: read/write/create; manager: full), salvo indicação contrária (aqui: `afr.relatorio.emissao` é somente leitura para todos — gravação só interna via `sudo()`).
- Grupos: `afr_qualificacao.group_afr_qualificacao_technician`, `..._user`, `..._manager`.
- **Nunca** usar nomes de clientes, pessoas ou números de certificados reais de `dados_sensiveis/` em código, seeds, testes ou docs. Usar "Cliente Teste", "Eng. Responsável".
- `engc_os` está **congelado**: não editar nada em `engenapp/engc_os/`.
- PWA (`pwa/`) **não muda**.
- Bibliotecas: `PyPDF2==1.26.0` (`PdfFileReader`, `PdfFileWriter`, `getPage`, `mergePage`, `mergeTransformedPage`, `addPage`, `getNumPages`, `isEncrypted`, `decrypt`), `reportlab 3.5`, `pdfminer.six 20200726`; `odoo.tools.pdf.merge_pdf`, `odoo.tools.pdf.PdfFileReader/PdfFileWriter` existem. **Não adicionar dependência pip.**
- Manifest ao final de P4: `"version": "16.0.8.3.0"`. P4 não cria seed via hook (o `mail.template` é XML `noupdate`), logo **não** há script de migração.
- Textos de UI em pt-BR.
- Em testes, `ir.actions.report._render_qweb_pdf` devolve **HTML** (modo teste) salvo `force_report_rendering=True`; por isso **todo** teste que monta PDF faz patch de `_render_qweb_pdf` com o renderizador falso de `tests/relatorio_fakes.py` (não depende de wkhtmltopdf). HttpCase **não** é usado (os testes rodam com `--no-http`): controllers são testados pelas funções de módulo.
- Fatos de biblioteca confirmados no container `odoo_engenapp-web-qualificacao-1` (2026-09-26): pdfminer extrai texto branco 1pt por página (reportlab e wkhtmltopdf 0.12.6.1 direto); PDF com só senha de dono abre com `decrypt("") == 1`; PDF com senha de usuário dá `PdfReadError: File has not been decrypted` em `getNumPages()`; lixo dá `PdfReadError: Could not read malformed PDF file`; `mergeTransformedPage` sobre `PageObject.createBlankPage(None, A4)` normaliza páginas paisagem e com `/Rotate` 90/180/270 (orientação conferida por bbox); marca d'água girada 45° sai do pdfminer com espaços entre letras (comparar com `re.sub(r"\s", "", texto)`).

## Contrato consumido (P1–P3)

Consumido exatamente como no índice: `afr.qualificacao.relatorio` (`name`, `os_id`, `equipment_id`, `partner_id`, `company_id`, `qualificacao_ids`, `state`, `revision`, `revision_label`, `data_*`, `amb_*`, `tolerancia_acima`, `criterio_f0_fator`, `checklist_ids`, `indicador_ids`, `leitura_ib_ids`, `proxima_qualificacao`, `template_id`, `block_ids`, `anexo_ids`, `aprovacao_ids`, `_render_block_body(block)`, `_afr_certificate_files(roles)`, `_afr_malha_certificate_files()`), `afr.relatorio.block`, `afr.relatorio.anexo`, `afr.relatorio.aprovacao`, `afr.relatorio.checklist`, `afr.relatorio.indicador`, `afr.relatorio.leitura.ib`, `afr.relatorio.sensor.pos`, `afr.qualificacao.cycle.janela_inicio/janela_fim/sensor_pos_ids`, report `afr_qualificacao.action_report_relatorio_corpo`, paperformat `paperformat_relatorio_final` (A4, top 35 mm, bottom 25 mm).

**Fatos fixados pelo plano P3 que P4 segue** (índice, "Fatos fixados pelo plano P3"; plano `2026-09-26-relatorio-final-p3-template-blocos.md`, Task 7):
1. `page_map` e `with_markers` vão como chaves do dict **`data`** do report: `_render_qweb_pdf("afr_qualificacao.action_report_relatorio_corpo", res_ids=rel.ids, data={"page_map": {...}, "with_markers": True})` — nunca por `env.context` (`_get_rendering_context` copia `data` para as variáveis do template).
2. `_apply_template()` **não** roda no `create()` nem em `action_generate_relatorios()`. Testes de P4 montam blocos/anexos à mão (fixture) ou chamam `rel._apply_template()` explicitamente.
3. O corpo renderiza primeiro `rel._body_blocks()` (blocos incluídos **sem** `anexo_code`) e depois, para cada `rel._anexos_included()` (ordem de `anexo_ids`): o separador `<div class="rq-anexo-sep">` (quebra de página antes **e** depois) com `@@RQ:anexo:<code>@@` (+ `@@RQ:bloco:<sep.id>@@` do `_anexo_separator_block(code)`, se houver) e, se `slot_kind == 'bloco'`, o bloco `anexo.block_id` logo em seguida **dentro do corpo**. Logo: anexo `bloco` não tem arquivo para intercalar (`_resolve_files()` devolve `[]`), e marcadores esperados = `_body_blocks()` + `_anexos_included()` (+ separadores e blocos de anexo `bloco`).
4. Token `anexo` é callable (`{{ anexo('micro') }}`) — P4 não depende disso.
5. `proxima_qualificacao` (P1) é **stored**, `compute="_compute_proxima_qualificacao"`, `@api.depends("data_fim_ensaios")`. P4 sobrescreve o mesmo método acrescentando `@api.depends("current_emissao_id.issued_at")` (o Odoo 16 acumula `depends` pela MRO) e usa a data de emissão + 12 meses quando houver emissão vigente.
6. `afr.relatorio.aprovacao.create` (P3) gera `access_token` uuid4 para `papel='cliente'`; `_apply_template` (P3) cria o executor já com `approved_at` (assinatura do PWA).
7. Form do relatório (P1): `afr_qualificacao.view_afr_qualificacao_relatorio_form`, `<header>` só com `<field name="state" widget="statusbar"/>`; P3 acrescenta `page_texto`, `page_anexos`, `page_aprovacoes`.

**P4 não pede nenhuma mudança no template de P3.** O fallback (Task 6), se precisar, filtra o que o template percorre por contexto (`rq_chunk_blocks`/`rq_chunk_anexos`) sobrescrevendo `_body_blocks()`/`_anexos_included()` — o template chama esses métodos em `doc`, que herda o contexto do `ir.actions.report` que renderiza.

## P4 produz (nomes vinculantes para P5)

- `afr.relatorio.anexo._resolve_files()` → `list[tuple[bytes, str, str]]` (só arquivos utilizáveis; `slot_kind='bloco'` → `[]`, o conteúdo está no corpo); `afr.relatorio.anexo._check_files()` → `list[str]`, cada item é `PROBLEM_EMPTY` (`"Nenhum arquivo encontrado para este anexo."`) **ou** `"<legenda do arquivo>: <motivo>"` (motivos: `arquivo vazio`, `PDF protegido por senha`, `PDF com criptografia não suportada`, `PDF sem páginas`, `PDF ilegível (<erro>)`, `imagem ilegível (<erro>)`, `tipo de arquivo não suportado (<mimetype>)`). Sugestão para P5: `problem == PROBLEM_EMPTY` → `ANEXO_VAZIO`, qualquer outro → `ANEXO_ILEGIVEL` (o plano P5 classifica "vazio" por `_resolve_files()` vazio; as duas regras só divergem quando **todos** os arquivos de um anexo são ilegíveis — P5 diria VAZIO, esta diria ILEGÍVEL; qualquer uma bloqueia a emissão).
- `afr.relatorio.pdf`: `build(relatorio, watermark=False)` → `bytes` (entrada síncrona — testes e fixtures; `action_emitir` usa o job, que roda o mesmo pipeline em etapas; P5 usa `FakeCorpo` + `run_build_jobs`); `_build(relatorio, watermark=False)` → `tuple[bytes, list[str]]` (avisos: arquivo ignorado, marcador de anexo não achado, índice não estabilizou; usado pela minuta); `_image_to_pdf(content, caption)` → `bytes`; `_find_markers(pdf_bytes)` → `dict[str, int]` (0-based); `_stamp(pdf_bytes, header, watermark)` → `bytes`; `_render_report(relatorio, data)` → `bytes` (único chamador de `ir.actions.report._render_qweb_pdf`, o que os testes de P4 mockam); `_render_body_and_markers(relatorio, page_map)` → `tuple[bytes, dict[str, int]]`.
- `afr.relatorio.emissao` (imutável). Em `afr.qualificacao.relatorio`: `emissao_ids`, `current_emissao_id`, `minuta_attachment_id`, `verify_url`; `action_gerar_minuta()` (enfileira; devolve `display_notification`), `action_aprovar_interno()` (aprova **todas** as linhas elaborador/emissor pendentes cujo `user_id == env.user`, numa chamada), `action_emitir()` (gate síncrono no clique; falho ⇒ **`UserError`** "Não é possível emitir o relatório <name>:\n- …"; senão enfileira e devolve `display_notification`), `action_revisar()`, `action_enviar_aprovacao_cliente()`; `_check_emission_gate()` → `list[str]`; `_scan_snapshot()` → `str` (`"[]"`); `_invalidate_internal_approvals()` (disparado por `write` do relatório nos campos `equipment_id, template_id, data_inicio_ensaios, data_fim_ensaios, amb_temperatura, amb_umidade, tolerancia_acima, criterio_f0_fator, block_ids, anexo_ids, checklist_ids, indicador_ids, leitura_ib_ids` e por create/write/unlink de `afr.relatorio.block/anexo/checklist/indicador/leitura.ib/sensor.pos` e write de `afr.qualificacao.cycle.janela_inicio/janela_fim/sensor_pos_ids`; **não** por `achado_ids`, `minuta_attachment_id`, chatter nem aprovações); `_check_editable()`; `_update_client_approval_state()`.
- `afr.relatorio.aprovacao._portal_url()` → `str`; `afr.relatorio.aprovacao._portal_approve(nome, ip)` → `bool`.
- Controllers `/qualificacao/relatorio/verify/<token>` e `/my/relatorio/<int:aprovacao_id>` (+ `/pdf`, `/aprovar`); funções de módulo `controllers/relatorio.py::_relatorio_verify_values(env, token)` e `_portal_aprovacao(env, aprovacao_id, access_token)`.
- Página `name="page_revisoes"` no form do relatório; botões no `//header`.

**Desvio consciente do pedido original:** o QR **não** é inserido por xpath no bloco `assinaturas` de P3 (`afr_qualificacao.rq_block_assinaturas`). Motivos: (1) o QR via `/report/barcode` obriga o wkhtmltopdf a buscar URL do próprio servidor (frágil com `web.base.url`/`report.url`); (2) com o QR no carimbo, o corpo renderizado é idêntico na minuta e na emissão, então a paginação não muda entre as duas; (3) é testável com o render falso. O QR é **carimbado** com reportlab no rodapé da página onde cai o marcador do bloco `assinaturas` (ou na última página do corpo, se não houver esse bloco) — exatamente o que a spec §8 descreve ("QR no rodapé da última página do corpo"). `verify_url` continua um compute com `@api.depends_context("rq_emission_token")`, então um QR em QWeb pode ser acrescentado depois sem mudar o modelo.

## Review Focus

1. Páginas de gráfico do validador em paisagem ou com `/Rotate` (Anexos 2/3) — devem sair em pé na orientação de leitura, dentro da área útil, sem o carimbo cobrir conteúdo → testes `test_fit_page_rotated_*` (Task 2) e `test_build_landscape_and_rotated_annex_pages_become_a4_portrait` (Task 5).
2. Certificado RBC de terceiro "criptografado" só com senha de dono (comum) — deve ser aceito; com senha de usuário ou corrompido — deve virar problema em `_check_files()` e ser pulado na montagem, nunca exceção → testes do Task 3.
3. Marcador de separador que o pdfminer não acha no corpo real (fonte/CSS do wkhtmltopdf) — as páginas do anexo vão para o fim do documento com aviso, nunca somem em silêncio → `test_build_annex_whose_marker_is_missing_goes_to_end_with_warning` (Task 5).
4. Edição de bloco/anexo/checklist/indicador/leitura depois de emitido — deve ser recusada; em `draft`, deve zerar as aprovações internas (inclusive quando a edição é feita direto no model filho, não pelo form do relatório) → testes do Task 7.
5. Reemissão: aprovações do cliente da Rev.00 não valem para a Rev.01; o token antigo passa a verificar como "substituída" só quando a nova é emitida; PDF armazenado alterado aparece como "adulterado" → testes dos Tasks 8 e 9.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `models/relatorio_pdf.py` (novo) | Funções puras de PDF (marcadores, normalização A4, imagem→PDF, carimbo) + AbstractModel `afr.relatorio.pdf` (render, montagem, `build`). |
| `models/relatorio_anexo_files.py` (novo) | `_inherit` de `afr.relatorio.anexo`: `_raw_files`, `_resolve_files`, `_check_files`, `PROBLEM_EMPTY`. |
| `models/relatorio_emissao.py` (novo) | Model `afr.relatorio.emissao` (imutável). |
| `models/relatorio_editorial.py` (novo) | Mixin `afr.relatorio.editorial.mixin` + ganchos em blocos/anexos/checklist/indicador/leitura/sensor/ciclo; guarda de campos de aprovação. |
| `models/relatorio_emissao_flow.py` (novo) | `_inherit` de `afr.qualificacao.relatorio`: campos de emissão, `verify_url`, guardas de `write`, invalidação, gate, minuta, emitir, revisar, aprovar, envio ao cliente, `proxima_qualificacao`; `_inherit` de `afr.relatorio.aprovacao`: portal. |
| `controllers/relatorio.py` (novo) | Verificação pública + portal de aprovação. |
| `views/relatorio_emissao_views.xml` (novo) | Botões no header, página `page_revisoes`, tree/form de emissão. |
| `views/relatorio_public_templates.xml` (novo) | Página pública de verificação + página do portal. |
| `data/mail_template_relatorio_aprovacao.xml` (novo) | E-mail com o link do portal. |
| `tests/relatorio_fakes.py` (novo, não registrado em `__init__`) | PDFs sintéticos, renderizador falso do corpo, fixture de relatório. |
| `tests/test_relatorio_pdf.py`, `tests/test_relatorio_emissao.py` (novos) | Testes. |
| `models/__init__.py`, `controllers/__init__.py`, `tests/__init__.py`, `security/ir.model.access.csv`, `__manifest__.py` | Registro. |

---

### Task 1: Spike (timebox 30 min) — marcadores do corpo real extraídos por página

Objetivo: decidir entre o caminho **(a) marcadores** (Tasks 2–5, 7–10) e **(b) fallback por pedaços** (Task 6 adicional). Nada é commitado neste task além do registro da decisão neste plano.

**Files:**
- Create (temporário, fora do repo): `/tmp/rq_spike.py` no container

**Interfaces:**
- Consumes: `afr_qualificacao.action_report_relatorio_corpo` (P3), `afr.relatorio.template` com `code` `RQT-HOSP` (P3), `relatorio._apply_template()`, `_body_blocks()`, `_anexos_included()`, `_anexo_separator_block(code)` (P3).
- Produces: decisão registrada no checkbox do Step 4.

Pré-validação já feita no container `odoo_engenapp-web-qualificacao-1`: wkhtmltopdf 0.12.6.1 puro, HTML com `<span class="rq-mark" style="color:#fff;font-size:1pt">@@RQ:...@@</span>` e `page-break-before`, extraído com `pdfminer.high_level.extract_pages` → marcadores achados nas páginas certas (0, 3, 4). O spike só confirma que o **template real de P3** (com CSS do layout, fontes, `t-out` de HTML) se comporta igual.

- [ ] **Step 1: Escrever o script do spike**

```python
# /tmp/rq_spike.py — rodar com: /entrypoint.sh odoo shell -d odoo_ecm_test --no-http < /tmp/rq_spike.py
import io
import re

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

MARK = re.compile(r"@@RQ:(bloco|anexo):([A-Za-z0-9_\-]+)@@")
REPORT = "afr_qualificacao.action_report_relatorio_corpo"


def markers(pdf):
    found = {}
    n = 0
    for idx, layout in enumerate(extract_pages(io.BytesIO(pdf))):
        n = idx + 1
        text = "".join(el.get_text() for el in layout if isinstance(el, LTTextContainer))
        for kind, key in MARK.findall(text):
            found.setdefault("%s:%s" % (kind, key), idx)
    return found, n


def render(rel, data):
    pdf, fmt = env["ir.actions.report"].with_context(
        force_report_rendering=True
    )._render_qweb_pdf(REPORT, res_ids=rel.ids, data=data)
    assert fmt == "pdf", "render devolveu %s (esperado pdf)" % fmt
    return pdf


# Fixture mínima (tudo desfeito no rollback final)
partner = env["res.partner"].create({"name": "Cliente Teste Spike"})
cat = env["engc.equipment.category"].create({"name": "Spike-Autoclave"})
means = env["engc.equipment.means.of.aquisition"].search([], limit=1) or \
    env["engc.equipment.means.of.aquisition"].create({"name": "Compra"})
loc = env["engc.equipment.location"].search([], limit=1) or \
    env["engc.equipment.location"].create({"name": "Sala S"})
marca = env["engc.equipment.marca"].search([], limit=1) or \
    env["engc.equipment.marca"].create({"name": "MarcaS"})
equip = env["engc.equipment"].create({
    "client_id": partner.id, "category_id": cat.id, "model": "SpikeModel",
    "serial_number": "SPK-001", "means_of_aquisition_id": means.id,
    "location_id": loc.id, "marca_id": marca.id, "tag": "AC-SPK",
})
os_rec = env["afr.qualificacao.os"].create({
    "partner_id": partner.id,
    "date_planned_start": "2026-07-01 08:00:00",
    "date_planned_end": "2026-07-01 17:00:00",
})
env["afr.qualificacao"].create({
    "name": "Qualif Spike", "equipment_id": equip.id,
    "qualification_type": "installation", "os_id": os_rec.id,
})
rel = env["afr.qualificacao.relatorio"].create({
    "os_id": os_rec.id, "equipment_id": equip.id, "index": 1,
})
tmpl = env["afr.relatorio.template"].search([("code", "=", "RQT-HOSP")], limit=1)
assert tmpl, "template RQT-HOSP (seed de P3) não encontrado"
rel.template_id = tmpl
rel._apply_template()  # P3: não roda no create
# Marcadores esperados = o que o template de P3 percorre (fato fixado P3 #3)
expected = {"bloco:%d" % b.id for b in rel._body_blocks()}
for anexo in rel._anexos_included():
    expected.add("anexo:%s" % anexo.code)
    sep = rel._anexo_separator_block(anexo.code)
    if sep:
        expected.add("bloco:%d" % sep.id)
    if anexo.slot_kind == "bloco" and anexo.block_id and anexo.block_id.included:
        expected.add("bloco:%d" % anexo.block_id.id)

pdf1 = render(rel, {"with_markers": True, "page_map": {}})
found1, n1 = markers(pdf1)
pdf2 = render(rel, {"with_markers": True, "page_map": {k: v + 1 for k, v in found1.items()}})
found2, n2 = markers(pdf2)
print("PAGES pass1=%s pass2=%s" % (n1, n2))
print("MISSING", sorted(expected - set(found1)))
print("STABLE", found1 == found2 and n1 == n2)
print("MAP", sorted(found1.items(), key=lambda kv: kv[1]))
# Cada separador de anexo precisa estar numa página só dele (quebra antes e
# depois): a página do marcador "anexo:" não pode ter outro marcador de bloco
# de texto.
body_keys = {"bloco:%d" % b.id for b in rel._body_blocks()}
by_page = {}
for key, page in found1.items():
    by_page.setdefault(page, set()).add(key)
print("SEPARATORS_ALONE", all(
    not (by_page[page] & body_keys)
    for key, page in found1.items() if key.startswith("anexo:")
))

open("/tmp/rq_spike_corpo.pdf", "wb").write(pdf1)
env.cr.rollback()
```

- [ ] **Step 2: Rodar o spike**

```bash
docker cp /tmp/rq_spike.py odoo_engenapp-web-1:/tmp/rq_spike.py   # escrever o arquivo do Step 1 em /tmp/rq_spike.py no host antes
docker exec odoo_engenapp-web-1 bash -c '/entrypoint.sh odoo shell -d odoo_ecm_test --no-http < /tmp/rq_spike.py' 2>&1 | grep -E "PAGES|MISSING|STABLE|MAP|ALONE|Error|assert"
docker cp odoo_engenapp-web-1:/tmp/rq_spike_corpo.pdf /tmp/rq_spike_corpo.pdf
```

Expected (caminho a): `MISSING []`, `STABLE True`, `SEPARATORS_ALONE True`. O shell **não** está em modo teste, então `_render_qweb_pdf` chama o wkhtmltopdf de verdade. Se `web.base.url` do banco apontar para uma URL inalcançável de dentro do container, o render demora (timeouts de CSS) mas funciona — não é falha do spike.

- [ ] **Step 3: Inspecionar visualmente**

Abrir `/tmp/rq_spike_corpo.pdf` (ex.: `Read` do PDF ou `pdf-viewer`) e conferir: nenhum `@@RQ:` visível; nenhuma linha em branco extra no início dos blocos causada pelo `span` (o `span` precisa estar dentro do primeiro elemento do bloco, `line-height:1pt`). Se aparecer, ajustar o CSS do `.rq-mark` no template de P3 (`color:#fff; font-size:1pt; line-height:1pt; position:absolute;`) e rodar de novo.

- [ ] **Step 4: Registrar a decisão**

- Se só `SEPARATORS_ALONE` for `False`: é CSS do template de P3 (`.rq-anexo-sep` sem `page-break-before/after`) — corrigir lá (commit `fix(relatorio): annex separator on its own page`) e rodar o spike de novo; não é motivo para o fallback.
- Se `MISSING == []` e `STABLE True` → **caminho (a)**: marcar aqui `[x] marcadores OK` e **pular o Task 6**.
- Senão → **caminho (b)**: marcar `[x] fallback` e executar o Task 6 logo depois do Task 5.

Decisão: `[ ] marcadores OK` / `[ ] fallback`

---

### Task 2: Núcleo de PDF — marcadores, normalização A4, imagem→PDF, carimbo

**Files:**
- Create: `models/relatorio_pdf.py`
- Create: `tests/relatorio_fakes.py`
- Create: `tests/test_relatorio_pdf.py`
- Modify: `models/__init__.py` (append `from . import relatorio_pdf`)
- Modify: `tests/__init__.py` (append `from . import test_relatorio_pdf`)

**Interfaces:**
- Consumes: nada de P1–P3 (funções puras); `tests/relatorio_fakes.py` já traz a fixture, `make_user` e o renderizador falso usados nos Tasks 3–9 (dependem de P1/P3, mas só são exercitados a partir do Task 3).
- Produces:
  - Módulo `odoo.addons.afr_qualificacao.models.relatorio_pdf`: `MARKER_RE`, `A4_W`, `A4_H`, `MARGIN_TOP`, `MARGIN_BOTTOM`, `MARGIN_SIDE`, `USABLE` (x, y, w, h), `WATERMARK_TEXT`, `IMAGE_MIMETYPES`, `pdf_bytes(writer) -> bytes`, `open_pdf(content) -> PdfFileReader` (levanta `ValueError(motivo)`), `find_markers(content) -> dict[str, int]`, `fit_page_to_usable(page) -> PageObject`, `image_to_pdf(content, caption) -> bytes`, `stamp_pdf(content, header, watermark) -> bytes`.
  - `afr.relatorio.pdf._find_markers(pdf_content)`, `._image_to_pdf(content, caption)`, `._stamp(pdf_content, header, watermark)`.
  - `header` dict: `logo` (bytes|None), `title`, `equipment`, `revision`, `date`, `footer`, `verify_url` (str|False), `qr_page_index` (int|None).
  - `tests/relatorio_fakes.py`: `make_pdf(pages, size=A4, rotate=0)`, `encrypt_pdf(data, user_pw="", owner_pw="dono")`, `make_png(w, h, color)`, `pdf_pages_text(data) -> list[str]`, `squash(text)`, `make_user(env, login, group_xmlid, email=None)`, `FakeCorpo(grow_each_call=False, skip_markers=())` com `.patch(env)` e `.calls` (cada item: `report_ref`, `res_ids`, `data`, `context`), `RelatorioFixtureMixin` com `_make_relatorio()`, `_block(...)`, `_anexo(...)`, `_attachment(...)`, `_standard_layout(rel)`.

- [ ] **Step 1: Criar o apoio de testes `tests/relatorio_fakes.py`**

```python
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
      (quebra antes e depois) com `@@RQ:anexo:<code>@@` (+ `@@RQ:bloco:<id>@@`
      do `_anexo_separator_block(code)`) e, se `slot_kind == 'bloco'`, o bloco
      `anexo.block_id` logo depois, no próprio corpo;
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
            sep = rel._anexo_separator_block(anexo.code)
            lines = mark("anexo:%s" % anexo.code)
            if sep:
                lines += mark("bloco:%d" % sep.id)
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
```

- [ ] **Step 2: Escrever os testes que falham (`tests/test_relatorio_pdf.py`)**

```python
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
```

Registrar: em `tests/__init__.py`, acrescentar ao fim:

```python

# Relatório Final — P4 (montagem do PDF, emissão, verificação, portal)
from . import test_relatorio_pdf
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioPdfCore --stop-after-init --no-http`
Expected: FAIL/ERROR — `ImportError: cannot import name 'relatorio_pdf'` (o módulo ainda não existe).

- [ ] **Step 4: Implementar `models/relatorio_pdf.py` (núcleo)**

```python
"""Montagem do PDF do Relatório Final (spec §6).

Funções puras (testáveis sem registry) + AbstractModel `afr.relatorio.pdf`,
que as expõe e orquestra: render do corpo com marcadores, intercalação dos
anexos, re-render com `page_map` e carimbo (cabeçalho, rodapé, QR, marca
d'água). Bibliotecas: PyPDF2 1.26 (API antiga), reportlab 3.5, pdfminer.six.
"""
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

from odoo import api, models
from odoo.tools.pdf import PdfFileReader, PdfFileWriter

MARKER_RE = re.compile(r"@@RQ:(bloco|anexo):([A-Za-z0-9_\-]+)@@")
A4_W, A4_H = A4
# Mesmas margens do paperformat_relatorio_final (P3): o carimbo vive nelas.
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
```

> Tasks 3, 5 e 6 acrescentam métodos a esta mesma classe e ampliam a linha `from odoo import ...` do topo.

Registrar em `models/__init__.py` (fim do arquivo):

```python
from . import relatorio_pdf
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioPdfCore --stop-after-init --no-http`
Expected: PASS (13 testes, 0 falhas).

- [ ] **Step 6: Commit**

Via agente `git-commit-push`, cwd `addons/afr_qualificacao`:
```bash
git add models/relatorio_pdf.py models/__init__.py tests/relatorio_fakes.py tests/test_relatorio_pdf.py tests/__init__.py
git commit -m "feat(relatorio): PDF core — markers, A4 fit, image page, stamp"
```

---

### Task 3: Arquivos dos anexos — `_resolve_files()` / `_check_files()` + render do corpo

**Files:**
- Create: `models/relatorio_anexo_files.py`
- Modify: `models/relatorio_pdf.py` (acrescentar `REPORT_CORPO`, `file_problem`, `_render_report`)
- Modify: `models/__init__.py` (append `from . import relatorio_anexo_files`)
- Test: `tests/test_relatorio_pdf.py` (nova classe `TestRelatorioAnexoFiles`)

**Interfaces:**
- Consumes: `afr.relatorio.anexo` (P3: `relatorio_id`, `slot_kind`, `collect_sections`, `cert_roles`, `block_id`, `attachment_ids`, `title`); `relatorio._afr_certificate_files(roles)` e `relatorio._afr_malha_certificate_files()` (P2, tuplas `(bytes, mimetype, legenda)`); `afr.qualificacao.collect.item` (`os_id`, `equipment_id`, `qualif_id`, `docx_section`, `state`, `file`, `mimetype`, `cycle_id`, `sequence`); `afr.qualificacao.cycle._order`.
- Produces:
  - `models/relatorio_anexo_files.py::PROBLEM_EMPTY` (str), `ALL_CERT_ROLES = ("antes", "depois", "externo")`; `models/relatorio_pdf.py::file_problem(content, mimetype=None) -> str | None` (guess_mimetype usa python-magic no container: `%PDF…` → `application/pdf`, texto → `text/plain`).
  - `afr.relatorio.anexo._raw_files() -> list[tuple[bytes, str, str]]`, `._resolve_files() -> list[tuple[bytes, str, str]]` (mimetype normalizado pelo conteúdo), `._check_files() -> list[str]`, `._collect_items() -> recordset`, `._cert_roles_list() -> list[str]`.
  - `afr.relatorio.pdf._render_report(relatorio, data: dict) -> bytes`; constante `REPORT_CORPO = "afr_qualificacao.action_report_relatorio_corpo"`.
  - Regras: `slot_kind='bloco'` não tem arquivo (o conteúdo sai no corpo, fato P3 #3): `_resolve_files()` → `[]`, `_check_files()` → `[]` se `block_id` incluído, senão `[PROBLEM_EMPTY]`; `attachment_ids` preenchido **substitui** a resolução automática (override manual) para os demais `slot_kind`; `cert_roles` vazio = todos os papéis; `collect_sections` vazio = nenhum item; itens de coleta ordenados por ciclo (itens sem ciclo primeiro, depois ciclos na `_order` do model de ciclo) e depois `sequence`, `id`.

- [ ] **Step 1: Escrever os testes que falham** — acrescentar a `tests/test_relatorio_pdf.py`:

Imports adicionais no topo do arquivo:

```python
import base64
from unittest.mock import patch

from odoo.addons.afr_qualificacao.models.relatorio_anexo_files import PROBLEM_EMPTY

from .common import AfrQualificacaoTestCommon
from .relatorio_fakes import FakeCorpo, RelatorioFixtureMixin
```

Nova classe:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioAnexoFiles --stop-after-init --no-http`
Expected: ERROR — `ModuleNotFoundError: ... relatorio_anexo_files`.

- [ ] **Step 3: Acrescentar o render do corpo em `models/relatorio_pdf.py`**

No topo, trocar `from odoo import api, models` por:

```python
from odoo import _, api, models
from odoo.exceptions import UserError
```

e, junto dos outros imports de terceiros:

```python
from odoo.tools.mimetypes import guess_mimetype
```

Constante e função pura de módulo (abaixo de `IMAGE_MIMETYPES`; `file_problem` mora aqui, e não em `relatorio_anexo_files.py`, para `relatorio_pdf.py` poder usá-la sem import circular):

```python
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
```

Métodos novos em `AfrRelatorioPdf`:

```python
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

```

- [ ] **Step 4: Implementar `models/relatorio_anexo_files.py`**

```python
"""Arquivos de cada posição de anexo do Relatório Final (spec §4.5).

`_resolve_files()` devolve só o que a montagem consegue usar; `_check_files()`
lista os problemas (consumido pela varredura de P5: `PROBLEM_EMPTY` →
ANEXO_VAZIO, qualquer outro → ANEXO_ILEGIVEL). Nada aqui levanta exceção por
causa de arquivo ruim — arquivo de terceiro exótico vira problema listado.
"""
import base64

from odoo import _, models
from odoo.tools.mimetypes import guess_mimetype

from .relatorio_pdf import file_problem

PROBLEM_EMPTY = "Nenhum arquivo encontrado para este anexo."
ALL_CERT_ROLES = ("antes", "depois", "externo")


class AfrRelatorioAnexoFiles(models.Model):
    _inherit = "afr.relatorio.anexo"

    def _cert_roles_list(self):
        self.ensure_one()
        roles = [r.strip() for r in (self.cert_roles or "").split(",") if r.strip()]
        return roles or list(ALL_CERT_ROLES)

    def _collect_sections_list(self):
        self.ensure_one()
        return [s.strip() for s in (self.collect_sections or "").split(",") if s.strip()]

    def _collect_items(self):
        """Itens coletados (com arquivo) das seções, do equipamento na OS.

        Ordem: itens sem ciclo, depois por ciclo (na `_order` do model de
        ciclo: qualificação, tipo, sequence), depois `sequence`, `id`.
        """
        self.ensure_one()
        Item = self.env["afr.qualificacao.collect.item"]
        sections = self._collect_sections_list()
        rel = self.relatorio_id
        if not sections or not rel:
            return Item
        items = Item.search([
            "|",
            ("qualif_id", "in", rel.qualificacao_ids.ids),
            "&",
            ("os_id", "=", rel.os_id.id),
            ("equipment_id", "=", rel.equipment_id.id),
            ("docx_section", "in", sections),
            ("state", "=", "collected"),
        ]).filtered(lambda i: i.file)
        cycles = self.env["afr.qualificacao.cycle"].search(
            [("id", "in", items.mapped("cycle_id").ids)]
        )
        rank = {cycle.id: pos for pos, cycle in enumerate(cycles, start=1)}
        return items.sorted(lambda i: (rank.get(i.cycle_id.id, 0), i.sequence, i.id))

    def _raw_files(self):
        """Candidatos `(bytes, mimetype, legenda)` sem validação."""
        self.ensure_one()
        if self.slot_kind == "bloco":
            # Conteúdo renderizado no próprio corpo (P3), logo após o separador.
            return []
        if self.attachment_ids:
            return [
                (att.raw or b"", att.mimetype or "", att.name or "")
                for att in self.attachment_ids.sorted("id")
            ]
        if self.slot_kind == "collect_section":
            files = []
            for item in self._collect_items():
                caption = item.name or ""
                if item.cycle_id:
                    caption = "%s — %s" % (item.cycle_id.display_name, caption)
                files.append((base64.b64decode(item.file), item.mimetype or "", caption))
            return files
        if self.slot_kind == "instrument_certs":
            return list(self.relatorio_id._afr_certificate_files(self._cert_roles_list()))
        if self.slot_kind == "malha_certs":
            return list(self.relatorio_id._afr_malha_certificate_files())
        return []

    def _resolve_files(self):
        """Lista ordenada `(bytes, mimetype, legenda)` só com arquivos utilizáveis."""
        self.ensure_one()
        files = []
        for content, mimetype, caption in self._raw_files():
            if file_problem(content, mimetype) is None:
                detected = guess_mimetype(content, default=mimetype or "")
                files.append((content, detected, caption))
        return files

    def _check_files(self):
        """Problemas do anexo (`[]` = ok).

        Formato dos itens: `PROBLEM_EMPTY` sozinho, ou
        `"<legenda do arquivo>: <motivo>"` (motivo de `file_problem`, ex.:
        `"cert.pdf: PDF protegido por senha"`).
        """
        self.ensure_one()
        if self.slot_kind == "bloco":
            ok = self.block_id and self.block_id.included
            return [] if ok else [PROBLEM_EMPTY]
        raw = self._raw_files()
        if not raw:
            return [PROBLEM_EMPTY]
        problems = []
        for content, mimetype, caption in raw:
            problem = file_problem(content, mimetype)
            if problem:
                problems.append("%s: %s" % (caption or _("arquivo sem nome"), problem))
        return problems
```

Registrar em `models/__init__.py`:

```python
from . import relatorio_anexo_files
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioAnexoFiles,/afr_qualificacao:TestRelatorioPdfCore --stop-after-init --no-http`
Expected: PASS (11 + 13).

- [ ] **Step 6: Commit**

```bash
git add models/relatorio_anexo_files.py models/relatorio_pdf.py models/__init__.py tests/test_relatorio_pdf.py
git commit -m "feat(relatorio): resolve and check annex files per slot kind"
```

---

### Task 4: `afr.relatorio.emissao` imutável + campos de emissão no relatório

**Files:**
- Create: `models/relatorio_emissao.py`
- Create: `models/relatorio_emissao_flow.py` (primeira parte: campos, `verify_url`, guarda de campos internos)
- Create: `tests/test_relatorio_emissao.py`
- Modify: `models/__init__.py` (append `from . import relatorio_emissao` e `from . import relatorio_emissao_flow`)
- Modify: `security/ir.model.access.csv`
- Modify: `tests/__init__.py` (append `from . import test_relatorio_emissao`)

**Interfaces:**
- Consumes: `afr.qualificacao.relatorio` (P1), `afr.qualificacao.manager.guard.mixin._check_manager_only(acao)` (existente, `models/qualificacao_security_mixin.py`).
- Produces:
  - Model `afr.relatorio.emissao`: `name` (compute, `"<relatorio.name> Rev.NN"`), `relatorio_id` (M2O, required, `ondelete="restrict"`), `revision` (Integer), `pdf_attachment_id` (M2O `ir.attachment`, `ondelete="restrict"`), `sha256` (Char), `token` (Char, index, unique), `issued_at` (Datetime), `issued_by` (M2O `res.users`), `blocks_snapshot` (Text JSON), `scan_snapshot` (Text JSON), `superseded` (Boolean). Criação/escrita só com `env.su` **e** contexto `rq_emissao_internal=True`; escrita interna aceita **apenas** `superseded=True`; `unlink` sempre bloqueado (exceto desinstalação do módulo).
  - Constante `models/relatorio_emissao.py::INTERNAL_CTX = "rq_emissao_internal"`.
  - Em `afr.qualificacao.relatorio` (agora também herda `afr.qualificacao.manager.guard.mixin`): `emissao_ids` (O2M), `current_emissao_id` (M2O), `minuta_attachment_id` (M2O `ir.attachment`), `verify_url` (Char compute, `@api.depends_context("rq_emission_token")`: token do contexto tem prioridade sobre `current_emissao_id.token`; formato `<web.base.url>/qualificacao/relatorio/verify/<token>?db=<db>` como `afr.qualificacao.certificate_verify_url`); `_RQ_INTERNAL_FIELDS = {"state", "revision", "current_emissao_id"}` só graváveis com `env.su`.

- [ ] **Step 1: Escrever os testes que falham (`tests/test_relatorio_emissao.py`)**

```python
"""P4 — emissão, revisão, aprovações, verificação pública e portal do Relatório Final."""
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon
from .relatorio_fakes import RelatorioFixtureMixin, make_user

MANAGER = "afr_qualificacao.group_afr_qualificacao_manager"
USER = "afr_qualificacao.group_afr_qualificacao_user"
TECH = "afr_qualificacao.group_afr_qualificacao_technician"


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioEmissaoModel(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = make_user(cls.env, "gestor.rq.emissao", MANAGER)

    def setUp(self):
        super().setUp()
        self.rel, _q = self._make_relatorio()
        self.att = self._attachment(b"%PDF-1.4 teste", "r.pdf", "application/pdf")

    def _internal_create(self, **vals):
        base = {
            "relatorio_id": self.rel.id, "revision": 0,
            "pdf_attachment_id": self.att.id, "sha256": "0" * 64,
            "token": "a" * 32,
        }
        base.update(vals)
        return self.env["afr.relatorio.emissao"].sudo().with_context(
            rq_emissao_internal=True
        ).create(base)

    def test_create_without_internal_flag_is_blocked(self):
        with self.assertRaises(UserError):
            self.env["afr.relatorio.emissao"].create({
                "relatorio_id": self.rel.id, "token": "b" * 32,
            })
        with self.assertRaises((AccessError, UserError)):
            self.env["afr.relatorio.emissao"].with_user(self.manager).create({
                "relatorio_id": self.rel.id, "token": "c" * 32,
            })

    def test_internal_create_and_supersede(self):
        emissao = self._internal_create()
        self.assertEqual(emissao.name, "%s Rev.00" % self.rel.name)
        emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": True})
        self.assertTrue(emissao.superseded)

    def test_write_is_blocked_even_for_superuser(self):
        emissao = self._internal_create()
        with self.assertRaises(UserError):
            emissao.write({"sha256": "f" * 64})
        with self.assertRaises(UserError):
            emissao.sudo().with_context(rq_emissao_internal=True).write({"sha256": "f" * 64})
        emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": True})
        with self.assertRaises(UserError):
            emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": False})
        with self.assertRaises((AccessError, UserError)):
            emissao.with_user(self.manager).write({"superseded": True})

    def test_unlink_is_blocked(self):
        emissao = self._internal_create()
        with self.assertRaises(UserError):
            emissao.unlink()

    def test_verify_url_prefers_context_token_then_current_emissao(self):
        self.assertFalse(self.rel.verify_url)
        url = self.rel.with_context(rq_emission_token="d" * 32).verify_url
        self.assertIn("/qualificacao/relatorio/verify/" + "d" * 32, url)
        emissao = self._internal_create(token="e" * 32)
        self.rel.write({"current_emissao_id": emissao.id})  # env admin (su)
        self.assertIn("/qualificacao/relatorio/verify/" + "e" * 32, self.rel.verify_url)

    def test_internal_fields_not_writable_by_users(self):
        rel_mgr = self.rel.with_user(self.manager)
        for vals in ({"state": "issued"}, {"revision": 3}):
            with self.assertRaises(UserError):
                rel_mgr.write(vals)
        self.rel.write({"revision": 2})  # su pode (migrações, código interno)
        self.assertEqual(self.rel.revision, 2)
```

Registrar em `tests/__init__.py` (depois de `test_relatorio_pdf`):

```python
from . import test_relatorio_emissao
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioEmissaoModel --stop-after-init --no-http`
Expected: ERROR — `KeyError: 'afr.relatorio.emissao'`.

- [ ] **Step 3: Implementar `models/relatorio_emissao.py`**

```python
"""Emissão imutável do Relatório Final (spec §4.6).

Mesmo espírito de `afr.qualificacao._CERTIFICATE_FIELDS`: ACL é só leitura
para todos os grupos e, além disso, create/write exigem `env.su` + contexto
`rq_emissao_internal` — o único chamador é `action_emitir` (manager-only).
A única escrita posterior permitida é marcar `superseded=True` quando a
revisão seguinte é emitida. Exclusão nunca (só na desinstalação do módulo).
"""
from odoo import _, api, fields, models
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from odoo.exceptions import UserError

INTERNAL_CTX = "rq_emissao_internal"


class AfrRelatorioEmissao(models.Model):
    _name = "afr.relatorio.emissao"
    _description = "Emissão do Relatório Final"
    _order = "relatorio_id, revision desc, id desc"

    name = fields.Char(compute="_compute_name")
    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", string="Relatório", required=True,
        ondelete="restrict", index=True, readonly=True,
    )
    revision = fields.Integer(string="Revisão", readonly=True)
    pdf_attachment_id = fields.Many2one(
        "ir.attachment", string="PDF", ondelete="restrict", readonly=True,
    )
    sha256 = fields.Char(string="SHA-256", readonly=True)
    token = fields.Char(string="Token", readonly=True, index=True, copy=False)
    issued_at = fields.Datetime(string="Emitido em", readonly=True)
    issued_by = fields.Many2one("res.users", string="Emitido por", readonly=True)
    blocks_snapshot = fields.Text(string="Blocos congelados (JSON)", readonly=True)
    scan_snapshot = fields.Text(string="Verificação congelada (JSON)", readonly=True)
    superseded = fields.Boolean(string="Substituída", readonly=True, default=False)

    _sql_constraints = [
        ("token_unique", "unique(token)", "Token de emissão duplicado."),
    ]

    @api.depends("relatorio_id.name", "revision")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s Rev.%02d" % (rec.relatorio_id.name or "", rec.revision)

    def _rq_is_internal(self):
        return self.env.su and bool(self.env.context.get(INTERNAL_CTX))

    @api.model_create_multi
    def create(self, vals_list):
        if not self._rq_is_internal():
            raise UserError(_(
                "Emissões do relatório final só são criadas pela ação Emitir."
            ))
        return super().create(vals_list)

    def write(self, vals):
        if not self._rq_is_internal() or set(vals) - {"superseded"}:
            raise UserError(_(
                "A emissão do relatório final é imutável: nada pode ser "
                "alterado depois de emitida."
            ))
        if not vals.get("superseded") and any(self.mapped("superseded")):
            raise UserError(_("Uma emissão substituída não volta a ser vigente."))
        return super().write(vals)

    def unlink(self):
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(_("A emissão do relatório final não pode ser excluída."))
```

- [ ] **Step 4: Implementar `models/relatorio_emissao_flow.py` (parte 1)**

```python
"""Relatório Final — emissão, revisão, aprovações e portal (P4).

Parte 1 (Task 4): campos de emissão, URL pública e guarda dos campos que só
as ações mudam. Tasks 7–9 acrescentam métodos a estas classes.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoRelatorioEmissao(models.Model):
    _name = "afr.qualificacao.relatorio"
    _inherit = ["afr.qualificacao.relatorio", "afr.qualificacao.manager.guard.mixin"]

    # Só as ações (Emitir / Revisar / aprovação do cliente) mudam estes
    # campos — via sudo(). Mesmo motivo do _CERTIFICATE_FIELDS de
    # afr.qualificacao: a ir.rule escopa registros, não valores.
    _RQ_INTERNAL_FIELDS = frozenset({"state", "revision", "current_emissao_id"})

    emissao_ids = fields.One2many(
        "afr.relatorio.emissao", "relatorio_id", string="Emissões", readonly=True,
    )
    current_emissao_id = fields.Many2one(
        "afr.relatorio.emissao", string="Emissão vigente", readonly=True, copy=False,
    )
    minuta_attachment_id = fields.Many2one(
        "ir.attachment", string="Última minuta", readonly=True, copy=False,
    )
    verify_url = fields.Char(
        compute="_compute_verify_url", string="URL pública de verificação",
    )

    @api.depends("current_emissao_id.token")
    @api.depends_context("rq_emission_token")
    def _compute_verify_url(self):
        """URL do QR. Durante a emissão o token vem do contexto: ele é gerado
        ANTES do PDF (o QR precisa dele) e a emissão só é criada depois,
        com o hash do PDF pronto."""
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param("web.base.url", default="")
        db_param = icp.get_param(
            "afr_qualificacao.verify_url_db", default=self.env.cr.dbname,
        )
        ctx_token = self.env.context.get("rq_emission_token")
        for rec in self:
            token = ctx_token or rec.current_emissao_id.token
            if not token:
                rec.verify_url = False
                continue
            url = "%s/qualificacao/relatorio/verify/%s" % (base, token)
            if db_param:
                url += "?db=%s" % db_param
            rec.verify_url = url

    def write(self, vals):
        if not self.env.su and self._RQ_INTERNAL_FIELDS.intersection(vals):
            raise UserError(_(
                "Status, revisão e emissão vigente do relatório final só mudam "
                "pelas ações Emitir, Revisar e pela aprovação do cliente."
            ))
        return super().write(vals)
```

Registrar em `models/__init__.py`:

```python
from . import relatorio_emissao
from . import relatorio_emissao_flow
```

ACL — acrescentar ao fim de `security/ir.model.access.csv`:

```csv
access_afr_relatorio_emissao_technician,afr_relatorio_emissao_technician,model_afr_relatorio_emissao,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_afr_relatorio_emissao_user,afr_relatorio_emissao_user,model_afr_relatorio_emissao,afr_qualificacao.group_afr_qualificacao_user,1,0,0,0
access_afr_relatorio_emissao_manager,afr_relatorio_emissao_manager,model_afr_relatorio_emissao,afr_qualificacao.group_afr_qualificacao_manager,1,0,0,0
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioEmissaoModel --stop-after-init --no-http`
Expected: PASS (6 testes).

- [ ] **Step 6: Commit**

```bash
git add models/relatorio_emissao.py models/relatorio_emissao_flow.py models/__init__.py security/ir.model.access.csv tests/test_relatorio_emissao.py tests/__init__.py
git commit -m "feat(relatorio): immutable emission record and verify URL"
```

---

### Task 5: Pipeline de montagem — `build()` / `_build()` (caminho dos marcadores)

**Files:**
- Modify: `models/relatorio_pdf.py` (função pura `compute_layout`, `MAX_PASSES`, métodos `build`, `_build`, `_render_body_and_markers`, `_body_render_data`, `_file_anexos`, `_annex_pdf`, `_assemble`, `_qr_page_index`, `_header`)
- Test: `tests/test_relatorio_pdf.py` (nova classe `TestRelatorioBuild`)

**Interfaces:**
- Consumes: Task 2 (`find_markers`, `fit_page_to_usable`, `image_to_pdf`, `open_pdf`, `stamp_pdf`, `pdf_bytes`), Task 3 (`file_problem`, `_render_report`, `anexo._raw_files()`), Task 4 (`relatorio.verify_url`, `relatorio.current_emissao_id`), P1 (`revision_label`, `company_id`, `equipment_id.tag`), P3 (`_body_blocks()`, `_anexos_included()`, `anexo.numero`, `anexo.code`, `block_kind`).
- Produces:
  - `relatorio_pdf.compute_layout(markers, body_count, annex_counts, codes) -> dict` com `insert_after: dict[int, list[str]]`, `trailing: list[str]`, `body_final: list[int]` (1-based), `page_map: dict[str, int]` (1-based), `total: int`.
  - `afr.relatorio.pdf.build(relatorio, watermark=False) -> bytes`; `._build(relatorio, watermark=False) -> tuple[bytes, list[str]]`; `._render_body_and_markers(relatorio, page_map) -> tuple[bytes, dict[str, int]]` (ponto de troca do fallback do Task 6); `._body_render_data(relatorio, page_map) -> dict` (`{"with_markers": True, "page_map": {...}}`); `._file_anexos(relatorio)` → anexos incluídos que levam arquivo (todos menos `slot_kind='bloco'`); `._header(relatorio, watermark, qr_page_index=None) -> dict`.
  - Contexto lido: `rq_emission_date` (datetime da emissão em curso, para a data do cabeçalho) e, via `verify_url`, `rq_emission_token`.
  - Regras: páginas de anexo PDF são encaixadas na área útil A4 (`fit_page_to_usable`); imagem vira 1 página por foto; anexo `bloco` não intercala nada (está no corpo); anexo cujo marcador não foi achado vai para o fim com aviso; até `MAX_PASSES = 3` renderizações do corpo até o `page_map` estabilizar (senão aviso); QR na página do marcador do 1º bloco `assinaturas` incluído (ou na última página do corpo); minuta: data "MINUTA", sem QR, com marca d'água.

- [ ] **Step 1: Escrever os testes que falham** — acrescentar a `tests/test_relatorio_pdf.py`:

```python
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
        for number, text in enumerate(pdf_pages_text(pdf), start=1):
            self.assertIn("Página %d de 9" % number, text)
            self.assertIn(self.rel.name, text)

    def test_body_render_data_goes_in_report_data(self):
        # Fato fixado P3 #1: page_map/with_markers no `data`, nunca no contexto.
        self.assertEqual(
            self.Pdf._body_render_data(self.rel, {"anexo:dados": 5}),
            {"with_markers": True, "page_map": {"anexo:dados": 5}},
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
        self.assertGreaterEqual(len(fake.calls), rp.MAX_PASSES)
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

    def test_public_build_returns_bytes(self):
        fake = FakeCorpo()
        with fake.patch(self.env):
            pdf = self.Pdf.build(self.rel)
        self.assertTrue(pdf.startswith(b"%PDF"))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioBuild --stop-after-init --no-http`
Expected: FAIL — `AttributeError: module ... has no attribute 'compute_layout'` / `'afr.relatorio.pdf' object has no attribute '_build'`.

- [ ] **Step 3: Implementar** — em `models/relatorio_pdf.py`:

Imports (topo): acrescentar `import base64` e trocar `from odoo import _, api, models` por

```python
from odoo import _, api, fields, models
```

Função pura de módulo (abaixo de `stamp_pdf`):

```python
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
```

Métodos novos em `AfrRelatorioPdf`:

```python
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

        O Task 6 (fallback) sobrescreve só este método.
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
        label = _("Anexo %s (%s)") % (anexo.numero or "?", anexo.title or anexo.code or "")
        raw = anexo._raw_files()
        if not raw:
            warnings.append(_("%s: nenhum arquivo — só o separador foi incluído.") % label)
            return b"", 0
        writer = PdfFileWriter()
        keep_alive = []  # PyPDF2 lê os streams de forma preguiçosa até o write
        for content, mimetype, caption in raw:
            problem = file_problem(content, mimetype)
            if problem:
                warnings.append(_("%s: '%s' ignorado — %s.") % (label, caption, problem))
                continue
            if guess_mimetype(content, default=mimetype or "") == "application/pdf":
                reader = open_pdf(content)
                keep_alive.append(reader)
                for idx in range(reader.getNumPages()):
                    page = reader.getPage(idx)
                    writer.addPage(fit_page_to_usable(page))
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
        keep_alive = [PdfFileReader(io.BytesIO(body), strict=False)]
        body_reader = keep_alive[0]

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
        """Página final (0-based) do 1º bloco `assinaturas` incluído."""
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
        """Dados do carimbo (ver `stamp_pdf`)."""
        company = relatorio.company_id or self.env.company
        equipment = relatorio.equipment_id
        if watermark:
            date_label = _("MINUTA")
            verify_url = False
        else:
            issued = (self.env.context.get("rq_emission_date")
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioBuild,/afr_qualificacao:TestRelatorioAnexoFiles,/afr_qualificacao:TestRelatorioPdfCore --stop-after-init --no-http`
Expected: PASS (13 + 11 + 13).

- [ ] **Step 5: Commit**

```bash
git add models/relatorio_pdf.py tests/test_relatorio_pdf.py
git commit -m "feat(relatorio): assemble body, annexes, index pass and stamp"
```

---

### Task 6 (EXECUTAR SÓ SE O SPIKE DO TASK 1 FALHAR): fallback — corpo renderizado em pedaços — **NÃO EXECUTADO** (spike passou)

Se os marcadores não forem confiáveis no template real, o corpo passa a ser renderizado em pedaços, um PDF por pedaço, e a posição de cada bloco/separador vem da **contagem direta de páginas**. O resto do pipeline (Task 5) não muda: só `_render_body_and_markers` é trocado, devolvendo o mesmo `(bytes, markers)`.

Como restringir o que o template de P3 percorre **sem mexer nele**: o template itera `doc._body_blocks()` e `doc._anexos_included()`, e `doc` herda o contexto do `ir.actions.report` que renderiza (`_get_rendering_context` faz `self.env[report.model].browse(docids)`; `_render_report` usa `relatorio.env`). Então P4 sobrescreve esses dois métodos para filtrar por `rq_chunk_blocks`/`rq_chunk_anexos` (tuplas de ids) e força contexto completo em `_block_numbering()` e `_report_index_entries()` (senão a numeração e o índice seriam só do pedaço).

Pedaços: blocos do texto agrupados até o próximo `page_break`; cada anexo incluído é um pedaço próprio (separador + bloco do anexo `bloco`). A posição de um bloco que não abre pedaço é aproximada pela 1ª página do pedaço (índice pode apontar uma página antes em blocos longos sem quebra — aceitável; blocos que aparecem no índice costumam ter `page_break`). O bloco de um anexo `bloco` fica na página seguinte ao separador (quebra depois do separador). Custo: nº de pedaços × até 3 passagens de wkhtmltopdf.

**Files:**
- Modify: `models/relatorio_pdf.py`
- Test: `tests/test_relatorio_pdf.py` (nova classe `TestRelatorioBuildFallback`)

**Interfaces:**
- Consumes: `_render_report` (Task 3, renderiza no env do relatório), P3 `_body_blocks()`, `_anexos_included()`, `_anexo_separator_block(code)`, `_block_numbering()`, `_report_index_entries()`; `merge_pdf` (`odoo.tools.pdf`).
- Produces: `afr.relatorio.pdf._body_chunks(relatorio) -> list[tuple[blocks, anexos]]`; `_render_body_and_markers` por pedaços; em `afr.qualificacao.relatorio`: `_body_blocks()`/`_anexos_included()` respeitam `rq_chunk_blocks`/`rq_chunk_anexos` quando presentes (ausentes/`None` = sem filtro). Interface pública inalterada.

- [ ] **Step 1: Escrever os testes que falham**

```python
@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioBuildFallback(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    def setUp(self):
        super().setUp()
        self.rel, _q = self._make_relatorio()
        self.blocks, self.anexos = self._standard_layout(self.rel)
        self.Pdf = self.env["afr.relatorio.pdf"]

    def test_chunks_split_on_page_break_and_per_annex(self):
        chunks = self.Pdf._body_chunks(self.rel)
        self.assertEqual(
            [(blocks.mapped("title"), anexos.mapped("code")) for blocks, anexos in chunks],
            [(["Capa"], []), (["Índice"], []), (["Objetivo"], []),
             (["Conclusao", "Assinaturas"], []), ([], ["dados"]), ([], ["fotos"])],
        )

    def test_chunk_context_filters_iteration_but_not_numbering_or_index(self):
        capa = self.blocks["capa"]
        rel_chunk = self.rel.with_context(rq_chunk_blocks=(capa.id,), rq_chunk_anexos=())
        self.assertEqual(rel_chunk._body_blocks(), capa)
        self.assertFalse(rel_chunk._anexos_included())
        self.assertEqual(rel_chunk._block_numbering(), self.rel._block_numbering())
        self.assertEqual(rel_chunk._report_index_entries(), self.rel._report_index_entries())

    def test_fallback_build_matches_marker_layout(self):
        fake = FakeCorpo()
        with fake.patch(self.env):
            pdf, warnings = self.Pdf._build(self.rel)
        pages = pdf_pages_text(pdf)
        self.assertEqual(len(pages), 9)
        self.assertIn("ANEXO 1: Resultados", pages[4])
        self.assertIn("ANEXO-DADOS p1", pages[5])
        self.assertIn("ANEXO 2: Impressões", pages[7])
        self.assertIn("impressao.png", pages[8])
        self.assertIn("IDX anexo:fotos=8", pages[1])
        self.assertFalse(any(c["data"]["with_markers"] for c in fake.calls))
        self.assertTrue(all("rq_chunk_blocks" in c["context"] for c in fake.calls))
        self.assertEqual(warnings, [])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioBuildFallback --stop-after-init --no-http`
Expected: FAIL — `AttributeError: ... '_body_chunks'`.

- [ ] **Step 3: Implementar** — em `models/relatorio_pdf.py`, acrescentar `merge_pdf` ao import:

```python
from odoo.tools.pdf import PdfFileReader, PdfFileWriter, merge_pdf
```

**substituir** `_render_body_and_markers` em `AfrRelatorioPdf` por:

```python
    @api.model
    def _body_chunks(self, relatorio):
        """`[(blocos, anexos)]` — cada pedaço começa em página nova."""
        Block = relatorio.block_ids.browse()
        Anexo = relatorio.anexo_ids.browse()
        chunks = []
        current = Block
        for block in relatorio._body_blocks():
            if block.page_break and current:
                chunks.append((current, Anexo))
                current = Block
            current |= block
        if current:
            chunks.append((current, Anexo))
        for anexo in relatorio._anexos_included():
            chunks.append((Block, anexo))
        return chunks

    @api.model
    def _render_body_and_markers(self, relatorio, page_map):
        """Fallback (spike falhou): um PDF por pedaço, posição por contagem."""
        parts, markers, page = [], {}, 0
        for blocks, anexos in self._body_chunks(relatorio):
            rel_chunk = relatorio.with_context(
                rq_chunk_blocks=tuple(blocks.ids), rq_chunk_anexos=tuple(anexos.ids),
            )
            pdf = self._render_report(
                rel_chunk, {"with_markers": False, "page_map": dict(page_map)}
            )
            count = PdfFileReader(io.BytesIO(pdf), strict=False).getNumPages()
            for block in blocks:
                markers.setdefault("bloco:%d" % block.id, page)
            for anexo in anexos:
                markers.setdefault("anexo:%s" % anexo.code, page)
                sep = relatorio._anexo_separator_block(anexo.code)
                if sep:
                    markers.setdefault("bloco:%d" % sep.id, page)
                if anexo.slot_kind == "bloco" and anexo.block_id and anexo.block_id.included:
                    markers.setdefault("bloco:%d" % anexo.block_id.id, page + 1)
            parts.append(pdf)
            page += count
        if not parts:
            body = self._render_report(relatorio, self._body_render_data(relatorio, page_map))
            return body, {}
        return merge_pdf(parts), markers
```

e, no fim do arquivo, a extensão do relatório:

```python
class AfrQualificacaoRelatorioChunks(models.Model):
    """Fallback do Task 6: restringe o que o template percorre por contexto."""

    _inherit = "afr.qualificacao.relatorio"

    def _body_blocks(self):
        blocks = super()._body_blocks()
        only = self.env.context.get("rq_chunk_blocks")
        if only is not None:
            blocks = blocks.filtered(lambda b: b.id in only)
        return blocks

    def _anexos_included(self):
        anexos = super()._anexos_included()
        only = self.env.context.get("rq_chunk_anexos")
        if only is not None:
            anexos = anexos.filtered(lambda a: a.id in only)
        return anexos

    def _rq_full(self):
        return self.with_context(rq_chunk_blocks=None, rq_chunk_anexos=None)

    def _block_numbering(self):
        return super(AfrQualificacaoRelatorioChunks, self._rq_full())._block_numbering()

    def _report_index_entries(self):
        return super(AfrQualificacaoRelatorioChunks, self._rq_full())._report_index_entries()
```

- [ ] **Step 4: Rodar e ver passar (Task 5 continua verde)**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioBuildFallback,/afr_qualificacao:TestRelatorioBuild --stop-after-init --no-http`
Expected: PASS (3 + 13). Os testes do Task 5 foram escritos sem depender do caminho (não contam chamadas nem exigem `with_markers` nas chamadas; `test_body_render_data_goes_in_report_data` testa o método, que continua existindo).

- [ ] **Step 5: Commit**

```bash
git add models/relatorio_pdf.py tests/test_relatorio_pdf.py
git commit -m "feat(relatorio): chunked body rendering fallback for page mapping"
```

---

### Task 7: Aprovações internas, gate de emissão, invalidação e trava de edição

**Files:**
- Create: `models/relatorio_editorial.py`
- Modify: `models/relatorio_emissao_flow.py` (substituir `write`; novos métodos)
- Modify: `models/__init__.py` (append `from . import relatorio_editorial`)
- Test: `tests/test_relatorio_emissao.py` (nova classe `TestRelatorioAprovacoes`)

**Interfaces:**
- Consumes: Task 4 (`_RQ_INTERNAL_FIELDS`, `write`); P3 `afr.relatorio.aprovacao` (`papel`, `user_id`, `partner_id`, `nome_exibicao`, `approved_at`, `ip`, `access_token`); P1/P3 filhos com `relatorio_id`; `afr.qualificacao.cycle` (`qualificacao_id`, `janela_inicio`, `janela_fim`, `sensor_pos_ids`); `afr.relatorio.sensor.pos.cycle_id`.
- Produces:
  - `models/relatorio_editorial.py`: `SKIP_CTX = "rq_skip_editorial_hook"`; AbstractModel `afr.relatorio.editorial.mixin` (`_rq_lock_when_issued`, `_rq_watched_fields`, `_rq_relatorios()`, `_rq_touch(vals=None)`, ganchos em `create`/`write`/`unlink`) aplicado a `afr.relatorio.block`, `afr.relatorio.anexo`, `afr.relatorio.checklist`, `afr.relatorio.indicador`, `afr.relatorio.leitura.ib` (trava + invalida) e a `afr.relatorio.sensor.pos`, `afr.qualificacao.cycle` (só invalida; ciclo só pelos campos `janela_inicio`, `janela_fim`, `sensor_pos_ids`).
  - `afr.relatorio.aprovacao`: `approved_at`/`ip` de papéis `elaborador`/`emissor`/`cliente` só graváveis com `env.su` (create — inclusive por default de contexto — e write); `access_token` já preenchido não é regravável sem `su`. Papel `executor` fica livre (P3 pode aprová-lo implicitamente).
  - Em `afr.qualificacao.relatorio`: `_RQ_EDITORIAL_FIELDS = {"equipment_id", "template_id", "data_inicio_ensaios", "data_fim_ensaios", "amb_temperatura", "amb_umidade", "tolerancia_acima", "criterio_f0_fator", "block_ids", "anexo_ids", "checklist_ids", "indicador_ids", "leitura_ib_ids"}`; `_check_editable()` (UserError se algum registro não está em `draft`); `_invalidate_internal_approvals()` → `bool` (zera `approved_at` de elaborador/emissor dos relatórios em `draft`, posta no chatter); `action_aprovar_interno()`; `_check_emission_gate()` → `list[str]` (P5 estende com `super()`); constantes `INTERNAL_ROLES = ("elaborador", "emissor")`, `ROLE_LABELS`.

- [ ] **Step 1: Escrever os testes que falham** — acrescentar a `tests/test_relatorio_emissao.py` (import extra no topo: `from odoo import fields`):

```python
@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioAprovacoes(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.elab = make_user(cls.env, "elab.rq.aprov", USER)
        cls.emis = make_user(cls.env, "emis.rq.aprov", MANAGER)
        cls.tech = make_user(cls.env, "tec.rq.aprov", TECH)

    def setUp(self):
        super().setUp()
        self.rel, self.qualif = self._make_relatorio()
        self.block = self._block(self.rel, "static", "Objetivo", 10)
        Aprov = self.env["afr.relatorio.aprovacao"]
        self.line_elab = Aprov.create({"relatorio_id": self.rel.id, "papel": "elaborador",
                                       "user_id": self.elab.id, "nome_exibicao": "Eng. Elaborador"})
        self.line_emis = Aprov.create({"relatorio_id": self.rel.id, "papel": "emissor",
                                       "user_id": self.emis.id, "nome_exibicao": "Eng. Responsável"})
        self.line_cli = Aprov.create({"relatorio_id": self.rel.id, "papel": "cliente",
                                      "partner_id": self.partner.id, "nome_exibicao": "Cliente Teste"})

    def _approve_internal(self):
        (self.line_elab | self.line_emis).sudo().write({"approved_at": fields.Datetime.now()})

    def _internal_approved(self):
        return bool(self.line_elab.approved_at or self.line_emis.approved_at)

    def test_aprovar_interno_marks_only_my_lines(self):
        self.rel.with_user(self.elab).action_aprovar_interno()
        self.assertTrue(self.line_elab.approved_at)
        self.assertFalse(self.line_emis.approved_at)

    def test_aprovar_interno_requires_designation(self):
        self.rel.with_user(self.emis).action_aprovar_interno()  # 1ª vez: ok
        with self.assertRaises(UserError):
            self.rel.with_user(self.emis).action_aprovar_interno()  # já aprovou
        with self.assertRaises(UserError):
            self.rel.with_user(self.tech).action_aprovar_interno()

    def test_cycle_edit_by_technician_invalidates_without_access_error(self):
        # Técnico só escreve ciclo da própria OS (rule_cycle_technician_write_own).
        employee = self.env["hr.employee"].create({"name": "Téc Campo", "user_id": self.tech.id})
        self.rel.os_id.tecnico_default_id = employee
        cycle = self.env["afr.qualificacao.cycle"].create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id,
        })
        self._approve_internal()
        cycle.with_user(self.tech).write({"janela_fim": fields.Datetime.now()})
        self.assertFalse(self._internal_approved())

    def test_gate_lists_missing_internal_approvals(self):
        problems = self.rel._check_emission_gate()
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("Elaborador" in p for p in problems))
        self.assertTrue(any("Emissor" in p for p in problems))
        self._approve_internal()
        self.assertEqual(self.rel._check_emission_gate(), [])

    def test_gate_requires_designated_roles(self):
        self.line_emis.unlink()
        problems = self.rel._check_emission_gate()
        self.assertTrue(any("Nenhum emissor" in p for p in problems), problems)

    def test_editing_relatorio_field_invalidates_internal_approvals(self):
        self._approve_internal()
        self.rel.write({"amb_temperatura": "22 a 25 °C"})
        self.assertFalse(self._internal_approved())
        self.assertIn("Aprovações internas zeradas", self.rel.message_ids[0].body)

    def test_editing_child_models_directly_invalidates(self):
        edits = [
            ("bloco", lambda: self.block.write({"body": "<p>novo texto</p>"})),
            ("anexo", lambda: self._anexo(self.rel, "dados", "Dados", 10)),
            ("checklist", lambda: self.env["afr.relatorio.checklist"].create({
                "relatorio_id": self.rel.id, "grupo": "Instalações elétricas",
                "descricao": "Tomada dedicada", "status": "aprovado", "sequence": 10})),
            ("indicador", lambda: self.env["afr.relatorio.indicador"].create({
                "relatorio_id": self.rel.id, "tipo": "biologico", "marca": "Marca T",
                "lote": "L-01"})),
            ("bloco removido", lambda: self._block(self.rel, "static", "X", 99).unlink()),
        ]
        for label, edit in edits:
            with self.subTest(edit=label):
                self._approve_internal()
                edit()
                self.assertFalse(self._internal_approved(), label)

    def test_non_editorial_write_keeps_approvals(self):
        self._approve_internal()
        att = self._attachment(b"%PDF-1.4", "m.pdf", "application/pdf")
        self.rel.write({"minuta_attachment_id": att.id})
        self.rel.message_post(body="comentário")
        self.assertTrue(self.line_elab.approved_at and self.line_emis.approved_at)

    def test_cycle_window_edit_invalidates_but_other_cycle_fields_do_not(self):
        cycle = self.env["afr.qualificacao.cycle"].create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id,
        })
        self._approve_internal()
        cycle.write({"notes": "sem efeito editorial"})
        self.assertTrue(self._internal_approved())
        cycle.write({"janela_inicio": fields.Datetime.now()})
        self.assertFalse(self._internal_approved())

    def test_edit_blocked_outside_draft(self):
        self.rel.write({"state": "issued"})  # su
        with self.assertRaises(UserError):
            self.block.write({"body": "<p>depois de emitido</p>"})
        with self.assertRaises(UserError):
            self.rel.write({"amb_umidade": "41 %UR"})
        with self.assertRaises(UserError):
            self.env["afr.relatorio.checklist"].create({
                "relatorio_id": self.rel.id, "grupo": "G", "descricao": "D",
                "status": "na", "sequence": 1})
        cycle = self.env["afr.qualificacao.cycle"].create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id,
        })
        cycle.write({"janela_fim": fields.Datetime.now()})  # ciclo não trava

    def test_users_cannot_forge_approval_fields(self):
        now = fields.Datetime.now()
        with self.assertRaises(UserError):
            self.line_elab.with_user(self.elab).write({"approved_at": now})
        Aprov = self.env["afr.relatorio.aprovacao"].with_user(self.elab)
        with self.assertRaises(UserError):
            Aprov.create({"relatorio_id": self.rel.id, "papel": "cliente",
                          "partner_id": self.partner.id, "approved_at": now})
        with self.assertRaises(UserError):
            Aprov.with_context(default_approved_at=now).create({
                "relatorio_id": self.rel.id, "papel": "emissor", "user_id": self.elab.id})
        executor = Aprov.create({"relatorio_id": self.rel.id, "papel": "executor",
                                 "nome_exibicao": "Téc. Campo", "approved_at": now})
        self.assertTrue(executor.approved_at)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioAprovacoes --stop-after-init --no-http`
Expected: FAIL — `AttributeError: ... 'action_aprovar_interno'` e asserts de invalidação.

- [ ] **Step 3: Implementar `models/relatorio_editorial.py`**

```python
"""Edição editorial do Relatório Final (spec §4.6).

Editar dados, texto ou anexos em rascunho zera as aprovações internas (evita
aprovar uma versão e emitir outra). Fora de rascunho a edição é recusada —
o PDF emitido e os dados não podem divergir até alguém clicar Revisar.
Os ganchos ficam nos models FILHOS também: o form de bloco (modal), anexos,
checklist etc. gravam direto no filho, sem passar por relatorio.write().
"""
from odoo import _, api, models
from odoo.exceptions import UserError

SKIP_CTX = "rq_skip_editorial_hook"


class AfrRelatorioEditorialMixin(models.AbstractModel):
    _name = "afr.relatorio.editorial.mixin"
    _description = "Mixin: edição editorial do Relatório Final"

    # True: recusa a edição com relatório fora de rascunho; False: só invalida.
    _rq_lock_when_issued = True
    # None: qualquer campo conta; frozenset: só estes campos contam no write.
    _rq_watched_fields = None

    def _rq_relatorios(self):
        return self.mapped("relatorio_id")

    def _rq_touch(self, vals=None):
        if self.env.context.get(SKIP_CTX) or not self:
            return
        if (vals is not None and self._rq_watched_fields is not None
                and not self._rq_watched_fields.intersection(vals)):
            return
        relatorios = self._rq_relatorios()
        if not relatorios:
            return
        if self._rq_lock_when_issued:
            relatorios._check_editable()
        relatorios._invalidate_internal_approvals()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._rq_touch()
        return records

    def write(self, vals):
        self._rq_touch(vals)
        return super().write(vals)

    def unlink(self):
        self._rq_touch()
        return super().unlink()


def _draft_relatorios_of(env, qualificacoes):
    if not qualificacoes:
        return env["afr.qualificacao.relatorio"]
    return env["afr.qualificacao.relatorio"].search([
        ("qualificacao_ids", "in", qualificacoes.ids),
        ("state", "=", "draft"),
    ])


class AfrRelatorioBlockEditorial(models.Model):
    _name = "afr.relatorio.block"
    _inherit = ["afr.relatorio.block", "afr.relatorio.editorial.mixin"]


class AfrRelatorioAnexoEditorial(models.Model):
    _name = "afr.relatorio.anexo"
    _inherit = ["afr.relatorio.anexo", "afr.relatorio.editorial.mixin"]


class AfrRelatorioChecklistEditorial(models.Model):
    _name = "afr.relatorio.checklist"
    _inherit = ["afr.relatorio.checklist", "afr.relatorio.editorial.mixin"]


class AfrRelatorioIndicadorEditorial(models.Model):
    _name = "afr.relatorio.indicador"
    _inherit = ["afr.relatorio.indicador", "afr.relatorio.editorial.mixin"]


class AfrRelatorioLeituraIbEditorial(models.Model):
    _name = "afr.relatorio.leitura.ib"
    _inherit = ["afr.relatorio.leitura.ib", "afr.relatorio.editorial.mixin"]


class AfrRelatorioSensorPosEditorial(models.Model):
    _name = "afr.relatorio.sensor.pos"
    _inherit = ["afr.relatorio.sensor.pos", "afr.relatorio.editorial.mixin"]

    # Dado de campo do ciclo: não trava (a qualificação pode seguir
    # sendo usada), só zera aprovações de relatórios em rascunho.
    _rq_lock_when_issued = False

    def _rq_relatorios(self):
        return _draft_relatorios_of(self.env, self.mapped("cycle_id.qualificacao_id"))


class AfrQualificacaoCycleEditorial(models.Model):
    _name = "afr.qualificacao.cycle"
    _inherit = ["afr.qualificacao.cycle", "afr.relatorio.editorial.mixin"]

    _rq_lock_when_issued = False
    _rq_watched_fields = frozenset({"janela_inicio", "janela_fim", "sensor_pos_ids"})

    def _rq_relatorios(self):
        return _draft_relatorios_of(self.env, self.mapped("qualificacao_id"))

    @api.model_create_multi
    def create(self, vals_list):
        # Criar ciclo (confirmação de SO, geração de OS) não é edição
        # editorial: pula o gancho do mixin.
        return super(
            AfrQualificacaoCycleEditorial, self.with_context(**{SKIP_CTX: True})
        ).create(vals_list).with_context(**{SKIP_CTX: False})

    def unlink(self):
        return super(
            AfrQualificacaoCycleEditorial, self.with_context(**{SKIP_CTX: True})
        ).unlink()


class AfrRelatorioAprovacaoGuard(models.Model):
    _inherit = "afr.relatorio.aprovacao"

    # Executor é aprovado implicitamente (assinatura do PWA) — fica livre.
    _RQ_GUARDED_ROLES = ("elaborador", "emissor", "cliente")
    _RQ_APPROVAL_FIELDS = frozenset({"approved_at", "ip"})

    def _rq_forbidden(self):
        raise UserError(_(
            "Data, IP e token de aprovação só são gravados pelas ações "
            "Aprovar (interno) e pelo portal do cliente."
        ))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Pós-checagem nos valores EFETIVOS: pega vals explícito e também
        # default_* de contexto / ir.default (lição do Task 14 do certificado).
        if not self.env.su and any(
            r.papel in self._RQ_GUARDED_ROLES and (r.approved_at or r.ip)
            for r in records
        ):
            self._rq_forbidden()
        return records

    def write(self, vals):
        if not self.env.su:
            if (self._RQ_APPROVAL_FIELDS.intersection(vals)
                    and any(r.papel in self._RQ_GUARDED_ROLES for r in self)):
                self._rq_forbidden()
            if "access_token" in vals and any(r.access_token for r in self):
                self._rq_forbidden()
        return super().write(vals)
```

> Atenção ao `create` do ciclo: o `.with_context(**{SKIP_CTX: False})` no retorno devolve os registros com o contexto de volta ao normal para quem chamou (senão gravações seguintes no mesmo recordset pulariam o gancho).

- [ ] **Step 4: Estender `models/relatorio_emissao_flow.py`**

Import no topo:

```python
from .relatorio_editorial import SKIP_CTX

INTERNAL_ROLES = ("elaborador", "emissor")
ROLE_LABELS = {"elaborador": "Elaborador", "emissor": "Emissor"}
```

Na classe `AfrQualificacaoRelatorioEmissao`, acrescentar o conjunto editorial e **substituir** o `write` do Task 4 por:

```python
    # Campos do próprio relatório cuja edição muda o conteúdo do PDF.
    _RQ_EDITORIAL_FIELDS = frozenset({
        "equipment_id", "template_id",
        "data_inicio_ensaios", "data_fim_ensaios",
        "amb_temperatura", "amb_umidade",
        "tolerancia_acima", "criterio_f0_fator",
        "block_ids", "anexo_ids", "checklist_ids", "indicador_ids", "leitura_ib_ids",
    })

    def write(self, vals):
        if not self.env.su and self._RQ_INTERNAL_FIELDS.intersection(vals):
            raise UserError(_(
                "Status, revisão e emissão vigente do relatório final só mudam "
                "pelas ações Emitir, Revisar e pela aprovação do cliente."
            ))
        editorial = (
            bool(self._RQ_EDITORIAL_FIELDS.intersection(vals))
            and not self.env.context.get(SKIP_CTX)
        )
        if editorial:
            self._check_editable()
        result = super().write(vals)
        if editorial:
            self._invalidate_internal_approvals()
        return result

    def _check_editable(self):
        locked = self.filtered(lambda r: r.state != "draft")
        if locked:
            raise UserError(_(
                "O relatório %(name)s já foi emitido (%(rev)s). Use Revisar para "
                "abrir uma nova revisão antes de editar."
            ) % {"name": locked[0].name, "rev": locked[0].revision_label})

    def _invalidate_internal_approvals(self):
        """Zera elaborador/emissor dos relatórios em rascunho. True se zerou algo."""
        lines = self.filtered(lambda r: r.state == "draft").mapped(
            "aprovacao_ids"
        ).filtered(lambda a: a.papel in INTERNAL_ROLES and a.approved_at)
        if not lines:
            return False
        lines.sudo().write({"approved_at": False})
        # sudo: o gatilho pode vir de um Técnico editando janela do ciclo
        # (write em afr.qualificacao.cycle) sem write no relatório.
        for rel in lines.mapped("relatorio_id").sudo():
            rel.message_post(body=_(
                "Aprovações internas zeradas: o relatório foi editado depois "
                "da aprovação."
            ))
        return True

    def action_aprovar_interno(self):
        """Aprova as linhas elaborador/emissor designadas ao usuário atual."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Só é possível aprovar internamente um relatório em rascunho."))
        lines = self.aprovacao_ids.filtered(
            lambda a: a.papel in INTERNAL_ROLES
            and a.user_id == self.env.user
            and not a.approved_at
        )
        if not lines:
            raise UserError(_(
                "Você não está designado como elaborador ou emissor com aprovação "
                "pendente neste relatório."
            ))
        now = fields.Datetime.now()
        for line in lines:
            line.sudo().write({
                "approved_at": now,
                "nome_exibicao": line.nome_exibicao or self.env.user.name,
            })
        self.message_post(body=_("Aprovado internamente por %(user)s (%(roles)s).") % {
            "user": self.env.user.name,
            "roles": ", ".join(ROLE_LABELS[p] for p in lines.mapped("papel")),
        })
        return True

    def _check_emission_gate(self):
        """Impedimentos para emitir (lista vazia = pode). P5 estende com super()."""
        self.ensure_one()
        problems = []
        for papel in INTERNAL_ROLES:
            label = ROLE_LABELS[papel]
            lines = self.aprovacao_ids.filtered(lambda a, p=papel: a.papel == p)
            if not lines:
                problems.append(_("Nenhum %s designado.") % label.lower())
            for line in lines:
                who = line.nome_exibicao or line.user_id.name or "—"
                if not line.user_id:
                    problems.append(_("%(role)s %(who)s sem usuário designado.") % {
                        "role": label, "who": who})
                elif not line.approved_at:
                    problems.append(_("%(role)s %(who)s ainda não aprovou.") % {
                        "role": label, "who": who})
        return problems
```

Registrar em `models/__init__.py`:

```python
from . import relatorio_editorial
```

- [ ] **Step 5: Rodar e ver passar (e a suíte P1–P3 continua verde)**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao --stop-after-init --no-http`
Expected: `TestRelatorioAprovacoes` PASS (11); nenhuma falha nova além das 3 pré-existentes conhecidas. Atenção especial aos testes de P1–P3 que editam blocos/anexos/checklist: eles rodam com relatório em `draft`, então só a invalidação (inofensiva) é acionada.

- [ ] **Step 6: Commit**

```bash
git add models/relatorio_editorial.py models/relatorio_emissao_flow.py models/__init__.py tests/test_relatorio_emissao.py
git commit -m "feat(relatorio): internal approvals, emission gate and edit lock"
```

---

### Task 8: Minuta, Emitir, Revisar, `proxima_qualificacao`

> **SUBSTITUÍDO** pelos Tasks 8A/8B/8R da emenda (fila + etapas): minuta e emissão enfileiram; emissão, estado, revisão, reset do cliente e minuta são gravados no finalize do job. O texto abaixo é o plano original.

**Files:**
- Modify: `models/relatorio_emissao_flow.py`
- Test: `tests/test_relatorio_emissao.py` (base `RelatorioEmissaoBase` + classe `TestRelatorioEmissaoFlow`)

**Interfaces:**
- Consumes: Task 4 (`afr.relatorio.emissao`, `INTERNAL_CTX`, `verify_url`), Task 5 (`afr.relatorio.pdf.build`, `._build`), Task 7 (`_check_emission_gate`, `_invalidate_internal_approvals`, `action_aprovar_interno`), P1 (`_compute_proxima_qualificacao`, stored), P3 (`_render_block_body`, `REPORT_CORPO` html).
- Produces (em `afr.qualificacao.relatorio`):
  - `action_gerar_minuta()` → `dict` `ir.actions.act_url` (`/web/content/<id>?download=true`); grupo `user`; usa `afr.relatorio.pdf._build(self, watermark=True)`, substitui a minuta anterior, posta avisos no chatter.
  - `action_emitir()` → `True`; manager-only; exige `state == "draft"`; `_check_emission_gate()` não vazio ⇒ **`UserError`** com `"Não é possível emitir o relatório <name>:\n- <problema 1>\n- <problema 2>"`; gera `token = uuid4().hex` **antes** do PDF e chama **`self.env["afr.relatorio.pdf"].build(self.with_context(rq_emission_token=token, rq_emission_date=issued_at), watermark=False)`** (ponto único a mockar nos testes de P5); SHA-256 dos bytes; `ir.attachment` com os mesmos bytes; `afr.relatorio.emissao` com `blocks_snapshot` (`_blocks_snapshot()`) e `scan_snapshot` (`_scan_snapshot()`); só **então** marca a anterior `superseded`; zera aprovações do cliente e gera token novo para elas; `state = "issued"`, `current_emissao_id`; chatter com o PDF anexo.
  - `action_revisar()` → `True`; manager-only; só de `issued`/`client_approved`; `revision += 1`, `state = "draft"`, zera aprovações internas; emissão anterior segue vigente.
  - `_scan_snapshot()` → `"[]"`; `_blocks_snapshot()` → `str` JSON `{"<block_id>": html do corpo do bloco, "__corpo__": html completo do corpo}`; `_reset_client_approvals()`; `_update_client_approval_state()`; `_rq_check_user_group(acao)`.
  - `_compute_proxima_qualificacao` (override, `@api.depends("current_emissao_id.issued_at")`): data da emissão vigente (fuso do usuário) + 12 meses; sem emissão, resultado de P1.

- [ ] **Step 1: Escrever os testes que falham** — acrescentar a `tests/test_relatorio_emissao.py`. Imports extras no topo:

```python
import hashlib
import json
from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from .relatorio_fakes import FakeCorpo, pdf_pages_text, squash
```

Base compartilhada (sem testes próprios) e a classe:

```python
class RelatorioEmissaoBase(RelatorioFixtureMixin, AfrQualificacaoTestCommon):
    """Relatório pronto para emitir: layout padrão + elaborador/emissor = gestor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = make_user(cls.env, "gestor.rq.flow", MANAGER)
        cls.office = make_user(cls.env, "escritorio.rq.flow", USER)
        cls.tech = make_user(cls.env, "tecnico.rq.flow", TECH)
        cls.partner.email = "cliente@example.test"

    def setUp(self):
        super().setUp()
        self.rel, self.qualif = self._make_relatorio()
        self.blocks, self.anexos = self._standard_layout(self.rel)
        Aprov = self.env["afr.relatorio.aprovacao"]
        self.line_elab = Aprov.create({"relatorio_id": self.rel.id, "papel": "elaborador",
                                       "user_id": self.manager.id, "nome_exibicao": "Eng. Elaborador"})
        self.line_emis = Aprov.create({"relatorio_id": self.rel.id, "papel": "emissor",
                                       "user_id": self.manager.id, "nome_exibicao": "Eng. Responsável"})
        self.line_cli = Aprov.create({"relatorio_id": self.rel.id, "papel": "cliente",
                                      "partner_id": self.partner.id, "nome_exibicao": "Cliente Teste"})

    def _approve(self):
        self.rel.with_user(self.manager).action_aprovar_interno()

    def _emit(self, user=None, fake=None):
        fake = fake or FakeCorpo()
        with fake.patch(self.env):
            return self.rel.with_user(user or self.manager).action_emitir()

    def _approve_and_emit(self):
        self._approve()
        self._emit()
        return self.rel.current_emissao_id

    def _revise_and_emit(self):
        self.rel.with_user(self.manager).action_revisar()
        return self._approve_and_emit()


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioEmissaoFlow(RelatorioEmissaoBase):

    def test_aprovar_interno_approves_all_my_lines_in_one_call(self):
        self._approve()
        self.assertTrue(self.line_elab.approved_at and self.line_emis.approved_at)

    def test_emitir_blocked_by_gate_lists_problems(self):
        with self.assertRaises(UserError) as ctx:
            self._emit()
        self.assertIn("Não é possível emitir", str(ctx.exception))
        self.assertIn("Elaborador", str(ctx.exception))
        self.assertEqual(self.rel.state, "draft")
        self.assertFalse(self.rel.emissao_ids)

    def test_emitir_requires_manager(self):
        self._approve()
        with self.assertRaises(UserError):
            self._emit(user=self.office)
        self.assertEqual(self.rel.state, "draft")

    def test_emitir_creates_emission_with_hash_of_attachment_bytes(self):
        emissao = self._approve_and_emit()
        self.assertEqual(self.rel.state, "issued")
        self.assertEqual(emissao.revision, 0)
        self.assertEqual(emissao.issued_by, self.manager)
        self.assertEqual(len(emissao.token), 32)
        self.assertEqual(emissao.sha256, hashlib.sha256(emissao.pdf_attachment_id.raw).hexdigest())
        self.assertEqual(json.loads(emissao.scan_snapshot), [])
        snapshot = json.loads(emissao.blocks_snapshot)
        self.assertIn(str(self.blocks["objetivo"].id), snapshot)
        self.assertIn("__corpo__", snapshot)
        message = self.rel.message_ids.filtered(lambda m: m.attachment_ids)[:1]
        self.assertEqual(message.attachment_ids, emissao.pdf_attachment_id)

    def test_emitted_pdf_has_qr_for_new_token_and_no_watermark(self):
        seen = []
        Pdf = type(self.env["afr.relatorio.pdf"])
        original = Pdf._stamp

        def spy(pdf_self, content, header, watermark):
            seen.append(dict(header, watermark=watermark))
            return original(pdf_self, content, header, watermark)

        with patch.object(Pdf, "_stamp", spy):
            emissao = self._approve_and_emit()
        self.assertIn(emissao.token, seen[0]["verify_url"])
        self.assertFalse(seen[0]["watermark"])
        self.assertNotEqual(seen[0]["date"], "MINUTA")
        text = squash("".join(pdf_pages_text(emissao.pdf_attachment_id.raw)))
        self.assertNotIn("SEMVALIDADE", text)

    def test_emitir_twice_is_blocked(self):
        self._approve_and_emit()
        with self.assertRaises(UserError):
            self._emit()

    def test_revision_flow_supersedes_only_on_new_emission(self):
        e0 = self._approve_and_emit()
        self.rel.with_user(self.manager).action_revisar()
        self.assertEqual(self.rel.state, "draft")
        self.assertEqual(self.rel.revision, 1)
        self.assertEqual(self.rel.revision_label, "Rev.01")
        self.assertFalse(self.line_elab.approved_at or self.line_emis.approved_at)
        self.assertFalse(e0.superseded)
        self.assertEqual(self.rel.current_emissao_id, e0)
        e1 = self._approve_and_emit()
        self.assertEqual(e1.revision, 1)
        self.assertTrue(e0.superseded)
        self.assertFalse(e1.superseded)
        self.assertEqual(self.rel.current_emissao_id, e1)
        self.assertNotEqual(e0.token, e1.token)

    def test_revisar_only_from_issued_and_by_manager(self):
        with self.assertRaises(UserError):
            self.rel.with_user(self.manager).action_revisar()  # rascunho
        self._approve_and_emit()
        with self.assertRaises(UserError):
            self.rel.with_user(self.office).action_revisar()

    def test_client_approvals_reset_on_new_emission(self):
        self._approve_and_emit()
        token_rev0 = self.line_cli.access_token
        self.line_cli.sudo().write({"approved_at": fields.Datetime.now(), "ip": "203.0.113.9"})
        self._revise_and_emit()
        self.assertFalse(self.line_cli.approved_at)
        self.assertFalse(self.line_cli.ip)
        self.assertNotEqual(self.line_cli.access_token, token_rev0)

    def test_proxima_qualificacao_follows_emission_date(self):
        self.rel.write({"data_fim_ensaios": date(2026, 7, 1)})
        self.assertEqual(self.rel.proxima_qualificacao, date(2027, 7, 1))
        emissao = self._approve_and_emit()
        issued_local = fields.Datetime.context_timestamp(self.rel, emissao.issued_at).date()
        self.assertEqual(self.rel.proxima_qualificacao, issued_local + relativedelta(months=12))

    def test_minuta_has_watermark_and_replaces_previous(self):
        fake = FakeCorpo()
        rel_office = self.rel.with_user(self.office)
        with fake.patch(self.env):
            action = rel_office.action_gerar_minuta()
            first = self.rel.minuta_attachment_id
            rel_office.action_gerar_minuta()
        second = self.rel.minuta_attachment_id
        self.assertIn("/web/content/%d" % first.id, action["url"])
        self.assertFalse(first.exists())
        self.assertTrue(second)
        text = squash("".join(pdf_pages_text(second.raw)))
        self.assertIn("MINUTA—SEMVALIDADE", text)
        self.assertEqual(self.rel.state, "draft")
        self.assertFalse(self.rel.emissao_ids)

    def test_minuta_forbidden_for_technician(self):
        with self.assertRaises(UserError):
            self.rel.with_user(self.tech).action_gerar_minuta()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioEmissaoFlow --stop-after-init --no-http`
Expected: FAIL — `AttributeError: ... 'action_emitir'` (e demais ações).

- [ ] **Step 3: Implementar** — em `models/relatorio_emissao_flow.py`:

Imports no topo (junto dos existentes):

```python
import hashlib
import json
import uuid

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from .relatorio_emissao import INTERNAL_CTX
from .relatorio_pdf import REPORT_CORPO

USER_GROUP = "afr_qualificacao.group_afr_qualificacao_user"
```

Métodos novos em `AfrQualificacaoRelatorioEmissao`:

```python
    # ------------------------------------------------------------------
    # Próxima qualificação: emissão + 12 meses (P1 usava fim dos ensaios)
    # ------------------------------------------------------------------
    @api.depends("current_emissao_id.issued_at")
    def _compute_proxima_qualificacao(self):
        super()._compute_proxima_qualificacao()
        for rel in self:
            issued = rel.current_emissao_id.issued_at
            if issued:
                local = fields.Datetime.context_timestamp(rel, issued).date()
                rel.proxima_qualificacao = local + relativedelta(months=12)

    # ------------------------------------------------------------------
    # Snapshots congelados na emissão
    # ------------------------------------------------------------------
    def _scan_snapshot(self):
        """JSON dos achados + decisões. P4 não tem varredura: '[]'. P5 sobrescreve."""
        self.ensure_one()
        return "[]"

    def _blocks_snapshot(self):
        """HTML final de cada bloco + corpo inteiro (tabelas dinâmicas incluídas)."""
        self.ensure_one()
        snapshot = {
            str(block.id): str(self._render_block_body(block))
            for block in self.block_ids.filtered("included")
        }
        html, _fmt = self.env["ir.actions.report"]._render_qweb_html(
            REPORT_CORPO, self.ids, data={"page_map": {}, "with_markers": False},
        )
        snapshot["__corpo__"] = html.decode() if isinstance(html, bytes) else str(html)
        return json.dumps(snapshot, ensure_ascii=False, sort_keys=True)

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    def _rq_check_user_group(self, acao):
        if self.env.su or self.env.user.has_group(USER_GROUP):
            return
        raise UserError(_("Apenas usuários do escritório podem %s.") % acao)

    def action_gerar_minuta(self):
        """PDF com marca d'água 'MINUTA — SEM VALIDADE'; substitui a anterior."""
        self.ensure_one()
        self._rq_check_user_group(_("gerar a minuta"))
        pdf, warnings = self.env["afr.relatorio.pdf"]._build(self, watermark=True)
        previous = self.minuta_attachment_id
        attachment = self.env["ir.attachment"].sudo().create({
            "name": "%s-%s-MINUTA.pdf" % (self.name, self.revision_label),
            "raw": pdf,
            "mimetype": "application/pdf",
            "res_model": self._name,
            "res_id": self.id,
        })
        self.write({"minuta_attachment_id": attachment.id})
        if previous:
            previous.sudo().unlink()
        body = Markup("%s") % _("Minuta gerada.")
        if warnings:
            body += Markup("<ul>%s</ul>") % Markup("").join(
                Markup("<li>%s</li>") % w for w in warnings
            )
        self.message_post(body=body)
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%d?download=true" % attachment.id,
            "target": "self",
        }

    def action_emitir(self):
        """Emite a revisão atual: gate → token → PDF → hash → emissão imutável."""
        self.ensure_one()
        self._check_manager_only(_("emitir o relatório final"))
        if self.state != "draft":
            raise UserError(_(
                "Só é possível emitir um relatório em rascunho. Use Revisar para "
                "abrir uma nova revisão."
            ))
        problems = self._check_emission_gate()
        if problems:
            raise UserError(_("Não é possível emitir o relatório %s:\n- %s") % (
                self.name, "\n- ".join(problems)))
        # Token ANTES do PDF: o QR do rodapé aponta para ele (spec §8).
        token = uuid.uuid4().hex
        issued_at = fields.Datetime.now()
        pdf = self.env["afr.relatorio.pdf"].build(
            self.with_context(rq_emission_token=token, rq_emission_date=issued_at),
            watermark=False,
        )
        sha256 = hashlib.sha256(pdf).hexdigest()
        attachment = self.env["ir.attachment"].sudo().create({
            "name": "%s-%s.pdf" % (self.name, self.revision_label),
            "raw": pdf,
            "mimetype": "application/pdf",
            "res_model": self._name,
            "res_id": self.id,
        })
        previous = self.emissao_ids.filtered(lambda e: not e.superseded)
        internal = {INTERNAL_CTX: True}
        emissao = self.env["afr.relatorio.emissao"].sudo().with_context(**internal).create({
            "relatorio_id": self.id,
            "revision": self.revision,
            "pdf_attachment_id": attachment.id,
            "sha256": sha256,
            "token": token,
            "issued_at": issued_at,
            "issued_by": self.env.user.id,
            "blocks_snapshot": self._blocks_snapshot(),
            "scan_snapshot": self._scan_snapshot(),
        })
        # A anterior só vira "substituída" agora que a nova existe (spec §4.6).
        previous.sudo().with_context(**internal).write({"superseded": True})
        self._reset_client_approvals()
        self.sudo().write({"state": "issued", "current_emissao_id": emissao.id})
        self.message_post(
            body=_("Relatório emitido (%(rev)s). SHA-256: %(sha)s") % {
                "rev": self.revision_label, "sha": sha256},
            attachment_ids=[attachment.id],
        )
        return True

    def action_revisar(self):
        """Abre Rev.N+1 em rascunho; a emissão vigente continua valendo até a nova."""
        self.ensure_one()
        self._check_manager_only(_("abrir uma revisão do relatório final"))
        if self.state not in ("issued", "client_approved"):
            raise UserError(_("Só é possível revisar um relatório emitido."))
        self.sudo().write({"revision": self.revision + 1, "state": "draft"})
        self._invalidate_internal_approvals()
        self.message_post(body=_(
            "Revisão %s aberta. A emissão anterior continua vigente até a nova "
            "ser emitida."
        ) % self.revision_label)
        return True

    def _reset_client_approvals(self):
        """Nova revisão precisa de nova aprovação do cliente (link novo)."""
        for line in self.aprovacao_ids.filtered(lambda a: a.papel == "cliente"):
            line.sudo().write({
                "approved_at": False,
                "ip": False,
                "access_token": uuid.uuid4().hex,
            })

    def _update_client_approval_state(self):
        """issued → client_approved quando todos os aprovadores do cliente aprovaram."""
        for rel in self:
            clientes = rel.aprovacao_ids.filtered(lambda a: a.papel == "cliente")
            if rel.state == "issued" and clientes and all(clientes.mapped("approved_at")):
                rel.sudo().write({"state": "client_approved"})
                rel.message_post(body=_(
                    "Todos os aprovadores do cliente aprovaram a %s."
                ) % rel.revision_label)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioEmissaoFlow,/afr_qualificacao:TestRelatorioAprovacoes,/afr_qualificacao:TestRelatorioEmissaoModel --stop-after-init --no-http`
Expected: PASS (12 + 11 + 6). Se `test_emitir_creates_emission_with_hash_of_attachment_bytes` falhar em `_render_qweb_html` do corpo (fixture sem algum dado que o template de P3 exige), corrigir a **fixture** (`_standard_layout`), não o código. Se a emissão/minuta como Gestor/Usuário der `AccessError` lendo os `ir.attachment` da fixture (criados pelo OdooBot, sem `res_id`), a correção é ler `self.attachment_ids.sudo()` em `_raw_files` (o acesso ao anexo já é o controle), não mudar a fixture.

- [ ] **Step 5: Commit**

```bash
git add models/relatorio_emissao_flow.py tests/test_relatorio_emissao.py
git commit -m "feat(relatorio): draft PDF, emission with hash and revision flow"
```

---

### Task 9: Verificação pública, portal de aprovação do cliente e envio por e-mail

**Files:**
- Create: `controllers/relatorio.py`
- Create: `views/relatorio_public_templates.xml`
- Create: `data/mail_template_relatorio_aprovacao.xml`
- Modify: `controllers/__init__.py` (append `from . import relatorio`)
- Modify: `models/relatorio_emissao_flow.py` (classe `_inherit` de `afr.relatorio.aprovacao`; `action_enviar_aprovacao_cliente`)
- Modify: `__manifest__.py` (`data`: os dois XML novos, no fim da lista)
- Test: `tests/test_relatorio_emissao.py` (classe `TestRelatorioPublicoPortal`)

**Interfaces:**
- Consumes: Task 8 (`RelatorioEmissaoBase`, `action_emitir`, `action_revisar`, `_update_client_approval_state`); P3 `afr.relatorio.aprovacao.access_token` (gerado no create para cliente e renovado por P4 a cada emissão).
- Produces:
  - `controllers/relatorio.py::_relatorio_verify_values(env, token) -> dict` com `status` ∈ `not_found`/`valid`/`superseded`/`tampered` (tampered = bytes do PDF armazenado não batem com `sha256`), `token`, e (se achado) `emissao`, `relatorio`, `current`, `under_revision` (bool: válido mas relatório reaberto em rascunho), `client_approvals` (recordset, só quando `valid`).
  - `controllers/relatorio.py::_portal_aprovacao(env, aprovacao_id, access_token) -> record | None` (sudo; só `papel == 'cliente'`; `consteq`).
  - Rotas: `GET /qualificacao/relatorio/verify/<token>` (public), `GET /my/relatorio/<int:aprovacao_id>?access_token=` (public, 404 se token errado), `GET /my/relatorio/<int:aprovacao_id>/pdf?access_token=`, `POST /my/relatorio/<int:aprovacao_id>/aprovar` (csrf; campos `access_token`, `nome`).
  - Templates `afr_qualificacao.relatorio_verify_template`, `afr_qualificacao.portal_relatorio_aprovacao`; `mail.template` `afr_qualificacao.mail_template_relatorio_aprovacao` (model `afr.relatorio.aprovacao`).
  - `afr.relatorio.aprovacao`: `portal_url` (Char compute), `_portal_url() -> str`, `_portal_approve(nome, ip) -> bool` (False se já aprovado; UserError se não é cliente ou não há revisão emitida).
  - `afr.qualificacao.relatorio.action_enviar_aprovacao_cliente()` → `True` (grupo user; só `issued`; e-mail para cada cliente pendente com e-mail).

- [ ] **Step 1: Escrever os testes que falham** — acrescentar a `tests/test_relatorio_emissao.py`. Import extra no topo:

```python
from odoo.addons.afr_qualificacao.controllers.relatorio import (
    _portal_aprovacao,
    _relatorio_verify_values,
)
```

```python
@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioPublicoPortal(RelatorioEmissaoBase):

    def test_verify_not_found(self):
        self.assertEqual(_relatorio_verify_values(self.env, "curto")["status"], "not_found")
        self.assertEqual(_relatorio_verify_values(self.env, "f" * 32)["status"], "not_found")

    def test_verify_valid_then_superseded_only_after_new_emission(self):
        e0 = self._approve_and_emit()
        values = _relatorio_verify_values(self.env, e0.token)
        self.assertEqual(values["status"], "valid")
        self.assertEqual(values["emissao"], e0)
        self.assertFalse(values["under_revision"])
        self.rel.with_user(self.manager).action_revisar()
        values = _relatorio_verify_values(self.env, e0.token)
        self.assertEqual(values["status"], "valid")
        self.assertTrue(values["under_revision"])
        e1 = self._approve_and_emit()
        self.assertEqual(_relatorio_verify_values(self.env, e0.token)["status"], "superseded")
        self.assertEqual(_relatorio_verify_values(self.env, e0.token)["current"], e1)
        self.assertEqual(_relatorio_verify_values(self.env, e1.token)["status"], "valid")

    def test_verify_detects_tampered_stored_pdf(self):
        e0 = self._approve_and_emit()
        e0.pdf_attachment_id.sudo().write({"raw": b"%PDF-1.4 outro conteudo"})
        self.assertEqual(_relatorio_verify_values(self.env, e0.token)["status"], "tampered")

    def test_portal_token_check(self):
        self._approve_and_emit()
        token = self.line_cli.access_token
        self.assertEqual(_portal_aprovacao(self.env, self.line_cli.id, token), self.line_cli)
        self.assertIsNone(_portal_aprovacao(self.env, self.line_cli.id, "errado"))
        self.assertIsNone(_portal_aprovacao(self.env, self.line_cli.id, None))
        self.assertIsNone(_portal_aprovacao(self.env, self.line_elab.id, token))
        self.assertIsNone(_portal_aprovacao(self.env, 999999999, token))

    def test_portal_approve_records_data_and_moves_state(self):
        emissao = self._approve_and_emit()
        self.assertTrue(self.line_cli._portal_approve("Cliente Teste Aprovador", "203.0.113.5"))
        self.assertTrue(self.line_cli.approved_at)
        self.assertEqual(self.line_cli.ip, "203.0.113.5")
        self.assertEqual(self.line_cli.nome_exibicao, "Cliente Teste Aprovador")
        self.assertEqual(self.rel.state, "client_approved")
        self.assertFalse(self.line_cli._portal_approve("De novo", "203.0.113.6"))
        # Aprovação do cliente não altera o PDF: hash preservado.
        self.assertEqual(emissao.sha256,
                         hashlib.sha256(emissao.pdf_attachment_id.raw).hexdigest())
        values = _relatorio_verify_values(self.env, emissao.token)
        self.assertEqual(values["client_approvals"], self.line_cli)

    def test_portal_approve_waits_for_every_client_approver(self):
        second = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": self.rel.id, "papel": "cliente",
            "partner_id": self.partner.id, "nome_exibicao": "Cliente Teste 2",
        })
        self._approve_and_emit()
        self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        self.assertEqual(self.rel.state, "issued")
        second._portal_approve("Cliente Teste 2", "203.0.113.7")
        self.assertEqual(self.rel.state, "client_approved")

    def test_portal_approve_refused_before_emission(self):
        with self.assertRaises(UserError):
            self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        self.assertFalse(self.line_cli.approved_at)

    def test_send_to_client_creates_mail_with_portal_link(self):
        self._approve_and_emit()
        self.rel.with_user(self.office).action_enviar_aprovacao_cliente()
        mail = self.env["mail.mail"].search([
            ("model", "=", "afr.relatorio.aprovacao"), ("res_id", "=", self.line_cli.id),
        ], limit=1)
        self.assertTrue(mail)
        self.assertIn("/my/relatorio/%d?access_token=%s" % (
            self.line_cli.id, self.line_cli.access_token), mail.body_html)
        self.assertIn("cliente@example.test", mail.email_to or "")

    def test_send_to_client_only_when_issued(self):
        with self.assertRaises(UserError):
            self.rel.with_user(self.office).action_enviar_aprovacao_cliente()

    def test_public_templates_exist(self):
        self.assertTrue(self.env.ref("afr_qualificacao.relatorio_verify_template"))
        self.assertTrue(self.env.ref("afr_qualificacao.portal_relatorio_aprovacao"))
        self.assertTrue(self.env.ref("afr_qualificacao.mail_template_relatorio_aprovacao"))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioPublicoPortal --stop-after-init --no-http`
Expected: ERROR — `ModuleNotFoundError: ... controllers.relatorio`.

- [ ] **Step 3: Implementar `controllers/relatorio.py`**

```python
"""Relatório Final: verificação pública e aprovação do cliente (spec §8).

Mesmo padrão de `controllers/main.py`: a lógica fica em funções de módulo
(testáveis sem request HTTP — os testes rodam com --no-http) e as rotas só
renderizam. O QR do PDF aponta para o token da emissão, não para o hash.
"""
import hashlib

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.exceptions import UserError
from odoo.http import content_disposition, request
from odoo.tools import consteq


def _relatorio_verify_values(env, token):
    """Valores do template público de verificação.

    status: 'not_found' | 'valid' | 'superseded' | 'tampered' (bytes do PDF
    armazenado não batem com o SHA-256 congelado na emissão).
    """
    values = {"status": "not_found", "token": token}
    if not token or len(token) != 32:
        return values
    emissao = env["afr.relatorio.emissao"].sudo().search([("token", "=", token)], limit=1)
    if not emissao:
        return values
    rel = emissao.relatorio_id
    raw = emissao.pdf_attachment_id.raw or b""
    if not raw or hashlib.sha256(raw).hexdigest() != emissao.sha256:
        status = "tampered"
    elif emissao.superseded:
        status = "superseded"
    else:
        status = "valid"
    values.update({
        "status": status,
        "emissao": emissao,
        "relatorio": rel,
        "current": rel.current_emissao_id,
        "under_revision": status == "valid" and rel.state == "draft",
        "client_approvals": rel.aprovacao_ids.filtered(
            lambda a: a.papel == "cliente" and a.approved_at
        ) if status == "valid" else rel.aprovacao_ids.browse(),
    })
    return values


def _portal_aprovacao(env, aprovacao_id, access_token):
    """Linha de aprovação do cliente se o token confere (comparação em tempo constante)."""
    aprovacao = env["afr.relatorio.aprovacao"].sudo().browse(int(aprovacao_id)).exists()
    if (not aprovacao or aprovacao.papel != "cliente" or not aprovacao.access_token
            or not access_token or not consteq(aprovacao.access_token, access_token)):
        return None
    return aprovacao


class RelatorioFinalPublicController(http.Controller):

    @http.route(
        ["/qualificacao/relatorio/verify/<string:token>"],
        type="http", auth="public", website=True, sitemap=False, csrf=False,
    )
    def relatorio_verify(self, token, **kwargs):
        return request.render(
            "afr_qualificacao.relatorio_verify_template",
            _relatorio_verify_values(request.env, token),
        )

    @http.route(
        ["/my/relatorio/<int:aprovacao_id>"],
        type="http", auth="public", website=True, sitemap=False,
    )
    def portal_relatorio(self, aprovacao_id, access_token=None, message=None, **kwargs):
        aprovacao = _portal_aprovacao(request.env, aprovacao_id, access_token)
        if not aprovacao:
            raise NotFound()
        rel = aprovacao.relatorio_id
        return request.render("afr_qualificacao.portal_relatorio_aprovacao", {
            "aprovacao": aprovacao,
            "relatorio": rel,
            "emissao": rel.current_emissao_id,
            "access_token": access_token,
            "message": message,
        })

    @http.route(
        ["/my/relatorio/<int:aprovacao_id>/pdf"],
        type="http", auth="public", website=True, sitemap=False,
    )
    def portal_relatorio_pdf(self, aprovacao_id, access_token=None, **kwargs):
        aprovacao = _portal_aprovacao(request.env, aprovacao_id, access_token)
        attachment = aprovacao and aprovacao.relatorio_id.current_emissao_id.pdf_attachment_id
        if not attachment:
            raise NotFound()
        return request.make_response(attachment.raw, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", content_disposition(attachment.name)),
        ])

    @http.route(
        ["/my/relatorio/<int:aprovacao_id>/aprovar"],
        type="http", auth="public", website=True, sitemap=False, methods=["POST"],
    )
    def portal_relatorio_aprovar(self, aprovacao_id, access_token=None, nome=None, **kwargs):
        aprovacao = _portal_aprovacao(request.env, aprovacao_id, access_token)
        if not aprovacao:
            raise NotFound()
        try:
            aprovacao._portal_approve(nome, request.httprequest.remote_addr)
            message = "ok"
        except UserError:
            message = "erro"
        return request.redirect("/my/relatorio/%d?access_token=%s&message=%s" % (
            aprovacao.id, access_token, message))
```

Registrar em `controllers/__init__.py`:

```python
from . import relatorio
```

- [ ] **Step 4: Métodos de portal e envio** — em `models/relatorio_emissao_flow.py`:

Na classe do relatório:

```python
    def action_enviar_aprovacao_cliente(self):
        """E-mail com o link do portal para cada aprovador do cliente pendente."""
        self.ensure_one()
        self._rq_check_user_group(_("enviar o relatório para aprovação do cliente"))
        if self.state != "issued":
            raise UserError(_("Envie para aprovação do cliente só depois de emitir."))
        pending = self.aprovacao_ids.filtered(
            lambda a: a.papel == "cliente" and not a.approved_at and a.partner_id.email
        )
        if not pending:
            raise UserError(_(
                "Nenhum aprovador do cliente pendente com e-mail cadastrado."
            ))
        template = self.env.ref("afr_qualificacao.mail_template_relatorio_aprovacao")
        for line in pending:
            template.sudo().send_mail(line.id, force_send=False)
        self.message_post(body=_("Link de aprovação enviado para: %s") % ", ".join(
            pending.mapped("partner_id.email")))
        return True
```

Nova classe no fim do arquivo:

```python
class AfrRelatorioAprovacaoPortal(models.Model):
    _inherit = "afr.relatorio.aprovacao"

    portal_url = fields.Char(compute="_compute_portal_url", string="Link do portal")

    def _compute_portal_url(self):
        for line in self:
            line.portal_url = line._portal_url() if line.papel == "cliente" else False

    def _portal_url(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        url = "%s/my/relatorio/%d?access_token=%s" % (
            icp.get_param("web.base.url", default=""), self.id, self.access_token or "")
        db_param = icp.get_param(
            "afr_qualificacao.verify_url_db", default=self.env.cr.dbname)
        if db_param:
            url += "&db=%s" % db_param
        return url

    def _portal_approve(self, nome, ip):
        """Aprovação pelo portal. False se já estava aprovada."""
        self.ensure_one()
        rel = self.relatorio_id
        if self.papel != "cliente":
            raise UserError(_("Só aprovadores do cliente aprovam pelo portal."))
        if rel.state not in ("issued", "client_approved") or not rel.current_emissao_id:
            raise UserError(_("Não há revisão emitida aguardando aprovação."))
        if self.approved_at:
            return False
        nome = (nome or "").strip()
        self.sudo().write({
            "approved_at": fields.Datetime.now(),
            "ip": ip or False,
            "nome_exibicao": nome or self.nome_exibicao or self.partner_id.name or "",
        })
        rel.sudo().message_post(body=_(
            "%(nome)s aprovou a %(rev)s pelo portal (IP %(ip)s)."
        ) % {"nome": self.nome_exibicao, "rev": rel.revision_label, "ip": ip or "—"})
        rel.sudo()._update_client_approval_state()
        return True
```

- [ ] **Step 5: Templates públicos — `views/relatorio_public_templates.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Verificação pública do Relatório Final (destino do QR). -->
    <template id="relatorio_verify_template" name="Verificação do Relatório Final">
        <t t-call="portal.frontend_layout">
            <div class="container py-5">
                <div class="row justify-content-center">
                    <div class="col-md-8">
                        <h2 class="mb-4">Verificação de Relatório Final</h2>

                        <div t-if="status == 'not_found'" class="alert alert-danger">
                            <h4 class="alert-heading">Relatório não encontrado</h4>
                            <p>Token inválido ou inexistente.</p>
                            <p><small><strong>Token consultado:</strong> <code t-esc="token or '—'"/></small></p>
                        </div>
                        <div t-if="status == 'tampered'" class="alert alert-danger">
                            <h4 class="alert-heading">Arquivo divergente</h4>
                            <p>O PDF armazenado não corresponde ao hash SHA-256 registrado na emissão.</p>
                        </div>
                        <div t-if="status == 'superseded'" class="alert alert-warning">
                            <h4 class="alert-heading">Revisão substituída</h4>
                            <p>Esta revisão foi substituída<t t-if="current"> pela
                                <strong t-esc="current.name"/></t>. Solicite a revisão vigente ao emissor.</p>
                        </div>
                        <div t-if="status == 'valid'" class="alert alert-success">
                            <h4 class="alert-heading">Relatório válido</h4>
                            <p>Esta é a revisão vigente, emitida pelo laboratório.</p>
                            <p t-if="under_revision" class="mb-0"><small>Uma nova revisão está em elaboração.</small></p>
                        </div>

                        <div t-if="status != 'not_found'" class="card">
                            <div class="card-body">
                                <h5 class="card-title" t-esc="relatorio.name"/>
                                <table class="table table-sm">
                                    <tr><th style="width:30%">Revisão</th><td t-esc="'Rev.%02d' % emissao.revision"/></tr>
                                    <tr><th>Cliente</th><td t-esc="relatorio.partner_id.name"/></tr>
                                    <tr><th>Equipamento</th><td t-esc="relatorio.equipment_id.display_name"/></tr>
                                    <tr><th>TAG</th><td t-esc="relatorio.equipment_id.tag or '—'"/></tr>
                                    <tr><th>Emitido em</th><td><span t-field="emissao.issued_at"/></td></tr>
                                    <tr><th>SHA-256 do PDF</th><td><code style="word-break:break-all;" t-esc="emissao.sha256"/></td></tr>
                                </table>
                                <t t-if="status == 'valid'">
                                    <h6>Aprovações do cliente</h6>
                                    <p t-if="not client_approvals" class="text-muted">Aguardando aprovação do cliente.</p>
                                    <ul t-if="client_approvals">
                                        <li t-foreach="client_approvals" t-as="ap">
                                            <t t-esc="ap.nome_exibicao"/> — <span t-field="ap.approved_at"/>
                                        </li>
                                    </ul>
                                </t>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </t>
    </template>

    <!-- Portal: aprovação do cliente (link com access_token por aprovador). -->
    <template id="portal_relatorio_aprovacao" name="Aprovação do Relatório Final">
        <t t-call="portal.frontend_layout">
            <div class="container py-5">
                <div class="row justify-content-center">
                    <div class="col-md-8">
                        <h2 class="mb-1" t-esc="relatorio.name"/>
                        <p class="text-muted" t-esc="relatorio.revision_label"/>

                        <div t-if="message == 'ok'" class="alert alert-success">Aprovação registrada. Obrigado.</div>
                        <div t-if="message == 'erro'" class="alert alert-danger">Não foi possível registrar a aprovação: não há revisão emitida aguardando aprovação.</div>

                        <t t-if="emissao">
                            <p>Emitido em <span t-field="emissao.issued_at"/>.<br/>
                                SHA-256: <code style="word-break:break-all;" t-esc="emissao.sha256"/></p>
                            <p><a class="btn btn-secondary"
                                  t-attf-href="/my/relatorio/#{aprovacao.id}/pdf?access_token=#{access_token}">Baixar PDF</a></p>
                        </t>

                        <div t-if="aprovacao.approved_at" class="alert alert-info">
                            Aprovado por <strong t-esc="aprovacao.nome_exibicao"/> em <span t-field="aprovacao.approved_at"/>.
                        </div>
                        <t t-elif="emissao and relatorio.state in ('issued', 'client_approved')">
                            <form method="post" t-attf-action="/my/relatorio/#{aprovacao.id}/aprovar">
                                <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
                                <input type="hidden" name="access_token" t-att-value="access_token"/>
                                <div class="mb-3">
                                    <label for="rq_nome" class="form-label">Seu nome</label>
                                    <input id="rq_nome" name="nome" class="form-control" required="required"
                                           t-att-value="aprovacao.nome_exibicao or aprovacao.partner_id.name"/>
                                </div>
                                <button type="submit" class="btn btn-primary">Aprovar relatório</button>
                            </form>
                        </t>
                        <div t-else="" class="alert alert-warning">Este relatório está em revisão. Aguarde a nova emissão.</div>
                    </div>
                </div>
            </div>
        </t>
    </template>
</odoo>
```

- [ ] **Step 6: E-mail — `data/mail_template_relatorio_aprovacao.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="mail_template_relatorio_aprovacao" model="mail.template">
            <field name="name">Relatório Final: aprovação do cliente</field>
            <field name="model_id" ref="afr_qualificacao.model_afr_relatorio_aprovacao"/>
            <field name="subject">Aprovação do relatório {{ object.relatorio_id.name }} {{ object.relatorio_id.revision_label }}</field>
            <field name="email_from">{{ object.relatorio_id.company_id.email or user.email }}</field>
            <field name="email_to">{{ object.partner_id.email }}</field>
            <field name="auto_delete" eval="True"/>
            <field name="body_html" type="html">
<div>
    <p>Prezado(a) <t t-out="object.nome_exibicao or object.partner_id.name or ''"/>,</p>
    <p>O relatório <strong t-out="object.relatorio_id.name"/> (<t t-out="object.relatorio_id.revision_label"/>) foi emitido e aguarda a sua aprovação.</p>
    <p><a t-att-href="object.portal_url">Ver o relatório e aprovar</a></p>
    <p>Se preferir, copie o endereço: <t t-out="object.portal_url"/></p>
</div>
            </field>
        </record>
    </data>
</odoo>
```

> O link é o campo público `portal_url` (e não `object._portal_url()`): o render QWeb de `mail.template` em modo restrito não chama métodos privados.

Manifest — no **fim** da lista `data` de `__manifest__.py`:

```python
        # Relatório Final P4 — verificação pública, portal e e-mail
        "views/relatorio_public_templates.xml",
        "data/mail_template_relatorio_aprovacao.xml",
```

- [ ] **Step 7: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioPublicoPortal,/afr_qualificacao:TestRelatorioEmissaoFlow --stop-after-init --no-http`
Expected: PASS (10 + 12).

- [ ] **Step 8: Commit**

```bash
git add controllers/relatorio.py controllers/__init__.py views/relatorio_public_templates.xml data/mail_template_relatorio_aprovacao.xml models/relatorio_emissao_flow.py __manifest__.py tests/test_relatorio_emissao.py
git commit -m "feat(relatorio): public verification, client portal approval and email"
```

---

### Task 10: Backend — botões no header, aba Revisões, manifest 16.0.8.3.0 e smoke de UI

**Files:**
- Create: `views/relatorio_emissao_views.xml`
- Modify: `__manifest__.py` (`version`, `data`)
- Test: `tests/test_relatorio_emissao.py` (classe `TestRelatorioViews`)

**Interfaces:**
- Consumes: form de P1 `afr_qualificacao.view_afr_qualificacao_relatorio_form` (`<header>` com `<field name="state" widget="statusbar"/>`, `<notebook>`); métodos dos Tasks 7–9.
- Produces: botões `action_gerar_minuta`, `action_aprovar_interno`, `action_emitir`, `action_revisar`, `action_enviar_aprovacao_cliente` no header (antes do statusbar); página `name="page_revisoes"` (fim do notebook; P5 acrescenta `page_verificacao` depois); views `view_afr_relatorio_emissao_tree`/`_form` (somente leitura).

- [ ] **Step 1: Escrever os testes que falham** — acrescentar a `tests/test_relatorio_emissao.py`:

```python
@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioViews(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Como Gestor: botões com groups= somem do arch para quem não tem o grupo
        # (o usuário padrão do teste, OdooBot, não está nos grupos do módulo).
        cls.manager = make_user(cls.env, "gestor.rq.views", MANAGER)

    def test_form_has_p4_buttons_and_revisoes_page(self):
        arch = self.env["afr.qualificacao.relatorio"].with_user(self.manager).get_views(
            [(False, "form")])["views"]["form"]["arch"]
        for name in ("action_gerar_minuta", "action_aprovar_interno", "action_emitir",
                     "action_revisar", "action_enviar_aprovacao_cliente"):
            self.assertIn('name="%s"' % name, arch)
        self.assertIn('name="page_revisoes"', arch)
        self.assertIn('name="emissao_ids"', arch)

    def test_emission_views_are_read_only(self):
        arch = self.env["afr.relatorio.emissao"].with_user(self.manager).get_views(
            [(False, "form")])["views"]["form"]["arch"]
        self.assertIn('create="0"', arch)
        self.assertIn('edit="0"', arch)

    def test_manifest_version_at_least_p4(self):
        # Piso, não igualdade: P5 sobe para 16.0.8.4.0 e este teste continua verde.
        module = self.env["ir.module.module"].search([("name", "=", "afr_qualificacao")])
        version = tuple(int(part) for part in module.latest_version.split("."))
        self.assertGreaterEqual(version, (16, 0, 8, 3, 0))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioViews --stop-after-init --no-http`
Expected: FAIL — `'name="action_emitir"' not found`, versão `16.0.8.2.0`.

- [ ] **Step 3: Conferir o xmlid do form de P1**

Run: `grep -n 'id="view_afr_qualificacao_relatorio_form"' views/*.xml`
Expected: uma linha em `views/relatorio_views.xml`. Se o id for outro, usar o id encontrado no `inherit_id` abaixo.

- [ ] **Step 4: Criar `views/relatorio_emissao_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Emissões: somente leitura (imutáveis — ver models/relatorio_emissao.py) -->
    <record id="view_afr_relatorio_emissao_tree" model="ir.ui.view">
        <field name="name">afr.relatorio.emissao.tree</field>
        <field name="model">afr.relatorio.emissao</field>
        <field name="arch" type="xml">
            <tree create="0" edit="0" delete="0" decoration-muted="superseded">
                <field name="revision" string="Rev."/>
                <field name="issued_at"/>
                <field name="issued_by"/>
                <field name="sha256"/>
                <field name="superseded"/>
                <field name="pdf_attachment_id"/>
            </tree>
        </field>
    </record>

    <record id="view_afr_relatorio_emissao_form" model="ir.ui.view">
        <field name="name">afr.relatorio.emissao.form</field>
        <field name="model">afr.relatorio.emissao</field>
        <field name="arch" type="xml">
            <form create="0" edit="0" delete="0">
                <sheet>
                    <div class="oe_title"><h1><field name="name"/></h1></div>
                    <group>
                        <group>
                            <field name="relatorio_id"/>
                            <field name="revision"/>
                            <field name="issued_at"/>
                            <field name="issued_by"/>
                            <field name="superseded"/>
                        </group>
                        <group>
                            <field name="pdf_attachment_id"/>
                            <field name="token"/>
                            <field name="sha256"/>
                        </group>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <!-- Form do relatório (P1): ações de P4 no header + aba Revisões -->
    <record id="view_afr_qualificacao_relatorio_form_p4" model="ir.ui.view">
        <field name="name">afr.qualificacao.relatorio.form.p4.emissao</field>
        <field name="model">afr.qualificacao.relatorio</field>
        <field name="inherit_id" ref="afr_qualificacao.view_afr_qualificacao_relatorio_form"/>
        <field name="arch" type="xml">
            <xpath expr="//header/field[@name='state']" position="before">
                <button name="action_gerar_minuta" type="object" string="Gerar minuta"
                        groups="afr_qualificacao.group_afr_qualificacao_user"
                        confirm="A montagem do PDF junta todos os anexos e pode levar alguns minutos. Continuar?"/>
                <button name="action_aprovar_interno" type="object" string="Aprovar (meu papel)"
                        attrs="{'invisible': [('state', '!=', 'draft')]}"/>
                <button name="action_emitir" type="object" string="Emitir" class="btn-primary"
                        groups="afr_qualificacao.group_afr_qualificacao_manager"
                        attrs="{'invisible': [('state', '!=', 'draft')]}"
                        confirm="Emitir congela esta revisão (PDF, hash e QR). Continuar?"/>
                <button name="action_enviar_aprovacao_cliente" type="object"
                        string="Enviar para aprovação do cliente"
                        groups="afr_qualificacao.group_afr_qualificacao_user"
                        attrs="{'invisible': [('state', '!=', 'issued')]}"/>
                <button name="action_revisar" type="object" string="Revisar"
                        groups="afr_qualificacao.group_afr_qualificacao_manager"
                        attrs="{'invisible': [('state', '=', 'draft')]}"
                        confirm="Abrir uma nova revisão? A emissão atual continua vigente até a nova ser emitida."/>
            </xpath>
            <xpath expr="//notebook" position="inside">
                <page string="Revisões" name="page_revisoes">
                    <group>
                        <group>
                            <field name="revision_label" string="Revisão atual"/>
                            <field name="current_emissao_id"/>
                            <field name="verify_url" widget="url"/>
                        </group>
                        <group>
                            <field name="minuta_attachment_id"/>
                            <field name="proxima_qualificacao"/>
                        </group>
                    </group>
                    <field name="emissao_ids" readonly="1"
                           context="{'tree_view_ref': 'afr_qualificacao.view_afr_relatorio_emissao_tree'}"/>
                </page>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 5: Manifest**

Em `__manifest__.py`: `"version": "16.0.8.3.0",` e, na lista `data`, **antes** das duas linhas do Task 9 (fim da lista):

```python
        # Relatório Final P4 — botões de emissão + aba Revisões
        "views/relatorio_emissao_views.xml",
```

- [ ] **Step 6: Rodar a suíte do módulo inteira**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao --stop-after-init --no-http`
Expected: `TestRelatorioViews` PASS (3) e todas as classes P4 verdes (`TestRelatorioPdfCore` 13, `TestRelatorioAnexoFiles` 11, `TestRelatorioBuild` 13, [`TestRelatorioBuildFallback` 3 se o Task 6 rodou], `TestRelatorioEmissaoModel` 6, `TestRelatorioAprovacoes` 11, `TestRelatorioEmissaoFlow` 12, `TestRelatorioPublicoPortal` 10); únicas falhas as 3 pré-existentes do índice.

- [ ] **Step 7: Smoke de UI (agent-browser, sem delegar ao usuário)**

Pré: base de dev com o módulo atualizado (`-u afr_qualificacao`) e `docker restart` do container web para recarregar assets. Seguir `CLAUDE.md` do monorepo (logout antes de re-login).

```bash
agent-browser open http://localhost:8083/web/login
agent-browser snapshot -i          # preencher login/senha de um Gestor e entrar
# Qualificação → Relatórios Finais → abrir um relatório com template aplicado
agent-browser snapshot -i          # conferir botões: Gerar minuta, Aprovar (meu papel), Emitir; aba Revisões
# Gerar minuta → baixa PDF: conferir marca d'água, "Página X de Y", anexos após cada separador
# Aprovar (meu papel) como elaborador e emissor → Emitir → aba Revisões mostra Rev.00, SHA-256, URL
agent-browser open "<verify_url copiada da aba Revisões>"   # página pública: "Relatório válido"
```

Registrar no relatório da task: tempo de montagem da minuta com o maior relatório de exemplo disponível (risco §12 "Tamanho") e se o QR do PDF abre a página de verificação.

**Gate de desempenho (obrigatório antes de fechar P4; substituído pela §8 da emenda):** minuta e
emissão de um relatório com ~150 páginas de anexo sintéticas montadas pelo job, medindo cada invocação
de `_cron_process()` no shell Odoo: toda invocação < 30 s de CPU e < 60 s de parede, e o job termina
`done`.

- [ ] **Step 8: Commit**

```bash
git add views/relatorio_emissao_views.xml __manifest__.py tests/test_relatorio_emissao.py
git commit -m "feat(relatorio): emission buttons, revisions tab and bump 16.0.8.3.0"
```

---

## Self-Review (feita na escrita do plano)

**Cobertura da spec:**
- §4.5 anexos — `_resolve_files`/`_check_files` por `slot_kind`, imagem → página, ilegível/criptografado → problema, `bloco` no corpo (fato P3): Task 3; ordem física por `anexo_ids`: Task 5.
- §4.6 estados/revisão — `draft → issued → client_approved`, Revisar Rev.N+1, `superseded` só na nova emissão, emissão imutável, invalidação de aprovações internas por edição em rascunho: Tasks 4, 7, 8, 9.
- §4.7 aprovações — interna por papel (Task 7), cliente pelo portal com `approved_at`/`ip`/nome e `client_approved` (Task 9), hash preservado (teste do Task 9).
- §6 montagem — corpo com marcadores (dados no `data`), pdfminer, intercalação após o separador, re-render com `page_map` até 3 passagens + aviso, carimbo cabeçalho/rodapé "Página X de Y"/e-mails/QR/marca d'água, escala para área útil, minuta/emissão: Tasks 2, 3, 5, 8; fallback §12: Tasks 1 e 6.
- §8 — token antes do PDF, SHA-256, chatter, verificação pública (válido/substituído/adulterado + aprovações do cliente), portal: Tasks 8, 9.
- §9 UI — botões e aba Revisões: Task 10 (Verificar/badge/aba Verificação são de P5).
- §10 testes — PDF sintético, "Página X de Y" por página, marcadores invisíveis (brancos 1pt; extraídos mas não visíveis), hash, imutabilidade, revisão, portal token errado/certo: Tasks 2–9.
- `proxima_qualificacao` = emissão + 12 meses: Task 8.

**Nomes/assinaturas conferidos entre tasks:** `open_pdf`, `file_problem`, `fit_page_to_usable`, `image_to_pdf`, `stamp_pdf`, `find_markers`, `compute_layout`, `MAX_PASSES`, `REPORT_CORPO` (relatorio_pdf); `PROBLEM_EMPTY` (relatorio_anexo_files); `INTERNAL_CTX` (relatorio_emissao); `SKIP_CTX` (relatorio_editorial); `INTERNAL_ROLES`, `ROLE_LABELS`, `USER_GROUP` (relatorio_emissao_flow); `FakeCorpo.patch(env)`/`.calls[i]["data"|"context"|"report_ref"|"res_ids"]`, `RelatorioEmissaoBase._approve/_emit/_approve_and_emit/_revise_and_emit`.

**Contrato do índice:** todos os nomes de "P4 produz" existem com as assinaturas do índice; adições (`_build`, `_render_report`, `_render_body_and_markers`, `_file_anexos`, `_blocks_snapshot`, `_reset_client_approvals`, `_update_client_approval_state`, `_check_editable`, `action_enviar_aprovacao_cliente`, `portal_url`, `_portal_approve`) não conflitam com P5. P5 usa `FakeCorpo().patch(env)` + `run_build_jobs(env)` (emenda): `action_emitir` enfileira e o job monta pelo mesmo pipeline de `build`.
