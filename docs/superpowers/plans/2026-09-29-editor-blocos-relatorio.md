# Editor de blocos do Relatório Final — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Editor de bloco do Relatório Final com blocos prontos (biblioteca), variáveis como etiquetas amigáveis e modo Editar | Visualizar, saída HTML inalterada.

**Architecture:** Backend ganha `afr.relatorio.snippet` (biblioteca + seed), `rq_variable_catalog`/`rq_preview_block` no relatório. Frontend ganha o field widget OWL `rq_block_html` que estende o `HtmlField` do `web_editor` 16 (comandos `/bloco` e `/variavel`, barra fixa, diálogos, preview). Variável é salva como `<span class="rq-var">{{ EXPR }}</span>`, resolvida pelo `inline_template` atual.

**Tech Stack:** Odoo 16, OWL 1/2 (legacy + `@odoo-module`), `web_editor` HtmlField, `mail.render.mixin` inline_template, wkhtmltopdf.

**Spec:** `addons/afr_qualificacao/docs/superpowers/specs/2026-09-29-editor-blocos-relatorio-design.md`

## Global Constraints

- Módulo `addons/afr_qualificacao` (submodule git próprio), branch `feat/relatorio-final`. Commits de dentro do submodule. **Não fazer push** (user commita/pusha após teste).
- Manifest: `16.0.8.7.0` → `16.0.8.8.0` (Task 4).
- `body` do bloco continua `fields.Html(sanitize=True)`; formato salvo da variável é exatamente `<span class="rq-var">{{ EXPR }}</span>` (só `class` + texto).
- Nenhum dado real de cliente em seeds/testes (`dados_sensiveis/` é proibido).
- Testes: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http` (subir `docker compose up -d db web` na raiz do monorepo se parado). Nunca `odoo -d` direto.
- UI manual: container `odoo_engenapp-web-qualificacao-1`, :8084, db `qualificacao-dev`; credenciais em `~/.config/engenapp/secrets.md`. Assets mudaram → `-u afr_qualificacao` no db + restart do container.
- Seeds HTML: compatível com wkhtmltopdf (sem flex/grid; colunas via `<table>`), estilos inline.
- Textos de UI em pt-BR.

## Review Focus

1. Bloco antigo com `{{ criterio['tolerancia'] }}` solto (sem span) — abre com etiqueta, salva sem alterar o texto renderizado no PDF. Teste: Task 2 (render com e sem span dão mesmo texto) + Task 3 (`normalizeVars` idempotente).
2. Expressão digitada inválida (`{{ criterio['xx'] }}`, `{{ relatorio.nao_existe }}`) no Visualizar — não explode, aparece em `missing`. Teste: Task 2.
3. Anexo excluído (`included=False`) referenciado por `anexo('X')` — preview marca missing (valor `''`). Teste: Task 2.
4. Usuário Técnico (só leitura) chamando `rq_preview_block` — não pode renderizar (mesma ACL de escrita do bloco). Teste: Task 2.
5. Salvar/reabrir o bloco não acumula atributos de decoração nem duplica spans (`cleanVars(decorate(x)) == x`). Teste: Task 3.

---

### Task 1: Biblioteca de blocos prontos (`afr.relatorio.snippet`)

**Files:**
- Create: `models/relatorio_snippet.py`
- Modify: `models/__init__.py` (importar `relatorio_snippet`)
- Create: `data/relatorio_snippet_seed.xml`
- Create: `views/relatorio_snippet_views.xml`
- Modify: `security/ir.model.access.csv`
- Modify: `__manifest__.py` (`data`: seed + views, depois de `views/qualificacao_menus.xml` para o menu pai existir)
- Test: `tests/test_relatorio_editor.py` (novo; importar em `tests/__init__.py`)

**Interfaces:**
- Produces: modelo `afr.relatorio.snippet` com `name`, `category` ∈ {`tabela`,`lista`,`destaque`,`layout`}, `sequence`, `body`, `active`; `@api.model rq_snippet_list() -> list[dict{id:int, name:str, category:str, body:str}]` (só ativos, ordem `category, sequence, id`); constante `SNIPPET_CATEGORIES` (lista de tuplas) exportada do módulo.

- [ ] **Step 1: Teste falhando**

```python
# tests/test_relatorio_editor.py
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common_relatorio import RelatorioTestCommon


@tagged("post_install", "-at_install")
class TestRelatorioSnippet(RelatorioTestCommon):

    def test_seed_loaded(self):
        Snip = self.env["afr.relatorio.snippet"]
        self.assertGreaterEqual(Snip.search_count([]), 10)
        cats = set(Snip.search([]).mapped("category"))
        self.assertEqual(cats, {"tabela", "lista", "destaque", "layout"})

    def test_list_filters_inactive_and_orders(self):
        Snip = self.env["afr.relatorio.snippet"]
        inactive = Snip.create({"name": "Z inativo", "category": "lista",
                                "body": "<p>x</p>", "active": False})
        items = Snip.rq_snippet_list()
        self.assertNotIn(inactive.id, [i["id"] for i in items])
        self.assertEqual(set(items[0]), {"id", "name", "category", "body"})
        order = [(i["category"]) for i in items]
        self.assertEqual(order, sorted(order))

    def test_acl(self):
        Snip = self.env["afr.relatorio.snippet"]
        snip = Snip.search([], limit=1)
        with self.assertRaises(AccessError):
            snip.with_user(self.user_qualif).write({"name": "hack"})
        snip.with_user(self.user_manager).write({"name": "ok gestor"})
        self.assertTrue(Snip.with_user(self.user_technician).rq_snippet_list())
```

- [ ] **Step 2: Rodar e ver falhar** (`--test-tags /afr_qualificacao:TestRelatorioSnippet`) — esperado: erro de modelo inexistente.

- [ ] **Step 3: Modelo**

```python
# models/relatorio_snippet.py
from odoo import api, fields, models

SNIPPET_CATEGORIES = [
    ("tabela", "Tabelas técnicas"),
    ("lista", "Listas e texto"),
    ("destaque", "Destaques"),
    ("layout", "Layout"),
]


class RelatorioSnippet(models.Model):
    """Bloco pronto inserido no corpo de um bloco do Relatório Final pelo
    editor `rq_block_html`. Gestor mantém a biblioteca sem deploy."""

    _name = "afr.relatorio.snippet"
    _description = "Bloco pronto do relatório"
    _order = "category, sequence, id"

    name = fields.Char(string="Nome", required=True)
    category = fields.Selection(SNIPPET_CATEGORIES, string="Categoria", required=True)
    sequence = fields.Integer(default=10)
    body = fields.Html(string="Conteúdo", sanitize=True)
    active = fields.Boolean(default=True)

    @api.model
    def rq_snippet_list(self):
        return [
            {"id": s.id, "name": s.name, "category": s.category, "body": s.body or ""}
            for s in self.search([])
        ]
```

ACL (`security/ir.model.access.csv`, acrescentar):
```
access_relatorio_snippet_technician,relatorio_snippet_technician,model_afr_relatorio_snippet,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_relatorio_snippet_user,relatorio_snippet_user,model_afr_relatorio_snippet,afr_qualificacao.group_afr_qualificacao_user,1,0,0,0
access_relatorio_snippet_manager,relatorio_snippet_manager,model_afr_relatorio_snippet,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
```

- [ ] **Step 4: Seed** `data/relatorio_snippet_seed.xml` com `<odoo noupdate="1">` e 12 registros (xmlids `snippet_<slug>`). Tabelas: `border-collapse:collapse; width:100%`, cabeçalho `background:#e9ecef; font-weight:bold`, células `border:1px solid #adb5bd; padding:4px 6px`. Conteúdo:
  - tabela: *Critérios de aceitação* (colunas Critério | Requisito | Referência; 3 linhas, 1ª linha requisito com `<span class="rq-var">{{ criterio['tolerancia'] }}</span>` °C); *Instrumentos utilizados* (Instrumento | Nº de série | Certificado | Validade; 2 linhas exemplo "Termopar tipo T"); *Resultados por ciclo* (Ciclo | Resultado | Observação; 3 linhas "Ciclo 1…").
  - lista: *Lista de verificação* (`<ul>` 4 itens "Item verificado…"); *Parágrafo com variáveis* (texto usando `relatorio.name`, `equipment.name`, `partner.name` como `span.rq-var`); *Definições* (`<dl>` ou tabela 2 colunas Termo | Definição com F0, Valor D).
  - destaque: *Nota* (div `border-left:4px solid #0d6efd; background:#e7f1ff; padding:8px 12px`); *Atenção* (mesma forma, `#ffc107`/`#fff8e1`); *Conclusão* (tabela 1 célula `border:2px solid #198754` com "O equipamento foi considerado APROVADO…"); *Citação de norma* (`<blockquote>` com "ABNT NBR ISO 17665 — …" texto genérico).
  - layout: *Duas colunas* (`<table>` 2 células 50% sem borda, `<p>` em cada); *Figura com legenda* (`<p style="text-align:center"><img src="/web/static/img/placeholder.png" style="width:50%"/></p><p style="text-align:center"><em>Figura 1 — Legenda da figura</em></p>`); *Quebra de página* (`<div style="page-break-after:always"></div><p><br></p>`).

- [ ] **Step 5: Views + menu** `views/relatorio_snippet_views.xml`: tree (`handle` sequence, name, category, active widget boolean_toggle), form (name, category, sequence, active; `body` com `widget="rq_block_html"` e `options="{'catalog': 'static'}"` — o widget só existe após Task 3; até lá usar `widget="html"` e a Task 3 troca), search com filtro por categoria e `active`, action `action_afr_relatorio_snippet`, menu `menu_afr_relatorio_snippet` "Blocos prontos" em `menu_afr_qualificacao_config`, `groups="afr_qualificacao.group_afr_qualificacao_manager"`.

- [ ] **Step 6: Rodar testes** — PASS 3/3.

- [ ] **Step 7: Commit** (de dentro de `addons/afr_qualificacao`): `feat(relatorio): biblioteca de blocos prontos (afr.relatorio.snippet)`.

---

### Task 2: Catálogo de variáveis, preview e CSS do PDF

**Files:**
- Modify: `models/relatorio_texto.py` (refatorar núcleo de `_render_block_body`; novos métodos)
- Modify: `reports/relatorio_corpo_templates.xml` (bloco `<style>` da linha ~11)
- Test: `tests/test_relatorio_editor.py` (classe `TestRelatorioEditorBackend`)

**Interfaces:**
- Consumes: `_criterio_values()`, `_token_context()`, `_anexo_number(code)`, `anexo_ids` (campos `code`, `title`, `included`).
- Produces (em `afr.qualificacao.relatorio`):
  - `_render_body_html(body: str) -> tuple[Markup, bool]` — núcleo; `(html, ok)`, `ok=False` quando o render levantou e o corpo voltou cru.
  - `_render_block_body(block)` passa a chamar `_render_body_html(block.body)[0]` (comportamento idêntico).
  - `rq_variable_catalog() -> list[dict{expr:str, label:str, group:str, value:str}]` (`ensure_one`).
  - `@api.model rq_variable_catalog_static() -> mesma forma com value=''` (sem entradas `anexo(...)`).
  - `rq_preview_block(body: str) -> dict{html:str, missing:list[str]}`.

- [ ] **Step 1: Testes falhando**

```python
@tagged("post_install", "-at_install")
class TestRelatorioEditorBackend(RelatorioTestCommon):

    def setUp(self):
        super().setUp()
        self.rel.write({"tolerancia_acima": 3.0, "criterio_f0_fator": 2.0})
        self.Anexo = self.env["afr.relatorio.anexo"]
        self.anx = self.Anexo.create({"relatorio_id": self.rel.id, "code": "CERT",
                                      "title": "Certificados", "included": True})
        self.anx_off = self.Anexo.create({"relatorio_id": self.rel.id, "code": "OFF",
                                          "title": "Excluído", "included": False})

    def _cat(self):
        return {c["expr"]: c for c in self.rel.rq_variable_catalog()}

    def test_catalog_values_and_groups(self):
        cat = self._cat()
        self.assertEqual(cat["criterio['tolerancia']"]["value"], "3")
        self.assertEqual(cat["criterio['f0_fator']"]["value"], "2")
        self.assertEqual(cat["criterio['valor_d']"]["value"], "")
        self.assertIn("anexo('CERT')", cat)
        self.assertIn("anexo('OFF')", cat)
        self.assertEqual(cat["anexo('OFF')"]["value"], "")
        self.assertTrue(all(c["label"] and c["group"] for c in cat.values()))

    def test_catalog_static_has_no_values_nor_anexos(self):
        items = self.env["afr.qualificacao.relatorio"].rq_variable_catalog_static()
        self.assertTrue(items)
        self.assertTrue(all(i["value"] == "" for i in items))
        self.assertFalse([i for i in items if i["expr"].startswith("anexo(")])

    def test_preview_resolves_and_reports_missing(self):
        body = ('<p>T <span class="rq-var">{{ criterio[\'tolerancia\'] }}</span> '
                'D <span class="rq-var">{{ criterio[\'valor_d\'] }}</span> '
                'A <span class="rq-var">{{ anexo(\'OFF\') }}</span></p>')
        res = self.rel.rq_preview_block(body)
        self.assertIn(">3<", res["html"])
        self.assertIn("criterio['valor_d']", res["missing"])
        self.assertIn("anexo('OFF')", res["missing"])
        self.assertNotIn("criterio['tolerancia']", res["missing"])

    def test_preview_invalid_expression_does_not_raise(self):
        body = '<p><span class="rq-var">{{ relatorio.nao_existe_xyz }}</span></p>'
        res = self.rel.rq_preview_block(body)
        self.assertIn("relatorio.nao_existe_xyz", res["missing"])
        self.assertIn("nao_existe_xyz", res["html"])

    def test_span_and_bare_render_same_text(self):
        Block = self.env["afr.relatorio.block"]
        old = Block.create({"relatorio_id": self.rel.id, "block_kind": "static",
                            "body": "<p>Tol {{ criterio['tolerancia'] }} C</p>"})
        new = Block.create({"relatorio_id": self.rel.id, "block_kind": "static",
                            "body": '<p>Tol <span class="rq-var">{{ criterio[\'tolerancia\'] }}</span> C</p>'})
        from lxml import html as lh
        t_old = lh.fromstring(str(self.rel._render_block_body(old))).text_content()
        t_new = lh.fromstring(str(self.rel._render_block_body(new))).text_content()
        self.assertEqual(t_old, t_new)
        self.assertIn("Tol 3 C", t_new)

    def test_sanitizer_keeps_rq_var(self):
        Block = self.env["afr.relatorio.block"]
        b = Block.create({"relatorio_id": self.rel.id, "block_kind": "static",
                          "body": '<p><span class="rq-var" data-rq-expr="x" contenteditable="false">{{ os.name }}</span></p>'})
        self.assertIn('<span class="rq-var">{{ os.name }}</span>', str(b.body))

    def test_preview_requires_write_access(self):
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.rel.with_user(self.user_technician).rq_preview_block("<p>x</p>")
        res = self.rel.with_user(self.user_qualif).rq_preview_block("<p>x</p>")
        self.assertIn("x", res["html"])
```

(Se o `block_kind` válido para texto livre não for `"static"`, conferir `REPORT_BLOCK_KINDS` em `models/relatorio_template.py` e usar a chave do "Bloco de Texto". Se `test_sanitizer_keeps_rq_var` mostrar que o sanitizer também remove `class` em span, PARAR e reportar — invalida a decisão 1 do spec.)

- [ ] **Step 2: Rodar e ver falhar** (`/afr_qualificacao:TestRelatorioEditorBackend`).

- [ ] **Step 3: Implementação** em `models/relatorio_texto.py`:

```python
import re

_RQ_EXPR_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")

# (expr, label, group) — fonte única dos labels do editor. Valores vêm do render.
RQ_STATIC_VARS = [
    ("relatorio.name", "Nº do relatório", "Relatório"),
    ("relatorio.revision_label", "Revisão", "Relatório"),
    ("relatorio._fmt_date(relatorio.data_inicio_ensaios)", "Início dos ensaios", "Relatório"),
    ("relatorio._fmt_date(relatorio.data_fim_ensaios)", "Fim dos ensaios", "Relatório"),
    ("relatorio.amb_temperatura", "Temperatura ambiente", "Relatório"),
    ("relatorio.amb_umidade", "Umidade ambiente", "Relatório"),
    ("relatorio._fmt_date(relatorio.proxima_qualificacao)", "Próxima qualificação", "Relatório"),
    ("criterio['tolerancia']", "Tolerância acima (°C)", "Critérios"),
    ("criterio['f0_fator']", "Fator do F0", "Critérios"),
    ("criterio['valor_d']", "Valor D do indicador (min)", "Critérios"),
    ("criterio['f0_minimo']", "F0 mínimo (min)", "Critérios"),
    ("os.name", "Nº da OS", "Cliente e equipamento"),
    ("partner.name", "Cliente", "Cliente e equipamento"),
    ("equipment.name", "Equipamento", "Cliente e equipamento"),
    ("company.name", "Empresa executora", "Cliente e equipamento"),
]
```

(Conferir que cada campo existe em `models/relatorio.py`/`engc` antes; remover do catálogo o que não existir — o teste `test_catalog_values_and_groups` + um teste extra `test_catalog_all_render` que renderiza cada `expr` e exige `ok=True` protege isso:)

```python
    def test_catalog_all_render(self):
        for c in self.rel.rq_variable_catalog():
            _html, ok = self.rel._render_body_html("<p>{{ %s }}</p>" % c["expr"])
            self.assertTrue(ok, c["expr"])
```

Métodos (dentro de `afr.qualificacao.relatorio`, seção tokens/render):

```python
    def _render_body_html(self, body):
        """Núcleo do render de corpo: (Markup, ok). ok=False ⇒ expressão
        inválida, corpo devolvido cru."""
        self.ensure_one()
        if not body or is_html_empty(body):
            return Markup(""), True
        try:
            # (manter aqui o comentário TODO(1.11) sobre sudo, movido de _render_block_body)
            rendered = self.env["mail.render.mixin"].sudo()._render_template(
                str(body), self._name, [self.id], engine="inline_template",
                add_context=self._token_context(),
            )
        except UserError:
            _logger.warning("Relatório %s: token inválido; corpo mantido sem render.",
                            self.display_name, exc_info=True)
            return Markup(str(body)), False
        return Markup(rendered.get(self.id) or ""), True

    def _render_block_body(self, block):
        self.ensure_one()
        return self._render_body_html(block.body)[0]

    def _rq_render_expr(self, expr):
        html, ok = self._render_body_html("{{ %s }}" % expr)
        return (str(html).strip() if ok else None)

    def rq_variable_catalog(self):
        self.ensure_one()
        items = [{"expr": e, "label": l, "group": g, "value": self._rq_render_expr(e) or ""}
                 for e, l, g in RQ_STATIC_VARS]
        for anx in self.anexo_ids.sorted(sort_key):
            expr = "anexo('%s')" % anx.code
            items.append({"expr": expr, "label": "Nº do anexo — %s" % anx.title,
                          "group": "Anexos", "value": self._anexo_number(anx.code)})
        return items

    @api.model
    def rq_variable_catalog_static(self):
        return [{"expr": e, "label": l, "group": g, "value": ""} for e, l, g in RQ_STATIC_VARS]

    def rq_preview_block(self, body):
        """Render de corpo NÃO salvo p/ o modo Visualizar do editor.
        Exige direito de escrita no relatório (quem pode editar o bloco)."""
        self.ensure_one()
        self.check_access_rights("write")
        self.check_access_rule("write")
        html, ok = self._render_body_html(body or "")
        missing = []
        for expr in dict.fromkeys(_RQ_EXPR_RE.findall(str(body or ""))):
            val = self._rq_render_expr(expr)
            if not val:
                missing.append(expr)
        return {"html": str(html), "missing": missing}
```

(Nota: `_render_template` pode HTML-escapar `'` para `&#39;` na string do corpo? O regex roda sobre o `body` recebido — o editor manda `'` literal; se o teste mostrar `&#39;`, aplicar `html.unescape` na expressão antes de renderizar.)

- [ ] **Step 4: CSS do PDF** — no `<style>` de `reports/relatorio_corpo_templates.xml` acrescentar:
```css
.rq-var { background: none; border: 0; padding: 0; color: inherit; font: inherit; }
```

- [ ] **Step 5: Rodar** `TestRelatorioEditorBackend` + regressão `/afr_qualificacao:TestRelatorioTemplate,/afr_qualificacao:TestRelatorioCorpoReport` (nomes de classe conferir nos arquivos `tests/test_relatorio_template.py` / `test_relatorio_corpo_report.py`) — tudo PASS.

- [ ] **Step 6: Commit**: `feat(relatorio): catálogo de variáveis e preview de bloco`.

---

### Task 3a: Widget `rq_block_html` — etiquetas de variável + form do bloco

Escopo 3a = Steps 1, 2, 4 (sem `openSnippets`/`setMode` — deixar métodos fora), diálogo **RqVariableDialog** do Step 3, barra só com botão Variável no Step 5, SCSS do Step 6 (etiqueta + página), Step 7 (form), Steps 8(a,b,e,f)/9/10. Galeria, preview e imagem ficam na Task 3b.

**Risco principal — reset do editor (verificar ANTES de codar o resto):** o adapter do `HtmlField` (`web_editor/static/src/js/backend/html_field.js` + `html_field.xml`) chama `resetEditor(newValue)` no `updateWidget` quando o valor novo difere do `editingValue`. Grep de onde `editingValue` vem. Se passar por `getEditingValue()`, o override basta; se ler `wysiwyg.getValue()` direto, todo blur→`commitChanges` reseta o editor com HTML limpo e as etiquetas somem (e o Range salvo morre). Em qualquer caso: redecorar no reset (`useSubEnv({ onWysiwygReset: () => this.decorate() })` ou hook equivalente que o 16 tenha) e considerar limpar também em `wysiwyg.getValue` (patch na instância) para todo consumidor ver a mesma string. **Teste de aceitação no browser:** digitar texto, clicar fora do editor, clicar Variável, inserir → etiquetas continuam decoradas e a inserção cai no cursor.

**Botões da barra:** usar `t-on-mousedown.prevent` (além do click) para não tirar o foco do editável — senão blur→commit e `saveRange` perde a seleção.

### Task 3b: Galeria de blocos prontos, Editar | Visualizar e botão Imagem

Escopo 3b = `openSnippets` + `RqSnippetDialog` (Step 3), `setMode` + preview (Steps 4–5), botões Inserir bloco/Imagem/toggle na barra (mesma regra `mousedown.prevent`), CSS de miniatura/preview (Step 6), form do snippet com `widget="rq_block_html"` `options="{'catalog': 'static'}"`, Steps 8(c,d)/9/10 com commit `feat(relatorio): galeria de blocos prontos e modo visualizar`.

### Task 3 (referência comum de 3a e 3b)

**Files:**
- Create: `static/src/fields/rq_block_html/rq_var_dom.js` (lógica pura)
- Create: `static/src/fields/rq_block_html/rq_block_html_field.js`
- Create: `static/src/fields/rq_block_html/rq_block_dialogs.js` (galeria + variáveis)
- Create: `static/src/fields/rq_block_html/rq_block_html.xml`
- Create: `static/src/fields/rq_block_html/rq_block_html.scss`
- Create: `static/tests/rq_var_dom_tests.js` (QUnit)
- Modify: `__manifest__.py` (`web.assets_backend` += `afr_qualificacao/static/src/fields/rq_block_html/*`; `web.qunit_suite_tests` += `afr_qualificacao/static/tests/rq_var_dom_tests.js`)
- Modify: `views/relatorio_texto_views.xml` (`view_relatorio_block_form`)
- Modify: `views/relatorio_snippet_views.xml` (form usa `widget="rq_block_html"`, `options="{'catalog': 'static'}"`)
- Modify: `models/relatorio_block.py` (`action_edit_block`: `"context": {"dialog_size": "extra-large"}`)

**Interfaces:**
- Consumes: `afr.qualificacao.relatorio.rq_variable_catalog()`, `.rq_variable_catalog_static()`, `.rq_preview_block(body)`; `afr.relatorio.snippet.rq_snippet_list()`; categorias `tabela/lista/destaque/layout`.
- Produces: field widget `rq_block_html`; funções `normalizeVars(root)`, `decorateVars(root, catalogByExpr)`, `cleanVarsHtml(html) -> string`, `makeVarNode(doc, expr, label) -> HTMLElement`.

- [ ] **Step 1: QUnit falhando** `static/tests/rq_var_dom_tests.js`:

```js
/** @odoo-module **/
import { normalizeVars, decorateVars, cleanVarsHtml } from "@afr_qualificacao/fields/rq_block_html/rq_var_dom";

function el(html) { const d = document.createElement("div"); d.innerHTML = html; return d; }
const CAT = { "criterio['tolerancia']": { label: "Tolerância acima (°C)", value: "3" } };

QUnit.module("afr_qualificacao.rq_var_dom", () => {
    QUnit.test("normalize wraps bare tokens once", (assert) => {
        const d = el("<p>A {{ criterio['tolerancia'] }} B</p>");
        normalizeVars(d); normalizeVars(d);
        assert.strictEqual(d.innerHTML,
            '<p>A <span class="rq-var">{{ criterio[\'tolerancia\'] }}</span> B</p>');
    });
    QUnit.test("decorate then clean is identity", (assert) => {
        const src = '<p>A <span class="rq-var">{{ criterio[\'tolerancia\'] }}</span> B</p>';
        const d = el(src);
        decorateVars(d, CAT);
        const span = d.querySelector(".rq-var");
        assert.strictEqual(span.getAttribute("contenteditable"), "false");
        assert.strictEqual(span.textContent, "Tolerância acima (°C)");
        assert.strictEqual(cleanVarsHtml(d.innerHTML), src);
        decorateVars(d, CAT);
        assert.strictEqual(cleanVarsHtml(d.innerHTML), src);
    });
    QUnit.test("unknown expr decorates with expr as label", (assert) => {
        const d = el('<p><span class="rq-var">{{ foo.bar }}</span></p>');
        decorateVars(d, {});
        assert.strictEqual(d.querySelector(".rq-var").textContent, "foo.bar");
        assert.ok(d.querySelector(".rq-var").classList.contains("rq-var-unknown"));
        assert.strictEqual(cleanVarsHtml(d.innerHTML), '<p><span class="rq-var">{{ foo.bar }}</span></p>');
    });
});
```

- [ ] **Step 2: Implementar `rq_var_dom.js`**

```js
/** @odoo-module **/
// Etiquetas de variável do editor de bloco. Formato salvo:
// <span class="rq-var">{{ EXPR }}</span>. Decoração (label, contenteditable,
// data-rq-expr, title, rq-var-unknown) existe SÓ no DOM do editor.
const TOKEN_RE = /\{\{\s*(.+?)\s*\}\}/g;
const DECOR_CLASSES = ["rq-var-unknown"];

export function makeVarNode(doc, expr, label) {
    const span = doc.createElement("span");
    span.className = "rq-var";
    span.textContent = `{{ ${expr} }}`;
    if (label !== undefined) decorateOne(span, expr, label, false);
    return span;
}

export function normalizeVars(root) {
    const doc = root.ownerDocument;
    const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const texts = [];
    while (walker.nextNode()) {
        const n = walker.currentNode;
        if (n.parentElement && n.parentElement.closest(".rq-var")) continue;
        if (TOKEN_RE.test(n.nodeValue)) texts.push(n);
        TOKEN_RE.lastIndex = 0;
    }
    for (const n of texts) {
        const frag = doc.createDocumentFragment();
        let last = 0;
        n.nodeValue.replace(TOKEN_RE, (m, expr, idx) => {
            frag.append(n.nodeValue.slice(last, idx), makeVarNode(doc, expr.trim()));
            last = idx + m.length;
        });
        frag.append(n.nodeValue.slice(last));
        n.replaceWith(frag);
    }
}

function exprOf(span) {
    if (span.dataset.rqExpr) return span.dataset.rqExpr;
    const m = /\{\{\s*(.+?)\s*\}\}/.exec(span.textContent);
    return m ? m[1].trim() : span.textContent.trim();
}

function decorateOne(span, expr, label, unknown) {
    span.dataset.rqExpr = expr;
    span.setAttribute("contenteditable", "false");
    span.title = `{{ ${expr} }}`;
    span.textContent = label;
    span.classList.toggle("rq-var-unknown", unknown);
}

export function decorateVars(root, catalogByExpr) {
    for (const span of root.querySelectorAll("span.rq-var")) {
        const expr = exprOf(span);
        const item = catalogByExpr[expr];
        decorateOne(span, expr, item ? item.label : expr, !item);
        if (item && item.value !== undefined && item.value !== "") {
            span.title = `{{ ${expr} }} → ${item.value}`;
        }
    }
}

export function cleanVarsHtml(html) {
    // Sem etiqueta ⇒ devolve a string intacta (re-serializar via innerHTML
    // faria o HtmlField achar que um bloco intocado mudou).
    if (!html || !html.includes("rq-var")) return html;
    const d = document.createElement("div");
    d.innerHTML = html;
    for (const span of d.querySelectorAll("span.rq-var")) {
        const expr = exprOf(span);
        for (const a of [...span.attributes]) {
            if (a.name !== "class") span.removeAttribute(a.name);
        }
        DECOR_CLASSES.forEach((c) => span.classList.remove(c));
        span.className = "rq-var";
        span.textContent = `{{ ${expr} }}`;
    }
    return d.innerHTML;
}
```

Rodar QUnit: subir UI (:8084), abrir `http://localhost:8084/web/tests?module=afr_qualificacao.rq_var_dom` via agent-browser (logado admin) — 3/3 verde. (Se o módulo QUnit não carregar por ordem de bundle, ajustar o manifest; não pular.)

- [ ] **Step 3: Diálogos `rq_block_dialogs.js`** (OWL, `Dialog` de `@web/core/dialog/dialog`):
  - `RqSnippetDialog` props `{snippets, onPick(body), close}`: abas (Tabelas técnicas | Listas e texto | Destaques | Layout) com `state.cat`; grade de cards (`.rq-snip-card`: nome + `<div class="rq-snip-thumb"><div class="rq-snip-inner" t-out="markup(body)"/></div>` (um wrapper só escalado; escalar cada filho gera sobreposição) com `transform: scale(.45)` num container fixo 220×150, `pointer-events:none`); clique → `onPick(body)`; `close()`.
  - `RqVariableDialog` props `{catalog, onPick(item), close}`: input de busca (filtra label/expr, case/acento-insensível via `normalize("NFD")`), lista agrupada por `group`; linha = label + valor atual em cinza (`→ 3`) ou "sem valor" em âmbar; clique → `onPick(item)`; `close()`.
  - Templates em `rq_block_html.xml` (`afr_qualificacao.RqSnippetDialog`, `afr_qualificacao.RqVariableDialog`), título pt-BR "Inserir bloco pronto" / "Inserir variável".

- [ ] **Step 4: Widget `rq_block_html_field.js`**

```js
/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { HtmlField } from "@web_editor/js/backend/html_field";
import { markup, useState } from "@odoo/owl";
import { normalizeVars, decorateVars, cleanVarsHtml, makeVarNode } from "./rq_var_dom";
import { RqSnippetDialog, RqVariableDialog } from "./rq_block_dialogs";

export class RqBlockHtmlField extends HtmlField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this.rq = useState({ mode: "edit", previewHtml: "", missing: [], loading: false });
        this.catalogByExpr = {};
        this.catalog = [];
    }
    get isStatic() { return this.props.rqCatalog === "static"; }
    get relatorioId() {
        const r = this.props.record.data.relatorio_id;
        return Array.isArray(r) ? r[0] : r && r.id ? r.id : r;   // m2o no OWL 16 = [id, name]
    }
    get wysiwygOptions() {
        const opts = super.wysiwygOptions;
        opts.powerboxCommands = [
            ...(opts.powerboxCommands || []),
            { category: "Relatório", name: "Bloco pronto", priority: 20,
              description: "Tabela, lista, destaque ou layout pronto",
              fontawesome: "fa-th-large", callback: () => this.openSnippets() },
            { category: "Relatório", name: "Variável", priority: 19,
              description: "Dado do relatório (critério, cliente, anexo…)",
              fontawesome: "fa-tag", callback: () => this.openVariables() },
        ];
        return opts;
    }
    async loadCatalog() {
        this.catalog = this.isStatic || !this.relatorioId
            ? await this.orm.call("afr.qualificacao.relatorio", "rq_variable_catalog_static", [])
            : await this.orm.call("afr.qualificacao.relatorio", "rq_variable_catalog", [[this.relatorioId]]);
        this.catalogByExpr = Object.fromEntries(this.catalog.map((c) => [c.expr, c]));
    }
    async startWysiwyg(...args) {
        await super.startWysiwyg(...args);
        await this.loadCatalog();
        this.decorate();
    }
    decorate() {
        const editor = this.wysiwyg && this.wysiwyg.odooEditor;
        if (!editor) return;
        editor.observerUnactive("rqDecorate");
        normalizeVars(editor.editable);
        decorateVars(editor.editable, this.catalogByExpr);
        editor.observerActive("rqDecorate");
    }
    getEditingValue() {
        const v = super.getEditingValue();
        return v === null ? v : cleanVarsHtml(v);
    }
    saveRange() {
        const sel = this.wysiwyg.odooEditor.document.getSelection();
        this._range = sel && sel.rangeCount &&
            this.wysiwyg.odooEditor.editable.contains(sel.anchorNode)
            ? sel.getRangeAt(0).cloneRange() : null;
    }
    insertNode(node) {
        const editor = this.wysiwyg.odooEditor;
        this.wysiwyg.focus();
        const sel = editor.document.getSelection();
        sel.removeAllRanges();
        if (this._range) {
            sel.addRange(this._range);
        } else {
            const r = editor.document.createRange();
            r.selectNodeContents(editor.editable);
            r.collapse(false);
            sel.addRange(r);
        }
        editor.execCommand("insert", node);
        editor.sanitize(editor.editable);
        this.decorate();
    }
    async openSnippets() {
        this.saveRange();
        const snippets = await this.orm.call("afr.relatorio.snippet", "rq_snippet_list", []);
        this.dialogService.add(RqSnippetDialog, {
            snippets,
            onPick: (body) => {
                // UMA inserção só: Range é vivo; inserir filho a filho com o
                // mesmo Range pode inverter a ordem.
                const doc = this.wysiwyg.odooEditor.document;
                const tmp = doc.createElement("div");
                tmp.innerHTML = body;
                const frag = doc.createDocumentFragment();
                frag.append(...tmp.childNodes);
                this.insertNode(frag);
            },
        });
    }
    async openVariables() {
        this.saveRange();
        await this.loadCatalog();
        this.dialogService.add(RqVariableDialog, {
            catalog: this.catalog,
            onPick: (item) => {
                const doc = this.wysiwyg.odooEditor.document;
                this.insertNode(makeVarNode(doc, item.expr, item.label));
            },
        });
    }
    async setMode(mode) {
        if (mode === this.rq.mode) return;
        if (mode === "preview") {
            if (this.isStatic || !this.relatorioId) return;
            this.rq.loading = true;
            const res = await this.orm.call("afr.qualificacao.relatorio", "rq_preview_block",
                [[this.relatorioId], this.getEditingValue() || ""]);
            this.rq.previewHtml = markup(res.html);
            this.rq.missing = res.missing.map((e) => (this.catalogByExpr[e] || {}).label || e);
            this.rq.loading = false;
        }
        this.rq.mode = mode;
    }
}
RqBlockHtmlField.template = "afr_qualificacao.RqBlockHtmlField";
RqBlockHtmlField.props = { ...HtmlField.props, rqCatalog: { type: String, optional: true } };
RqBlockHtmlField.extractProps = (...args) => {
    const [{ attrs }] = args;
    return { ...HtmlField.extractProps(...args), rqCatalog: attrs.options.catalog };
};
registry.category("fields").add("rq_block_html", RqBlockHtmlField);
```

Notas para o implementador (verificar no browser, não assumir):
- Snippet entra como UM `DocumentFragment` num único `execCommand('insert')`. Critério: tabela inserida fica irmã do parágrafo, na ordem do snippet. Se o `insert` do OdooEditor não aceitar fragment, embrulhar num `<div>` e desembrulhar após inserir.
- Se `startWysiwyg` não for o hook certo em 16 (valor redesenhado depois), decorar também no `onWysiwygBlur`/após `commitChanges` não é necessário — mas etiquetas DEVEM aparecer ao abrir bloco salvo.
- Seleção: backspace imediatamente após etiqueta deve remover a etiqueta inteira.

- [ ] **Step 5: Template `rq_block_html.xml`** — `afr_qualificacao.RqBlockHtmlField` com `t-inherit="web_editor.HtmlField" t-inherit-mode="primary"`: envolver o conteúdo num `<div class="rq-block-editor">` com, antes do editor, a barra `.rq-toolbar` (sticky top 0): botões `+ Inserir bloco` (`t-on-click="openSnippets"`, `fa-th-large`), `Variável` (`fa-tag`, `openVariables`), `Imagem` (`fa-image`; callback abre o comando nativo de mídia: `this.wysiwyg.openMediaDialog()` se existir em 16, senão remover o botão e confiar no `/image`), e à direita um `btn-group` Editar | Visualizar (`setMode('edit'|'preview')`, oculto se `isStatic`). Com `rq.mode==='preview'`: esconder a área do editor via classe `d-none` (não destruir) e mostrar `<div class="rq-preview o_readonly" t-out="rq.previewHtml"/>` + alerta âmbar "Variáveis sem valor: …" quando `rq.missing.length`. Botões desativados em readonly.

- [ ] **Step 6: SCSS `rq_block_html.scss`**
```scss
.rq-block-editor {
  .rq-toolbar { position: sticky; top: 0; z-index: 5; display: flex; gap: .5rem; align-items: center;
    padding: .4rem .5rem; background: $o-view-background-color; border-bottom: 1px solid $border-color; }
  .note-editable, .odoo-editor-editable, .rq-preview { max-width: 794px; margin: 0 auto; min-height: 320px;
    padding: 24px 32px; font-size: 11pt; line-height: 1.45; }
  span.rq-var { display: inline-block; padding: 0 .45em; margin: 0 .05em; border-radius: 1em;
    background: #e7f1ff; color: #0a58ca; border: 1px solid #b6d4fe; font-size: .92em; line-height: 1.5;
    cursor: default; user-select: all;
    &.rq-var-unknown { background: #fdecea; color: #b02a37; border-color: #f5c2c7; }
  }
}
.rq-snip-card { cursor: pointer; border: 1px solid $border-color; border-radius: .5rem; overflow: hidden;
  &:hover { border-color: $o-brand-primary; box-shadow: 0 0 0 2px rgba($o-brand-primary, .2); } }
.rq-snip-thumb { width: 220px; height: 150px; overflow: hidden; pointer-events: none;
  > .rq-snip-inner { transform: scale(.45); transform-origin: top left; width: 222%; } }
```

- [ ] **Step 7: Form do bloco** (`view_relatorio_block_form`):

```xml
<form string="Bloco do Relatório">
    <sheet>
        <field name="relatorio_id" invisible="1"/>
        <div class="d-flex flex-wrap align-items-end gap-3 mb-2">
            <div class="flex-grow-1">
                <label for="title"/>
                <h3 class="mb-0"><field name="title" placeholder="Título do bloco"/></h3>
            </div>
            <field name="block_kind" readonly="1" class="badge text-bg-light"/>
        </div>
        <div class="d-flex flex-wrap gap-4 mb-2">
            <div><field name="included" widget="boolean_toggle"/><label for="included"/></div>
            <div><field name="page_break" widget="boolean_toggle"/><label for="page_break"/></div>
            <div><field name="show_number" widget="boolean_toggle"/><label for="show_number"/></div>
            <div><field name="show_title" widget="boolean_toggle"/><label for="show_title"/></div>
        </div>
        <details class="mb-3">
            <summary class="text-muted">Mais opções</summary>
            <group>
                <field name="parent_id"
                       domain="[('relatorio_id', '=', relatorio_id), ('id', '!=', id), ('is_anexo_content', '=', False)]"/>
                <field name="section_id" readonly="1"/>
            </group>
        </details>
        <field name="body" widget="rq_block_html" nolabel="1"/>
    </sheet>
    <footer>
        <button string="Salvar e Fechar" class="btn-primary" special="save"/>
        <button string="Descartar" class="btn-secondary" special="cancel"/>
    </footer>
</form>
```
(Se `<details>` não renderizar/for sanitizado pela view, trocar por `<group string="Mais opções">` aninhado — ver memória "Odoo group string label requires nesting".) `action_edit_block`: acrescentar `"context": {"dialog_size": "extra-large"}`.

- [ ] **Step 8: Upgrade + validação UI (agent-browser)** no `qualificacao-dev`: `-u afr_qualificacao`, restart `odoo_engenapp-web-qualificacao-1`, login (logout antes). Abrir um relatório → aba Texto → Editar bloco "Critérios de Aceitação": (a) `{{ }}` antigos aparecem como etiquetas; (b) `/variavel` e botão Variável inserem etiqueta com label; (c) `/bloco` insere "Critérios de aceitação" como tabela; (d) Visualizar mostra "3" (ou valor do relatório) no lugar da etiqueta e aviso de missing quando houver; (e) salvar, reabrir: etiquetas voltam, sem atributos extras no banco (conferir `body` via odoo-mcp/shell contém só `<span class="rq-var">{{ … }}</span>`); (f) backspace após etiqueta apaga ela inteira. Screenshot de cada estado.

- [ ] **Step 9: Rodar suíte Python do módulo inteira** (regressão) + QUnit 3/3.

- [ ] **Step 10: Commit**: `feat(relatorio): editor de bloco com blocos prontos, variáveis e preview`.

---

### Task 4: Imagem no PDF, bump de versão e validação ponta-a-ponta

**Files:**
- Possibly modify: `models/relatorio_texto.py` (`_render_body_html`: fallback data-URI)
- Modify: `__manifest__.py` (version `16.0.8.8.0`)
- Test: `tests/test_relatorio_editor.py` (classe `TestRelatorioEditorImage`)

**Interfaces:**
- Consumes: `_render_body_html(body)` da Task 2; pipeline de minuta existente (`relatorio_pdf.py`).
- Produces: `_rq_inline_images(html: str) -> str` (só se o fallback for necessário).

- [ ] **Step 1: Verificação empírica** no `qualificacao-dev` via UI: no bloco, inserir "Figura com legenda", trocar imagem por upload (PNG qualquer gerado localmente), aplicar largura 50% e crop pela toolbar nativa, salvar, gerar Minuta e abrir o PDF. Registrar: imagem aparece? cortada? tamanho?

- [ ] **Step 2 (só se a imagem NÃO aparecer no PDF): teste falhando**

```python
@tagged("post_install", "-at_install")
class TestRelatorioEditorImage(RelatorioTestCommon):
    def test_private_attachment_image_inlined(self):
        import base64
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
        att = self.env["ir.attachment"].create({"name": "f.png", "datas": base64.b64encode(png),
                                                "res_model": "afr.relatorio.block", "res_id": 0})
        html, ok = self.rel._render_body_html('<p><img src="/web/image/%d"/></p>' % att.id)
        self.assertTrue(ok)
        self.assertIn('src="data:image/png;base64,', str(html))
```
Implementar `_rq_inline_images` (regex `src="/web/image/(\d+)[^"]*"` → `sudo().browse(id)`, só `mimetype` `image/*`, `data:<mimetype>;base64,<datas>`) e chamar no fim de `_render_body_html` quando `ok`. Repetir Step 1 até a imagem sair no PDF.

- [ ] **Step 3: Bump** `__manifest__.py` `"version": "16.0.8.8.0"`.

- [ ] **Step 4: Suíte completa do módulo** (via test-runner) — sem falhas novas.

- [ ] **Step 5: Commit**: `feat(relatorio): imagem de bloco no PDF e bump 16.0.8.8.0` (ou `chore: bump 16.0.8.8.0` se o fallback não foi necessário).
