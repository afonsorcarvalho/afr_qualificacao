# Plano — Barra de estado por dia na grade do Mês

Data: 2026-09-18
Branch: `fix/agenda-filtro-marca-instrumento` (submodule `addons/afr_qualificacao`),
a mesma dos dois consertos do filtro, ainda não mergeada.
Escopo: **somente frontend** em `pwa/`. Nenhuma mudança em Python.

## Contexto

A grade do modo Mês desenha, por célula: o número do dia, bolinhas por técnico,
triângulos por instrumento, o anel de "hoje" (`ring-primary`), o fundo sólido do
dia selecionado (`bg-primary`), o esmaecimento das células fora do mês e um
contorno de perigo nos pontinhos quando há conflito.

O usuário pediu um sinal de estado por dia, legível de relance: **dia com
visita**, **dia com conflito**, **dia vazio**.

## Decisões tomadas com o usuário (não reabrir)

- O sinal é uma **barra fina na base da célula**, largura total — não uma borda
  em volta (colidiria com o anel de "hoje") nem fundo tingido (competiria com os
  pontinhos, que são a identidade do técnico).
- **Dia vazio não ganha barra**: a ausência é o terceiro estado.
- **Conflito manda sobre visita**: dia com conflito é vermelho, não verde.
- Com filtro ativo:
  - **verde** = há visita **depois do filtro** (mesma fonte dos pontinhos, para
    barra e marcas nunca se contradizerem);
  - **vermelha** = há conflito **no dia inteiro**, ignorando o filtro — filtrar
    nunca pode esconder conflito.
- Consequência assumida: com filtro ativo, um dia pode ficar **sem pontinhos e
  com barra vermelha**. É o aviso de que há conflito no que foi filtrado fora.

## Global Constraints

1. **Nenhuma mudança em arquivo Python, nem bump de `__manifest__.py`.**
2. **Nunca ler o relógio do aparelho:** `Date.UTC`/`setUTCDate`, ISO
   `YYYY-MM-DD`, `Intl` sempre com `timeZone:'UTC'`; o "hoje" vem de
   `data.server_today`.
3. **Sem dependência nova.**
4. **Acessibilidade:** `min-h-[44px]` nos alvos; **cor nunca é o único
   portador** — a barra é decorativa e quem carrega o estado em texto é o
   `aria-label` da célula.
5. **UI em pt-BR**; comentários em pt-BR explicando o PORQUÊ.
6. **Testes:** `npm run test` e `npx tsc --noEmit` a partir de `pwa/`. Baseline
   **479 testes verdes** — qualquer falha é regressão.
7. **TDD:** teste que falha primeiro.
8. Dev server em `:3010` a partir de `pwa/`: não derrubar, não subir outro, não
   rodar `npm run build`.

## Task 1 — A barra e a fonte de conflito não filtrada

### 1a. Função pura

Em `app/tecnico/qualificacao/agenda/mes.ts`:

```ts
/** Datas (ISO) da janela em que ALGUMA visita está em conflito — sobre a
 *  lista NÃO filtrada, porque o filtro não pode esconder conflito. */
export function conflitosPorDia(
  visitas: VisitaAgenda[],
  dias: string[],
): Set<string>
```

Uma varredura O(nº de visitas), não 42 × visitas: percorra `visitas` uma vez,
some as datas com `v.conflict`, e devolva só as que estão em `dias`.

### 1b. A barra na célula

`_GradeMes.tsx` ganha a prop `conflitos: ReadonlySet<string>` (casada por
`date`, como `instrumentos` já é — nunca por posição).

Por célula, o estado sai de duas fontes distintas, de propósito:
- **conflito**: `conflitos.has(date)` (janela inteira, não filtrada);
- **tem visita**: o `total` do `PontosDia` daquele dia, que já chega filtrado.

Desenho: barra de 3px, largura total, na base da célula, abaixo das marcas,
`aria-hidden`. `--danger` quando há conflito; `--ok` quando há visita e não há
conflito; nada quando o dia está vazio. Célula fora do mês continua esmaecida,
mas a barra vale igual (o dia existe, só não é do mês visível).

**Contraste:** a barra precisa ser legível sobre os DOIS fundos de célula —
`--card` (normal) e `--primary` (dia selecionado) — nos dois temas. O projeto já
tem uma guarda desse tipo para a `PALETA` dos pontinhos em `mes.test.ts`;
estenda o mesmo método para `--ok` e `--danger` contra os quatro fundos
(card claro/escuro, primary claro/escuro). Se algum par não alcançar 3:1, NÃO
invente um token novo em silêncio: relate no relatório e proponha.

### 1c. `aria-label` acompanha a nova regra

Hoje o sufixo `", com conflito"` sai do conjunto **filtrado**. Com a barra
vermelha valendo para o dia inteiro, o sufixo passa a sair da mesma fonte não
filtrada — senão a barra teria cor sem equivalente textual, violando a
Constraint 4. O resto do rótulo (contagem, nomes, instrumentos, `", hoje"`,
prefixo `"fora do mês, "`) continua como está, filtrado.

### Testes

`__tests__/mes.test.ts`:
- `conflitosPorDia` devolve só as datas com alguma visita em conflito.
- Data com conflito fora da janela não entra.
- Dia sem visita não entra; lista vazia devolve conjunto vazio.
- A guarda de contraste de `--ok`/`--danger` contra os quatro fundos.

`__tests__/GradeMes.test.tsx`:
- Dia com visita e sem conflito: barra `--ok`.
- Dia com conflito: barra `--danger`, mesmo havendo visita.
- Dia vazio: nenhuma barra.
- Dia selecionado (fundo sólido) continua com a barra visível.
- A barra é `aria-hidden` e não entra na árvore de acessibilidade.

`__tests__/ModoMes.test.tsx`:
- Com filtro que esconde as visitas de um dia em conflito: o dia fica **sem
  pontinhos**, **com barra vermelha** e o `aria-label` **continua** dizendo
  `", com conflito"`.
- Com filtro que esconde as visitas de um dia SEM conflito: o dia perde a barra
  verde junto com os pontinhos.

## Task 2 — Validação no navegador (o controlador faz, não subagente)

PWA em `:3010` contra o Odoo de `qualificacao-dev` em `:8084`. O banco já tem
dados semeados para isso: 23/09/2026 com conflito de técnico E de instrumento,
18/09 com conflito de técnico, vários dias só com visita, e dias vazios.
Conferir os três estados, o dia selecionado, o tema claro e o escuro, e o caso
"filtro ativo + dia em conflito".
