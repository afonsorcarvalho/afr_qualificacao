# PWA Técnico — Layout desktop

**Data:** 2026-09-04
**Módulo:** `afr_qualificacao` / `pwa`
**Status:** aprovado (brainstorming), pendente de plano de implementação

## Problema

A casca do app (`pwa/app/tecnico/qualificacao/layout.tsx`) tem
`max-w-[480px]` fixo. Em notebook o conteúdo fica espremido numa coluna
estreita no meio da tela, com o resto vazio. O dono do produto relatou em
2026-09-04 que o técnico nem sempre está em campo: às vezes revisa a OS pelo
notebook.

Todas as telas verificadas até hoje foram em 390×844 / 390×900. Nenhuma passada
foi feita em resolução de desktop.

Isto contradiz o que os documentos de design dizem hoje — `PRODUCT.md`
princípio 6 ("Uma mão, retrato, luva") e `DESIGN.md` ("Coluna única, sempre;
retrato de celular é o caso de projeto"). Os dois textos precisam ser
reescritos na mesma passada, senão a regra volta a proibir o que se quer fazer.

## Decisões tomadas

1. **Desktop ganha um segundo painel** (lista + detalhe lado a lado), não só
   uma coluna mais larga.
2. **O par lista+detalhe existe só dentro da OS.** Home, Histórico, Perfil e
   Finalizar turno ficam em coluna larga centrada.
3. **A navegação vira lateral esquerda em `≥1024px`.** Barra inferior continua
   em celular e tablet.
4. **A montagem é por casca compartilhada nas duas rotas** — sem parallel
   routes, sem intercepting routes, sem estado de seleção no client.

### Por que casca compartilhada e não parallel/intercepting routes

Clicar numa coleta continua sendo navegação de rota real. Isso preserva sem
exceção: URL correta, deep link, botão voltar, `Escape` = `router.back()`,
`PendingLink` e `NavProgressBar`. A alternativa idiomática do App Router
(`@detalhe` + `(.)coleta/[itemId]`) exigiria redefinir o `Escape` para "fecha
painel", dar tratamento próprio de "toque reconhecido" ao painel (DESIGN.md §5)
e manter uma rota não-interceptada em paralelo para o modo celular.

Não há custo de rede: `[osId]/page.tsx` e `[osId]/coleta/[itemId]/page.tsx` já
usam `useOsDetail`, então a lista à esquerda é servida do cache do React Query.

## Arquitetura

### Grade e breakpoints

Breakpoints padrão do Tailwind (`sm` 640, `lg` 1024).

| Faixa | Casca | Conteúdo |
|---|---|---|
| `<640` celular | igual hoje | `max-w-[480px]`, barra inferior |
| `640–1023` tablet | coluna única | `max-w-[720px]`, barra inferior |
| `≥1024` desktop | sidebar 200px + área de conteúdo | dentro da OS: grid `minmax(320px,380px) 1fr`, total `max-w-[1440px]`; fora da OS: coluna `max-w-[880px]` |

### Componentes novos

- **`_components/SplitPane.tsx`** — recebe `list` e `children`. Em `≥1024px`
  renderiza os dois em grid de duas colunas. Abaixo de `1024px` renderiza um
  lado só, escolhido pela prop `narrow`: `'list'` em `/[osId]` (o estado vazio
  do painel não aparece em celular) e `'detail'` na rota da coleta (a lista não
  aparece acima do formulário). Assim o comportamento em celular fica idêntico
  ao de hoje. A coluna da esquerda rola sozinha (`lg:sticky` sob o header +
  `overflow-auto`); a direita rola com a página.
- **`_components/ColetaList.tsx`** — extraído de `[osId]/page.tsx`. Mantém o
  agrupamento por equipamento, a separação pendentes/feitas e a etiqueta de
  tipo condicional (`mostrarTipo`). Recebe `selectedId` opcional.
- **Estado vazio do painel** — em `/[osId]` sem item selecionado, o lado
  direito mostra "Escolha uma coleta" em vez de área em branco.

### Rotas depois da mudança

```
/[osId]                  → SplitPane: ColetaList | estado vazio
/[osId]/coleta/[itemId]  → SplitPane: ColetaList(selectedId) | formulário
/                        → coluna larga centrada
/historico               → coluna larga centrada
/perfil                  → coluna larga centrada
/[osId]/relatorio/[relId]/finalizar → coluna larga centrada
```

### Navegação lateral (`lg:`)

A barra inferior é escondida em `lg` e substituída por coluna fixa à esquerda:
título + ícone no topo, os três destinos empilhados, item com altura mínima de
44px, `aria-current` no ativo, e o mesmo tratamento de espera de hoje
(`useTransition` + spinner no item + `NavProgressBar`). Sem a sombra
"Sobreposto" — a sidebar não flutua sobre conteúdo rolável; separação é fio de
1px, conforme a Regra do Fio. O header do app deixa de cobrir a largura toda e
passa a ser a faixa superior da área de conteúdo.

### Item selecionado na lista

A linha da coleta aberta é marcada com fio + `aria-current="true"` e não apenas
com cor de fundo — a Regra do Par vale aqui como em qualquer estado.

### Densidade

O espaço ganho vai para **mais linhas visíveis e mais meta por linha**
(equipamento, ciclo, tipo), nunca para encolher controle: alvos de toque
continuam ≥44px, porque notebook com tela sensível existe. Nada de aba, tabela
larga ou toolbar — é exatamente a anti-referência "tela de ERP / backoffice
Odoo" nomeada nos dois documentos.

## Reescrita dos documentos de design

Feita na mesma passada, senão a regra escrita proíbe o que foi aprovado.

**`PRODUCT.md`, princípio 6** ("Uma mão, retrato, luva"): celular em retrato
continua sendo o caso de projeto e o piso de qualidade. Desktop é o mesmo app
mais largo, mais um painel de detalhe no máximo — não é uma segunda
arquitetura de informação. A frase "Se algo só funciona em tablet deitado, não
funciona" continua valendo como está: nada pode existir só no desktop.

**`DESIGN.md`:**
- Overview / Key Characteristics: "Coluna única, sempre" → "a coluna é a
  unidade de leitura; em `≥1024px` a tela pode exibir duas — lista e detalhe —
  e nada além disso".
- §5 Navigation: descreve hoje só a barra inferior de 56px com sombra
  Sobreposto. Passa a descrever as duas variantes, dizendo em que faixa cada
  uma vale.
- Regra nova, junto do anti-ERP: **o espaço extra do desktop compra linha e
  meta, não aba, tabela nem toolbar.**

## Verificação

- **Baseline de testes não regride**: 11 arquivos / 38 testes do front
  (`pwa/docs/BASELINE.md` — sem falhas ambientais, qualquer falha é regressão).
- **Testes novos** para `ColetaList` (agrupamento, separação pendente/feita,
  `selectedId` marcando a linha) e `SplitPane` (renderiza os dois lados no modo
  largo, um só no estreito — com `matchMedia` mockado no jsdom).
- **Passada visual** com `agent-browser viewport <w> <h>` em 390×844,
  1280×800 e 1920×1080, nas sete telas.
- **Assinatura com mouse**: `react-signature-canvas` (sobre `signature_pad`) já
  usa pointer events, então mouse e trackpad funcionam por construção — a
  verificação é visual, não é código a escrever.
- **Pré-requisito de ambiente**: o Odoo :8084 estava fora em 2026-09-04
  (`curl` sem resposta). Subir o container antes da passada visual. Dado
  semeado: OS26-06-0002 (id 4, `in_progress`, 24 coletas pendentes) no db
  `qualificacao-dev`, PWA em :3010.

## Fora de escopo

- **Bloco de comemoração em `[osId]/page.tsx` (linhas ~106-120)**: gradiente
  esmeralda, `animate-pulse`, blur e 🎉🏆🎊. Viola os Don'ts do `DESIGN.md`
  (gradiente decorativo, emoji como ícone de interface, glow em loop) e o
  "a tela não comemora, informa" do `PRODUCT.md` — o que também significa que
  o item "Limpeza de neon. **Feita em 2026-09-03**" do `TODO.md` está
  incorreto. Fica registrado no TODO como item próprio.
- Auditoria de contraste tela a tela (já pendente no TODO).
- Painel de detalhe para a tela de fechar turno — foi considerado e recusado
  nesta passada.
