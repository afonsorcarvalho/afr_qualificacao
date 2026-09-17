# Plano — Modo Mês na agenda do PWA Técnico

Data: 2026-09-17
Branch: `feat/agenda-modo-mes` (submodule `addons/afr_qualificacao`)
Escopo: **somente frontend** em `pwa/`. Nenhuma mudança em Python.

## Contexto

A agenda (`pwa/app/tecnico/qualificacao/agenda/page.tsx`) tem hoje dois modos:
`lista` (janela de 14 dias, cards agrupados por dia) e `semana` (faixa de 7
dias + painel de recursos + gesto de mover visita). O usuário pediu um
terceiro modo, **Mês**, no espírito do Google Agenda do celular: uma grade do
mês inteiro que mostra de relance em que dias há visitas.

Decisões já tomadas com o usuário:

- Cada célula mostra o número do dia + **pontinhos coloridos, um por técnico**
  com visita naquele dia (cor estável por id). Nada de texto de evento.
- Tocar num dia **seleciona o dia** e lista os `VisitaCard` daquele dia abaixo
  da grade; com uma visita selecionada para ajuste (só Gestor), tocar outro
  dia **move a visita** para lá — mesmo gesto do modo Semana.

O backend já serve isto sem mudança: `pwa_agenda_fetch` aceita
`date_from`/`date_to` arbitrários e trunca em `_PWA_MAX_SPAN_DAYS = 92`; a
grade de 42 dias cabe.

## Global Constraints

Valem para TODAS as tasks. Uma violação é achado de review.

1. **Nenhuma mudança em arquivo Python, nem bump de `__manifest__.py`.**
   Mudança só de front não bumpa a versão do módulo (a versão do PWA vive no
   `package.json`, e nesta feature não muda).
2. **Nunca ler o relógio do aparelho.** Toda aritmética de data usa
   `Date.UTC` / `setUTCDate` e strings ISO `YYYY-MM-DD`, como
   `deslocarJanela` em `agenda/janela.ts` e `diasDaSemana` em `agenda/carga.ts`.
   Nada de `new Date()` sem argumentos, `Date.now()`, `getFullYear()`,
   `toLocaleDateString()` sem `timeZone: 'UTC'`. O servidor é a fonte do
   "hoje" (`server_today` no payload).
3. **Sem dependência nova.** Só o que já está no `package.json`
   (react, next, zustand, @tanstack/react-query, clsx, lucide-react, vitest,
   @testing-library/react).
4. **Acessibilidade:** alvos de toque com `min-h-[44px]`; cor nunca é o único
   portador de informação — todo `aria-label` que dependa de cor carrega
   também o texto equivalente.
5. **Texto de UI em pt-BR.** Comentários de código em pt-BR, no mesmo estilo
   dos arquivos vizinhos: comentar o **porquê** (a armadilha que a linha
   evita), não o que a linha faz.
6. **Testes:** `npm run test` (vitest) a partir de `pwa/`. Testes novos ficam
   em `pwa/app/tecnico/qualificacao/__tests__/`. A baseline em
   `pwa/docs/BASELINE.md` é limpa: qualquer falha é regressão, não ruído.
   `npx tsc --noEmit` precisa passar.
7. **TDD:** teste que falha primeiro, depois a implementação.

## Task 1 — `agenda/mes.ts`: as funções puras da grade

Criar `pwa/app/tecnico/qualificacao/agenda/mes.ts`, sem React e sem rede, no
mesmo espírito de `carga.ts`. Criar
`pwa/app/tecnico/qualificacao/__tests__/mes.test.ts` com os casos abaixo.

### Funções

```ts
/** "2026-09-17" → "2026-09-01". Normaliza qualquer dia para o 1º do mês. */
export function primeiroDiaDoMes(iso: string): string

/** Soma `n` meses ao 1º do mês da âncora. `n` pode ser negativo.
 *  Sempre devolve o dia 1 do mês resultante — nunca estoura para o mês
 *  seguinte (o bug clássico de somar mês em cima de um dia 31). */
export function deslocarMes(iso: string, n: number): string

/** Grade de 6×7 = 42 dias ISO, começando no DOMINGO anterior (ou igual) ao
 *  dia 1 do mês da âncora. Sempre 42 — mês curto sobra dia no fim, mês que
 *  atravessa 6 semanas cabe. */
export function gradeDoMes(iso: string): string[]

/** `true` se a data ISO pertence ao mês da âncora (para esmaecer as células
 *  de fora sem escondê-las). */
export function noMes(iso: string, ancora: string): boolean

/** "setembro de 2026", pt-BR, `timeZone: 'UTC'`. */
export function rotuloMes(iso: string): string

/** Cor estável por id de técnico. `false` (visita sem técnico) devolve o
 *  cinza neutro. A estabilidade é por id, não por posição no roster: o
 *  roster muda de tamanho entre janelas e cores que dançam mentem sobre
 *  quem é quem. */
export function corDoTecnico(id: number | false): string

/** Um item por técnico distinto com visita no dia, na ordem do roster
 *  (que já vem ordenado por nome em `rosterTecnicos`), seguido do balde
 *  "sem técnico" quando houver visita sem `tecnico_id`. */
export function tecnicosPorDia(
  visitas: VisitaAgenda[],
  dias: string[],
  roster: Opcao[],
): PontosDia[]
```

```ts
export interface PontoTecnico {
  /** `false` = visita sem técnico atribuído. */
  id: number | false
  name: string   // "Sem técnico" quando id === false
  cor: string
  visitas: number
}

export interface PontosDia {
  date: string
  pontos: PontoTecnico[]
  /** Soma das visitas do dia (≥ soma dos pontos quando um técnico tem duas). */
  total: number
  conflito: boolean
}
```

`PALETA` é um array de cores fixas (hex ou `rgb()`) legíveis tanto no tema
claro quanto no escuro — os `--card` dos dois temas são quase branco e quase
preto, então use tons saturados de faixa média (equivalentes a tailwind
`*-500`: sky, emerald, amber, violet, rose, teal, orange, fuchsia). `corDoTecnico`
indexa a paleta por `id % PALETA.length`. Exporte `COR_SEM_TECNICO` (cinza
neutro) separado da paleta para que o teste possa afirmar que nenhum técnico
recebe a cor do "sem técnico".

Reutilize `Opcao` e `VisitaAgenda` de `@/lib/odoo/agenda` — não redefinir.

### Testes obrigatórios

- `gradeDoMes('2026-09-17')` tem 42 entradas, começa em `'2026-08-30'`
  (domingo) e termina em `'2026-10-10'`; `2026-09-01` e `2026-09-30` estão
  dentro.
- Mês cujo dia 1 **cai num domingo** (`2026-11-01`): a grade começa no próprio
  dia 1, não sete dias antes.
- Mês que precisa das 6 semanas (`2026-05-01`, sexta, 31 dias): o dia 31 está
  na grade.
- Fevereiro bissexto (`2028-02-01`): 29/02 presente, 30/02 ausente.
- `deslocarMes('2026-01-31', 1)` → `'2026-02-01'` (não `'2026-03-03'`).
- `deslocarMes('2026-01-15', -1)` → `'2025-12-01'`; `deslocarMes('2026-12-10', 1)`
  → `'2027-01-01'` (virada de ano nos dois sentidos).
- `noMes` marca as células acinzentadas do começo e do fim da grade como fora.
- `corDoTecnico` é estável entre chamadas para o mesmo id, e difere para dois
  ids que caem em índices diferentes da paleta; `corDoTecnico(false)` é
  `COR_SEM_TECNICO` e nenhum valor da `PALETA` é igual a ele.
- `tecnicosPorDia`: dia com duas visitas do MESMO técnico rende **um** ponto
  com `visitas: 2` e `total: 2`; dia com visita sem técnico rende o ponto
  "Sem técnico"; dia sem visita rende `pontos: []`, `total: 0`; `conflito`
  reflete `v.conflict` de qualquer visita do dia; técnico do roster **sem**
  visita no dia não vira ponto (a célula só mostra quem tem visita ali).

## Task 2 — `_GradeMes.tsx`: a grade

Criar `pwa/app/tecnico/qualificacao/agenda/_GradeMes.tsx` e
`pwa/app/tecnico/qualificacao/__tests__/GradeMes.test.tsx`.

```tsx
export function GradeMes({
  dias,            // PontosDia[42], na ordem de gradeDoMes
  ancora,          // 1º do mês visível, para saber o que esmaecer
  hoje,            // server_today ISO, ou null
  selecionado,     // ISO do dia selecionado
  onSelecionar,    // (date: string) => void
}: {...})
```

Requisitos:

- Cabeçalho de 7 colunas com as siglas `D S T Q Q S S` (pt-BR, derivadas via
  `Intl` com `timeZone: 'UTC'`, não hardcoded em array literal).
- 7 colunas × 6 linhas de botões. Cada célula: número do dia (2 dígitos), até
  **4 pontinhos**; com mais de 4 técnicos distintos, mostra 3 pontinhos + um
  rótulo textual `+N` (N = técnicos restantes).
- Célula fora do mês (`noMes === false`): esmaecida (`text-muted-foreground`,
  opacidade reduzida) mas **clicável** — mover uma visita para a célula
  acinzentada precisa funcionar, senão a visita sai da janela buscada e o
  gesto parece falhar.
- Dia selecionado: `aria-pressed={true}` e fundo `bg-accent`.
- `hoje`: anel/contorno distinto do selecionado (o Google marca os dois de
  formas diferentes); quando `hoje` é `null`, nenhuma célula recebe a marca.
- Dia com `conflito`: os pontinhos ganham um contorno de perigo E o
  `aria-label` diz "com conflito" — cor sozinha não basta.
- `aria-label` de cada célula, em pt-BR, carregando dia + total + nomes:
  `"17 de setembro, 3 visitas: Ana Silva, João Lima, Sem técnico"`, ou
  `"18 de setembro, sem visitas"`, e sufixo `", com conflito"` quando houver.
  Fora do mês, prefixe `"fora do mês, "`.
- Alvos com `min-h-[44px]`. Pontinhos são `aria-hidden` (o label já os
  descreve).

Testes: renderiza 42 células; célula fora do mês tem o prefixo no label e
continua clicável (dispara `onSelecionar`); `aria-pressed` só no selecionado;
dia com 6 técnicos mostra `+3` e 3 pontos; `aria-label` de dia vazio, de dia
com conflito, e de dia com visita sem técnico (o nome "Sem técnico" aparece);
`hoje === null` não marca ninguém.

## Task 3 — `_VistaMes.tsx` + integração na `page.tsx`

A `page.tsx` já tem 303 linhas e dois modos; o terceiro não pode entrar como
ternário triplo embutido.

### 3a. Store

`pwa/lib/store/tecnicoSettings.ts`: `ModoAgenda` passa a
`'lista' | 'semana' | 'mes'`. Conferir se o `persist` do zustand precisa de
`migrate`/validação para um valor gravado desconhecido — se um valor antigo
inválido puder vazar para o estado, sanear no `merge`.

### 3b. Colapsar os branches de modo

Hoje a `page.tsx` tem `semana ? ... : ...` em vários pontos (filtro "Só
minhas" desabilitado, `useTecnicoOptions(semana)`, `useAgenda(..., semana ?
false : filterMine, ...)`, textos do rótulo). Introduza

```ts
const visaoEquipe = modoAgenda !== 'lista'   // semana e mês são visão de equipe
```

e use `visaoEquipe` em TODOS esses pontos, em vez de acrescentar `|| mes` em
cada um (é exatamente aí que um dos sítios fica para trás). No mês, como na
semana: "Só minhas" desligado e desabilitado, `onlyMine=false` no fetch.

### 3c. Janela e navegação

- Novo estado `ancoraMes: string | null` — o **1º dia do mês visível**,
  separado do `inicio` que ancora lista/semana (misturar as duas semânticas no
  mesmo estado é como o mês vira "14 dias a partir de").
- Fetch no modo mês: `date_from = grade[0]`, `date_to = grade[41]` (42 dias,
  bem abaixo do teto de 92 do servidor).
- Setas ◀ ▶ no modo mês: `setAncoraMes(deslocarMes(ancoraMes, ±1))` — um mês
  de calendário, **não** ±N dias.
- Cabeçalho no modo mês: `rotuloMes(ancoraMes)` ("setembro de 2026"). Não usar
  `date_from – date_to` do payload, que leria "dom 30 ago – sáb 10 out".
- Primeira carga do mês: `ancoraMes` nasce `null`; sem ele não há faixa para
  pedir. Enquanto `ancoraMes` for `null`, o fetch sai sem datas (o servidor
  aplica a janela padrão e devolve `server_today`); um `useEffect` ancora
  `ancoraMes = primeiroDiaDoMes(data.server_today)` assim que o payload chega,
  e a segunda busca traz a grade completa. Enquanto isso, **não** renderizar a
  grade meio vazia: mostrar o `LoadingState`. Duas buscas na primeira abertura
  é o preço aceito.

### 3d. `_VistaMes.tsx`

Componente que recebe o que já foi calculado na página e monta: `GradeMes` +
legenda + `VisitaCard`s do dia selecionado.

```tsx
export function VistaMes({
  visitas, dias /* PontosDia[] */, ancora, hoje,
  diaSel, onSelecionarDia,
  roster,                    // Opcao[] para a legenda
  podeAjustar,               // data.can_manage
  emAjuste, onAjustar, onAlternarAjuste,
  erroAjuste,
  onSelecionarVisita,        // abre a VisitaSheet
}: {...})
```

- Legenda abaixo da grade: um chip por técnico **presente na janela** (não o
  roster inteiro — 20 chips de gente sem visita é ruído), com o ponto da cor
  de `corDoTecnico` e o nome; inclui "Sem técnico" quando houver visita sem
  técnico no mês.
- Abaixo, os `VisitaCard` do dia selecionado, com `onAjustar` só quando
  `podeAjustar` — mesma forma do modo Semana; dia vazio mostra
  "Nenhuma visita neste dia."
- Tocar num dia da grade com visita em ajuste chama `onAjustar({ date })`;
  sem visita em ajuste, chama `onSelecionarDia`. Depois de mover, a seleção
  segue a visita (`setDiaSel(vals.date)`) — a `page.tsx` já faz isso dentro de
  `ajustar`; se o dia destino estiver fora do mês visível, **também** avance
  `ancoraMes` para o mês do destino, senão o card sai da grade e a seleção
  fica presa.
- A rede de segurança que já existe (`useEffect` que encerra o ajuste quando a
  visita some do payload ou perde `editable`) vale igual no mês — não
  duplicar, deve continuar na `page.tsx` e cobrir os dois modos.

### 3e. Toggle

O seletor de modo passa a ter três botões: `Lista | Semana | Mês`.

### Testes (em `__tests__/ModoMes.test.tsx`)

Mesmo estilo de `ModoSemana.test.tsx` (mockar os hooks de `@/lib/hooks/useAgenda`):

- Selecionar "Mês" renderiza a grade e o cabeçalho com o nome do mês.
- ▶ avança um mês de calendário: o cabeçalho muda de "setembro de 2026" para
  "outubro de 2026" e o fetch é chamado com a faixa da grade de outubro.
- "Só minhas" aparece desabilitado no modo mês e o fetch recebe
  `onlyMine=false`.
- Tocar num dia lista as visitas daquele dia; tocar num dia vazio mostra
  "Nenhuma visita neste dia."
- Gestor: selecionar visita para ajuste + tocar outro dia chama
  `pwa_visita_update` com o `date` do destino.
- Mover para célula **fora do mês** (acinzentada) grava e a vista acompanha o
  destino (a âncora avança para o mês do destino).
- Não-gestor (`can_manage: false`) não vê o gesto de ajuste.

## Task 4 — Validação no navegador (o controlador faz, não subagente)

Depois das tasks 1-3 verdes: `devserver list`, subir o PWA em :3010 a partir
de `pwa/`, aquecer as rotas com curl e validar via `agent-browser`:
navegar entre meses (incluindo virada de ano), mover visita para célula
acinzentada, visita sem técnico, mês sem nenhuma visita, tema claro e escuro.

## Limite conhecido (fora de escopo)

`_PWA_FETCH_LIMIT = 500` no servidor, sem paginação, ordenado por
`date, time_start, id`: 42 dias da equipe inteira podem estourar o limite, e o
corte cai silenciosamente no **fim do mês** (últimos dias sem pontos). O modo
Semana nunca chegava perto. Tratar isso exige mudança de backend e não entra
nesta feature — fica registrado aqui e é reportado ao usuário na entrega.
