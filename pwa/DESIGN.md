---
name: PWA Técnico de Campo — Qualificação
description: Prancheta digital do técnico de qualificação, usada de uma mão só dentro do CME.
colors:
  base: "#030712"
  surface: "#0a0f1e"
  surface-raised: "#0d1424"
  ink: "#ffffff"
  ink-muted: "#a3adc2"
  ink-faint: "#6b7689"
  line: "#1b2334"
  action: "#f8fafc"
  action-ink: "#0a0f1e"
  state-done: "#34d399"
  state-pending: "#fbbf24"
  state-error: "#f87171"
  focus: "#22d3ee"
  light-base: "#f8fafc"
  light-surface: "#ffffff"
  light-ink: "#1e293b"
  light-ink-muted: "#475569"
  light-line: "#e2e8f0"
typography:
  metric:
    fontFamily: "Geist Sans, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
  title:
    fontFamily: "Geist Sans, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.3
  row:
    fontFamily: "Geist Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Geist Sans, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  meta:
    fontFamily: "Geist Sans, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.4
  stamp:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "tnum"
rounded:
  sm: "6px"
  md: "8px"
  pill: "9999px"
spacing:
  tight: "8px"
  row: "12px"
  block: "16px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.action-ink}"
    rounded: "{rounded.md}"
    padding: "12px 20px"
    height: "48px"
    typography: "{typography.body}"
  button-primary-hover:
    backgroundColor: "#e2e8f0"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "44px"
  button-destructive:
    backgroundColor: "{colors.state-error}"
    textColor: "{colors.base}"
    rounded: "{rounded.md}"
    padding: "12px 20px"
    height: "48px"
  task-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "64px"
  badge-done:
    backgroundColor: "#0e2b22"
    textColor: "{colors.state-done}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
    typography: "{typography.meta}"
  badge-pending:
    backgroundColor: "#2b220e"
    textColor: "{colors.state-pending}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
    typography: "{typography.meta}"
  input-field:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px"
    height: "48px"
---

# Design System: PWA Técnico de Campo

## 1. Overview

**Creative North Star: "A Prancheta"**

O app é a prancheta de checklist que o técnico levaria pro CME, se prancheta
soubesse a hora certa e não deixasse foto solta. Tudo o que ele precisa saber
cabe numa coluna: o que falta fazer, o que já foi feito, e onde ele está no
turno. A tela não é um painel de controle nem um relatório — é uma lista de
tarefas com estado, lida em pé, com uma mão, sob luz artificial de hospital.

Densidade é a favor da lista: linhas próximas, altura previsível, o nome da
coleta como âncora. O que não ajuda a decidir "qual é a próxima" desce um
nível de hierarquia ou sai. A cor não decora: ela só diz estado — verde é
feito, âmbar é pendente, vermelho é erro. Fora isso o sistema é neutro escuro.

Isto rejeita explicitamente duas coisas que o PRODUCT.md nomeia: **tela de ERP
/ backoffice Odoo** (formulário denso, abas, tabela) e **landing SaaS genérica**
(grade de cards iguais, hierarquia decorativa). E rejeita o passado do próprio
código: o tema "cyber/neon" com roxo, rosa, gradiente e glow nasceu como
enfeite e sai de cena — o escuro fica, o brilho não.

**Key Characteristics:**
- Coluna única, sempre; retrato de celular é o caso de projeto, não o degradado.
- Cor exclusivamente semântica (feito / pendente / erro).
- Neutro escuro de base, herdado do código atual (#030712 → #0d1424).
- Números tabulares em qualquer contagem, progresso ou carimbo de hora.
- Alvo de toque nunca abaixo de 44px.
- Tipografia única (Geist) em pesos; mono só para carimbos de data/hora.

## 2. Colors

Neutro escuro quase sem croma, com três cores de estado que só aparecem
quando comunicam alguma coisa.

### Primary
- **Papel Invertido** (#f8fafc): a cor da ação principal. O botão que conclui
  (Salvar coleta, Fechar relatório) é claro sobre fundo escuro — chama por
  contraste, não por matiz, e por isso não compete com as cores de estado.

### Secondary
- **Verde Concluído** (#34d399): item coletado, progresso realizado, turno
  fechado. Nunca usado como cor de marca ou de fundo decorativo.
- **Âmbar Pendente** (#fbbf24): o que ainda falta — coleta pendente, turno em
  aberto. Sempre acompanhado de texto; âmbar sozinho não é mensagem.
- **Vermelho Falha** (#f87171): erro de gravação, item recusado pelo servidor,
  ação destrutiva.

### Tertiary
- **Ciano Foco** (#22d3ee): exclusivamente o anel de foco de teclado e o
  indicador de campo ativo. É o único resto do neon antigo, mantido porque
  foco precisa ser inconfundível e nenhuma cor de estado pode ser gasta nisso.

### Neutral
- **Preto Bancada** (#030712): fundo do app.
- **Superfície** (#0a0f1e): linha de tarefa, bloco de conteúdo.
- **Superfície Elevada** (#0d1424): campo de entrada, área destacada dentro de
  um bloco.
- **Tinta** (#ffffff): texto primário — nome da coleta, número, título.
- **Tinta Fraca** (#a3adc2): texto secundário — cliente, ciclo, legenda.
  Passa 4.5:1 sobre superfície; é o piso do texto legível.
- **Tinta Apagada** (#6b7689): apenas ícone desativado e separador textual.
  **Proibido em texto que o técnico precisa ler.**
- **Fio** (#1b2334): borda e divisória. 1px, sempre.

O tema claro espelha os mesmos papéis (#f8fafc base, #ffffff superfície,
#1e293b tinta, #475569 tinta fraca, #e2e8f0 fio) e existe pro dia em que o
técnico trabalhar sob luz forte; hoje o escuro é o default.

### Named Rules

**A Regra do Estado.** Cor só entra quando responde "em que pé está isto?".
Verde, âmbar e vermelho são vocabulário fechado. Roxo, rosa, gradiente de
marca e glow estão **proibidos** — não existe estado que eles nomeiem.

**A Regra do Par.** Nenhum estado é comunicado só por cor: verde vem com
"coletada" ou ícone de check, âmbar com "pendente", vermelho com a frase do
erro. Se apagar a cor, a informação continua lá.

## 3. Typography

**Display / Body Font:** Geist Sans (fallback system-ui, sans-serif)
**Stamp Font:** Geist Mono (fallback ui-monospace, monospace)

**Character:** uma família só, resolvida em pesos. Geist é uma grotesca neutra
de leitura rápida em tela pequena — não tem personalidade a declarar, o que é
exatamente o que um instrumento precisa. O mono aparece só onde número tem que
alinhar: hora, duração, contadores.

### Hierarchy
- **Metric** (600, 30px/1, `tnum`): o número que a tela existe pra dar — quantas
  coletas neste turno, quanto tempo de execução. Um por tela, no máximo.
- **Title** (600, 18px/1.3): título da tela ("Finalizar relatório #1975").
- **Row** (600, 16px/1.4): nome da coleta na lista. É a âncora de leitura; nada
  na linha pode competir com ele.
- **Body** (400, 14px/1.5): texto corrente, rótulo de campo, descrição.
- **Meta** (400, 12px/1.4): cliente, ciclo, contexto secundário da linha.
- **Stamp** (mono, 400, 12px, `tnum`): data, hora e duração carimbadas pelo
  servidor.

### Named Rules

**A Regra do Número Tabular.** Toda contagem, progresso, duração ou horário usa
`tabular-nums`. Números que dançam ao atualizar fazem o técnico reler.

**A Regra da Âncora.** Numa lista de 18 coletas, o nome do item é o único
elemento em peso 600 na linha. Chip, ícone e legenda ficam em Meta.

## 4. Elevation

Sistema **tonal, não sombreado**. Profundidade vem da escada de fundo
(#030712 → #0a0f1e → #0d1424) mais um fio de 1px (#1b2334), nunca de sombra
projetada. Um app de lista lida em tela pequena não tem espaço pra penumbra: a
sombra só embaça a borda e come contraste.

Sombra existe em exatamente um caso: elemento que flutua sobre o conteúdo
(barra inferior de navegação, modal, toast), onde ela sinaliza "isto está por
cima", não "isto é bonito".

### Shadow Vocabulary
- **Sobreposto** (`box-shadow: 0 -8px 24px rgba(0,0,0,0.45)`): barra fixa e
  modal sobre conteúdo rolável.

### Named Rules

**A Regra do Fio.** Separação é 1px de #1b2334. `border-left` colorido com mais
de 1px como acento — a "faixa lateral" — está **proibido**; era o padrão do
cartão de resumo antigo e sai onde aparecer.

**A Regra do Vidro Aposentado.** As utilidades `glass` / `backdrop-filter` do
tema antigo não são mais o default de superfície. Vidro só se houver conteúdo
real rolando por baixo (barra fixa), nunca como textura de cartão.

## 5. Components

### Buttons
- **Shape:** cantos suaves (8px), largura total em ação principal de tela.
- **Primary:** Papel Invertido (#f8fafc) com tinta escura (#0a0f1e), altura
  48px, padding 12px 20px. É a ação que conclui: Salvar coleta, Fechar
  relatório, Entrar.
- **Ghost:** transparente, texto em Tinta Fraca, altura 44px. Navegação e ações
  reversíveis (Voltar, Pular, Cancelar, Limpar).
- **Destructive:** Vermelho Falha com tinta escura. Só para perda de trabalho.
- **Hover / Focus:** hover escurece o primário um passo (#e2e8f0); foco de
  teclado é anel de 2px em Ciano Foco com 2px de offset. Transição de 150ms
  em `background-color` apenas.
- **Altura mínima 44px em qualquer variante**, inclusive ícone.

### Chips
- **Style:** pílula (9999px), fundo do próprio matiz a ~12% e texto na cor de
  estado; sem borda luminosa, sem `box-shadow`.
- **State:** `badge-done` (verde) para coletado, `badge-pending` (âmbar) para
  pendente. O texto do chip nomeia o estado — nunca só a cor.

### Cards / Containers
O componente central não é cartão, é **linha de tarefa** (`task-row`): fundo
Superfície, 8px de raio, padding 12px 16px, altura mínima 64px, fio de 1px.
Ícone de tipo à esquerda, nome ancorado, estado à direita, seta de avanço.

- **Cartão aninhado está proibido.** O bloco "Qualificador / padrão cadastrado"
  dentro da linha de coleta vira texto Meta na própria linha; se estiver vazio,
  não é renderizado.
- Padding interno: 16px em bloco, 12px em linha.
- Sem sombra (ver Elevation).

### Inputs / Fields
- **Style:** fundo Superfície Elevada, fio de 1px, 8px de raio, altura mínima
  48px, texto 14px. Rótulo sempre visível acima do campo — placeholder não é
  rótulo.
- **Focus:** fio passa a Ciano Foco + anel de 2px; sem glow.
- **Error:** fio em Vermelho Falha e a mensagem **abaixo do campo**, em texto,
  dizendo o que fazer.

### Navigation
Barra fixa inferior com três destinos (OSs, Histórico, Perfil), altura 56px,
alvo de 44px por item, sombra Sobreposto. Item ativo em Tinta + ícone
preenchido; inativo em Tinta Fraca. **Ícone é SVG de traço, nunca emoji** — o
emoji atual (📋 📊 👤) é de app de consumo e sai.

### Signature Pad (componente de assinatura)
Área branca de 160px de altura, raio 8px, fio de 1px, com o botão "Limpar" em
ghost logo abaixo. É a única superfície branca permitida no tema escuro:
assinatura é documento, e documento é sobre papel.

## 6. Do's and Don'ts

### Do:
- **Do** usar cor apenas para estado: #34d399 feito, #fbbf24 pendente,
  #f87171 erro.
- **Do** manter todo alvo de toque com no mínimo 44px de altura — o técnico
  usa de luva.
- **Do** garantir 4.5:1 em qualquer texto que precise ser lido; Tinta Fraca
  (#a3adc2) é o limite inferior, Tinta Apagada (#6b7689) nunca é texto.
- **Do** usar `tabular-nums` em contador, progresso, duração e hora.
- **Do** escrever erro como instrução em pt-BR ("Anexe o arquivo antes de
  salvar"), dizendo se o trabalho foi perdido.
- **Do** deixar o servidor carimbar data e hora; a tela exibe, não calcula.
- **Do** respeitar `prefers-reduced-motion`: transição vira corte.

### Don't:
- **Don't** parecer **tela de ERP / backoffice Odoo**: nada de aba, tabela
  larga ou formulário de 20 campos numa tela de campo.
- **Don't** parecer **landing SaaS genérica**: grade de cartões idênticos com
  ícone + título + texto é o anti-padrão nomeado no PRODUCT.md.
- **Don't** usar roxo (#a855f7), rosa (#ec4899), `bg-gradient-cyber`,
  `shadow-glow-*` ou `animate-pulse-glow` — todo o vocabulário neon decorativo
  está aposentado.
- **Don't** aninhar cartão dentro de cartão. Nunca.
- **Don't** usar `border-left` colorido acima de 1px como acento.
- **Don't** usar emoji como ícone de interface.
- **Don't** comunicar estado só por cor, sem texto ou ícone.
- **Don't** usar `glass` / `backdrop-filter` como textura de superfície parada.
- **Don't** escrever classe utilitária que não exista no projeto. Os papéis
  semânticos (`bg-card`, `text-muted-foreground`, `border-border`,
  `bg-primary`, `bg-muted`) passaram a existir em 2026-09-03 — antes disso
  geravam zero CSS e o botão primário ficava sem fundo. Token novo entra em
  `app/globals.css` **e** no mapa de `tailwind.config.ts`, nunca só num deles.
- **Don't** gatilhar a visibilidade do conteúdo numa animação de entrada
  (`initial={{ opacity: 0 }}` ou `scale: 0` no framer-motion). Se a animação
  não roda — aba em segundo plano, PWA retomado do standby, renderizador
  headless — a tela fica em branco com o conteúdo no DOM. Entrada é
  deslocamento sobre conteúdo já visível.
