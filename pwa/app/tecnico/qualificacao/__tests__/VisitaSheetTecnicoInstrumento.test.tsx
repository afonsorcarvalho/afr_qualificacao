// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
// Task 1 (2026-09-17-folha-visita-tecnico-instrumento): a folha de edição da
// visita não mostrava o técnico já gravado quando ele não estava mais no
// roster oficial (`pwa_tecnico_options`), e não deixava marcar/desmarcar os
// instrumentos de qualificação. Estes testes cobrem as duas correções.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { VisitaSheet } from '../_components/VisitaSheet'
import type { VisitaAgenda } from '@/lib/odoo/agenda'

const mutateUpdate = vi.fn()
const mutateCreate = vi.fn()
const mutateDelete = vi.fn()
const mockInstrumentoOptions = vi.fn()

// Roster oficial de propósito SEM o técnico da visita (441/Afonso Carvalho):
// é exatamente essa ausência que reproduz o defeito.
vi.mock('@/lib/hooks/useAgenda', () => ({
  useUpdateVisita: () => ({ mutateAsync: mutateUpdate, isPending: false }),
  useCreateVisita: () => ({ mutateAsync: mutateCreate, isPending: false }),
  useDeleteVisita: () => ({ mutateAsync: mutateDelete, isPending: false }),
  useTecnicoOptions: () => ({ data: [{ id: 9, name: 'Bruno' }, { id: 12, name: 'Paulo' }] }),
  useOsOptions: () => ({ data: [] }),
  useInstrumentoOptions: (enabled: boolean) => mockInstrumentoOptions(enabled),
}))

const visita: VisitaAgenda = {
  id: 1, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 4,
  os_id: 4, os_name: 'OS26-06-0002', os_state: 'scheduled',
  partner_name: 'Hospital', city: 'São Luís',
  equipment_list: [], instrument_list: [], instrument_ids: [1],
  tecnico_id: 441, tecnico_name: 'Afonso Carvalho', is_mine: true,
  state: 'planned', overflow: false, editable: true, lock_reason: false,
  conflict: false, conflict_msg: '', note: '',
}

describe('VisitaSheet — técnico atual e instrumentos', () => {
  beforeEach(() => {
    mutateUpdate.mockReset().mockResolvedValue(visita)
    mutateCreate.mockReset().mockResolvedValue(visita)
    mutateDelete.mockReset().mockResolvedValue(true)
    mockInstrumentoOptions.mockReset().mockReturnValue({ data: [] })
  })

  it('mostra o técnico da visita mesmo fora do roster oficial', () => {
    render(<VisitaSheet open modo="editar" visita={visita} onClose={vi.fn()} />)
    const select = screen.getByLabelText('Técnico') as HTMLSelectElement
    expect(select.value).toBe('441')
    expect(screen.getByRole('option', { name: 'Afonso Carvalho' })).toBeInTheDocument()
  })

  it('salvar sem tocar no técnico mantém o técnico da visita no pwa_visita_update', async () => {
    render(<VisitaSheet open modo="editar" visita={visita} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Salvar/ }))
    await waitFor(() => expect(mutateUpdate).toHaveBeenCalled())
    expect(mutateUpdate.mock.calls[0][0].vals.tecnico_id).toBe(441)
  })

  it('não duplica o técnico oficial quando ele já é o técnico da visita', () => {
    const v = { ...visita, tecnico_id: 9, tecnico_name: 'Bruno' }
    render(<VisitaSheet open modo="editar" visita={v} onClose={vi.fn()} />)
    expect(screen.getAllByRole('option', { name: 'Bruno' })).toHaveLength(1)
  })

  it('visita sem técnico fica em — e salvar não inventa um técnico', async () => {
    const v = { ...visita, tecnico_id: false as const, tecnico_name: '' }
    render(<VisitaSheet open modo="editar" visita={v} onClose={vi.fn()} />)
    const select = screen.getByLabelText('Técnico') as HTMLSelectElement
    expect(select.value).toBe('')
    fireEvent.click(screen.getByRole('button', { name: /Salvar/ }))
    await waitFor(() => expect(mutateUpdate).toHaveBeenCalled())
    // Nenhum id de técnico real (Bruno=9, Paulo=12, Afonso=441) foi enviado.
    expect(mutateUpdate.mock.calls[0][0].vals.tecnico_id).toBeFalsy()
  })

  it('marca os instrumentos da visita e reflete a alternância no pwa_visita_update', async () => {
    mockInstrumentoOptions.mockReturnValue({
      data: [
        { id: 1, name: 'Q001', validade: '2027-01-01' },
        { id: 2, name: 'Q002', validade: '2027-01-01' },
      ],
    })
    const v = { ...visita, instrument_ids: [1] }
    render(<VisitaSheet open modo="editar" visita={v} onClose={vi.fn()} />)

    const cbQ001 = screen.getByRole('checkbox', { name: /Q001/ }) as HTMLInputElement
    const cbQ002 = screen.getByRole('checkbox', { name: /Q002/ }) as HTMLInputElement
    expect(cbQ001.checked).toBe(true)
    expect(cbQ002.checked).toBe(false)

    fireEvent.click(cbQ002)
    fireEvent.click(cbQ001)
    fireEvent.click(screen.getByRole('button', { name: /Salvar/ }))

    await waitFor(() => expect(mutateUpdate).toHaveBeenCalled())
    expect(mutateUpdate.mock.calls[0][0].vals.instrument_ids).toEqual([2])
  })

  it('mostra aviso de certificado vencido conforme a data escolhida no formulário', () => {
    mockInstrumentoOptions.mockReturnValue({
      data: [{ id: 1, name: 'Q001', validade: '2026-09-10' }],
    })
    const v = { ...visita, date: '2026-09-17', instrument_ids: [1] }
    render(<VisitaSheet open modo="editar" visita={v} onClose={vi.fn()} />)

    expect(screen.getByText(/certificado vencido/)).toBeInTheDocument()

    // Muda a data do formulário para antes da validade: o aviso some, porque
    // a regra é contra a data escolhida, não a data original da visita.
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-09-01' } })
    expect(screen.queryByText(/certificado vencido/)).toBeNull()
  })

  it('pwa_instrumento_options vazio mostra "Nenhum instrumento cadastrado."', () => {
    mockInstrumentoOptions.mockReturnValue({ data: [] })
    render(<VisitaSheet open modo="editar" visita={visita} onClose={vi.fn()} />)
    expect(screen.getByText('Nenhum instrumento cadastrado.')).toBeInTheDocument()
  })

  it('modo criar não renderiza campo de instrumentos nem habilita a busca', () => {
    render(<VisitaSheet open modo="criar" visita={null} onClose={vi.fn()} />)
    expect(screen.queryByText('Instrumentos')).toBeNull()
    expect(mockInstrumentoOptions).toHaveBeenCalledWith(false)
  })
})
