# P3 — Template, blocos, anexos (posições), aprovações (registro) + corpo QWeb — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao `afr.qualificacao.relatorio` um texto montado por blocos (padrão da cotação), posições de anexo numeradas, registro de aprovações e o corpo do PDF em QWeb com marcadores de página, a partir de templates Hospitalar/Industrial semeados.

**Architecture:** A numeração hierárquica da cotação vira função pura (`models/_numbering.py`) usada pela cotação e pelo relatório. Novos modelos espelham `afr.proposal.template/line/block` (sem mixin, sem refatorar a cotação); a biblioteca de seções é a mesma (`afr.proposal.section`) com `document_type`. O relatório ganha, por `_inherit` num arquivo novo (`models/relatorio_texto.py`), `template_id`, `block_ids`, `anexo_ids`, `aprovacao_ids` e os métodos do contrato; o corpo (`report_relatorio_corpo`) percorre os blocos do texto e, depois, as posições de anexo **na ordem de `anexo_ids`**, emitindo marcadores `@@RQ:...@@` quando `with_markers` vem nos `data` do report.

**Tech Stack:** Odoo 16.0 (ORM, QWeb, `mail.render.mixin` engine `inline_template`), Python 3, wkhtmltopdf (só em P4).

**Spec:** `docs/superpowers/specs/2026-09-26-relatorio-final-qualificacao-design.md` (§4.5 posições/numeração, §4.7 registros, §5). Contrato de interfaces: `docs/superpowers/plans/2026-09-26-relatorio-final-00-indice.md` ("P3 produz"). Ler os dois antes de começar.

## Global Constraints

- Odoo **16.0**. Módulo `afr_qualificacao` é **git submodule** em `addons/afr_qualificacao/`. Trabalhar na branch `feat/relatorio-final` **dentro do submodule** (criada por P1 a partir de `main`).
- Commits: sempre de dentro de `addons/afr_qualificacao/`, via agente `git-commit-push` (haiku), paths relativos ao submodule. **Não** fazer push nem bump do pointer no monorepo sem o usuário pedir. Mensagens em inglês, Conventional Commits.
- Testes: via agente `test-runner` (sonnet) quando rodados pelo orquestrador. Comando base (copiado do índice):
  `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http`
  (`-u` obrigatório quando tocar XML; `--no-http` obrigatório). ⚠️ Em 2026-09-26 o container `odoo_engenapp-web-1` estava **parado**; o que roda é `odoo_engenapp-web-qualificacao-1`. O `test-runner` deve confirmar com `docker ps` qual container/db usar antes do primeiro run — não adivinhar o nome do banco.
  Falhas pré-existentes conhecidas: `TestResourcePlan.test_fleet_single_logger_two_temp_standards`, `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`, `TestProposalReport.test_render_schedule_block`.
- Novos testes herdam de `tests/common.py::AfrQualificacaoTestCommon` quando precisarem de SO/OS/equipamento; registrar cada novo arquivo em `tests/__init__.py`.
- Todo novo model: entrada em `models/__init__.py`, ACL em `security/ir.model.access.csv` (technician: read; user: read/write/create; manager: full), salvo indicação contrária (ver Task 3: templates são config → user só lê; blocos/anexos → user também apaga, porque "Recarregar template" apaga).
- Grupos: `afr_qualificacao.group_afr_qualificacao_technician`, `..._user`, `..._manager`.
- **Nunca** usar nomes de clientes, pessoas ou números de certificados reais dos exemplos em `dados_sensiveis/` em código, seeds, testes ou docs. Usar "Cliente Teste", "Eng. Responsável".
- `engc_os` está **congelado**: não editar nada em `engenapp/engc_os/`.
- PWA (`pwa/`) **não muda**.
- Não adicionar dependência pip.
- Manifest: `version` → `16.0.8.2.0`; seed novo ⇒ `migrations/16.0.8.2.0/post-migrate.py` chamando a mesma função do `hooks.py` (idempotente).
- Textos de UI e seeds em pt-BR. Seeds genéricos (sem cliente); **não fixar ano de edição de norma** (a edição varia por cliente).

## Decisões deste plano (leia antes de implementar)

1. **Token `anexo` continua callable** (`{{ anexo('micro') }}`), como no contrato. Verificado em `odoo/tools/safe_eval.py::check_values` do container: só rejeita valores `ModuleType`; chamar uma closure passada em `add_context` é permitido. Um teste (Task 6) prende isso com corpo salvo pelo ORM (sanitizado).
2. **`page_map` e `with_markers` chegam como chaves de `data`** do report (`_render_qweb_html(ref, ids, data={...})` / `_render_qweb_pdf(ref, ids, data={...})`), não por `env.context`: `ir.actions.report._get_rendering_context` copia `data` para as variáveis do template. P4 deve passar assim.
3. **Ordem física dos anexos = ordem de `anexo_ids` (sequence, id)**, não a posição do bloco `anexo_separador` na aba Texto. O corpo renderiza primeiro os blocos de texto (os que **não** têm `anexo_code`), depois, para cada anexo incluído: o separador ("Anexo N: título") e, se `slot_kind == 'bloco'`, o bloco de conteúdo (`anexo.block_id`). Assim número e posição nunca divergem. Anexos `bloco` têm o conteúdo **no corpo**; P4 não intercala arquivos para eles. Blocos de um anexo excluído continuam `included=True` mas **não** são renderizados — P4 deve derivar os marcadores esperados de `_body_blocks()` + `_anexos_included()` (+ `_anexo_separator_block(code)` e `anexo.block_id`), não de `block_ids.filtered("included")`.
4. **Marcadores dentro do container que quebra página.** `@@RQ:bloco:<id>@@` é o primeiro filho do `<div>` do bloco (que carrega `rq-page-break` quando `page_break`); o separador de anexo tem `page-break-before` **e** `page-break-after` e contém `@@RQ:anexo:<code>@@` (e o `@@RQ:bloco:<id>@@` do bloco separador, se existir). Assim o pdfminer de P4 acha o marcador na página certa e os arquivos intercalados entram logo após a página do separador.
5. **`_apply_template()` não roda no `create()` nem em `action_generate_relatorios()`** — o teste de P1 `test_seed_checklist_creates_lines_in_order` gera relatórios com `action_generate_relatorios()` e espera checklist vazio; como o seed de P3 existe no banco de teste, aplicar ali quebraria P1. `create()` só sugere `template_id`; o `_apply_template()` roda no wrapper de UI `afr.qualificacao.os.action_generate_relatorios_open()` (override com `super()`, P1 Task de views) e no botão "Recarregar template". Código que gera relatórios programaticamente (P4, P5) chama `rel._apply_template()` explicitamente — P4 já faz isso.
6. **Um token inválido não derruba o corpo**: `_render_block_body` captura o `UserError` do `inline_template` e devolve o corpo cru (com `{{`), para P5 (`TOKEN_NAO_RESOLVIDO`) acusar.
7. Hook de instalação real do manifest é `_install_proposal_template_seed` (não `post_init_hook`) e ele **retorna cedo** quando o template da proposta já existe; `_seed_relatorio_templates(env)` é chamado **no topo**, antes desse `return`.
8. Anexos semeados sem fonte automática confiável (`graficos`, `f0`, `impressoes`, `protocolo_cliente`, `micro` industrial) usam `slot_kind='upload'` (o escritório anexa os PDFs); `dados` usa `collect_section` com `qo_mapeamento_ciclo1..3,qd_penetracao_ciclo1..3`. O bucket genérico `anexos` **não** é usado (misturaria arquivos quaisquer). Industrial semeia 10 posições (o exemplo analisado tinha 9); o escritório desliga as que não se aplicam.

## Review Focus

- **Token inválido num bloco** (`{{ relatorio.campo_que_nao_existe }}`, aspas quebradas): o corpo inteiro ainda renderiza e o bloco sai cru com `{{` — nunca uma exceção na geração da minuta. Testes: Task 6 `test_bad_token_falls_back_to_raw_body`, Task 7 `test_bad_token_does_not_break_render`.
- **Anexo desligado que o texto referencia**: excluir `dados` renumera os seguintes (sem buracos) e `{{ anexo('dados') }}` vira `""`; o separador e os marcadores dele somem do corpo. Testes: Task 5 `test_anexo_numbering_skips_excluded`, Task 6 `test_render_tokens_criterio_and_anexo`, Task 7 `test_excluded_anexo_not_rendered`.
- **Marcador fora do container de quebra**: se o span ficar antes do `<div>` com `page-break-before`, P4 atribui o bloco à página anterior. Testes: Task 7 `test_marker_inside_page_break_container`, `test_anexo_separator_breaks_both_sides`.
- **Usuário comum (grupo Usuário, sem "Mail Template Editor") gerando o corpo**: `inline_template` levanta `AccessError` sem `sudo()`. Teste: Task 6 `test_render_as_plain_user`.
- **"Recarregar template" fora do rascunho / reaplicar em cima de edições**: reaplicar é idempotente (não duplica blocos, anexos, checklist, aprovações) e o recarregamento destrutivo é bloqueado fora de `draft`. Testes: Task 5 `test_apply_template_is_idempotent`, `test_reload_blocked_outside_draft`.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `models/_numbering.py` | Criar | `hierarchical_numbering(records)`, `sort_key(record)` — puros |
| `models/sale_order.py` | Modificar (`_proposal_block_numbering`, ~l.1070-1110) | usa a função |
| `models/proposal_template.py` | Modificar (`_compute_display_number`, `section_id` domain) | usa a função; domínio `proposal` |
| `models/proposal_section.py` | Modificar | campo `document_type` |
| `views/proposal_section_views.xml`, `views/proposal_template_views.xml` | Modificar | coluna/filtro/domínio `document_type` |
| `models/relatorio_template.py` | Criar | `REPORT_BLOCK_KINDS`, `ANEXO_SLOT_KINDS`, template, line, checklist line, anexo line |
| `models/relatorio_block.py` | Criar | `afr.relatorio.block` |
| `models/relatorio_anexo.py` | Criar | `afr.relatorio.anexo` (+ `numero`) |
| `models/relatorio_aprovacao.py` | Criar | `afr.relatorio.aprovacao` |
| `models/relatorio_texto.py` | Criar | `_inherit` do relatório (campos + métodos do contrato + helpers do corpo) e override de `afr.qualificacao.os.action_generate_relatorios_open` |
| `models/__init__.py` | Modificar | imports |
| `security/ir.model.access.csv` | Modificar | ACLs |
| `views/relatorio_template_views.xml` | Criar | config: templates, seções de relatório, menus |
| `views/relatorio_texto_views.xml` | Criar | páginas `page_texto`, `page_anexos`, `page_aprovacoes`; form do bloco |
| `reports/relatorio_corpo_report.xml` | Criar | paperformat + `ir.actions.report` |
| `reports/relatorio_corpo_templates.xml` | Criar | `report_relatorio_corpo` + sub-templates `rq_*` |
| `hooks.py` | Modificar | `RELATORIO_SECTIONS`, `RELATORIO_TEMPLATES`, `_seed_relatorio_templates(env)`; chamada no hook de install |
| `migrations/16.0.8.2.0/post-migrate.py` | Criar | chama o seed |
| `__manifest__.py` | Modificar | versão + data files |
| `tests/test_relatorio_template.py` | Criar | Tasks 1–6 |
| `tests/test_relatorio_corpo_report.py` | Criar | Task 7 |
| `tests/__init__.py` | Modificar | registrar os dois |

**Dependência de P1 a confirmar (Task 5, Step 1):** o xmlid do form do relatório. Este plano assume `afr_qualificacao.view_afr_qualificacao_relatorio_form` em `views/relatorio_views.xml`. Se P1 usou outro, trocar **só** o `ref`/o nome do arquivo nos pontos indicados.

---

### Task 1: Numeração hierárquica compartilhada

**Files:**
- Create: `models/_numbering.py`
- Modify: `models/sale_order.py` (`_proposal_block_numbering`, ~l.1070-1110; import no topo)
- Modify: `models/proposal_template.py` (`AfrProposalTemplateLine._compute_display_number`, ~l.233-287)
- Create: `tests/test_relatorio_template.py`
- Modify: `tests/__init__.py`

**Interfaces:**
- Consumes: nada.
- Produces: `models/_numbering.py::hierarchical_numbering(records) -> dict[id, str]` (itera qualquer iterável de objetos com `sequence`, `id`, `parent_id` (com `.id`, falsy quando vazio), `show_number`; ordena por `(sequence, id)` com NewId → `id.origin or 0`; **não** filtra `included`); `sort_key(record) -> tuple`.

- [ ] **Step 1: Escrever os testes (função pura + paridade ORM)**

Criar `tests/test_relatorio_template.py`:

```python
"""P3 — template/blocos/anexos/aprovações do Relatório Final."""

from types import SimpleNamespace

from odoo.tests.common import TransactionCase

from odoo.addons.afr_qualificacao.models._numbering import hierarchical_numbering

from .common import AfrQualificacaoTestCommon


def _rec(rid, seq, parent=None, show=True):
    return SimpleNamespace(id=rid, sequence=seq, parent_id=parent, show_number=show)


class _FakeNewId:
    """Imita odoo.models.NewId: não é int, expõe `origin`."""

    def __init__(self, origin):
        self.origin = origin

    def __hash__(self):
        return id(self)


class TestHierarchicalNumbering(TransactionCase):

    def _tree(self):
        a = _rec(1, 10)
        b = _rec(2, 20, show=False)
        c = _rec(3, 30, parent=a)
        g = _rec(7, 35, parent=b)
        d = _rec(4, 40, parent=a, show=False)
        e = _rec(5, 50, parent=c)
        f = _rec(6, 60)
        return [f, e, d, g, c, b, a]  # fora de ordem de propósito

    def test_nesting_hidden_and_orphan_child(self):
        numbers = hierarchical_numbering(self._tree())
        self.assertEqual(numbers, {
            1: "1", 2: "", 3: "1.1", 7: "1", 4: "", 5: "1.1.1", 6: "2",
        })

    def test_ties_broken_by_id(self):
        x = _rec(9, 10)
        y = _rec(8, 10)
        self.assertEqual(hierarchical_numbering([x, y]), {8: "1", 9: "2"})

    def test_newid_sorted_by_origin(self):
        nid = _FakeNewId(origin=3)
        late = SimpleNamespace(id=nid, sequence=10, parent_id=None, show_number=True)
        early = _rec(2, 10)
        numbers = hierarchical_numbering([late, early])
        self.assertEqual(numbers[2], "1")
        self.assertEqual(numbers[nid], "2")

    def test_empty(self):
        self.assertEqual(hierarchical_numbering([]), {})


class TestNumberingParity(AfrQualificacaoTestCommon):
    """Cotação (template + blocos) mantém exatamente a numeração antiga."""

    def _build_template(self):
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Numeração"})
        Line = self.env["afr.proposal.template.line"]

        def mk(seq, parent=False, show=True):
            return Line.create({
                "template_id": tpl.id, "sequence": seq, "block_kind": "schedule",
                "parent_id": parent.id if parent else False, "show_number": show,
            })
        a = mk(10)
        b = mk(20, show=False)
        c = mk(30, parent=a)
        g = mk(35, parent=b)
        d = mk(40, parent=a, show=False)
        e = mk(50, parent=c)
        f = mk(60)
        return tpl, dict(a=a, b=b, c=c, g=g, d=d, e=e, f=f)

    def test_template_line_display_number(self):
        tpl, L = self._build_template()
        got = {k: v.display_number for k, v in L.items()}
        self.assertEqual(got, {
            "a": "1", "b": "", "c": "1.1", "g": "1", "d": "", "e": "1.1.1", "f": "2",
        })

    def test_sale_order_numbering_with_excluded_block(self):
        tpl, L = self._build_template()
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id, "proposal_template_id": tpl.id,
        })
        so.action_reload_proposal_blocks()
        by_seq = {b.sequence: b for b in so.proposal_block_ids}
        numbers = so._proposal_block_numbering()
        self.assertEqual(numbers[by_seq[50].id], "1.1.1")
        self.assertEqual(numbers[by_seq[60].id], "2")
        # Excluir o bloco raiz A: comportamento legado preservado
        by_seq[10].included = False
        numbers = so._proposal_block_numbering()
        self.assertNotIn(by_seq[10].id, numbers)
        self.assertEqual(numbers[by_seq[30].id], "1")
        self.assertEqual(numbers[by_seq[35].id], "1")
        self.assertEqual(numbers[by_seq[40].id], "")
        self.assertEqual(numbers[by_seq[50].id], "1.1")
        self.assertEqual(numbers[by_seq[60].id], "1")
        self.assertEqual(numbers[by_seq[20].id], "")
```

Adicionar ao final de `tests/__init__.py`:

```python

# Relatório Final — P3: template, blocos, anexos, aprovações
from . import test_relatorio_template
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestHierarchicalNumbering --stop-after-init --no-http`
Expected: FAIL/ERROR com `ModuleNotFoundError: No module named 'odoo.addons.afr_qualificacao.models._numbering'`.

- [ ] **Step 3: Implementar `models/_numbering.py`**

```python
"""Numeração hierárquica compartilhada (cotação e relatório final).

Função pura: não depende do ORM. Recebe qualquer iterável de objetos com
`sequence`, `id`, `parent_id` (objeto com `.id`, falsy quando vazio) e
`show_number`. Quem chama decide o que entra (ex.: só blocos `included`).
"""


def sort_key(record):
    """(sequence, id) — NewId (registro virtual de onchange) usa `origin` ou 0."""
    rec_id = record.id
    if not isinstance(rec_id, int):
        rec_id = getattr(rec_id, "origin", 0) or 0
    return (record.sequence, rec_id)


def hierarchical_numbering(records):
    """Retorna {record.id: '1' | '3.1' | '1.1.1' | ''}.

    Registros com show_number=False recebem ''. Filho de pai sem número (ou
    de pai fora do conjunto) numera a partir de 1 sem prefixo — comportamento
    histórico da cotação, mantido sem mudança.
    """
    numbers = {}
    root_counter = 0
    child_counters = {}
    for rec in sorted(records, key=sort_key):
        if not rec.parent_id:
            if rec.show_number:
                root_counter += 1
                numbers[rec.id] = str(root_counter)
                child_counters[rec.id] = 0
            else:
                numbers[rec.id] = ""
        else:
            pid = rec.parent_id.id
            child_counters.setdefault(pid, 0)
            if rec.show_number:
                child_counters[pid] += 1
                parent_num = numbers.get(pid, "")
                numbers[rec.id] = (
                    f"{parent_num}.{child_counters[pid]}"
                    if parent_num
                    else str(child_counters[pid])
                )
            else:
                numbers[rec.id] = ""
    return numbers
```

- [ ] **Step 4: Trocar a cotação para usar a função**

Em `models/sale_order.py`, junto aos imports do topo (depois dos `from odoo ...`):

```python
from ._numbering import hierarchical_numbering
```

Substituir o corpo inteiro de `_proposal_block_numbering` (manter docstring) por:

```python
    def _proposal_block_numbering(self):
        """Retorna dict {block_id: 'número_hierárquico'} para todos os blocos incluídos.

        Ex: {1: '1', 2: '2', 3: '3', 4: '3.1', 5: '3.2', 6: '3.3', 7: '4'}
        Blocos com show_number=False recebem string vazia ''.
        Suporta profundidade arbitrária (1, 1.1, 1.1.1, …).
        Implementação em models/_numbering.py (compartilhada com o relatório final).
        """
        self.ensure_one()
        return hierarchical_numbering(self.proposal_block_ids.filtered("included"))
```

Em `models/proposal_template.py`, import no topo:

```python
from ._numbering import hierarchical_numbering
```

e substituir o corpo de `AfrProposalTemplateLine._compute_display_number` (manter decorator `@api.depends` e docstring) por:

```python
        for line in self:
            line.display_number = ""
        for template in self.mapped("template_id"):
            numbers = hierarchical_numbering(template.line_ids)
            for line in template.line_ids:
                line.display_number = numbers.get(line.id, "")
```

- [ ] **Step 5: Rodar os testes novos + regressão da cotação**

Run (um por vez, ou tags separadas por vírgula):
`docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestHierarchicalNumbering,/afr_qualificacao:TestNumberingParity,/afr_qualificacao:TestProposalReport,/afr_qualificacao:TestProposalBuilder,/afr_qualificacao:TestProposalBlockEdit,/afr_qualificacao:TestScopeRef --stop-after-init --no-http`
Expected: PASS em tudo, exceto as 2 falhas pré-existentes conhecidas de `TestProposalReport` (`test_render_equipment_scope_omits_cronograma_footer`, `test_render_schedule_block`). `TestScopeRef` cobre `_qualif_scope_ref`, que consome a numeração.

- [ ] **Step 6: Commit** (agente `git-commit-push`, cwd `addons/afr_qualificacao`)

```bash
git add models/_numbering.py models/sale_order.py models/proposal_template.py tests/test_relatorio_template.py tests/__init__.py
git commit -m "refactor: extract hierarchical numbering into shared pure function"
```

---

### Task 2: `document_type` na biblioteca de seções + filtro na cotação

**Files:**
- Modify: `models/proposal_section.py`
- Modify: `models/proposal_template.py` (`AfrProposalTemplateLine.section_id`)
- Modify: `views/proposal_section_views.xml`, `views/proposal_template_views.xml`
- Test: `tests/test_relatorio_template.py`

**Interfaces:**
- Consumes: —
- Produces: `afr.proposal.section.document_type` Selection `[("proposal","Proposta"),("report","Relatório")]` default `proposal`; constante `SECTION_DOCUMENT_TYPES` em `models/proposal_section.py`. `afr.proposal.template.line.section_id` com `domain=[("document_type", "=", "proposal")]`. `action_proposal_section` só lista `proposal`.

- [ ] **Step 1: Escrever o teste**

Acrescentar em `tests/test_relatorio_template.py`:

```python
class TestSectionDocumentType(TransactionCase):

    def test_default_is_proposal(self):
        sec = self.env["afr.proposal.section"].create({"name": "Sec X"})
        self.assertEqual(sec.document_type, "proposal")

    def test_existing_seed_sections_are_proposal(self):
        sec = self.env.ref("afr_qualificacao.proposal_section_objetivo")
        self.assertEqual(sec.document_type, "proposal")

    def test_quote_line_domain_only_offers_proposal_sections(self):
        field = self.env["afr.proposal.template.line"]._fields["section_id"]
        self.assertEqual(field.domain, [("document_type", "=", "proposal")])

    def test_quote_section_action_filters_proposal(self):
        action = self.env.ref("afr_qualificacao.action_proposal_section")
        self.assertIn("document_type", action.domain or "")
        self.assertIn("proposal", action.domain or "")

    def test_quote_views_filter_section_by_document_type(self):
        arch = self.env.ref("afr_qualificacao.view_proposal_template_form").arch_db
        self.assertIn("('document_type', '=', 'proposal')", arch)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestSectionDocumentType --stop-after-init --no-http`
Expected: FAIL (`AttributeError`/`KeyError` em `document_type`).

- [ ] **Step 3: Implementar o campo**

Em `models/proposal_section.py`, depois de `PROPOSAL_SECTION_CATEGORIES`:

```python
# Biblioteca única de seções: proposta (cotação) e relatório final (P3).
SECTION_DOCUMENT_TYPES = [
    ("proposal", "Proposta"),
    ("report", "Relatório"),
]
```

e na classe, depois de `category`:

```python
    document_type = fields.Selection(
        selection=SECTION_DOCUMENT_TYPES,
        string="Documento",
        default="proposal",
        required=True,
        index=True,
        help=(
            "Em qual documento a seção pode ser usada. A cotação só oferece "
            "seções de Proposta; o relatório final, só de Relatório."
        ),
    )
```

Em `models/proposal_template.py`, no `section_id` de `AfrProposalTemplateLine`, acrescentar o parâmetro:

```python
        domain=[("document_type", "=", "proposal")],
```

- [ ] **Step 4: Views da cotação**

Em `views/proposal_template_views.xml`, nos **dois** `<field name="section_id" .../>` (tree editável do `view_proposal_template_form` e `view_proposal_template_line_form`), acrescentar o atributo:

```xml
domain="[('document_type', '=', 'proposal')]"
```

Em `views/proposal_section_views.xml`:
- no tree, depois de `<field name="category"/>`: `<field name="document_type" optional="show"/>`
- no form, depois de `<field name="category"/>`: `<field name="document_type"/>`
- substituir o `action_proposal_section` por:

```xml
    <record id="action_proposal_section" model="ir.actions.act_window">
        <field name="name">Blocos de Proposta</field>
        <field name="res_model">afr.proposal.section</field>
        <field name="view_mode">tree,form</field>
        <field name="domain">[('document_type', '=', 'proposal')]</field>
        <field name="context">{'default_document_type': 'proposal'}</field>
    </record>
```

- [ ] **Step 5: Rodar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestSectionDocumentType,/afr_qualificacao:TestProposalCatalog --stop-after-init --no-http`
Expected: PASS. (A coluna nova é `required` com default: registros antigos recebem `proposal` no `-u`.)

- [ ] **Step 6: Commit**

```bash
git add models/proposal_section.py models/proposal_template.py views/proposal_section_views.xml views/proposal_template_views.xml tests/test_relatorio_template.py
git commit -m "feat: add document_type to proposal sections and filter quote to proposal"
```

---

### Task 3: Modelos de template, bloco, anexo, aprovação + ACL + telas de configuração

**Files:**
- Create: `models/relatorio_template.py`, `models/relatorio_block.py`, `models/relatorio_anexo.py`, `models/relatorio_aprovacao.py`, `models/relatorio_texto.py` (esqueleto)
- Modify: `models/__init__.py`, `security/ir.model.access.csv`, `__manifest__.py` (data)
- Create: `views/relatorio_template_views.xml`
- Test: `tests/test_relatorio_template.py`

**Interfaces:**
- Consumes: `hierarchical_numbering`, `sort_key` (Task 1); `document_type` (Task 2); model `afr.qualificacao.relatorio` (P1).
- Produces: `REPORT_BLOCK_KINDS`, `ANEXO_SLOT_KINDS` (`models/relatorio_template.py`); models `afr.relatorio.template`, `afr.relatorio.template.line`, `afr.relatorio.template.checklist.line`, `afr.relatorio.template.anexo.line`, `afr.relatorio.block`, `afr.relatorio.anexo` (`numero` compute), `afr.relatorio.aprovacao` (gera `access_token` uuid4 hex para `papel='cliente'` no create); actions `action_relatorio_template`, `action_relatorio_section`; menu `menu_afr_relatorio_config`; em `afr.qualificacao.relatorio` (esqueleto): `template_id`, `block_ids`, `anexo_ids`, `aprovacao_ids`, `_body_blocks()`, `_block_numbering()`, `_anexos_included()`. `afr.relatorio.block.action_edit_block()` referencia `afr_qualificacao.view_relatorio_block_form` (criado na Task 5 — até lá o método não é chamado por teste).

- [ ] **Step 1: Escrever os testes**

Acrescentar em `tests/test_relatorio_template.py`:

```python
from odoo.exceptions import ValidationError


class TestRelatorioTemplateModels(TransactionCase):

    def setUp(self):
        super().setUp()
        self.section = self.env["afr.proposal.section"].create({
            "name": "Objetivo RQ", "document_type": "report", "body": "<p>x</p>",
        })
        self.tpl = self.env["afr.relatorio.template"].create({
            "name": "Tpl Teste", "code": "RQT-TESTE",
        })

    def test_line_section_domain_is_report(self):
        field = self.env["afr.relatorio.template.line"]._fields["section_id"]
        self.assertEqual(field.domain, [("document_type", "=", "report")])

    def test_block_kinds(self):
        from odoo.addons.afr_qualificacao.models.relatorio_template import REPORT_BLOCK_KINDS
        self.assertEqual(
            [k for k, _l in REPORT_BLOCK_KINDS],
            ["static", "capa", "indice", "protocolo", "laudo_micro",
             "assinaturas", "anexo_separador"],
        )

    def test_static_line_requires_section(self):
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.template.line"].create({
                "template_id": self.tpl.id, "block_kind": "static",
            })

    def test_separator_line_requires_anexo_code(self):
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.template.line"].create({
                "template_id": self.tpl.id, "block_kind": "anexo_separador",
            })

    def test_template_line_display_number(self):
        Line = self.env["afr.relatorio.template.line"]
        root = Line.create({"template_id": self.tpl.id, "sequence": 10,
                            "block_kind": "static", "section_id": self.section.id})
        child = Line.create({"template_id": self.tpl.id, "sequence": 20,
                             "block_kind": "static", "section_id": self.section.id,
                             "parent_id": root.id})
        capa = Line.create({"template_id": self.tpl.id, "sequence": 5,
                            "block_kind": "capa", "show_number": False})
        self.assertEqual((capa.display_number, root.display_number, child.display_number),
                         ("", "1", "1.1"))

    def test_client_approval_gets_token(self):
        # afr.relatorio.aprovacao exige relatorio_id; testado com relatório real
        # na Task 5 (TestRelatorioApplyTemplate.test_default_approvals).
        field = self.env["afr.relatorio.aprovacao"]._fields["papel"]
        self.assertEqual([k for k, _l in field.selection],
                         ["elaborador", "emissor", "executor", "cliente"])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioTemplateModels --stop-after-init --no-http`
Expected: ERROR `KeyError: 'afr.relatorio.template'`.

- [ ] **Step 3: `models/relatorio_template.py`**

```python
"""Template do Relatório Final de Qualificação (P3).

Espelha afr.proposal.template/line (sem mixin — decisão do spec §5): um
template é a lista ordenada de blocos do texto + checklist padrão + posições
de anexo padrão. `_apply_template()` do relatório copia tudo para registros
editáveis por relatório.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ._numbering import hierarchical_numbering

REPORT_BLOCK_KINDS = [
    ("static", "Bloco de Texto"),
    ("capa", "Capa"),
    ("indice", "Índice"),
    ("protocolo", "Protocolo (PrQT)"),
    ("laudo_micro", "Laudo Microbiológico (ReQM)"),
    ("assinaturas", "Quadro de Assinaturas"),
    ("anexo_separador", "Separador de Anexo"),
]

ANEXO_SLOT_KINDS = [
    ("collect_section", "Itens de coleta (por seção)"),
    ("instrument_certs", "Certificados de instrumentos"),
    ("malha_certs", "Certificados das malhas"),
    ("bloco", "Bloco do relatório"),
    ("upload", "Arquivos anexados"),
]


class AfrRelatorioTemplate(models.Model):
    _name = "afr.relatorio.template"
    _description = "Template de Relatório Final"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    line_ids = fields.One2many(
        "afr.relatorio.template.line", "template_id", string="Blocos", copy=True)
    checklist_line_ids = fields.One2many(
        "afr.relatorio.template.checklist.line", "template_id",
        string="Checklist padrão", copy=True)
    anexo_line_ids = fields.One2many(
        "afr.relatorio.template.anexo.line", "template_id",
        string="Anexos padrão", copy=True)
    equipment_category_ids = fields.Many2many(
        "engc.equipment.category",
        relation="afr_relatorio_template_equip_category_rel",
        column1="template_id", column2="category_id",
        string="Categorias de equipamento",
        help="O relatório sugere o template cuja categoria bate com a do equipamento.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)


class AfrRelatorioTemplateLine(models.Model):
    _name = "afr.relatorio.template.line"
    _description = "Bloco do Template de Relatório"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "afr.relatorio.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    block_kind = fields.Selection(
        REPORT_BLOCK_KINDS, string="Tipo de Bloco", required=True, default="static")
    section_id = fields.Many2one(
        "afr.proposal.section", string="Seção de Texto", ondelete="restrict",
        domain=[("document_type", "=", "report")],
        help="Obrigatória em Bloco de Texto; opcional nos dinâmicos (texto após as tabelas).",
    )
    page_break = fields.Boolean(string="Nova Página", default=False)
    title = fields.Char(string="Título", translate=True)
    parent_id = fields.Many2one(
        "afr.relatorio.template.line", string="Linha Pai", ondelete="set null",
        domain="[('template_id', '=', template_id), ('id', '!=', id)]")
    show_number = fields.Boolean(string="Numerado", default=True)
    show_title = fields.Boolean(string="Titulado", default=True)
    anexo_code = fields.Char(
        string="Código do anexo",
        help="Liga o bloco a uma posição de anexo (separador ou conteúdo do anexo 'bloco').",
    )
    display_label = fields.Char(compute="_compute_display_label", string="Conteúdo")
    display_number = fields.Char(compute="_compute_display_number", string="Nº")

    @api.depends("title", "section_id", "block_kind")
    def _compute_display_label(self):
        labels = dict(REPORT_BLOCK_KINDS)
        for line in self:
            line.display_label = (
                line.title or line.section_id.name or labels.get(line.block_kind, ""))

    @api.depends(
        "template_id", "sequence", "parent_id", "show_number",
        "template_id.line_ids.sequence", "template_id.line_ids.parent_id",
        "template_id.line_ids.show_number",
    )
    def _compute_display_number(self):
        for line in self:
            line.display_number = ""
        for template in self.mapped("template_id"):
            numbers = hierarchical_numbering(template.line_ids)
            for line in template.line_ids:
                line.display_number = numbers.get(line.id, "")

    @api.constrains("block_kind", "section_id")
    def _check_static_has_section(self):
        for rec in self:
            if rec.block_kind == "static" and not rec.section_id:
                raise ValidationError(_("Bloco de texto exige uma Seção de Texto selecionada."))

    @api.constrains("block_kind", "anexo_code")
    def _check_separator_has_code(self):
        for rec in self:
            if rec.block_kind == "anexo_separador" and not rec.anexo_code:
                raise ValidationError(_("Separador de anexo exige o código do anexo."))

    def action_edit_template_line(self):
        """Abre a seção (static) ou a própria linha em modal — igual à cotação."""
        self.ensure_one()
        if self.block_kind == "static" and self.section_id:
            return {
                "type": "ir.actions.act_window", "name": _("Editar Seção"),
                "res_model": "afr.proposal.section", "res_id": self.section_id.id,
                "view_mode": "form", "target": "new",
            }
        return {
            "type": "ir.actions.act_window", "name": _("Editar Linha do Template"),
            "res_model": "afr.relatorio.template.line", "res_id": self.id,
            "view_mode": "form", "target": "new",
        }


class AfrRelatorioTemplateChecklistLine(models.Model):
    _name = "afr.relatorio.template.checklist.line"
    _description = "Item de Checklist Padrão do Template de Relatório"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "afr.relatorio.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    grupo = fields.Char(required=True)
    descricao = fields.Char(string="Descrição", required=True)


class AfrRelatorioTemplateAnexoLine(models.Model):
    _name = "afr.relatorio.template.anexo.line"
    _description = "Posição de Anexo Padrão do Template de Relatório"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "afr.relatorio.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(required=True, help="Chave estável usada pelo token anexo('code').")
    title = fields.Char(string="Título", required=True, translate=True)
    slot_kind = fields.Selection(ANEXO_SLOT_KINDS, string="Origem", required=True, default="upload")
    collect_sections = fields.Char(
        string="Seções de coleta", help="docx_section separados por vírgula.")
    cert_roles = fields.Char(
        string="Papéis de certificado", help="afr_role separados por vírgula (antes,depois,externo).")
    included_default = fields.Boolean(string="Incluído por padrão", default=True)
```

- [ ] **Step 4: `models/relatorio_block.py`**

```python
"""Bloco do texto de um Relatório Final (cópia editável do template)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .relatorio_template import REPORT_BLOCK_KINDS


class AfrRelatorioBlock(models.Model):
    _name = "afr.relatorio.block"
    _description = "Bloco do Relatório Final"
    _order = "sequence, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    block_kind = fields.Selection(
        REPORT_BLOCK_KINDS, string="Tipo de Bloco", required=True, default="static")
    section_id = fields.Many2one(
        "afr.proposal.section", string="Seção de Origem", ondelete="set null",
        domain=[("document_type", "=", "report")])
    title = fields.Char(string="Título")
    body = fields.Html(
        string="Conteúdo", sanitize=True,
        help="Aceita {{ expressões }}: relatorio, os, partner, equipment, company, "
             "criterio['tolerancia'|'f0_fator'|'f0_minimo'|'valor_d'], anexo('code').")
    included = fields.Boolean(string="Incluir", default=True)
    page_break = fields.Boolean(string="Nova Página", default=False)
    parent_id = fields.Many2one(
        "afr.relatorio.block", string="Bloco Pai", ondelete="set null", index=True,
        domain="[('relatorio_id', '=', relatorio_id), ('id', '!=', id)]")
    show_number = fields.Boolean(string="Numerado", default=True)
    show_title = fields.Boolean(string="Titulado", default=True)
    anexo_code = fields.Char(string="Código do anexo")
    display_label = fields.Char(compute="_compute_display_label", string="Conteúdo")
    display_number = fields.Char(compute="_compute_display_number", string="Nº")

    @api.depends("title", "section_id", "block_kind")
    def _compute_display_label(self):
        labels = dict(REPORT_BLOCK_KINDS)
        for block in self:
            block.display_label = (
                block.title or block.section_id.name or labels.get(block.block_kind, ""))

    @api.depends(
        "relatorio_id", "sequence", "parent_id", "show_number", "included", "anexo_code",
        "relatorio_id.block_ids.sequence", "relatorio_id.block_ids.parent_id",
        "relatorio_id.block_ids.show_number", "relatorio_id.block_ids.included",
    )
    def _compute_display_number(self):
        for block in self:
            block.display_number = ""
        for rel in self.mapped("relatorio_id"):
            numbers = rel._block_numbering()
            for block in rel.block_ids:
                block.display_number = numbers.get(block.id, "")

    @api.constrains("parent_id")
    def _check_no_cycle(self):
        for rec in self:
            seen = {rec.id}
            ancestor = rec.parent_id
            while ancestor:
                if ancestor.id in seen:
                    raise ValidationError(
                        _("Hierarquia circular detectada no bloco '%s'.") % (rec.title or rec.id))
                seen.add(ancestor.id)
                ancestor = ancestor.parent_id

    def name_get(self):
        labels = dict(REPORT_BLOCK_KINDS)
        return [(r.id, r.title or labels.get(r.block_kind, r.block_kind or "")) for r in self]

    def action_edit_block(self):
        """Abre o bloco em modal. Só blocos de texto têm corpo livre; nos
        dinâmicos o corpo é um texto opcional exibido após as tabelas."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Editar Bloco do Relatório"),
            "res_model": "afr.relatorio.block",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref("afr_qualificacao.view_relatorio_block_form").id, "form")],
            "target": "new",
        }
```

- [ ] **Step 5: `models/relatorio_anexo.py`**

```python
"""Posição de anexo do Relatório Final (P3: posições e numeração).

Resolução de arquivos (`_resolve_files`, `_check_files`) é de P4.
"""

from odoo import api, fields, models

from ._numbering import sort_key
from .relatorio_template import ANEXO_SLOT_KINDS


class AfrRelatorioAnexo(models.Model):
    _name = "afr.relatorio.anexo"
    _description = "Anexo do Relatório Final"
    _order = "sequence, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    included = fields.Boolean(string="Incluir", default=True)
    code = fields.Char(required=True)
    title = fields.Char(string="Título", required=True)
    slot_kind = fields.Selection(ANEXO_SLOT_KINDS, string="Origem", required=True, default="upload")
    collect_sections = fields.Char(string="Seções de coleta")
    cert_roles = fields.Char(string="Papéis de certificado")
    block_id = fields.Many2one(
        "afr.relatorio.block", string="Bloco", ondelete="set null",
        domain="[('relatorio_id', '=', relatorio_id)]")
    attachment_ids = fields.Many2many(
        "ir.attachment", relation="afr_relatorio_anexo_attachment_rel",
        column1="anexo_id", column2="attachment_id", string="Arquivos")
    numero = fields.Integer(string="Nº", compute="_compute_numero")

    @api.depends(
        "included", "sequence",
        "relatorio_id.anexo_ids.included", "relatorio_id.anexo_ids.sequence",
    )
    def _compute_numero(self):
        """1..N sobre os incluídos, na ordem (sequence, id); excluído = 0."""
        for anexo in self:
            anexo.numero = 0
        for rel in self.mapped("relatorio_id"):
            n = 0
            for anexo in rel.anexo_ids.sorted(sort_key):
                if anexo.included:
                    n += 1
                    anexo.numero = n
                else:
                    anexo.numero = 0
```

- [ ] **Step 6: `models/relatorio_aprovacao.py`**

```python
"""Registro de aprovações do Relatório Final (P3: só o registro).

Fluxo de aprovação (botões, portal, gate) é de P4.
"""

import uuid

from odoo import api, fields, models

APROVACAO_PAPEIS = [
    ("elaborador", "Elaborador"),
    ("emissor", "Emissor / Responsável Técnico"),
    ("executor", "Executor"),
    ("cliente", "Cliente"),
]


class AfrRelatorioAprovacao(models.Model):
    _name = "afr.relatorio.aprovacao"
    _description = "Aprovação do Relatório Final"
    _order = "sequence, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    papel = fields.Selection(APROVACAO_PAPEIS, required=True)
    user_id = fields.Many2one("res.users", string="Usuário")
    partner_id = fields.Many2one("res.partner", string="Contato")
    nome_exibicao = fields.Char(string="Nome no relatório")
    registro = fields.Char(string="Registro (CREA etc.)")
    approved_at = fields.Datetime(string="Aprovado em", readonly=True, copy=False)
    ip = fields.Char(readonly=True, copy=False)
    access_token = fields.Char(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("papel") == "cliente" and not vals.get("access_token"):
                vals["access_token"] = uuid.uuid4().hex
        return super().create(vals_list)
```

- [ ] **Step 7: Esqueleto de `models/relatorio_texto.py` + registrar models e ACL**

Os `@api.depends("relatorio_id.block_ids...")` / `("relatorio_id.anexo_ids...")` dos computes acima só resolvem se os O2M já existirem no relatório — senão o `-u` levanta `ValueError: Wrong @depends ... Dependency field 'block_ids' not found`. Por isso o `_inherit` com os O2M e os helpers de numeração nasce **nesta** task (a Task 5 substitui o arquivo inteiro pela versão completa).

Criar `models/relatorio_texto.py`:

```python
"""Relatório Final — texto (blocos), anexos (posições) e aprovações (P3).

Esqueleto da Task 3 (O2M + helpers de numeração); completado na Task 5.
"""

from odoo import fields, models

from ._numbering import hierarchical_numbering, sort_key


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    template_id = fields.Many2one(
        "afr.relatorio.template", string="Template", ondelete="set null",
        tracking=True, help="Sugerido pela categoria do equipamento.")
    block_ids = fields.One2many(
        "afr.relatorio.block", "relatorio_id", string="Blocos do texto", copy=False)
    anexo_ids = fields.One2many(
        "afr.relatorio.anexo", "relatorio_id", string="Anexos", copy=False)
    aprovacao_ids = fields.One2many(
        "afr.relatorio.aprovacao", "relatorio_id", string="Aprovações", copy=False)

    def _body_blocks(self):
        """Blocos do texto principal (incluídos e sem vínculo a anexo), ordenados."""
        self.ensure_one()
        return self.block_ids.filtered(
            lambda b: b.included and not b.anexo_code).sorted(sort_key)

    def _block_numbering(self):
        self.ensure_one()
        return hierarchical_numbering(self._body_blocks())

    def _anexos_included(self):
        self.ensure_one()
        return self.anexo_ids.filtered("included").sorted(sort_key)
```

Final de `models/__init__.py` (depois do `from . import relatorio` de P1 e dos imports de P2):

```python
from . import relatorio_template        # Relatório Final P3
from . import relatorio_block           # Relatório Final P3
from . import relatorio_anexo           # Relatório Final P3
from . import relatorio_aprovacao       # Relatório Final P3
from . import relatorio_texto           # Relatório Final P3 (_inherit relatorio + os)
```

Acrescentar ao final de `security/ir.model.access.csv`:

```csv
access_relatorio_template_technician,relatorio_template_technician,model_afr_relatorio_template,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_relatorio_template_user,relatorio_template_user,model_afr_relatorio_template,afr_qualificacao.group_afr_qualificacao_user,1,0,0,0
access_relatorio_template_manager,relatorio_template_manager,model_afr_relatorio_template,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_relatorio_template_line_technician,relatorio_template_line_technician,model_afr_relatorio_template_line,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_relatorio_template_line_user,relatorio_template_line_user,model_afr_relatorio_template_line,afr_qualificacao.group_afr_qualificacao_user,1,0,0,0
access_relatorio_template_line_manager,relatorio_template_line_manager,model_afr_relatorio_template_line,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_relatorio_template_checklist_technician,relatorio_template_checklist_technician,model_afr_relatorio_template_checklist_line,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_relatorio_template_checklist_user,relatorio_template_checklist_user,model_afr_relatorio_template_checklist_line,afr_qualificacao.group_afr_qualificacao_user,1,0,0,0
access_relatorio_template_checklist_manager,relatorio_template_checklist_manager,model_afr_relatorio_template_checklist_line,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_relatorio_template_anexo_technician,relatorio_template_anexo_technician,model_afr_relatorio_template_anexo_line,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_relatorio_template_anexo_user,relatorio_template_anexo_user,model_afr_relatorio_template_anexo_line,afr_qualificacao.group_afr_qualificacao_user,1,0,0,0
access_relatorio_template_anexo_manager,relatorio_template_anexo_manager,model_afr_relatorio_template_anexo_line,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_relatorio_block_technician,relatorio_block_technician,model_afr_relatorio_block,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_relatorio_block_user,relatorio_block_user,model_afr_relatorio_block,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
access_relatorio_block_manager,relatorio_block_manager,model_afr_relatorio_block,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_relatorio_anexo_technician,relatorio_anexo_technician,model_afr_relatorio_anexo,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_relatorio_anexo_user,relatorio_anexo_user,model_afr_relatorio_anexo,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
access_relatorio_anexo_manager,relatorio_anexo_manager,model_afr_relatorio_anexo,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_relatorio_aprovacao_technician,relatorio_aprovacao_technician,model_afr_relatorio_aprovacao,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_relatorio_aprovacao_user,relatorio_aprovacao_user,model_afr_relatorio_aprovacao,afr_qualificacao.group_afr_qualificacao_user,1,1,1,0
access_relatorio_aprovacao_manager,relatorio_aprovacao_manager,model_afr_relatorio_aprovacao,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_proposal_section_technician,proposal_section_technician,model_afr_proposal_section,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
```

(A última linha existe porque o técnico abre o form do relatório, que mostra `block_ids.section_id`.)

- [ ] **Step 8: `views/relatorio_template_views.xml` (config + menus)**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_relatorio_template_tree" model="ir.ui.view">
        <field name="name">afr.relatorio.template.tree</field>
        <field name="model">afr.relatorio.template</field>
        <field name="arch" type="xml">
            <tree string="Templates de Relatório">
                <field name="sequence" widget="handle"/>
                <field name="name"/>
                <field name="code"/>
                <field name="equipment_category_ids" widget="many2many_tags"/>
                <field name="company_id" groups="base.group_multi_company"/>
                <field name="active" widget="boolean_toggle"/>
            </tree>
        </field>
    </record>

    <record id="view_relatorio_template_form" model="ir.ui.view">
        <field name="name">afr.relatorio.template.form</field>
        <field name="model">afr.relatorio.template</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <group>
                            <field name="name"/>
                            <field name="code"/>
                            <field name="equipment_category_ids" widget="many2many_tags"/>
                        </group>
                        <group>
                            <field name="sequence"/>
                            <field name="company_id" groups="base.group_multi_company"/>
                            <field name="active"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Blocos do texto" name="template_blocos">
                            <field name="line_ids">
                                <tree editable="bottom">
                                    <field name="template_id" invisible="1"/>
                                    <field name="sequence" widget="handle"/>
                                    <field name="display_number" string="Nº" readonly="1"/>
                                    <field name="show_number" widget="boolean_toggle"/>
                                    <field name="show_title" widget="boolean_toggle"/>
                                    <field name="title" placeholder="(usa nome da seção / rótulo do tipo)"/>
                                    <field name="block_kind"/>
                                    <field name="anexo_code" optional="show"/>
                                    <field name="parent_id"
                                           domain="[('template_id','=',parent.id),('id','!=',id)]"
                                           options="{'no_create': True, 'no_create_edit': True}"/>
                                    <field name="display_label" string="Conteúdo" readonly="1"/>
                                    <field name="section_id" optional="hide"
                                           domain="[('document_type', '=', 'report')]"
                                           attrs="{'required': [('block_kind', '=', 'static')]}"
                                           options="{'no_create': True, 'no_create_edit': True}"/>
                                    <field name="page_break" widget="boolean_toggle"/>
                                    <button name="action_edit_template_line" type="object"
                                            string="Editar" icon="fa-pencil" class="btn-link"/>
                                </tree>
                            </field>
                        </page>
                        <page string="Checklist padrão" name="template_checklist">
                            <field name="checklist_line_ids">
                                <tree editable="bottom">
                                    <field name="sequence" widget="handle"/>
                                    <field name="grupo"/>
                                    <field name="descricao"/>
                                </tree>
                            </field>
                        </page>
                        <page string="Anexos padrão" name="template_anexos">
                            <field name="anexo_line_ids">
                                <tree editable="bottom">
                                    <field name="sequence" widget="handle"/>
                                    <field name="code"/>
                                    <field name="title"/>
                                    <field name="slot_kind"/>
                                    <field name="collect_sections" optional="show"/>
                                    <field name="cert_roles" optional="show"/>
                                    <field name="included_default" widget="boolean_toggle"/>
                                </tree>
                            </field>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <record id="view_relatorio_template_line_form" model="ir.ui.view">
        <field name="name">afr.relatorio.template.line.form</field>
        <field name="model">afr.relatorio.template.line</field>
        <field name="arch" type="xml">
            <form string="Linha do Template de Relatório">
                <sheet>
                    <group>
                        <group>
                            <field name="template_id" readonly="1"/>
                            <field name="block_kind"/>
                            <field name="title"/>
                            <field name="anexo_code"/>
                            <field name="parent_id"
                                   domain="[('template_id','=',template_id),('id','!=',id)]"/>
                        </group>
                        <group>
                            <field name="sequence"/>
                            <field name="show_number"/>
                            <field name="show_title"/>
                            <field name="page_break"/>
                            <field name="section_id" domain="[('document_type', '=', 'report')]"
                                   attrs="{'required': [('block_kind','=','static')]}"/>
                        </group>
                    </group>
                </sheet>
                <footer>
                    <button string="Salvar e Fechar" class="btn-primary" special="save"/>
                    <button string="Descartar" class="btn-secondary" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <record id="action_relatorio_template" model="ir.actions.act_window">
        <field name="name">Templates de Relatório</field>
        <field name="res_model">afr.relatorio.template</field>
        <field name="view_mode">tree,form</field>
    </record>

    <record id="action_relatorio_section" model="ir.actions.act_window">
        <field name="name">Blocos de Relatório</field>
        <field name="res_model">afr.proposal.section</field>
        <field name="view_mode">tree,form</field>
        <field name="domain">[('document_type', '=', 'report')]</field>
        <field name="context">{'default_document_type': 'report'}</field>
    </record>

    <menuitem id="menu_afr_relatorio_config"
              name="Relatório Final"
              parent="menu_afr_qualificacao_config"
              sequence="85"
              groups="afr_qualificacao.group_afr_qualificacao_manager"/>
    <menuitem id="menu_afr_relatorio_template"
              name="Templates de Relatório"
              parent="menu_afr_relatorio_config"
              action="afr_qualificacao.action_relatorio_template"
              sequence="10"
              groups="afr_qualificacao.group_afr_qualificacao_manager"/>
    <menuitem id="menu_afr_relatorio_section"
              name="Blocos de Relatório"
              parent="menu_afr_relatorio_config"
              action="afr_qualificacao.action_relatorio_section"
              sequence="20"
              groups="afr_qualificacao.group_afr_qualificacao_manager"/>
</odoo>
```

No `__manifest__.py`, em `data`, logo **depois** de `"views/qualificacao_menus.xml",`:

```python
        # Relatório Final P3 — config de templates (menus sob Configurações)
        "views/relatorio_template_views.xml",
```

- [ ] **Step 9: Rodar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioTemplateModels --stop-after-init --no-http`
Expected: PASS (e o `-u` carrega sem `Wrong @depends`).

- [ ] **Step 10: Commit**

```bash
git add models/relatorio_template.py models/relatorio_block.py models/relatorio_anexo.py models/relatorio_aprovacao.py models/relatorio_texto.py models/__init__.py security/ir.model.access.csv views/relatorio_template_views.xml __manifest__.py tests/test_relatorio_template.py
git commit -m "feat: add final report template, block, annex and approval models"
```

---

### Task 4: Seeds Hospitalar/Industrial + migração + versão

**Files:**
- Modify: `hooks.py`
- Create: `migrations/16.0.8.2.0/post-migrate.py`
- Modify: `__manifest__.py` (`version`)
- Test: `tests/test_relatorio_template.py`

**Interfaces:**
- Consumes: models da Task 3; `afr_qualificacao.cat_autoclave_vapor` (seed existente).
- Produces: `hooks._seed_relatorio_templates(env)` (idempotente); xmlids `afr_qualificacao.relatorio_template_hosp` (code `RQT-HOSP`, sequence 10, categoria autoclave a vapor) e `afr_qualificacao.relatorio_template_ind` (code `RQT-IND`, sequence 20); seções `afr_qualificacao.rqt_sec_*` com `document_type='report'`. Anexos hospitalar na ordem: `protocolo, dados, graficos, micro, f0, malhas, validador, padroes`; industrial: `protocolo, protocolo_cliente, dados, graficos, impressoes, micro, f0, malhas, validador, padroes`.

- [ ] **Step 1: Escrever o teste**

```python
from odoo.addons.afr_qualificacao.hooks import _seed_relatorio_templates


class TestRelatorioSeeds(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_relatorio_templates(cls.env)
        cls.hosp = cls.env.ref("afr_qualificacao.relatorio_template_hosp")
        cls.ind = cls.env.ref("afr_qualificacao.relatorio_template_ind")

    def test_codes_and_category(self):
        self.assertEqual((self.hosp.code, self.ind.code), ("RQT-HOSP", "RQT-IND"))
        self.assertIn(self.env.ref("afr_qualificacao.cat_autoclave_vapor"),
                      self.hosp.equipment_category_ids)

    def test_hosp_anexos_order(self):
        codes = self.hosp.anexo_line_ids.sorted(lambda l: (l.sequence, l.id)).mapped("code")
        self.assertEqual(codes, ["protocolo", "dados", "graficos", "micro", "f0",
                                 "malhas", "validador", "padroes"])
        dados = self.hosp.anexo_line_ids.filtered(lambda l: l.code == "dados")
        self.assertEqual(dados.slot_kind, "collect_section")
        self.assertIn("qd_penetracao_ciclo1", dados.collect_sections)
        validador = self.hosp.anexo_line_ids.filtered(lambda l: l.code == "validador")
        self.assertEqual((validador.slot_kind, validador.cert_roles),
                         ("instrument_certs", "antes,depois"))

    def test_ind_anexos_order(self):
        codes = self.ind.anexo_line_ids.sorted(lambda l: (l.sequence, l.id)).mapped("code")
        self.assertEqual(codes, ["protocolo", "protocolo_cliente", "dados", "graficos",
                                 "impressoes", "micro", "f0", "malhas", "validador",
                                 "padroes"])
        micro = self.ind.anexo_line_ids.filtered(lambda l: l.code == "micro")
        self.assertEqual(micro.slot_kind, "upload")

    def test_sections_are_report_and_use_tokens(self):
        crit = self.env.ref("afr_qualificacao.rqt_sec_criterios")
        self.assertEqual(crit.document_type, "report")
        self.assertIn("criterio['tolerancia']", str(crit.body))
        self.assertIn("anexo('protocolo')",
                      str(self.env.ref("afr_qualificacao.rqt_sec_objetivo").body))

    def test_hosp_lines_have_kinds_and_bloco_links(self):
        kinds = set(self.hosp.line_ids.mapped("block_kind"))
        self.assertTrue({"capa", "indice", "static", "protocolo", "laudo_micro",
                         "assinaturas", "anexo_separador"} <= kinds)
        proto = self.hosp.line_ids.filtered(lambda l: l.block_kind == "protocolo")
        self.assertEqual(proto.anexo_code, "protocolo")
        self.assertFalse(self.ind.line_ids.filtered(lambda l: l.block_kind == "laudo_micro"))

    def test_checklist_seeded(self):
        self.assertGreaterEqual(len(self.hosp.checklist_line_ids), 10)
        self.assertGreater(len(self.ind.checklist_line_ids), len(self.hosp.checklist_line_ids))

    def test_seed_is_idempotent(self):
        before = (len(self.hosp.line_ids), len(self.hosp.anexo_line_ids),
                  len(self.hosp.checklist_line_ids))
        _seed_relatorio_templates(self.env)
        _seed_relatorio_templates(self.env)
        Tpl = self.env["afr.relatorio.template"].with_context(active_test=False)
        self.assertEqual(Tpl.search_count([("code", "=", "RQT-HOSP")]), 1)
        self.assertEqual(Tpl.search_count([("code", "=", "RQT-IND")]), 1)
        self.assertEqual((len(self.hosp.line_ids), len(self.hosp.anexo_line_ids),
                          len(self.hosp.checklist_line_ids)), before)

    def test_quote_does_not_see_report_sections(self):
        sec = self.env.ref("afr_qualificacao.rqt_sec_objetivo")
        found = self.env["afr.proposal.section"].search([("document_type", "=", "proposal")])
        self.assertNotIn(sec, found)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioSeeds --stop-after-init --no-http`
Expected: ERROR `ImportError: cannot import name '_seed_relatorio_templates'`.

- [ ] **Step 3: Seeds em `hooks.py`**

Acrescentar **antes** de `def _install_proposal_template_seed`:

```python
# ─────────────────────────────────────────────────────────────────────────
# Relatório Final de Qualificação (P3) — seções, templates, checklist, anexos
# Texto genérico (sem cliente). Edições de norma NÃO fixadas: a edição
# aplicável varia por cliente e é citada no protocolo.
# ─────────────────────────────────────────────────────────────────────────

# (xmlid_suffix, code, name, category, body_html)
RELATORIO_SECTIONS = [
    ("rqt_sec_objetivo", "RQT-OBJETIVO", "Objetivo", "objetivo",
     "<p>Este relatório apresenta os resultados da Qualificação Térmica do "
     "equipamento <strong>{{ equipment.name }}</strong>, número de série "
     "<strong>{{ equipment.serial_number }}</strong>, de <strong>{{ partner.name }}</strong>, "
     "realizada para demonstrar, por meio de evidências documentadas, que o equipamento "
     "está instalado adequadamente, opera dentro dos limites especificados e produz, de "
     "forma reprodutível, resultados que atendem aos critérios de aceitação estabelecidos.</p>"
     "<p>Os ensaios seguiram o protocolo apresentado no Anexo {{ anexo('protocolo') }} "
     "deste relatório.</p>"),
    ("rqt_sec_normas", "RQT-NORMAS", "Normas e Referências", "normas",
     "<ul>"
     "<li>ABNT NBR ISO 17665 — Esterilização de produtos para saúde — Vapor — Requisitos "
     "para o desenvolvimento, validação e controle de rotina de processos de esterilização.</li>"
     "<li>ABNT NBR 16328 — Esterilização de produtos para saúde — Vapor — Esterilizadores "
     "a vapor de pequeno porte.</li>"
     "<li>ABNT NBR ISO 11138 — Esterilização de produtos para saúde — Indicadores biológicos.</li>"
     "<li>ABNT NBR ISO 11140 — Esterilização de produtos para saúde — Indicadores químicos.</li>"
     "<li>Legislação sanitária aplicável ao processamento de produtos para saúde.</li>"
     "</ul>"
     "<p>Aplicam-se as edições indicadas no protocolo (Anexo {{ anexo('protocolo') }}).</p>"),
    ("rqt_sec_definicoes", "RQT-DEFINICOES", "Termos e Definições", "tecnico",
     "<ul>"
     "<li><strong>Qualificação de Instalação (QI):</strong> verificação documentada de que o "
     "equipamento e suas utilidades foram fornecidos e instalados conforme a especificação.</li>"
     "<li><strong>Qualificação de Operação (QO):</strong> verificação documentada de que o "
     "equipamento opera dentro dos limites predeterminados, com a câmara vazia.</li>"
     "<li><strong>Qualificação de Desempenho (QD):</strong> verificação documentada de que o "
     "equipamento, operando com cargas de referência, produz resultados consistentes com os "
     "critérios de aceitação.</li>"
     "<li><strong>Tempo de equilíbrio:</strong> intervalo entre o instante em que o ponto de "
     "referência atinge a temperatura de esterilização e o instante em que todos os pontos a "
     "atingem.</li>"
     "<li><strong>Tempo de manutenção (período de esterilização):</strong> intervalo em que todos "
     "os pontos permanecem na faixa de temperatura de esterilização.</li>"
     "<li><strong>F0:</strong> letalidade acumulada expressa em minutos equivalentes a 121,1 °C, "
     "com z = 10 °C.</li>"
     "<li><strong>Valor D:</strong> tempo, em minutos, para reduzir em 90% a população do "
     "microrganismo de referência na condição especificada.</li>"
     "<li><strong>Indicador biológico (IB) / Indicador químico (IQ):</strong> dispositivos de "
     "desafio usados para evidenciar a letalidade e a exposição ao agente esterilizante.</li>"
     "</ul>"),
    ("rqt_sec_procedimento", "RQT-PROCEDIMENTO", "Procedimento de Qualificação", "tecnico",
     "<p>A qualificação foi executada conforme o protocolo do Anexo {{ anexo('protocolo') }}, "
     "com sensores de temperatura calibrados distribuídos na câmara e nas cargas segundo a "
     "disposição registrada no protocolo. Os valores coletados pelo sistema de aquisição "
     "encontram-se no Anexo {{ anexo('dados') }} e os gráficos no Anexo {{ anexo('graficos') }}.</p>"),
    ("rqt_sec_qi", "RQT-QI", "Qualificação de Instalação (QI)", "tecnico",
     "<p>Foram verificados as instalações elétricas, as utilidades, a documentação, os "
     "componentes, as calibrações das malhas de controle e o treinamento dos operadores, "
     "conforme a lista de verificação do protocolo. Itens reprovados, quando houver, estão "
     "registrados com comentário e ação recomendada.</p>"),
    ("rqt_sec_qo", "RQT-QO", "Qualificação de Operação (QO)", "tecnico",
     "<p>Foram executados ciclos com a câmara vazia para verificar a distribuição de "
     "temperatura, o funcionamento dos controles, indicadores e alarmes, e a repetibilidade "
     "dos parâmetros programados.</p>"),
    ("rqt_sec_qd", "RQT-QD", "Qualificação de Desempenho (QD)", "tecnico",
     "<p>Foram executados ciclos com carga de referência representativa da pior condição de "
     "uso, com sensores posicionados nos pontos de mais difícil penetração de calor e "
     "indicadores biológicos e químicos distribuídos conforme o protocolo.</p>"),
    ("rqt_sec_micro", "RQT-MICRO", "Avaliação Microbiológica", "tecnico",
     "<p>Os indicadores biológicos processados foram incubados juntamente com um controle "
     "positivo não processado do mesmo lote. Os resultados constam do laudo microbiológico "
     "no Anexo {{ anexo('micro') }}.</p>"),
    ("rqt_sec_qdf", "RQT-QDF", "Qualificação de Desempenho Física (QDF)", "tecnico",
     "<p>Foram executados ciclos com carga de referência, com sensores de temperatura e "
     "pressão posicionados nos pontos críticos da carga e da câmara. Quando aplicável, foram "
     "realizados o teste de estanqueidade (vazamento de ar) e o teste de remoção de ar e "
     "penetração de vapor (Bowie-Dick).</p>"),
    ("rqt_sec_qdm", "RQT-QDM", "Qualificação de Desempenho Microbiológica (QDM)", "tecnico",
     "<p>Os indicadores biológicos foram posicionados nos pontos de pior caso da carga e "
     "encaminhados ao laboratório indicado pelo cliente. O laudo emitido pelo laboratório "
     "consta do Anexo {{ anexo('micro') }}.</p>"),
    ("rqt_sec_certificacao", "RQT-CERTIFICACAO", "Certificação dos Instrumentos", "normas",
     "<p>O sistema de aquisição de dados foi calibrado antes e depois da campanha de ensaios "
     "(Anexo {{ anexo('validador') }}), contra padrões com rastreabilidade metrológica "
     "(Anexo {{ anexo('padroes') }}). Os certificados das malhas de controle do equipamento "
     "constam do Anexo {{ anexo('malhas') }}.</p>"),
    ("rqt_sec_criterios", "RQT-CRITERIOS", "Critérios de Aceitação", "tecnico",
     "<ul>"
     "<li>Durante o período de esterilização, todas as temperaturas medidas devem permanecer "
     "entre a temperatura nominal do ciclo e a temperatura nominal acrescida de "
     "{{ criterio['tolerancia'] }} °C.</li>"
     "<li>O F0 acumulado em cada ponto deve ser igual ou superior a {{ criterio['f0_fator'] }} "
     "vezes o valor D do indicador biológico utilizado (valor D = {{ criterio['valor_d'] }} min; "
     "F0 mínimo = {{ criterio['f0_minimo'] }} min).</li>"
     "<li>Todos os indicadores biológicos processados devem apresentar resultado negativo e o "
     "controle positivo, crescimento.</li>"
     "<li>Todos os indicadores químicos devem apresentar viragem completa.</li>"
     "</ul>"),
    ("rqt_sec_validade", "RQT-VALIDADE", "Validade", "condicoes",
     "<p>Os resultados deste relatório são válidos por 12 (doze) meses a partir da data de "
     "emissão, ou até que ocorra manutenção corretiva relevante, mudança do local de "
     "instalação, alteração dos parâmetros dos ciclos ou da configuração das cargas — "
     "situações que exigem requalificação.</p>"),
    ("rqt_sec_conclusao", "RQT-CONCLUSAO", "Conclusão", "custom",
     "<p>Com base nos resultados obtidos e nos critérios de aceitação estabelecidos, o "
     "equipamento {{ equipment.name }}, número de série {{ equipment.serial_number }}, foi "
     "considerado <strong>QUALIFICADO</strong> para os ciclos avaliados, conforme detalhado "
     "nos anexos deste relatório.</p>"),
    ("rqt_sec_protocolo_textos", "RQT-PROTOCOLO-TEXTOS",
     "Procedimentos, Segurança da Informação e Responsabilidades", "custom",
     "<p><strong>Procedimentos.</strong> Os sensores são instalados conforme a disposição "
     "registrada neste protocolo; os ciclos são executados na quantidade e nos parâmetros "
     "indicados; a aquisição é contínua, com intervalo configurado no sistema de aquisição.</p>"
     "<p><strong>Segurança da informação.</strong> Os dados brutos do sistema de aquisição são "
     "preservados sem edição, com acesso restrito à equipe técnica; os arquivos anexados a este "
     "relatório são cópias fiéis dos originais.</p>"
     "<p><strong>Responsabilidades.</strong> Contratada: planejamento, execução dos ensaios, "
     "análise dos dados e emissão do relatório. Cliente ({{ partner.name }}): disponibilizar o "
     "equipamento, as utilidades e as cargas representativas, e designar responsável para "
     "acompanhar os ensaios.</p>"),
]

# Checklist QI: (grupo, descricao)
RELATORIO_CHECKLIST_BASE = [
    ("Instalações elétricas", "Tensão de alimentação compatível com a placa de identificação"),
    ("Instalações elétricas", "Aterramento elétrico presente e adequado"),
    ("Instalações elétricas", "Circuito de alimentação exclusivo, com proteção"),
    ("Utilidades", "Água de alimentação com qualidade conforme recomendação do fabricante"),
    ("Utilidades", "Ponto de drenagem/exaustão adequado"),
    ("Utilidades", "Ventilação do ambiente de instalação adequada"),
    ("Documentação", "Manual de operação do fabricante disponível"),
    ("Documentação", "Registro do equipamento no órgão sanitário (quando aplicável)"),
    ("Documentação", "Registros de manutenção preventiva disponíveis"),
    ("Componentes", "Placa de identificação legível (fabricante, modelo, número de série)"),
    ("Componentes", "Porta, trava e guarnição de vedação íntegras"),
    ("Componentes", "Indicadores de temperatura e pressão funcionais"),
    ("Componentes", "Registrador/impressora de ciclo funcional (quando aplicável)"),
    ("Calibrações", "Malhas de controle (temperatura, pressão e tempo) com calibração vigente"),
    ("Treinamentos", "Operadores treinados na operação do equipamento"),
]
RELATORIO_CHECKLIST_IND_EXTRA = [
    ("Utilidades", "Linha de vapor/gerador de vapor com pressão e qualidade adequadas"),
    ("Utilidades", "Ar comprimido com pressão adequada (quando aplicável)"),
    ("Componentes", "Bomba de vácuo funcional"),
    ("Componentes", "Filtro de ar de admissão íntegro e dentro da validade"),
]

# Linhas: (suffix, seq, block_kind, section_suffix|None, page_break,
#          parent_suffix|None, show_number, show_title, anexo_code|None, title|None)
_RQT_HEAD = [
    ("l010", 10, "capa", None, False, None, False, False, None, "Capa"),
    ("l020", 20, "indice", None, True, None, False, True, None, "Sumário"),
    ("l030", 30, "static", "rqt_sec_objetivo", True, None, True, True, None, None),
    ("l040", 40, "static", "rqt_sec_normas", False, None, True, True, None, None),
    ("l050", 50, "static", "rqt_sec_definicoes", False, None, True, True, None, None),
    ("l060", 60, "static", "rqt_sec_procedimento", True, None, True, True, None, None),
    ("l070", 70, "static", "rqt_sec_qi", False, "l060", True, True, None, None),
    ("l080", 80, "static", "rqt_sec_qo", False, "l060", True, True, None, None),
]
_RQT_TAIL = [
    ("l110", 110, "static", "rqt_sec_certificacao", True, None, True, True, None, None),
    ("l120", 120, "static", "rqt_sec_criterios", False, None, True, True, None, None),
    ("l130", 130, "static", "rqt_sec_validade", False, None, True, True, None, None),
    ("l140", 140, "static", "rqt_sec_conclusao", False, None, True, True, None, None),
    ("l150", 150, "assinaturas", None, False, None, True, True, None, "Quadro de Assinaturas"),
]


def _rqt_separators(codes, start_seq):
    return [
        ("s_%s" % code, start_seq + i * 10, "anexo_separador", None, False, None,
         False, False, code, None)
        for i, code in enumerate(codes)
    ]


# Anexos: (code, seq, title, slot_kind, collect_sections, cert_roles, included_default)
_RQT_DADOS_SECTIONS = (
    "qo_mapeamento_ciclo1,qo_mapeamento_ciclo2,qo_mapeamento_ciclo3,"
    "qd_penetracao_ciclo1,qd_penetracao_ciclo2,qd_penetracao_ciclo3"
)
RELATORIO_ANEXOS_HOSP = [
    ("protocolo", 10, "Protocolo de Qualificação Térmica", "bloco", "", "", True),
    ("dados", 20, "Resultados dos Valores Coletados", "collect_section", _RQT_DADOS_SECTIONS, "", True),
    ("graficos", 30, "Gráficos dos Ciclos", "upload", "", "", True),
    ("micro", 40, "Laudo Microbiológico", "bloco", "", "", True),
    ("f0", 50, "Curvas de Letalidade (F0)", "upload", "", "", True),
    ("malhas", 60, "Certificados de Calibração das Malhas de Controle", "malha_certs", "", "", True),
    ("validador", 70, "Certificados de Calibração do Sistema de Aquisição", "instrument_certs", "", "antes,depois", True),
    ("padroes", 80, "Certificados dos Padrões de Referência", "instrument_certs", "", "externo", True),
]
RELATORIO_ANEXOS_IND = [
    ("protocolo", 10, "Protocolo de Qualificação Térmica", "bloco", "", "", True),
    ("protocolo_cliente", 20, "Protocolo do Cliente", "upload", "", "", True),
    ("dados", 30, "Resultados dos Valores Coletados", "collect_section", _RQT_DADOS_SECTIONS, "", True),
    ("graficos", 40, "Gráficos dos Ciclos", "upload", "", "", True),
    ("impressoes", 50, "Registros Impressos pelo Equipamento", "upload", "", "", True),
    ("micro", 60, "Laudo Microbiológico (Laboratório do Cliente)", "upload", "", "", True),
    ("f0", 70, "Curvas de Letalidade (F0)", "upload", "", "", True),
    ("malhas", 80, "Certificados de Calibração das Malhas de Controle", "malha_certs", "", "", True),
    ("validador", 90, "Certificados de Calibração do Sistema de Aquisição", "instrument_certs", "", "antes,depois", True),
    ("padroes", 100, "Certificados dos Padrões de Referência", "instrument_certs", "", "externo", True),
]

RELATORIO_TEMPLATES = [
    {
        "xmlid": "relatorio_template_hosp",
        "name": "Relatório de Qualificação — Hospitalar",
        "code": "RQT-HOSP",
        "sequence": 10,
        "category_xmlids": ["cat_autoclave_vapor"],
        "lines": (
            _RQT_HEAD
            + [
                ("l090", 90, "static", "rqt_sec_qd", False, "l060", True, True, None, None),
                ("l100", 100, "static", "rqt_sec_micro", False, "l060", True, True, None, None),
            ]
            + _RQT_TAIL
            + _rqt_separators([a[0] for a in RELATORIO_ANEXOS_HOSP], 500)
            + [
                ("c_protocolo", 900, "protocolo", "rqt_sec_protocolo_textos", False, None,
                 False, False, "protocolo", "Protocolo de Qualificação Térmica"),
                ("c_micro", 910, "laudo_micro", None, False, None,
                 False, False, "micro", "Laudo Microbiológico"),
            ]
        ),
        "checklist": RELATORIO_CHECKLIST_BASE,
        "anexos": RELATORIO_ANEXOS_HOSP,
    },
    {
        "xmlid": "relatorio_template_ind",
        "name": "Relatório de Qualificação — Industrial",
        "code": "RQT-IND",
        "sequence": 20,
        "category_xmlids": [],
        "lines": (
            _RQT_HEAD
            + [
                ("l090", 90, "static", "rqt_sec_qdf", False, "l060", True, True, None, None),
                ("l100", 100, "static", "rqt_sec_qdm", False, "l060", True, True, None, None),
            ]
            + _RQT_TAIL
            + _rqt_separators([a[0] for a in RELATORIO_ANEXOS_IND], 500)
            + [
                ("c_protocolo", 900, "protocolo", "rqt_sec_protocolo_textos", False, None,
                 False, False, "protocolo", "Protocolo de Qualificação Térmica"),
            ]
        ),
        "checklist": RELATORIO_CHECKLIST_BASE + RELATORIO_CHECKLIST_IND_EXTRA,
        "anexos": RELATORIO_ANEXOS_IND,
    },
]


def _upsert_xmlid(env, name, record):
    """Registra/reaponta afr_qualificacao.<name> (noupdate) para `record`."""
    Imd = env["ir.model.data"]
    imd = Imd.search([("module", "=", "afr_qualificacao"), ("name", "=", name)], limit=1)
    vals = {"model": record._name, "res_id": record.id, "noupdate": True}
    if imd:
        imd.write(vals)
    else:
        Imd.create(dict(vals, name=name, module="afr_qualificacao"))


def _seed_relatorio_templates(env):
    """Cria seções de relatório e templates RQT-HOSP / RQT-IND.

    Idempotente: registro cujo xmlid já resolve não é tocado (o usuário
    controla o conteúdo depois do seed). Chamado pelo hook de install e pela
    migração 16.0.8.2.0.
    """
    Section = env["afr.proposal.section"]
    sections = {}
    for seq, (suffix, code, name, category, body) in enumerate(RELATORIO_SECTIONS, start=1):
        rec = env.ref("afr_qualificacao.%s" % suffix, raise_if_not_found=False)
        if not rec:
            rec = Section.create({
                "name": name, "code": code, "category": category,
                "document_type": "report", "body": body, "sequence": 1000 + seq * 10,
            })
            _upsert_xmlid(env, suffix, rec)
        sections[suffix] = rec

    Template = env["afr.relatorio.template"]
    Line = env["afr.relatorio.template.line"]
    for spec in RELATORIO_TEMPLATES:
        if env.ref("afr_qualificacao.%s" % spec["xmlid"], raise_if_not_found=False):
            continue
        categories = [
            env.ref("afr_qualificacao.%s" % x, raise_if_not_found=False)
            for x in spec["category_xmlids"]
        ]
        template = Template.create({
            "name": spec["name"],
            "code": spec["code"],
            "sequence": spec["sequence"],
            "equipment_category_ids": [(6, 0, [c.id for c in categories if c])],
            "checklist_line_ids": [
                (0, 0, {"sequence": (i + 1) * 10, "grupo": grupo, "descricao": desc})
                for i, (grupo, desc) in enumerate(spec["checklist"])
            ],
            "anexo_line_ids": [
                (0, 0, {
                    "code": code, "sequence": seq, "title": title, "slot_kind": slot,
                    "collect_sections": sects or False, "cert_roles": roles or False,
                    "included_default": inc,
                })
                for code, seq, title, slot, sects, roles, inc in spec["anexos"]
            ],
        })
        _upsert_xmlid(env, spec["xmlid"], template)
        by_suffix = {}
        for (suffix, seq, kind, sec_suffix, page_break, _parent,
             show_number, show_title, anexo_code, title) in spec["lines"]:
            section = sections.get(sec_suffix) if sec_suffix else False
            line = Line.create({
                "template_id": template.id,
                "sequence": seq,
                "block_kind": kind,
                "section_id": section.id if section else False,
                "page_break": page_break,
                "show_number": show_number,
                "show_title": show_title,
                "anexo_code": anexo_code or False,
                "title": title or False,
            })
            by_suffix[suffix] = line
        for (suffix, _seq, _kind, _sec, _pb, parent_suffix, *_rest) in spec["lines"]:
            if parent_suffix and parent_suffix in by_suffix:
                by_suffix[suffix].parent_id = by_suffix[parent_suffix].id
```

No `_install_proposal_template_seed`, logo após `_install_qualif_type_configs(env)` (e **antes** do `if template: ... return`):

```python
    # Relatório Final (P3) — seções/templates de relatório (idempotente).
    _seed_relatorio_templates(env)
```

- [ ] **Step 4: Migração e versão**

Criar `migrations/16.0.8.2.0/post-migrate.py`:

```python
"""Relatório Final P3 — semeia seções e templates RQT-HOSP / RQT-IND.

post_init_hook só roda em install; bases existentes recebem os seeds aqui.
Idempotente (mesma função do hooks.py).
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.afr_qualificacao.hooks import _seed_relatorio_templates


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_relatorio_templates(env)
```

Em `__manifest__.py`: `"version": "16.0.8.2.0",`.

- [ ] **Step 5: Rodar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioSeeds,/afr_qualificacao:TestProposalCatalog --stop-after-init --no-http`
Expected: PASS (log mostra a migração `16.0.8.2.0` rodando no `-u`).

- [ ] **Step 6: Commit**

```bash
git add hooks.py migrations/16.0.8.2.0/post-migrate.py __manifest__.py tests/test_relatorio_template.py
git commit -m "feat: seed hospital and industrial final report templates"
```

---

### Task 5: Relatório aplica o template (blocos, anexos, checklist, aprovações) + abas do form

**Files:**
- Modify: `models/relatorio_texto.py` (substituir o esqueleto da Task 3 pela versão completa)
- Create: `views/relatorio_texto_views.xml`
- Modify: `__manifest__.py` (data)
- Test: `tests/test_relatorio_template.py`

**Interfaces:**
- Consumes: P1 — `afr.qualificacao.relatorio` (`os_id`, `equipment_id`, `partner_id`, `company_id`, `state`, `_seed_checklist(lines)`, `checklist_ids`), `afr.qualificacao.os.action_generate_relatorios()` → recordset, `afr.qualificacao.os.action_generate_relatorios_open()` → dict, `afr.qualificacao.os.relatorio_final_ids`; `afr.qualificacao.os.relatorio.tecnico_ids` (M2M `hr.employee`), `.signature_technician_date`, `.state`. Task 3/4 models e seeds.
- Produces (em `afr.qualificacao.relatorio`): campos `template_id`, `block_ids`, `anexo_ids`, `aprovacao_ids`; `_suggest_template()` → `afr.relatorio.template` (0/1); `_apply_template()` → `True` (idempotente por parte: só cria blocos se não há blocos, anexos se não há anexos, aprovações se não há aprovações; checklist via `_seed_checklist`); `action_reload_template()` (só `draft`; apaga anexos+blocos e reaplica); `_block_numbering()` → `dict[int,str]` sobre `_body_blocks()`; `_body_blocks()` → blocos `included` **sem** `anexo_code`, ordenados; `_anexos_included()` → anexos incluídos ordenados; `_anexo_number(code)` → `str`; `_anexo_separator_block(code)` → bloco (0/1). `afr.qualificacao.os.action_generate_relatorios_open()` (botão) passa a chamar `_apply_template()` em `relatorio_final_ids`; `action_generate_relatorios()` (programático) **não** muda. Views: páginas `page_texto`, `page_anexos`, `page_aprovacoes`; `afr_qualificacao.view_relatorio_block_form`.

- [ ] **Step 1: Confirmar o xmlid do form de P1**

Run: `grep -n 'afr.qualificacao.relatorio"' /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/views/*.xml | grep -i form; grep -n '"views/relatorio' /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/__manifest__.py`
Expected: um `record id="view_afr_qualificacao_relatorio_form"` em `views/relatorio_views.xml`. Se o id/arquivo for outro, usar o real no `inherit_id` do Step 5 e na posição do manifest (Step 6). Confirmar também que o form tem `page[@name='page_ciclos']` e um `<field name="state" .../>`.

- [ ] **Step 2: Escrever os testes**

```python
from odoo.exceptions import UserError


class RelatorioTemplateFixture(AfrQualificacaoTestCommon):
    """Fixture sem testes (reusada por Apply e Tokens): OS + técnico com
    relatório diário assinado + relatório final com RQT-HOSP aplicado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_relatorio_templates(cls.env)
        cls.hosp = cls.env.ref("afr_qualificacao.relatorio_template_hosp")

    def setUp(self):
        super().setUp()
        so = self._apply(do_qi=True, qo_cycles=1)
        self.os = self._confirm_and_generate_os(so)
        self.employee = self.env["hr.employee"].create({"name": "Técnico Teste"})
        self.daily = self.env["afr.qualificacao.os.relatorio"].create({
            "os_id": self.os.id,
            "descricao": "Dia 1",
            "data_inicio": "2026-09-01 08:00:00",
            "data_fim": "2026-09-01 17:00:00",
            "tecnico_ids": [(6, 0, self.employee.ids)],
            "signature_technician_date": "2026-09-01 17:05:00",
        })
        self.os.action_generate_relatorios_open()
        self.rel = self.os.relatorio_final_ids.filtered(
            lambda r: r.equipment_id == self.equip1)
        self.rel.template_id = self.hosp
        self.rel.action_reload_template()


class TestRelatorioApplyTemplate(RelatorioTemplateFixture):

    def test_generate_applies_template(self):
        self.assertTrue(self.rel.block_ids)
        self.assertEqual(len(self.rel.block_ids), len(self.hosp.line_ids))
        self.assertEqual(len(self.rel.anexo_ids), len(self.hosp.anexo_line_ids))
        self.assertEqual(len(self.rel.checklist_ids), len(self.hosp.checklist_line_ids))

    def test_programmatic_generate_only_suggests_template(self):
        """Compatibilidade com P1: action_generate_relatorios() (recordset)
        não semeia nada; só o template é sugerido no create()."""
        so2 = self._apply(do_qi=True)
        os2 = self._confirm_and_generate_os(so2)
        rels2 = os2.action_generate_relatorios()
        self.assertTrue(rels2)
        self.assertTrue(all(r.template_id for r in rels2))
        self.assertFalse(rels2.mapped("block_ids"))
        self.assertFalse(rels2.mapped("checklist_ids"))
        self.assertFalse(rels2.mapped("aprovacao_ids"))

    def test_block_hierarchy_copied(self):
        qi = self.rel.block_ids.filtered(lambda b: b.title == "Qualificação de Instalação (QI)")
        self.assertEqual(qi.parent_id.title, "Procedimento de Qualificação")
        self.assertIn("{{", str(qi.parent_id.body))  # corpo copiado da seção

    def test_bloco_anexo_linked_to_content_block(self):
        proto = self.rel.anexo_ids.filtered(lambda a: a.code == "protocolo")
        self.assertEqual(proto.block_id.block_kind, "protocolo")
        micro = self.rel.anexo_ids.filtered(lambda a: a.code == "micro")
        self.assertEqual(micro.block_id.block_kind, "laudo_micro")
        dados = self.rel.anexo_ids.filtered(lambda a: a.code == "dados")
        self.assertFalse(dados.block_id)

    def test_default_approvals(self):
        ap = self.rel.aprovacao_ids
        self.assertEqual(ap.sorted("sequence").mapped("papel"),
                         ["elaborador", "emissor", "executor", "cliente"])
        executor = ap.filtered(lambda a: a.papel == "executor")
        self.assertEqual(executor.nome_exibicao, "Técnico Teste")
        self.assertTrue(executor.approved_at)
        cliente = ap.filtered(lambda a: a.papel == "cliente")
        self.assertEqual(cliente.partner_id, self.rel.partner_id)
        self.assertEqual(cliente.nome_exibicao, self.rel.partner_id.name)
        self.assertEqual(len(cliente.access_token or ""), 32)

    def test_apply_template_is_idempotent(self):
        counts = (len(self.rel.block_ids), len(self.rel.anexo_ids),
                  len(self.rel.checklist_ids), len(self.rel.aprovacao_ids))
        self.rel._apply_template()
        self.os.action_generate_relatorios_open()
        self.assertEqual((len(self.rel.block_ids), len(self.rel.anexo_ids),
                          len(self.rel.checklist_ids), len(self.rel.aprovacao_ids)), counts)

    def test_reload_blocked_outside_draft(self):
        self.rel.write({"state": "issued"})
        with self.assertRaises(UserError):
            self.rel.action_reload_template()

    def test_reload_discards_block_edits(self):
        blk = self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")
        blk.body = "<p>editado</p>"
        self.rel.action_reload_template()
        blk = self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")
        self.assertNotIn("editado", str(blk.body))

    def test_anexo_numbering_skips_excluded(self):
        num = {a.code: a.numero for a in self.rel.anexo_ids}
        self.assertEqual((num["protocolo"], num["dados"], num["graficos"], num["micro"]),
                         (1, 2, 3, 4))
        self.rel.anexo_ids.filtered(lambda a: a.code == "dados").included = False
        self.assertEqual(self.rel._anexo_number("dados"), "")
        self.assertEqual(self.rel._anexo_number("graficos"), "2")
        self.assertEqual(self.rel._anexo_number("micro"), "3")
        self.assertEqual(self.rel._anexo_number("nao_existe"), "")

    def test_block_numbering_ignores_anexo_blocks(self):
        numbers = self.rel._block_numbering()
        anexo_blocks = self.rel.block_ids.filtered("anexo_code")
        self.assertTrue(anexo_blocks)
        for blk in anexo_blocks:
            self.assertNotIn(blk.id, numbers)
        objetivo = self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")
        self.assertEqual(numbers[objetivo.id], "1")
        qi = self.rel.block_ids.filtered(lambda b: b.title == "Qualificação de Instalação (QI)")
        self.assertEqual(numbers[qi.id], "4.1")

    def test_suggest_template_by_category_then_sequence(self):
        tpl = self.env["afr.relatorio.template"].create({
            "name": "Tpl Categoria", "code": "RQT-CAT", "sequence": 99,
            "equipment_category_ids": [(6, 0, self.category.ids)],
        })
        self.assertEqual(self.rel._suggest_template(), tpl)
        tpl.equipment_category_ids = [(5, 0, 0)]
        lowest = self.env["afr.relatorio.template"].search(
            [("company_id", "in", [self.rel.company_id.id, False])],
            order="sequence, id", limit=1)
        self.assertEqual(self.rel._suggest_template(), lowest)
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioApplyTemplate --stop-after-init --no-http`
Expected: ERROR (`AttributeError: ... 'action_reload_template'` / campo `template_id` inexistente).

- [ ] **Step 4: `models/relatorio_texto.py` — substituir o conteúdo inteiro por:**

```python
"""Relatório Final — texto (blocos), anexos (posições) e aprovações (P3).

Extensão por _inherit do modelo criado em P1 (models/relatorio.py), para não
misturar dados de campo com montagem de texto.
"""

import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import is_html_empty

from ._numbering import hierarchical_numbering, sort_key
from .relatorio_template import REPORT_BLOCK_KINDS

_logger = logging.getLogger(__name__)


def _fmt_num(value):
    """3.0 → '3'; 1.5 → '1,5'. None/False → ''."""
    if value is None or value is False:
        return ""
    return ("%g" % value).replace(".", ",")


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    template_id = fields.Many2one(
        "afr.relatorio.template", string="Template", ondelete="set null",
        tracking=True, help="Sugerido pela categoria do equipamento.")
    block_ids = fields.One2many(
        "afr.relatorio.block", "relatorio_id", string="Blocos do texto", copy=False)
    anexo_ids = fields.One2many(
        "afr.relatorio.anexo", "relatorio_id", string="Anexos", copy=False)
    aprovacao_ids = fields.One2many(
        "afr.relatorio.aprovacao", "relatorio_id", string="Aprovações", copy=False)

    # ── criação / template ───────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records.filtered(lambda r: not r.template_id):
            rec.template_id = rec._suggest_template()
        return records

    def _suggest_template(self):
        """Template cuja categoria = categoria do equipamento; senão o de menor sequence."""
        self.ensure_one()
        Template = self.env["afr.relatorio.template"]
        company_dom = [("company_id", "in", [(self.company_id or self.env.company).id, False])]
        category = self.equipment_id.category_id
        if category:
            tpl = Template.search(
                company_dom + [("equipment_category_ids", "in", category.ids)],
                order="sequence, id", limit=1)
            if tpl:
                return tpl
        return Template.search(company_dom, order="sequence, id", limit=1)

    def _apply_template(self):
        """Copia o template para blocos/anexos/checklist/aprovações. Idempotente."""
        for rel in self:
            tpl = rel.template_id
            if tpl and not rel.block_ids:
                rel._apply_template_blocks(tpl)
            if tpl and not rel.anexo_ids:
                rel._apply_template_anexos(tpl)
            if tpl and tpl.checklist_line_ids:
                rel._seed_checklist([
                    {"grupo": l.grupo, "descricao": l.descricao, "sequence": l.sequence}
                    for l in tpl.checklist_line_ids.sorted(sort_key)
                ])
            if not rel.aprovacao_ids:
                rel._apply_default_aprovacoes()
        return True

    def _apply_template_blocks(self, tpl):
        self.ensure_one()
        Block = self.env["afr.relatorio.block"]
        labels = dict(REPORT_BLOCK_KINDS)
        line_to_block = {}
        for line in tpl.line_ids.sorted(sort_key):
            section = line.section_id
            line_to_block[line.id] = Block.create({
                "relatorio_id": self.id,
                "sequence": line.sequence,
                "block_kind": line.block_kind,
                "section_id": section.id if section else False,
                "title": line.title or section.name or labels.get(line.block_kind, ""),
                "body": section.body if section else False,
                "page_break": line.page_break,
                "show_number": line.show_number,
                "show_title": line.show_title,
                "anexo_code": line.anexo_code or False,
            })
        for line in tpl.line_ids.filtered("parent_id"):
            parent_block = line_to_block.get(line.parent_id.id)
            if parent_block:
                line_to_block[line.id].parent_id = parent_block

    def _apply_template_anexos(self, tpl):
        self.ensure_one()
        vals = []
        for line in tpl.anexo_line_ids.sorted(sort_key):
            block = self.env["afr.relatorio.block"]
            if line.slot_kind == "bloco":
                block = self.block_ids.filtered(
                    lambda b, c=line.code: b.anexo_code == c
                    and b.block_kind != "anexo_separador")[:1]
            vals.append({
                "relatorio_id": self.id,
                "sequence": line.sequence,
                "included": line.included_default,
                "code": line.code,
                "title": line.title,
                "slot_kind": line.slot_kind,
                "collect_sections": line.collect_sections or False,
                "cert_roles": line.cert_roles or False,
                "block_id": block.id or False,
            })
        self.env["afr.relatorio.anexo"].create(vals)

    def _apply_default_aprovacoes(self):
        """Elaborador/emissor vazios; executor = técnicos dos relatórios diários
        (aprovado pela assinatura já coletada no PWA); cliente = partner."""
        self.ensure_one()
        vals = [
            {"relatorio_id": self.id, "sequence": 10, "papel": "elaborador"},
            {"relatorio_id": self.id, "sequence": 20, "papel": "emissor"},
        ]
        daily = self.os_id.sudo().relatorio_ids.filtered(lambda d: d.state != "cancel")
        seq = 30
        for emp in daily.mapped("tecnico_ids"):
            signed = daily.filtered(
                lambda d, e=emp: e in d.tecnico_ids and d.signature_technician_date)
            vals.append({
                "relatorio_id": self.id,
                "sequence": seq,
                "papel": "executor",
                "user_id": emp.user_id.id or False,
                "nome_exibicao": emp.name,
                "approved_at": max(signed.mapped("signature_technician_date")) if signed else False,
            })
            seq += 1
        vals.append({
            "relatorio_id": self.id,
            "sequence": 100,
            "papel": "cliente",
            "partner_id": self.partner_id.id or False,
            "nome_exibicao": self.partner_id.name or False,
        })
        self.env["afr.relatorio.aprovacao"].create(vals)

    def action_reload_template(self):
        """Descarta blocos e anexos (inclusive arquivos anexados) e reaplica."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Só é possível recarregar o template com o relatório em rascunho."))
        self.anexo_ids.unlink()
        self.block_ids.unlink()
        self._apply_template()
        return True

    # ── numeração / anexos ───────────────────────────────────────────────
    def _body_blocks(self):
        """Blocos do texto principal (incluídos e sem vínculo a anexo), ordenados."""
        self.ensure_one()
        return self.block_ids.filtered(
            lambda b: b.included and not b.anexo_code).sorted(sort_key)

    def _block_numbering(self):
        self.ensure_one()
        return hierarchical_numbering(self._body_blocks())

    def _anexos_included(self):
        self.ensure_one()
        return self.anexo_ids.filtered("included").sorted(sort_key)

    def _anexo_number(self, code):
        """'4' para o 4º anexo incluído; '' se excluído ou inexistente."""
        self.ensure_one()
        anexo = self.anexo_ids.filtered(lambda a: a.code == code)[:1]
        if not anexo or not anexo.included or not anexo.numero:
            return ""
        return str(anexo.numero)

    def _anexo_separator_block(self, code):
        self.ensure_one()
        return self.block_ids.filtered(
            lambda b: b.block_kind == "anexo_separador" and b.anexo_code == code
            and b.included)[:1]


class AfrQualificacaoOs(models.Model):
    _inherit = "afr.qualificacao.os"

    def action_generate_relatorios_open(self):
        """Botão "Gerar relatórios finais": além de gerar (P1), aplica o
        template. `action_generate_relatorios()` (recordset) fica intacto —
        testes de P1 dependem de relatório sem checklist semeado."""
        action = super().action_generate_relatorios_open()
        self.mapped("relatorio_final_ids")._apply_template()
        return action
```

(O import em `models/__init__.py` já existe desde a Task 3.)

- [ ] **Step 5: `views/relatorio_texto_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Form modal do bloco (botão Editar da aba Texto) -->
    <record id="view_relatorio_block_form" model="ir.ui.view">
        <field name="name">afr.relatorio.block.form</field>
        <field name="model">afr.relatorio.block</field>
        <field name="arch" type="xml">
            <form string="Bloco do Relatório">
                <sheet>
                    <field name="relatorio_id" invisible="1"/>
                    <group>
                        <group>
                            <field name="block_kind" readonly="1"/>
                            <field name="title"/>
                            <field name="parent_id"/>
                            <field name="anexo_code" readonly="1"/>
                        </group>
                        <group>
                            <field name="included"/>
                            <field name="page_break"/>
                            <field name="show_number"/>
                            <field name="show_title"/>
                            <field name="section_id" readonly="1"/>
                        </group>
                    </group>
                    <separator string="Conteúdo (aceita {{ expressões }}: relatorio, os, partner, equipment, company, criterio['tolerancia'], anexo('code'))"/>
                    <field name="body" options="{'codeview': True}"/>
                </sheet>
                <footer>
                    <button string="Salvar e Fechar" class="btn-primary" special="save"/>
                    <button string="Descartar" class="btn-secondary" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <record id="view_afr_qualificacao_relatorio_form_texto" model="ir.ui.view">
        <field name="name">afr.qualificacao.relatorio.form.texto</field>
        <field name="model">afr.qualificacao.relatorio</field>
        <field name="inherit_id" ref="afr_qualificacao.view_afr_qualificacao_relatorio_form"/>
        <field name="arch" type="xml">
            <xpath expr="//page[@name='page_ciclos']" position="after">
                <page string="Texto" name="page_texto">
                    <group>
                        <group>
                            <field name="template_id" options="{'no_create': True}"
                                   attrs="{'readonly': [('state', '!=', 'draft')]}"/>
                        </group>
                    </group>
                    <button name="action_reload_template" type="object"
                            string="Recarregar template" class="btn-secondary"
                            attrs="{'invisible': [('state', '!=', 'draft')]}"
                            confirm="Recarregar descarta as edições dos blocos e os arquivos anexados às posições de anexo deste relatório. Continuar?"/>
                    <field name="block_ids" attrs="{'readonly': [('state', '!=', 'draft')]}">
                        <tree editable="bottom">
                            <field name="relatorio_id" invisible="1"/>
                            <field name="sequence" widget="handle"/>
                            <field name="display_number" string="Nº" readonly="1"/>
                            <field name="included" widget="boolean_toggle"/>
                            <field name="show_number" widget="boolean_toggle" optional="show"/>
                            <field name="show_title" widget="boolean_toggle" optional="show"/>
                            <field name="title"/>
                            <field name="block_kind"/>
                            <field name="anexo_code" optional="hide"/>
                            <field name="parent_id"
                                   domain="[('relatorio_id','=',parent.id),('id','!=',id)]"
                                   options="{'no_create': True, 'no_create_edit': True}"
                                   optional="show"/>
                            <field name="page_break" widget="boolean_toggle"/>
                            <button name="action_edit_block" type="object"
                                    string="Editar" icon="fa-pencil" class="btn-link"/>
                        </tree>
                    </field>
                </page>
                <page string="Anexos" name="page_anexos">
                    <p class="text-muted">
                        A ordem desta lista é a ordem dos anexos no PDF e define a numeração
                        usada pelo token <code>{{ anexo('code') }}</code>.
                    </p>
                    <field name="anexo_ids" attrs="{'readonly': [('state', '!=', 'draft')]}">
                        <tree>
                            <field name="sequence" widget="handle"/>
                            <field name="numero" string="Nº"/>
                            <field name="included" widget="boolean_toggle"/>
                            <field name="code"/>
                            <field name="title"/>
                            <field name="slot_kind"/>
                            <field name="attachment_ids" widget="many2many_tags" optional="show"/>
                        </tree>
                        <form string="Anexo">
                            <group>
                                <group>
                                    <field name="relatorio_id" invisible="1"/>
                                    <field name="title"/>
                                    <field name="code"/>
                                    <field name="slot_kind"/>
                                    <field name="included"/>
                                </group>
                                <group>
                                    <field name="collect_sections"
                                           attrs="{'invisible': [('slot_kind', '!=', 'collect_section')]}"/>
                                    <field name="cert_roles"
                                           attrs="{'invisible': [('slot_kind', '!=', 'instrument_certs')]}"/>
                                    <field name="block_id"
                                           attrs="{'invisible': [('slot_kind', '!=', 'bloco')]}"/>
                                </group>
                            </group>
                            <separator string="Arquivos (upload ou substituição manual)"/>
                            <field name="attachment_ids" widget="many2many_binary"/>
                        </form>
                    </field>
                </page>
                <page string="Aprovações" name="page_aprovacoes">
                    <field name="aprovacao_ids" attrs="{'readonly': [('state', '!=', 'draft')]}">
                        <tree editable="bottom">
                            <field name="sequence" widget="handle"/>
                            <field name="papel"/>
                            <field name="user_id"
                                   attrs="{'invisible': [('papel', '=', 'cliente')]}"/>
                            <field name="partner_id"
                                   attrs="{'invisible': [('papel', '!=', 'cliente')]}"/>
                            <field name="nome_exibicao"/>
                            <field name="registro"/>
                            <field name="approved_at"/>
                        </tree>
                    </field>
                </page>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 6: Manifest**

Em `data`, logo **depois** do arquivo de views do relatório criado por P1 (e do de P2, se houver) — confirmado no Step 1:

```python
        # Relatório Final P3 — abas Texto / Anexos / Aprovações
        "views/relatorio_texto_views.xml",
```

- [ ] **Step 7: Rodar (inclui regressão de P1)**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioApplyTemplate,/afr_qualificacao:TestRelatorioTemplateModels --stop-after-init --no-http`
Expected: PASS.
Depois rodar as classes de teste criadas por P1 e P2 (listar com `grep -n "^class Test" tests/test_relatorio_*.py` excluindo os dois arquivos de P3) com o mesmo comando. Expected: PASS. Em especial `TestRelatorioModel.test_seed_checklist_creates_lines_in_order` (P1) tem de continuar verde — é o motivo de o template não ser aplicado em `action_generate_relatorios()`. Qualquer falha de P1/P2: **parar e reportar ao orquestrador** — não relaxar o teste de P1/P2.

- [ ] **Step 8: Commit**

```bash
git add models/relatorio_texto.py views/relatorio_texto_views.xml __manifest__.py tests/test_relatorio_template.py
git commit -m "feat: apply report template to final report with annexes and approvals"
```

---

### Task 6: Tokens e render do corpo dos blocos

**Files:**
- Modify: `models/relatorio_texto.py`
- Test: `tests/test_relatorio_template.py`

**Interfaces:**
- Consumes: Task 5; P1 `tolerancia_acima`, `criterio_f0_fator`, `indicador_ids` (`tipo`, `valor_d`).
- Produces: `_criterio_values()` → `dict` com `tolerancia`, `f0_fator`, `f0_minimo`, `valor_d` (strings pt-BR; `valor_d`/`f0_minimo` = `""` sem IB biológico com valor D); `_token_context()` → `dict` (`relatorio, os, partner, equipment, company, criterio, anexo`), `anexo` é **callable** `anexo(code) -> str`; `_render_block_body(block)` → `Markup` (erro de token ⇒ corpo cru, sem exceção).

- [ ] **Step 1: Escrever os testes**

```python
class TestRelatorioTokens(RelatorioTemplateFixture):
    """Reusa a fixture da Task 5 (relatório com RQT-HOSP aplicado)."""

    def _objetivo(self):
        return self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")

    def test_render_tokens_criterio_and_anexo(self):
        blk = self._objetivo()
        blk.body = ("<p>T={{ criterio['tolerancia'] }};A={{ anexo('micro') }};"
                    "S={{ equipment.serial_number }}</p>")
        self.assertIn("anexo('micro')", str(blk.body))  # sanitizer preserva aspas
        self.rel.tolerancia_acima = 4.0
        html = str(self.rel._render_block_body(blk))
        self.assertIn("T=4;A=4;S=TSN-001", html)
        self.rel.anexo_ids.filtered(lambda a: a.code == "micro").included = False
        html = str(self.rel._render_block_body(blk))
        self.assertIn("T=4;A=;S=TSN-001", html)

    def test_criterio_values(self):
        self.rel.write({"tolerancia_acima": 3.0, "criterio_f0_fator": 12.0})
        self.assertEqual(self.rel._criterio_values()["valor_d"], "")
        self.env["afr.relatorio.indicador"].create({
            "relatorio_id": self.rel.id, "tipo": "biologico", "valor_d": 1.5,
        })
        crit = self.rel._criterio_values()
        self.assertEqual(crit, {"tolerancia": "3", "f0_fator": "12",
                                "valor_d": "1,5", "f0_minimo": "18"})

    def test_token_context_keys(self):
        ctx = self.rel._token_context()
        self.assertEqual(set(ctx), {"relatorio", "os", "partner", "equipment",
                                    "company", "criterio", "anexo"})
        self.assertEqual(ctx["anexo"]("protocolo"), "1")

    def test_seeded_bodies_render_without_braces(self):
        for blk in self.rel.block_ids.filtered("body"):
            self.assertNotIn("{{", str(self.rel._render_block_body(blk)), blk.title)

    def test_bad_token_falls_back_to_raw_body(self):
        blk = self._objetivo()
        blk.body = "<p>{{ relatorio.campo_que_nao_existe }}</p>"
        html = str(self.rel._render_block_body(blk))
        self.assertIn("{{", html)

    def test_empty_body(self):
        blk = self._objetivo()
        blk.body = False
        self.assertEqual(str(self.rel._render_block_body(blk)), "")

    def test_render_as_plain_user(self):
        user = self.env["res.users"].create({
            "name": "Usuário RQ", "login": "usuario_rq_p3",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
            ])],
        })
        blk = self._objetivo()
        blk.body = "<p>T={{ criterio['tolerancia'] }};A={{ anexo('dados') }}</p>"
        html = str(self.rel.with_user(user)._render_block_body(blk.with_user(user)))
        self.assertIn("T=3;A=2", html)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioTokens --stop-after-init --no-http`
Expected: FAIL (`AttributeError: ... '_render_block_body'`).

- [ ] **Step 3: Implementar em `models/relatorio_texto.py`** (métodos na classe `AfrQualificacaoRelatorio`, após `_anexo_separator_block`)

```python
    # ── tokens / render ──────────────────────────────────────────────────
    def _criterio_values(self):
        self.ensure_one()
        bio = self.indicador_ids.filtered(
            lambda i: i.tipo == "biologico" and i.valor_d)[:1]
        valor_d = bio.valor_d if bio else 0.0
        fator = self.criterio_f0_fator or 0.0
        return {
            "tolerancia": _fmt_num(self.tolerancia_acima),
            "f0_fator": _fmt_num(fator),
            "valor_d": _fmt_num(valor_d) if valor_d else "",
            "f0_minimo": _fmt_num(fator * valor_d) if valor_d else "",
        }

    def _token_context(self):
        """Contexto restrito do inline_template dos blocos."""
        self.ensure_one()
        rel = self
        return {
            "relatorio": self,
            "os": self.os_id,
            "partner": self.partner_id,
            "equipment": self.equipment_id,
            "company": self.company_id,
            "criterio": self._criterio_values(),
            "anexo": lambda code: rel._anexo_number(code),
        }

    def _render_block_body(self, block):
        """Resolve {{ }} do corpo do bloco. Erro de expressão ⇒ corpo cru
        (P5 acusa TOKEN_NAO_RESOLVIDO), nunca exceção no PDF."""
        self.ensure_one()
        body = block.body
        if not body or is_html_empty(body):
            return Markup("")
        try:
            rendered = self.env["mail.render.mixin"].sudo()._render_template(
                str(body), self._name, [self.id], engine="inline_template",
                add_context=self._token_context(),
            )
        except UserError:
            _logger.warning(
                "Relatório %s: token inválido no bloco %s; corpo mantido sem render.",
                self.display_name, block.id, exc_info=True)
            return Markup(str(body))
        return Markup(rendered.get(self.id) or "")
```

- [ ] **Step 4: Rodar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioTokens,/afr_qualificacao:TestRelatorioApplyTemplate --stop-after-init --no-http`
Expected: PASS. Se `test_render_as_plain_user` der `AccessError` em modelo de P1/P2 (ex.: `afr.relatorio.indicador`), é ACL de P1 faltando para o grupo Usuário — reportar, não contornar com `sudo()` no contexto.

- [ ] **Step 5: Commit**

```bash
git add models/relatorio_texto.py tests/test_relatorio_template.py
git commit -m "feat: render final report block tokens with criterio and anexo"
```

---

### Task 7: Corpo QWeb (`report_relatorio_corpo`) com índice, protocolo, laudo, assinaturas e marcadores

**Files:**
- Modify: `models/relatorio_texto.py` (helpers do corpo)
- Create: `reports/relatorio_corpo_report.xml`, `reports/relatorio_corpo_templates.xml`
- Modify: `__manifest__.py` (data)
- Create: `tests/test_relatorio_corpo_report.py`
- Modify: `tests/__init__.py`

**Interfaces:**
- Consumes: Tasks 5–6; P1 `_doc_number(prefix)`, `revision_label`, `data_inicio_ensaios`, `data_fim_ensaios`, `amb_temperatura`, `amb_umidade`, `checklist_ids` (`grupo`, `descricao`, `status`, `comentario`), `indicador_ids`, `leitura_ib_ids`, `cycle_ids` (`sequence`, `cycle_type_id`, `sale_order_line_id`, `qualificacao_id`, `sensor_pos_ids` → `canal`, `posicao`, `ib_label`); P2 `_afr_certificate_selection()` → `list[dict(instrument, resource_role, role, certificate)]`.
- Produces: `afr_qualificacao.paperformat_relatorio_final`; `afr_qualificacao.action_report_relatorio_corpo` (qweb-pdf, `report_name` `afr_qualificacao.report_relatorio_corpo`); template aceita nos **`data`** do report: `page_map` (`{"bloco:<id>"|"anexo:<code>": nº página}`, impresso como veio) e `with_markers` (bool) → `<span class="rq-mark">@@RQ:bloco:<id>@@</span>` como 1º filho de cada `<div class="rq-block ...">` e `<span class="rq-mark">@@RQ:anexo:<code>@@</span>` como 1º filho de cada `<div class="rq-anexo-sep">`. Helpers: `_report_index_entries()`, `_report_cycle_rows()`, `_report_sensor_tables()`, `_report_instrument_rows()`, `_report_signature_rows()`, `_fmt_date(value)`, `_fmt_datetime(value)`, `_sel_label(record, fname)`.

- [ ] **Step 1: Escrever os testes** — `tests/test_relatorio_corpo_report.py`

```python
"""P3 — corpo QWeb do Relatório Final (HTML; PDF é P4)."""

from odoo.addons.afr_qualificacao.hooks import _seed_relatorio_templates

from .common import AfrQualificacaoTestCommon

REPORT = "afr_qualificacao.action_report_relatorio_corpo"


class TestRelatorioCorpoReport(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_relatorio_templates(cls.env)
        cls.hosp = cls.env.ref("afr_qualificacao.relatorio_template_hosp")

    def setUp(self):
        super().setUp()
        so = self._apply(do_qi=True, qo_cycles=1)
        os = self._confirm_and_generate_os(so)
        rels = os.action_generate_relatorios()
        self.rel = rels.filtered(lambda r: r.equipment_id == self.equip1)
        self.rel.write({
            "template_id": self.hosp.id,
            "data_inicio_ensaios": "2026-09-01",
            "data_fim_ensaios": "2026-09-02",
            "amb_temperatura": "22 a 25 °C",
            "amb_umidade": "45 %UR",
        })
        self.rel.action_reload_template()

    def _render(self, **data):
        html, _t = self.env["ir.actions.report"]._render_qweb_html(
            REPORT, self.rel.ids, data=dict(data))
        return html.decode() if isinstance(html, bytes) else html

    def _block(self, title):
        return self.rel.block_ids.filtered(lambda b: b.title == title)

    def test_report_action_and_paperformat(self):
        report = self.env.ref(REPORT)
        self.assertEqual(report.report_name, "afr_qualificacao.report_relatorio_corpo")
        pf = self.env.ref("afr_qualificacao.paperformat_relatorio_final")
        self.assertEqual(report.paperformat_id, pf)
        self.assertEqual((pf.format, pf.margin_top, pf.margin_bottom), ("A4", 35, 25))

    def test_markers_absent_by_default(self):
        self.assertNotIn("@@RQ:", self._render())

    def test_markers_present_with_flag(self):
        html = self._render(with_markers=True)
        for blk in self.rel._body_blocks():
            self.assertIn("@@RQ:bloco:%d@@" % blk.id, html)
        for anexo in self.rel._anexos_included():
            self.assertIn("@@RQ:anexo:%s@@" % anexo.code, html)
        self.assertIn('class="rq-mark"', html)

    def test_marker_inside_page_break_container(self):
        blk = self._block("Objetivo")
        self.assertTrue(blk.page_break)
        html = self._render(with_markers=True)
        pos = html.index("@@RQ:bloco:%d@@" % blk.id)
        opening = html[html.rindex("<div", 0, pos):pos]
        self.assertIn("rq-page-break", opening)

    def test_anexo_separator_breaks_both_sides(self):
        html = self._render(with_markers=True)
        pos = html.index("@@RQ:anexo:dados@@")
        opening = html[html.rindex("<div", 0, pos):pos]
        self.assertIn("rq-anexo-sep", opening)
        self.assertIn("page-break-after: always", html)

    def test_index_uses_page_map(self):
        blk = self._block("Objetivo")
        html = self._render(page_map={"bloco:%d" % blk.id: 7, "anexo:dados": 23})
        self.assertIn('<span class="rq-toc-page">7</span>', html)
        self.assertIn('<span class="rq-toc-page">23</span>', html)
        self.assertIn("Anexo 2 — Resultados dos Valores Coletados", html)

    def test_index_without_page_map_renders_blank_pages(self):
        html = self._render()
        self.assertIn('<span class="rq-toc-page"></span>', html)

    def test_protocolo_contains_equipment_and_numbers(self):
        html = self._render()
        self.assertIn("TSN-001", html)
        self.assertIn(self.rel._doc_number("PrQT"), html)
        self.assertIn(self.rel._doc_number("ReQM"), html)
        self.assertIn("22 a 25 °C", html)
        self.assertIn("Anexo 1: Protocolo de Qualificação Térmica", html)

    def test_no_unresolved_tokens(self):
        self.assertNotIn("{{", self._render())

    def test_excluded_anexo_not_rendered(self):
        self.rel.anexo_ids.filtered(lambda a: a.code == "micro").included = False
        html = self._render(with_markers=True)
        self.assertNotIn("@@RQ:anexo:micro@@", html)
        self.assertNotIn(self.rel._doc_number("ReQM"), html)
        self.assertIn("Anexo 4: Curvas de Letalidade (F0)", html)

    def test_signatures_list_client(self):
        html = self._render()
        self.assertIn("Quadro de Assinaturas", html)
        self.assertIn(self.rel.partner_id.name, html)

    def test_bad_token_does_not_break_render(self):
        self._block("Conclusão").body = "<p>{{ relatorio.nao_existe }}</p>"
        html = self._render()
        self.assertIn("{{ relatorio.nao_existe }}", html)
        self.assertIn("TSN-001", html)
```

Adicionar ao final de `tests/__init__.py`:

```python
from . import test_relatorio_corpo_report
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCorpoReport --stop-after-init --no-http`
Expected: ERROR `ValueError: External ID not found in the system: afr_qualificacao.action_report_relatorio_corpo`.

- [ ] **Step 3: Helpers do corpo em `models/relatorio_texto.py`** (na classe `AfrQualificacaoRelatorio`)

```python
    # ── helpers do corpo QWeb ────────────────────────────────────────────
    def _fmt_date(self, value):
        return fields.Date.to_date(value).strftime("%d/%m/%Y") if value else ""

    def _fmt_datetime(self, value):
        if not value:
            return ""
        return fields.Datetime.context_timestamp(self, value).strftime("%d/%m/%Y %H:%M")

    def _sel_label(self, record, fname):
        value = record[fname]
        if not value:
            return ""
        return dict(record._fields[fname]._description_selection(self.env)).get(value, value)

    def _report_index_entries(self):
        """Linhas do índice: blocos titulados do texto + anexos incluídos.
        `key` casa com as chaves de page_map."""
        self.ensure_one()
        numbers = self._block_numbering()
        entries = []
        for blk in self._body_blocks():
            if blk.block_kind in ("capa", "indice") or not blk.show_title:
                continue
            entries.append({
                "key": "bloco:%d" % blk.id,
                "number": numbers.get(blk.id, ""),
                "title": blk.title or blk.display_label or "",
                "child": bool(blk.parent_id),
            })
        for anexo in self._anexos_included():
            entries.append({
                "key": "anexo:%s" % anexo.code,
                "number": "",
                "title": "Anexo %s — %s" % (anexo.numero, anexo.title or ""),
                "child": False,
            })
        return entries

    def _report_cycle_rows(self):
        """Ciclos agrupados por (etapa, tipo de ciclo) com qtd/temperatura/tempo."""
        self.ensure_one()
        qtype_labels = dict(
            self.env["afr.qualificacao"]._fields["qualification_type"]
            ._description_selection(self.env))
        groups, order = {}, []
        for cycle in self.cycle_ids.sorted(
                lambda c: (c.qualificacao_id.qualification_type or "", c.sequence, c.id)):
            key = (cycle.qualificacao_id.qualification_type, cycle.cycle_type_id.id)
            if key not in groups:
                line = cycle.sale_order_line_id
                ctype = cycle.cycle_type_id
                groups[key] = {
                    "etapa": qtype_labels.get(key[0], ""),
                    "name": ctype.name or cycle.display_name,
                    "qty": 0,
                    "temperature": line.temperature or ctype.temperature or "",
                    "duration": line.duration or ctype.duration or "",
                }
                order.append(key)
            groups[key]["qty"] += 1
        return [groups[k] for k in order]

    def _report_sensor_tables(self):
        self.ensure_one()
        return [
            {"cycle": c.display_name,
             "rows": c.sensor_pos_ids.sorted(lambda s: (s.sequence, s.id))}
            for c in self.cycle_ids.sorted(lambda c: (c.sequence, c.id))
            if c.sensor_pos_ids
        ]

    def _report_instrument_rows(self):
        """Validadores e padrões do plano de recursos com o certificado selecionado (P2)."""
        self.ensure_one()
        role_labels = {
            "antes": _("Antes da campanha"),
            "depois": _("Depois da campanha"),
            "externo": _("Certificado externo"),
        }
        rows = []
        for sel in self._afr_certificate_selection():
            inst, cert = sel["instrument"], sel["certificate"]
            rows.append({
                "instrument": inst.name or "",
                "identification": inst.id_number or inst.tag or "",
                "resource_role": _("Validador") if sel["resource_role"] == "validador" else _("Padrão"),
                "role": role_labels.get(sel["role"], sel["role"] or ""),
                "certificate": (cert.certificate_number or "—") if cert else "—",
                "date": self._fmt_date(cert.date_calibration) if cert else "",
                "validade": self._fmt_date(cert.validate_calibration) if cert else "",
            })
        return rows

    def _report_signature_rows(self):
        self.ensure_one()
        return [{
            "papel": self._sel_label(ap, "papel"),
            "nome": ap.nome_exibicao or ap.user_id.name or ap.partner_id.name or "",
            "registro": ap.registro or "",
            "approved_at": self._fmt_datetime(ap.approved_at),
        } for ap in self.aprovacao_ids.sorted(sort_key)]
```

- [ ] **Step 4: `reports/relatorio_corpo_report.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Margens reservadas ao carimbo (cabeçalho/rodapé) aplicado em P4. -->
    <record id="paperformat_relatorio_final" model="report.paperformat">
        <field name="name">Relatório Final de Qualificação (A4)</field>
        <field name="default" eval="False"/>
        <field name="format">A4</field>
        <field name="orientation">Portrait</field>
        <field name="margin_top">35</field>
        <field name="margin_bottom">25</field>
        <field name="margin_left">20</field>
        <field name="margin_right">20</field>
        <field name="header_line" eval="False"/>
        <field name="header_spacing">0</field>
        <field name="dpi">90</field>
    </record>

    <!-- Sem binding: quem gera o PDF é P4 (minuta/emissão). -->
    <record id="action_report_relatorio_corpo" model="ir.actions.report">
        <field name="name">Relatório Final — Corpo</field>
        <field name="model">afr.qualificacao.relatorio</field>
        <field name="report_type">qweb-pdf</field>
        <field name="report_name">afr_qualificacao.report_relatorio_corpo</field>
        <field name="report_file">afr_qualificacao.report_relatorio_corpo</field>
        <field name="print_report_name">'Corpo - %s' % (object.name)</field>
        <field name="paperformat_id" ref="paperformat_relatorio_final"/>
        <field name="groups_id" eval="[(4, ref('afr_qualificacao.group_afr_qualificacao_user'))]"/>
    </record>
</odoo>
```

- [ ] **Step 5: `reports/relatorio_corpo_templates.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!--
        Corpo do Relatório Final. Variáveis opcionais (chaves de `data` do report):
          page_map     {"bloco:<id>" | "anexo:<code>": nº página} — impresso no índice como veio
          with_markers bool — emite <span class="rq-mark">@@RQ:...@@</span> (branco, 1pt)
        Marcador SEMPRE como 1º filho do container que quebra página (P4 localiza
        a página pelo texto extraído).
    -->
    <template id="rq_styles">
        <style>
            .rq-page { color: #212529; font-size: 12px; font-family: Arial, Helvetica, sans-serif; }
            .rq-mark { color: #ffffff; font-size: 1pt; line-height: 1pt; }
            .rq-page-break { page-break-before: always; }
            .rq-title { font-size: 15px; font-weight: bold; margin: 14px 0 6px 0; color: var(--lq-brand, #1f3b63); }
            .rq-title-child { font-size: 13px; margin-left: 12px; }
            .rq-body { text-align: justify; }
            .rq-subtitle { font-weight: bold; margin: 10px 0 4px 0; }
            .rq-table { width: 100%; border-collapse: collapse; margin: 4px 0 10px 0; }
            .rq-table th, .rq-table td { border: 1px solid #999999; padding: 3px 5px; vertical-align: top; }
            .rq-table th { background: #eef1f5; text-align: left; }
            .rq-table tr { page-break-inside: avoid; }
            .rq-cover { text-align: center; padding-top: 120px; }
            .rq-cover-company { font-size: 16px; color: #555555; }
            .rq-cover-title { font-size: 26px; font-weight: bold; margin: 30px 0 10px 0; color: var(--lq-brand, #1f3b63); }
            .rq-cover-number { font-size: 16px; margin-bottom: 40px; }
            .rq-cover-meta { width: 80%; margin: 0 auto; text-align: left; }
            .rq-toc { width: 100%; border-collapse: collapse; }
            .rq-toc-row td { height: 18px; padding: 0 4px; border-bottom: 1px dotted #bbbbbb; }
            .rq-toc-num { width: 50px; }
            .rq-toc-child .rq-toc-title { padding-left: 16px; }
            .rq-toc-page-cell { width: 50px; text-align: right; }
            .rq-anexo-sep { page-break-before: always; page-break-after: always; text-align: center; padding-top: 260px; }
            .rq-anexo-title { font-size: 22px; font-weight: bold; }
            .rq-doc-header { text-align: center; margin-bottom: 10px; }
            .rq-doc-title { font-size: 17px; font-weight: bold; }
            .rq-doc-number { font-size: 13px; color: #555555; }
        </style>
    </template>

    <template id="rq_block_capa">
        <div class="rq-cover">
            <div class="rq-cover-company" t-esc="doc.company_id.name or ''"/>
            <div class="rq-cover-title">RELATÓRIO DE QUALIFICAÇÃO TÉRMICA</div>
            <div class="rq-cover-number"><span t-esc="doc.name"/> — <span t-esc="doc.revision_label"/></div>
            <table class="rq-table rq-cover-meta">
                <tr><th style="width:35%;">Cliente</th><td t-esc="doc.partner_id.name or ''"/></tr>
                <tr><th>Equipamento</th><td t-esc="doc.equipment_id.name or ''"/></tr>
                <tr><th>Número de série</th><td t-esc="doc.equipment_id.serial_number or ''"/></tr>
                <tr><th>TAG</th><td t-esc="doc.equipment_id.tag or ''"/></tr>
                <tr><th>Período dos ensaios</th>
                    <td><t t-esc="doc._fmt_date(doc.data_inicio_ensaios)"/> a <t t-esc="doc._fmt_date(doc.data_fim_ensaios)"/></td></tr>
            </table>
        </div>
    </template>

    <template id="rq_block_indice">
        <table class="rq-toc">
            <t t-foreach="doc._report_index_entries()" t-as="entry">
                <tr t-attf-class="rq-toc-row#{' rq-toc-child' if entry['child'] else ''}">
                    <td class="rq-toc-num" t-esc="entry['number']"/>
                    <td class="rq-toc-title" t-esc="entry['title']"/>
                    <td class="rq-toc-page-cell"><span class="rq-toc-page" t-esc="pmap.get(entry['key'], '')"/></td>
                </tr>
            </t>
        </table>
    </template>

    <template id="rq_block_protocolo">
        <div class="rq-doc-header">
            <div class="rq-doc-title">PROTOCOLO DE QUALIFICAÇÃO TÉRMICA</div>
            <div class="rq-doc-number" t-esc="doc._doc_number('PrQT')"/>
        </div>

        <div class="rq-subtitle">1. Identificação do Cliente</div>
        <table class="rq-table">
            <tr><th style="width:30%;">Cliente</th><td t-esc="doc.partner_id.name or ''"/></tr>
            <tr><th>CNPJ/CPF</th><td t-esc="doc.partner_id.vat or ''"/></tr>
            <tr><th>Endereço</th><td t-esc="doc.partner_id.contact_address or ''"/></tr>
        </table>

        <div class="rq-subtitle">2. Identificação do Equipamento</div>
        <table class="rq-table">
            <tr><th style="width:30%;">Equipamento</th><td t-esc="doc.equipment_id.name or ''"/></tr>
            <tr><th>Categoria</th><td t-esc="doc.equipment_id.category_id.name or ''"/></tr>
            <tr><th>Marca</th><td t-esc="doc.equipment_id.marca_id.name or ''"/></tr>
            <tr><th>Modelo</th><td t-esc="doc.equipment_id.model or ''"/></tr>
            <tr><th>Número de série</th><td t-esc="doc.equipment_id.serial_number or ''"/></tr>
            <tr><th>TAG</th><td t-esc="doc.equipment_id.tag or ''"/></tr>
            <tr><th>Patrimônio</th><td t-esc="doc.equipment_id.patrimony or ''"/></tr>
        </table>

        <div class="rq-subtitle">3. Condições Ambientais e Período</div>
        <table class="rq-table">
            <tr><th style="width:30%;">Temperatura ambiente</th><td t-esc="doc.amb_temperatura or ''"/></tr>
            <tr><th>Umidade relativa</th><td t-esc="doc.amb_umidade or ''"/></tr>
            <tr><th>Início dos ensaios</th><td t-esc="doc._fmt_date(doc.data_inicio_ensaios)"/></tr>
            <tr><th>Fim dos ensaios</th><td t-esc="doc._fmt_date(doc.data_fim_ensaios)"/></tr>
        </table>

        <div class="rq-subtitle">4. Ciclos</div>
        <table class="rq-table">
            <thead><tr><th>Etapa</th><th>Ciclo</th><th>Qtd</th><th>Temperatura</th><th>Tempo</th></tr></thead>
            <tbody>
                <t t-foreach="doc._report_cycle_rows()" t-as="row">
                    <tr>
                        <td t-esc="row['etapa']"/>
                        <td t-esc="row['name']"/>
                        <td t-esc="row['qty']"/>
                        <td t-esc="row['temperature']"/>
                        <td t-esc="row['duration']"/>
                    </tr>
                </t>
            </tbody>
        </table>

        <div class="rq-subtitle">5. Lista de Verificação (QI)</div>
        <table class="rq-table">
            <thead><tr><th>Grupo</th><th>Item</th><th>Resultado</th><th>Comentário</th></tr></thead>
            <tbody>
                <t t-foreach="doc.checklist_ids.sorted(lambda c: (c.sequence, c.id))" t-as="item">
                    <tr>
                        <td t-esc="item.grupo or ''"/>
                        <td t-esc="item.descricao or ''"/>
                        <td t-esc="doc._sel_label(item, 'status')"/>
                        <td t-esc="item.comentario or ''"/>
                    </tr>
                </t>
            </tbody>
        </table>

        <div class="rq-subtitle">6. Disposição dos Sensores</div>
        <t t-foreach="doc._report_sensor_tables()" t-as="st">
            <div t-esc="st['cycle']" style="font-weight:bold;"/>
            <table class="rq-table">
                <thead><tr><th>Canal</th><th>Posição</th><th>Indicador</th></tr></thead>
                <tbody>
                    <t t-foreach="st['rows']" t-as="pos">
                        <tr>
                            <td t-esc="pos.canal or ''"/>
                            <td t-esc="pos.posicao or ''"/>
                            <td t-esc="pos.ib_label or ''"/>
                        </tr>
                    </t>
                </tbody>
            </table>
        </t>

        <div class="rq-subtitle">7. Instrumentos e Padrões</div>
        <table class="rq-table">
            <thead><tr><th>Instrumento</th><th>Identificação</th><th>Função</th><th>Certificado</th><th>Nº</th><th>Calibração</th><th>Validade</th></tr></thead>
            <tbody>
                <t t-foreach="doc._report_instrument_rows()" t-as="row">
                    <tr>
                        <td t-esc="row['instrument']"/>
                        <td t-esc="row['identification']"/>
                        <td t-esc="row['resource_role']"/>
                        <td t-esc="row['role']"/>
                        <td t-esc="row['certificate']"/>
                        <td t-esc="row['date']"/>
                        <td t-esc="row['validade']"/>
                    </tr>
                </t>
            </tbody>
        </table>
    </template>

    <template id="rq_block_laudo_micro">
        <div class="rq-doc-header">
            <div class="rq-doc-title">LAUDO MICROBIOLÓGICO</div>
            <div class="rq-doc-number" t-esc="doc._doc_number('ReQM')"/>
        </div>
        <div class="rq-subtitle">Indicadores utilizados</div>
        <table class="rq-table">
            <thead><tr><th>Tipo</th><th>Marca</th><th>Modelo / Tipo</th><th>Lote</th><th>Validade</th><th>Valor D (min)</th><th>População</th></tr></thead>
            <tbody>
                <t t-foreach="doc.indicador_ids" t-as="ind">
                    <tr>
                        <td t-esc="doc._sel_label(ind, 'tipo')"/>
                        <td t-esc="ind.marca or ''"/>
                        <td t-esc="ind.modelo_tipo or ''"/>
                        <td t-esc="ind.lote or ''"/>
                        <td t-esc="doc._fmt_date(ind.validade)"/>
                        <td t-esc="ind.valor_d or ''"/>
                        <td t-esc="ind.populacao or ''"/>
                    </tr>
                </t>
            </tbody>
        </table>
        <div class="rq-subtitle">Leituras dos indicadores biológicos</div>
        <table class="rq-table">
            <thead><tr><th>Ciclo</th><th>Lote</th><th>Incubação</th><th>Leitura</th><th>Leitor</th><th>Resultado</th><th>Controle positivo</th></tr></thead>
            <tbody>
                <t t-foreach="doc.leitura_ib_ids" t-as="lt">
                    <tr>
                        <td t-esc="lt.cycle_id.display_name or ''"/>
                        <td t-esc="lt.indicador_id.lote or ''"/>
                        <td t-esc="doc._fmt_date(lt.data_incubacao)"/>
                        <td t-esc="doc._fmt_date(lt.data_leitura)"/>
                        <td t-esc="lt.leitor or ''"/>
                        <td t-esc="doc._sel_label(lt, 'resultado')"/>
                        <td t-esc="'Crescimento (OK)' if lt.controle_positivo_ok else 'Não conforme'"/>
                    </tr>
                </t>
            </tbody>
        </table>
    </template>

    <template id="rq_block_assinaturas">
        <table class="rq-table">
            <thead><tr><th>Papel</th><th>Nome</th><th>Registro</th><th>Aprovação</th></tr></thead>
            <tbody>
                <t t-foreach="doc._report_signature_rows()" t-as="row">
                    <tr>
                        <td t-esc="row['papel']"/>
                        <td t-esc="row['nome']"/>
                        <td t-esc="row['registro']"/>
                        <td t-esc="row['approved_at'] or '______________________'"/>
                    </tr>
                </t>
            </tbody>
        </table>
    </template>

    <!-- Um bloco. Espera: doc, block, block_numbers, markers, pmap -->
    <template id="rq_block">
        <t t-set="blk_num" t-value="block_numbers.get(block.id, '')"/>
        <div t-att-class="'rq-block rq-page-break' if block.page_break else 'rq-block'"
             t-att-data-rq-block="block.id"><span t-if="markers" class="rq-mark" t-esc="'@@RQ:bloco:%s@@' % block.id"/>
            <div t-if="block.show_title and block.block_kind != 'capa' and (block.title or blk_num)"
                 t-attf-class="rq-title#{' rq-title-child' if block.parent_id else ''}">
                <t t-if="blk_num"><span t-esc="blk_num"/> </t><span t-esc="block.title or ''"/>
            </div>
            <t t-if="block.block_kind == 'capa'"><t t-call="afr_qualificacao.rq_block_capa"/></t>
            <t t-if="block.block_kind == 'indice'"><t t-call="afr_qualificacao.rq_block_indice"/></t>
            <t t-if="block.block_kind == 'protocolo'"><t t-call="afr_qualificacao.rq_block_protocolo"/></t>
            <t t-if="block.block_kind == 'laudo_micro'"><t t-call="afr_qualificacao.rq_block_laudo_micro"/></t>
            <t t-if="block.block_kind == 'assinaturas'"><t t-call="afr_qualificacao.rq_block_assinaturas"/></t>
            <div t-if="block.block_kind not in ('capa', 'indice', 'anexo_separador') and block.body"
                 class="rq-body" t-out="doc._render_block_body(block)"/>
        </div>
    </template>

    <!-- Uma posição de anexo incluída: separador (+ conteúdo se slot 'bloco'). Espera: doc, anexo, markers -->
    <template id="rq_anexo">
        <t t-set="sep" t-value="doc._anexo_separator_block(anexo.code)"/>
        <div class="rq-anexo-sep" t-att-data-rq-anexo="anexo.code"><span t-if="markers" class="rq-mark" t-esc="'@@RQ:anexo:%s@@' % anexo.code"/><span t-if="markers and sep" class="rq-mark" t-esc="'@@RQ:bloco:%s@@' % sep.id"/>
            <div class="rq-anexo-title" t-esc="'Anexo %s: %s' % (anexo.numero, anexo.title or '')"/>
            <div t-if="sep and sep.body" class="rq-body" t-out="doc._render_block_body(sep)"/>
        </div>
        <t t-if="anexo.slot_kind == 'bloco' and anexo.block_id and anexo.block_id.included">
            <t t-set="block" t-value="anexo.block_id"/>
            <t t-call="afr_qualificacao.rq_block"/>
        </t>
    </template>

    <template id="report_relatorio_corpo">
        <t t-foreach="docs" t-as="doc">
            <t t-call="web.basic_layout">
                <t t-set="markers" t-value="bool(with_markers)"/>
                <t t-set="pmap" t-value="page_map or {}"/>
                <t t-set="block_numbers" t-value="doc._block_numbering()"/>
                <t t-call="afr_qualificacao.rq_styles"/>
                <div class="page rq-page">
                    <t t-foreach="doc._body_blocks()" t-as="block">
                        <t t-call="afr_qualificacao.rq_block"/>
                    </t>
                    <t t-foreach="doc._anexos_included()" t-as="anexo">
                        <t t-call="afr_qualificacao.rq_anexo"/>
                    </t>
                </div>
            </t>
        </t>
    </template>
</odoo>
```

Nota: o `<span class="rq-mark">` fica na **mesma linha** da abertura do `<div>` de propósito — nada (nem texto) entre a abertura do container e o marcador.

- [ ] **Step 6: Manifest**

Em `data`, ao final da seção `# Reports` (depois de `"reports/quotation_template.xml",`):

```python
        # Relatório Final P3 — corpo QWeb (sub-templates antes do report)
        "reports/relatorio_corpo_templates.xml",
        "reports/relatorio_corpo_report.xml",
```

- [ ] **Step 7: Rodar a task**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCorpoReport --stop-after-init --no-http`
Expected: PASS.

- [ ] **Step 8: Gate final de P3 (regressão)**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao --stop-after-init --no-http`
Expected: suíte inteira verde, exceto as 3 falhas pré-existentes listadas nas Global Constraints. Qualquer falha em classe de P1/P2 (`test_relatorio_*` fora dos dois arquivos de P3) ou da cotação é regressão desta fase: corrigir antes de fechar.

- [ ] **Step 9: Validação visual (agent-browser, regra do projeto)**

Reiniciar o container de dev (assets/views), logout → login, abrir uma OS com relatório gerado, conferir abas **Texto** (numeração `Nº`, toggle Incluir, botão Editar abre modal), **Anexos** (Nº recalcula ao desligar um anexo) e **Aprovações** (4 papéis), e o menu Configurações → Relatório Final → Templates de Relatório (RQT-HOSP/RQT-IND). O PDF do corpo **não** é testado aqui (é P4).

- [ ] **Step 10: Commit**

```bash
git add models/relatorio_texto.py reports/relatorio_corpo_report.xml reports/relatorio_corpo_templates.xml __manifest__.py tests/test_relatorio_corpo_report.py tests/__init__.py
git commit -m "feat: add final report body QWeb with index, protocol and page markers"
```

---

## Self-review (feito)

- **Cobertura do spec/contrato "P3 produz":** `hierarchical_numbering` (T1); `document_type` + filtros da cotação (T2); `REPORT_BLOCK_KINDS`, 4 models de template, bloco, anexo (`numero`), aprovação (`access_token`) (T3); seeds `RQT-HOSP`/`RQT-IND` + migração + chamada no hook (T4); `template_id`, `block_ids`, `anexo_ids`, `aprovacao_ids`, `_apply_template`, `action_reload_template`, `_block_numbering`, `_anexo_number`, páginas `page_texto/page_anexos/page_aprovacoes` (T5); `_token_context`, `_render_block_body` (T6); paperformat, `action_report_relatorio_corpo`, `report_relatorio_corpo` com `page_map`/`with_markers` (T7). §4.5 resolução de arquivos e §4.7 fluxo de aprovação ficam para P4 (fora deste plano, por contrato).
- **Placeholders:** nenhum; o único ponto dependente de nome externo (xmlid do form de P1) tem passo explícito de verificação (T5 Step 1).
- **Consistência de nomes:** `sort_key`/`hierarchical_numbering` (T1) usados em T3/T5; `_body_blocks`, `_anexos_included`, `_anexo_separator_block`, `_block_numbering` (T5) usados em T7; `_criterio_values`/`_token_context` (T6) usados por `_render_block_body`; `_report_*` e `_fmt_*` definidos em T7 Step 3 antes do XML que os usa.
- **Review Focus:** cada linha tem teste na task dona (T5, T6, T7).
