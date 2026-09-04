# PWA Técnico — painel esquerdo persistente

**Data:** 2026-09-04
**Módulo:** `afr_qualificacao` / `pwa`
**Status:** aprovado (brainstorming), pendente de plano de implementação
**Antecessor:** `2026-09-04-pwa-tecnico-layout-desktop-design.md` (entregue)

## Problema

`SplitPane` e `ColetaList` são renderizados por **cada página** — `[osId]/page.tsx`
e `[osId]/coleta/[itemId]/page.tsx` — e não por um layout de segmento. O Next
desmonta e remonta a coluna esquerda a cada navegação.

Em `≥1024px` o painel da lista é o próprio container de rolagem, então ele
renasce com `scrollTop 0`. Numa OS com 24 coletas, rolar até o item 20 e clicar
nele joga a lista de volta ao topo: a linha marcada com `aria-current` some da
vista exatamente no momento em que deveria orientar o técnico.

Apontado pela revisão final do layout desktop e adiado de propósito, com o custo
dimensionado, em `pwa/TODO.md`.

## Decisões tomadas

### 1. O layout hoista a coluna esquerda inteira, não só a lista

Hoje a coluna esquerda de `/[osId]` carrega bem mais que a lista: botão Voltar,
identidade da OS, `RelatorioHeader`, `ReviewPanel`, bloco de conclusão,
`ColetaList` e o botão "Finalizar relatório do dia".

Hoistar só a lista obrigaria os outros blocos a migrar para o painel direito, e
no celular — onde só um lado aparece — a ordem da tela mudaria (o botão de
finalizar subiria para cima da lista). Por isso **o layout passa a ser o dono da
coluna esquerda inteira**, junto com o `useOsDetail` e os handlers que ela usa.

Consequências:
- `[osId]/page.tsx` fica com `<EmptyDetail/>` e nada mais.
- A rota da coleta fica só com o formulário.
- No celular nada muda: `narrow="list"` em `/[osId]` mostra a mesma coluna, na
  mesma ordem; `narrow="detail"` na coleta mostra só o formulário.
- No desktop, o painel esquerdo passa a manter `RelatorioHeader` e o botão de
  finalizar visíveis enquanto o técnico preenche uma coleta. Isso é ganho, não
  duplicação: é a mesma instância, que agora sobrevive à navegação.

### 2. Route group `(painel)`, não um `[osId]/layout.tsx` cru

Um layout direto em `[osId]/` envolveria também `relatorio/[relId]` e
`relatorio/[relId]/finalizar`, que pelo spec anterior são coluna larga centrada,
sem lista ao lado.

Estrutura final (as URLs não mudam — route group não vira segmento de caminho):

```
[osId]/(painel)/layout.tsx              ← SplitPane + coluna esquerda + dados
[osId]/(painel)/page.tsx                ← <EmptyDetail/>
[osId]/(painel)/coleta/[itemId]/page.tsx ← formulário da coleta
[osId]/relatorio/[relId]/page.tsx        ← FORA do grupo, inalterado
[osId]/relatorio/[relId]/finalizar/page.tsx ← FORA do grupo, inalterado
```

### 3. `selectedId` sai do `usePathname()`, nunca do `useParams()`

Dentro de `(painel)/layout.tsx` o segmento `itemId` está **abaixo** do layout,
então `useParams()` devolve só `{ osId }`. Ler `itemId` dali daria `undefined`
em silêncio e o marcador `aria-current` pararia de funcionar — justamente o que
este refactor existe para manter na tela.

O layout extrai o id do pathname (`/tecnico/qualificacao/<osId>/coleta/<itemId>`)
e passa `selectedId` ao `ColetaList`.

### 4. Carregando e erro ficam DENTRO do `SplitPane`, com `{children}` montado

O layout **não** pode fazer early-return de `<LoadingState/>` ou da mensagem de
erro: isso apagaria o painel direito junto, refazendo os achados 2 e 7 da revisão
anterior (a coluna inteira piscando a cada clique, e 380px em branco enquanto a
OS carrega).

O layout sempre renderiza o `SplitPane`. O estado de carregamento e o de erro
ocupam o **painel da lista**; `{children}` continua montado no painel direito.

## Arquitetura

### `(painel)/layout.tsx` (novo)

Client Component. Passa a ser o dono de:
- `useOsDetail(id, userId)` e `useTecnicoSettings()`;
- `useStartDailyRelatorio()` e os handlers `handleStart`, `handleContinue`;
- `handleFinalize` com o `useTransition`;
- todo o JSX da coluna esquerda, sem alteração de markup ou de ordem.

`narrow` deixa de ser fixo por página: o layout decide pela rota — `'detail'`
quando o pathname tem `/coleta/`, `'list'` caso contrário.

### Import depth

Mover os arquivos muda a profundidade dos imports relativos. Valores exatos:

| Arquivo | Antes | Depois |
|---|---|---|
| `(painel)/page.tsx` | `../_components/X` | `../../_components/X` |
| `(painel)/coleta/[itemId]/page.tsx` | `../../../_components/X` | `../../../../_components/X` |

Imports por alias (`@/lib/...`, `@/components/...`) não mudam.

### Handlers que atravessam a fronteira do grupo

`handleFinalize` navega para `relatorio/[relId]/finalizar`, que está **fora** do
grupo: navegar para lá desmonta o layout. O `useTransition` (`finalizando`) vive
num componente que está sendo destruído. Funciona, mas o spinner precisa ser
conferido na passada visual.

Do mesmo modo, `isFetching && !isLoading` agora alimenta o `RelatorioHeader`
enquanto o técnico está na rota da coleta — conferir que não pisca no meio do
preenchimento.

## Testes

### Migração obrigatória de `__tests__/ColetaPage.test.tsx`

O arquivo importa `'../[osId]/coleta/[itemId]/page'`; o caminho passa a ser
`'../[osId]/(painel)/coleta/[itemId]/page'`.

Mais grave: duas das suas quatro asserções cobrem garantias que **mudam de
dono**. O achado 3 (identidade da OS acima da lista) e o achado 7 (estado de
espera no painel da lista) passam a vir do layout, não da página — renderizando
a página isolada, essas asserções falham.

Elas não podem simplesmente sumir: foram verificadas na onda de fix e são a
prova de dois defeitos reais. As duas migram para um teste novo do layout
(`__tests__/PainelLayout.test.tsx`), que renderiza o layout com um filho de
mentira. O teste da página guarda o que continua sendo dela: os achados 1
(salvar navega pra frente) e 2 (o painel da lista sobrevive ao carregamento da
coleta — agora asserido no layout com `{children}` em estado de espera).

### Testes novos

- **Persistência**: a coluna esquerda é a mesma instância entre as duas rotas
  (contador de montagem no layout, ou asserção de que o `useOsDetail` não
  refaz a montagem ao trocar `children`).
- **`selectedId` vem do pathname**: com `usePathname()` devolvendo
  `/tecnico/qualificacao/4/coleta/7`, a linha 7 sai com `aria-current="true"`.
- **`narrow` segue a rota**: `'detail'` com `/coleta/` no pathname, `'list'`
  sem ele.
- **`relatorio/` ficou de fora**: a rota de finalizar não renderiza `SplitPane`
  nem `ColetaList`.

### Baseline

17 arquivos / 80 testes verdes, `tsc` limpo, `npm run build` com 17 rotas.
Route group não altera a contagem de rotas — se o build mudar de 17, algo saiu
do lugar.

## Verificação

O critério de aceitação **não** é coberto por teste unitário:

- Em 1280×800, dentro da OS26-06-0002 (24 coletas): rolar a lista até por volta
  do item 20, clicar nele, e confirmar que o painel **não** pulou para o topo e
  que a linha marcada continua visível.
- Em 390×844, percorrer home → OS → coleta → salvar: tem que continuar
  idêntico. A afirmação central deste desenho, no celular, é "nada muda".
- Em 1280×800, abrir a tela de finalizar turno e confirmar que ela segue como
  coluna larga centrada, sem lista ao lado.
- Conferir o spinner do botão "Finalizar relatório do dia" ao sair do grupo.

## Risco que mata o desenho

A premissa inteira é que o Next preserva a instância do layout de segmento entre
`/[osId]` e `/[osId]/coleta/[itemId]`. É o comportamento documentado do App
Router, e o `layout.tsx` de `/tecnico/qualificacao` já depende disso hoje (busca
`session-info` "uma vez por montagem do layout").

Ainda assim, **a primeira task do plano é provar isso empiricamente** com um
layout-esqueleto e um contador de montagem, no servidor de dev. Se remontar, o
hoist não compra nada e o plano morre ali — cinco minutos em vez de seis tasks.

## Fora de escopo

- Bloco de comemoração com gradiente/emoji em `[osId]/page.tsx` (já no TODO).
- Auditoria de contraste tela a tela.
- Qualquer mudança nas rotas de `relatorio/`.
