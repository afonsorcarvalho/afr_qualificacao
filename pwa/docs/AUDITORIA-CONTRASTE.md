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
  ou fronteira de controle interativo precisa dos 3:1. A maioria dos
  achados de borda em ambos os temas é desse tipo; cada um foi olhado à mão
  neste ciclo e nenhum é fronteira de controle real (ver tabela por
  arquivo abaixo).
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
`THEME=dark npm run audit:contrast` na branch `feat/tema-claro-contraste`.

Da leitura de "142 → 140": as duas ocorrências fechadas são exatamente as
duas composições (`sobre background` / `sobre card`) do `text-info` em
`ReviewPanel.tsx:288`, que a Task 13 levou de 3.66:1 (abaixo do piso de
4.5:1) para o valor do token `--info` recalculado (6.86:1 na página). Não
sobrou nenhum achado real de **texto** em nenhum dos dois temas — os que
restam (tabela abaixo) são o falso positivo estrutural do `PdfViewerModal`
e bordas decorativas.

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
corrigiu): pior caso é `--info` a 4.75:1, ainda acima do piso de 3:1 exigido
de fronteira de controle (o hover não é texto).

## Como rodar de novo

```bash
cd pwa
npm run audit:contrast            # tema claro
THEME=dark npm run audit:contrast # tema escuro
```

Sem servidor, sem browser — roda em segundos e serve de checagem rápida
antes de qualquer PR que mexa em cor.
