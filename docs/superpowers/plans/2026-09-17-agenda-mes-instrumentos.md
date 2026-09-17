# Plano — Instrumentos no modo Mês (triângulos)

Data: 2026-09-17
Branch: `feat/agenda-instrumentos-mes` (submodule `addons/afr_qualificacao`)
Escopo: **somente frontend** em `pwa/`. Nenhuma mudança em Python.

## Contexto

O modo Mês da agenda (entregue em `61abc81`) mostra, em cada célula da grade
de 42 dias, um pontinho colorido por técnico com visita naquele dia. O usuário
pediu a mesma leitura para os **instrumentos de qualificação**, representados
por **triângulos** (a bolinha continua sendo o técnico), e a possibilidade de
ver quais instrumentos rodam em cada dia.

Arquivos de hoje:

- `pwa/app/tecnico/qualificacao/agenda/mes.ts` — funções puras (`gradeDoMes`,
  `tecnicosPorDia`, `corDoTecnico`, `PALETA` de 12 tons, `COR_SEM_TECNICO`).
- `pwa/app/tecnico/qualificacao/agenda/_GradeMes.tsx` — a grade 6×7.
- `pwa/app/tecnico/qualificacao/agenda/_VistaMes.tsx` — grade + legenda +
  cards do dia selecionado.
- `pwa/app/tecnico/qualificacao/agenda/page.tsx` — estado e queries.
- `pwa/app/tecnico/qualificacao/agenda/carga.ts` — `usoPorInstrumento(visitas,
  dia, instrumentos)`, que o painel do modo Semana já usa e devolve, por
  instrumento, os usos do dia com `osName`, `tecnicoName` e `faixa` de horário.

**Armadilha de dados, verificada no servidor:** em `_pwa_serialize`
(`afr_qualificacao_agendamento/models/os_visita.py`), `instrument_ids` são os
ids, mas `instrument_list` é `list(filter(None, ...mapped('name')))` — um
instrumento sem nome some da lista e permanece nos ids. **Os dois arrays podem
ficar desalinhados; nunca pareie por índice.** O nome vem de
`pwa_instrumento_options` (`useInstrumentoOptions`); id que não estiver lá vira
`Instrumento #<id>`.

## Global Constraints

1. **Nenhuma mudança em arquivo Python, nem bump de `__manifest__.py`.**
2. **Nunca ler o relógio do aparelho:** só `Date.UTC`/`setUTCDate`, strings ISO
   `YYYY-MM-DD`, `Intl` sempre com `timeZone:'UTC'`. O "hoje" vem de
   `data.server_today`.
3. **Sem dependência nova.**
4. **Acessibilidade:** alvos de toque `min-h-[44px]`; **cor e forma nunca são o
   único portador** — tudo que o desenho diz, o `aria-label` também diz.
5. **UI em pt-BR**; comentários em pt-BR explicando o PORQUÊ.
6. **Testes:** `npm run test` e `npx tsc --noEmit` a partir de `pwa/`. Testes em
   `pwa/app/tecnico/qualificacao/__tests__/`. Baseline: **385 testes verdes** —
   qualquer falha é regressão.
7. **TDD:** teste que falha primeiro.
8. Há um dev server em `:3010` a partir de `pwa/`: não derrubar, não subir
   outro, não rodar `npm run build`.

## Task 1 — `mes.ts`: instrumentos por dia e cor de recurso

### Funções

```ts
/** Cor estável por id, da mesma `PALETA` de 12 tons. Técnico e instrumento
 *  podem cair na mesma cor — o que separa os dois domínios é a FORMA
 *  (bolinha x triângulo), não o matiz. */
export function corDoInstrumento(id: number): string

/** Um item por instrumento distinto usado no dia, na ordem de `opcoes`
 *  (que já vem ordenada do servidor), seguido dos ids que não estão em
 *  `opcoes`, em ordem crescente de id. */
export function instrumentosPorDia(
  visitas: VisitaAgenda[],
  dias: string[],
  opcoes: InstrumentoOpcao[],
): PontosInstrumentoDia[]
```

```ts
export interface PontoInstrumento {
  id: number
  /** Nome de `pwa_instrumento_options`; `Instrumento #<id>` quando o id não
   *  está nas opções — NUNCA pareado com `instrument_list`, que pode estar
   *  desalinhado com `instrument_ids` (ver Contexto). */
  name: string
  cor: string
  /** Quantas visitas do dia usam este instrumento. */
  visitas: number
}

export interface PontosInstrumentoDia {
  date: string
  instrumentos: PontoInstrumento[]
}
```

`corDoTecnico` e `COR_SEM_TECNICO` continuam exportados e inalterados: a grade
e a legenda de técnicos dependem deles e há testes em cima.

### Testes (acrescentar a `__tests__/mes.test.ts`)

- Dia com duas visitas usando o MESMO instrumento rende **um** item com
  `visitas: 2`.
- Instrumento presente em `instrument_ids` mas ausente de `opcoes` vira
  `Instrumento #<id>` — e este teste usa uma visita cujo `instrument_list`
  contém OUTRO nome, provando que o código não pareia por índice.
- Dia sem visita rende `instrumentos: []`.
- Instrumento que está nas opções mas não é usado no dia não vira ponto.
- A ordem segue `opcoes`, com os desconhecidos no fim por id crescente.
- `corDoInstrumento` é estável para o mesmo id e vem da `PALETA`.
- A guarda de contraste existente (que mede a `PALETA` contra os quatro fundos)
  continua verde — não afrouxe nem remova essa asserção.

## Task 2 — `_GradeMes.tsx`: o triângulo e a regra de slots

### Props

`GradeMes` ganha `instrumentos: PontosInstrumentoDia[]`, na MESMA ordem de
`dias` (as duas listas vêm de `gradeDoMes`). Não derive uma da outra por
índice sem checar `date`: case os dois por `date`, não por posição.

### Desenho da célula

Uma fileira só, bolinhas (técnicos) primeiro, triângulos (instrumentos)
depois. Triângulo em **SVG inline** com `fill` da cor (não borda CSS), tamanho
próximo ao da bolinha, `aria-hidden` como as bolinhas.

Regra de lotação, com `total = tecnicos.length + instrumentos.length`:

- `total <= 4`: mostra todos, sem `+N`.
- `total > 4`: mostra **3 marcas + `+N`**, com `N = total - 3`. Os 3 slots são
  repartidos assim: se os dois tipos têm item, **cada tipo recebe 1 slot
  garantido** e o slot restante vai para o tipo com mais itens (empate →
  técnicos). Se só um tipo tem item, ele leva os 3.
  Sem essa garantia, um dia com 3 técnicos e 5 instrumentos esconderia os
  instrumentos por inteiro — que é justamente o que esta feature existe para
  mostrar.

### `aria-label`

Passa a carregar os dois grupos, em pt-BR:
`"17 de setembro, hoje, 3 visitas: Ana Silva (2), João Lima; instrumentos: Q001, Q002"`.
Dia sem instrumento não escreve a parte de instrumentos. O que já existe
(prefixo "fora do mês, ", sufixo ", hoje", ", com conflito", contagem
`Nome (2)`) permanece.

### Testes (`__tests__/GradeMes.test.tsx`)

- Dia com 2 técnicos e 1 instrumento: 3 marcas, sem `+N`.
- Dia com 3 técnicos e 5 instrumentos: `+5`, e **pelo menos um triângulo E pelo
  menos uma bolinha** renderizados (o teste tem de falhar se a repartição
  ignorar um dos tipos).
- Dia com 5 instrumentos e nenhum técnico: 3 triângulos + `+2`.
- `aria-label` com e sem instrumentos.
- Bolinhas e triângulos continuam fora da árvore de acessibilidade.

## Task 3 — `_VistaMes.tsx` + `page.tsx`: legenda e lista do dia

### 3a. Query

`useInstrumentoOptions` hoje é habilitado com `semana && dimensao ===
'instrumento'`. Passa a ser habilitado também no Mês. Prefira uma expressão
única e legível (ex. `const querInstrumentos = mes || (semana && dimensao ===
'instrumento')`) em vez de espalhar `|| mes`.

### 3b. Legenda

A legenda abaixo da grade ganha uma segunda faixa: triângulo + nome, só dos
instrumentos usados nos **42 dias da grade** (mesmo critério da faixa de
técnicos, que cobre a janela desenhada, não o mês estrito). Sem instrumento
na janela, a faixa não é renderizada — nada de rótulo órfão.

### 3c. Lista do dia selecionado

Acima dos `VisitaCard`, uma seção "Instrumentos do dia": uma linha por
instrumento usado no dia selecionado, com o triângulo da cor, o nome, e os
usos (OS e faixa de horário). **Reuse `usoPorInstrumento` de `carga.ts`** —
ela já monta exatamente isso para o painel da Semana; filtre o resultado para
os instrumentos com uso no dia. Não reimplemente a agregação.

Dia sem instrumento: a seção não aparece (o "Nenhuma visita neste dia." já
cobre o dia vazio).

**Fora de escopo, por escolha do usuário:** aviso de certificado vencido. Não
renderize aviso de vencido nem na legenda nem na lista, mesmo que
`InstrumentoOpcao.validade` esteja à mão.

### Testes (`__tests__/ModoMes.test.tsx`)

- Legenda mostra o instrumento usado na janela e **não** mostra um instrumento
  das opções que ninguém usa.
- Sem instrumento na janela, a faixa de instrumentos não é renderizada.
- Tocar num dia com instrumento mostra a seção com nome, OS e faixa de horário.
- Tocar num dia sem instrumento não mostra a seção.
- `useInstrumentoOptions` é habilitado no modo Mês (asserção sobre o argumento
  do mock).
- Nenhum texto de "vencido" aparece, mesmo com `validade` passada — guarda do
  escopo acordado.

## Task 4 — Validação no navegador (o controlador faz, não subagente)

PWA em `:3010` contra o Odoo de `qualificacao-dev` em `:8084`: conferir
triângulos na grade, legenda das duas faixas, lista do dia, um dia com
estouro de marcas (`+N` com os dois tipos visíveis), tema claro e escuro, e
viewport de 390px.
