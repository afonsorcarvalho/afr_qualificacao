// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FinalizarPage from '../[osId]/relatorio/[relId]/finalizar/page'
import * as hooks from '@/lib/hooks/useTecnicoQualif'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'

const push = vi.fn()
const replace = vi.fn()
const back = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace, back }),
  useParams: () => ({ osId: '4', relId: '99' }),
  usePathname: () => '/tecnico/qualificacao/4/relatorio/99/finalizar',
}))

vi.mock('@/lib/hooks/useTecnicoQualif', async () => {
  const actual = await vi.importActual<typeof import('@/lib/hooks/useTecnicoQualif')>(
    '@/lib/hooks/useTecnicoQualif',
  )
  return { ...actual, useOsDetail: vi.fn(), useFinalizeRelatorio: vi.fn() }
})

// A IA fica fora do caminho: sem chave o app já roda assim, e o auto-resumo
// só atrapalharia a asserção de navegação.
vi.mock('@/lib/hooks/useGroqStatus', () => ({
  useGroqStatus: () => ({ enabled: false }),
}))

// O pad real desenha em <canvas>, que o happy-dom não pinta. O dublê entrega
// a assinatura por um botão, que é tudo que este teste precisa dela.
vi.mock('../_components/SignatureCanvas', () => ({
  SignaturePad: ({ onChange }: { onChange: (b: string | null) => void }) => (
    <button type="button" onClick={() => onChange('data:image/png;base64,AAA')}>
      assinar (dublê)
    </button>
  ),
}))

const osDetail = {
  os: { id: 4, name: 'OS26-06-0002', partner_id: [2, 'Hospital X'] },
  open_relatorio_id: 99,
  equipments: {},
  instruments: {},
  qualifs: {},
  collect_items: [
    {
      id: 1, name: 'Ciclo 1', kind: 'foto', required: true, state: 'collected',
      description: '', instruction: '', requires_instrument: false,
      docx_section: false, qualif_id: false, equipment_id: [10, 'Autoclave A'],
      relatorio_id: [99, 'REL'],
    },
  ],
} as any

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  push.mockClear()
  replace.mockClear()
  useTecnicoSettings.setState({ lastUserId: 7 })
  vi.mocked(hooks.useOsDetail).mockReturnValue({
    data: osDetail, isLoading: false, isFetching: false, error: null, refetch: vi.fn(),
  } as any)
})

function preencheEFinaliza() {
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'Turno normal, sem intercorrências.' },
  })
  fireEvent.click(screen.getByRole('button', { name: /assinar \(dublê\)/ }))
  fireEvent.click(screen.getByRole('button', { name: /Fechar relatório/i }))
}

describe('FinalizarPage', () => {
  it('depois de finalizar, SUBSTITUI a entrada no histórico em vez de empilhar', () => {
    // Com `push`, o botão voltar do navegador levava de volta ao formulário
    // do relatório recém-fechado; tentar finalizar de novo dava erro no
    // servidor, e só o segundo "voltar" chegava na OS. Relatado em campo
    // 2026-09-05. É o mesmo beco sem saída que a tela de coleta já tinha
    // resolvido com `replace`.
    vi.mocked(hooks.useFinalizeRelatorio).mockReturnValue({
      mutate: (_vars: unknown, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.(),
      isPending: false,
    } as any)

    wrap(<FinalizarPage />)
    preencheEFinaliza()

    expect(replace).toHaveBeenCalledWith('/tecnico/qualificacao/4')
    expect(push).not.toHaveBeenCalled()
  })

  it('falha ao finalizar não navega para lugar nenhum', () => {
    // Sem isto, um erro de rede poderia tirar o técnico da tela com a
    // assinatura ainda por gravar.
    vi.mocked(hooks.useFinalizeRelatorio).mockReturnValue({
      mutate: (_vars: unknown, opts?: { onError?: (e: unknown) => void }) =>
        opts?.onError?.(new Error('falhou')),
      isPending: false,
    } as any)

    wrap(<FinalizarPage />)
    preencheEFinaliza()

    expect(replace).not.toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
  })
})
