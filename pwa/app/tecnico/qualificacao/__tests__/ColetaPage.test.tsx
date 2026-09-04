// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ColetaPage from '../[osId]/coleta/[itemId]/page'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import odooClient from '@/lib/odoo/client'
import * as hooks from '@/lib/hooks/useTecnicoQualif'

// Achados 1, 2, 3 e 7 da revisão de branch (2026-09-04): ver
// docs/superpowers/specs/2026-09-04-pwa-tecnico-layout-desktop-design.md.

const push = vi.fn()
const back = vi.fn()
const replace = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, back, replace }),
  useParams: () => ({ osId: '4', itemId: '1' }),
}))

vi.mock('@/lib/odoo/client', () => ({
  default: { searchRead: vi.fn() },
}))

vi.mock('@/lib/hooks/useTecnicoQualif', async () => {
  const actual = await vi.importActual<typeof import('@/lib/hooks/useTecnicoQualif')>(
    '@/lib/hooks/useTecnicoQualif',
  )
  return { ...actual, useOsDetail: vi.fn(), useCollectItem: vi.fn() }
})

const osDetailData = {
  os: { id: 4, name: 'OS26-06-0002', partner_id: [2, 'Hospital X'] },
  open_relatorio_id: 99,
  equipments: {},
  instruments: {},
  qualifs: {},
  collect_items: [
    {
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
    },
  ],
} as any

const item = {
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
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ColetaPage />
    </QueryClientProvider>,
  )
}

describe('ColetaPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useTecnicoSettings.setState({ lastUserId: 7 })
  })

  it('achado 1: ao salvar, navega pra frente pra rota da OS, não pra trás', async () => {
    vi.mocked(odooClient.searchRead).mockResolvedValue([item])
    const mutate = vi.fn((_vars, opts) => opts?.onSuccess?.())
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: osDetailData,
      isLoading: false,
    } as any)
    vi.mocked(hooks.useCollectItem).mockReturnValue({
      mutate,
      isPending: false,
    } as any)

    renderPage()
    const pularBtn = await screen.findByRole('button', { name: 'Pular' })
    fireEvent.click(pularBtn)

    expect(replace).toHaveBeenCalledWith('/tecnico/qualificacao/4')
    expect(back).not.toHaveBeenCalled()
  })

  it('achado 2: enquanto a coleta carrega, o painel da lista continua com o conteúdo da OS', async () => {
    // searchRead nunca resolve nesta asserção: simula o item ainda em voo.
    vi.mocked(odooClient.searchRead).mockReturnValue(new Promise(() => {}))
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: osDetailData,
      isLoading: false,
    } as any)
    vi.mocked(hooks.useCollectItem).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)

    renderPage()

    expect(await screen.findByText('Carregando coleta...')).toBeInTheDocument()
    // A lista (achado 2) e a identidade da OS (achado 3) continuam visíveis
    // — a coluna esquerda não é apagada enquanto o item da direita carrega.
    expect(screen.getByText('OS26-06-0002')).toBeInTheDocument()
    expect(screen.getByText('Hospital X')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Ciclo 1/ })).toBeInTheDocument()
  })

  it('achado 3: o painel da lista mostra nome e parceiro da OS acima da lista de coletas', async () => {
    vi.mocked(odooClient.searchRead).mockResolvedValue([item])
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: osDetailData,
      isLoading: false,
    } as any)
    vi.mocked(hooks.useCollectItem).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)

    renderPage()

    expect(await screen.findByRole('heading', { name: 'OS26-06-0002' })).toBeInTheDocument()
    expect(screen.getByText('Hospital X')).toBeInTheDocument()
  })

  it('achado 7: enquanto a OS ainda carrega, o painel da lista mostra um estado de espera em vez de ficar em branco', async () => {
    vi.mocked(odooClient.searchRead).mockResolvedValue([item])
    vi.mocked(hooks.useOsDetail).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any)
    vi.mocked(hooks.useCollectItem).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)

    renderPage()

    expect(await screen.findByText('Carregando OS...')).toBeInTheDocument()
  })
})
