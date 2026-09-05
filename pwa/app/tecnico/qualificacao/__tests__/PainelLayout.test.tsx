// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PainelLayout from '../[osId]/(painel)/layout'
import * as hooks from '@/lib/hooks/useTecnicoQualif'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'

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
  // `userId` real (não mockado) entra na conta do achado 1(a): sem isto,
  // os testes de sucesso já existentes cairiam no branch de carregando.
  useTecnicoSettings.setState({ lastUserId: 7 })
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
    // Achado 1(b): o "← Voltar" também aparece no branch de erro, não só no
    // de sucesso — é o único controle de volta em ≥1024px.
    expect(screen.getByRole('button', { name: /Voltar/ })).toBeInTheDocument()
  })

  it('achado 1(a): userId ainda não chegou do store (query desabilitada) mostra carregando, não erro', () => {
    // Uma query `enabled: false` do React Query v5 reporta isLoading: false
    // — é exatamente essa forma que o hook mockado devolve aqui, simulando
    // a janela entre o layout montar e `lastUserId` chegar via zustand
    // `persist` (storage limpo, sessão lenta/offline).
    useTecnicoSettings.setState({ lastUserId: null })
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: undefined, isLoading: false, isFetching: false, error: null,
      refetch: vi.fn(),
    } as any)
    wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByText('Carregando OS...')).toBeInTheDocument()
    expect(screen.queryByText(/Erro ao carregar OS/)).not.toBeInTheDocument()
    expect(screen.getByText('painel direito')).toBeInTheDocument()
  })

  it('achado 1(b): "← Voltar" aparece também enquanto a OS carrega, não só no sucesso', () => {
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: undefined, isLoading: true, isFetching: true, error: null,
      refetch: vi.fn(),
    } as any)
    wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByText('Carregando OS...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Voltar/ })).toBeInTheDocument()
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

  it('anuncia a troca do painel direito numa região viva sempre presente', () => {
    // A região precisa existir ANTES da troca: inserir o nó junto com o texto
    // não é anunciado pela maioria dos leitores de tela. Por isso ela nasce
    // vazia e só o texto muda.
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: osDetailData, isLoading: false, isFetching: false, error: null,
      refetch: vi.fn(),
    } as any)
    const { unmount } = wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    const regiao = screen.getByTestId('painel-anuncio')
    expect(regiao).toHaveAttribute('aria-live', 'polite')
    expect(regiao).toHaveTextContent('')
    unmount()

    pathname = '/tecnico/qualificacao/4/coleta/7'
    wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByTestId('painel-anuncio')).toHaveTextContent(/Ciclo 7/)
  })

  it('a região viva fica fora dos branches de carregando e erro', () => {
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: undefined, isLoading: true, isFetching: true, error: null,
      refetch: vi.fn(),
    } as any)
    wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByTestId('painel-anuncio')).toBeInTheDocument()
  })

  it('a região viva não está dentro do painel escondido em tela estreita', () => {
    // `display:none` não é anunciado: dentro da coluna da lista a região
    // ficaria inerte justo no celular, onde a rota troca a tela inteira.
    pathname = '/tecnico/qualificacao/4/coleta/7'
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: osDetailData, isLoading: false, isFetching: false, error: null,
      refetch: vi.fn(),
    } as any)
    const { container } = wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    const lista = container.querySelector('[data-pane="list"]') as HTMLElement
    expect(lista.className).toContain('hidden')
    expect(lista.querySelector('[data-testid="painel-anuncio"]')).toBeNull()
  })

  it('OS concluída informa sem comemorar: sem emoji, gradiente ou pulse', () => {
    const tudoColetado = {
      ...osDetailData,
      collect_items: osDetailData.collect_items.map((i: any) => ({
        ...i, state: 'collected',
      })),
    }
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: tudoColetado, isLoading: false, isFetching: false, error: null,
      refetch: vi.fn(),
    } as any)
    const { container } = wrap(<PainelLayout><p>painel direito</p></PainelLayout>)
    expect(screen.getByText(/Todas as coletas concluídas/)).toBeInTheDocument()
    expect(screen.getByText(/2 de 2/)).toBeInTheDocument()
    expect(screen.getByText(/Pronto pra finalizar o relatório/)).toBeInTheDocument()
    const html = container.innerHTML
    // Sem flag `u`: o alvo do tsconfig é anterior a es6. O par substituto
    // cobre todo o plano astral, que é onde mora emoji.
    expect(html).not.toMatch(/[\uD800-\uDBFF][\uDC00-\uDFFF]/)
    expect(html).not.toContain('animate-pulse')
    expect(html).not.toContain('animate-bounce')
    expect(html).not.toContain('bg-gradient-to-br')
    expect(html).not.toContain('blur-3xl')
  })
})
