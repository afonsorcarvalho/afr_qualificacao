# Escopo por equipamento como tabela única (ciclos, dias e valores embutidos)

Data: 2026-08-20
Módulo: `afr_qualificacao`
Versão alvo: `16.0.7.0.0` (feature com quebra de layout da proposta)

## Problema

O escopo da proposta hoje lista, por equipamento, uma tabela hierárquica
(Tipo → Parte → itens em bullets). Os ciclos aparecem como bullets com
temperatura e tempo concatenados no texto (F8.16), as previsões de dias
vivem só no bloco Cronograma, e os valores por equipamento foram removidos
do escopo (F8.10) para o bloco Resumo Financeiro.

O cliente pediu o formato da proposta antiga: **uma tabela por equipamento
que contém tudo** — as etapas de qualificação, as tabelas de ciclos, a
previsão de dias e o subtotal de cada etapa, fechando com a previsão total
de dias e o valor unitário do equipamento.

Consequências pedidas junto:

- O bloco "Tabela Resumo de Ciclos" deixa de ser usado (já está fora do
  template default desde F8.8).
- O bloco "Resumo Financeiro" deixa de existir na proposta; o total geral
  passa a ser impresso ao fim do escopo.
- "Serviços opcionais" deixam de ser apresentados como cardápio no PDF;
  os aceitos viram **adicionais** listados na decomposição do total geral.

## Formato alvo

```
a. Autoclave a Vapor — GETINGE, SOLSUS 66 · S/N: 8AA200568

┌───────────────────────────────┬────────────────────────────────────────┐
│ Qualificação da Instalação —  │ Conforme item 5.1 — Qualificação de    │
│ QI (primeira parte)           │ Instalação (QI)                        │
├───────────────────────────────┼────────────────────────────────────────┤
│ Previsão de 0,5 dia de serviço│ Subtotal QI: R$ 1.500,00               │
├───────────────────────────────┼────────────────────────────────────────┤
│ Qualificação de Operação —    │ Conforme item 5.2 — Qualificação de    │
│ QO (primeira parte)           │ Operação (QO)                          │
├───────────────────────────────┼────────────────────────────────────────┤
│ Previsão de 0,5 dia de serviço│ Subtotal QO: R$ 1.700,00               │
├───────────────────────────────┼────────────────────────────────────────┤
│ Qualificação da Instalação —  │ Calibração dos equipamentos de         │
│ QI (segunda parte)            │ controle:                              │
│                               │  • Malha de Temperatura                │
│                               │  • Malha de Pressão                    │
│                               │  • Temporizador                        │
├───────────────────────────────┼────────────────────────────────────────┤
│ Qualificação de Operação —    │ Execução dos ciclos sem carga          │
│ QO (segunda parte)            │ ┌────────┬──────────┬──────┬─────────┐ │
│                               │ │Quantid.│Ciclo     │Temp. │Tempo    │ │
│                               │ │   03   │Bowie Dick│134°C │3,5 min  │ │
│                               │ └────────┴──────────┴──────┴─────────┘ │
├───────────────────────────────┼────────────────────────────────────────┤
│ Qualificação de Desempenho —  │ Execução dos ciclos com carga          │
│ QD                            │ ┌────────┬──────────┬──────┬─────────┐ │
│                               │ │   03   │Carga Mista│134°C│7 min    │ │
│                               │ └────────┴──────────┴──────┴─────────┘ │
├───────────────────────────────┼────────────────────────────────────────┤
│ Previsão de 1,0 dia de serviço│ Subtotal QD: R$ 1.848,00               │
├───────────────────────────────┴────────────────────────────────────────┤
│ Previsão de 2,0 dia(s) de serviço  │  Valor Unitário: R$ 5.048,00      │
└────────────────────────────────────┴───────────────────────────────────┘
```

Depois da última tabela de equipamento:

```
Total dos Serviços de Qualificação            R$ 4.800,00
Despesas de viagem, hospedagem e alimentação  R$ 1.000,00
Pasta impressa e envio correio                R$   400,00
──────────────────────────────────────────────────────────
TOTAL GERAL DA PROPOSTA                       R$ 6.200,00
```

Sem nenhum adicional, imprime só a linha `TOTAL GERAL DA PROPOSTA`.

## Decisões

| # | Questão | Decisão |
|---|---|---|
| D1 | Agrupamento das linhas "Previsão / Subtotal" | Fiel à proposta antiga: `{QI parte 01}`, `{QO parte 01}`, `{QI parte 02 + QO parte 02 + QD}` |
| D2 | Rótulo do subtotal do 3º grupo | `Subtotal QD` |
| D3 | Previsão de dias no rodapé | Soma dos dias **já arredondados** dos grupos |
| D4 | Valor Unitário | `equipment_target_price` quando `equipment_target_state == 'ok'`; senão `equipment_subtotal` |
| D5 | Conjunto de linhas do escopo | Idêntico a `_rateio_base_lines()` — managed, sem `display_type`, não opcional, não declinada, `qty > 0` |
| D6 | QI-1 / QO-1 | Remissiva ao tópico, não lista de itens |
| D7 | Numeração da remissiva | Automática, via `_proposal_block_numbering()`; degrada pro nome do tópico |
| D8 | Numeração do equipamento | Mantém letras (`a.`, `b.`, …) |
| D9 | Colunas da tabela de ciclos | `Quantidade / Ciclo / Temperatura / Tempo` — carga vira título do grupo |
| D10 | Renders | Os três: PDF, portal e snapshot HTML (DOCX / bloco editável) |
| D11 | Bloco `financial` | Sai do template default; tipo continua existindo |
| D12 | Bloco `cycle_specs` | Nada muda — segue disponível, fora do default |
| D13 | Bloco `optionals` | Sai do template default; aceite continua no portal |
| D14 | Adicionais | Toda linha fora do rateio de qualquer equipamento, com subtotal ≠ 0 |
| D15 | Total geral | `amount_untaxed`, com linha residual "Outros" se a enumeração não fechar |

## Arquitetura

### `_qualif_scope_table(equipment)` — fonte única

Novo helper em `sale.order`. Os três renders consomem esta estrutura;
nenhum deles refaz agregação ou aritmética.

```python
{
    "equipment": <engc.equipment>,
    "groups": [
        {
            "key": "qi1",
            "label": "Qualificação da Instalação — QI (primeira parte)",
            "rows": [{"kind": "ref", "ref": "5.1 — Qualificação de Instalação (QI)"}],
            "days": 0.5,
            "subtotal": 1500.0,
            "subtotal_label": "Subtotal QI",
        },
        {
            "key": "qo1", ...  # idem, "Subtotal QO"
        },
        {
            "key": "parte2",
            "rows": [
                {"kind": "list", "label": "Qualificação da Instalação — QI (segunda parte)",
                 "title": "Calibração dos equipamentos de controle:",
                 "items": ["Malha de Temperatura", "Malha de Pressão", "Temporizador"]},
                {"kind": "cycles", "label": "Qualificação de Operação — QO (segunda parte)",
                 "title": "Execução dos ciclos sem carga",
                 "time_label": "Tempo de Esterilização",
                 "cycles": [{"qty": 3, "name": "Bowie Dick",
                             "temperature": "134°C", "duration": "3,5 minutos"}]},
                {"kind": "cycles", "label": "Qualificação de Desempenho — QD",
                 "title": "Execução dos ciclos com carga", ...},
            ],
            "days": 1.0,
            "subtotal": 1848.0,
            "subtotal_label": "Subtotal QD",
        },
    ],
    "footer": {"days": 2.0, "unit_price": 5048.00},
}
```

**Mapeamento grupo → linhas** (D1):

| Grupo | `qualification_type` | `part` |
|---|---|---|
| `qi1` | `installation` | `01` |
| `qo1` | `operational` | `01` |
| `parte2` | `installation` + `calibration` | `02` |
| `parte2` | `operational` | `02` |
| `parte2` | `performance` | qualquer |

Tipo/parte fora dessa matriz (ex.: `software`, item sem `part`) vira grupo
próprio ao fim, `kind: "list"`, com previsão e subtotal próprios rotulados
pelo label do tipo. Nada some silenciosamente.

**Título do sub-bloco de ciclos** deriva de `qualification_type`:
`operational` → "Execução dos ciclos sem carga", `performance` → "Execução
dos ciclos com carga". Não usa `load_type` (D9).

**Cabeçalho da coluna de tempo** continua vindo de
`equipment.category_id._qualif_time_label()` (esterilização / lavagem /
desinfecção), como no `cycle_specs` atual.

### Conjunto de linhas e reconciliação (D5, D15)

`_qualif_scope_table` filtra exatamente como `_rateio_base_lines()`:

```python
l.equipment_id == equipment
and l.is_qualificacao_managed
and not l.display_type
and not l.is_proposal_optional
and not l.part01_declined
and l.product_uom_qty > 0
```

Isso garante `Σ subtotais dos grupos == equipment_subtotal` por construção
— hoje `_qualif_equipment_summary()` não filtra opcionais e inclui
declinadas com `price_subtotal = 0`, o que faria dias e dinheiro serem
calculados sobre conjuntos diferentes em células vizinhas.

`_qualif_equipment_summary()` **não muda** — segue servindo o box de itens
declinados e o painel do form. O escopo passa a usar o helper novo.

### Adicionais e total geral (D14, D15)

`_qualif_proposal_totals()` é reescrito para enumerar em vez de só computar
resto:

```python
{
    "equip_total": <Σ footer.unit_price de cada equipamento>,
    "adicionais": [{"name": "Despesas de viagem…", "amount": 1000.0}, ...],
    "residual": 0.0,          # guard: nunca perde dinheiro
    "grand_total": self.amount_untaxed,
}
```

- **Adicional** = `order_line` com `not display_type`, subtotal ≠ 0, que
  não pertence ao `_rateio_base_lines()` de nenhum equipamento. Opcional
  recusado tem `product_uom_qty = 0` → subtotal 0 → fora, sem regra
  especial. Descrição = `line.name`, valor = `price_subtotal`.
- **`residual`** = `grand_total − equip_total − Σ adicionais`. Deve ser
  zero. Se não for (equipamento com alvo desviado, arredondamento), imprime
  uma linha `Outros` com o residual — o bug C26-06-0005 (dinheiro invisível
  no total) não pode voltar pelo lado da enumeração.
- Chaves antigas `optional_total` / `outros_total` saem; os consumidores
  (`_qualif_grand_total_html`, portal, bloco financeiro) são atualizados.

### Remissiva (D6, D7)

`_qualif_scope_ref(qualification_type)`:

1. Mapeia tipo → code da seção: `installation`→`SEC-QI`,
   `operational`→`SEC-QO`, `performance`→`SEC-QD`, `software`→`SEC-QS`,
   `calibration`→`SEC-CALIB`.
2. Procura em `proposal_block_ids.filtered('included')` o bloco cujo
   `section_id.code` bate.
3. Número via `_proposal_block_numbering()[block.id]`.

Degradações obrigatórias:

- Bloco ausente (cliente removeu) → `"Qualificação de Instalação (QI)"`, sem
  "Conforme item".
- `show_number = False` → numbering devolve `""` → mesma degradação.
- Nunca interpolar `None`/`False` no QWeb.

Portal também numera (`sale_order_portal_template.xml:97` já chama
`_proposal_block_numbering()`), então PDF e portal citam o mesmo número.

### Previsão de dias (D3)

- Horas do grupo: override `line.estimated_hours`, senão
  `cycle_type_id.estimated_hours` / `malha_type_id.estimated_hours`, senão
  `afr.qualificacao.type.config.estimated_hours` do tipo — mesma hierarquia
  de `_qualif_estimated_hours`. Multiplicadas por
  `qualif_cycle_qty or product_uom_qty`.
- Dias do grupo = horas ÷ `_qualif_work_hours_per_day(equipment)`,
  arredondado **para cima ao próximo 0,5** (fórmula já usada em
  `block_cycle_specs.xml`).
- Rodapé = soma dos dias arredondados dos grupos, para fechar com o
  impresso.

`_qualif_section_hours(equipment, phase)` hoje só aceita `qo`/`qd`/
`calibration` — QI é inalcançável. Estender para
`_qualif_group_hours(equipment, qtype, part=None)` e reapontar os
chamadores existentes.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `models/sale_order.py` | `_qualif_scope_table`, `_qualif_scope_ref`, `_qualif_group_hours`; reescrita de `_qualif_proposal_totals` e `_qualif_grand_total_html` |
| `reports/templates_blocos/block_equipment_scope.xml` | Tabela nova + bloco de totais ao fim (PDF) |
| `views/sale_order_portal_template.xml` | Mesma tabela no escopo (`:143`); total geral do portal (`:465`) alinhado ao novo formato |
| `models/proposal_block.py` | `_html_equipment_scope` reescrito sobre `_qualif_scope_table` |
| `reports/templates_blocos/styles.xml` | Estilos: 2 colunas, linha de previsão/subtotal, rodapé, tabela de ciclos aninhada |
| `data/proposal_template_seed.xml` | Remove `l12` (financial) e `l13` (optionals) |
| `data/proposal_template_cleanup.xml` (novo, sem `noupdate`) | `<delete>` dos blocos financial/optionals do template TPL-LABQUALI em bases existentes |
| `__manifest__.py` | Versão + novo data file |

Não mudam: `block_cycle_specs.xml`, `_html_cycle_specs`, `block_financial.xml`,
`block_optionals.xml`, `_html_optionals`, aba Opcionais do form
(`sale_order_views.xml:132`), wizard configurador. Os tipos de bloco
continuam disponíveis para quem montar template manualmente.

### Delete dos blocos seeded

O seed é `noupdate="1"`: remover o `<record>` não apaga o registro de bases
existentes. Forma segura (não depende de `ref()` a xmlid removido):

```xml
<delete model="afr.proposal.template.line"
        search="[('template_id.code','=','TPL-LABQUALI'),
                 ('block_kind','in',['financial','optionals'])]"/>
```

Validar no banco local antes de subir: o `<delete>` roda em arquivo **sem**
`noupdate`, e o `<record>` correspondente sai do seed no mesmo commit.
Cotações já materializadas (`afr.proposal.block`) não são tocadas — só o
template.

## Testes

Novo `tests/test_scope_table.py`:

1. `_qualif_scope_table` monta os 3 grupos com labels e subtotal_labels corretos.
2. Σ subtotais dos grupos == `equipment_subtotal` da section line.
3. Rodapé: dias == soma dos dias arredondados; `unit_price` == alvo quando
   `state == 'ok'`.
4. Alvo desviado → `unit_price` cai para `equipment_subtotal` (D4).
5. Opcional aceito com `equipment_id` não entra no escopo, entra nos adicionais.
6. Tipo fora da matriz (QS) vira grupo próprio, não some.
7. Remissiva: com bloco SEC-QI presente cita número; sem bloco, degrada pro nome.
8. `residual == 0` numa cotação com equipamentos + adicionais + opcional recusado.
9. Sem adicionais → bloco de total imprime só `TOTAL GERAL DA PROPOSTA`.

Suítes existentes a ajustar (assertam os bullets F8.16 e o bloco financeiro):
`test_partes_qi_qo.py` (`qq-scope-type-row`), `test_qo_cycles.py`,
`test_proposal_report.py` (`test_scope_bullet_process_word_follows_category`),
`test_proposal_builder.py`, `test_proposal_block_edit.py`,
`test_docx_render.py`, `test_quotation_report.py`,
`test_optional_accepted.py`, `test_optional_wizard.py`,
`test_hours_vs_cycles.py`, `test_equipment_target_price.py`.

Execução via subagente `test-runner`.

## Validação manual

1. Odoo local (porta 8083), `-u afr_qualificacao`, restart para assets.
2. Cotação com autoclave a vapor: QI/QO parte 01 e 02, calibrações,
   ciclos QO sem carga e QD com carga, preço-alvo rateado, um adicional
   (viagem) e um opcional recusado.
3. Conferir PDF, portal e DOCX pelo `agent-browser`; a soma impressa tem de
   fechar com o `amount_untaxed` do SO nos três.
4. Só depois: produção.

## Riscos

- **Layout em 2 colunas com tabela aninhada no wkhtmltopdf.** Tabela dentro
  de `<td>` quebra página mal. Mitigação: `page-break-inside: avoid` no
  bloco do grupo e teste com equipamento de muitos ciclos.
- **Alvo desviado.** D4 evita imprimir número que não fecha, mas o comercial
  vê um valor diferente do alvo que digitou. O form já sinaliza o drift; a
  resolução continua sendo aplicar o rateio.
- **Cotações antigas.** O template default muda só para cotações novas;
  cotações com blocos já materializados seguem com financial/optionals.
  Intencional.
