# Plano — Isolar um técnico/instrumento com toque longo

Data: 2026-09-18
Branch: `feat/agenda-instrumentos-mes` (submodule `addons/afr_qualificacao`), a
mesma dos blocos anteriores, ainda não mergeada.
Escopo: **somente frontend** em `pwa/`. Nenhuma mudança em Python.

## Contexto

As duas faixas de legenda do modo Mês ("Técnicos:" e "Instrumentos:") são
badges de filtro: toque liga/desliga, e o badge "Todos" limpa a restrição da
faixa. O problema relatado pelo usuário: **para ver só UM recurso é preciso
desligar todos os outros, um a um** — inviável quando a equipe ou o catálogo
crescem.

Decisão tomada com o usuário: **toque longo isola**; o toque simples continua
alternando, para que "ver tudo menos o Fulano" siga custando um toque.

Código de hoje:
- `pwa/app/tecnico/qualificacao/agenda/_VistaMes.tsx` — componente local
  `FaixaLegenda<T extends number | false>`, com `role="group"` +
  `aria-labelledby`, o badge "Todos" (`aria-label` "Todos os técnicos" /
  "Todos os instrumentos") e um botão por recurso com `aria-pressed`. Estado
  ligado: `border-transparent bg-accent font-semibold text-foreground`;
  desligado: `border-dashed border-border text-muted-foreground`, com a marca
  (bolinha/triângulo) em contorno.
- `pwa/app/tecnico/qualificacao/agenda/page.tsx` — `tecnicosSel: Set<number|false> | null`
  e `instrumentosSel: Set<number> | null` (`null` = "Todos"), em memória,
  zerados ao trocar de modo. `visitasVisiveis` aplica a interseção das duas
  faixas e alimenta **apenas** as marcas da grade.

## Global Constraints

1. **Nenhuma mudança em arquivo Python, nem bump de `__manifest__.py`.**
2. **Nunca ler o relógio do aparelho:** `Date.UTC`/ISO/`Intl` com
   `timeZone:'UTC'`; o "hoje" vem de `data.server_today`.
3. **Sem dependência nova.** Nada de biblioteca de gestos — pointer events
   nativos.
4. **Acessibilidade:** alvos de toque `min-h-[44px]`; cor nunca é o único
   portador; **todo gesto tem equivalente alcançável por teclado**.
5. **UI em pt-BR**; comentários em pt-BR explicando o PORQUÊ.
6. **Testes:** `npm run test` e `npx tsc --noEmit` a partir de `pwa/`. Baseline
   **449 testes verdes** — qualquer falha é regressão.
7. **TDD:** teste que falha primeiro.
8. Dev server em `:3010` a partir de `pwa/`: não derrubar, não subir outro, não
   rodar `npm run build`.

## Task 1 — O gesto de isolar

### Comportamento

- **Toque longo (~500ms) num chip:** a faixa passa a ter só aquele recurso
  ligado (`Set` com um único id). Vale para as duas faixas.
- **Toque longo num chip que já é o único ligado:** volta para "Todos"
  (`null`) — o gesto é reversível por si mesmo, sem obrigar a caçar o badge
  "Todos".
- **Toque simples:** continua ligando/desligando aquele recurso, exatamente
  como hoje. Um toque longo NÃO pode disparar também o toque simples.
- **Arrastar cancela:** a faixa quebra em várias linhas e rola no celular; se o
  ponteiro se mover além de um limiar pequeno (~10px) antes dos 500ms, não
  isola e não alterna — foi rolagem, não toque.
- **Equivalente de teclado:** `Alt+Enter`, `Alt+Espaço` e `Alt+clique` isolam.
  É o que torna o gesto alcançável por quem navega por teclado ou leitor de
  tela; sem isso o recurso não existe para essas pessoas.
- **Dica na tela:** uma linha curta, em texto apagado, dentro de cada faixa:
  `Segure um para ver só ele`. Sem isso o gesto é invisível.
- Cada chip anuncia o atalho para tecnologia assistiva (ex. `aria-keyshortcuts`
  e/ou o texto do `title`), em pt-BR.

### Implementação

- Pointer events (`onPointerDown`/`onPointerUp`/`onPointerCancel`/
  `onPointerMove`), que cobrem dedo e mouse com um caminho só. Guarde o
  timer e a posição inicial por chip; limpe o timer em TODOS os caminhos de
  saída, inclusive desmontagem — timer solto disparando depois que a faixa
  mudou é a armadilha clássica aqui.
- Suprima o menu de contexto e a seleção de texto que o toque longo dispara no
  mobile (`onContextMenu` + `select-none`/`touch-action`), senão o gesto
  concorre com o comportamento nativo do navegador.
- A ação de isolar mora em `page.tsx` (é ela que detém os dois `Set`); a
  `FaixaLegenda` recebe um `onIsolar(id)` além do `onAlternar(id)` que já tem.
- Não mexa na regra de interseção, no alcance do filtro (só as marcas da
  grade), no reset ao trocar de modo, nem nas escotilhas de saída já
  existentes (faixa com restrição ativa continua renderizada mesmo sem itens;
  `semInstrumentoNaJanela` segue ignorando restrição que não tem o que
  filtrar).

### Testes (`__tests__/ModoMes.test.tsx`)

Use os eventos de ponteiro do `@testing-library` com timers falsos do vitest
para o limiar de 500ms.

- Toque longo num chip deixa só ele ligado: os demais ficam `aria-pressed=false`
  e as marcas da grade refletem isso.
- Toque longo no chip já isolado volta para "Todos" (`aria-pressed` do "Todos"
  volta a `true`).
- Toque simples continua alternando só aquele chip, sem isolar.
- Toque longo **não** dispara também o alternar (o chip isolado termina ligado,
  não desligado).
- Arrastar além do limiar antes dos 500ms não isola nem alterna.
- `Alt+Enter` (ou `Alt+clique`) isola, provando o caminho de teclado.
- A dica `Segure um para ver só ele` aparece nas duas faixas.
- Isolar na faixa de instrumentos não mexe na de técnicos (as faixas são
  independentes no gesto; a interseção continua sendo a regra de leitura).

## Task 2 — Validação no navegador (o controlador faz, não subagente)

PWA em `:3010` contra o Odoo de `qualificacao-dev` em `:8084`: toque longo com
mouse isolando, toque longo de novo voltando a "Todos", toque simples ainda
alternando, arrastar não isolando, a dica visível, tema claro e escuro,
viewport de 390px.
