// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAgenda } from '@/lib/hooks/useAgenda'
import * as agendaApi from '@/lib/odoo/agenda'

vi.mock('@/lib/odoo/agenda')

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useAgenda', () => {
  beforeEach(() => vi.clearAllMocks())

  it('busca quando enabled=true', async () => {
    vi.mocked(agendaApi.fetchAgenda).mockResolvedValue({
      server_today: '2026-09-16', date_from: '2026-09-16', date_to: '2026-09-29',
      my_employee_id: 441, can_manage: false, visitas: [],
    })
    const { result } = renderHook(() => useAgenda(null, null, false, true), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(agendaApi.fetchAgenda).toHaveBeenCalled()
  })

  // Cobre o defeito da Task 6: `useAgendaDisponivel()` é assíncrona e
  // devolve `undefined` na primeira montagem — só o `false` explícito
  // (módulo de agendamento ausente) deve segurar o `pwa_agenda_fetch`. Sem
  // o `enabled`, a RPC disparava contra um modelo inexistente antes da
  // mensagem correta de indisponibilidade aparecer, e o usuário via um
  // flash de "Erro ao carregar a agenda. Verifique conexão." que atribuía a
  // um problema de conexão o que era módulo ausente.
  it('não busca quando enabled=false (módulo de agendamento ausente)', async () => {
    vi.mocked(agendaApi.fetchAgenda).mockResolvedValue({
      server_today: '2026-09-16', date_from: '2026-09-16', date_to: '2026-09-29',
      my_employee_id: 441, can_manage: false, visitas: [],
    })
    const { result } = renderHook(() => useAgenda(null, null, false, false), { wrapper })
    // Dá tempo do react-query rodar um microtask, se fosse disparar.
    await new Promise((r) => setTimeout(r, 10))
    expect(agendaApi.fetchAgenda).not.toHaveBeenCalled()
    expect(result.current.isLoading).toBe(false)
    expect(result.current.fetchStatus).toBe('idle')
  })
})
