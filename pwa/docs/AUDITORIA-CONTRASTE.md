# Auditoria de contraste — tema claro e escuro

Registro da auditoria de contraste WCAG AA feita durante o trabalho
"tema claro sem contraste" (`docs/superpowers/plans/2026-09-06-pwa-tema-claro-contraste.md`).
Script versionado em `scripts/contrast-audit.mjs`, rodado via
`npm run audit:contrast` (tema claro, default) e `THEME=dark npm run audit:contrast`
(tema escuro).

## Método

Estático, determinístico, sem browser — varre `app/**/*.tsx` e
`components/**/*.tsx`, extrai classes `text-*` / `border-*` / `ring-*` /
`bg-*` por linha via regex, resolve cada nome de cor contra:

1. os tokens declarados em `:root` (claro) / `:root.dark` (escuro) de
   `app/globals.css` — `text-ok` → `--ok`, `bg-ok-surface` → `--ok-surface`;
2. a paleta real do Tailwind resolvida por `tailwindcss/resolveConfig.js`
   (inclui o `extend` de `tailwind.config.ts`), para shade cru tipo
   `text-red-400`.

Para cada classe de cor de texto/borda/anel na linha, compõe o `bg-*`
declarado **na mesma linha** (aproximação do elemento) sobre o fundo da
página; se não houver `bg-*` local, testa contra as duas superfícies base do
app (`--background` e `--card`, pior caso). Calcula a razão WCAG e compara
contra o piso: **4.5:1 para texto**, **3:1 para borda/anel** (foco e
fronteira de controle).

Roda com `import resolveConfig from 'tailwindcss/resolveConfig.js'` estático
— funciona porque o script vive dentro do projeto (`pwa/scripts/`) e o
pacote resolve pelo `node_modules` local. A cópia arquivada em
`docs/superpowers/plans/2026-09-06-contrast-audit.mjs` usa import dinâmico
por variável de ambiente (`process.env.TW_RESOLVE`) porque foi escrita para
rodar de fora do projeto; **não portar esse import de volta**.

### Limitações conhecidas

- **Fundo inferido só da mesma linha de código.** Se o `bg-*` do elemento
  estiver numa linha diferente da classe de texto/borda (JSX quebrado em
  várias linhas, `cn()` com condicionais), o script cai no pior caso contra
  `--background`/`--card` — pode gerar falso positivo (fundo real é outra
  superfície mais favorável) ou, mais raro, falso negativo.
- **Borda decorativa não tem piso, mas o script não distingue.** Todo
  `border-*`/`ring-*` abaixo de 3:1 é reportado, inclusive fio de 1px
  puramente decorativo (`border-border`, `border-border/60`) que WCAG não
  exige que passe piso nenhum — só borda que funciona como indicador de foco
  ou fronteira de controle interativo precisa dos 3:1. Os achados de borda
  foram triados por **classe** (qual token, não ocorrência a ocorrência) —
  a maioria (`border-border*`, `border-ok/30`, `border-danger/40`, ...) é
  fio decorativo puro. Duas classes ficam **em aberto, não decididas nesta
  task**: `border-input` (7 ocorrências, 1.14–1.24:1, em
  `components/ui/button.tsx` e nos campos de login/coleta/finalizar) é
  literalmente a borda de um campo/botão, então pode contar como fronteira
  de controle; `ring-foreground/20` (`ColetaFilter.tsx:61`, 1.47:1) marca o
  segmento ativo do filtro segmentado (`DESIGN.md`, "anel de 1px" no ativo),
  então também pode ser estado de controle, não decoração pura. Nenhum dos
  dois tem urgência — ambos os elementos têm preenchimento/texto próprio que
  já sinaliza o estado — mas ficam registrados para quem decidir se merecem
  correção de token dedicada.
- **`PdfViewerModal.tsx` é falso positivo por construção.** O visualizador
  declara cromo escuro fixo nos dois temas (decisão de projeto, registrada
  em `PERMITIDO_TEMA` — foto e PDF se leem melhor sobre fundo escuro). O
  script compõe as classes `text-white*`/`border-white*` do componente sobre
  o fundo do **tema corrente** — no claro isso dá ~1:1 (branco sobre
  branco), porque o script não sabe que o painel em si é escuro fixo. Não é
  bug de código a corrigir; é o script sem contexto de "cromo declarado". A
  correção certa é ensinar o script a pular arquivos com cromo declarado, ou
  ler caso a caso — optou-se por anotar aqui em vez de mudar o script nesta
  rodada, para não arriscar mascarar um achado real em outro arquivo.
- **O script é CEGO a `opacity-N` no elemento.** Ele lê a opacidade embutida
  na classe de cor (`text-muted-foreground/60`, `bg-warn/5`) e compõe; não lê
  `opacity-60` como utilitário separado, e portanto não vê a redução de tinta
  que ele aplica ao texto de dentro. Confirmado por `grep -i opacity
  scripts/contrast-audit.mjs`: zero ocorrências. Isto importa porque os dois
  mecanismos compõem **pixel idêntico** — `text-muted-foreground/60` e
  `text-muted-foreground` + `opacity-60` dão os mesmos 2,80:1 no claro e
  3,74:1 no escuro. Enquanto o script não olhar `opacity`, "zero achados de
  texto" dele significa "zero achados **da forma que ele enxerga**". É o
  mesmo modo de falha que já aconteceu uma vez nesta migração (a versão do
  script cega a token novo, que devolvia `null` em silêncio e reportava
  contagem artificialmente baixa) — repetido num eixo diferente. A guarda
  contra ele hoje não é o script, é a regra "opacidade nua sobre token de
  texto" em `temaTokens.test.ts`, que também não é completa (ver as três
  fronteiras conhecidas anotadas naquele arquivo).
- **Opacidade de fundo em `bg-X/N` é composta sobre a superfície base, não
  sobre o pixel real por trás.** Se duas camadas translúcidas se empilham
  (ex.: tom sobre `bg-background` que por sua vez fica sobre um cartão), o
  script só enxerga um nível de composição.

## Antes / depois

| Momento | Claro | Escuro | Arquivos afetados (claro) |
|---|---|---|---|
| Antes de qualquer mudança (2026-09-06, medido para este plano) | **397** | 191 | 28 |
| Depois da migração de tokens, antes da Task 13 | 142 | — | — |
| Depois da Task 13 (correção do `text-info` em `ReviewPanel.tsx:288`) | **140**\* | **112**\* | 25 |

\* Medido nesta task (Task 9), rodando `npm run audit:contrast` e
`THEME=dark npm run audit:contrast` na branch `feat/tema-claro-contraste`. O
397 original (medido antes da migração começar) não foi decomposto por
categoria na hora — não dá pra dizer quanto dele já era borda decorativa
antes de qualquer mudança de token.

"142 → 140" é o delta **líquido**, não decomposto ocorrência a ocorrência: a
Task 13 não só corrigiu o `text-info` de `ReviewPanel.tsx:288` (3.66:1,
abaixo do piso de 4.5:1, para o valor recalculado do token — 6.86:1 na
página), como também mudou os valores HSL de `--ok`/`--danger`/`--info`, o
que desloca a razão de toda classe que os usa (`border-ok/30`,
`border-danger/40`, etc.), para cima ou para baixo. O que dá para afirmar
com confiança, porque foi revisado ocorrência a ocorrência (tabela abaixo):
**dos achados que o script reporta, nenhum é texto real** — os 140 que restam
no claro são o falso positivo estrutural do `PdfViewerModal` e bordas
decorativas.

> **Correção de 2026-09-06 (revisão final da branch).** A redação anterior
> desta frase dizia "não sobrou nenhum achado real de texto em nenhum dos
> dois temas", sem a ressalva. **Era falsa**, e da pior maneira: confundia o
> que o script mede com o que existe. O script é cego a `opacity-N` (ver
> Limitações conhecidas), e a revisão final encontrou **sete** sites de texto
> real abaixo do piso que ele não reportou, todos com tinta reduzida pelo
> elemento em vez de pela classe de cor:
>
> | Site | Medido (claro / escuro) | Desfecho |
> |---|---|---|
> | `app/login/page.tsx` — dica "N disponíveis" | 2,80 / 3,74 | corrigido (token puro, hierarquia por `font-normal`) |
> | `app/login/page.tsx` — rótulo do passo futuro do `StepIndicator` | 2,80 / 3,74 | corrigido (hierarquia por peso de fonte) |
> | `app/login/page.tsx` — rodapé (`animate={{ opacity: 0.6 }}` do Framer) | 2,80 / 3,74 | corrigido (opacidade volta a 1) |
> | `_components/RelatorioHeader.tsx:79` — "Comece o turno" | 3,47 / 3,47 | corrigido (hierarquia por tamanho/caixa alta) |
> | `_components/KindPill.tsx:55` — sub-rótulo | 3,47 / 3,47 | corrigido (hierarquia por peso) |
> | `_components/ColetaList.tsx` — prévia das coletas (opacidade no container) | 3,39 nome / 2,82 instrução — 6,01 / 3,71 no escuro | corrigido (borda tracejada no lugar da tinta reduzida) |
> | `_components/ReviewPanel.tsx` — linha de achado ignorado (opacidade no container) | 2,85 rótulo do botão "Restaurar" / 3,74 | corrigido (borda tracejada; a linha tem controles VIVOS dentro, então a isenção do WCAG para componente inativo não valia) |
>
> `historico/page.tsx:196` (`ChevronRight` a 60%) foi mantido: é ícone, não
> texto, e não responde a piso.
>
> Os números 140/112 abaixo foram **re-medidos** depois desta rodada de
> correções e não mudaram — nenhuma das mudanças moveu ocorrência através do
> piso pela ótica do script (os sites de `opacity` ele nunca contou, e
> `destructive` -> `danger` só troca um vermelho que já passava por outro que
> passa com mais folga).

**Checagem de cegueira do script** (a mesma armadilha que gerou "zero
achados" numa versão anterior): confirmado manualmente que `--ok` e
`--ok-surface` resolvem para RGB real antes de aceitar os números —
`--ok: 163 88% 20%` → `rgb(6, 96, 70)`, não `null`. Se o script estivesse
cego a token novo, cada `text-ok`/`bg-ok-surface` cairia em `return null` e
seria pulado em silêncio, e o relatório sairia artificialmente baixo. Não é
o caso aqui: os 140/112 encontrados batem com o que a leitura manual do
código já esperava (só borda decorativa + `PdfViewerModal`).

### Composição dos 140 achados do tema claro (140/140 revisados)

| Categoria | Ocorrências | Piso se aplica? |
|---|---|---|
| `border-*`/`ring-*` decorativo (fio de 1px, tom de superfície) | 106 | Não — decorativo, sem piso |
| `text-*`/`border-*` do `PdfViewerModal.tsx` (cromo escuro declarado) | 34 | Não — falso positivo por composição sobre o tema errado; o painel real é escuro fixo nos dois temas |
| Texto real abaixo do piso fora do `PdfViewerModal`, **pela ótica do script** | **0** | — |
| Texto real abaixo do piso **invisível para o script** (`opacity-N` no elemento) — **fora dos 140**, por isso a coluna soma mais que o total | 7, achados por leitura de código na revisão final — **todos corrigidos** | Sim — ver quadro de correção acima |

### Composição dos 112 achados do tema escuro

| Categoria | Ocorrências | Piso se aplica? |
|---|---|---|
| `border-*`/`ring-*` decorativo | 100 | Não — decorativo, sem piso |
| `border-white/10`, `border-white/5`, `text-white/40` do `PdfViewerModal.tsx` | 12 | Não — mesmo cromo declarado do claro; aqui o painel escuro real coincide com o tema, então a razão medida já é alta (3.73:1+) — o script ainda reporta por composição, mas não é achado |
| Texto real abaixo do piso | **0** | — |

## Tabela de tokens — valor e razão medida

Ver `DESIGN.md` §2 ("A fonte da verdade é o token, não o hex") para a tabela
completa com os dois temas lado a lado. Resumo dos tokens de estado no
tema **claro** (o que esta task auditou):

| Token | HSL | RGB | Sobre `--background` | Sobre `--card` | Piso |
|---|---|---|---|---|---|
| `--foreground` | `217 33% 17%` | rgb(30,41,59) | 14.17:1 | 14.82:1 | 4.5:1 |
| `--muted-foreground` | `215 19% 35%` | rgb(70,85,105) | 7.13:1 | 7.46:1 | 4.5:1 |
| `--ok` | `163 88% 20%` | rgb(6,96,70) | 7.25:1 | 7.58:1 | 4.5:1 |
| `--warn` | `23 83% 31%` | rgb(145,64,13) | 6.82:1 | 7.14:1 | 4.5:1 |
| `--danger` | `0 70% 35%` | rgb(152,27,27) | 8.00:1 | 8.37:1 | 4.5:1 |
| `--info` | `194 70% 27%` | rgb(21,95,117) | 6.86:1 | 7.18:1 | 4.5:1 |
| `--destructive` | `0 74% 42%` | rgb(186,28,28) | 6.14:1 | 6.42:1 | 4.5:1 |
| `--border` | `214 32% 91%` | rgb(225,231,239) | 1.19:1 | — | decorativo, sem piso |
| `--ring` | `188 86% 34%` | rgb(12,141,161) | 3.76:1 | — | 3:1 |

`--ok`/`--warn`/`--danger`/`--info` também foram checados com
`hover:bg-X/20` sobre a própria superfície `-surface` (o caso que a Task 13
corrigiu): o token pinta o próprio TEXTO do chip nesse hover (ex. `text-info`
sobre `hover:bg-info/20`), então o piso que vale é o de texto, 4.5:1 — não
3:1. Pior caso é `--info` a 4.75:1, ainda acima. Foi essa folga que faltou
antes da Task 13: `--info` caía a 3.66:1 em `ReviewPanel.tsx:288`, abaixo de
4.5 (`temaTokens.test.ts`, describe "token de estado tem folga para o hover
do próprio matiz", `expect(comHover).toBeGreaterThanOrEqual(4.5)`).

## Verificação visual dos dois temas (Task 9)

Com o dev server de pé, os dois temas foram percorridos via `agent-browser`
(`localStorage.setItem('theme', 'light'|'dark')` + reload) nas rotas de
login (passos 1 e 2), lista de OSs, detalhe da OS 4, lightbox de foto,
Histórico, detalhe de relatório fechado e Perfil.

**Escuro, comparado pixel a pixel** (Python/PIL) contra
`docs/baseline-escuro/` (captura de referência de **antes** de qualquer
mudança do plano):

- `os-4.png`: 58.333 px diferentes de 1.152.000 — **100% explicados** pela
  mudança autorizada do fundo do `EquipmentHeader`
  (`rgb(4,25,28)→rgb(11,41,45)`, amostrado manualmente em várias
  coordenadas) mais ruído de anti-aliasing de texto isolado.
- `login-1.png`: 22.224 px diferentes, concentrados no campo de URL/botão
  Conectar — é estado transitório de foco/cursor piscando entre as duas
  capturas, não mudança de token; cor e layout batem.
- `lista.png`/`historico.png`: conteúdo difere porque os dados do banco
  mudaram desde a baseline (mais OSs, relatório fechado semeado) — não é
  regressão visual; paleta idêntica a olho.
- `perfil.png`: achado — ver "Achados fora do escopo mecânico" abaixo.

**Claro** (nunca auditado visualmente antes desta task): nenhuma rota
capturada mostrou texto sumindo ou exigindo esforço, incluindo o cabeçalho
de grupo do `EquipmentHeader` (título + metadado lado a lado) e o
`ReviewPanel` com veredito renderizado (ver seção própria abaixo).

**Não coberto por captura, com o motivo:** seletor "Empresa ativa" no Perfil
(a conta de teste só tem uma empresa, sem permissão de escrita para semear
uma segunda), `PdfViewerModal` no claro com PDF real (banco de dev sem item
`kind='pdf'`, técnico sem permissão de escrita em `collect.item` para forçar
um), formulário de coleta aberto (as três OSs do técnico estão com 0
pendentes; reabrir uma na OS 4 desfaria o estado usado pelas outras
verificações desta task).

### `ReviewPanel` com veredito renderizado

O gate de `/api/groq/status` é só `!!process.env.GROQ_API_KEY` (não valida a
chave), e o veredito vem inteiramente de `useReviewCache`
(`localStorage.getItem('groq-review-result-<relId>')`, sem chamada de rede).
Verificado subindo o dev server com uma env var **dummy** (não a chave real,
que segue vazada/pendente de rotação) e semeando
`localStorage['groq-review-result-2077']` com um `ReviewResponse` sintético
(2 `warning` + 1 `info`) via `agent-browser eval`. Capturado nos dois temas:
badge "⚠ 2" (`bg-warn-surface`/`text-warn`), ícones `text-warn`/`text-info`
por severidade, pílula "Ir para item" (`bg-info-surface`/`text-info`) — só
tokens semânticos, nenhum shade cru `-200`/`-300`. Dev server religado sem a
env var dummy depois (`enabled: false` de novo), sem tocar em `.env.local`
nem na chave real.

### Minors diferidos — triagem (Task 9, item 7 do "herdado")

Três minors foram listados no brief como "diferidos a triar":

1. **Item `kind='pdf'` permanente no banco de dev.** Não é um débito de
   design, é uma lacuna de dado de teste — ver "não coberto" acima.
2. **Badge "concluído" do `StepIndicator` do login usa `bg-ok-surface`
   (calibrado a 15%) onde o original era `rgba(emerald, 0.20)`.**
   Recalculado: `--ok-surface` escuro (`187 61% 11%`) resolve a
   `rgb(11,41,45)`; o original a 20% sobre o cartão dava `rgb(11,49,51)`; a
   15% (a calibração que o resto do app usa, documentada no comentário de
   `--ok-surface` em `globals.css`) dá `rgb(11,40,46)` — o token bate quase
   exato com o 15%, não com o 20% que este componente específico usava
   sozinho. Distância end a end (Euclidiana em RGB) ≈ 10 — perceptível só em
   comparação lado a lado, não isoladamente. **Decisão: não corrigir.** É
   uma superfície decorativa atrás de um ícone de check (não há piso de
   contraste em jogo — o ícone `text-ok` por cima segue passando o piso nos
   dois casos), o papel semântico (verde = concluído) não muda, e o 20%
   original já era a exceção (o resto do app mede 15%) — manter o token
   compartilhado é mais consistente do que reintroduzir um valor
   hard-coded só para este badge.
3. **Anel estático do spinner do `AuthGuard` ficou mais escuro/azulado no
   escuro.** `border-border` (`221 32% 15%` → `rgb(26,34,50)`) contra o
   `border-white/20` original sobre `--background`
   (`rgb(53,57,65)`) — distância Euclidiana ≈ 38, bem mais perceptível que o
   item 2. **Decisão: registrar como débito, não corrigir agora.** É
   puramente decorativo (o aro girante `border-t-foreground` por cima é
   quem comunica progresso; o aro estático é só o "trilho"), sem piso de
   contraste aplicável, e aparece só durante o carregamento inicial — mas o
   salto de ~38 unidades é grande o bastante pra não descartar sem registro.
   Se algum dia incomodar: `border-border/40` ou similar aproximaria mais
   do neutro claro original sem reintroduzir branco absoluto.

### Achados fora do escopo mecânico

Dois achados que apareceram durante a verificação visual, fora do que esta
task se propôs a mexer:

1. **Bug de backend bloqueia o fechamento real de relatório no PWA.** Ao
   clicar "Fechar relatório" pela UI (fluxo real de técnico), o servidor
   Odoo estoura `ValueError: Invalid field 'request_service_scope' on model
   'hr.employee.public'`, dentro de `mail.thread._track_prepare()` ao ler
   `tecnico_ids` (proxy de segurança `hr.employee` → `hr.employee.public`
   para usuário sem acesso de RH). Reproduzido duas vezes; não é causado por
   nada deste plano (`hr.employee.public` é de fora do módulo
   `afr_qualificacao`) — parece mismatch de versão de módulo no ambiente
   `qualificacao-dev` (porta 8084). O relatório usado nesta auditoria
   (`RQOS00033`/#2077, OS 4) foi fechado contornando o bug via `write` direto
   por ORM (`context={tracking_disable: true}`), só para semear o dado — o
   bug em si não foi investigado nem corrigido, e nenhum técnico consegue
   fechar relatório do dia neste ambiente até alguém resolver isso.
2. **Ícones do Perfil convergiram para `text-muted-foreground` no escuro.**
   O diff pixel a pixel de `perfil.png` contra a baseline mostrou os ícones
   de identidade (Nome/Email/Empresa/Servidor/Database), o header com
   gradiente violeta→ciano e o ícone Lua/Sol do toggle de tema saindo de
   cores decorativas (`violet-300`/`cyan-300`/`emerald-300`/`amber-300`)
   para `text-muted-foreground` uniforme. `git diff main -- app/tecnico/qualificacao/perfil/page.tsx`
   confirma que essa mudança já está commitada em task anterior deste mesmo
   plano — não foi introduzida aqui. É consistente com a "Regra do Estado"
   do `DESIGN.md` (cores decorativas sem significado de estado) e com a
   limpeza de neon já registrada no `TODO.md`; as cores de origem eram todas
   shade `-300`, a mesma família que a mudança autorizada #1 do plano já
   cobre em termos gerais. Registrado por precaução, não por suspeita de
   regressão real.

## Deriva de superfície aceita no tema escuro (revisão final, 2026-09-06)

Os tokens `--*-surface` foram calibrados a **15%** do próprio matiz, mas a
migração os aplicou onde havia 5%, 10%, 15% e 20%. Onde o valor de origem
estava na faixa `/10..15`, a troca é imperceptível; fora dela, a superfície
muda de aparência no escuro — que está em produção. O levantamento completo:

| Site | Opacidade de origem | Desfecho |
|---|---|---|
| `_components/ColetaList.tsx` — aviso "Inicie o relatório do dia pra coletar" | `/5` | **Corrigido.** `bg-warn-surface` levava rgb(15,15,17) para rgb(45,36,27) no escuro: marrom nítido onde havia um véu quase invisível. Restaurado com token bruto (`bg-warn/5`), que é o mecanismo certo para **tingimento** de fundo — `-surface` fica para o chip que precisa de fundo de verdade. |
| `_components/ColetaList.tsx` — prévia das coletas | — | Registrado **por completude**, não é deriva de `-surface`: ao trocar a opacidade de container por borda tracejada, o fio passou de `border-border/40` para `/70`. Borda é decorativa e não tem piso; o ajuste existe só para a tracejada continuar visível sem a opacidade que antes a envolvia. |
| `components/ui/StatusBadge.tsx` | `/10` | **Aceito, não corrigido.** Chip fica levemente mais forte; texto sobre fundo caiu de 8,72:1 para 7,99:1, ainda com folga larga sobre o piso. |
| `_components/ReviewPanel.tsx` — badges | `/20` | **Aceito, não corrigido.** Badges ficaram mais escuros (20% -> 15%). |
| `_components/ReviewPanel.tsx` — `IssueRow` (`bg-cyan-600/10`) | `/10` | **Aceito, não corrigido.** Dentro da faixa. |
| `_components/EquipmentHeader.tsx` | — | **Já aceito em task anterior**, mesma classe de decisão. |

O critério que separa as duas colunas: `-surface` é **fundo de elemento**
(chip, badge, cartão de estado) e pode absorver alguns pontos de opacidade
sem mudar o que a superfície comunica; `bg-X/5` é **tingimento** de um bloco
que continua lendo como parte da página, e trocá-lo por uma superfície de
verdade muda o desenho, não só o tom.

## `focus:border-ring` dentro do `PdfViewerModal` — incoerência aceita

O visualizador é cromo escuro fixo nos dois temas (decisão de projeto), mas
os campos de página e de busca usam `focus:border-ring`, e `--ring` segue o
tema do **app**. Resultado: a borda de foco muda de tom num painel que não
muda.

**Decisão: fica como está**, e o motivo está escrito no próprio
`PdfViewerModal.tsx`, ao lado do primeiro uso. Anel de foco é vocabulário do
app inteiro; fixar um valor só aqui faria a navegação por teclado divergir
do resto — que é a incoerência que o técnico percebe de verdade. Os dois
valores passam o piso de 3:1 de fronteira de controle sobre o campo escuro
fixo (`#030712`): **5,12:1** com `--ring` do tema claro e **11,13:1** com o
do escuro.

## Como rodar de novo

```bash
cd pwa
npm run audit:contrast            # tema claro
THEME=dark npm run audit:contrast # tema escuro
```

Sem servidor, sem browser — roda em segundos e serve de checagem rápida
antes de qualquer PR que mexa em cor.
