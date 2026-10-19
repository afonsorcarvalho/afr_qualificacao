# Relatório Final — Anexos Unificados Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Acabar com o bloco "Separador de Anexo": a página separadora nasce só do anexo, o conteúdo de anexo (protocolo/micro) sai da lista do corpo, e a aba Texto mostra Corpo → Anexos na ordem do PDF.

**Architecture:** O vínculo anexo→bloco passa a ser só `afr.relatorio.anexo.block_id`. Um bloco apontado por algum anexo é "conteúdo de anexo" (`is_anexo_content`, stored) e fica fora do corpo, da numeração e da lista `body_block_ids` mostrada na tela. O kind `anexo_separador` some (seed, selection, QWeb, regras); um pre-migrate apaga os legados dos bancos de dev.

**Tech Stack:** Odoo 16 (Python ORM, QWeb, XML views), testes `TransactionCase` via container Docker.

**Spec:** `addons/afr_qualificacao/docs/superpowers/specs/2026-09-29-relatorio-anexos-unificados-design.md`

## Global Constraints

- Todos os paths são relativos a `addons/afr_qualificacao/` (git submodule, branch `feat/relatorio-final`). Git sempre de dentro do submodule.
- **Pré-requisito do orquestrador (antes do Task 1):** a árvore tem trabalho não commitado de outras frentes (relatório: `__manifest__.py` assets, views, `relatorio_pdf.py`, template corpo; wizard Aplicar Procedimento). Ele precisa estar commitado (com OK do user) antes de começar, senão os commits deste plano misturam mudanças. Não usar `git stash`/checkout (quebra o dev server :8084).
- Commits via agente `git-commit-push` (haiku), `cwd` = submodule, só os arquivos do task. Sem push.
- Versão: `16.0.8.5.1` → `16.0.8.6.0` (Task 2).
- Sem migração de dados de produção (labquali em dev); só o pre-migrate de limpeza do Task 2.
- Comentários/docstrings em português, no estilo do código vizinho.
- Comando de teste (container `odoo_engenapp-web-1`, db `odoo_ecm_test`):
  `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http 2>&1 | grep -E "FAIL|ERROR|Ran |tests"`
  Suíte completa: `--test-tags /afr_qualificacao`. Baseline conhecido: 2 falhas pré-existentes de relatório (`test_proxima_qualificacao_follows_emission_date`, `test_level1_title_zero_padded_and_toc_uses_same_number`) — não são regressão deste plano; qualquer outra é.
- Não mexer no container `web-qualificacao` exceto no Task 3 (validação de UI).

## Review Focus

1. Edição do corpo pela nova lista `body_block_ids` precisa continuar invalidando aprovações/bump editorial como `block_ids` faz — teste no Task 1.
2. Bloco com `anexo_code` mas sem anexo apontando (anexo apagado) volta ao corpo **e** à numeração, sem divergir — teste no Task 1.
3. Trocar `anexo.block_id` para outro bloco recalcula `is_anexo_content` dos dois (antigo volta ao corpo) — teste no Task 1.
4. Relatório já gerado no dev com blocos `anexo_separador` não quebra o upgrade (pre-migrate) — teste no Task 2.
5. "Editar conteúdo" num anexo sem `block_id` não pode estourar com erro cru — teste no Task 3.

---

### Task 1: `is_anexo_content`, `body_block_ids` e corpo/numeração pelo vínculo real

**Files:**
- Modify: `models/relatorio_block.py` (campos novos; `_compute_display_number` depends)
- Modify: `models/relatorio_texto.py:36-39` (campo `body_block_ids`), `:235-239` (`_body_blocks`)
- Modify: `models/relatorio_emissao_flow.py:89-95` (`_RQ_EDITORIAL_FIELDS`)
- Test: `tests/test_relatorio_template.py` (classe `TestRelatorioApplyTemplate`), `tests/test_relatorio_emissao.py` (classe `TestRelatorioAprovacoes`)

**Interfaces:**
- Produces: `afr.relatorio.block.anexo_ids` (O2m `afr.relatorio.anexo`/`block_id`), `afr.relatorio.block.is_anexo_content` (Boolean stored), `afr.qualificacao.relatorio.body_block_ids` (O2m com domain `[("is_anexo_content", "=", False)]`). `_body_blocks()` filtra `included and not is_anexo_content`.

- [ ] **Step 1: Testes que falham** — em `TestRelatorioApplyTemplate` (fixture já tem RQT-HOSP aplicado, com anexos `protocolo` e `micro` de slot `bloco` ligados a blocos `protocolo`/`laudo_micro`):

```python
    def test_anexo_content_blocks_leave_body_list(self):
        proto = self.rel.anexo_ids.filtered(lambda a: a.code == "protocolo").block_id
        self.assertTrue(proto.is_anexo_content)
        self.assertNotIn(proto, self.rel.body_block_ids)
        self.assertNotIn(proto, self.rel._body_blocks())
        objetivo = self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")
        self.assertFalse(objetivo.is_anexo_content)
        self.assertIn(objetivo, self.rel.body_block_ids)

    def test_relinking_anexo_block_recomputes_both(self):
        anexo = self.rel.anexo_ids.filtered(lambda a: a.code == "protocolo")
        old = anexo.block_id
        new = self.env["afr.relatorio.block"].create({
            "relatorio_id": self.rel.id, "sequence": 999, "block_kind": "protocolo",
            "title": "Outro protocolo",
        })
        anexo.block_id = new
        self.assertTrue(new.is_anexo_content)
        self.assertFalse(old.is_anexo_content)
        self.assertIn(old, self.rel.body_block_ids)

    def test_orphan_anexo_code_block_is_body_and_numbered(self):
        anexo = self.rel.anexo_ids.filtered(lambda a: a.code == "protocolo")
        block = anexo.block_id
        block.show_number = True
        anexo.unlink()
        self.assertFalse(block.is_anexo_content)
        self.assertIn(block, self.rel._body_blocks())
        self.assertIn(block.id, self.rel._block_numbering())
        self.assertTrue(block.display_number)
```

E ajustar o existente `test_block_numbering_ignores_anexo_blocks` (hoje `filtered("anexo_code")`, que no Task 2 deixará de ter separadores) para:

```python
    def test_block_numbering_ignores_anexo_blocks(self):
        numbers = self.rel._block_numbering()
        anexo_blocks = self.rel.block_ids.filtered("is_anexo_content")
        self.assertTrue(anexo_blocks)
        for blk in anexo_blocks:
            self.assertNotIn(blk.id, numbers)
        objetivo = self.rel.block_ids.filtered(lambda b: b.title == "Objetivo")
        self.assertEqual(numbers[objetivo.id], "1")
        qi = self.rel.block_ids.filtered(lambda b: b.title == "Qualificação de Instalação (QI)")
        self.assertEqual(numbers[qi.id], "4.1")
```

Em `TestRelatorioAprovacoes` (`tests/test_relatorio_emissao.py`):

```python
    def test_editing_body_block_list_invalidates(self):
        self._approve_internal()
        self.rel.write({"body_block_ids": [(1, self.block.id, {"body": "<p>via lista</p>"})]})
        self.assertFalse(self._internal_approved())
```

- [ ] **Step 2: Rodar e ver falhar** — classes `TestRelatorioApplyTemplate` e `TestRelatorioAprovacoes`. Esperado: `AttributeError`/`KeyError` em `is_anexo_content`/`body_block_ids`.

- [ ] **Step 3: Implementar**

`models/relatorio_block.py` — após `anexo_code`:

```python
    anexo_ids = fields.One2many(
        "afr.relatorio.anexo", "block_id", string="Anexos que usam este bloco")
    is_anexo_content = fields.Boolean(
        compute="_compute_is_anexo_content", store=True, index=True,
        help="Bloco apontado por um anexo (origem 'Bloco do relatório'): "
             "impresso na posição do anexo, fora do corpo e da numeração.")
```

```python
    @api.depends("anexo_ids")
    def _compute_is_anexo_content(self):
        for block in self:
            block.is_anexo_content = bool(block.anexo_ids)
```

No `@api.depends` de `_compute_display_number`, trocar `"anexo_code"` e `"relatorio_id.block_ids.anexo_code"` por `"is_anexo_content"` e `"relatorio_id.block_ids.is_anexo_content"`.

`models/relatorio_texto.py` — após `block_ids`:

```python
    body_block_ids = fields.One2many(
        "afr.relatorio.block", "relatorio_id", string="Corpo do relatório",
        domain=[("is_anexo_content", "=", False)], copy=False,
        help="Blocos do corpo; conteúdo de anexo é editado pelo anexo.")
```

`_body_blocks()`:

```python
    def _body_blocks(self):
        """Blocos do corpo principal (incluídos e que não são conteúdo de
        anexo), ordenados. Conteúdo de anexo = bloco apontado por
        `afr.relatorio.anexo.block_id`."""
        self.ensure_one()
        return self.block_ids.filtered(
            lambda b: b.included and not b.is_anexo_content).sorted(sort_key)
```

`models/relatorio_emissao_flow.py` — incluir `"body_block_ids"` em `_RQ_EDITORIAL_FIELDS`.

- [ ] **Step 4: Rodar e ver passar** — as duas classes, depois `tests/test_relatorio_pdf.py` e `tests/test_relatorio_rules.py` inteiros (`--test-tags /afr_qualificacao:TestRelatorioBuild,/afr_qualificacao:TestRelatorioAnexoFiles` ou o módulo todo). Nota: testes de PDF que criam bloco com `anexo_code` **sem** anexo apontando passam a ter esse bloco no corpo; se algum quebrar por isso, o teste estava contando com o critério antigo — ajustar ligando o bloco a um anexo (`block_id`), não voltando ao `anexo_code`.

- [ ] **Step 5: Commit** — `feat(relatorio): anexo content derives from anexo.block_id, not anexo_code` com os 3 models + 2 testes.

---

### Task 2: Remover o kind `anexo_separador` (seed, QWeb, regras, fakes) + pre-migrate

**Files:**
- Modify: `models/relatorio_template.py:14-22` (kinds), `:102-106` (docstring), `:120-124` (remover `_check_separator_has_code`)
- Modify: `hooks.py:376-381` (remover `_rqt_separators`), `:426`, `:450` (remover uso)
- Modify: `models/relatorio_texto.py:136-140` (`_apply_template_anexos`), `:257-261` (remover `_anexo_separator_block`)
- Modify: `reports/relatorio_corpo_templates.xml:274`, `:279-292`
- Modify: `models/relatorio_rules.py:58-90` (`rendered_blocks` + comentários)
- Modify: `tests/relatorio_fakes.py:100-120`, `:173-180` (`FakeCorpo`)
- Create: `migrations/16.0.8.6.0/pre-migrate.py`
- Modify: `__manifest__.py:3` (versão `16.0.8.6.0`)
- Test: `tests/test_relatorio_template.py`, `tests/test_relatorio_rules.py:150-160`

**Interfaces:**
- Consumes: `is_anexo_content`, `_body_blocks()` do Task 1.
- Produces: `REPORT_BLOCK_KINDS` sem `anexo_separador`; `rq_anexo` renderiza só página "Anexo N"+título+marcador+`block_id`; `rendered_blocks(rel)` = corpo + `block_id` dos anexos "bloco" incluídos.

- [ ] **Step 1: Testes que falham / ajustados** em `tests/test_relatorio_template.py`:

`test_block_kinds` → lista esperada sem `"anexo_separador"`:

```python
            ["static", "capa", "indice", "protocolo", "laudo_micro", "assinaturas"],
```

Apagar `test_separator_line_requires_anexo_code`. Reescrever `test_separator_line_excluded_from_numbering` como:

```python
    def test_anexo_code_line_excluded_from_template_numbering(self):
        """Linha de template com `anexo_code` (conteúdo de anexo) não conta
        na numeração — espelha o `is_anexo_content` do relatório."""
        Line = self.env["afr.relatorio.template.line"]
        root = Line.create({"template_id": self.tpl.id, "sequence": 10,
                            "block_kind": "static", "section_id": self.section.id})
        content = Line.create({"template_id": self.tpl.id, "sequence": 15,
                               "block_kind": "protocolo", "anexo_code": "protocolo"})
        second = Line.create({"template_id": self.tpl.id, "sequence": 20,
                              "block_kind": "static", "section_id": self.section.id})
        self.assertEqual(
            (root.display_number, content.display_number, second.display_number),
            ("1", "", "2"),
        )
```

Em `test_anexo_code_format_rejected_across_models`, trocar a linha de template criada com `"block_kind": "anexo_separador"` por `"block_kind": "protocolo"`.

Em `test_hosp_lines_have_kinds_and_bloco_links` (`~:610`):

```python
        kinds = set(self.hosp.line_ids.mapped("block_kind"))
        self.assertTrue({"capa", "indice", "static", "protocolo", "laudo_micro",
                         "assinaturas"} <= kinds)
        self.assertNotIn("anexo_separador", kinds)
```

Novos em `TestRelatorioApplyTemplate`:

```python
    def test_applied_report_has_no_separator_blocks(self):
        self.assertNotIn("anexo_separador", self.rel.block_ids.mapped("block_kind"))
        proto = self.rel.anexo_ids.filtered(lambda a: a.code == "protocolo")
        self.assertEqual(proto.block_id.block_kind, "protocolo")

    def test_corpo_html_lists_anexos_in_anexo_order(self):
        self.rel.anexo_ids.filtered(lambda a: a.code == "graficos").sequence = 1
        self.rel.anexo_ids.filtered(lambda a: a.code == "dados").included = False
        html, _f = self.env["ir.actions.report"]._render_qweb_html(
            "afr_qualificacao.report_relatorio_corpo", self.rel.ids,
            data={"page_map": {}, "with_markers": True},
        )
        html = html.decode()
        codes = [a.code for a in self.rel._anexos_included()]
        self.assertEqual(codes[0], "graficos")
        positions = [html.index("@@RQ:anexo:%s@@" % c) for c in codes]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("@@RQ:anexo:dados@@", html)
```

Teste do pre-migrate (nova classe no fim de `tests/test_relatorio_template.py`):

```python
class TestPreMigrateSeparators(RelatorioTemplateFixture):

    def test_pre_migrate_deletes_legacy_separators(self):
        import importlib.util
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "migrations",
                            "16.0.8.6.0", "pre-migrate.py")
        spec = importlib.util.spec_from_file_location("rq_pre_migrate_8_6", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cr = self.env.cr
        cr.execute("""
            INSERT INTO afr_relatorio_block
                   (relatorio_id, sequence, block_kind, anexo_code, included,
                    page_break, show_number, show_title)
            VALUES (%s, 500, 'anexo_separador', 'dados', true, false, false, false)
        """, [self.rel.id])
        cr.execute("""
            INSERT INTO afr_relatorio_template_line
                   (template_id, sequence, block_kind, anexo_code, page_break,
                    show_number, show_title)
            VALUES (%s, 500, 'anexo_separador', 'dados', false, false, false)
        """, [self.hosp.id])
        mod.migrate(cr, "16.0.8.5.1")
        cr.execute("SELECT count(*) FROM afr_relatorio_block WHERE block_kind = 'anexo_separador'")
        self.assertEqual(cr.fetchone()[0], 0)
        cr.execute("SELECT count(*) FROM afr_relatorio_template_line WHERE block_kind = 'anexo_separador'")
        self.assertEqual(cr.fetchone()[0], 0)
```

(Se o INSERT falhar por coluna NOT NULL não listada, conferir `\d afr_relatorio_block` no db de teste e completar as colunas obrigatórias — não relaxar o teste.)

- [ ] **Step 2: Rodar e ver falhar** — `TestRelatorioTemplateModels`, `TestRelatorioSeeds`, `TestRelatorioApplyTemplate`, `TestPreMigrateSeparators`. Esperado: kinds ainda com separador; seed cria separadores; arquivo de migração inexistente.

- [ ] **Step 3: Implementar**

`models/relatorio_template.py`: remover a tupla `("anexo_separador", "Separador de Anexo")` de `REPORT_BLOCK_KINDS`; remover `_check_separator_has_code`; docstring de `_compute_display_number` da linha de template:

```python
        """Linhas com `anexo_code` (conteúdo de anexo, p.ex. protocolo) não
        contam na numeração — espelha `is_anexo_content`/`_body_blocks()` do
        relatório, para a numeração do template bater com o PDF."""
```

`hooks.py`: apagar `def _rqt_separators(...)` e as duas linhas `+ _rqt_separators([...], 500)`. O seed é upsert por xmlid (`_upsert_xmlid`); conferir em `_seed_relatorio_templates` (`hooks.py:473+`) se linhas de template que sumiram do spec são apagadas — se não forem, o pre-migrate cuida delas nos bancos existentes; não adicionar lógica de remoção ao seed.

`models/relatorio_texto.py` `_apply_template_anexos` — filtro do bloco:

```python
            if line.slot_kind == "bloco":
                block = self.block_ids.filtered(
                    lambda b, c=line.code: b.anexo_code == c)[:1]
```

Apagar `_anexo_separator_block`.

`reports/relatorio_corpo_templates.xml`:
- `rq_block`: `t-if="block.block_kind not in ('capa', 'indice') and block.body"`.
- `rq_anexo` inteiro:

```xml
    <!-- Uma posição de anexo incluída: página separadora (+ conteúdo se slot 'bloco'). Espera: doc, anexo, markers -->
    <template id="rq_anexo">
        <div class="rq-anexo-sep" t-att-data-rq-anexo="anexo.code"><span t-if="markers" class="rq-mark" t-esc="'@@RQ:anexo:%s@@' % anexo.code"/>
            <div class="rq-anexo-eyebrow">Anexo</div>
            <div class="rq-anexo-num" t-esc="anexo.numero"/>
            <div class="rq-anexo-title" t-esc="anexo.title or ''"/>
            <div class="rq-anexo-rule"/>
        </div>
        <t t-if="anexo.slot_kind == 'bloco' and anexo.block_id and anexo.block_id.included">
            <t t-set="block" t-value="anexo.block_id"/>
            <t t-call="afr_qualificacao.rq_block"/>
        </t>
    </template>
```

`models/relatorio_rules.py`: comentário de `_TOKEN_SKIP_KINDS` sem a parte do separador; `rendered_blocks`:

```python
def rendered_blocks(rel):
    """Blocos que efetivamente aparecem no documento renderizado: o corpo
    (`_body_blocks()`, sem capa/índice — `_TOKEN_SKIP_KINDS`) mais, para cada
    anexo incluído de origem 'bloco', o `anexo.block_id` quando incluído e não
    capa/índice. Espelha `reports/relatorio_corpo_templates.xml` (`rq_block`/
    `rq_anexo`) e `tests/relatorio_fakes.py::FakeCorpo.render`, para as regras
    de token não acusarem bloco que nunca é impresso."""
    rel.ensure_one()
    blocks = rel._body_blocks().filtered(
        lambda b: b.block_kind not in _TOKEN_SKIP_KINDS)
    for anexo in rel._anexos_included():
        if (anexo.slot_kind == "bloco" and anexo.block_id and anexo.block_id.included
                and anexo.block_id.block_kind not in _TOKEN_SKIP_KINDS):
            blocks |= anexo.block_id
    return blocks
```

`tests/relatorio_fakes.py` `FakeCorpo.render` — laço dos anexos:

```python
        for anexo in rel._anexos_included():
            lines = mark("anexo:%s" % anexo.code)
            lines.append("ANEXO %s: %s" % (anexo.numero, anexo.title or ""))
            emit(lines, True)
            state["force_new"] = True  # page-break-after do separador
            if (anexo.slot_kind == "bloco" and anexo.block_id
                    and anexo.block_id.included):
                add_block(anexo.block_id, new_page=True)
```

e na docstring trocar "(+ `@@RQ:bloco:<id>@@` do `_anexo_separator_block(code)`)" por nada. Em `tests/test_relatorio_rules.py:156` atualizar a docstring para `('capa', 'indice')`.

`migrations/16.0.8.6.0/pre-migrate.py`:

```python
"""Anexos unificados (spec 2026-09-29): o kind `anexo_separador` saiu de
REPORT_BLOCK_KINDS — a página separadora nasce do próprio anexo. Apaga os
separadores legados dos relatórios e templates antes do registry carregar a
selection nova. Idempotente."""


def migrate(cr, version):
    cr.execute("DELETE FROM afr_relatorio_block WHERE block_kind = 'anexo_separador'")
    cr.execute(
        "DELETE FROM afr_relatorio_template_line WHERE block_kind = 'anexo_separador'")
```

`__manifest__.py`: `"version": "16.0.8.6.0",`.

- [ ] **Step 4: Rodar e ver passar** — as classes do Step 2 e depois a suíte completa do módulo. Esperado: só as 2 falhas de baseline. `grep -rn "anexo_separador\|_anexo_separator_block" models reports views hooks.py tests wizards` → só o pre-migrate, o teste do pre-migrate e o `assertNotIn` do seed.

- [ ] **Step 5: Commit** — `refactor(relatorio): drop anexo_separador block kind; separator page comes from the anexo` (arquivos listados + `migrations/16.0.8.6.0/`).

---

### Task 3: Tela — aba Texto com Corpo + Anexos, "Editar conteúdo" no anexo

**Files:**
- Modify: `views/relatorio_texto_views.xml:60-115` (aba Texto; remover page Anexos)
- Modify: `models/relatorio_anexo.py` (método `action_edit_block_content`)
- Test: `tests/test_relatorio_template.py` (`TestRelatorioApplyTemplate`)

**Interfaces:**
- Consumes: `body_block_ids` (Task 1); `afr.relatorio.block.action_edit_block()` (`models/relatorio_block.py:83`).
- Produces: `afr.relatorio.anexo.action_edit_block_content()` → dict de action (modal do bloco) ou `UserError` se não houver bloco.

- [ ] **Step 1: Testes que falham**

```python
    def test_edit_block_content_opens_linked_block(self):
        anexo = self.rel.anexo_ids.filtered(lambda a: a.code == "protocolo")
        action = anexo.action_edit_block_content()
        self.assertEqual(action["res_model"], "afr.relatorio.block")
        self.assertEqual(action["res_id"], anexo.block_id.id)
        self.assertEqual(action["target"], "new")

    def test_edit_block_content_without_block_raises(self):
        anexo = self.rel.anexo_ids.filtered(lambda a: a.code == "protocolo")
        anexo.block_id = False
        with self.assertRaises(UserError):
            anexo.action_edit_block_content()

    def test_texto_page_has_body_then_anexos_and_no_anexos_page(self):
        arch = self.env["afr.qualificacao.relatorio"].get_view(view_type="form")["arch"]
        self.assertNotIn('name="page_anexos"', arch)
        self.assertIn('name="body_block_ids"', arch)
        self.assertLess(arch.index('name="body_block_ids"'), arch.index('name="anexo_ids"'))
        self.assertIn("action_edit_block_content", arch)
```

- [ ] **Step 2: Rodar e ver falhar** — `TestRelatorioApplyTemplate`. Esperado: `AttributeError: action_edit_block_content`, asserts de arch.

- [ ] **Step 3: Implementar**

`models/relatorio_anexo.py` (garantir `from odoo.exceptions import UserError` e `_` importados):

```python
    def action_edit_block_content(self):
        """Abre o bloco de conteúdo (origem 'Bloco do relatório') no mesmo
        modal do "Editar" da lista do corpo."""
        self.ensure_one()
        if not self.block_id:
            raise UserError(_(
                "O anexo '%s' não tem bloco de conteúdo vinculado. "
                "Use 'Recarregar template' ou escolha o bloco no campo Bloco."
            ) % (self.title or self.code))
        return self.block_id.action_edit_block()
```

`views/relatorio_texto_views.xml`, dentro de `page_texto`, substituir o `<field name="block_ids" ...>...</field>` e a `<page string="Anexos" name="page_anexos">` inteira por:

```xml
                    <separator string="Corpo do relatório"/>
                    <field name="body_block_ids" nolabel="1"
                           attrs="{'readonly': [('state', '!=', 'draft')]}">
                        <tree editable="bottom">
                            <field name="relatorio_id" invisible="1"/>
                            <field name="sequence" widget="handle"/>
                            <field name="display_number" string="Nº" readonly="1"/>
                            <field name="included" widget="boolean_toggle"/>
                            <field name="show_number" widget="boolean_toggle" optional="show"/>
                            <field name="show_title" widget="boolean_toggle" optional="show"/>
                            <field name="title"/>
                            <field name="block_kind"/>
                            <field name="parent_id"
                                   domain="[('relatorio_id','=',parent.id),('id','!=',id),('is_anexo_content','=',False)]"
                                   options="{'no_create': True, 'no_create_edit': True}"
                                   optional="show"/>
                            <field name="page_break" widget="boolean_toggle"/>
                            <button name="action_edit_block" type="object"
                                    string="Editar" icon="fa-pencil" class="btn-link"/>
                        </tree>
                    </field>
                    <separator string="Anexos"/>
                    <p class="text-muted small">
                        Impressos depois do corpo, nesta ordem. A ordem define a numeração
                        usada pelo token <code>{{ anexo('code') }}</code>.
                    </p>
                    <field name="anexo_ids" nolabel="1"
                           attrs="{'readonly': [('state', '!=', 'draft')]}">
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
                                    <button name="action_edit_block_content" type="object"
                                            string="Editar conteúdo" icon="fa-pencil"
                                            class="btn-link"
                                            attrs="{'invisible': ['|', ('slot_kind', '!=', 'bloco'), ('block_id', '=', False)]}"/>
                                </group>
                            </group>
                            <separator string="Arquivos (upload ou substituição manual)"/>
                            <field name="attachment_ids" widget="many2many_binary"/>
                        </form>
                    </field>
```

(Tree e form idênticos aos da page removida, só com o botão novo.) Se o form do relatório tiver outra view herdando `page_anexos` por xpath (`grep -rn "page_anexos" views`), ajustar o xpath para o novo local.

- [ ] **Step 4: Rodar e ver passar** — `TestRelatorioApplyTemplate`, depois suíte completa (só baseline).

- [ ] **Step 5: Validação de UI (orquestrador, agent-browser)** — upgrade no dev: `docker exec odoo_engenapp-web-qualificacao-1 /entrypoint.sh odoo -d qualificacao-dev -u afr_qualificacao --stop-after-init --no-http` + `docker restart odoo_engenapp-web-qualificacao-1`; login com credencial de `~/.config/engenapp/secrets.md`; abrir um relatório final em rascunho → "Recarregar template" → aba Texto mostra "Corpo do relatório" sem separadores/protocolo/micro e "Anexos" abaixo; não existe aba Anexos; abrir anexo `protocolo` → "Editar conteúdo" abre o bloco; "Gerar minuta" e conferir no PDF que os anexos saem na ordem da tabela. Screenshot de cada passo.

- [ ] **Step 6: Commit** — `feat(relatorio): texto tab shows body then anexos; edit anexo content from the anexo` (view + model + teste). Só após OK do user na UI.
