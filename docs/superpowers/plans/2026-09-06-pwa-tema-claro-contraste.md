# Tema claro legível — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o tema claro do PWA Técnico legível — hoje o login perde o texto
inteiro (branco sobre branco) e as informações protagonistas do Histórico saem a
~1.2:1 — corrigindo na camada de tokens, com uma trava que impeça a volta.

**Architecture:** As cores de estado deixam de ser shades cruas do Tailwind
espalhadas pelos componentes (`text-emerald-300`, `text-white/60`,
`bg-cyan-500/15`) e passam a ser **tokens semânticos** (`--ok`, `--warn`,
`--danger`, `--info`, mais as superfícies tonais correspondentes), definidos nos
dois temas em `app/globals.css` e mapeados em `tailwind.config.ts`. A troca é
mecânica, arquivo a arquivo, com um **teste-catraca**: ele proíbe os padrões
antigos e nasce com uma lista de exceções que enumera os arquivos infratores de
hoje; cada task apaga suas linhas dessa lista, então a lista só encolhe e um
arquivo novo com `text-white/60` falha o build.

**Tech Stack:** Next.js 14 (App Router), Tailwind 3, next-themes (`attribute="class"`,
`defaultTheme="dark"`), vitest + happy-dom, agent-browser para verificação visual.

**Spec:** este documento (a decisão de projeto está em `pwa/DESIGN.md` §2 Colors
e §6 Do's and Don'ts; a auditoria que originou o plano está em
`pwa/docs/AUDITORIA-CONTRASTE.md`, criada na Task 9).

## Global Constraints

- **O tema escuro não pode mudar de aparência.** Ele está em produção, foi
  verificado em dezenas de sessões e é o default. Toda troca de classe precisa
  render no escuro o que rendia antes — a única exceção autorizada está na Task 1
  (convergência de `-300` para os hexes do DESIGN.md), e é verificada por
  captura antes/depois na Task 9.
- **Piso de contraste:** 4.5:1 para texto (WCAG AA), 3:1 para indicador de foco e
  fronteira de controle. Bordas decorativas e divisórias não têm piso.
- **Tokens em tripla HSL sem `hsl()`** — `--ok: 163 94% 24%`, nunca
  `--ok: #047857` nem `--ok: hsl(163 94% 24%)`. O modificador de opacidade do
  Tailwind (`bg-ok/15`) só funciona nesse formato; token em hex gera **zero CSS**,
  que é exatamente o defeito das 236 classes indefinidas já corrigido em 2026-09-03.
- **Todo token novo entra nos DOIS blocos** de `app/globals.css`: `:root` (claro) e
  `:root.dark` (escuro).
- **Sem bump de `__manifest__.py`** — mudança só de front. A versão do PWA vive em
  `pwa/package.json`.
- **Commits em português, formato Conventional Commits**, feitos de dentro de
  `addons/afr_qualificacao/` (é submodule; `git push origin main` de lá antes de
  qualquer bump de pointer no monorepo).
- Diretório de trabalho de todos os comandos: `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa`.

---

## Contexto medido (não repetir a medição)

Auditoria determinística rodada em 2026-09-06 (script na Task 9): **397
ocorrências abaixo do piso AA no tema claro, 28 arquivos**; o tema escuro, que
está certo, marca 191 — a diferença entre os dois conjuntos é o defeito real.

Verificado na tela, com `localStorage.theme='light'`:

| Tela | Estado |
|---|---|
| `/login` (passos 1 e 2) | **Texto some.** Rótulos, valor digitado, nome do banco e indicador de passo são branco sobre `bg-card` branco. Só ícone, título e botão aparecem. |
| `/tecnico/qualificacao/historico` | Os três contadores (a informação protagonista) em `cyan-300`/`violet-300`/`emerald-300`, ~1.2:1. Rótulo "HOJE" idem. |
| `/tecnico/qualificacao/perfil` | Rótulo "TÉCNICO" lavado; cabeçalho com gradiente violeta→ciano (proibido pelo DESIGN.md). |
| `/tecnico/qualificacao/<os>` | Ações "Ver foto"/"Baixar", chips de ciclo e o aviso "Sem qualificador/padrão cadastrado" lavados. |
| `/tecnico/qualificacao` (lista) | OK. |

**Valores dos tokens já calculados** (contraste conferido; não recalcular):

| Token | Claro | ct sobre `#f8fafc` | ct sobre a superfície tonal | Escuro | ct sobre `--card` |
|---|---|---|---|---|---|
| `--ok` | `163 94% 24%` (emerald-700) | 5.24 | 4.91 | `158 64% 52%` (#34d399) | 9.93 |
| `--warn` | `23 83% 31%` (amber-800) | 6.78 | 6.46 | `43 96% 56%` (#fbbf24) | 11.44 |
| `--danger` | `0 74% 42%` (red-700) | 6.18 | 5.55 | `0 91% 71%` (#f87171) | 6.90 |
| `--info` | `193 82% 31%` (cyan-700) | 5.12 | 4.79 | `188 86% 53%` (#22d3ee) | 10.56 |
| `--ok-surface` | `160 57% 93%` | — | — | `187 61% 11%` | — |
| `--warn-surface` | `36 93% 94%` | — | — | `30 25% 14%` | — |
| `--danger-surface` | `0 83% 95%` | — | — | `323 31% 13%` | — |
| `--info-surface` | `190 71% 93%` | — | — | `201 73% 13%` | — |
| `--surface-raised` | `210 14% 97%` | — | — | `224 30% 12%` | — |
| `--ring` (corrigido) | `188 86% 34%` | 3.99 | — | `188 86% 53%` (inalterado) | — |
| `--destructive` (corrigido) | `0 74% 42%` | 6.18 | — | `0 91% 71%` (inalterado) | — |

Os valores **escuros** das superfícies são a composição medida do que o app
renderiza hoje (`bg-emerald-500/15` sobre `--card`), por isso os matizes saem
puxados para o azul do fundo — é fidelidade ao pixel atual, não escolha estética.

**Divergência consciente** (única mudança autorizada no escuro): DESIGN.md §2
define Verde Concluído `#34d399` (emerald-**400**), mas 11 chamadas usam
`emerald-300` e 27 usam `cyan-300`. O token adota o valor do DESIGN.md e os
call sites convergem para ele. No escuro isso escurece levemente esses textos
(todos seguem acima de 9:1). A Task 9 confirma por captura antes/depois.

---

## Estrutura de arquivos

**Camada de tokens (Task 1–2)**
- `app/globals.css` — declaração dos tokens nos dois temas + higiene do bloco `@layer base`.
- `tailwind.config.ts` — mapa `ok`/`warn`/`danger`/`info`/`surface-raised` para as classes utilitárias.

**Trava (Task 1, encolhe até a Task 8)**
- `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` — teste-catraca, mesmo
  idioma de `navegacaoHistorico.test.ts` (lê o código-fonte, exige justificativa).

**Troca mecânica (Tasks 3–7)** — 17 arquivos, agrupados por tela para o revisor
conseguir aprovar/rejeitar um grupo sem depender do vizinho.

**Verificação e documentação (Task 9)**
- `scripts/contrast-audit.mjs` + `npm run audit:contrast`
- `docs/AUDITORIA-CONTRASTE.md`, `DESIGN.md`, `TODO.md`

**Correções independentes (Tasks 10–12)** — deep link no login, `no-img-element`,
formalizações do checklist.

---

### Task 1: Camada de tokens + teste-catraca

**Files:**
- Modify: `app/globals.css` (blocos `:root` e `:root.dark`)
- Modify: `tailwind.config.ts` (`theme.extend.colors`)
- Create: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts`
- Create: `docs/baseline-escuro/` (capturas de referência)

**Interfaces:**
- Consumes: nada.
- Produces: as classes `text-ok`, `bg-ok-surface`, `text-warn`, `bg-warn-surface`,
  `text-danger`, `bg-danger-surface`, `text-info`, `bg-info-surface`,
  `bg-surface-raised` — todas com modificador de opacidade funcionando
  (`bg-ok/15`). E `PERMITIDO_TEMA`, o mapa de exceções que as Tasks 3–7 esvaziam.

- [ ] **Step 1: Capturar a linha de base do tema ESCURO antes de tocar em qualquer coisa**

O tema escuro é critério de aceitação; sem captura anterior não há como provar
que não mudou. O servidor de dev já está de pé na porta 3010 (registro do
`devserver`, sessão `f058f279`); se não estiver, subir com
`~/.claude/bin/devserver start --port 3010 --dir <pwa>` — nunca com `npm run dev &`.

```bash
mkdir -p docs/baseline-escuro
agent-browser open http://localhost:3010/login
agent-browser eval "localStorage.setItem('theme','dark')"
# login: servidor http://localhost:8084, banco qualificacao-dev,
#        usuário tecnico.a@teste.local, senha Teste@2026
# (depois de autenticar, para cada rota abaixo: abrir, esperar 5s, capturar)
for r in /tecnico/qualificacao /tecnico/qualificacao/historico /tecnico/qualificacao/perfil /tecnico/qualificacao/4; do
  echo "$r"
done
```

Capturas obrigatórias em `docs/baseline-escuro/`: `login-1.png`, `login-2.png`,
`lista.png`, `historico.png`, `perfil.png`, `os-4.png`.

- [ ] **Step 2: Escrever o teste-catraca (vai falhar — o arquivo de teste ainda não existe)**

Criar `app/tecnico/qualificacao/__tests__/temaTokens.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

/**
 * Guarda do tema claro.
 *
 * Em 2026-09-06 o user relatou, usando o app publicado, que no MODO CLARO
 * "botões e informações ficaram difíceis de ler". A medição achou 397
 * ocorrências abaixo do piso AA e a inspeção na tela mostrou coisa pior: o
 * login perde o texto inteiro, porque `text-white/60` sobre `bg-card` é
 * branco sobre branco.
 *
 * A causa não é um componente: é que cor de estado virou shade crua do
 * Tailwind espalhada por 17 arquivos, cada uma escolhida olhando só o tema
 * escuro. Consertar componente a componente traz o defeito de volta no
 * próximo componente escrito.
 *
 * Então este teste proíbe os PADRÕES, não os pixels:
 *   - `text-white`, `bg-white/40`, `border-white/10` e cia. — cor absoluta
 *     que assume fundo escuro;
 *   - `text-emerald-300`, `bg-cyan-500/15` e cia. — shade crua no lugar do
 *     token semântico (`text-ok`, `bg-info-surface`);
 *   - `text-muted-foreground/80` — "Tinta Apagada", que o DESIGN.md proíbe
 *     em texto que o técnico precisa ler (a /80 dá 4.35:1, abaixo do piso).
 *
 * `PERMITIDO_TEMA` nasceu enumerando os infratores de 2026-09-06 e só pode
 * ENCOLHER: cada task da migração apaga as suas linhas. Entrada morta é
 * erro, para a lista não virar depósito.
 */

const RAIZ = join(__dirname, '..', '..', '..', '..')
const PASTAS = ['app', 'components', 'lib']

const FAMILIAS = 'emerald|amber|red|rose|cyan|sky|blue|green|yellow|orange|teal|violet|indigo|fuchsia|pink|lime'

const PROIBIDO: { nome: string; re: RegExp; conserto: string }[] = [
  {
    nome: 'cor absoluta branca',
    re: new RegExp(String.raw`\b(?:text|bg|border|divide|ring)-white(?:\/\d{1,3})?\b`, 'g'),
    conserto: 'usar o papel semântico: text-foreground / text-muted-foreground / bg-surface-raised / border-border',
  },
  {
    nome: 'shade crua de cor de estado',
    re: new RegExp(String.raw`\b(?:text|bg|border|ring)-(?:${FAMILIAS})-\d{2,3}(?:\/\d{1,3})?\b`, 'g'),
    conserto: 'usar o token de estado: text-ok/warn/danger/info e bg-*-surface',
  },
  {
    nome: 'opacidade sobre tinta secundária',
    re: /\btext-muted-foreground\/\d{1,3}\b/g,
    conserto: 'usar text-muted-foreground puro — a opacidade derruba abaixo de 4.5:1',
  },
  {
    nome: 'família dark-* (fundo fixo escuro)',
    re: /\bbg-dark-\d{3}\b/g,
    conserto: 'usar bg-card / bg-muted / bg-surface-raised, ou declarar a superfície como cromo escuro em PERMITIDO_TEMA',
  },
]

/**
 * Exceções justificadas. Chave: `caminho relativo :: classe`.
 * NÃO acrescentar linha sem justificativa que sobreviva a uma revisão.
 */
const PERMITIDO_TEMA: Record<string, string> = {
  // --- catraca da migração de 2026-09-06: estas linhas SAEM conforme as tasks avançam ---
  // Task 3 (_components/)
  'app/tecnico/qualificacao/_components/ColetaList.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/CollectedCard.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/EquipmentHeader.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/FileInput.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/InstrumentBadges.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/OsCard.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/RelatorioHeader.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/ReviewPanel.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/SignatureCanvas.tsx :: *': 'migração pendente (Task 3)',
  'components/ui/StatusBadge.tsx :: *': 'migração pendente (Task 3)',
  // Task 4 (histórico + perfil)
  'app/tecnico/qualificacao/historico/page.tsx :: *': 'migração pendente (Task 4)',
  'app/tecnico/qualificacao/perfil/page.tsx :: *': 'migração pendente (Task 4)',
  // Task 5 (OS / coleta / relatório)
  'app/tecnico/qualificacao/[osId]/(painel)/layout.tsx :: *': 'migração pendente (Task 5)',
  'app/tecnico/qualificacao/[osId]/(painel)/coleta/[itemId]/page.tsx :: *': 'migração pendente (Task 5)',
  'app/tecnico/qualificacao/[osId]/relatorio/[relId]/page.tsx :: *': 'migração pendente (Task 5)',
  'app/tecnico/qualificacao/[osId]/relatorio/[relId]/finalizar/page.tsx :: *': 'migração pendente (Task 5)',
  'components/providers/AuthGuard.tsx :: *': 'migração pendente (Task 5)',
  // Task 6 (login)
  'app/login/page.tsx :: *': 'migração pendente (Task 6)',
  // Task 7 (visualizador)
  'components/ui/PdfViewerModal.tsx :: *': 'migração pendente (Task 7)',
}

function arquivos(): string[] {
  const out: string[] = []
  for (const pasta of PASTAS) {
    const walk = (d: string) => {
      for (const nome of readdirSync(d)) {
        if (nome === 'node_modules' || nome.startsWith('.')) continue
        const p = join(d, nome)
        if (statSync(p).isDirectory()) { walk(p); continue }
        if (!/\.tsx?$/.test(nome)) continue
        if (p.includes('__tests__')) continue
        out.push(p)
      }
    }
    walk(join(RAIZ, pasta))
  }
  return out
}

describe('tema: cor de estado só via token semântico', () => {
  /**
   * As duas verificações vivem no MESMO `it` de propósito. Se a lista de
   * exceções usadas fosse montada num teste e lida noutro, rodar a suíte
   * filtrada (`vitest -t "..."`, que este plano usa em várias tasks) acusaria
   * exceção morta que não está morta — o outro teste simplesmente não rodou.
   */
  it('nenhuma cor absoluta ou shade crua fora da lista, e nenhuma exceção morta', () => {
    const violacoes: string[] = []
    const usadas = new Set<string>()

    for (const abs of arquivos()) {
      const rel = relative(RAIZ, abs).split('\\').join('/')
      const src = readFileSync(abs, 'utf8')
      for (const regra of PROIBIDO) {
        for (const m of src.match(regra.re) ?? []) {
          const chaveCuringa = `${rel} :: *`
          const chaveExata = `${rel} :: ${m}`
          if (chaveCuringa in PERMITIDO_TEMA) { usadas.add(chaveCuringa); continue }
          if (chaveExata in PERMITIDO_TEMA) { usadas.add(chaveExata); continue }
          violacoes.push(`${rel}: \`${m}\` (${regra.nome}) — ${regra.conserto}`)
        }
      }
    }

    const mortas = Object.keys(PERMITIDO_TEMA).filter((k) => !usadas.has(k))

    expect(violacoes, `Classe de cor sem token semântico:\n  ${violacoes.join('\n  ')}`).toEqual([])
    expect(mortas, `Exceção que não corresponde a nenhum uso — apague:\n  ${mortas.join('\n  ')}`).toEqual([])
  })
})

describe('tema: tokens definidos nos dois temas', () => {
  const css = readFileSync(join(RAIZ, 'app/globals.css'), 'utf8')
  const bloco = (sel: string) => {
    const i = css.indexOf(`${sel} {`)
    expect(i, `bloco ${sel} não encontrado em globals.css`).toBeGreaterThan(-1)
    return css.slice(i, css.indexOf('\n}', i))
  }
  const NOVOS = ['ok', 'ok-surface', 'warn', 'warn-surface', 'danger', 'danger-surface',
                 'info', 'info-surface', 'surface-raised']

  it.each(NOVOS)('--%s existe nos dois temas, em tripla HSL', (nome) => {
    for (const sel of [':root', ':root.dark']) {
      const m = bloco(sel).match(new RegExp(String.raw`--${nome}:\s*([^;]+);`))
      expect(m, `--${nome} ausente em ${sel}`).not.toBeNull()
      // Tripla HSL crua: é o que faz `bg-ok/15` gerar CSS. Hex ou hsl() gera ZERO.
      expect(m![1].trim()).toMatch(/^\d{1,3} \d{1,3}% \d{1,3}%$/)
    }
  })

  it.each(NOVOS)('%s está mapeado no tailwind.config.ts com <alpha-value>', (nome) => {
    const cfg = readFileSync(join(RAIZ, 'tailwind.config.ts'), 'utf8')
    expect(cfg).toContain(`hsl(var(--${nome}) / <alpha-value>)`)
  })
})
```

- [ ] **Step 3: Rodar o teste e confirmar que falha pelo motivo certo**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/temaTokens.test.ts`
Expected: FAIL — os blocos `tema: tokens definidos nos dois temas` falham com
`--ok ausente em :root`. Os dois primeiros testes devem **passar** (a lista de
exceções cobre todos os infratores de hoje). Se algum arquivo aparecer como
violação, é arquivo que faltou na lista: acrescentar com a task correspondente.

- [ ] **Step 4: Declarar os tokens em `app/globals.css`**

No bloco `:root` (tema claro), depois de `--ring`:

```css
  /* Cores de estado (DESIGN.md §2). Valor CLARO escolhido pelo piso AA:
     cada um passa 4.5:1 tanto sobre o fundo da página (#f8fafc) quanto
     sobre a sua própria superfície tonal. As shades cruas do Tailwind que
     estavam espalhadas pelo código (`text-emerald-300`) saíam a ~1.2:1 aqui
     — foram escolhidas olhando só o tema escuro. */
  --ok:               163 94% 24%;   /* emerald-700 · 5.24:1 */
  --ok-surface:       160 57% 93%;
  --warn:             23 83% 31%;    /* amber-800   · 6.78:1 */
  --warn-surface:     36 93% 94%;
  --danger:           0 74% 42%;     /* red-700     · 6.18:1 */
  --danger-surface:   0 83% 95%;
  --info:             193 82% 31%;   /* cyan-700    · 5.12:1 */
  --info-surface:     190 71% 93%;
  /* Superfície um degrau acima do cartão — substitui `bg-white/5`, que no
     tema claro é branco sobre branco. */
  --surface-raised:   210 14% 97%;
```

E no mesmo bloco, **corrigir** dois tokens existentes:

```css
  /* Era `188 86% 42%`: 2.52:1 sobre o fundo claro, abaixo do piso de 3:1 que
     WCAG 1.4.11 exige de indicador de foco. */
  --ring:                  188 86% 34%;
  /* Era `0 72% 51%`: passa sobre o fundo puro, mas cai a 3.94:1 em cima da
     superfície tonal de erro, que é onde ele de fato aparece. */
  --destructive:           0 74% 42%;
```

No bloco `:root.dark`, depois de `--ring`:

```css
  /* Valores do DESIGN.md §2 (Verde Concluído / Âmbar Pendente / Vermelho
     Falha / Ciano Foco). As superfícies são a composição MEDIDA do que o app
     renderiza hoje (`bg-emerald-500/15` sobre `--card`) — por isso o matiz
     sai puxado para o azul do fundo: é fidelidade ao pixel atual. */
  --ok:               158 64% 52%;   /* #34d399 */
  --ok-surface:       187 61% 11%;
  --warn:             43 96% 56%;    /* #fbbf24 */
  --warn-surface:     30 25% 14%;
  --danger:           0 91% 71%;     /* #f87171 */
  --danger-surface:   323 31% 13%;
  --info:             188 86% 53%;   /* #22d3ee */
  --info-surface:     201 73% 13%;
  --surface-raised:   224 30% 12%;
```

- [ ] **Step 5: Mapear no `tailwind.config.ts`**

Dentro de `theme.extend.colors`, depois de `ring`:

```ts
        // Cores de estado. `<alpha-value>` + tripla HSL crua no globals.css
        // é o que permite `bg-ok/15`; token em hex geraria zero CSS.
        ok: {
          DEFAULT: 'hsl(var(--ok) / <alpha-value>)',
          surface: 'hsl(var(--ok-surface) / <alpha-value>)',
        },
        warn: {
          DEFAULT: 'hsl(var(--warn) / <alpha-value>)',
          surface: 'hsl(var(--warn-surface) / <alpha-value>)',
        },
        danger: {
          DEFAULT: 'hsl(var(--danger) / <alpha-value>)',
          surface: 'hsl(var(--danger-surface) / <alpha-value>)',
        },
        info: {
          DEFAULT: 'hsl(var(--info) / <alpha-value>)',
          surface: 'hsl(var(--info-surface) / <alpha-value>)',
        },
        'surface-raised': 'hsl(var(--surface-raised) / <alpha-value>)',
```

Atenção: o teste procura a string `hsl(var(--ok-surface) / <alpha-value>)`, que
com a forma aninhada acima aparece como `surface: 'hsl(var(--ok-surface) / <alpha-value>)'`
— confere.

- [ ] **Step 6: Rodar o teste e confirmar verde**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/temaTokens.test.ts`
Expected: PASS, todos os blocos.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `npx vitest run`
Expected: PASS, sem regressão. Baseline em `docs/BASELINE.md` — qualquer falha
aqui é regressão, não ruído ambiental.

Nota: **não** tente provar aqui que os tokens geram CSS. Nenhum arquivo usa
`text-ok` ainda, e o Tailwind emite as declarações de `:root` de qualquer jeito
— qualquer `grep` daria resultado enganoso nos dois sentidos. A prova está na
Task 3 Step 6, quando os primeiros usos existirem, e procura a **utilidade**
emitida, não a variável.

- [ ] **Step 8: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/globals.css pwa/tailwind.config.ts \
        pwa/app/tecnico/qualificacao/__tests__/temaTokens.test.ts \
        pwa/docs/baseline-escuro
git commit -m "feat(pwa): tokens de estado nos dois temas, com catraca contra shade crua"
```

---

### Task 2: Higiene do `@layer base` — o que já era escuro fixo

**Files:**
- Modify: `app/globals.css:84-112` (bloco `@layer base`)
- Modify: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` (novo bloco de teste)

**Interfaces:**
- Consumes: nada da Task 1.
- Produces: nada. Task independente — pode ser revisada e rejeitada sozinha.

Três regras globais assumem fundo escuro sem nenhuma condição de tema. A do
`color-scheme` é a mais séria: ela pinta o seletor nativo de data **e o cromo do
próprio input** de escuro numa página clara, e é forte candidata a parte do
"botões e informações difíceis de ler" que o user relatou.

Note que o script inline do `next-themes` já faz `d.style.colorScheme = e || 'dark'`
no `<html>` — ou seja, o app **já** informa o esquema certo ao navegador, e a
regra do `globals.css` estava sobrescrevendo isso só para os inputs de data.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `temaTokens.test.ts`:

```ts
describe('tema: nada de escuro fixo no @layer base', () => {
  const css = readFileSync(join(RAIZ, 'app/globals.css'), 'utf8')

  it('color-scheme dos inputs de data segue o tema, não é fixo em dark', () => {
    // O script do next-themes já escreve `document.documentElement.style.colorScheme`.
    // Uma regra `color-scheme: dark` incondicional no CSS vence isso para os
    // inputs e entrega seletor de data escuro em página clara.
    const base = css.slice(css.indexOf('@layer base'))
    expect(base).not.toMatch(/color-scheme:\s*dark\s*;/)
  })

  it('scrollbar e seleção de texto não usam branco absoluto', () => {
    const base = css.slice(css.indexOf('@layer base'), css.indexOf('@layer utilities'))
    // `rgba(255,255,255,0.1)` num thumb sobre fundo claro é invisível;
    // `::selection { color: white }` sobre um realce de 20% de opacidade
    // apaga o texto selecionado.
    expect(base).not.toMatch(/rgba\(255,\s*255,\s*255/)
    expect(base).not.toMatch(/color:\s*white/)
  })
})
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/temaTokens.test.ts -t "escuro fixo"`
Expected: FAIL nos dois testes.

- [ ] **Step 3: Corrigir o `@layer base`**

Substituir os três trechos. Scrollbar:

```css
  ::-webkit-scrollbar-thumb {
    /* Era `rgba(255,255,255,0.1)`: invisível no tema claro. O token de borda
       existe nos dois temas. */
    background: hsl(var(--border));
    border-radius: 3px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: hsl(var(--muted-foreground) / 0.5);
  }
```

Seleção:

```css
  ::selection {
    /* Era ciano a 20% com `color: white` — no tema claro o texto selecionado
       sumia. Realce pelo token de foco, e a tinta segue o tema. */
    background: hsl(var(--ring) / 0.25);
    color: hsl(var(--foreground));
  }
```

Inputs de data — apagar o bloco inteiro:

```css
  /* REMOVIDO: `input[type="date"] { color-scheme: dark }` e irmãos.
     O script do next-themes já escreve `colorScheme` no <html>, e os inputs
     herdam. A regra fixa entregava seletor de data escuro em página clara. */
```

- [ ] **Step 4: Rodar e confirmar verde**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/temaTokens.test.ts`
Expected: PASS.

- [ ] **Step 5: Conferir na tela que o seletor de data segue o tema**

O campo de data aparece no formulário de coleta. Com o servidor de dev de pé:

```bash
agent-browser eval "localStorage.setItem('theme','light')"
agent-browser open "http://localhost:3010/tecnico/qualificacao/4"
agent-browser eval "getComputedStyle(document.documentElement).colorScheme"
```

Expected: `"light"`. Repetir com `'dark'` e esperar `"dark"`.

- [ ] **Step 6: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/globals.css pwa/app/tecnico/qualificacao/__tests__/temaTokens.test.ts
git commit -m "fix(pwa): tira o escuro fixo da scrollbar, da seleção e do seletor de data"
```

---

### Task 3: Migrar `_components/` e `StatusBadge`

**Files:**
- Modify: `app/tecnico/qualificacao/_components/ColetaList.tsx`
- Modify: `app/tecnico/qualificacao/_components/CollectedCard.tsx`
- Modify: `app/tecnico/qualificacao/_components/EquipmentHeader.tsx`
- Modify: `app/tecnico/qualificacao/_components/FileInput.tsx`
- Modify: `app/tecnico/qualificacao/_components/InstrumentBadges.tsx`
- Modify: `app/tecnico/qualificacao/_components/OsCard.tsx`
- Modify: `app/tecnico/qualificacao/_components/RelatorioHeader.tsx`
- Modify: `app/tecnico/qualificacao/_components/ReviewPanel.tsx`
- Modify: `app/tecnico/qualificacao/_components/SignatureCanvas.tsx`
- Modify: `components/ui/StatusBadge.tsx`
- Modify: `app/tecnico/qualificacao/_components/MicButton.tsx` — achado na Task 1, faltava na lista
- Modify: `components/ui/GlassCard.tsx` — achado na Task 1, faltava na lista
- Modify: `app/tecnico/qualificacao/page.tsx` — `accent-emerald-500` no checkbox
  "OSs atribuídas a você" (linha 53). Achado na revisão da Task 1: escapava do
  regex e não pertencia a task nenhuma. Vira `accent-ok`. **Atenção:** a Task 12
  também edita este arquivo (comentário na linha 23) — linhas diferentes, e a
  T3 roda antes.
- Modify: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` (apagar as linhas de `PERMITIDO_TEMA` marcadas `Task 3`)

**Dois casos que a troca mecânica não resolve sozinha** (levantados pela Task 1):

- `MicButton.tsx:187` — `text-red-500` no cronômetro de gravação (`● mm:ss`).
  Não é `-300`, então a troca para `text-danger` **muda** o escuro: red-500 →
  red-400. **Autorizado**: é indicador de estado (gravando), e no escuro o token
  sobe de 3.9:1 para 6.9:1 sobre o cartão — a mudança melhora a legibilidade em
  vez de degradar. Registrar na captura de verificação.
- `GlassCard.tsx:36` — `border-amber-600/50` na borda de alerta. É **borda**:
  sem piso de contraste, e a deriva de matiz no escuro já está aceita pela
  regra de bordas desta tabela. Vira `border-warn/50` sem cerimônia.

**Interfaces:**
- Consumes: `text-ok|warn|danger|info`, `bg-*-surface`, `bg-surface-raised` (Task 1).
- Produces: nada de API nova. Os componentes mantêm props e nomes.

**Tabela de tradução — vale para as Tasks 3 a 6, aplicar mecanicamente:**

> ⚠️ **CORREÇÃO (revisão final, 2026-09-06) — duas linhas desta tabela
> estavam ERRADAS e induziram defeito real em quatro sites.** As linhas de
> `text-white/20..40` e do par apaga→acende mandavam substituir a opacidade
> embutida na cor por `opacity-N` no elemento, com o argumento de que "o
> mecanismo proibido é a opacidade embutida na classe de COR". Isso confunde
> **mecanismo** com **efeito**: `text-muted-foreground/60` e
> `text-muted-foreground` + `opacity-60` compõem pixel idêntico (2,80:1 no
> claro, 3,74:1 no escuro). A saída sancionada reproduzia o defeito no mesmo
> valor, agora invisível para a catraca. **O erro é do plano**, não de quem o
> aplicou. As duas linhas estão corrigidas abaixo; a regra definitiva é "A
> Regra da Tinta Única" no `DESIGN.md`.

| Antes | Depois |
|---|---|
| `text-emerald-200/300/400` | `text-ok` |
| `text-amber-200/300/400`, `text-amber-600/700` | `text-warn` |
| `text-red-300/400/500/600`, `text-rose-*` | `text-danger` |
| `text-cyan-200/300`, `text-cyan-600/700/800` | `text-info` |
| `text-violet-300/500` | `text-muted-foreground` (violeta não nomeia estado nenhum — DESIGN.md §2 proíbe) |
| `bg-emerald-500/10..15` | `bg-ok-surface` |
| `bg-amber-500/10..15` | `bg-warn-surface` |
| `bg-red-500/10..15`, `bg-rose-*/1x` | `bg-danger-surface` |
| `bg-cyan-500/10..15`, `bg-blue-500/10` | `bg-info-surface` |
| `border-emerald-400/30`, `border-emerald-500/40`, `border-emerald-600/30`, … | `border-ok/30` — **e o mesmo para as demais famílias**. Decisão consciente: borda é decorativa, não tem piso de contraste (ver Global Constraints), então a deriva de matiz e de opacidade no tema escuro é aceita em troca de uma regra só. Não enumerar shade por shade. |
| `bg-white/5`, `bg-white/[0.02]` | `bg-surface-raised` |
| `bg-white/10` (trilho de progresso) | `bg-muted` |
| `border-white/5..20`, `divide-white/10` | `border-border` |
| `text-white` | `text-foreground` |
| `text-white/50..70` | `text-muted-foreground` |
| `text-white/20..40` (ícone desativado) | `text-muted-foreground` puro. **Se for TEXTO, é só isso** — não existe terceiro nível de tinta, e `opacity-N` no elemento NÃO é uma saída: compõe idêntico à opacidade na cor. Precisando de menos peso, use tamanho ou peso de fonte. `opacity-N` só vale se o alvo for de fato ícone/decoração, onde não há piso. |
| `text-muted-foreground/60,70,80` | `text-muted-foreground` |
| `bg-gradient-to-*` decorativo | superfície tonal chapada (`bg-ok-surface`, `bg-info-surface`) |
| `hover:bg-X-500/10..20` (**tingimento de hover**, não superfície estática) | `hover:bg-ok/10` — token BRUTO em baixa opacidade, **não** `bg-ok-surface`. As superfícies tonais são chapadas e opacas; usá-las num hover trocaria um tingimento translúcido por um bloco sólido e mudaria o escuro. Lacuna da tabela achada na revisão da Task 4. |
| `text-X/60 transition group-hover:text-X` (**par apaga→acende**) | Depende do que é o alvo. **Ícone/decoração:** `text-X opacity-60 transition group-hover:opacity-100` — sem piso, a opacidade preserva a interação. **Texto:** `text-muted-foreground transition group-hover:text-foreground` — o par vira uma troca de token, não de tinta, porque o estado de repouso também precisa ser legível. **Apagar o hover não é traduzir o hover** (defeito das Tasks 3 e 4); **e igualar repouso e hover é apagar o hover com outro nome** (defeito de um fix round posterior, em `app/login/page.tsx`). |
| `bg-gradient-to-r from-emerald-500 to-teal-400` (barra de progresso) | `bg-ok` |
| par `text-emerald-700 dark:text-emerald-400` (39 variantes `dark:` no projeto) | `text-ok` — o token já resolve o tema; o par vira ruído. **O render tem que ficar idêntico nos dois temas**: onde o par existia, o código já estava certo. |

- [ ] **Step 1: Escrever o teste de comportamento que trava o resultado**

Criar `app/tecnico/qualificacao/__tests__/StatusBadge.test.tsx`.

**Contexto que muda o sentido desta migração:** `StatusBadge` é o único
componente do projeto que **já** trata os dois temas certo — ele usa
`text-emerald-700 dark:text-emerald-400`, e esses dois valores são exatamente
`--ok` claro e `--ok` escuro. Migrar aqui não conserta defeito: consolida o
padrão certo num token, para que o próximo componente herde em vez de repetir.
A consequência prática é que **o render não pode mudar em tema nenhum** — se
mudar, o token foi mapeado errado.

A API real é `tone: 'done' | 'progress' | 'waiting' | 'error' | 'neutral'`
(ver `components/ui/StatusBadge.tsx`), não `ok`/`warn`.

```tsx
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { StatusBadge } from '@/components/ui/StatusBadge'

describe('StatusBadge: cor de estado por token', () => {
  it('estado concluído usa o token --ok em vez do par emerald-700/dark:emerald-400', () => {
    const { container } = render(<StatusBadge tone="done">Coletada</StatusBadge>)
    const cls = container.firstElementChild!.className
    expect(cls).toContain('text-ok')
    expect(cls).not.toMatch(/emerald-\d/)
    // O token já resolve o tema: o par `dark:` vira ruído e some.
    expect(cls).not.toContain('dark:')
  })

  it('em espera usa --warn, falha usa --danger', () => {
    const warn = render(<StatusBadge tone="waiting">Pendente</StatusBadge>)
    expect(warn.container.firstElementChild!.className).toContain('text-warn')
    const err = render(<StatusBadge tone="error">Falhou</StatusBadge>)
    expect(err.container.firstElementChild!.className).toContain('text-danger')
  })

  it('a informação sobrevive sem a cor (Regra do Par, DESIGN.md §2)', () => {
    const { container } = render(<StatusBadge tone="waiting">Pendente</StatusBadge>)
    expect(container.textContent).toBe('Pendente')
  })
})
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/StatusBadge.test.tsx`
Expected: FAIL — `expected '...text-emerald-700 dark:text-emerald-400...' to contain 'text-ok'`.

- [ ] **Step 3: Trocar as classes nos 10 arquivos**

Aplicar a tabela de tradução. Duas armadilhas:

0. **`SignatureCanvas`: o traço não é classe, é JavaScript.** Antes de mexer nas
   classes, rodar `grep -nE "strokeStyle|'#fff|\"#fff|white|rgb\(255" app/tecnico/qualificacao/_components/SignatureCanvas.tsx`.
   Cor de traço fixada em literal no canvas **não é pega pelo teste-catraca** —
   e assinatura branca sobre papel branco no tema claro é exatamente a classe de
   defeito que este plano existe para fechar. Se houver literal, ler a cor do
   tema em tempo de desenho:
   `getComputedStyle(canvas).getPropertyValue('color')` com a classe
   `text-foreground` no elemento, em vez de hex fixo. Escrever um teste que
   afirme que o arquivo não contém literal de cor branca.

1. **`bg-emerald-500/15` não vira `bg-ok/15`.** O token `--ok` é a cor do TEXTO;
   a 15% de opacidade ele dá uma superfície diferente da medida. Usar
   `bg-ok-surface` (chapada, já calculada nos dois temas).
2. **`OsCard.tsx:78`** tem a barra de progresso com gradiente
   (`from-emerald-500 to-teal-400`). Vira `bg-ok` chapado — o DESIGN.md §6 lista
   gradiente entre os Don'ts, e a barra já comunica por comprimento.

- [ ] **Step 4: Apagar as 10 linhas da catraca**

Em `temaTokens.test.ts`, remover do `PERMITIDO_TEMA` as entradas marcadas
`(Task 3)`.

- [ ] **Step 5: Rodar os testes**

Run: `npx vitest run`
Expected: PASS. Se `temaTokens` acusar violação num dos 10 arquivos, ficou classe
crua para trás — o erro nomeia arquivo e classe.

- [ ] **Step 6: Confirmar que as classes novas geram CSS**

```bash
npx tailwindcss -c tailwind.config.ts -i app/globals.css -o /tmp/tw-check.css \
  --content './app/**/*.tsx,./components/**/*.tsx' 2>/dev/null
grep -E '^\.(text|bg)-(ok|info|warn|danger)' /tmp/tw-check.css | head
```

Expected: as regras `.text-ok`, `.bg-ok-surface` etc. aparecem. Procurar por
`var(--ok)` **não** serve de prova: o Tailwind copia as declarações de `:root`
para a saída mesmo que nenhuma classe exista. Saída vazia aqui significa token
mal mapeado no `tailwind.config.ts` — o defeito das 236 classes indefinidas
voltando.

- [ ] **Step 7: Conferir na tela, nos dois temas**

Lista de OSs e detalhe da OS 4, em `light` e em `dark`. No escuro, comparar com
`docs/baseline-escuro/lista.png` e `os-4.png`: a diferença aceita é só o leve
escurecimento dos textos que eram `-300`.

- [ ] **Step 8: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/_components pwa/components/ui/StatusBadge.tsx \
        pwa/app/tecnico/qualificacao/__tests__
git commit -m "refactor(pwa): componentes de campo passam a usar os tokens de estado"
```

---

### Task 4: Migrar Histórico e Perfil (as duas telas com gradiente)

**Files:**
- Modify: `app/tecnico/qualificacao/historico/page.tsx`
- Modify: `app/tecnico/qualificacao/perfil/page.tsx`
- Modify: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` (apagar 2 linhas)
- Test: `app/tecnico/qualificacao/__tests__/HistoricoPerfil.test.tsx` (criar)

**Interfaces:**
- Consumes: tokens da Task 1; a tabela de tradução da Task 3.
- Produces: nada.

São as duas telas com o pior sintoma depois do login: no Histórico os **três
contadores** — a informação protagonista — saem a ~1.2:1, e as duas telas
carregam cabeçalho com gradiente decorativo (`from-cyan-500/15 via-blue-500/10`,
`from-violet-500/15 via-cyan-500/10`), que escapou da limpeza do neon de
2026-09-03 e viola o DESIGN.md §6.

- [ ] **Step 1: Escrever o teste que falha**

```tsx
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const RAIZ = join(__dirname, '..', '..', '..', '..')
const ler = (p: string) => readFileSync(join(RAIZ, p), 'utf8')

describe('Histórico e Perfil: sem enfeite, com token', () => {
  const telas = [
    'app/tecnico/qualificacao/historico/page.tsx',
    'app/tecnico/qualificacao/perfil/page.tsx',
  ]

  it.each(telas)('%s não usa gradiente decorativo (DESIGN.md §6 Don\'t)', (p) => {
    expect(ler(p)).not.toMatch(/bg-gradient-to-/)
  })

  it.each(telas)('%s não usa sombra colorida', (p) => {
    // `shadow-cyan-500/10` é o mesmo vocabulário do glow aposentado.
    expect(ler(p)).not.toMatch(/shadow-(?:cyan|violet|emerald|blue)-/)
  })

  it('os contadores do Histórico usam os tokens de estado', () => {
    const src = ler('app/tecnico/qualificacao/historico/page.tsx')
    expect(src).toMatch(/text-(?:info|ok|warn|foreground)\b/)
    expect(src).not.toMatch(/text-(?:cyan|violet|emerald)-\d/)
  })
})
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/HistoricoPerfil.test.tsx`
Expected: FAIL nos quatro casos.

- [ ] **Step 3: Trocar as classes**

Aplicar a tabela da Task 3, mais:

- `historico/page.tsx:93` — cabeçalho "HOJE": trocar
  `bg-gradient-to-br from-cyan-500/15 via-blue-500/10 to-transparent p-4 shadow-lg shadow-cyan-500/10`
  por `bg-info-surface p-4`. O rótulo "HOJE" vira `text-info`; os três números
  viram `text-foreground` (são dado neutro, não estado — o estado quem diz é o
  rótulo abaixo), e cada ícone acompanha o token do seu escopo.
- `perfil/page.tsx:92` — cabeçalho: `bg-gradient-to-br from-violet-500/15 via-cyan-500/10 to-transparent`
  vira `bg-muted`. O rótulo "TÉCNICO" vira `text-muted-foreground`.
- `perfil/page.tsx:101` — avatar `bg-gradient-to-br from-violet-500 to-cyan-500`
  vira `bg-muted` com `text-foreground`.
- Ícones de campo (violeta/ciano/âmbar/esmeralda) viram `text-muted-foreground`:
  são decoração ao lado de um rótulo que já diz tudo, e cinco matizes diferentes
  ali é exatamente cor usada como categoria, que o DESIGN.md §2 proíbe.

- [ ] **Step 4: Apagar as 2 linhas da catraca (`Task 4`)**

- [ ] **Step 5: Rodar os testes**

Run: `npx vitest run`
Expected: PASS.

- [ ] **Step 6: Conferir na tela, nos dois temas**

`/tecnico/qualificacao/historico` e `/perfil`, em `light` e `dark`. No claro, os
contadores têm que ser a coisa mais legível da tela. No escuro, comparar com
`docs/baseline-escuro/historico.png` e `perfil.png`.

- [ ] **Step 7: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/historico pwa/app/tecnico/qualificacao/perfil \
        pwa/app/tecnico/qualificacao/__tests__
git commit -m "fix(pwa): contadores do Histórico legíveis no claro, e fim dos gradientes decorativos"
```

---

### Task 5: Migrar OS, coleta, relatório e AuthGuard

**Files:**
- Modify: `app/tecnico/qualificacao/[osId]/(painel)/layout.tsx`
- Modify: `app/tecnico/qualificacao/[osId]/(painel)/coleta/[itemId]/page.tsx`
- Modify: `app/tecnico/qualificacao/[osId]/relatorio/[relId]/page.tsx`
- Modify: `app/tecnico/qualificacao/[osId]/relatorio/[relId]/finalizar/page.tsx`
- Modify: `components/providers/AuthGuard.tsx`
- Modify: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` (apagar 5 linhas)

**Interfaces:**
- Consumes: tokens da Task 1; tabela da Task 3.
- Produces: nada.

- [ ] **Step 1: Rodar o teste existente do painel, que já guarda parte disto**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/PainelLayout.test.tsx`
Expected: PASS (linha 224 já proíbe `bg-gradient-to-br` no bloco de conclusão).
É a rede que impede a troca de classes de reintroduzir enfeite.

- [ ] **Step 2: Estender esse teste para o token**

Acrescentar a `PainelLayout.test.tsx`:

```tsx
  it('o bloco de conclusão usa o token de estado, não shade crua', () => {
    // Mesmo render usado pelos testes vizinhos deste arquivo.
    expect(html).toContain('ok-surface')
    expect(html).not.toMatch(/emerald-\d/)
  })
```

Usar a mesma variável `html` que os testes vizinhos do arquivo já montam.

- [ ] **Step 3: Rodar e confirmar a falha**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/PainelLayout.test.tsx`
Expected: FAIL — `expected '...emerald-500/10...' to contain 'ok-surface'`.

- [ ] **Step 4: Trocar as classes nos 5 arquivos**

Aplicar a tabela da Task 3. Pontos que exigem decisão, não substituição cega:

- `relatorio/[relId]/page.tsx:65` — `bg-gradient-to-br from-emerald-500/10 via-cyan-500/5 to-transparent`
  vira `bg-ok-surface`.
- `relatorio/[relId]/finalizar/page.tsx:137` — barra de progresso
  `bg-gradient-to-r from-emerald-500 to-teal-400` vira `bg-ok`.
- [ ] **Step 5: Apagar as 5 linhas da catraca (`Task 5`)**

- [ ] **Step 6: Rodar os testes**

Run: `npx vitest run`
Expected: PASS.

- [ ] **Step 7: Conferir na tela — inclusive a assinatura**

Abrir um relatório do dia com a conta que tem OS atribuída, ir até
`/relatorio/<id>/finalizar` no tema **claro**, e desenhar no campo de assinatura.
O traço tem que aparecer. Comparar a OS no escuro com `docs/baseline-escuro/os-4.png`.

- [ ] **Step 8: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao pwa/components/providers/AuthGuard.tsx
git commit -m "refactor(pwa): telas de OS, coleta e relatório passam aos tokens de estado"
```

---

### Task 6: Reescrever a camada de cor do login

**Files:**
- Modify: `app/login/page.tsx` (~40 classes de cor)
- Modify: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` (apagar 1 linha)
- Test: `app/tecnico/qualificacao/__tests__/LoginTema.test.tsx` (criar)

**Interfaces:**
- Consumes: tokens da Task 1.
- Produces: nada.

É a tela mais quebrada: no claro os rótulos, o valor digitado, o nome do banco e
o indicador de passo somem — `text-white/60` sobre `bg-card` branco. O usuário vê
um formulário sem rótulo e sem o que digitou.

- [ ] **Step 1: Escrever o teste que falha**

```tsx
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const SRC = readFileSync(join(__dirname, '..', '..', '..', '..', 'app/login/page.tsx'), 'utf8')

describe('login: legível nos dois temas', () => {
  it('nenhuma tinta branca absoluta', () => {
    // `text-white/60` sobre `bg-card` é branco sobre branco no tema claro:
    // o rótulo e o valor digitado somem da tela.
    expect(SRC).not.toMatch(/\b(?:text|bg|border|divide)-white(?:\/\d{1,3})?\b/)
  })

  it('as opções do seletor de banco não fixam fundo escuro', () => {
    // `bg-dark-800 text-white` num <option> entrega texto branco em lista
    // clara nos navegadores que respeitam o estilo da opção.
    expect(SRC).not.toMatch(/bg-dark-\d{3}/)
  })

  it('nenhuma shade crua de cor de estado', () => {
    expect(SRC).not.toMatch(/\b(?:text|bg|border)-(?:emerald|red|amber|cyan)-\d{2,3}\b/)
  })
})
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/LoginTema.test.tsx`
Expected: FAIL nos três casos.

- [ ] **Step 3: Trocar as classes**

Aplicar a tabela da Task 3. Específicos do login:

- `page.tsx:270` — trilho do indicador de passo `bg-white/10` vira `bg-muted`;
  o preenchimento `bg-foreground/30` vira `bg-ok` (o passo concluído é estado).
- `page.tsx:602` — `<option className="bg-dark-800 text-white">` perde a classe
  inteira: o `<option>` herda o esquema de cor do `<select>`, e o `color-scheme`
  do `<html>` (já correto depois da Task 2) faz o navegador pintar a lista.
- Mensagem de erro: `text-red-400` vira `text-danger`, sobre `bg-danger-surface`.
- Confirmação de servidor válido: `text-emerald-400` vira `text-ok`.

- [ ] **Step 4: Apagar a linha da catraca (`Task 6`)**

- [ ] **Step 5: Rodar os testes**

Run: `npx vitest run`
Expected: PASS. `LoginRedirect.test.tsx` continua verde — a troca é só de cor.

- [ ] **Step 6: Conferir na tela — é o teste de aceitação desta task**

```bash
agent-browser eval "localStorage.setItem('theme','light')"
agent-browser open http://localhost:3010/login
agent-browser screenshot /tmp/login-claro-1.png
```

No passo 1 têm que aparecer: rótulo do campo de servidor, placeholder e texto de
apoio. Preencher `http://localhost:8084`, avançar, e no passo 2: rótulos "Banco
de dados", "Usuário", "Senha", o nome do banco dentro do seletor, e o que for
digitado no campo de usuário. Comparar o escuro com `docs/baseline-escuro/login-1.png`
e `login-2.png`.

- [ ] **Step 7: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/login/page.tsx pwa/app/tecnico/qualificacao/__tests__
git commit -m "fix(pwa): login perdia rótulo e texto digitado no tema claro"
```

---

### Task 7: Declarar o visualizador como cromo escuro

**Files:**
- Modify: `components/ui/PdfViewerModal.tsx`
- Modify: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` (trocar 1 linha de curinga por exceções nomeadas)

**Interfaces:**
- Consumes: nada.
- Produces: nada.

Decisão de projeto, não conserto: o visualizador já se compromete com fundo
escuro (overlay `bg-black/85`, sombra pesada) porque foto de coleta e PDF se leem
melhor sobre escuro, nos dois temas. O defeito é ele misturar isso com
`bg-card`/`bg-muted`, que no tema claro viram branco **por baixo de texto
branco**. O conserto é assumir o escuro explicitamente, não tematizar o cromo.

- [ ] **Step 1: Escrever o teste que registra a decisão**

Acrescentar a `temaTokens.test.ts`:

```ts
describe('visualizador: superfície escura declarada', () => {
  const src = readFileSync(join(RAIZ, 'components/ui/PdfViewerModal.tsx'), 'utf8')

  it('o painel não usa superfície temática por baixo de tinta branca', () => {
    // `bg-card` + `text-white` = branco no branco quando o tema é claro.
    // Aqui o cromo é escuro DE PROPÓSITO: então a superfície tem que ser
    // escura de propósito também.
    expect(src).not.toMatch(/bg-(?:card|muted|background)\b/)
  })

  it('a decisão está escrita no arquivo', () => {
    expect(src).toMatch(/cromo escuro/i)
  })
})
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/temaTokens.test.ts -t visualizador`
Expected: FAIL nos dois.

- [ ] **Step 3: Fixar a superfície escura**

No topo do componente, um comentário que explique a exceção:

```tsx
/**
 * Cromo escuro nos dois temas, por decisão: foto de coleta e PDF se leem
 * melhor sobre fundo escuro, e o overlay já é `bg-black/85`. Por isso este é
 * o único arquivo que usa a família `dark-*` e tinta branca — e por isso ele
 * aparece nomeado em PERMITIDO_TEMA no teste do tema.
 */
```

Trocar `bg-card` do painel por `bg-dark-800`, `bg-muted` por `bg-dark-700`, e
`border-border` do cromo por `border-white/10`. As tintas `text-white*` ficam.

- [ ] **Step 4: Trocar a linha da catraca**

Remover `'components/ui/PdfViewerModal.tsx :: *': 'migração pendente (Task 7)'` e
pôr no lugar exceções nomeadas, com a justificativa de projeto:

```ts
  'components/ui/PdfViewerModal.tsx :: text-white': 'Cromo escuro declarado: o visualizador é escuro nos dois temas (overlay bg-black/85).',
  'components/ui/PdfViewerModal.tsx :: bg-dark-800': 'Cromo escuro declarado — superfície do painel do visualizador.',
  'components/ui/PdfViewerModal.tsx :: bg-dark-700': 'Cromo escuro declarado — superfície elevada dentro do visualizador.',
```

Acrescentar as demais classes brancas do arquivo (`text-white/40`, `border-white/10`,
…) uma a uma, cada qual com a mesma justificativa. **Nomeadas, não curinga**: o
curinga deixaria o arquivo livre para receber qualquer classe no futuro.

- [ ] **Step 5: Rodar os testes**

Run: `npx vitest run`
Expected: PASS. Se o teste de entrada morta reclamar, é classe que a lista prevê
e o arquivo não usa mais — apagar a linha.

- [ ] **Step 6: Conferir na tela**

No tema **claro**, abrir uma coleta com foto e clicar em "Ver foto"; depois uma
com planilha/PDF e clicar em "Baixar"/visualizar. Cabeçalho, nome do arquivo e
controles têm que estar legíveis sobre o painel escuro.

- [ ] **Step 7: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/components/ui/PdfViewerModal.tsx pwa/app/tecnico/qualificacao/__tests__
git commit -m "fix(pwa): visualizador assume cromo escuro em vez de misturar com superfície clara"
```

---

### Task 8: Fechar a catraca

**Files:**
- Modify: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts`

**Interfaces:**
- Consumes: Tasks 3–7 completas.
- Produces: a garantia de que classe crua nova falha o build.

- [ ] **Step 1: Confirmar que só sobraram as exceções do visualizador**

```bash
grep -n "migração pendente" app/tecnico/qualificacao/__tests__/temaTokens.test.ts
```

Expected: nenhuma linha. Se sobrar alguma, a task correspondente não terminou —
voltar nela em vez de apagar a linha.

- [ ] **Step 2 (novo): fechar os dois buracos que a migração revelou na guarda**

A Task 6 achou `placeholder-white/40` no login — o prefixo `placeholder` não está
em `PREFIXOS`, então a classe escapava das duas regras e só apareceu por grep
manual. Acrescente `placeholder` à constante, rode o teste, e trate toda violação
nova que aparecer (o critério é o de sempre: a task dona da tela).

O segundo buraco não tem conserto por regex e por isso precisa ficar escrito: o
indicador de passo do login usava `rgba(255,255,255,…)` **inline**, dentro das
props de animação do Framer Motion. Cor em objeto JavaScript não é classe e
nenhuma varredura de className a alcança — e o Framer não resolve variável CSS na
interpolação, então o token também não entra ali direto. Registre a limitação num
comentário no topo de `temaTokens.test.ts`, dizendo o que a guarda **não** cobre
(cor em `style`, em prop de animação, ou montada em string) e o que fazer no lugar
(classe token no elemento, animando só opacidade/transform).

- [ ] **Step 3: Provar que a catraca morde (teste de mutação)**

```bash
sed -i 's/className="flex items-center/className="flex items-center text-emerald-300/' \
  app/tecnico/qualificacao/_components/OsCard.tsx
npx vitest run app/tecnico/qualificacao/__tests__/temaTokens.test.ts
git checkout -- app/tecnico/qualificacao/_components/OsCard.tsx
```

Expected: FAIL nomeando `OsCard.tsx: \`text-emerald-300\` (shade crua de cor de
estado)`. Se passar, a guarda é decorativa — consertar o regex antes de seguir.
Reverter o arquivo depois (o `git checkout` acima já faz).

- [ ] **Step 4: Reauditar com o script de contraste**

```bash
node scripts/contrast-audit.mjs .           # criado na Task 9; se ainda não existir, adiar este passo para lá
```

Expected: as ocorrências que sobram são bordas decorativas e o visualizador.
Nenhuma classe `text-*` de estado abaixo de 4.5:1.

- [ ] **Step 5: Rodar a suíte inteira e o build de produção**

**Não** rodar `npm run build` com o dev server de pé — os dois usam `.next/` e o
build corrompe o servidor em execução. Parar antes:

```bash
~/.claude/bin/devserver stop 3010
npx vitest run
npm run build
```

Expected: testes PASS; build gerando as 17 rotas, sem erro de tipo.

- [ ] **Step 6: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/__tests__/temaTokens.test.ts
git commit -m "test(pwa): fecha a catraca do tema — só o visualizador segue como exceção"
```

---

### Task 9: Auditoria versionada, verificação visual e documentação

**Files:**
- Create: `scripts/contrast-audit.mjs`
- Modify: `package.json` (script `audit:contrast`)
- Create: `docs/AUDITORIA-CONTRASTE.md`
- Modify: `DESIGN.md` (§2 Colors **e a linha 388**)
- Modify: `TODO.md`

**Herdado de julgamentos das tasks anteriores — nada disto está nos Steps abaixo,
e some se você não fizer de propósito:**

1. **`DESIGN.md:388` afirma que o Signature Pad é a ÚNICA superfície branca fixa
   permitida no escuro. São TRÊS**: o pad, o logo da empresa no Perfil (ativo
   externo, logo escuro sobre branco) e a assinatura já capturada no detalhe do
   relatório (tinta preta fixa). As três estão em `PERMITIDO_TEMA`; o texto é que
   está desatualizado.
2. **Semear o relatório fechado.** A Task 5 deixou um relatório ABERTO na OS 4
   (`RQOS00033`/REL #2077). Feche-o: é o que gera o relatório fechado que faltava
   para ver o `RelatorioCard` do Histórico na tela — badge, ícone e hover nunca
   foram vistos por task nenhuma.
3. **Alcançar o `ReviewPanel` COM veredito renderizado.** A captura da Task 4 pegou
   o painel em estado "não executada", e por isso a deriva dos badges no escuro
   não apareceu em captura nenhuma.
4. **Comparar os dois visualizadores no tema claro.** "Ver foto" NÃO usa o
   `PdfViewerModal`: é um lightbox próprio em `CollectedCard.tsx:180-200`, com
   overlay preto e botão de fechar CLARO, enquanto o visualizador de PDF tem cromo
   escuro. Os dois são legíveis; a pergunta é se a incoerência estética incomoda.
   Registre o veredito, seja ele qual for.
5. **Olhar `--destructive` ao lado de `--danger` no tema claro.** A Task 13 escureceu
   `--danger` para red-800 e os dois passaram a divergir (`--destructive` segue
   red-700). São dois vermelhos para o mesmo significado. NÃO mude o token às
   cegas — `--destructive` também pinta botão preenchido com
   `--destructive-foreground` por cima. Coloque as duas cores na mesma tela, decida
   se a diferença aparece, e registre o veredito: convergir, ou documentar por que
   são dois.
6. **Corrigir dois números errados nos comentários de `app/globals.css`.** A revisão da
   Task 13 recalculou e achou: `--danger` está comentado como "7.94:1 na página,
   5.09:1 c/ hover" quando o valor HSL salvo dá **8.00 / 5.05** (a tabela foi
   calculada do hex do Tailwind, o arquivo guarda o HSL arredondado); e `--warn`
   diz "6.78:1" quando o real é **6.82:1** — esse já estava errado antes. Nenhum
   afeta o piso, mas a função inteira daquele comentário é documentar a aritmética.
7. **Minors diferidos a triar:** o badge "concluído" do `StepIndicator` do login usa
   `bg-ok-surface` (calibrado a 15%) onde o original era `rgba(emerald,0.20)`; o anel
   estático do spinner do `AuthGuard` ficou levemente mais escuro no tema escuro; o
   banco de dev não tem item `kind='pdf'` permanente.

**Interfaces:**
- Consumes: Tasks 1–8.
- Produces: `npm run audit:contrast`.

- [ ] **Step 1: Versionar o script de auditoria**

Copiar `docs/superpowers/plans/2026-09-06-contrast-audit.mjs` para
`scripts/contrast-audit.mjs`
(ele resolve a paleta do Tailwind e os tokens do `globals.css`, compõe a
opacidade sobre o fundo e calcula a razão WCAG; aceita `THEME=dark`). Trocar o
`import` dinâmico por `import resolveConfig from 'tailwindcss/resolveConfig.js'`,
já que rodando de dentro do projeto o pacote resolve.

**Duas armadilhas já corrigidas na cópia — não as reintroduza:**

- O regex do nome da classe tem que ser `[a-z]+(?:-[a-z]+)*(?:-\d{2,3})?`, nunca
  `[a-z-]+(?:-\d{2,3})?`: a primeira versão truncava `text-emerald-300` em
  `text-emerald-` e não achava nada.
- `resolveColor` tem que consultar `tokens[name]` direto. A primeira versão usava
  um mapa fixo de nomes semânticos, escrito antes dos tokens de estado existirem —
  e depois da migração quase toda classe da árvore virou token novo, cada uma
  caindo no `return null` e sendo pulada em silêncio. O relatório saía **limpo por
  cegueira**. Se a auditoria "depois" vier quase vazia, confirme antes que
  `text-ok` e `bg-ok-surface` resolvem para RGB de verdade.

**O `PdfViewerModal` é falso positivo por construção.** O script compõe tudo sobre
o fundo do tema; o visualizador tem cromo escuro declarado nos dois temas, então
suas classes brancas aparecem como ~1:1. Ou ensine o script a ignorar os arquivos
de cromo declarado, ou anote no relatório — mas não "conserte" o visualizador.

Em `package.json`, `"audit:contrast": "node scripts/contrast-audit.mjs ."`.

- [ ] **Step 2: Gravar a auditoria em `docs/AUDITORIA-CONTRASTE.md`**

Registrar: método (determinístico, sem browser), a limitação conhecida (o fundo é
inferido da mesma linha, então borda decorativa aparece como falso positivo), o
antes (397 no claro / 191 no escuro, 2026-09-06), o depois, e a tabela de valores
dos tokens com as razões medidas.

- [ ] **Step 3: Documentar o tema claro no `DESIGN.md`**

O §2 hoje descreve as cores de estado só em hex do tema escuro, e despacha o
claro em uma frase ("espelha os mesmos papéis"). Foi essa lacuna que deixou o
claro sair sem revisão. Reescrever o §2 para nomear os **tokens** como fonte da
verdade, com as duas colunas de valor e a razão de contraste de cada um, e
acrescentar a regra: *cor de estado só entra por token; shade do Tailwind em
componente é proibida, e o teste `temaTokens.test.ts` recusa.*

**E acrescentar as duas coisas que a guarda NÃO consegue impor** — são o
aprendizado mais durável deste trabalho, e morrem com o ledger se não forem
escritas aqui:

- **Opacidade numa classe de cor às vezes é papel, não ruído.** `text-X/80` ao lado
  de `text-X` costuma ser hierarquia (título vs. metadado); `text-X/60` com
  `group-hover:text-X` é interação. Apagar a opacidade apaga o papel. Este erro
  apareceu **seis vezes** na migração de 2026-09-06, em quatro telas diferentes, e
  nenhuma vez foi pego por teste: só por leitura. **Mas o papel só justifica
  opacidade onde não há piso** — em texto, o papel volta por tamanho ou peso de
  fonte, nunca por tinta (ver a correção no topo da tabela de tradução).
- **Cor fora de `className` é invisível para a guarda.** Cor em `style`, em prop de
  animação do Framer Motion, ou montada por concatenação de string não é alcançada
  por varredura nenhuma — e o Framer nem resolve variável CSS na interpolação. A
  saída é classe de token no elemento, animando só opacidade e transform.

Corrigir junto a linha 388 do `DESIGN.md`, que hoje afirma ser o Signature Pad a
**única** superfície branca fixa permitida no tema escuro. A Task 4 achou uma
segunda, legítima: o fundo branco do `<img>` do logo da empresa no Perfil — é
ativo externo, logo escuro sobre branco, e sem o fundo fixo ele some no escuro.
Já está registrada como exceção permanente em `PERMITIDO_TEMA`; falta o texto
parar de contradizer o código.

- [ ] **Step 4: Verificação visual final — as duas metades**

Com o servidor de dev de pé, para cada tema (`light` e `dark`) e cada rota
(`/login` passos 1 e 2, lista, OS 4, coleta com formulário aberto, histórico,
perfil, visualizador aberto): abrir, capturar, conferir.

Critério: no claro, nenhum texto some nem exige esforço; no escuro, a captura
bate com `docs/baseline-escuro/` a menos do escurecimento previsto dos textos que
eram `-300`.

**Semear o que falta antes de capturar.** A conta de teste não tem relatório
fechado nem segunda empresa, então três aplicações de token nunca foram vistas na
tela em task nenhuma: o `RelatorioCard` do Histórico (badge, ícone e hover do
relatório fechado) e o estado "selecionado" do seletor de "Empresa ativa" no
Perfil. Feche um relatório do dia na OS 4 para gerar o primeiro; se a segunda
empresa não for viável de semear, registre a limitação em vez de dar por
verificado.

**Estados que a verificação PRECISA alcançar** (a revisão da Task 3 mostrou que a
captura padrão passa por cima deles): o `ReviewPanel` com veredito renderizado —
na tela testada ele estava em "não executada", e por isso a deriva dos badges
`-200`/`-300` no escuro não apareceu em captura nenhuma; e o cabeçalho de grupo do
`EquipmentHeader` com título E metadado visíveis lado a lado, para confirmar que a
hierarquia entre os dois voltou.

- [ ] **Step 5: Atualizar o `TODO.md`**

Fechar os dois itens de contraste da seção "Design system" (`~~...~~` +
**Resolvido em 2026-09-06**), descrevendo o que era, o que foi medido e o que
trava a volta. Registrar as capturas em `docs/baseline-escuro/` e o
`npm run audit:contrast`.

- [ ] **Step 6: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/scripts pwa/package.json pwa/docs pwa/DESIGN.md pwa/TODO.md
git commit -m "docs(pwa): audita o contraste, documenta os tokens dos dois temas"
```

---

### Task 10: Deep link não pode perder o destino no login

**Files:**
- Create: `lib/navegacao.ts` (`destinoSeguro`)
- Modify: `middleware.ts`
- Modify: `app/login/page.tsx` (ler o destino e usá-lo no `router.replace` de sucesso)
- Test: `app/tecnico/qualificacao/__tests__/LoginRedirect.test.tsx` (estender)

**Interfaces:**
- Consumes: nada das tasks anteriores — independente, pode ser executada em paralelo.
- Produces: `destinoSeguro(next: string | null): string` em `lib/navegacao.ts`, e
  o parâmetro de query `?next=<pathname+search>` na rota `/login`.

Abrir `/tecnico/qualificacao/<osId>/coleta/<itemId>` sem sessão manda para o
login e, depois de autenticar, cai na home em vez da coleta pedida. Atrapalha
suporte ("abre este link") e o retorno do PWA depois de a sessão expirar.

- [ ] **Step 1: Escrever os testes que falham**

```tsx
  it('guarda o destino original ao expulsar para o login', () => {
    // middleware: rota protegida sem sessão -> /login?next=<destino>
    const req = new NextRequest('http://localhost:3010/tecnico/qualificacao/4/coleta/213')
    const res = middleware(req)
    const destino = new URL(res.headers.get('location')!)
    expect(destino.pathname).toBe('/login')
    expect(destino.searchParams.get('next')).toBe('/tecnico/qualificacao/4/coleta/213')
  })

  it('depois de autenticar vai para o destino guardado, sem deixar o login no histórico', () => {
    // `replace`, não `push`: o formulário de credenciais não pode sobreviver
    // no histórico (regra travada por navegacaoHistorico.test.ts).
    expect(replace).toHaveBeenCalledWith('/tecnico/qualificacao/4/coleta/213')
    expect(push).not.toHaveBeenCalled()
  })

  it('recusa destino externo (open redirect)', () => {
    // `?next=https://evil.example` faria o login mandar o técnico para fora.
    // Só caminho absoluto interno vale.
    const req = new NextRequest('http://localhost:3010/login?next=https://evil.example')
    expect(destinoSeguro(req.nextUrl.searchParams.get('next'))).toBe('/tecnico/qualificacao')
  })
```

Ajustar os mocks ao que `LoginRedirect.test.tsx` já monta (ele já mocka
`useRouter` com `replace`/`push`).

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/LoginRedirect.test.tsx`
Expected: FAIL — `next` vem `null`.

- [ ] **Step 3: Implementar**

No `middleware.ts`, ao redirecionar para `/login`, anexar
`next = req.nextUrl.pathname + req.nextUrl.search`.

Criar `lib/navegacao.ts` exportando `destinoSeguro` — mora em `lib/` e não
dentro da página porque o `middleware.ts` precisa da mesma função no dia em que
ecoar `next` de volta, e duas cópias da regra de segurança divergem. No
`app/login/page.tsx`, no sucesso da autenticação, usar
`router.replace(destinoSeguro(searchParams.get('next')))`, com:

```ts
/**
 * Só caminho interno vale. `?next=https://evil.example` transformaria o
 * login num open redirect: o técnico autentica e o app o joga para fora.
 * `//evil.example` também é URL absoluta para o navegador — daí o segundo teste.
 */
function destinoSeguro(next: string | null): string {
  if (!next) return '/tecnico/qualificacao'
  if (!next.startsWith('/') || next.startsWith('//')) return '/tecnico/qualificacao'
  return next
}
```

- [ ] **Step 4: Rodar os testes**

Run: `npx vitest run`
Expected: PASS, incluindo `navegacaoHistorico.test.ts` (segue `replace`).

- [ ] **Step 5: Conferir na tela**

Sair da sessão, abrir `http://localhost:3010/tecnico/qualificacao/4/coleta/213`,
autenticar. Tem que cair na coleta 213, não na lista. Depois testar
`?next=https://evil.example` na mão e confirmar que cai na lista.

- [ ] **Step 6: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/lib/navegacao.ts pwa/middleware.ts pwa/app/login/page.tsx \
        pwa/app/tecnico/qualificacao/__tests__
git commit -m "fix(pwa): login volta para o link que o técnico abriu"
```

---

### Task 11: Fechar os 5 avisos de `no-img-element`

**Files:**
- Modify: os arquivos que o `npm run lint` apontar (foto de coleta e logo)
- Modify: `next.config.mjs` se a foto vier de origem remota

**Interfaces:**
- Consumes: nada. Independente.
- Produces: nada.

- [ ] **Step 1: Listar os avisos**

Run: `npm run lint 2>&1 | grep -A2 no-img-element`
Anotar arquivo e linha de cada um dos 5.

- [ ] **Step 2: Decidir caso a caso, sem trocar cegamente**

`next/image` exige dimensões conhecidas e, para origem remota, entrada em
`images.remotePatterns`. Para foto de coleta que chega como **data URL** (base64
do Odoo), `next/image` não ajuda e a troca só acrescentaria custo — nesse caso a
decisão certa é `// eslint-disable-next-line @next/next/no-img-element` **com o
motivo escrito na linha de cima**, não a troca.

- [ ] **Step 3: Aplicar e conferir**

Run: `npm run lint`
Expected: nenhum aviso `no-img-element` — ou porque virou `next/image`, ou porque
está silenciado com justificativa.

- [ ] **Step 4: Conferir na tela que a imagem ainda aparece**

Abrir uma coleta com foto e o login (logo). As duas imagens têm que carregar.

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa
git commit -m "chore(pwa): fecha os avisos de no-img-element"
```

---

### Task 12: Formalizar o que o checklist descreve errado

**Files:**
- Modify: `app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md` (itens F.1, F.2, H3, A.3)
- Modify: `app/tecnico/qualificacao/page.tsx:23` (comentário)
- Modify: `TODO.md`

**Interfaces:**
- Consumes: nada. Independente.
- Produces: nada.

Duas decisões de 2026-09-04 ficaram registradas no `TODO.md` mas nunca chegaram
ao checklist, que segue descrevendo comportamento que o app não tem:

1. **F.1/F.2** prometem isolamento de **leitura** por técnico. Não existe: as
   `ir.rule` do grupo Técnico têm `perm_read = False`
   (`security/qualificacao_groups.xml:59`) — o escopo é só de escrita, e assim
   permanece por decisão. O técnico vê as OSs dos colegas ao desligar "Só minhas".
2. **H3/A.3** descrevem como se desligar o filtro sempre mostrasse *mais* cards.
   Rascunho alheio não entra: desligar serve para ver as OSs **em andamento e
   agendadas** dos colegas.

- [ ] **Step 1: Reescrever F.1 e F.2**

Trocar a expectativa de record rule pela do filtro de cliente: o que se verifica é
que "Só minhas" ligado mostra apenas as OSs do técnico autenticado, e que a
restrição de **escrita** (coletar em OS alheia) é recusada pelo servidor.

- [ ] **Step 2: Reescrever H3 e A.3**

Descrever o comportamento real: desligar "Só minhas" acrescenta as OSs em
andamento e agendadas dos colegas, e **não** acrescenta rascunho de ninguém.

- [ ] **Step 3: Comentar a intenção no código**

Em `app/tecnico/qualificacao/page.tsx:23`, sobre `filterMine ? drafts : []`:

```tsx
// Rascunho alheio não entra na lista do técnico: desligar "Só minhas" serve
// para ver as OSs EM ANDAMENTO e AGENDADAS dos colegas, não o rascunho de
// todo mundo. Decidido em 2026-09-04.
```

- [ ] **Step 4: Riscar os dois itens no `TODO.md`**

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md \
        pwa/app/tecnico/qualificacao/page.tsx pwa/TODO.md
git commit -m "docs(pwa): checklist passa a descrever o escopo real do filtro e das record rules"
```

---

### Task 13: devolver folga de contraste aos tokens de estado no tema claro

**Files:**
- Modify: `app/globals.css` (bloco `:root` apenas — o `:root.dark` não muda)
- Modify: `app/tecnico/qualificacao/__tests__/temaTokens.test.ts` (teste novo)

**Interfaces:**
- Consumes: os tokens da Task 1.
- Produces: nada de novo — os mesmos nomes, com valores mais escuros no claro.

**Ordem de execução: esta task roda DEPOIS da Task 8 e ANTES da Task 9**, porque
muda valores que a verificação visual e a auditoria da Task 9 precisam medir.

Achado pela auditoria corrigida, depois da migração: texto de estado sobre a
**própria** superfície tonal tem folga mínima no tema claro — `text-info` sobre
`bg-info-surface` dá 4.78:1, com o piso em 4.5. Qualquer tingimento de hover do
mesmo matiz come essa folga e derruba abaixo do piso. É o que acontece hoje em
`ReviewPanel.tsx:288` (`text-info` + `hover:bg-info/20` = **3.66:1**), e
aconteceria em qualquer chip que ganhasse hover depois.

Não é defeito de um componente: é falta de margem no token. Como só o tema claro
muda, **não há risco para o escuro**.

Valores medidos (contraste sobre a página / sobre a própria superfície / sobre a
superfície com hover a 20%):

| Token | Hoje | Novo | Efeito |
|---|---|---|---|
| `--info` | `193 82% 31%` (cyan-700) — 5.12 / 4.78 / **3.66** | `194 70% 27%` (cyan-800) | 6.86 / 6.40 / **4.75** |
| `--ok` | `163 94% 24%` (emerald-700) — 5.31 / 4.99 / **3.77** | `163 88% 20%` (emerald-800) | 7.25 / 6.80 / **5.00** |
| `--danger` | `0 74% 42%` (red-700) — 6.14 / 5.47 / **3.95** | `0 70% 35%` (red-800) | 7.94 / 7.03 / **5.09** |
| `--warn` | `23 83% 31%` (amber-800) — 6.82 / 6.50 / 4.77 | inalterado | já tem folga |

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `temaTokens.test.ts` um teste que calcule contraste de verdade — não
que compare strings. Ele resolve `--X` e `--X-surface` do `globals.css`, compõe o
tingimento de hover a 20%, e exige ≥4.5:1 nos dois temas:

```ts
describe('tema: token de estado tem folga para o hover do próprio matiz', () => {
  // Um chip `text-info` sobre `bg-info-surface` que ganha `hover:bg-info/20`
  // fica com texto e fundo do MESMO matiz se aproximando. Se o token não tiver
  // margem, o hover derruba abaixo do piso — foi o que aconteceu em
  // ReviewPanel.tsx:288 (3.66:1), achado pela auditoria de 2026-09-06.
  const hsl2rgb = (t: string) => { /* ... */ }
  const contraste = (a: number[], b: number[]) => { /* ... */ }
  const sobre = (fg: number[], alpha: number, bg: number[]) =>
    fg.map((c, i) => Math.round(c * alpha + bg[i] * (1 - alpha)))

  it.each(['ok', 'warn', 'danger', 'info'])(
    '--%s legível sobre a própria superfície, inclusive com hover a 20%%',
    (papel) => {
      for (const tema of [':root', ':root.dark']) {
        const fg = hsl2rgb(tokenDe(tema, papel))
        const bg = hsl2rgb(tokenDe(tema, `${papel}-surface`))
        expect(contraste(fg, bg)).toBeGreaterThanOrEqual(4.5)
        expect(contraste(fg, sobre(fg, 0.2, bg))).toBeGreaterThanOrEqual(4.5)
      }
    },
  )
})
```

Implemente `hsl2rgb`, `contraste` (luminância relativa WCAG) e `tokenDe` (lê o
bloco do `globals.css`) de verdade — o esqueleto acima marca onde entram.

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/temaTokens.test.ts -t folga`
Expected: FAIL para `ok`, `danger` e `info` no caso do hover (3.77, 3.95 e 3.66).
`warn` passa. Se `warn` falhar também, a sua implementação de contraste está
errada — confira contra os números da tabela acima antes de mexer nos tokens.

- [ ] **Step 2-A: fechar o último buraco de família da catraca**

A Task 8 achou a mesma assimetria que motivou `accent` e `placeholder`, agora em
FAMÍLIA em vez de prefixo: as regras não cobrem `gray|slate|zinc|neutral|stone`
nem `-black`. Há dois usos reais, os dois deliberados: `bg-black/85` e `/60` no
`PdfViewerModal` (cromo escuro declarado) e `bg-black/90` no lightbox de foto do
`CollectedCard.tsx:182`.

Acrescente as famílias e `black` às regras, rode, e cadastre esses usos como
exceções **nomeadas** em `PERMITIDO_TEMA` — overlay preto sobre conteúdo é
legítimo nos dois temas (é o que faz a foto e o PDF se lerem), e a justificativa
tem que dizer isso. Qualquer outro hit que aparecer é achado de verdade: trate.

- [ ] **Step 3: Escurecer os três tokens no bloco `:root`**

```css
  --ok:               163 88% 20%;   /* emerald-800 · 7.25:1 na página */
  --danger:           0 70% 35%;     /* red-800     · 7.94:1 */
  --info:             194 70% 27%;   /* cyan-800    · 6.86:1 */
```

Atualizar os comentários de cada linha com o número novo. **Não toque no
`:root.dark`** e não mexa em `--warn`.

- [ ] **Step 4: Rodar e confirmar verde**

Run: `npx vitest run`
Expected: PASS, suíte inteira. Nenhum outro teste deve quebrar — os que afirmam
qual CLASSE um elemento carrega não olham o valor do token.

- [ ] **Step 5: Conferir na tela que nada ficou escuro demais**

No tema **claro**, olhar o Histórico (contadores), a OS 4 (chips de ciclo, "Ver
foto"/"Baixar") e o `ReviewPanel`. Os tokens ficaram mais escuros: confirme que
continuam lendo como cor de estado e não como texto preto qualquer. No tema
**escuro**, confirmar que nada mudou — nenhum valor do `:root.dark` foi tocado.

- [ ] **Step 6: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/globals.css pwa/app/tecnico/qualificacao/__tests__/temaTokens.test.ts
git commit -m "fix(pwa): tokens de estado ganham folga p/ o hover do próprio matiz no tema claro"
```

---

## Fora de escopo (decidido em 2026-09-06)

- **Notificação push no celular** — levantado, não decidido. O custo não é o
  código, é decidir o que notifica e manter as assinaturas vivas.
- **Busca por nome do ciclo na lista de coletas** — decidido fora de escopo em
  2026-09-05.
- **Rotação da `GROQ_API_KEY`** e **TLS em produção** (`deploy/setup-pwa-proxy.sh`)
  — dependem do user: a chave precisa ser reemitida, e a chave SSH desta máquina é
  recusada em `191.252.113.190`.
- **Upgrade do labquali 16.0.7.0.0 → 16.0.7.4.0** — independente deste plano. O
  PWA é container próprio; o acoplamento é só o piso de versão do backend. Os
  achados de autorização já estão fechados no 7.4.0, então não há nada de backend
  para empacotar junto com estas correções de front.
