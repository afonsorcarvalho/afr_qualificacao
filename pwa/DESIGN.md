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
- A coluna é a unidade de leitura. Retrato de celular é o caso de projeto,
  não o degradado; a partir de 1024px a tela pode exibir duas colunas — lista
  e detalhe — e nada além disso.
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

### A fonte da verdade é o token, não o hex

Os parágrafos acima nomeiam cores pelo hex do tema **escuro** porque foi nele
que o design nasceu — mas o hex não é o que o código consome. O código
consome os tokens HSL de `app/globals.css` (`--ok`, `--warn`, `--danger`,
`--info`, mais a superfície `-surface` de cada um), redeclarados em
`:root` (claro) e `:root.dark` (escuro). Até 2026-09-06 só o valor escuro
tinha sido revisado; o claro ficou de fora da auditoria de contraste — e foi
essa lacuna, não um bug de código, que deixou 397 ocorrências abaixo do piso
AA passarem sem ninguém notar. A tabela abaixo é a fonte da verdade dos dois
temas, com a razão de contraste medida (auditoria em
`docs/AUDITORIA-CONTRASTE.md`, script `npm run audit:contrast`):

| Token | Papel | Claro (HSL) | Claro sobre fundo/cartão | Escuro (HSL) | Escuro sobre fundo/cartão |
|---|---|---|---|---|---|
| `--foreground` | Tinta primária | `217 33% 17%` | 14.17 / 14.82 | `0 0% 100%` | 20.15 / 19.07 |
| `--muted-foreground` | Tinta Fraca | `215 19% 35%` | 7.13 / 7.46 | `221 20% 70%` | 8.94 / 8.46 |
| `--ok` | Verde Concluído | `163 88% 20%` | 7.25 / 7.58 | `158 64% 52%` | 10.49 / 9.93 |
| `--warn` | Âmbar Pendente | `23 83% 31%` | 6.82 / 7.14 | `43 96% 56%` | 11.90 / 11.27 |
| `--danger` | Vermelho Falha (estado) | `0 70% 35%` | 8.00 / 8.37 | `0 91% 71%` | 7.33 / 6.94 |
| `--info` | Ciano Foco (texto/ícone) | `194 70% 27%` | 6.86 / 7.18 | `188 86% 53%` | 11.14 / 10.55 |
| `--destructive` | Vermelho de ação irreversível | `0 74% 42%` | 6.14 / 6.42 | `0 91% 71%` | 7.33 / 6.94 |
| `--border` | Fio (decorativo) | `214 32% 91%` | 1.19 / — | `221 32% 15%` | 1.27 / — |
| `--ring` | Anel de foco | `188 86% 34%` | 3.76 / — | `188 86% 53%` | 11.14 / — |

`--ok`, `--warn`, `--danger` e `--info` carregam ainda uma folga acima do
piso: cada um continua passando o piso de **4.5:1 de texto** (o token pinta o
próprio texto do chip, ex. `text-info` sobre `hover:bg-info/20`) mesmo quando
ganha `hover:bg-X/20` sobre a própria superfície `-surface` (a razão mais
apertada é `--info`, a 4.75:1 no claro — ver `temaTokens.test.ts`, describe
"token de estado tem folga para o hover do próprio matiz",
`expect(comHover).toBeGreaterThanOrEqual(4.5)`). Foi exatamente a folga que
faltou em `--info` antes da Task 13 (`ReviewPanel.tsx:288`, caía a 3.66:1 —
abaixo de 4.5, não de 3). `--border` e o fio geral são decorativos e **não
têm piso**
(ver "Herdado de julgamentos" do plano de contraste); `--ring` e qualquer
borda que funcione como indicador de foco ou fronteira de controle
respondem ao piso de 3:1.

`--danger` (estado "falhou") e `--destructive` (ação irreversível: apagar,
descartar) são dois vermelhos, de propósito — não é duplicação a corrigir.
`--danger` pinta chip/badge de estado; `--destructive` pinta o botão que
apaga ou descarta trabalho, com `--destructive-foreground` por cima do
próprio fundo (não é texto sobre a página). Os dois passam o piso com folga
nos dois temas. Como não aparecem lado a lado em tela nenhuma do app hoje, a
comparação foi feita fora do app — um swatch isolado com o HSL real de cada
token (`0 70% 35%` / `0 74% 42%`, ambos sobre `--background`) — e a
diferença de tom entre eles é sutil o bastante para não ler como
inconsistência quando vistos separadamente, no contexto onde cada um
realmente aparece. Convergiram só a intenção (vermelho = erro/perigo), não
o valor.

**A Regra do Token.** Cor de estado só entra por classe de token
(`text-ok`, `bg-danger-surface`, `border-info/40`, ...), nunca por shade cru
do Tailwind (`text-emerald-300`, `bg-red-500/15`) direto num componente. O
teste `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` recusa shade
cru fora da lista de exceções nomeadas (`PERMITIDO_TEMA`) — ele é a guarda
mecânica desta regra, não um substituto pra revisão visual dos dois temas.

**Duas coisas que a guarda mecânica não pega:**
- **Opacidade numa classe de cor às vezes é papel, não ruído.** `text-X/80`
  ao lado de `text-X` costuma marcar hierarquia (título vs. metadado);
  `text-X/60` com `group-hover:text-X` é interação. Apagar a opacidade apaga
  o papel — não é limpeza, é perda de informação. O mecanismo proibido é a
  opacidade **embutida na cor** (`text-danger/60`, que muda o RGB efetivo);
  `opacity-N` solto no elemento é permitido e preserva os dois papéis porque
  não mexe na cor resolvida. Este erro apareceu **seis vezes** na migração de
  2026-09-06, em quatro telas diferentes, e nenhuma vez foi pego por teste —
  só por leitura de código.
- **Cor fora de `className` é invisível pra guarda.** Cor em `style`, em
  prop de animação do Framer Motion, ou montada por concatenação de string
  não é alcançada por nenhuma varredura estática — e o Framer nem resolve
  variável CSS na interpolação (anima o valor resolvido no primeiro frame,
  não o token). A saída é sempre classe de token no elemento, animando só
  `opacity`/`transform`/`scale`.

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

### Estados de espera (transversal)

Nenhum controle fica mudo. O padrão é sempre o mesmo, pra que "estou
processando" tenha uma cara só no app inteiro:

- **Botão**: prop `loading` do `components/ui/button` — spinner de 16px à
  esquerda, rótulo trocado pelo gerúndio do que está rodando ("Salvando...",
  "Finalizando...", "Iniciando relatório..."), `disabled` e `aria-busy`
  enquanto dura. Dois botões que disparam a mesma ação guardam qual foi
  tocado, senão o spinner acende no botão errado.
- **Navegação**: `components/ui/PendingLink` — a linha tocada escurece
  (`opacity-60`), ganha spinner à direita e para de aceitar toque; ao mesmo
  tempo acende a barra de 2px sob o cabeçalho (`NavProgressBar`), que só
  apaga quando a rota nova aparece.
- **Tela ou bloco carregando**: `components/ui/LoadingState` — spinner +
  frase do que está sendo buscado, com `role="status"`. Nunca uma tela vazia,
  nunca um "Carregando..." solto sem contexto.
- **Depois da ação**: toast de sucesso ou a mensagem de erro em pt-BR (ver
  "Erro é instrução" no PRODUCT.md). O estado de espera some só quando um dos
  dois aparece.

**A Regra do Toque Reconhecido.** Se um controle pode demorar mais que um
quadro, ele muda de aparência no toque. Não existe caminho em que o técnico
toque e a tela fique igual.

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

**A Regra do Espaço Extra.** A largura ganha no desktop compra **mais linhas
visíveis e mais meta por linha** — nunca aba, tabela larga ou toolbar. Essas
três são exatamente a anti-referência "tela de ERP / backoffice Odoo" do
PRODUCT.md, e uma tela larga é justamente onde a tentação aparece. Layout de
duas colunas é permitido em um caso só: lista de coletas à esquerda, detalhe
da coleta à direita, dentro da OS.

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
Três destinos (OSs, Histórico, Perfil), em duas variantes que dividem a mesma
lógica de ativo e o mesmo tratamento de espera:

- **Barra inferior**, abaixo de 1024px: fixa no rodapé, altura 56px, alvo de
  44px por item, sombra Sobreposto. É o padrão de polegar.
- **Coluna lateral**, a partir de 1024px: 200px de largura à esquerda, itens
  empilhados com ícone + rótulo, alvo de 44px, item ativo com fundo
  Superfície Elevada. Sem sombra — a coluna não flutua sobre conteúdo
  rolável, então separa por fio de 1px (A Regra do Fio). Um rodapé fixo a
  1080px de altura fica longe do olho e do cursor.

Item ativo em Tinta + `aria-current`; inativo em Tinta Fraca. **Ícone é SVG de
traço, nunca emoji.**

### Filtro segmentado (não é aba)
Dois botões lado a lado num bloco de 1px de fio, grudados no topo da coluna
que rola (`sticky`, fundo opaco — translúcido deixa o cartão atravessar o
rótulo). Alvo de 44px, contagem em `tabular-nums` no rótulo, inclusive a do
segmento inativo: é ela que diz que existe algo do outro lado. Ativo em
Superfície Elevada com anel de 1px; inativo em Tinta Fraca.

**Quem rola é o `<main>`, não a janela** — em toda largura, desde
2026-09-05. O invólucro do app tem altura definida (`h-dvh` + `min-h-0`), o
`main` é o scrollport e o respiro de 12px vive num wrapper **dentro** dele:
com o padding no próprio scrollport, o conteúdo rolava por dentro da faixa
acima do primeiro elemento grudado (sticky ancora na borda do padding), e
cartão passando por trás do filtro é o que ele existe pra impedir. Por isso
todo `sticky` de tela do técnico usa `top-0` como referência — o cabeçalho do
app está fora do scrollport.

**A distinção com "aba" é semântica, não cosmética.** O Don't contra aba
existe porque aba anuncia outro *destino* — é o vocabulário de backoffice de
ERP, onde cada aba é uma tela. Um filtro segmentado não troca de tela: a
lista é a mesma, exibida em recorte. Por isso o ARIA é `role="group"` com
botões `aria-pressed`, **nunca** `tablist`/`tab`/`tabpanel` — usar o ARIA de
aba aqui faria o leitor de tela anunciar exatamente a mentira que o Don't
quer evitar.

Em uso: a lista de coletas de dentro da OS (`ColetaFilter`), pendentes de um
lado e feitas do outro. Antes disso as duas seções eram empilhadas, e ver o
que já foi feito custava rolar a lista inteira de pendentes.

### Grupo recolhível de equipamento
Cabeçalho tonal (Ciclo em ciano, Realizadas em esmeralda) que **é** o
controle: `<button aria-expanded aria-controls>` com chevron que gira, alvo
de 44px, nunca `<details>` — o grupo precisa abrir por decisão de fora
(abrir uma coleta expande o grupo dela), e `<details>` só responde a toque.

Três regras que a implementação não pode perder:
- **Padrão recolhido só quando há mais de um grupo.** Grupo único nasce
  aberto: recolher esconderia a lista inteira sem ganho de rolagem.
- **Progresso é do equipamento, não do recorte em exibição** ("3 de 8", em
  `tabular-nums`). Dentro de "Pendentes" a contagem do segmento seria sempre
  "quanto falta", que a lista aberta já mostra.
- **Fundo opaco por baixo do tom.** O tom é translúcido
  (`bg-cyan-500/15`); grudado sobre a lista rolando, ele deixava os cartões
  atravessarem o nome do equipamento. A camada de tom vai por cima de
  `bg-background`, não direto sobre a página.

Grupo fechado não gruda (já ocupa uma linha e nada rola por baixo dele) e
não monta os cartões — o container do `aria-controls` continua no DOM, só
vazio.

### Signature Pad (componente de assinatura)
Área branca de 160px de altura, raio 8px, fio de 1px, com o botão "Limpar" em
ghost logo abaixo. Assinatura é documento, e documento é sobre papel — por
isso não segue o tema.

O pad é uma de **três** superfícies brancas fixas permitidas no tema escuro,
todas pelo mesmo raciocínio ("papel", não "tela"), registradas como exceção
permanente em `PERMITIDO_TEMA` (`temaTokens.test.ts`):
1. **Este Signature Pad** — a área de captura do traço.
2. **Logotipo da empresa no Perfil** (`perfil/page.tsx`) — ativo externo,
   traço escuro pensado sobre fundo branco; sem o branco fixo, some no
   escuro.
3. **Assinatura já capturada** no detalhe do relatório fechado
   (`relatorio/[relId]/page.tsx`) — mesma lógica de "documento", agora em
   modo leitura: o traço foi gravado em preto (`penColor="black"`), e um
   fundo que seguisse o tema (`bg-card` é navy no escuro) apagaria a
   assinatura.

### Visualizadores de anexo (foto / PDF) — dois cromos, de propósito

O app tem dois visualizadores de anexo, e eles não compartilham chrome:

- **"Ver foto"** (`CollectedCard.tsx`): lightbox próprio, `bg-black/90` de
  overlay, botão de fechar que **segue o tema**
  (`bg-muted/60 text-foreground` — círculo claro com X escuro no tema
  claro, claro sobre escuro no tema escuro).
- **`PdfViewerModal`**: cromo escuro **fixo nos dois temas**
  (`bg-dark-800`/`bg-dark-900`, texto `text-white*`), decisão de projeto
  registrada em `PERMITIDO_TEMA` — foto e PDF se leem melhor sobre fundo
  escuro, e o overlay já é preto.

**Veredito (Task 9):** no tema claro os dois continuam cada um legível por
si só, mas ficam **esteticamente incoerentes entre si** — o botão de fechar
da foto vira claro (segue o tema), enquanto o do PDF permanece escuro fixo.
Antes da migração de tokens essa diferença já existia (o PDF sempre foi
cromo escuro) e não incomodava porque **tudo** era escuro; agora que só um
dos dois clareia, a divergência fica mais visível. Ainda assim: os dois
nunca aparecem abertos ao mesmo tempo, cada um é legível isoladamente, e o
cromo escuro do PDF é decisão de projeto documentada (não acidente) — não é
prioridade de correção agora. Se algum dia incomodar de verdade, a saída é
uma de duas: (a) o lightbox de foto adotar o mesmo cromo escuro fixo do
`PdfViewerModal` (perde a coerência com o resto do app claro, ganha
coerência entre os dois visualizadores), ou (b) o `PdfViewerModal` passar a
seguir o tema (mexe numa decisão de projeto já tomada e testada). Nenhuma
das duas é óbvia o bastante para decidir sem o usuário — fica registrado
como débito, não como bug.

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
- **Do** dar resposta imediata a todo toque que dispara ação demorada:
  `loading` no botão, `PendingLink` na navegação, `LoadingState` no bloco.

### Don't:
- **Don't** parecer **tela de ERP / backoffice Odoo**: nada de aba, tabela
  larga ou formulário de 20 campos numa tela de campo. (Filtro segmentado
  **não** é aba — ver o componente na seção 5 para a diferença e para o ARIA
  que a sustenta.)
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
- **Don't** deixar um toque sem retorno visual. Botão que dispara RPC sem
  `loading`, linha de lista que navega sem `PendingLink` e espera sem
  `LoadingState` são o mesmo defeito: o técnico lê como travamento.
- **Don't** gatilhar a visibilidade do conteúdo numa animação de entrada
  (`initial={{ opacity: 0 }}` ou `scale: 0` no framer-motion). Se a animação
  não roda — aba em segundo plano, PWA retomado do standby, renderizador
  headless — a tela fica em branco com o conteúdo no DOM. Entrada é
  deslocamento sobre conteúdo já visível.
