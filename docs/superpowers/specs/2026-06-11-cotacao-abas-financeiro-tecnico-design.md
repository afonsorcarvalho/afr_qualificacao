# Abas da Cotação — Resumo Financeiro + Detalhes Técnicos Ricos

**Data:** 2026-06-11
**Módulo:** `afr_qualificacao` (Odoo 16.0)
**Status:** Design aprovado (mockup validado) — aguardando review do spec
**Depende de:** refatoração form cotação 3 abas (commits `017e8be`..`d252b19`)

## Problema / Objetivo

A refatoração em 3 abas (Comercial / Opcionais / Detalhes Técnicos) está entregue,
mas:

1. **Resumo financeiro** só aparece no painel direito e não traz o **total geral**
   (equipamentos + opcionais aceitos). O usuário quer ver, no rodapé das abas
   Comercial e Opcionais: subtotal por equipamento → soma dos equipamentos →
   opcionais aceitos → **total geral da proposta**.
2. **Aba Detalhes Técnicos** mostra só cards simples (equipamento → tipo → itens).
   O usuário quer o conteúdo técnico completo que aparece na cotação impressa:
   **Escopo**, **Tabela de Ciclos** (temperatura/tempo/carga/tempo estimado) e
   **Tempo de Execução** por equipamento.

Tudo **read-only** (edição segue no configurador). Reusa a maquinaria de dados já
existente do relatório de cotação.

## Decisões (aprovadas)

- Técnico: somente exibição (read-only), visual estilo cotação impressa.
- Financeiro: rodapé das abas Comercial **e** Opcionais (mantém também painel direito).
- Conteúdo técnico: Tabela de Ciclos + Escopo + Tempo de Execução (sem normas).

## Parte 1 — Resumo financeiro com Total Geral

### Modelo (`models/sale_order.py`)

O campo `qualif_subtotals_html` já renderiza "Subtotais por Equipamento" (+TOTAL)
e "Subtotais de Opcionais aceitos" (+TOTAL OPCIONAIS). Adicionar um bloco final
**"TOTAL GERAL DA PROPOSTA"**.

- Novo helper `_qualif_grand_total_html()` (em `sale_order.py`, junto de
  `_qualif_optionals_subtotals_html`):
  - `equip_total = sum(s["subtotal"] for s in self._qualif_equipment_summary())`
  - `opt_total = sum(self.order_line.filtered(lambda l: l.is_proposal_optional and l.optional_accepted).mapped("price_subtotal"))`
  - `grand = equip_total + opt_total`
  - Retorna banner HTML (verde, full-width) com label "TOTAL GERAL DA PROPOSTA" +
    valor formatado (`formatLang` com `currency_obj`), e linha-nota
    "(equipamentos X + opcionais aceitos Y)" quando há opcionais.
  - Valores escapados via `markupsafe` (`Markup`/`escape`) — corrige de passagem o
    padrão de interpolação crua do bloco de opcionais que este helper acompanha.
- `_compute_qualif_subtotals_html`: após `+= _qualif_optionals_subtotals_html()`,
  acrescentar `+= _qualif_grand_total_html()`.

### View (`views/sale_order_views.xml`)

Exibir `qualif_subtotals_html` (read-only, nolabel) no **rodapé** das abas:
- Page `qualif_comercial`: após o `<field name="regular_line_ids">`.
- Page `qualif_opcionais`: após o `<field name="optional_line_ids">`.
Ambos com `attrs="{'invisible': [('has_qualif_lines','=',False)]}"`. O painel
direito (`group sale_total`) permanece inalterado.

## Parte 2 — Aba Detalhes Técnicos rica

### Modelo — novo arquivo `models/sale_order_form_panels.py`

Mover o campo `qualif_tecnico_html` + seu compute de `sale_order.py` para este
arquivo novo (`class SaleOrder(models.Model): _inherit = "sale.order"`), e
enriquecer o render. Importar o arquivo em `models/__init__.py`.

`_compute_qualif_tecnico_html` (reescrito) — por equipamento de
`_qualif_equipment_summary()`, monta um card com 3 blocos, tudo via `Markup`/`escape`:

1. **Header:** `equip.display_name` + ` — S/N: ` + serial + ` · Categoria: ` + categoria (se houver).
2. **ESCOPO:** tabela: para cada `tp` em `eq["types"]`, linha-cabeçalho com
   `tp["label"]`; abaixo os `tp["items"]` agrupados por `item["part"]` ("Parte 01"/
   "Parte 02"/sem parte), cada item como `name` (× `qty` quando `qty`). Itens
   `declined` riscados com "(não solicitado)".
3. **TABELA DE CICLOS:** casar o equipamento com `_qualif_cycle_specs()` (por
   `equipment`). Se houver `rows`: tabela com colunas Ciclo · Qtd · Temperatura ·
   Tempo (`time_label`) · Carga · Tempo Estimado (`'%.1f h'`); `tfoot` com
   "Total: N ciclo(s)" e `Σ estimated_hours_total` em `'%.1f h · %.1f dias'`
   (dias = horas / 8). Se sem ciclos, omitir o bloco.
4. **TEMPO DE EXECUÇÃO (equipamento):** `_qualif_estimated_hours(equip)` /
   `_qualif_estimated_days(equip)` → "X h · Y dias úteis".

**Rodapé do campo:** banner "TEMPO TOTAL DE EXECUÇÃO DA PROPOSTA" = soma de
`_qualif_estimated_hours()` / `_qualif_estimated_days()` (sem arg = todos
equipamentos) — métodos já agregam quando `equipment=None`.

Guard: se `not has_qualif_lines` ou `summary` vazio → `False`.

`@api.depends`: manter os atuais (equipment_id, qualification_type,
is_qualificacao_managed, cycle_type_id, malha_type_id, name, product_id,
qualif_cycle_qty, product_uom_qty, display_type) + acrescentar
`order_line.temperature`, `order_line.duration`, `order_line.load_type`,
`order_line.estimated_hours` (campos exibidos na tabela de ciclos).

### View

Nenhuma mudança estrutural: o campo `qualif_tecnico_html` já está na page
`qualif_tecnico`. Só o conteúdo do compute muda.

## Organização / arquivos

- **Modify** `models/sale_order.py` — `_qualif_grand_total_html()` + chamada no
  compute; remover field/compute `qualif_tecnico_html` (movidos).
- **Create** `models/sale_order_form_panels.py` — field `qualif_tecnico_html` +
  `_compute_qualif_tecnico_html` + helpers privados de render (`_qualif_tecnico_card`,
  ou funções internas) reusando `_qualif_equipment_summary`, `_qualif_cycle_specs`,
  `_qualif_estimated_hours/days`.
- **Modify** `models/__init__.py` — importar `sale_order_form_panels`.
- **Modify** `views/sale_order_views.xml` — `qualif_subtotals_html` nos rodapés
  das abas Comercial e Opcionais.
- **Modify** `__manifest__.py` — bump `16.0.6.2.0` → `16.0.6.3.0`.
- **Modify** `tests/test_cotacao_form_refactor.py` — novos testes.

## Estilo visual (validado em mockup)

Tema Odoo: roxo `#714B67` (títulos/cabeçalhos de tabela), verde `#1f7a3d` (banner
total geral). Tabelas `border-collapse`, fonte 12px, zebra `#fafafa`. Estilos
inline (consistente com `qualif_subtotals_html`).

## Testes (`tests/test_cotacao_form_refactor.py`)

- `qualif_subtotals_html` contém "TOTAL GERAL DA PROPOSTA"; com SO de equipamentos
  sem opcionais aceitos, grand total == soma dos subtotais de equipamento.
- Com 1 opcional aceito, grand total == equip_total + opt_subtotal.
- `qualif_tecnico_html` (SO com ciclos) contém: cabeçalho "Temperatura" e "Carga"
  (tabela de ciclos), label de tipo do escopo (ex. "Qualificação de Operação"),
  "TEMPO DE EXECUÇÃO" e "TEMPO TOTAL DE EXECUÇÃO DA PROPOSTA".
- `qualif_tecnico_html` vazio (False) sem qualif_lines.
- Sem regressão: `TestCotacaoFormRefactor` existentes seguem passando.

## Fora de escopo (YAGNI)

- Edição de campos técnicos na aba (decisão: read-only).
- Tabela de Normas na aba técnica.
- Reaproveitar os templates QWeb do relatório diretamente (rendem em contexto de
  report com vars/CSS próprios; reusamos os **métodos de dados**, não o QWeb).
- Mudar o relatório impresso, configurador ou aba Proposta (Blocos).
