// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { VisitaSheet } from '../_components/VisitaSheet'
import type { VisitaAgenda } from '@/lib/odoo/agenda'

const mutateUpdate = vi.fn()
const mutateCreate = vi.fn()
const mutateDelete = vi.fn()

vi.mock('@/lib/hooks/useAgenda', () => ({
  useUpdateVisita: () => ({ mutateAsync: mutateUpdate, isPending: false }),
  useCreateVisita: () => ({ mutateAsync: mutateCreate, isPending: false }),
  useDeleteVisita: () => ({ mutateAsync: mutateDelete, isPending: false }),
  useTecnicoOptions: () => ({ data: [{ id: 441, name: 'Afonso' }, { id: 9, name: 'Bruno' }] }),
  useOsOptions: () => ({ data: [{ id: 4, name: 'OS26-06-0002 - Hospital' }] }),
}))

const visita: VisitaAgenda = {
  id: 1, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 4,
  os_id: 4, os_name: 'OS26-06-0002', os_state: 'scheduled',
  partner_name: 'Hospital', city: 'São Luís',
  equipment_list: [], instrument_list: [],
  tecnico_id: 441, tecnico_name: 'Afonso', is_mine: true,
  state: 'planned', overflow: false, editable: true, lock_reason: false,
  conflict: false, conflict_msg: '', note: '',
}

describe('VisitaSheet', () => {
  beforeEach(() => {
    mutateUpdate.mockReset().mockResolvedValue(visita)
    mutateCreate.mockReset().mockResolvedValue(visita)
    mutateDelete.mockReset().mockResolvedValue(true)
  })

  it('salva só os campos da whitelist', async () => {
    render(<VisitaSheet open modo="editar" visita={visita} onClose={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-09-18' } })
    fireEvent.click(screen.getByRole('button', { name: /Salvar/ }))
    await waitFor(() => expect(mutateUpdate).toHaveBeenCalled())
    const enviado = mutateUpdate.mock.calls[0][0]
    expect(enviado.id).toBe(1)
    expect(Object.keys(enviado.vals).sort()).toEqual(
      ['date', 'note', 'tecnico_id', 'time_start', 'time_stop'],
    )
    expect(enviado.vals.date).toBe('2026-09-18')
  })

  it('apagar exige confirmação', async () => {
    render(<VisitaSheet open modo="editar" visita={visita} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Apagar/ }))
    expect(mutateDelete).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /Confirmar exclusão/ }))
    await waitFor(() => expect(mutateDelete).toHaveBeenCalledWith(1))
  })

  it('erro do servidor aparece na folha e não fecha', async () => {
    const onClose = vi.fn()
    mutateUpdate.mockRejectedValue(new Error('Não é possível programar uma visita para uma data passada'))
    render(<VisitaSheet open modo="editar" visita={visita} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: /Salvar/ }))
    await waitFor(() =>
      expect(screen.getByText(/data passada/)).toBeInTheDocument(),
    )
    expect(onClose).not.toHaveBeenCalled()
  })

  it('modo criar pede OS, técnico e data', async () => {
    render(<VisitaSheet open modo="criar" visita={null} onClose={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('OS'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Técnico'), { target: { value: '441' } })
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-09-20' } })
    fireEvent.click(screen.getByRole('button', { name: /Criar/ }))
    await waitFor(() =>
      expect(mutateCreate).toHaveBeenCalledWith({ osId: 4, tecnicoId: 441, date: '2026-09-20' }),
    )
  })

  it('modo criar não oferece apagar', () => {
    render(<VisitaSheet open modo="criar" visita={null} onClose={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Apagar/ })).toBeNull()
  })
})
