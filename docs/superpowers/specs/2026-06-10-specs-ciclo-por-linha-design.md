# Specs de ciclo editáveis por linha (proposta) — Design

**Data:** 2026-06-10
**Módulo:** afr_qualificacao (Odoo 16.0)
**Status:** Spec aprovado (design) — aguardando revisão do spec escrito

## Problema

As specs técnicas de um ciclo de qualificação (temperatura, tempo, tipo de
carga) hoje vivem **só** no catálogo `afr.qualificacao.cycle.type`. A tabela de
ciclos da proposta (`block_cycle_specs`, `_qualif_cycle_specs`,
`_qualif_cycle_rows_for`) lê esses valores **do tipo de ciclo**, não da linha.

Consequências:
- O comercial não consegue ajustar temperatura/tempo/carga **por proposta** sem
  alterar o catálogo (que afeta todas as propostas).
- As specs não aparecem no **template de equipamento** nem no **wizard
  configurador** — só ficam escondidas no cadastro do tipo de ciclo.

## Objetivo

Tornar temperatura / tempo / tipo de carga **overrides editáveis por linha**,
visíveis e editáveis no **template de equipamento** e no **wizard
configurador**, com a **proposta lendo da linha** (fallback no tipo de ciclo).
Modelo híbrido idêntico ao já existente para `estimated_hours`.

## Premissas

- **"Lavagem / esterilização / desinfecção" = label dinâmico do campo único
  `duration`, por categoria.** Cada `engc.equipment.category` tem exatamente um
  `process_type` (`esterilizacao` / `lavagem` / `desinfeccao` /
  `monitoramento`), que já define o rótulo da coluna de tempo via
  `_qualif_time_label()`. NÃO são três campos simultâneos. Equipamento
  multi-fase é modelado como **múltiplas linhas de ciclo**, cada uma com sua
  própria temp/tempo (ex: "Vazio 80°C" e "Vazio 92°C" da Termodesinfectora).
- **`load_type` na linha é só exibição** na coluna "Carga" da proposta. A
  separação QO (sem carga) vs QD (com carga) continua **estrutural** (abas /
  `qualification_type`), não muda com o override.
- **`cycle_type_id` não pode ser ocultado de vez** no editor: é `required` e é a
  única fonte de `product_id` / preço da linha. Fica na **largura mínima**; a
  coluna **Descrição** (que herda o nome do produto/ciclo) vira a identidade
  visível da linha.
- Specs editáveis **só** no template e no wizard. A linha SO **recebe** os
  valores no Apply e a proposta lê deles, mas a árvore de linhas do SO **não**
  expõe colunas editáveis de spec (editar = reabrir o configurador).

## Padrão de referência: `estimated_hours`

`estimated_hours` já é um override line-level do valor do `cycle.type`, presente
em **todos** os níveis a tocar. Os 3 campos novos são **espelhos linha-por-linha**
de `estimated_hours` em cada um destes pontos:

| Ponto | Arquivo | O que faz com estimated_hours (a espelhar) |
|---|---|---|
| Campo template QO/QD | `models/config_template.py` | `Float estimated_hours` na linha |
| Campo wizard QO/QD | `wizards/qualificacao_configurator.py` | `Float estimated_hours` na linha |
| Campo bulk QO/QD | `wizards/qualificacao_configurator.py` | `Float estimated_hours` na linha |
| Campo linha SO | `models/sale_order_line.py` | `Float estimated_hours` (copy=True) |
| Onchange wizard/bulk | `_onchange_cycle_type_defaults` | semeia do cycle_type se vazio |
| Template→wizard | `_onchange_config_template` | copia `line.estimated_hours or cycle_type.estimated_hours` |
| Apply → linha SO | `action_apply` | grava `hours` na linha SO |
| Reabrir (relê SO) | `_load_from_existing_lines` | lê `line.estimated_hours` de volta |
| Duplicar / bulk apply | `action_duplicate`, bulk `action_apply` | copia entre linhas |

## Campos novos

Tipos idênticos ao `afr.qualificacao.cycle.type`:

```python
temperature = fields.Char(string="Temperatura")          # ex: "134°C"
duration    = fields.Char(string="Tempo")                # label genérico no editor
load_type   = fields.Selection(                          # só exibição na proposta
    selection=[("vazio", "Câmara Vazia"),
               ("sem_carga", "Sem Carga"),
               ("com_carga", "Com Carga")],
    string="Tipo de Carga")
```

Adicionar em:
- `afr.qualificacao.config.template.qo` e `.qd` (template)
- `afr.qualificacao.configurator.qo.line` e `.qd.line` (wizard)
- `afr.qualificacao.configurator.bulk.qo` e `.bulk.qd` (bulk)
- `sale.order.line` (com `copy=True`, igual `estimated_hours`)

**Não** adicionar nas linhas/malhas de calibração (malha não tem
temperatura/tempo/carga).

## Propagação (detalhe)

1. **`_onchange_cycle_type_defaults`** (wizard qo/qd + bulk qo/qd): após o bloco
   de `estimated_hours`, semear `temperature`/`duration`/`load_type` do
   `cycle_type_id` quando vazios (mesmo idioma `if not line.<campo>`).
2. **Novo onchange nas linhas do template** (`config.template.qo` e `.qd`):
   `@api.onchange("cycle_type_id")` semeando temp/duration/load_type (+
   description/estimated_hours se ainda não houver) — hoje o template **não tem**
   onchange; sem ele as specs ficam em branco ao escolher o ciclo.
3. **`_onchange_config_template`**: ao montar `qo_line_ids`/`qd_line_ids` a partir
   do template, incluir
   `temperature: line.temperature or line.cycle_type_id.temperature`
   (idem duration; load_type análogo).
4. **`action_apply`**: nos dicts `qo_vals`/`qd_vals`, gravar
   `temperature`/`duration`/`load_type` (line-wins, fallback cycle_type) na
   linha SO.
5. **`_load_from_existing_lines`**: nos buckets `qo_cycles` e `qd`, ler
   `line.temperature` / `line.duration` / `line.load_type` de volta para a linha
   do wizard (crítico — sem isso, reabrir o configurador apaga as edições).
6. **`action_duplicate`** e **bulk `action_apply`**: incluir os 3 campos nas
   cópias `(0, 0, {...})` das linhas qo/qd.

## Proposta — linha vence, cycle_type fallback

Em `models/sale_order.py`, nos 3 read-sites (≈424–425, ≈830–831, ≈867–869):

```python
"temperature": line.temperature or line.cycle_type_id.temperature or "",
"duration":    line.duration    or line.cycle_type_id.duration    or "",
# load_type: usa o label da seleção
"load_type":   load_labels.get(line.load_type or line.cycle_type_id.load_type, ""),
```

Mantém orçamentos antigos e linhas criadas fora do onchange funcionando (fallback
no catálogo), e honra a edição do comercial quando presente.

## Views

- **`views/config_template_views.xml`** (form do template, abas Ciclos QO / QD):
  adicionar colunas editáveis **Temperatura / Tempo / Carga**; `cycle_type_id`
  na largura mínima (`width`/`optional` conforme aplicável; permanece visível e
  editável porque é required).
- **`wizards/qualificacao_configurator_views.xml`** (step Escopo, árvores qo/qd):
  mesmas colunas editáveis; `cycle_type_id` estreito.
- Header do editor: **"Tempo"** genérico (árvore Odoo não muda cabeçalho por
  linha). O PDF da proposta mantém o label dinâmico por categoria
  (`_qualif_time_label`).
- **Sem** coluna "Processo".
- Árvore de linhas do SO: **não** adicionar colunas de spec.

## Testes

Estender suites existentes:
- **`tests/test_proposal_report.py`** (ou `test_qo_cycles.py`): criar linha SO
  com `temperature`/`duration`/`load_type` próprios diferentes do cycle_type;
  assertar que `_qualif_cycle_specs()` / `_qualif_cycle_rows_for()` retornam o
  valor **da linha** (não do cycle_type). Caso fallback: linha sem override →
  retorna o do cycle_type.
- **Round-trip reabrir**: aplicar configurador com specs editadas, recarregar via
  `_load_from_existing_lines`, assertar specs preservadas nas linhas do wizard.

## Fora de escopo

- Edição inline de spec na árvore de linhas do SO.
- Reclassificação QO/QD via load_type.
- Múltiplos campos de tempo por fase (lavagem + desinfecção simultâneos).
- Specs em linhas de calibração.
