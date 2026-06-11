# Refatoração do Formulário de Cotação (sale.order) — afr_qualificacao

**Data:** 2026-06-11
**Módulo:** `afr_qualificacao` (Odoo 16.0)
**Status:** Design aprovado (Abordagem A) — aguardando review do usuário

## Problema

O form da cotação (`sale.order`, herdado em `views/sale_order_views.xml`) injeta
**8 colunas customizadas** no tree do `order_line`, somadas a ~10 colunas padrão
do `sale`. O tree fica largo demais, misturando três naturezas de dado num só
lugar e confundindo o usuário:

- **Técnico:** `equipment_id`, `qualification_type`, `cycle_type_id`, `malha_type_id`
- **Comercial:** `product_id`, qtd, preço unit., desconto, impostos, subtotal
- **Opcional:** `is_proposal_optional`, `optional_qty`, `optional_accepted`

## Objetivo

Separar as três naturezas em páginas distintas do notebook, cada tela com
4–6 colunas focadas. Os campos técnicos são **somente referência** (preenchidos
pelo wizard configurador) — não precisam de edição inline na linha. Opcionais
geridos exclusivamente em aba própria.

## Abordagem (A) — 3 abas funcionais

Estrutura do notebook após refatoração:

```
┌─ Linhas (Comercial) ─┬─ Opcionais ─┬─ Detalhes Técnicos ─┬─ Proposta (Blocos) ─┐
```

### Aba "Linhas (Comercial)" — editável
- Backing field: **`regular_line_ids`** (novo, ver abaixo).
- Colunas: `sequence` (handle) · `product_id` · `name` · `product_uom_qty` ·
  `product_uom` · `price_unit` · `discount` (optional) · `tax_id` (optional=hide) ·
  `price_subtotal`.
- Esconde ruído de draft: `qty_delivered`, `qty_invoiced`.
- Mantém `<control>` padrão de "Adicionar produto / seção / nota".

### Aba "Opcionais" — editável
- Backing field: **`optional_line_ids`** (novo).
- Colunas: `product_id` · `name` · `optional_qty` · `price_unit` ·
  `optional_accepted` (boolean_toggle) · `price_subtotal`.
- Linhas novas herdam `is_proposal_optional=True` automaticamente (via domain).

### Aba "Detalhes Técnicos" — read-only (cards por equipamento)
- Backing field: **`qualif_tecnico_html`** (novo, computed Html).
- Reusa o helper existente `_qualif_equipment_summary()` (já agrega
  equipamento → tipo qualif → itens). Renderiza um bloco/card por equipamento
  com suas qualificações e ciclos/malhas. Estilo análogo ao
  `qualif_subtotals_html` já existente.

### Aba "Proposta (Blocos)"
- Inalterada.

## Mudanças no modelo (`models/sale_order.py`)

```python
regular_line_ids = fields.One2many(
    "sale.order.line", "order_id",
    domain=[("is_proposal_optional", "=", False)],
    string="Linhas",
)
optional_line_ids = fields.One2many(
    "sale.order.line", "order_id",
    domain=[("is_proposal_optional", "=", True)],
    string="Opcionais",
)
qualif_tecnico_html = fields.Html(
    compute="_compute_qualif_tecnico_html", sanitize=False,
)
```

- Os três one2many (`order_line` padrão + os dois novos) compartilham o mesmo
  inverse `order_id` e a mesma tabela. São **disjuntos por domain**, então edições
  numa aba não colidem com a outra. O `order_line` padrão continua enxergando
  todos os registros — os totais (`amount_total`, `tax_totals`) seguem corretos.
- O domain `[('is_proposal_optional','=',True)]` propaga o default para registros
  novos criados na aba Opcionais (comportamento padrão Odoo de domain-as-default
  em x2many).
- `_compute_qualif_tecnico_html`: itera `_qualif_equipment_summary()` e monta os
  cards. Vazio quando `has_qualif_lines` é False.

## Mudanças na view (`views/sale_order_views.xml`)

1. **Remover** o bloco xpath que injeta as 8 colunas customizadas no tree padrão
   do `order_line` (linhas 42–55 do arquivo atual).
2. **Esconder** a página padrão "Order Lines" (`position="attributes"` →
   `invisible=1`), como já é feito com `optional_products`. O campo `order_line`
   permanece carregado (invisível) garantindo totais e onchanges padrão.
3. **Adicionar** 3 novas páginas no notebook: "Linhas (Comercial)" (`regular_line_ids`),
   "Opcionais" (`optional_line_ids`), "Detalhes Técnicos" (`qualif_tecnico_html`).
4. Painel financeiro (`qualif_subtotals_html` + `tax_totals`) permanece no group
   `sale_total` à direita, **fora** do notebook — visível em qualquer aba.
5. O `<field name="has_qualif_lines" invisible="1"/>` permanece.

## Riscos a validar na implementação

- **Múltiplos one2many no mesmo inverse:** confirmar que salvar via
  `regular_line_ids`/`optional_line_ids` dispara os onchanges padrão do `sale`
  (preço, impostos) e não gera comandos conflitantes. Validar via odoo-shell/MCP
  (browser bloqueado em WSL).
- **Controls de seção/nota:** garantir que "Adicionar seção/nota" funciona na aba
  Comercial usando `regular_line_ids` (sections têm `is_proposal_optional=False`,
  caem na aba certa).
- **Reclassificação:** não há toggle "Opcional" na aba Comercial (decisão de
  escopo). Opcionais só nascem na aba Opcionais ou no configurador. Dados
  existentes já flagueados aparecem na aba correta automaticamente.

## Fora de escopo (YAGNI)

- Botão "mover para opcional" / toggle inline de reclassificação.
- Mudanças no wizard configurador, no PDF da proposta, ou na aba Proposta (Blocos).
- Alterar a lógica de subtotais financeiros.

## Testes

- Linha não-opcional aparece em `regular_line_ids`, não em `optional_line_ids`.
- Linha criada via `optional_line_ids` nasce com `is_proposal_optional=True`.
- `amount_total` permanece correto com linhas distribuídas nas duas abas.
- `qualif_tecnico_html` vazio sem qualif_lines; com cards quando há.
- Regressão: configurador continua criando linhas que caem nas abas corretas.
