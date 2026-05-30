# Design — Templates de cotação QI/QO/QD fáceis para vendas

**Data:** 2026-05-30 · **Módulo:** afr_qualificacao (16.0.4.19.0) · **Fase:** 1 de 2

## Problema
Time de vendas demora/erra ao montar cotação de Qualificação Térmica (QI/QO/QD).
Três frições confirmadas:
1. **Montar equipamento do zero** — só "Autoclave a Vapor" vem pronto como pacote
   (`afr.qualificacao.config.template`); o catálogo de ciclos/malhas cobre ~6
   equipamentos mas não há pacote pronto pros demais.
2. **Preços errados** — todos os ciclos compartilham **um** produto
   (`product_cycle_execution`) e todas as malhas compartilham
   `product_malha_calibracao`; logo o preço não distingue por equipamento e
   `list_price` pode vir zerado.
3. **Muitos cliques** — wizard configurador multi-step; pacote não vem pré-escolhido.

Fonte da verdade do conteúdo: `docs/Exemplos diversos/REFERENCIA_PROPOSTAS_LABQUALI.md`
(consolidado dos 3 `.doc` reais do cliente).

## Decisões (tomadas pelo usuário em 2026-05-30)
- **Arquétipo primeiro:** QI/QO/QD (Térmica). Calibração pura e Venda+Calibração ficam para depois.
- **Abordagem:** B faseado — Fase 1 = dados (pacotes + preços); Fase 2 = encurtar fluxo.
- **Modelo de faturamento:** manter **por linha** (ciclo/malha) — não por equipamento nem por fase.
- **Fonte de preço:** **produto Odoo (`list_price`)** — comercial mantém no produto.
- **Consequência obrigatória:** como o preço vem do produto e o faturamento é por
  linha, cada ciclo/malha precisa de **produto próprio** → split do produto
  compartilhado em N produtos distintos (1 por `cycle.type` + 1 por `malha.type`).

## Escopo — Fase 1

### 1. Split de produtos (resolve "preços errados")
- Criar 1 `product.product` (serviço, `invoice_policy='delivery'`) por `cycle.type`
  e por `malha.type` existente, cada um com seu `list_price` (valor inicial de
  referência; comercial ajusta).
- Reapontar `cycle.type.product_id` / `malha.type.product_id` para o produto novo.
- Produtos compartilhados antigos (`product_cycle_execution`,
  `product_malha_calibracao`) ficam órfãos/descontinuados — **não** mexer em SO
  lines já existentes (elas guardam cópia do `product_id`).
- Risco: médio. Mitigação: não tocar dados transacionais; só catálogo.

### 2. Completar catálogo (resolve "montar do zero" — pré-requisito dos pacotes)
- Novos `cycle.type`: Seladora, Secadora (Sercon), Autoclave a Gás Exterimax
  (variantes faltantes vs §4 da referência).
- Novo `malha.type`: **Temporizador** (recorrente nos `.doc`, hoje inexistente).
- Cada novo tipo com `temperature`/`duration`/`estimated_hours`/`product_id` (item 1).

### 3. Pacotes prontos (resolve "montar do zero")
- Seedar/criar os `config.template` faltantes espelhando a tabela §4 da referência:
  Termodesinfectora, Lavadora Ultrassônica, Refrigerador/Freezer/Câmara (grupo),
  Estufa de Esterilização/Despirogenização, Autoclave a Gás (ETO), Autoclave a Gás
  Exterimax, Seladora, Secadora.
- Cada pacote: `do_qi`/`do_qo`, `qo_line_ids` (ciclos sem carga), `qd_line_ids`
  (ciclos com carga), `calib_line_ids` (malhas incl. Temporizador), `estimated_days`.

### Fluxo (inalterado na Fase 1)
Configurador → adiciona equipamento → escolhe pacote (`config_template_id`) →
onchange `_onchange_config_template` auto-preenche linhas QD/QO/Calib com qty,
`estimated_hours`, descrição e `unit_price` (de `product.list_price`).

## Fora de escopo (Fase 2 / depois)
- Encurtar o wizard (menos steps / "adicionar por pacote" em 1 tela).
- Enriquecer o documento PDF/blocos institucionais (NÃO é fricção atual).
- Templates de Calibração pura e Venda+Calibração.

## Entrega / workflow (definido pelo usuário)
- Se houver **código** (modelos/seed XML/tests): commit+push no submodule
  `afr_qualificacao` → usuário faz pull no server → eu faço upgrade do módulo.
- **Templates e pacotes**: adicionados no server **labquali** via odoo-mcp.
- Decisão aberta a confirmar: pacotes/produtos como **seed XML no módulo**
  (reprodutível em fresh install, exige upgrade) **vs** apenas **dados live via
  MCP** (rápido, sem reprodutibilidade). Recomendação: seed XML para o que é
  catálogo estável (produtos, cycle/malha types, pacotes), pois sobrevive a
  reinstalação e mantém paridade dev/prod.

## Testes
- Seed load: N pacotes presentes após install/upgrade.
- Autofill: para cada pacote, onchange popula linhas com `unit_price` ≠ 0,
  `estimated_hours` ≠ 0, qty correta.
- Regressão: suíte existente (~236 tests) sem quebra.

## Riscos
- Split de produtos toca o catálogo central — validar que SO lines existentes não
  regridem (guardam product_id próprio).
- Valores de `list_price` por ciclo/malha não vêm dos `.doc` (lá é por
  equipamento/fase) → seed com defaults; comercial revisa.
