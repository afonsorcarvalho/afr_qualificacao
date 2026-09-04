# PWA Técnico — Layout desktop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o PWA do técnico usar a tela do notebook — coluna que cresce por breakpoint, navegação lateral em desktop e painel lista+detalhe dentro da OS — sem perder nada do comportamento em celular.

**Architecture:** A casca (`layout.tsx`) vira flex-row em `lg`, com a navegação extraída para um componente de duas variantes (barra inferior em telas estreitas, coluna lateral em desktop). Dentro da OS, as duas rotas existentes (`/[osId]` e `/[osId]/coleta/[itemId]`) passam a renderizar a mesma casca `SplitPane` com a lista de coletas extraída para `ColetaList`; a escolha de qual lado aparece em tela estreita é **CSS puro**, sem detectar viewport em JS — nada de estado de seleção no client, nada de parallel/intercepting routes. Clicar numa coleta continua sendo navegação de rota real.

**Tech Stack:** Next.js 14 App Router, React 18, TypeScript, Tailwind, Vitest + Testing Library + happy-dom, `clsx`, `lucide-react`.

**Spec:** `docs/superpowers/specs/2026-09-04-pwa-tecnico-layout-desktop-design.md`

## Global Constraints

- Todos os caminhos deste plano são relativos a `addons/afr_qualificacao/pwa/`.
- Breakpoints são os padrão do Tailwind: `sm` = 640px, `lg` = 1024px. Não criar breakpoint customizado.
- Larguras: `<640` → `max-w-[480px]`; `640–1023` → `max-w-[720px]`; `≥1024` → sidebar de `200px` + área de conteúdo; dentro da OS `grid-cols-[minmax(320px,380px)_1fr]` com `max-w-[1440px]`; fora da OS `max-w-[880px]`.
- **Alvo de toque mínimo 44px em qualquer controle**, inclusive na navegação lateral (`min-h-[44px]`).
- **Estado nunca só por cor** (DESIGN.md, "A Regra do Par"): a linha selecionada precisa de `aria-current` além do fundo.
- **Sem detectar viewport em JS.** Nada de `matchMedia`, `window.innerWidth` ou `useEffect` decidindo o que renderizar — o servidor renderiza o mesmo HTML que o cliente hidrata. Visibilidade é classe Tailwind (`hidden` / `lg:block` / `lg:hidden`).
- **Nunca esconder conteúdo atrás de animação de entrada** (`initial={{opacity:0}}`), regra explícita do DESIGN.md.
- Mudança só de front **não** bumpa `__manifest__.py`; a versão do PWA vive no `package.json`.
- Baseline de testes: `npm test` roda 11 arquivos / 38 testes verdes hoje (`pwa/docs/BASELINE.md`). Não há falha ambiental — qualquer falha nova é regressão.
- Testes de componente usam `// @vitest-environment happy-dom` na primeira linha do arquivo (o `vitest.config.ts` roda em `node` por padrão).
- Commits sempre de dentro de `addons/afr_qualificacao/` (é submodule), com `git push origin main`. O bump do pointer no monorepo é feito uma vez só, na Task 7.

---

### Task 1: Casca responsiva e navegação em duas variantes

**Files:**
- Create: `app/tecnico/qualificacao/_components/TecnicoNav.tsx`
- Create: `app/tecnico/qualificacao/__tests__/TecnicoNav.test.tsx`
- Modify: `app/tecnico/qualificacao/layout.tsx`

**Interfaces:**
- Consumes: `useNavProgress` de `@/components/providers/NavProgress` (tem valor default no contexto, então funciona sem provider em teste).
- Produces:
  - `NAV_ITEMS: { href: string; label: string; icon: LucideIcon }[]`
  - `TecnicoNav({ variant }: { variant: 'bottom' | 'side' })`

- [ ] **Step 1: Escrever o teste que falha**

Criar `app/tecnico/qualificacao/__tests__/TecnicoNav.test.tsx`:

```tsx
// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TecnicoNav } from '../_components/TecnicoNav'

const push = vi.fn()
let pathname = '/tecnico/qualificacao'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, back: vi.fn() }),
  usePathname: () => pathname,
}))

describe('TecnicoNav', () => {
  beforeEach(() => {
    pathname = '/tecnico/qualificacao'
    push.mockClear()
  })

  it('renderiza os três destinos com href correto', () => {
    render(<TecnicoNav variant="bottom" />)
    expect(screen.getByRole('link', { name: /OSs/ })).toHaveAttribute(
      'href',
      '/tecnico/qualificacao',
    )
    expect(screen.getByRole('link', { name: /Histórico/ })).toHaveAttribute(
      'href',
      '/tecnico/qualificacao/historico',
    )
    expect(screen.getByRole('link', { name: /Perfil/ })).toHaveAttribute(
      'href',
      '/tecnico/qualificacao/perfil',
    )
  })

  it('marca aria-current no destino ativo', () => {
    pathname = '/tecnico/qualificacao/historico'
    render(<TecnicoNav variant="bottom" />)
    expect(screen.getByRole('link', { name: /Histórico/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: /OSs/ })).not.toHaveAttribute('aria-current')
  })

  it('todo item tem alvo de toque de 44px em qualquer variante', () => {
    const { unmount } = render(<TecnicoNav variant="bottom" />)
    for (const link of screen.getAllByRole('link')) {
      expect(link.className).toContain('min-h-[44px]')
    }
    unmount()
    render(<TecnicoNav variant="side" />)
    for (const link of screen.getAllByRole('link')) {
      expect(link.className).toContain('min-h-[44px]')
    }
  })

  it('variante bottom é barra fixa embaixo e some em lg', () => {
    const { container } = render(<TecnicoNav variant="bottom" />)
    const nav = container.querySelector('nav') as HTMLElement
    expect(nav.className).toContain('sticky')
    expect(nav.className).toContain('bottom-0')
    expect(nav.className).toContain('lg:hidden')
  })

  it('variante side é coluna vertical, só visível em lg, sem sombra flutuante', () => {
    const { container } = render(<TecnicoNav variant="side" />)
    const nav = container.querySelector('nav') as HTMLElement
    expect(nav.className).toContain('hidden')
    expect(nav.className).toContain('lg:flex')
    expect(nav.className).toContain('flex-col')
    expect(nav.className).toContain('border-r')
    expect(nav.className).not.toContain('shadow-[0_-8px_24px')
  })
})
```

- [ ] **Step 2: Rodar o teste e ver falhar**

```bash
cd addons/afr_qualificacao/pwa
npx vitest run app/tecnico/qualificacao/__tests__/TecnicoNav.test.tsx
```

Esperado: FAIL — `Failed to resolve import "../_components/TecnicoNav"`.

- [ ] **Step 3: Criar `TecnicoNav.tsx`**

Criar `app/tecnico/qualificacao/_components/TecnicoNav.tsx` movendo `BottomNav` e `NavItem` de `layout.tsx` (mesma lógica de ativo, mesmo `useTransition`, mesmo spinner):

```tsx
'use client'
import { useTransition } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { ClipboardList, BarChart3, User, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useNavProgress } from '@/components/providers/NavProgress'

const ROOT_PATH = '/tecnico/qualificacao'

export const NAV_ITEMS = [
  { href: ROOT_PATH, label: 'OSs', Icon: ClipboardList },
  { href: `${ROOT_PATH}/historico`, label: 'Histórico', Icon: BarChart3 },
  { href: `${ROOT_PATH}/perfil`, label: 'Perfil', Icon: User },
] as const

function useActiveHref() {
  const pathname = usePathname()
  const isHist = pathname.startsWith(`${ROOT_PATH}/historico`)
  const isPerfil = pathname.startsWith(`${ROOT_PATH}/perfil`)
  if (isHist) return `${ROOT_PATH}/historico`
  if (isPerfil) return `${ROOT_PATH}/perfil`
  return pathname.startsWith(ROOT_PATH) ? ROOT_PATH : ''
}

/**
 * Navegação principal do app, em duas variantes.
 *
 * `bottom` é o padrão de polegar: barra fixa no rodapé, do celular ao tablet.
 * `side` é o padrão de mouse: coluna à esquerda a partir de 1024px, onde um
 * rodapé fixo ficaria longe do olho e do cursor. A sombra "Sobreposto" do
 * DESIGN.md §4 só vale pra elemento que flutua sobre conteúdo rolável — a
 * coluna lateral não flutua, então separa por fio de 1px.
 *
 * As duas variantes são renderizadas sempre; quem escolhe é o CSS
 * (`lg:hidden` / `hidden lg:flex`). Detectar viewport em JS quebraria a
 * hidratação e é proibido pelo plano.
 */
export function TecnicoNav({ variant }: { variant: 'bottom' | 'side' }) {
  const activeHref = useActiveHref()
  const isSide = variant === 'side'
  return (
    <nav
      className={clsx(
        'bg-card',
        isSide
          ? 'hidden w-[200px] shrink-0 flex-col gap-1 border-r border-border p-3 lg:flex'
          : 'sticky bottom-0 flex justify-around border-t border-border px-2 py-1 text-xs shadow-[0_-8px_24px_rgba(0,0,0,0.45)] lg:hidden',
      )}
    >
      {NAV_ITEMS.map(({ href, label, Icon }) => (
        <NavItem
          key={href}
          href={href}
          active={activeHref === href}
          label={label}
          icon={<Icon className="h-5 w-5" aria-hidden />}
          isSide={isSide}
        />
      ))}
    </nav>
  )
}

function NavItem({
  href,
  active,
  icon,
  label,
  isSide,
}: {
  href: string
  active: boolean
  icon: React.ReactNode
  label: string
  isSide: boolean
}) {
  const router = useRouter()
  const { begin } = useNavProgress()
  const [isPending, startTransition] = useTransition()
  return (
    <a
      href={href}
      aria-current={active ? 'page' : undefined}
      aria-busy={isPending || undefined}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
        e.preventDefault()
        if (active || isPending) return
        begin()
        startTransition(() => router.push(href))
      }}
      className={clsx(
        'flex min-h-[44px] items-center rounded-md transition-colors',
        isSide
          ? 'gap-3 px-3 text-sm'
          : 'flex-1 flex-col justify-center gap-0.5',
        active
          ? 'font-semibold text-foreground'
          : 'text-muted-foreground hover:text-foreground',
        isSide && active && 'bg-accent',
      )}
    >
      {isPending ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> : icon}
      {label}
    </a>
  )
}
```

- [ ] **Step 4: Rodar o teste e ver passar**

```bash
npx vitest run app/tecnico/qualificacao/__tests__/TecnicoNav.test.tsx
```

Esperado: PASS, 5 testes.

- [ ] **Step 5: Reescrever a casca em `layout.tsx`**

Em `app/tecnico/qualificacao/layout.tsx`: apagar as funções `BottomNav` e `NavItem` do arquivo, importar `TecnicoNav`, e trocar o JSX do `return` do `TecnicoLayout` por:

```tsx
  return (
    <NavProgressProvider>
      <div className="mx-auto flex min-h-screen w-full max-w-[480px] flex-col bg-background sm:max-w-[720px] lg:h-dvh lg:min-h-0 lg:max-w-none lg:flex-row lg:overflow-hidden">
        <TecnicoNav variant="side" />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-10 border-b border-border bg-card shadow-md lg:static lg:shadow-none">
            <div className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-2">
                <Wrench className="h-5 w-5 text-foreground" />
                <span className="font-semibold">Qualificação · Técnico</span>
              </div>
            </div>
            {/* Toda navegação acende esta barra até a rota nova aparecer. */}
            <NavProgressBar />
          </header>
          <main className="flex-1 overflow-auto p-3">{children}</main>
          <TecnicoNav variant="bottom" />
        </div>
      </div>
    </NavProgressProvider>
  )
```

Os imports de `ClipboardList`, `BarChart3`, `User`, `Loader2`, `clsx` e `useTransition` deixam de ser usados em `layout.tsx` — remover. Ficam `Wrench`, `useEffect`, `usePathname`, `useRouter`, `useTecnicoSettings`, `NavProgressBar`, `NavProgressProvider`. O `useNavProgress` também sai do import.

Nada da lógica de `useEffect` (session-info, tecla Esc) muda.

- [ ] **Step 6: Dar largura de desktop às telas fora da OS**

Nestes quatro arquivos, no `<div>` mais externo do `return`, acrescentar `mx-auto w-full max-w-[880px]` às classes existentes:

- `app/tecnico/qualificacao/page.tsx`
- `app/tecnico/qualificacao/historico/page.tsx`
- `app/tecnico/qualificacao/perfil/page.tsx`
- `app/tecnico/qualificacao/[osId]/relatorio/[relId]/finalizar/page.tsx`

Exemplo do que a mudança parece (`className="space-y-4"` → `className="mx-auto w-full max-w-[880px] space-y-4"`). Se o arquivo tiver retornos antecipados (`isLoading`, `error`), deixar como estão — são blocos curtos e centrados.

- [ ] **Step 7: Rodar a suíte inteira**

```bash
npm test
```

Esperado: 12 arquivos / 43 testes, todos verdes (11/38 da baseline + o arquivo novo com 5).

- [ ] **Step 8: Commit**

```bash
cd addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/_components/TecnicoNav.tsx \
        pwa/app/tecnico/qualificacao/__tests__/TecnicoNav.test.tsx \
        pwa/app/tecnico/qualificacao/layout.tsx \
        pwa/app/tecnico/qualificacao/page.tsx \
        pwa/app/tecnico/qualificacao/historico/page.tsx \
        pwa/app/tecnico/qualificacao/perfil/page.tsx \
        "pwa/app/tecnico/qualificacao/[osId]/relatorio/[relId]/finalizar/page.tsx"
git commit -m "feat(pwa): responsive shell with sidebar nav on desktop

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

### Task 2: Componente `SplitPane`

**Files:**
- Create: `app/tecnico/qualificacao/_components/SplitPane.tsx`
- Create: `app/tecnico/qualificacao/__tests__/SplitPane.test.tsx`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces: `SplitPane({ list, narrow, children }: { list: React.ReactNode; narrow: 'list' | 'detail'; children: React.ReactNode })`

Componente puramente apresentacional: sem hook, sem router, sem estado. Em `lg` mostra os dois lados em grid; abaixo de `lg` mostra só o lado indicado por `narrow` — via classe, nunca via JS.

- [ ] **Step 1: Escrever o teste que falha**

Criar `app/tecnico/qualificacao/__tests__/SplitPane.test.tsx`:

```tsx
// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SplitPane } from '../_components/SplitPane'

const setup = (narrow: 'list' | 'detail') =>
  render(
    <SplitPane narrow={narrow} list={<p>lado lista</p>}>
      <p>lado detalhe</p>
    </SplitPane>,
  )

describe('SplitPane', () => {
  it('renderiza os dois lados no DOM, em qualquer modo', () => {
    setup('list')
    expect(screen.getByText('lado lista')).toBeInTheDocument()
    expect(screen.getByText('lado detalhe')).toBeInTheDocument()
  })

  it('narrow=list esconde o detalhe abaixo de lg', () => {
    const { container } = setup('list')
    const [lista, detalhe] = Array.from(
      container.querySelectorAll('[data-pane]'),
    ) as HTMLElement[]
    expect(lista.className).not.toContain('hidden')
    expect(detalhe.className).toContain('hidden')
    expect(detalhe.className).toContain('lg:block')
  })

  it('narrow=detail esconde a lista abaixo de lg', () => {
    const { container } = setup('detail')
    const [lista, detalhe] = Array.from(
      container.querySelectorAll('[data-pane]'),
    ) as HTMLElement[]
    expect(lista.className).toContain('hidden')
    expect(lista.className).toContain('lg:block')
    expect(detalhe.className).not.toContain('hidden')
  })

  it('vira grid de duas colunas em lg, com teto de largura', () => {
    const { container } = setup('list')
    const root = container.firstElementChild as HTMLElement
    expect(root.className).toContain('lg:grid')
    expect(root.className).toContain('lg:grid-cols-[minmax(320px,380px)_1fr]')
    expect(root.className).toContain('lg:max-w-[1440px]')
  })

  it('a coluna da lista rola sozinha em lg', () => {
    const { container } = setup('list')
    const lista = container.querySelector('[data-pane="list"]') as HTMLElement
    expect(lista.className).toContain('lg:sticky')
    expect(lista.className).toContain('lg:overflow-y-auto')
  })
})
```

- [ ] **Step 2: Rodar o teste e ver falhar**

```bash
npx vitest run app/tecnico/qualificacao/__tests__/SplitPane.test.tsx
```

Esperado: FAIL — `Failed to resolve import "../_components/SplitPane"`.

- [ ] **Step 3: Criar `SplitPane.tsx`**

```tsx
import { clsx } from 'clsx'

/**
 * Casca de duas colunas de dentro da OS: lista de coletas à esquerda, detalhe
 * à direita, a partir de 1024px.
 *
 * As duas rotas (`/[osId]` e `/[osId]/coleta/[itemId]`) renderizam este mesmo
 * componente — é por isso que clicar numa coleta continua sendo navegação de
 * rota real, com URL, deep link, botão voltar, Esc, `PendingLink` e
 * `NavProgressBar` funcionando sem nenhum caso especial.
 *
 * Abaixo de 1024px só um lado aparece, escolhido por `narrow`, e o resultado é
 * idêntico ao layout de coluna única de antes. A escolha é CSS: os dois lados
 * estão sempre no DOM. Decidir isso em JS (matchMedia) daria HTML diferente no
 * servidor e no cliente — hidratação quebrada, que já custou caro aqui antes.
 *
 * Custo aceito: em celular, a rota da coleta monta a lista escondida. Não há
 * requisição extra — as duas rotas já usam `useOsDetail`, então vem do cache
 * do React Query.
 */
export function SplitPane({
  list,
  narrow,
  children,
}: {
  list: React.ReactNode
  narrow: 'list' | 'detail'
  children: React.ReactNode
}) {
  return (
    <div className="mx-auto w-full lg:grid lg:max-w-[1440px] lg:grid-cols-[minmax(320px,380px)_1fr] lg:items-start lg:gap-6">
      <div
        data-pane="list"
        className={clsx(
          'lg:sticky lg:top-0 lg:block lg:max-h-full lg:overflow-y-auto lg:pr-1',
          narrow === 'detail' && 'hidden',
        )}
      >
        {list}
      </div>
      <div
        data-pane="detail"
        className={clsx('min-w-0 lg:block', narrow === 'list' && 'hidden')}
      >
        {children}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Rodar o teste e ver passar**

```bash
npx vitest run app/tecnico/qualificacao/__tests__/SplitPane.test.tsx
```

Esperado: PASS, 5 testes.

- [ ] **Step 5: Commit**

```bash
cd addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/_components/SplitPane.tsx \
        pwa/app/tecnico/qualificacao/__tests__/SplitPane.test.tsx
git commit -m "feat(pwa): add SplitPane shell for the OS list/detail pair

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

### Task 3: Extrair `ColetaList` e marcar a linha selecionada

**Files:**
- Create: `app/tecnico/qualificacao/_components/ColetaList.tsx`
- Create: `app/tecnico/qualificacao/__tests__/ColetaList.test.tsx`
- Modify: `app/tecnico/qualificacao/_components/ColetaCard.tsx`
- Modify: `components/ui/PendingLink.tsx`
- Modify: `lib/odoo/tecnico.ts:153-169` (extrair o tipo de retorno de `getOsDetail`)

**Interfaces:**
- Consumes: `ColetaCard`, `CollectedCard`, `EquipmentHeader` (já existem); tipos `OsDetail`-like de `@/lib/odoo/tecnico`.
- Produces:
  - `OsDetailData` — interface exportada de `lib/odoo/tecnico.ts`, extraída do tipo de retorno anônimo de `getOsDetail`
  - `ColetaList({ data, osId, selectedId }: { data: OsDetailData; osId: number; selectedId?: number })`
  - `ColetaCard` ganha a prop opcional `selected?: boolean`
  - `PendingLink` ganha a prop opcional `'aria-current'?: 'page' | 'true' | undefined`

`ColetaList` é a lista que hoje vive dentro de `[osId]/page.tsx`: agrupamento por equipamento, seção "Coletas pendentes"/"Prévia das coletas", seção "Já coletadas", a etiqueta de tipo condicional (`mostrarTipo`) e o aviso "Inicie o relatório do dia pra coletar." Nada do comportamento muda — muda só o endereço do código, mais a marcação da linha selecionada.

- [ ] **Step 1: Escrever o teste que falha**

Criar `app/tecnico/qualificacao/__tests__/ColetaList.test.tsx`:

```tsx
// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ColetaList } from '../_components/ColetaList'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  usePathname: () => '/tecnico/qualificacao/4',
}))

const item = (over: Record<string, unknown>) => ({
  id: 1,
  name: 'Ciclo 1',
  kind: 'foto',
  required: true,
  state: 'pending',
  description: '',
  instruction: '',
  requires_instrument: false,
  docx_section: false,
  qualif_id: false,
  equipment_id: [10, 'Autoclave A'],
  ...over,
})

const data = {
  os: { id: 4, name: 'OS26-06-0002', partner_id: [2, 'Hospital X'] },
  open_relatorio_id: 99,
  equipments: {},
  instruments: {},
  qualifs: {},
  collect_items: [
    item({ id: 1, name: 'Ciclo 1' }),
    item({ id: 2, name: 'Ciclo 2' }),
    item({ id: 3, name: 'Ciclo 3', state: 'collected', equipment_id: [11, 'Autoclave B'] }),
  ],
} as any

describe('ColetaList', () => {
  it('separa pendentes de coletadas, com a contagem no título', () => {
    render(<ColetaList data={data} osId={4} />)
    expect(screen.getByText('Coletas pendentes (2)')).toBeInTheDocument()
    expect(screen.getByText('Já coletadas (1)')).toBeInTheDocument()
  })

  it('agrupa por equipamento', () => {
    render(<ColetaList data={data} osId={4} />)
    expect(screen.getByText('Autoclave A')).toBeInTheDocument()
    expect(screen.getByText('Autoclave B')).toBeInTheDocument()
  })

  it('marca a coleta selecionada com aria-current, não só com cor', () => {
    render(<ColetaList data={data} osId={4} selectedId={2} />)
    const selecionada = screen.getByRole('link', { name: /Ciclo 2/ })
    expect(selecionada).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('link', { name: /Ciclo 1/ })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('sem relatório aberto, avisa que é preciso iniciar o relatório', () => {
    render(<ColetaList data={{ ...data, open_relatorio_id: null }} osId={4} />)
    expect(screen.getByText(/Inicie o relatório do dia/)).toBeInTheDocument()
    expect(screen.getByText('Prévia das coletas (2)')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rodar o teste e ver falhar**

```bash
npx vitest run app/tecnico/qualificacao/__tests__/ColetaList.test.tsx
```

Esperado: FAIL — `Failed to resolve import "../_components/ColetaList"`.

- [ ] **Step 3: Dar `aria-current` ao `PendingLink`**

Em `components/ui/PendingLink.tsx`, acrescentar a prop ao objeto de parâmetros e ao tipo, e repassá-la ao `<a>`:

```tsx
export function PendingLink({
  href,
  children,
  className,
  spinnerClassName,
  'aria-label': ariaLabel,
  'aria-current': ariaCurrent,
}: {
  href: string
  children: React.ReactNode
  className?: string
  spinnerClassName?: string
  'aria-label'?: string
  /** Marca a linha aberta no painel de detalhe (DESIGN.md, "A Regra do Par":
   *  estado nunca é comunicado só por cor). */
  'aria-current'?: 'page' | 'true'
}) {
```

e no `<a>`, logo abaixo de `aria-label={ariaLabel}`:

```tsx
      aria-current={ariaCurrent}
```

- [ ] **Step 4: Dar a prop `selected` ao `ColetaCard`**

Em `app/tecnico/qualificacao/_components/ColetaCard.tsx`, acrescentar `selected = false` à desestruturação e ao tipo:

```tsx
  mostrarTipo = false,
  selected = false,
}: {
  osId: number
  item: ColetaItemDetail
  instruments?: Record<number, InstrumentInfo>
  qualifs?: Record<number, QualifInfo>
  /** Só marca o tipo quando a lista mistura QI/QO/QD — numa OS de um tipo só,
   *  a etiqueta seria a mesma em todas as linhas e viraria ruído. */
  mostrarTipo?: boolean
  /** Linha aberta no painel de detalhe, em desktop. */
  selected?: boolean
}) {
```

e trocar o `PendingLink`/`GlassCard` por:

```tsx
    <PendingLink
      href={`/tecnico/qualificacao/${osId}/coleta/${item.id}`}
      aria-current={selected ? 'true' : undefined}
    >
      <GlassCard
        variant={selected ? 'selected' : 'hover'}
        noPadding
        className="cursor-pointer p-3"
      >
```

- [ ] **Step 5: Criar `ColetaList.tsx`**

Criar `app/tecnico/qualificacao/_components/ColetaList.tsx` com **exatamente** o markup das seções de lista de `[osId]/page.tsx` (a partir de `{(pending_items.length > 0 || done_items.length === 0) && (` até o fim da seção "Já coletadas"), mais o `groupByEquipment`/`mostrarTipo` que hoje moram no corpo daquela página:

```tsx
'use client'
import { ColetaCard } from './ColetaCard'
import { CollectedCard } from './CollectedCard'
import { EquipmentHeader } from './EquipmentHeader'
import type { OsDetailData } from '@/lib/odoo/tecnico'

export function ColetaList({
  data,
  osId,
  selectedId,
}: {
  data: OsDetailData
  osId: number
  /** Item aberto no painel direito, em desktop. */
  selectedId?: number
}) {
  const { collect_items, open_relatorio_id, equipments, instruments, qualifs } = data
  const pending_items = collect_items.filter((i) => i.state === 'pending')
  const done_items = collect_items.filter(
    (i) => i.state === 'collected' || i.state === 'skipped',
  )

  function groupByEquipment(items: typeof collect_items) {
    const groups = new Map<
      string,
      { label: string; eqId: number | null; items: typeof collect_items }
    >()
    for (const it of items) {
      const eqId = it.equipment_id ? it.equipment_id[0] : null
      const key = eqId !== null ? `eq-${eqId}` : 'sem-equip'
      const label = it.equipment_id ? it.equipment_id[1] : 'Sem equipamento'
      if (!groups.has(key)) groups.set(key, { label, eqId, items: [] })
      groups.get(key)!.items.push(it)
    }
    return Array.from(groups.values()).sort((a, b) => a.label.localeCompare(b.label))
  }

  // A etiqueta de tipo (QI/QO/QD) só ganha sentido quando há mais de um tipo
  // na mesma OS; senão repetiria a mesma sigla em toda linha.
  const tiposNaOs = new Set(
    collect_items
      .map((i) => (i.qualif_id ? qualifs[i.qualif_id[0]]?.qualification_type : null))
      .filter(Boolean),
  )
  const mostrarTipo = tiposNaOs.size > 1

  const groupList = groupByEquipment(pending_items)
  const doneGroupList = groupByEquipment(done_items)

  return (
    <div className="space-y-4">
      {(pending_items.length > 0 || done_items.length === 0) && (
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
            {open_relatorio_id
              ? `Coletas pendentes (${pending_items.length})`
              : `Prévia das coletas (${pending_items.length})`}
          </h2>
          {pending_items.length === 0 ? (
            <p className="rounded-lg border border-border/70 bg-muted/30 p-3 text-center text-sm text-muted-foreground/90">
              Nenhuma coleta cadastrada.
            </p>
          ) : (
            groupList.map((g) => (
              <div key={g.label} className="space-y-2">
                <EquipmentHeader
                  label={g.label}
                  eq={g.eqId ? equipments[g.eqId] : undefined}
                  count={g.items.length}
                  tone="cyan"
                />
                <div className="space-y-2 pl-2">
                  {g.items.map((item) =>
                    open_relatorio_id ? (
                      <ColetaCard
                        key={item.id}
                        osId={osId}
                        item={item}
                        instruments={instruments}
                        qualifs={qualifs}
                        mostrarTipo={mostrarTipo}
                        selected={item.id === selectedId}
                      />
                    ) : (
                      <div
                        key={item.id}
                        className="rounded-lg border border-border/40 bg-muted/20 p-3 opacity-60"
                      >
                        <p className="truncate text-sm text-foreground/90">{item.name}</p>
                        {item.instruction && (
                          <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground/80">
                            {item.instruction}
                          </p>
                        )}
                      </div>
                    ),
                  )}
                </div>
              </div>
            ))
          )}
          {!open_relatorio_id && pending_items.length > 0 && (
            <p className="rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-center text-xs text-amber-300/80">
              Inicie o relatório do dia pra coletar.
            </p>
          )}
        </div>
      )}

      {done_items.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
            Já coletadas ({done_items.length})
          </h2>
          {doneGroupList.map((g) => (
            <div key={`done-${g.label}`} className="space-y-2">
              <EquipmentHeader
                label={g.label}
                eq={g.eqId ? equipments[g.eqId] : undefined}
                count={g.items.length}
                tone="emerald"
              />
              <div className="space-y-2 pl-2">
                {g.items.map((item) => (
                  <CollectedCard
                    key={item.id}
                    osId={osId}
                    item={item}
                    canEdit={!!open_relatorio_id}
                    instruments={instruments}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

**O tipo `OsDetailData` ainda não existe** — hoje `getOsDetail` declara o formato inline, em `lib/odoo/tecnico.ts:161-168`. Antes de escrever o `ColetaList`, extrair a interface ali (não criar um tipo paralelo dentro do componente):

```ts
export interface OsDetailData {
  os: OsTecnicoSummary
  collect_items: ColetaItemDetail[]
  open_relatorio_id: number | null
  equipments: Record<number, EquipmentInfo>
  instruments: Record<number, InstrumentInfo>
  qualifs: Record<number, QualifInfo>
}
```

e trocar a assinatura para `): Promise<OsDetailData> {`, mantendo o resto da função (e o comentário do `_userId`) intacto.

- [ ] **Step 6: Rodar o teste e ver passar**

```bash
npx vitest run app/tecnico/qualificacao/__tests__/ColetaList.test.tsx
```

Esperado: PASS, 4 testes.

- [ ] **Step 7: Rodar a suíte inteira e o typecheck**

```bash
npm test
npx tsc --noEmit
```

Esperado: suíte verde (14 arquivos / 52 testes) e `tsc` sem erro. `[osId]/page.tsx` ainda tem a lista antiga duplicada neste ponto — isso é esperado e sai na Task 4.

- [ ] **Step 8: Commit**

```bash
cd addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/_components/ColetaList.tsx \
        pwa/app/tecnico/qualificacao/_components/ColetaCard.tsx \
        pwa/app/tecnico/qualificacao/__tests__/ColetaList.test.tsx \
        pwa/components/ui/PendingLink.tsx \
        pwa/lib/odoo/tecnico.ts
git commit -m "feat(pwa): extract ColetaList and mark the selected row

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

### Task 4: Ligar o painel nas duas rotas da OS

**Files:**
- Modify: `app/tecnico/qualificacao/[osId]/page.tsx`
- Modify: `app/tecnico/qualificacao/[osId]/coleta/[itemId]/page.tsx`
- Create: `app/tecnico/qualificacao/__tests__/EmptyDetail.test.tsx`
- Create: `app/tecnico/qualificacao/_components/EmptyDetail.tsx`

**Interfaces:**
- Consumes: `SplitPane` (Task 2), `ColetaList` (Task 3).
- Produces: `EmptyDetail()` — o estado vazio do painel direito.

- [ ] **Step 1: Escrever o teste que falha**

Criar `app/tecnico/qualificacao/__tests__/EmptyDetail.test.tsx`:

```tsx
// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyDetail } from '../_components/EmptyDetail'

describe('EmptyDetail', () => {
  it('convida a escolher uma coleta', () => {
    render(<EmptyDetail />)
    expect(screen.getByText('Escolha uma coleta')).toBeInTheDocument()
  })

  it('nasce visível — não depende de animação de entrada', () => {
    const { container } = render(<EmptyDetail />)
    const root = container.firstElementChild as HTMLElement
    expect(root.className).not.toContain('opacity-0')
  })
})
```

- [ ] **Step 2: Rodar o teste e ver falhar**

```bash
npx vitest run app/tecnico/qualificacao/__tests__/EmptyDetail.test.tsx
```

Esperado: FAIL — `Failed to resolve import "../_components/EmptyDetail"`.

- [ ] **Step 3: Criar `EmptyDetail.tsx`**

```tsx
import { MousePointerClick } from 'lucide-react'

/**
 * Lado direito de `/[osId]` quando nenhuma coleta está aberta. Só existe em
 * desktop — em celular o `SplitPane` esconde este lado e a tela é a lista.
 */
export function EmptyDetail() {
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center rounded-lg border border-dashed border-border p-6 text-center">
      <MousePointerClick className="h-6 w-6 text-muted-foreground" aria-hidden />
      <p className="mt-3 text-sm font-semibold text-foreground">Escolha uma coleta</p>
      <p className="mt-1 text-xs text-muted-foreground">
        O formulário abre aqui, ao lado da lista.
      </p>
    </div>
  )
}
```

- [ ] **Step 4: Rodar o teste e ver passar**

```bash
npx vitest run app/tecnico/qualificacao/__tests__/EmptyDetail.test.tsx
```

Esperado: PASS, 2 testes.

- [ ] **Step 5: Reescrever `[osId]/page.tsx` para usar o `SplitPane`**

No arquivo `app/tecnico/qualificacao/[osId]/page.tsx`:

1. Trocar os imports de `ColetaCard`, `CollectedCard` e `EquipmentHeader` por `ColetaList`, `SplitPane` e `EmptyDetail`:

```tsx
import { ColetaList } from '../_components/ColetaList'
import { SplitPane } from '../_components/SplitPane'
import { EmptyDetail } from '../_components/EmptyDetail'
```

(`EquipmentHeader` continua importado só se ainda for usado no arquivo; depois desta task não é — remover.)

2. Apagar do corpo da função: `groupByEquipment`, `tiposNaOs`, `mostrarTipo`, `groupList`, `doneGroupList`. `pending_items` e `done_items` **continuam**, porque `RelatorioHeader` (`allDone`) e o bloco de conclusão os usam.

3. Substituir as duas seções de lista (todo o trecho de `{(pending_items.length > 0 || done_items.length === 0) && (` até o fechamento da seção "Já coletadas") por nada — elas agora vêm de `ColetaList`.

4. Envolver o conteúdo: o `return` passa a ser

```tsx
  return (
    <SplitPane narrow="list" list={<ColetaList data={data} osId={id} />}>
      <EmptyDetail />
    </SplitPane>
  )
```

A coluna esquerda continua sendo a tela de hoje inteira: o `<div className="space-y-4">` externo vira o conteúdo de `list`, com `<ColetaList/>` ocupando o lugar exato onde as duas seções de lista estavam. Ou seja, os cinco blocos que já existem no arquivo **não se movem nem mudam** — o botão "← Voltar" com o `<kbd>Esc</kbd>`, o bloco do nome da OS + cliente, o `<RelatorioHeader .../>`, o `<ReviewPanel .../>` e o bloco de conclusão (`pending_items.length === 0 && done_items.length > 0`) ficam antes; o `<Button ... loadingText="Abrindo fechamento...">Finalizar relatório do dia</Button>` fica depois. O `return` final:

```tsx
  return (
    <SplitPane narrow="list" list={
      <div className="space-y-4">
        {/* 1. Voltar  2. nome da OS  3. RelatorioHeader  4. ReviewPanel
            5. bloco de conclusão — todos exatamente como estão hoje */}
        <ColetaList data={data} osId={id} />
        {/* 6. botão "Finalizar relatório do dia", como está hoje */}
      </div>
    }>
      <EmptyDetail />
    </SplitPane>
  )
```

Ordem final da coluna esquerda, de cima pra baixo, idêntica à de hoje: Voltar → cabeçalho da OS → `RelatorioHeader` → `ReviewPanel` → bloco de conclusão → lista de pendentes → lista de coletadas → botão "Finalizar relatório do dia". Se algum bloco mudar de posição ou de markup, a task está errada.

- [ ] **Step 6: Reescrever `[osId]/coleta/[itemId]/page.tsx` para usar o `SplitPane`**

No arquivo `app/tecnico/qualificacao/[osId]/coleta/[itemId]/page.tsx`:

1. Acrescentar imports:

```tsx
import { ColetaList } from '../../../_components/ColetaList'
import { SplitPane } from '../../../_components/SplitPane'
```

2. Envolver **cada** `return` de conteúdo (o do caminho normal e o do erro "Inicie um relatório do dia antes de coletar") no `SplitPane`, com a lista à esquerda:

```tsx
  const lista = osDetail.data ? (
    <ColetaList data={osDetail.data} osId={oid} selectedId={iid} />
  ) : null

  // ...
  return (
    <SplitPane narrow="detail" list={lista}>
      {/* conteúdo que já existia */}
    </SplitPane>
  )
```

O `return <LoadingState label="Carregando coleta..." />` de `if (!item)` fica como está — não vale montar a casca antes de ter o item.

- [ ] **Step 7: Rodar a suíte, o typecheck e o build**

```bash
npm test
npx tsc --noEmit
npm run build
```

Esperado: suíte verde (15 arquivos / 54 testes), `tsc` limpo, build com as 17 rotas de sempre.

- [ ] **Step 8: Commit**

```bash
cd addons/afr_qualificacao
git add "pwa/app/tecnico/qualificacao/[osId]/page.tsx" \
        "pwa/app/tecnico/qualificacao/[osId]/coleta/[itemId]/page.tsx" \
        pwa/app/tecnico/qualificacao/_components/EmptyDetail.tsx \
        pwa/app/tecnico/qualificacao/__tests__/EmptyDetail.test.tsx
git commit -m "feat(pwa): show collect list and detail side by side on desktop

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

### Task 5: Verificação visual nos três viewports

**Files:**
- Modify: `pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md` (registrar o resultado; se o arquivo não tiver seção de layout, criar uma no fim chamada `## Layout desktop (2026-09-04)`)

Nenhum código novo aqui — é a passada de conferência que o spec exige. Se algo quebrar, o conserto entra nesta task, com o teste correspondente.

- [ ] **Step 1: Subir o ambiente**

```bash
docker ps --format '{{.Names}}\t{{.Ports}}' | grep -i qualif
curl -s -o /dev/null -w '%{http_code}\n' -m 5 http://localhost:8084/web/login
```

Se o Odoo :8084 não responder, subir o container antes de seguir (ver `pwa/docs/` e o docker-compose do módulo). Com ele de pé:

```bash
cd addons/afr_qualificacao/pwa && npm run dev   # :3010
```

Dado semeado: OS26-06-0002 (id 4, `in_progress`, 24 coletas pendentes), db `qualificacao-dev`, técnico = employee 441 / uid 2.

- [ ] **Step 2: Conferir 1280×800**

```bash
agent-browser viewport 1280 800
agent-browser open http://localhost:3010/tecnico/qualificacao
agent-browser snapshot -i
```

Fazer login se cair na tela de login, navegar até a OS 4, abrir uma coleta e conferir, item a item:
- navegação está na lateral esquerda, sem barra inferior;
- lista à esquerda e formulário à direita, ao mesmo tempo;
- a linha da coleta aberta está marcada (fundo + `aria-current` no snapshot);
- a coluna da esquerda rola sem levar a direita junto;
- nada de barra de rolagem horizontal na página.

- [ ] **Step 3: Conferir 1920×1080**

```bash
agent-browser viewport 1920 1080
```

Repetir a navegação. Conferir que o conteúdo para em 1440px e fica centrado — não estica até a borda.

- [ ] **Step 4: Conferir 390×844 (regressão de celular)**

```bash
agent-browser viewport 390 844
```

Percorrer o fluxo inteiro: home → OS → coleta → salvar → finalizar turno. Tem que estar **idêntico** ao de antes: coluna única, barra inferior, sem sinal da lista na tela de coleta.

- [ ] **Step 5: Conferir a assinatura com mouse**

Em 1280×800, ir até fechar turno e desenhar no `SignaturePad` arrastando o mouse. `react-signature-canvas` usa pointer events, então deve funcionar; a conferência é visual (o traço aparece, "Limpar" apaga).

- [ ] **Step 6: Registrar o resultado e commitar**

Escrever no checklist o que foi conferido em cada viewport, com data. Depois:

```bash
cd addons/afr_qualificacao
git add pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md
git commit -m "docs(pwa): record desktop layout verification at three viewports

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

### Task 6: Reescrever PRODUCT.md e DESIGN.md

**Files:**
- Modify: `pwa/PRODUCT.md`
- Modify: `pwa/DESIGN.md`
- Modify: `pwa/TODO.md`

Sem esta task o documento de design continua proibindo o que acabou de ser construído, e a próxima revisão reverte tudo. Nenhum teste automatizado cobre isto — a verificação é leitura.

- [ ] **Step 1: Reescrever o princípio 6 do `PRODUCT.md`**

Substituir o item 6 inteiro por:

```markdown
6. **Uma mão, retrato, luva — e o notebook quando ele volta.** O caso de
   projeto é o celular em retrato, numa mão só, de luva: é o piso de
   qualidade e o que precisa funcionar sempre. Mas o técnico nem sempre está
   em campo — às vezes revisa a OS pelo notebook, e ali a coluna de 480px no
   meio de uma tela de 1920px é desperdício. Desktop é **o mesmo app mais
   largo**, com no máximo um painel de detalhe ao lado da lista; não é uma
   segunda arquitetura de informação. O espaço extra compra linha e contexto,
   nunca controle menor: alvo de toque continua ≥44px, porque notebook com
   tela sensível existe. Se algo só funciona em tela grande, não funciona.
```

- [ ] **Step 2: Corrigir o Key Characteristics do `DESIGN.md`**

Trocar a linha

```markdown
- Coluna única, sempre; retrato de celular é o caso de projeto, não o degradado.
```

por

```markdown
- A coluna é a unidade de leitura. Retrato de celular é o caso de projeto,
  não o degradado; a partir de 1024px a tela pode exibir duas colunas — lista
  e detalhe — e nada além disso.
```

- [ ] **Step 3: Reescrever a seção Navigation do `DESIGN.md` (§5)**

Substituir o parágrafo de "### Navigation" por:

```markdown
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
```

- [ ] **Step 4: Acrescentar a regra do espaço extra ao `DESIGN.md`**

Na seção "### Cards / Containers", logo após o parágrafo do `task-row`, inserir:

```markdown
**A Regra do Espaço Extra.** A largura ganha no desktop compra **mais linhas
visíveis e mais meta por linha** — nunca aba, tabela larga ou toolbar. Essas
três são exatamente a anti-referência "tela de ERP / backoffice Odoo" do
PRODUCT.md, e uma tela larga é justamente onde a tentação aparece. Layout de
duas colunas é permitido em um caso só: lista de coletas à esquerda, detalhe
da coleta à direita, dentro da OS.
```

- [ ] **Step 5: Atualizar o `TODO.md`**

Marcar o item "Layout preso em 480px" como resolvido (`~~...~~ **Resolvido em 2026-09-04**`), com uma frase do que foi feito e o ponteiro para o spec. Tirar o marcador `👉 **PRÓXIMO PASSO**` dali.

Acrescentar, na seção "Técnico Qualificação", o item que ficou fora de escopo:

```markdown
- **Bloco de comemoração viola o DESIGN.md.** `[osId]/page.tsx` (~linhas 106-120)
  tem gradiente esmeralda, `animate-pulse` em loop, blur e 🎉🏆🎊 quando todas as
  coletas terminam. Isso contraria três Don'ts (gradiente decorativo, emoji como
  ícone de interface, glow em loop) e o "a tela não comemora, informa" do
  PRODUCT.md — ou seja, o item "Limpeza de neon. **Feita em 2026-09-03**" acima
  está incompleto. Trocar por confirmação sóbria com o número de coletas.
```

- [ ] **Step 6: Reler os três arquivos procurando contradição**

```bash
grep -n "Coluna única\|coluna única\|retrato\|480px\|barra inferior" pwa/PRODUCT.md pwa/DESIGN.md
```

Nenhuma ocorrência pode continuar dizendo que coluna única é obrigatória em qualquer largura. Corrigir o que restar.

- [ ] **Step 7: Commit**

```bash
cd addons/afr_qualificacao
git add pwa/PRODUCT.md pwa/DESIGN.md pwa/TODO.md
git commit -m "docs(pwa): allow the desktop layout in PRODUCT.md and DESIGN.md

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

### Task 7: Bump do pointer do submodule no monorepo

**Files:**
- Modify: `addons/afr_qualificacao` (pointer, no repo `odoo_engenapp`)

Feito uma vez só, no fim, depois que todos os commits das tasks 1-6 já foram pushados para `origin main` do submodule. Fazer o bump antes disso deixaria o pointer apontando para um commit que não existe no remote.

- [ ] **Step 1: Conferir que o submodule está limpo e sincronizado**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git status --short
git log --oneline -1
git rev-parse HEAD origin/main   # os dois hashes têm que bater
```

Esperado: nada pendente e `HEAD` == `origin/main`.

- [ ] **Step 2: Bump e push**

```bash
cd /home/afonso/docker/odoo_engenapp
git add addons/afr_qualificacao
git commit -m "chore: bump submodule afr_qualificacao (layout desktop do PWA técnico)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push
```
