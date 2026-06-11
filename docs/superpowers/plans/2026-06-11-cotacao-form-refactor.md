# Refatoração Form Cotação (3 abas) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dividir o tree largo do `order_line` no form da cotação em 3 abas focadas (Comercial / Opcionais / Detalhes Técnicos), reduzindo poluição visual.

**Architecture:** Dois novos one2many filtrados por domain (`regular_line_ids`, `optional_line_ids`) sobre o mesmo inverse `order_id` (mesma tabela, registros disjuntos) alimentam as abas Comercial e Opcionais editáveis; um campo Html computado (`qualif_tecnico_html`) reusa `_qualif_equipment_summary()` para cards read-only por equipamento. A página padrão "Order Lines" é escondida; o campo `order_line` permanece carregado (invisível) garantindo totais e onchanges padrão do `sale`.

**Tech Stack:** Odoo 16.0, Python (TransactionCase), XML views. Testes via docker (entrypoint custom, porta 8083 — NÃO usar `odoo-bin` direto).

---

## File Structure

- **Modify** `models/sale_order.py` — adiciona `regular_line_ids`, `optional_line_ids`, `qualif_tecnico_html` + compute `_compute_qualif_tecnico_html`.
- **Modify** `views/sale_order_views.xml` — remove colunas injetadas no tree padrão; esconde page `order_lines`; adiciona 3 pages.
- **Create** `tests/test_cotacao_form_refactor.py` — cobre filtros dos one2many, default do flag, totais, html técnico.
- **Modify** `__manifest__.py` — bump versão `16.0.6.1.0` → `16.0.6.2.0`.

---

## Task 1: Campos one2many filtrados (`regular_line_ids`, `optional_line_ids`)

**Files:**
- Modify: `models/sale_order.py` (adicionar fields após o bloco `qualif_subtotals_html`)
- Test: `tests/test_cotacao_form_refactor.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_cotacao_form_refactor.py`:

```python
# -*- coding: utf-8 -*-
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestCotacaoFormRefactor(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _svc(self, price=100.0):
        return self.env["product.product"].create({
            "name": "Svc", "type": "service", "sale_ok": True,
            "list_price": price,
        })

    def _line(self, so, optional=False, price=100.0, qty=1.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self._svc(price).id,
            "name": "L",
            "is_proposal_optional": optional,
            "optional_qty": qty if optional else 0.0,
            "product_uom_qty": qty,
            "price_unit": price,
        })

    def test_regular_line_ids_excludes_optional(self):
        so = self._so()
        reg = self._line(so, optional=False)
        opt = self._line(so, optional=True)
        self.assertIn(reg, so.regular_line_ids)
        self.assertNotIn(opt, so.regular_line_ids)

    def test_optional_line_ids_only_optional(self):
        so = self._so()
        reg = self._line(so, optional=False)
        opt = self._line(so, optional=True)
        self.assertIn(opt, so.optional_line_ids)
        self.assertNotIn(reg, so.optional_line_ids)
```

- [ ] **Step 2: Rodar e verificar que falha**

Delegar ao agente `test-runner` (model sonnet):
> Rodar test-tags `afr_qualificacao` classe `TestCotacaoFormRefactor` métodos `test_regular_line_ids_excludes_optional` e `test_optional_line_ids_only_optional`.

Esperado: FAIL — `AttributeError: 'sale.order' object has no attribute 'regular_line_ids'`.

- [ ] **Step 3: Implementar os campos**

Em `models/sale_order.py`, logo após o field `qualif_subtotals_html` (antes do próximo bloco), adicionar:

```python
    regular_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        domain=[("is_proposal_optional", "=", False)],
        string="Linhas",
        help=(
            "Linhas NÃO-opcionais (comercial + seções/notas). Mesmo conjunto "
            "de registros de order_line filtrado por domain — usado na aba "
            "Comercial do form."
        ),
    )
    optional_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        domain=[("is_proposal_optional", "=", True)],
        string="Opcionais",
        help=(
            "Linhas opcionais (is_proposal_optional=True). Usado na aba "
            "Opcionais. Novas linhas recebem o flag via context default da view."
        ),
    )
```

- [ ] **Step 4: Rodar e verificar que passa**

Delegar ao `test-runner`: mesmas 2 tags do Step 2.
Esperado: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add models/sale_order.py tests/test_cotacao_form_refactor.py
git commit -m "feat: one2many regular_line_ids/optional_line_ids filtrados por domain"
```

---

## Task 2: Default do flag opcional + integridade dos totais

**Files:**
- Test: `tests/test_cotacao_form_refactor.py` (adicionar métodos)

Nota: o default do `is_proposal_optional` em novas linhas opcionais vem do
`context` da view (Task 4). Aqui validamos o mecanismo de context-default a nível
ORM e que os totais somam corretamente com linhas distribuídas.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar à classe `TestCotacaoFormRefactor`:

```python
    def test_optional_context_default_flag(self):
        # Simula o default_get usado pela aba Opcionais (context na view).
        Line = self.env["sale.order.line"].with_context(
            default_is_proposal_optional=True)
        vals = Line.default_get(["is_proposal_optional"])
        self.assertTrue(vals.get("is_proposal_optional"))

    def test_amount_total_with_split_lines(self):
        so = self._so()
        self._line(so, optional=False, price=100.0, qty=2.0)   # 200
        self._line(so, optional=True, price=50.0, qty=1.0)     # opcional
        # order_line (padrão) enxerga ambos os registros.
        self.assertEqual(len(so.order_line), 2)
        self.assertEqual(
            len(so.regular_line_ids) + len(so.optional_line_ids),
            len(so.order_line),
        )
```

- [ ] **Step 2: Rodar e verificar resultado**

Delegar ao `test-runner`: classe `TestCotacaoFormRefactor` métodos
`test_optional_context_default_flag` e `test_amount_total_with_split_lines`.
Esperado: ambos PASS (o mecanismo de context-default e os one2many já existem da Task 1).
Se `test_amount_total_with_split_lines` falhar na contagem, investigar se algum
onchange/compute filtra `order_line` — não deveria.

- [ ] **Step 3: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add tests/test_cotacao_form_refactor.py
git commit -m "test: default context opcional + integridade totais com linhas split"
```

---

## Task 3: Campo `qualif_tecnico_html` (cards por equipamento)

**Files:**
- Modify: `models/sale_order.py`
- Test: `tests/test_cotacao_form_refactor.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar à classe `TestCotacaoFormRefactor`:

```python
    def test_qualif_tecnico_html_empty_without_qualif(self):
        so = self._so()
        self._line(so, optional=False)  # linha comum, sem equipment
        self.assertFalse(so.qualif_tecnico_html)

    def test_qualif_tecnico_html_has_cards_with_qualif(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo CMax",
            "is_qualificacao_managed": True,
            "qualification_type": "performance",
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 1,
            "price_unit": 700.0,
        })
        html = so.qualif_tecnico_html
        self.assertTrue(html)
        self.assertIn(self.equip1.display_name, html)
```

- [ ] **Step 2: Rodar e verificar que falha**

Delegar ao `test-runner`: métodos `test_qualif_tecnico_html_empty_without_qualif`
e `test_qualif_tecnico_html_has_cards_with_qualif`.
Esperado: FAIL — `AttributeError: ... 'qualif_tecnico_html'`.

- [ ] **Step 3: Implementar o campo + compute**

Em `models/sale_order.py`, adicionar o field após `optional_line_ids` (Task 1):

```python
    qualif_tecnico_html = fields.Html(
        compute="_compute_qualif_tecnico_html",
        string="Detalhes Técnicos",
        sanitize=False,
        help=(
            "Cards read-only por equipamento (equipamento → tipo qualif → "
            "itens), gerados do agregado das linhas managed. Aba de conferência."
        ),
    )
```

Adicionar o compute (colocar logo após `_compute_qualif_subtotals_html` para
manter os computes de HTML juntos):

```python
    @api.depends(
        "order_line.equipment_id",
        "order_line.qualification_type",
        "order_line.is_qualificacao_managed",
        "order_line.cycle_type_id",
        "order_line.malha_type_id",
    )
    def _compute_qualif_tecnico_html(self):
        for order in self:
            if not order.has_qualif_lines:
                order.qualif_tecnico_html = False
                continue
            summary = order._qualif_equipment_summary()
            if not summary:
                order.qualif_tecnico_html = False
                continue
            cards = []
            for s in summary:
                equip = s["equipment"]
                equip_label = equip.display_name or _("Equipamento")
                if equip.serial_number:
                    equip_label += " — S/N: %s" % equip.serial_number
                type_blocks = []
                for t in s["types"]:
                    items = "".join(
                        '<li style="margin:1px 0;">%s%s</li>' % (
                            it["name"],
                            (" &times; %s" % int(it["qty"]))
                            if it.get("qty") else "",
                        )
                        for it in t["items"]
                    )
                    type_blocks.append(
                        '<div style="margin:4px 0 4px 8px;">'
                        '<div style="font-weight:bold;color:#555;">%s</div>'
                        '<ul style="margin:2px 0 2px 16px;padding:0;'
                        'font-size:12px;">%s</ul>'
                        '</div>' % (t["label"], items)
                    )
                cards.append(
                    '<div style="border:1px solid #ddd;border-radius:6px;'
                    'margin:8px 0;padding:8px 12px;background:#fafafa;">'
                    '<div style="font-weight:bold;font-size:13px;color:#222;'
                    'border-bottom:1px solid #eee;padding-bottom:4px;'
                    'margin-bottom:4px;">%s</div>%s</div>'
                    % (equip_label, "".join(type_blocks))
                )
            order.qualif_tecnico_html = (
                '<div style="width:100%%;">%s</div>' % "".join(cards)
            )
```

Verificar que `_` e `api` já estão importados no topo de `sale_order.py`
(estão — usados por `_compute_qualif_subtotals_html`).

- [ ] **Step 4: Rodar e verificar que passa**

Delegar ao `test-runner`: os 2 métodos do Step 2.
Esperado: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add models/sale_order.py tests/test_cotacao_form_refactor.py
git commit -m "feat: qualif_tecnico_html cards read-only por equipamento"
```

---

## Task 4: Refatorar a view (esconder tree padrão, 3 abas novas)

**Files:**
- Modify: `views/sale_order_views.xml`

- [ ] **Step 1: Remover as colunas injetadas no tree padrão**

Em `views/sale_order_views.xml`, **deletar** o bloco xpath que injeta as 8 colunas
(atualmente linhas 42–55):

```xml
            <xpath expr="//field[@name='order_line']/tree/field[@name='product_id']" position="after">
                <field name="is_qualificacao_managed" optional="hide"/>
                ... (todo o bloco até) ...
                <field name="optional_accepted" string="Aceito"
                       attrs="{'invisible': [('is_proposal_optional', '=', False)]}"
                       widget="boolean_toggle" optional="show"/>
            </xpath>
```

- [ ] **Step 2: Esconder a página padrão "Order Lines"**

Adicionar, dentro do `<field name="arch" type="xml">` do record
`view_sale_order_form_inherit_qualificacao`, um xpath que esconde a page padrão:

```xml
            <xpath expr="//page[@name='order_lines']" position="attributes">
                <attribute name="invisible">1</attribute>
            </xpath>
```

- [ ] **Step 3: Adicionar as 3 novas páginas**

Substituir o xpath existente `<xpath expr="//notebook" position="inside">` (que hoje
só tem a page "Proposta (Blocos)") para que ele inclua, ANTES da page de blocos, as
3 novas páginas. O bloco final do xpath `//notebook position="inside"` fica:

```xml
            <xpath expr="//notebook" position="inside">
                <page string="Linhas (Comercial)" name="qualif_comercial">
                    <field name="regular_line_ids">
                        <tree editable="bottom">
                            <control>
                                <create name="add_product" string="Adicionar produto"/>
                                <create name="add_section" string="Adicionar seção"
                                        context="{'default_display_type': 'line_section'}"/>
                                <create name="add_note" string="Adicionar nota"
                                        context="{'default_display_type': 'line_note'}"/>
                            </control>
                            <field name="sequence" widget="handle"/>
                            <field name="display_type" invisible="1"/>
                            <field name="product_id"
                                   attrs="{'required': [('display_type','=',False)]}"/>
                            <field name="name" widget="section_and_note_text"/>
                            <field name="product_uom_qty"
                                   attrs="{'column_invisible': [('parent.state','=','sale')]}"
                                   optional="show"/>
                            <field name="product_uom"
                                   groups="uom.group_uom"
                                   optional="hide"/>
                            <field name="price_unit"/>
                            <field name="discount" string="Desc.%" optional="hide"/>
                            <field name="tax_id" widget="many2many_tags"
                                   optional="hide"/>
                            <field name="price_subtotal"/>
                        </tree>
                    </field>
                </page>

                <page string="Opcionais" name="qualif_opcionais">
                    <field name="optional_line_ids"
                           context="{'default_is_proposal_optional': 1}">
                        <tree editable="bottom">
                            <field name="is_proposal_optional" invisible="1"/>
                            <field name="sequence" widget="handle"/>
                            <field name="product_id"/>
                            <field name="name"/>
                            <field name="optional_qty" string="Qtd Opc."/>
                            <field name="price_unit"/>
                            <field name="optional_accepted" string="Aceito"
                                   widget="boolean_toggle"/>
                            <field name="price_subtotal"/>
                        </tree>
                    </field>
                </page>

                <page string="Detalhes Técnicos" name="qualif_tecnico"
                      attrs="{'invisible': [('has_qualif_lines','=',False)]}">
                    <field name="qualif_tecnico_html" nolabel="1" readonly="1"/>
                </page>

                <page string="Proposta (Blocos)" name="proposal_blocks">
                    <!-- conteúdo existente da page de blocos, INALTERADO -->
                </page>
            </xpath>
```

IMPORTANTE: preservar o conteúdo interno EXISTENTE da page "Proposta (Blocos)"
(o `<group>`, o botão `action_reload_proposal_blocks`, e o
`<field name="proposal_block_ids">` com seu tree/form). Apenas mover as 3 novas
pages para antes dela, dentro do mesmo xpath `//notebook position="inside"`.

- [ ] **Step 4: Restart container + upgrade do módulo**

```bash
docker exec -u root odoo-labquali /entrypoint.sh -u afr_qualificacao -d labquali --stop-after-init 2>&1 | tail -20
docker restart odoo-labquali
```

Esperado: upgrade sem ParseError; container sobe.

- [ ] **Step 5: Validar via odoo-mcp (browser bloqueado WSL)**

Usar odoo-mcp para confirmar que o form carrega e os campos existem:
- `odoo_fields_get` em `sale.order` inclui `regular_line_ids`, `optional_line_ids`, `qualif_tecnico_html`.
- `odoo_view_get` do form `view_sale_order_form_inherit_qualificacao` renderiza sem erro e contém as pages `qualif_comercial`, `qualif_opcionais`, `qualif_tecnico`.

Esperado: campos presentes; arch resolvido sem exceção.

- [ ] **Step 6: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add views/sale_order_views.xml
git commit -m "feat: form cotação em 3 abas (comercial/opcionais/técnico)"
```

---

## Task 5: Bump de versão + suíte completa

**Files:**
- Modify: `__manifest__.py`

- [ ] **Step 1: Bump da versão**

Em `__manifest__.py`, alterar:

```python
    "version": "16.0.6.1.0",
```
para:
```python
    "version": "16.0.6.2.0",
```

- [ ] **Step 2: Rodar a suíte completa do módulo**

Delegar ao `test-runner`: suíte completa de `afr_qualificacao`.
Esperado: todos os testes pré-existentes + os 6 novos PASS. Separar qualquer
falha nova de falhas pré-existentes/ambientais.

- [ ] **Step 3: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add __manifest__.py
git commit -m "chore: bump afr_qualificacao 16.0.6.2.0 (form cotação 3 abas)"
```

---

## Validação final (manual, pelo usuário)

Browser bloqueado em WSL para OWL — validação de clique fica com o usuário após
o deploy. Checklist:
1. Abrir uma cotação com linhas geradas pelo configurador.
2. Aba "Linhas (Comercial)": só colunas comerciais, sem campos técnicos.
3. Aba "Opcionais": só linhas opcionais; criar uma nova já nasce marcada opcional.
4. Aba "Detalhes Técnicos": cards por equipamento, read-only.
5. Painel financeiro à direita (subtotais + impostos) visível em qualquer aba.
6. Totais da cotação corretos.

## Notas de risco (revalidar durante execução)

- **Múltiplos one2many no mesmo inverse:** se salvar pela aba Comercial não
  disparar onchange de preço/imposto padrão, considerar manter a edição via
  `order_line` padrão visível e usar `regular_line_ids` só leitura. Validar no
  Step 5 da Task 4 e no teste de totais (Task 2).
- **Seções/notas:** o `<control>` na aba Comercial cria seções com
  `is_proposal_optional=False` (default), caindo na aba certa.
