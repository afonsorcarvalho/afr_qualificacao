// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AgendaPage from '../agenda/page'
import * as agendaApi from '@/lib/odoo/agenda'

vi.mock('@/lib/odoo/agenda')

/**
 * Cobre o defeito confirmado na review da Task 6 (fechado na Task 7, junto
 * do `VisitaSheet`): `useAgenda(...)` era chamado antes do guard
 * `disponivel.data === false` na página, e como `useAgendaDisponivel()` é
 * ela própria assíncrona, a query da agenda disparava contra
 * `afr.qualificacao.os.visita` mesmo quando o servidor não tem o módulo de
 * agendamento — o usuário via "Erro ao carregar a agenda. Verifique
 * conexão." antes da mensagem correta de indisponibilidade aparecer.
 *
 * A correção foi o parâmetro `enabled` em `useAgenda` (lib/hooks/useAgenda.ts)
 * e `agenda/page.tsx` passando `disponivel.data !== false`. O teste unitário
 * de `useAgenda` (lib/hooks/__tests__/useAgenda.test.tsx) cobre o hook
 * isolado; este cobre a FIAÇÃO na página real: com `agenda-disponivel` já
 * resolvido para `false` no cache (staleTime Infinity, não refetch), o
 * `fetchAgenda` nunca deve ser chamado, e quem renderiza é a mensagem de
 * indisponibilidade, não o flash de erro de conexão.
 */
function wrapperComCacheIndisponivel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  qc.setQueryData(['agenda-disponivel'], false)
  return qc
}

describe('AgendaPage — disponibilidade guarda a busca', () => {
  beforeEach(() => vi.clearAllMocks())

  it('não chama fetchAgenda quando o módulo de agendamento está ausente', async () => {
    vi.mocked(agendaApi.fetchAgenda).mockResolvedValue({
      server_today: '2026-09-16', date_from: '2026-09-16', date_to: '2026-09-29',
      my_employee_id: 441, can_manage: false, visitas: [],
    })
    const qc = wrapperComCacheIndisponivel()
    render(
      <QueryClientProvider client={qc}>
        <AgendaPage />
      </QueryClientProvider>,
    )
    expect(
      await screen.findByText(/módulo de agendamento não está instalado/),
    ).toBeInTheDocument()
    expect(agendaApi.fetchAgenda).not.toHaveBeenCalled()
    expect(screen.queryByText(/Verifique conexão/)).toBeNull()
  })
})
