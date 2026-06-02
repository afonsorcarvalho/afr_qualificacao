# Design — Partes 01/02 da QI e QO + declínio de execução (Parte 01)

**Módulo:** afr_qualificacao
**Data:** 2026-06-01
**Bump alvo:** 16.0.5.9.0
**Escopo:** apenas comercial (proposta/cotação). NÃO toca execução `afr.qualificacao` / `engc.os` / relatório QI/QO.

## Contexto de negócio

QI (Qualificação de Instalação) e QO (Qualificação de Operação) têm **duas partes** cada:

| Tipo | Parte 01 | Parte 02 |
|---|---|---|
| **QI** | Verificações (11 itens: documentação, elementos de controle, software, componentes, materiais, instrumentação, utilidades, equipamentos críticos, alimentação/proteção, conexões, módulos I/O) | Calibrações (certificados / rastreabilidade metrológica) = **malhas existentes** |
| **QO** | Verificações, avaliações e comprovações (11 itens: perda energia, validação software, parâmetros, alarmes, controle de acesso, intertravamento, auditoria, segurança info, backup, falta utilidades, interface operador) | Ciclos de operação sem carga = **ciclos existentes** |

**Regras:**
- A **Parte 02 é obrigatória** se o tipo for feito. Não existe "só Parte 01".
- A **Parte 01 é opcional** — o cliente pode declinar (não solicitar execução).
- A **Parte 01 é bem mais cara** → preço próprio, separado.
- Combinações válidas por tipo: (1) Completa = P01+P02; (2) Só P02 (P01 declinada); (3) Nenhuma (tipo não selecionado).

**Problema regulatório:** a Vigilância Sanitária **exige** a Parte 01. Quando o cliente não a solicita, a proposta deve **registrar explicitamente** que a Parte 01 não foi solicitada para execução — evidência documentada de que a omissão foi escolha do cliente (auditoria pergunta o porquê).

**Cardinalidade:**
- QI Parte 01 → 1 linha por equipamento
- QI Parte 02 → N linhas (malhas)
- QO Parte 01 → 1 linha por equipamento (**novo no fluxo** — hoje QO só tem ciclos)
- QO Parte 02 → N linhas (ciclos)

## Estado atual (referência)

- `sale.order.line` tem `qualification_type` Selection (`installation`/`operational`/`performance`/`software`/`calibration`), `equipment_id`, `is_qualificacao_managed`.
- Preços: QI/QS via `afr.qualificacao.type.config.default_unit_price`; QO/QD via `cycle_type.product_id` + `unit_price` da sub-linha; Calib via `malha_type.product_id` + `unit_price`.
- Configurador (`afr.qualificacao.configurator.equipment`): `do_qi`, `do_qo`, `do_qs` (bools) + `qo_line_ids` (ciclos), `qd_line_ids`, `calib_line_ids` (malhas).
- `action_apply` apaga linhas managed e recria a matriz; semeia section line por equipamento; chama `_seed_proposal_blocks`.
- Relatório cotação custom (inherit `sale.report_saleorder_document`, gate `has_qualif_lines`) + portal + helper `_qualif_schedule_rows`.

## Contexto de ambiente

labquali (remoto) **ainda em desenvolvimento**: sem produção, sem cotações reais. **Migration NÃO necessária** — pode recriar produtos/variantes. (Quando entrar em produção o user avisará; ver memória `project_labquali_dev_stage`.)

## Abordagem escolhida — "A" (atributo de produto / variantes)

### Bloco 1 — Catálogo

- Novo `product.attribute` **"Parte"** (`create_variant='always'`), valores **"Parte 01"** e **"Parte 02"** (seed XML).
- Aplicado aos produtos-serviço de `type_config` **installation (QI)** e **operational (QO)** → cada produto vira 2 variantes.
- **Parte=01** carrega o preço das verificações (via `price_extra` do `product.template.attribute.value` ou `list_price`/lista do variante — definir no plano; preferência: `price_extra` no valor Parte 01).
- **Parte=02** existe como rótulo; o preço real da Parte 02 segue vindo das malhas (QI) / ciclos (QO).
- `type_config.service_product_id` (QI e QO) passa a resolver o **variante Parte=01** para a linha de verificação. Sem migration.

### Bloco 2 — Modelo de dados (`sale.order.line`)

- `part` Selection `{('01','Parte 01'),('02','Parte 02')}` — set pelo configurador.
- `part01_declined` Boolean — Parte 01 "não solicitada execução".
- Linha Parte 01 declinada: `product_uom_qty=0` (subtotal 0 → **não infla `amount_total`**), `price_unit` mantém o valor do variante para exibição no relatório. `is_qualificacao_managed=True`.
- Sem novo modelo.

### Bloco 3 — Configurador (`afr.qualificacao.configurator.equipment`)

Novos campos:
- `do_qi` (existe) = QI Parte 01. + `qi_part01_declined` Boolean.
- `do_qo_part01` Boolean (**novo**) = QO Parte 01 (verificações), 1×/equip. + `qo_part01_declined` Boolean.
- `qo_line_ids` (existe) = QO Parte 02 (ciclos). `calib_line_ids` (existe) = QI Parte 02 (malhas). Inalterados; ganham `part='02'` na geração.

`action_apply`:
- QI Parte 01: linha do variante QI Parte=01, `part='01'`, qty=1. Se `qi_part01_declined` → `qty=0` + `part01_declined=True`, `price_unit`=preço do variante.
- QO Parte 01: **nova** linha do variante QO Parte=01, `part='01'`, qty=1, mesma lógica de decline.
- Malhas → `part='02'` (QI). Ciclos → `part='02'` (QO). Demais inalterados.
- Validação: não declinar Parte 01 de um tipo sem a Parte 02 correspondente selecionada (aviso `UserError`).

Decline = checkbox **por equipamento** (um por QI, um por QO).

### Bloco 4 — Relatório / proposta

Agrupamento por Parte (PDF cotação + portal), por equipamento:
- `PARTE 01 — Verificações` → linhas `part='01'`
- `PARTE 02 — Calibrações` (QI) / `PARTE 02 — Ciclos de Operação` (QO) → linhas `part='02'`

Linha Parte 01 declinada (formato **a**): aparece no escopo **com o preço** (`price_unit`), destacada/riscada + selo **"NÃO SOLICITADO EXECUÇÃO"**; **não soma** ao total.

Box formal (formato **c**): seção **"Itens Não Solicitados para Execução"** — só aparece se houver ≥1 declínio. Lista equipamento + tipo + valor de referência + declaração institucional.

**Rascunho do texto do box** (editável pelo user / noupdate):
> **ITENS NÃO SOLICITADOS PARA EXECUÇÃO**
> Os itens listados abaixo integram o escopo técnico recomendado da qualificação, conforme exigências da Vigilância Sanitária aplicáveis, porém **não foram solicitados para execução pelo cliente** nesta contratação. O registro é mantido para fins de rastreabilidade documental e eventual auditoria, evidenciando que a não realização decorreu de opção do contratante.
> [tabela: Equipamento | Tipo | Item (Parte 01) | Valor de referência]

Cronograma (`_qualif_schedule_rows` / `_html_schedule`): lista só executáveis; linhas declinadas (qty=0) ficam fora do cronograma.

## Renders impactados

1. Cotação PDF (`quotation_template.xml` / report inherit)
2. Portal (`sale_order_portal_template.xml`)
3. `qualif_subtotals_html` / `_html_schedule` (helper de blocos) — declinados excluídos do cronograma

## Testes (alvo)

- Configurador gera QI P01 + QO P01 (1 linha/equip cada) + P02 com `part='02'`.
- Decline QI/QO P01 → linha qty=0, `part01_declined=True`, `amount_total` não conta o preço.
- Variantes Parte=01/02 criados nos produtos QI/QO; type_config resolve Parte=01.
- Validação: declinar P01 sem P02 do tipo → `UserError`.
- Relatório: agrupa por parte; declinada com selo + fora do total; box aparece só com declínio; cronograma exclui declinada.
- Regressão: SO sem partes/decline renderiza como antes; suite existente verde.

## Fora de escopo

- Execução `afr.qualificacao` / `engc.os` / relatório final QI/QO (os 11 itens como collect items).
- Migration (ambiente dev).
- Parte 02 colapsada num único item (rejeitado — mantém granularidade malha/ciclo + cronograma).
