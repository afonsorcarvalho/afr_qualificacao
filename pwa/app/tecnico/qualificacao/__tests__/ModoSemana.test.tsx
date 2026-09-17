// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AgendaPage from '../agenda/page'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import type { AgendaPayload, VisitaAgenda } from '@/lib/odoo/agenda'

const mutateUpdate = vi.fn()

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

const payload: AgendaPayload = {
  server_today: '2026-09-17',
  date_from: '2026-09-17',
  date_to: '2026-09-23',
  my_employee_id: 441,
  can_manage: true,
  visitas: [visita()],
}

let payloadAtual: AgendaPayload = payload

vi.mock('@/lib/hooks/useAgenda', () => ({
  useAgendaDisponivel: () => ({ data: true }),
  useAgenda: () => ({ data: payloadAtual, isLoading: false, error: null }),
  useUpdateVisita: () => ({ mutateAsync: mutateUpdate, isPending: false }),
  useCreateVisita: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteVisita: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useTecnicoOptions: () => ({ data: [{ id: 441, name: 'Afonso' }, { id: 9, name: 'Bruno' }] }),
  useOsOptions: () => ({ data: [] }),
  useInstrumentoOptions: () => ({
    data: [{ id: 1, name: 'Q001', validade: '2027-01-01' }],
  }),
}))

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
  )
  return { qc, ...utils }
}

function irParaSemana() {
  fireEvent.click(screen.getByRole('button', { name: /Semana/ }))
}

describe('Modo Semana', () => {
  beforeEach(() => {
    payloadAtual = payload
    mutateUpdate.mockReset().mockResolvedValue(visita())
    // O store é um singleton do módulo (zustand + persist): sem resetar
    // `modoAgenda` aqui, o toque em "Semana" de um teste vaza para o
    // próximo, que já nasceria no modo errado.
    useTecnicoSettings.setState({ modoAgenda: 'lista' })
  })

  it('o botão de modo alterna Lista e Semana', () => {
    montar()
    expect(screen.queryByRole('button', { name: /^Técnico$/ })).toBeNull()
    irParaSemana()
    expect(screen.getByRole('button', { name: /^Técnico$/ })).toBeInTheDocument()
  })

  it('"Só minhas" chega desabilitado no modo Semana', () => {
    montar()
    const filtro = screen.getByRole('checkbox') as HTMLInputElement
    expect(filtro.disabled).toBe(false)
    irParaSemana()
    expect((screen.getByRole('checkbox') as HTMLInputElement).disabled).toBe(true)
  })

  it('tocar num técnico com a visita em ajuste passa a visita para ele', async () => {
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /Bruno/ }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { tecnico_id: 9 } }),
    )
  })

  it('tocar num dia com a visita em ajuste move para aquele dia', async () => {
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^sáb 19/i }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { date: '2026-09-19' } }),
    )
  })

  it('tocar num instrumento liga, e tocar de novo desliga', async () => {
    const { rerender, qc } = montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^Instrumento$/ }))
    fireEvent.click(screen.getByRole('button', { name: /Q001/ }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { instrument_ids: [1] } }),
    )
    payloadAtual = { ...payload, visitas: [visita({ instrument_ids: [1] })] }
    // `useAgenda` aqui é um mock estático (não é o react-query real): trocar
    // `payloadAtual` não dispara, sozinho, um novo render — no app de
    // verdade quem faz isso é o refetch que o `onSuccess` da mutação
    // invalida. `rerender` simula esse refetch já ter chegado antes do
    // próximo toque.
    rerender(
      <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
    )
    mutateUpdate.mockClear()
    fireEvent.click(screen.getByRole('button', { name: /Q001/ }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { instrument_ids: [] } }),
    )
  })

  it('erro do servidor aparece em tarja e a seleção não se perde', async () => {
    mutateUpdate.mockRejectedValue(
      new Error('Não é possível programar uma visita para uma data passada'),
    )
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /Bruno/ }))
    await waitFor(() =>
      expect(screen.getByText(/data passada/)).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: /Concluir/ })).toBeInTheDocument()
  })

  it('sem can_manage não há "Ajustar" e o painel não vira alvo', () => {
    payloadAtual = {
      ...payload, can_manage: false,
      visitas: [visita({ editable: false, lock_reason: 'Somente o Gestor edita a agenda.' })],
    }
    montar()
    irParaSemana()
    expect(screen.queryByRole('button', { name: /Ajustar/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Bruno/ })).toBeNull()
  })
})
