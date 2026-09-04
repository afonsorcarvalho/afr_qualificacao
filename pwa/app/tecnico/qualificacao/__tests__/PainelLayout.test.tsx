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
