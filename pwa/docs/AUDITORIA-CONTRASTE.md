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
**não sobrou nenhum achado real de texto** em nenhum dos dois temas — os 140
que restam no claro são o falso positivo estrutural do `PdfViewerModal` e
bordas decorativas.

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
| Texto real abaixo do piso fora do `PdfViewerModal` | **0** | — |

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

## Como rodar de novo

```bash
cd pwa
npm run audit:contrast            # tema claro
THEME=dark npm run audit:contrast # tema escuro
```

Sem servidor, sem browser — roda em segundos e serve de checagem rápida
antes de qualquer PR que mexa em cor.
