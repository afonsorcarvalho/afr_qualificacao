# PWA Técnico — painel esquerdo persistente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a coluna esquerda da OS sobreviver à navegação, para que a lista de coletas não volte ao topo a cada clique no desktop.

**Architecture:** Um route group `(painel)` passa a envolver `/[osId]` e `/[osId]/coleta/[itemId]`, e o `layout.tsx` desse grupo vira o dono do `SplitPane`, do `useOsDetail` e da coluna esquerda inteira. As duas páginas ficam com o conteúdo do painel direito e nada mais. As rotas de `relatorio/` ficam de fora do grupo, intactas.

**Tech Stack:** Next.js 14 App Router, React 18, TypeScript, Tailwind, Vitest + Testing Library + happy-dom.

**Spec:** `docs/superpowers/specs/2026-09-04-pwa-tecnico-painel-persistente-design.md`

## Global Constraints

- Todos os caminhos são relativos a `addons/afr_qualificacao/pwa/`.
- **As URLs não podem mudar.** Route group não vira segmento de caminho: `/tecnico/qualificacao/4` e `/tecnico/qualificacao/4/coleta/7` continuam existindo como estão. `npm run build` tem que continuar emitindo **17 rotas** — se mudar, algo saiu do lugar.
- **`selectedId` sai do `usePathname()`, nunca do `useParams()`.** Dentro do layout do grupo o segmento `itemId` está abaixo dele; `useParams()` devolve só `{ osId }`, e ler `itemId` dali dá `undefined` em silêncio.
- **O layout nunca faz early-return de carregando/erro.** Ele sempre renderiza o `SplitPane`; carregando e erro ocupam o painel da lista, com `{children}` montado. Early-return apagaria o painel direito, refazendo os achados 2 e 7 da revisão anterior.
- **Sem detectar viewport em JS**: nada de `matchMedia`, `window.innerWidth` ou `useEffect` decidindo o que renderizar.
- **Nunca esconder conteúdo atrás de animação de entrada** (`initial={{opacity:0}}`, `scale: 0`).
- **Estado nunca só por cor**: `aria-current` continua acompanhando o destaque da linha selecionada.
- Alvo de toque ≥44px em qualquer controle.
- Mudança só de front: **não** bumpar `__manifest__.py`, não tocar em `package.json`.
- Testes de componente levam `// @vitest-environment happy-dom` na primeira linha e `/// <reference types="@testing-library/jest-dom" />` na segunda (o `tsconfig.json` exclui `tests/**`; sem isso o `tsc --noEmit` quebra).
- Baseline: **17 arquivos / 80 testes verdes**, `tsc` limpo, build com 17 rotas.
- Commits sempre de dentro de `addons/afr_qualificacao/` (é submodule), com `git push origin main`, **staging só dos paths que a task lista** — `git add .` nunca, a árvore tem muitos arquivos alheios não rastreados. O bump do pointer no monorepo é a última task.

---

### Task 1: Provar que o layout de segmento persiste

**Files:**
- Create (temporário, apagado no fim da task): `app/tecnico/qualificacao/[osId]/layout.tsx`

Esta task não entrega código. Ela responde a pergunta de que o plano inteiro depende: **o Next preserva a instância do layout entre `/[osId]` e `/[osId]/coleta/[itemId]`?** É o comportamento documentado do App Router, e o `layout.tsx` de `/tecnico/qualificacao` já depende disso, mas o custo de provar é cinco minutos e o custo de errar são as tasks 2 a 4 inteiras.

- [ ] **Step 1: Criar o layout-esqueleto**

```tsx
'use client'
import { useEffect, useRef } from 'react'

export default function ProvaLayout({ children }: { children: React.ReactNode }) {
  const montagens = useRef(0)
  useEffect(() => {
    montagens.current += 1
    console.log('[PROVA] layout montou, total =', montagens.current)
  }, [])
  return <>{children}</>
}
```

- [ ] **Step 2: Navegar entre as duas rotas com o console aberto**

O servidor de dev já roda em `http://localhost:3010` a partir de `addons/afr_qualificacao/pwa`, e o Odoo responde em `http://localhost:8084` (db `qualificacao-dev`). Credenciais em `~/.config/engenapp/secrets.md` — nunca escrever credencial em arquivo, commit ou relatório.

Com `agent-browser`: abrir a OS 4 (`/tecnico/qualificacao/4`), ler o console, clicar numa coleta, ler o console de novo.

- [ ] **Step 3: Ler o veredicto**

- **Uma** linha `[PROVA] layout montou` nas duas rotas → a premissa se confirma, seguir para a Task 2.
- **Duas** linhas (uma por navegação) → o layout remonta, o hoist não compra nada. **Parar aqui e reportar BLOCKED** com o que se viu; o plano morre e o item volta pro TODO com a descoberta anotada.

- [ ] **Step 4: Apagar o layout-esqueleto**

```bash
rm "app/tecnico/qualificacao/[osId]/layout.tsx"
```

Nada é commitado nesta task. Confirmar com `git status --short` que a árvore voltou ao que era.

---

### Task 2: Mover para `(painel)` e hoistar a coluna esquerda

**Files:**
- Create: `app/tecnico/qualificacao/[osId]/(painel)/layout.tsx`
- Move: `app/tecnico/qualificacao/[osId]/page.tsx` → `app/tecnico/qualificacao/[osId]/(painel)/page.tsx`
- Move: `app/tecnico/qualificacao/[osId]/coleta/[itemId]/page.tsx` → `app/tecnico/qualificacao/[osId]/(painel)/coleta/[itemId]/page.tsx`
- Create: `app/tecnico/qualificacao/__tests__/PainelLayout.test.tsx`
- Modify: `app/tecnico/qualificacao/__tests__/ColetaPage.test.tsx`

**Interfaces:**
- Consumes: `SplitPane({list, narrow, children})`, `ColetaList({data, osId, selectedId})`, `EmptyDetail()`, `RelatorioHeader`, `ReviewPanel` — todos inalterados.
- Produces: `(painel)/layout.tsx` como dono de `useOsDetail`, dos handlers da OS e da coluna esquerda.

Usar `git mv` para mover os arquivos, para o histórico seguir a renomeação.

- [ ] **Step 1: Escrever o teste do layout que falha**

Criar `app/tecnico/qualificacao/__tests__/PainelLayout.test.tsx`. Ele cobre o que **muda de dono** (achados 3 e 7 da revisão anterior, que hoje são asseridos contra a página e passariam a não ser asseridos em lugar nenhum) mais as garantias novas:

```tsx
// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PainelLayout from '../[osId]/(painel)/layout'
import * as hooks from '@/lib/hooks/useTecnicoQualif'

let pathname = '/tecnico/qualificacao/4'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ osId: '4' }),
  usePathname: () => pathname,
}))

vi.mock('@/lib/hooks/useTecnicoQualif', async () => {
  const actual = await vi.importActual<typeof import('@/lib/hooks/useTecnicoQualif')>(
    '@/lib/hooks/useTecnicoQualif',
  )
  return {
    ...actual,
    useOsDetail: vi.fn(),
    useStartDailyRelatorio: vi.fn(),
  }
})

const osDetailData = {
  os: { id: 4, name: 'OS26-06-0002', partner_id: [2, 'Hospital X'] },
  open_relatorio_id: 99,
  equipments: {},
  instruments: {},
  qualifs: {},
  collect_items: [
    {
      id: 7, name: 'Ciclo 7', kind: 'foto', required: true, state: 'pending',
      description: '', instruction: '', requires_instrument: false,
      docx_section: false, qualif_id: false, equipment_id: [10, 'Autoclave A'],
    },
    {
      id: 8, name: 'Ciclo 8', kind: 'foto', required: true, state: 'pending',
      description: '', instruction: '', requires_instrument: false,
      docx_section: false, qualif_id: false, equipment_id: [10, 'Autoclave A'],
    },
  ],
} as any

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  pathname = '/tecnico/qualificacao/4'
  vi.mocked(hooks.useStartDailyRelatorio).mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as any)
})

describe('PainelLayout', () => {
  it('achado 3 (agora do layout): mostra nome e parceiro da OS acima da lista', () => {
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: osDetailData, isLoading: false, isFetching: false, error: null,
      refetch: vi.fn(),
    } as any)
    wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByText('OS26-06-0002')).toBeInTheDocument()
    expect(screen.getByText('Hospital X')).toBeInTheDocument()
  })

  it('achado 7 (agora do layout): enquanto a OS carrega, o painel direito continua montado', () => {
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: undefined, isLoading: true, isFetching: true, error: null,
      refetch: vi.fn(),
    } as any)
    wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByText('Carregando OS...')).toBeInTheDocument()
    // A regra que o early-return quebrava: children NUNCA some.
    expect(screen.getByText('painel direito')).toBeInTheDocument()
  })

  it('erro também não derruba o painel direito', () => {
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: undefined, isLoading: false, isFetching: false,
      error: new Error('falhou'), refetch: vi.fn(),
    } as any)
    wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByText(/Erro ao carregar OS/)).toBeInTheDocument()
    expect(screen.getByText('painel direito')).toBeInTheDocument()
  })

  it('selectedId vem do pathname, não do useParams', () => {
    pathname = '/tecnico/qualificacao/4/coleta/7'
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: osDetailData, isLoading: false, isFetching: false, error: null,
      refetch: vi.fn(),
    } as any)
    wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByRole('link', { name: /Ciclo 7/ })).toHaveAttribute(
      'aria-current', 'true',
    )
    expect(screen.getByRole('link', { name: /Ciclo 8/ })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('narrow segue a rota: detail na coleta, list fora dela', () => {
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: osDetailData, isLoading: false, isFetching: false, error: null,
      refetch: vi.fn(),
    } as any)
    const { container, unmount } = wrap(<PainelLayout><p>d</p></PainelLayout>)
    // Sem /coleta/ no pathname: a lista é o lado visível em tela estreita.
    expect(
      (container.querySelector('[data-pane="list"]') as HTMLElement).className,
    ).not.toContain('hidden')
    unmount()

    pathname = '/tecnico/qualificacao/4/coleta/7'
    const { container: c2 } = wrap(<PainelLayout><p>d</p></PainelLayout>)
    expect(
      (c2.querySelector('[data-pane="list"]') as HTMLElement).className,
    ).toContain('hidden')
  })
})
```

- [ ] **Step 2: Rodar o teste e ver falhar**

```bash
cd addons/afr_qualificacao/pwa
npx vitest run app/tecnico/qualificacao/__tests__/PainelLayout.test.tsx
```

Esperado: FAIL — `Failed to resolve import "../[osId]/(painel)/layout"`.

- [ ] **Step 3: Mover os dois arquivos para o grupo**

```bash
cd addons/afr_qualificacao/pwa/app/tecnico/qualificacao
mkdir -p "[osId]/(painel)/coleta"
git mv "[osId]/page.tsx" "[osId]/(painel)/page.tsx"
git mv "[osId]/coleta/[itemId]" "[osId]/(painel)/coleta/[itemId]"
rmdir "[osId]/coleta"
```

Conferir que `[osId]/relatorio/` **não** se moveu.

- [ ] **Step 4: Corrigir a profundidade dos imports relativos**

| Arquivo | De | Para |
|---|---|---|
| `(painel)/page.tsx` | `../_components/X` | `../../_components/X` |
| `(painel)/coleta/[itemId]/page.tsx` | `../../../_components/X` | `../../../../_components/X` |

Imports por alias (`@/lib/...`, `@/components/...`) não mudam.

- [ ] **Step 5: Criar o `(painel)/layout.tsx` com a coluna esquerda**

O corpo vem inteiro do que hoje é `(painel)/page.tsx`: o mesmo `useOsDetail`, os mesmos handlers e **o mesmo markup, na mesma ordem** — Voltar, identidade da OS, `RelatorioHeader`, `ReviewPanel`, bloco de conclusão, `ColetaList`, botão "Finalizar relatório do dia". Nada de reescrever markup nesta task; se um bloco mudar de aparência ou de posição, a task está errada.

As três diferenças em relação ao que a página fazia:

```tsx
// 1. `narrow` deixa de ser fixo: segue a rota.
const pathname = usePathname()
const emColeta = pathname.includes('/coleta/')

// 2. `selectedId` sai do pathname — dentro deste layout o segmento `itemId`
//    está abaixo, então `useParams()` devolve só { osId } e ler `itemId` dali
//    daria undefined em silêncio, apagando o marcador da linha aberta.
const m = pathname.match(/\/coleta\/(\d+)/)
const selectedId = m ? parseInt(m[1], 10) : undefined

// 3. Carregando e erro NÃO fazem early-return: ocupam o painel da lista, com
//    {children} montado. Early-return apagaria o painel direito junto — foram
//    os achados 2 e 7 da revisão do layout desktop.
const listaEsquerda = isLoading ? (
  <LoadingState label="Carregando OS..." />
) : error || !data ? (
  <p className="text-center text-red-400">Erro ao carregar OS</p>
) : (
  <div className="space-y-4">{/* ...a coluna esquerda de sempre... */}</div>
)

return (
  <SplitPane narrow={emColeta ? 'detail' : 'list'} list={listaEsquerda}>
    {children}
  </SplitPane>
)
```

Os handlers (`handleStart`, `handleContinue`, `handleFinalize`) e o `useTransition` do finalizar vão junto, sem alteração. Como agora eles vivem acima do early-return que não existe mais, garantir que nenhum hook fique dentro de condicional.

- [ ] **Step 6: Esvaziar as duas páginas**

`(painel)/page.tsx` inteiro:

```tsx
import { EmptyDetail } from '../../_components/EmptyDetail'

export default function OsDetailPage() {
  return <EmptyDetail />
}
```

`(painel)/coleta/[itemId]/page.tsx`: tirar o `SplitPane`, o `ColetaList`, o bloco de identidade da OS e a variável `lista` — tudo isso agora é do layout. A página passa a devolver diretamente o que hoje é o conteúdo do painel direito: o `LoadingState` de `if (!item)`, a mensagem de `if (!relatorioId)` e o formulário. O `useOsDetail` **continua** na página, porque `relatorioId` vem dele.

- [ ] **Step 7: Migrar `ColetaPage.test.tsx`**

- Trocar o import para `'../[osId]/(painel)/coleta/[itemId]/page'`.
- Adicionar `usePathname` ao mock de `next/navigation` (o componente pode não usar, mas o mock precisa ser completo se algum filho usar).
- **Remover** os casos dos achados 3 e 7: essas garantias passaram para `PainelLayout.test.tsx` no Step 1, e contra a página isolada elas agora falham por desenho.
- **Manter** o caso do achado 1 (salvar chama `router.replace` para a rota da OS, não `router.back()`).
- O caso do achado 2 vira: enquanto a coleta carrega, a página devolve o `LoadingState` — sem `SplitPane`, que agora é do layout.

Cada remoção ganha um comentário de uma linha dizendo para onde a garantia foi.

- [ ] **Step 8: Rodar tudo**

```bash
npx vitest run app/tecnico/qualificacao/__tests__/PainelLayout.test.tsx
npx vitest run app/tecnico/qualificacao/__tests__/ColetaPage.test.tsx
npm test
npx tsc --noEmit
npm run build
```

Esperado: todos verdes, `tsc` limpo, e o build **com 17 rotas** — o route group não pode ter mudado a contagem.

- [ ] **Step 9: Commit**

```bash
cd addons/afr_qualificacao
git add "pwa/app/tecnico/qualificacao/[osId]" \
        pwa/app/tecnico/qualificacao/__tests__/PainelLayout.test.tsx \
        pwa/app/tecnico/qualificacao/__tests__/ColetaPage.test.tsx
git status --short   # conferir que nada alheio entrou
git commit -m "refactor(pwa): hoist the OS left column into a (painel) layout

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

### Task 3: Conferência visual do ganho

**Files:**
- Modify: `pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md`

O critério de aceitação deste plano não é coberto por teste unitário. Se algo quebrar, o conserto entra nesta task, com o teste correspondente.

Ambiente: dev server em `http://localhost:3010` (a partir de `addons/afr_qualificacao/pwa`), Odoo em `http://localhost:8084`, db `qualificacao-dev`, OS26-06-0002 (id 4, 24 coletas). Credenciais em `~/.config/engenapp/secrets.md` — nunca escrever credencial em arquivo, commit ou relatório.

- [ ] **Step 1: O ganho, em 1280×800**

```bash
agent-browser viewport 1280 800
agent-browser open http://localhost:3010/tecnico/qualificacao/4
agent-browser snapshot -i
```

Rolar o painel da lista até por volta do item 20, clicar nele, e conferir:
- o painel **não** pulou para o topo;
- a linha marcada (`aria-current="true"`) continua visível;
- o formulário abriu à direita.

Este é o passo que justifica o plano inteiro. Registrar o valor de `scrollTop` antes e depois do clique como evidência, não uma impressão.

- [ ] **Step 2: `relatorio/` ficou fora do grupo**

Ainda em 1280×800, abrir a tela de finalizar turno. Ela tem que aparecer como coluna larga centrada, **sem lista ao lado** e sem `SplitPane`.

- [ ] **Step 3: O spinner que atravessa a fronteira**

Clicar em "Finalizar relatório do dia" e observar o botão: ele dispara `useTransition` num componente (o layout) que está sendo desmontado pela navegação para fora do grupo. Confirmar que o spinner acende e que nada trava nem pisca.

Conferir também que o `RelatorioHeader` não pisca (`isFetching && !isLoading`) enquanto se preenche uma coleta.

- [ ] **Step 4: Regressão de celular, 390×844**

```bash
agent-browser viewport 390 844
```

Percorrer home → OS → coleta → salvar. Tem que estar **idêntico**: coluna única, mesma ordem de blocos (Voltar, identidade, RelatorioHeader, lista, Finalizar), sem sinal da lista na tela de coleta. A afirmação central deste desenho no celular é "nada muda".

- [ ] **Step 5: Registrar e commitar**

Escrever no checklist o que foi conferido, com os números do Step 1. Depois:

```bash
cd addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md
git commit -m "docs(pwa): record the persistent-panel verification

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

### Task 4: Fechar o TODO e bumpar o pointer

**Files:**
- Modify: `pwa/TODO.md`
- Modify: `addons/afr_qualificacao` (pointer, no repo `odoo_engenapp`)

- [ ] **Step 1: Marcar o item como resolvido**

Em `pwa/TODO.md`, o item "**Lista volta ao topo a cada clique no desktop**" passa a `~~riscado~~` com **Resolvido em 2026-09-04**, uma frase do que foi feito (route group `(painel)` + layout dono da coluna esquerda) e o ponteiro para `docs/superpowers/specs/2026-09-04-pwa-tecnico-painel-persistente-design.md`.

- [ ] **Step 2: Commit e push no submodule**

```bash
cd addons/afr_qualificacao
git add pwa/TODO.md
git commit -m "docs(pwa): close the list-remount item

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
git rev-parse HEAD origin/main   # têm que bater
```

- [ ] **Step 3: Bump do pointer**

Só depois de confirmar que `HEAD == origin/main` no submodule:

```bash
cd /home/afonso/docker/odoo_engenapp
git add addons/afr_qualificacao
git commit -m "chore: bump submodule afr_qualificacao (painel esquerdo persistente)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push
```
