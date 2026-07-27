# Rateio de Preço Final por Equipamento (processo inverso)

Data: 2026-07-26
Módulo: `afr_qualificacao`
Status: design aprovado, pronto para plano de implementação

## Problema

Hoje a precificação é **direta**: o wizard configurador define `price_unit` por
linha (R$/hora nas linhas de ciclo/malha; valor fechado em QI/QO-Parte01/QS) e
`product_uom_qty` = horas (`nº ciclos × horas/ciclo`). O total do equipamento é
consequência da soma — e sai quebrado (ex.: C26-07-0009 = R$ 3.858,47).

O cliente quer o **inverso**: negociar um preço final fechado por equipamento
(ex.: R$ 8.000,00) e o sistema distribuir esse total entre as linhas daquele
equipamento, back-calculando o `price_unit` de cada uma, de modo que a soma dos
subtotais do equipamento dê exatamente o valor negociado.

## Decisões

| Decisão | Escolha |
|---|---|
| Base do alvo | **Sem impostos** — alvo = Σ `price_subtotal` das linhas do equipamento |
| Onde o vendedor digita | **Linha de section do equipamento no SO** (não no wizard) |
| Após editar ciclos/horas | **One-shot + aviso de desvio** — nada recalcula sozinho |
| Critério de rateio | **Proporcional ao subtotal atual** (preserva o mix de preços) |
| Base do rateio | Só qualificações firmes (managed, qty>0, não opcional, não declinada) |
| Proposta PDF | **Sem mudança** — já imprime `price_subtotal` por item |
| Resíduo de arredondamento | Busca combinada em até 3 linhas; avisa se impossível |

Verificado no ambiente `odoo-labquali`: `account.tax` id=1 (ICMS 17%) tem
`price_include = False`, e a maioria dos SOs sai com `amount_tax = 0` por posição
fiscal. Precisão decimal "Product Price" = **2 casas** (global — não alterar).

## Modelo de dados

Campos novos em `sale.order.line`, relevantes apenas em linhas com
`display_type = 'line_section'` e `equipment_id` preenchido:

| Campo | Tipo | Papel |
|---|---|---|
| `equipment_target_price` | Monetary, editável, `copy=True` | Preço final fechado do equipamento |
| `equipment_target_delta` | Monetary, compute | `equipment_subtotal − equipment_target_price` (0 quando não há alvo) |
| `equipment_target_state` | Selection compute (`none`/`ok`/`drift`) | Dirige decoration no tree |

`equipment_target_state`:
- `none` — sem alvo definido
- `ok` — alvo definido e `equipment_subtotal == equipment_target_price`
- `drift` — alvo definido e subtotal divergente (escopo mudou, ou fechamento
  exato foi impossível)

`copy=True` no alvo: duplicar o SO carrega o preço negociado, coerente com o
`copy=True` já usado nos metadados de qualificação da linha.

## Fluxo de uso

1. Vendedor monta o escopo pelo wizard configurador (inalterado).
2. No tree do SO, digita `equipment_target_price` na linha de section do
   equipamento e salva.
3. Clica o botão **Ratear** na própria linha de section
   (`<button type="object">` no tree).
   Alternativa em massa: botão **Ratear todos** no header do SO, que processa
   todo equipamento em estado `drift`.
4. O rateio é um `write` real (não `onchange`) — exige o SO salvo. `onchange` de
   linha não altera linhas irmãs de forma confiável.
5. Se depois o vendedor mexer em ciclos/horas/linhas, `equipment_subtotal` muda,
   o estado vira `drift`, a linha ganha `decoration-warning` e o delta fica
   visível. Nada recalcula sozinho — reaplicar é ação manual.

### Sobrevivência ao re-apply do wizard

O configurador apaga e recria as linhas `is_qualificacao_managed`, incluindo as
sections — o alvo morreria. Seguir o padrão já existente para
`config_template_id`: antes de recriar, o wizard lê `{equipment_id: target}` das
sections atuais e regrava nas novas sections.

Após o re-apply os `price_unit` voltam aos valores de tabela, então o equipamento
entra em `drift` e o vendedor clica Ratear. Comportamento previsível, sem
recálculo implícito.

## Algoritmo

Método `_apply_equipment_target(target)` na linha de section, apoiado por um
helper puro (sem ORM) para o cálculo dos shares, testável isoladamente.

**1. Base.** Linhas do mesmo `equipment_id`, no mesmo SO, que satisfaçam:
`is_qualificacao_managed`, `not display_type`, `not is_proposal_optional`,
`not part01_declined`, `product_uom_qty > 0`.

Ficam **fora** e não têm preço tocado:
- linhas de section (qty=0, preço 0);
- Parte 01 declinada — `price_unit` é preço de referência impresso na proposta;
  reescalar distorceria o documento;
- opcionais (aceitos ou não);
- linhas manuais não-managed, mesmo com `equipment_id`.

**2. Guardas.**
- `current = Σ price_subtotal` da base. `current == 0` → `UserError`
  ("defina os preços base antes de ratear").
- Base vazia → `UserError`.
- `target <= 0` → limpa o alvo, não mexe em nenhum preço.

**3. Shares.** `share_i = round(target × subtotal_i / current, 2)`.
Resíduo `target − Σ share` é somado à linha de maior subtotal (menos visível).

**4. Back-calc.** `pu_i = round(share_i / qty_i, 2)`, escrito em `price_unit`.

**5. Verificação real.** Após o `write`, reler `price_subtotal` do ORM e calcular
`diff = target − Σ price_subtotal`. A asserção é sobre o que o Odoo computou em
`compute_all`, nunca sobre a aritmética local.

**6. Correção fina.** Se `diff != 0`: cada linha tem uma grade própria — o passo
de subtotal por centavo de `price_unit` é `qty × 0,01` (qty=1 → R$ 0,01;
qty=7,5 → ≈ R$ 0,08). Ordenar as linhas da grade mais fina para a mais grossa e
buscar um ajuste combinado de `n × 0,01` no `price_unit` de até 3 linhas, com
`|n| ≤ 20`, que zere `diff`. Reverificar lendo `price_subtotal` de novo.

**7. Falha honesta.** Se ainda sobrar diferença, gravar assim mesmo (melhor
aproximação), postar mensagem no chatter e devolver notification:
"Fechou em R$ 7.999,97 — R$ 0,03 abaixo do alvo (limite de arredondamento)".
Estado permanece `drift`, nunca `ok`.

**8. Idempotência.** Rodar duas vezes seguidas não altera nenhum `price_unit`.

## Ajuste de coerência

`equipment_subtotal` (compute existente em `sale_order_line.py:229`) soma todas
as linhas de produto com aquele `equipment_id`, incluindo opcionais aceitos — que
o rateio exclui. Sem alinhamento, o delta mente.

`equipment_subtotal` passa a usar exatamente a mesma base do rateio. Opcionais
aceitos deixam de entrar nesse número.

## Testes

Arquivo novo `tests/test_equipment_target_price.py`, seguindo o padrão do módulo.

1. **Invariante exata** — alvo R$ 10.000,00 sobre 3 linhas (7,5h / 12,3h / qty=1);
   assertar `Σ price_subtotal == 10000.00` lendo do ORM após o write.
2. **Só ciclos fracionários** — 2 linhas (7,5h / 12,3h), sem linha qty=1;
   exercita a busca combinada do passo 6.
3. **Impossível** — configuração onde nenhuma combinação fecha: assertar a
   diferença mínima, a mensagem no chatter e `state == 'drift'`.
4. **Idempotência** — rodar 2×, `price_unit` idêntico.
5. **Membership** — Parte 01 declinada fora da base e com `price_unit`
   inalterado; opcional aceito fora; section intocada; linha manual intocada.
6. **Drift** — editar `qualif_cycle_qty` após ratear → `state == 'drift'` e delta
   igual à diferença real.
7. **Sobrevive ao wizard** — gravar alvo, re-apply do configurador, alvo presente
   na nova section.
8. **Guardas** — base com preços zerados → `UserError`; base vazia → `UserError`;
   alvo 0 → limpa sem tocar preço.

## Fora de escopo

- Alvo no SO inteiro (rateio de dois níveis).
- Alvo com impostos embutidos.
- Peso manual por linha.
- Mudanças no PDF da proposta — já imprime `price_subtotal`, a soma passa a bater
  no alvo automaticamente.
- Rateio de opcionais.
- Campo de alvo no wizard configurador (o wizard só preserva o alvo existente).

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `models/sale_order_line.py` | Campos novos, computes, `_apply_equipment_target`, helper de shares, alinhamento de `equipment_subtotal` |
| `models/sale_order.py` | Botão "Ratear todos" no header |
| `views/sale_order_views.xml` | Colunas alvo/delta, botão na section, `decoration-warning` |
| `wizards/qualificacao_configurator.py` | Preservar `{equipment_id: target}` no re-apply |
| `tests/test_equipment_target_price.py` | Novo |
| `__manifest__.py` | Bump de versão (feat → MINOR) |
