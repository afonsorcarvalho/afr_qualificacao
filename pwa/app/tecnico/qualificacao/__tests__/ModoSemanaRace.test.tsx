// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
/**
 * Integração de verdade (sem mockar `@/lib/hooks/useAgenda`, ao contrário de
 * `ModoSemana.test.tsx`): só a camada de transporte (`@/lib/odoo/agenda`) é
 * mock. É a única forma de flagrar o defeito do item 2 do review — ele mora
 * dentro do `useUpdateVisita` de verdade (`onSuccess`/cache do react-query),
 * e um `mutateAsync: vi.fn()` não tem esse `onSuccess` para exercitar.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AgendaPage from '../agenda/page'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import * as agendaApi from '@/lib/odoo/agenda'
import type { AgendaPayload, VisitaAgenda } from '@/lib/odoo/agenda'

vi.mock('@/lib/odoo/agenda')

function visita(over: Partial<VisitaAgenda> = {}): VisitaAgenda {
  return {
    id: 7, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 4,
    os_id: 4, os_name: 'OS26-02', os_state: 'scheduled',
    partner_name: 'Hospital', city: 'São Luís',
    equipment_list: [], instrument_list: [], instrument_ids: [],
    tecnico_id: 441, tecnico_name: 'Afonso', is_mine: true,
    state: 'planned', overflow: false, editable: true, lock_reason: false,
    conflict: false, conflict_msg: '', note: '',
    ...over,
  }
}

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>)
}

describe('useUpdateVisita — dois toques rápidos não perdem o primeiro', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useTecnicoSettings.setState({ modoAgenda: 'semana', filterMine: false })
    vi.mocked(agendaApi.agendaDisponivel).mockResolvedValue(true)
    vi.mocked(agendaApi.listTecnicoOptions).mockResolvedValue([{ id: 441, name: 'Afonso' }])
    vi.mocked(agendaApi.listInstrumentoOptions).mockResolvedValue([
      { id: 1, name: 'Q001', validade: '2027-01-01' },
      { id: 2, name: 'Q002', validade: '2027-01-01' },
    ])
    vi.mocked(agendaApi.listOsOptions).mockResolvedValue([])
  })

  it('toque em Q001 e, sem esperar o refetch, toque em Q002: o segundo envia [1, 2], nunca [2]', async () => {
    const inicial: AgendaPayload = {
      server_today: '2026-09-17', date_from: '2026-09-17', date_to: '2026-09-23',
      my_employee_id: 441, can_manage: true, visitas: [visita()],
    }
    // `fetchAgenda` (o refetch disparado por `invalidateQueries` após cada
    // gravação) é deliberadamente LENTO. É a diferença entre o cache
    // atualizado NA HORA pelo retorno do `pwa_visita_update` (o fix desta
    // rodada) e um cache que só atualizaria quando esse refetch, mais
    // devagar, chegasse — que é exatamente a janela em que o segundo toque
    // lia o payload velho e apagava o primeiro.
    vi.mocked(agendaApi.fetchAgenda).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(inicial), 40)),
    )
    // O servidor real substitui a lista inteira via `(6, 0, ids)`; o mock
    // imita isso devolvendo a visita exatamente como o `vals` pediu — é o
    // retorno de `pwa_visita_update` que o fix usa para atualizar o cache.
    vi.mocked(agendaApi.updateVisita).mockImplementation(async (_id, vals) => ({
      ...inicial.visitas[0],
      ...vals,
    }))

    montar()
    // Modo Semana com `inicio` ainda nulo dispara DOIS fetches em sequência
    // (o inicial de janela ampla + o da âncora do item 5, já janela de 7
    // dias) — ambos usam o mesmo mock lento de propósito. Espera os dois
    // resolverem e o estado estabilizar antes de interagir; sem isto, o
    // teste pode flagrar o "Ajustar" no intervalo transitório entre um
    // fetch e outro.
    await new Promise((r) => setTimeout(r, 150))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Ajustar/ })).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^Instrumento$/ }))
    // `useInstrumentoOptions` só liga quando a dimensão troca para
    // "instrumento" — dá tempo do `listInstrumentoOptions()` mockado
    // resolver antes de procurar Q001/Q002.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Q001/ })).toBeInTheDocument(),
    )

    fireEvent.click(screen.getByRole('button', { name: /Q001/ }))
    await waitFor(() =>
      expect(agendaApi.updateVisita).toHaveBeenCalledWith(7, { instrument_ids: [1] }),
    )

    // Neste ponto o `mutateAsync` do primeiro toque já resolveu (o mock de
    // `updateVisita` não tem atraso nenhum) e o `onSuccess` já rodou — mas
    // o refetch de `fetchAgenda` (40ms) ainda não chegou. Mesmo assim, o
    // SEGUNDO toque precisa enxergar o instrumento já ligado.
    fireEvent.click(screen.getByRole('button', { name: /Q002/ }))
    await waitFor(() =>
      expect(agendaApi.updateVisita).toHaveBeenCalledWith(7, { instrument_ids: [1, 2] }),
    )
    expect(agendaApi.updateVisita).not.toHaveBeenCalledWith(7, { instrument_ids: [2] })
  })
})
