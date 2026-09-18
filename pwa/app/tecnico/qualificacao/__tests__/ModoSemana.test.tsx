// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
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

// `vi.fn` que NÃO descarta os argumentos: uma lambda `() => ({...})` não
// permite provar QUAL `onlyMine` a página pediu — é exatamente o formato
// que deixou passar o item 1 do review (modo Semana buscando com
// `only_mine=true`).
const mockUseAgenda = vi.fn(
  (_dateFrom: string | null, _dateTo: string | null, _onlyMine: boolean, _enabled: boolean) => (
    { data: payloadAtual, isLoading: false, error: null }
  ),
)

vi.mock('@/lib/hooks/useAgenda', () => ({
  useAgendaDisponivel: () => ({ data: true }),
  useAgenda: (...args: [string | null, string | null, boolean, boolean]) => mockUseAgenda(...args),
  useUpdateVisita: () => ({ mutateAsync: mutateUpdate, isPending: false }),
  useCreateVisita: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteVisita: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useTecnicoOptions: () => ({ data: [{ id: 441, name: 'Afonso' }, { id: 9, name: 'Bruno' }] }),
  useOsOptions: () => ({ data: [] }),
  useInstrumentoOptions: () => ({
    data: [
      { id: 1, name: 'Q001', validade: '2027-01-01' },
      { id: 2, name: 'Q002', validade: '2027-01-01' },
    ],
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
    mockUseAgenda.mockClear()
    // O store é um singleton do módulo (zustand + persist): sem resetar
    // `modoAgenda` aqui, o toque em "Semana" de um teste vaza para o
    // próximo, que já nasceria no modo errado. `filterMine` também: o
    // default persistido é `true`, e é justamente essa persistência que faz
    // do modo Semana com filtro ligado o caso comum, não a aresta.
    useTecnicoSettings.setState({ modoAgenda: 'lista', filterMine: true })
  })

  it('o botão de modo alterna Lista e Semana', () => {
    montar()
    expect(screen.queryByRole('button', { name: /^Técnico$/ })).toBeNull()
    irParaSemana()
    expect(screen.getByRole('button', { name: /^Técnico$/ })).toBeInTheDocument()
  })

  it('"Só minhas" chega desabilitado E DESMARCADO no modo Semana, mesmo com o filtro persistido ligado', () => {
    // `filterMine: true` é o default persistido (`tecnicoSettings.ts`) — a
    // UI não pode mostrar o checkbox marcado (ligado) ao lado de um texto
    // que diz "desligado na semana": a mesma linha se contradizendo.
    montar()
    const filtro = screen.getByRole('checkbox') as HTMLInputElement
    expect(filtro.disabled).toBe(false)
    expect(filtro.checked).toBe(true)
    irParaSemana()
    const filtroSemana = screen.getByRole('checkbox') as HTMLInputElement
    expect(filtroSemana.disabled).toBe(true)
    expect(filtroSemana.checked).toBe(false)
  })

  it('modo Semana busca com onlyMine=false SEMPRE, mesmo com "Só minhas" persistido ligado — e volta a true na Lista', () => {
    montar()
    irParaSemana()
    const ultimaChamadaSemana = mockUseAgenda.mock.calls.at(-1)
    expect(ultimaChamadaSemana?.[2]).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: /^Lista$/ }))
    const ultimaChamadaLista = mockUseAgenda.mock.calls.at(-1)
    expect(ultimaChamadaLista?.[2]).toBe(true)
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

  it('tocar num dia com a visita em ajuste abre diálogo de confirmação; Confirmar move para aquele dia', async () => {
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^sáb 19/i }))

    // Não grava direto — abre a confirmação com as duas datas no texto.
    expect(mutateUpdate).not.toHaveBeenCalled()
    const dialogo = screen.getByRole('dialog', { name: 'Mudar data da visita' })
    expect(within(dialogo).getByText(
      'Tem certeza que deseja mudar a data da visita OS26-02 de 17/09/2026 para 19/09/2026?',
    )).toBeInTheDocument()

    fireEvent.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { date: '2026-09-19' } }),
    )
  })

  it('Cancelar no diálogo de confirmação não grava e mantém a visita armada', async () => {
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^sáb 19/i }))

    const dialogo = screen.getByRole('dialog', { name: 'Mudar data da visita' })
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar' }))

    expect(mutateUpdate).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).toBeNull()
    // A visita continua armada — o Gestor precisa poder escolher outro dia
    // sem recomeçar.
    expect(screen.getByRole('button', { name: /Concluir/ })).toBeInTheDocument()
  })

  it('tocar no mesmo dia em que a visita já está não abre diálogo', async () => {
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^qui 17/i }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(mutateUpdate).not.toHaveBeenCalled()
  })

  it('ajuste de técnico e de instrumento continuam sem diálogo de confirmação (guarda de escopo: só data pede confirmação)', async () => {
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /Bruno/ }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { tecnico_id: 9 } }),
    )
    expect(screen.queryByRole('dialog')).toBeNull()

    mutateUpdate.mockClear()
    fireEvent.click(screen.getByRole('button', { name: /^Instrumento$/ }))
    fireEvent.click(screen.getByRole('button', { name: /Q001/ }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { instrument_ids: [1] } }),
    )
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('rede de segurança: visita em ajuste que SOME do payload fecha o diálogo pendente de confirmação de data', async () => {
    const { rerender, qc } = montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^sáb 19/i }))
    expect(screen.getByRole('dialog', { name: 'Mudar data da visita' })).toBeInTheDocument()

    payloadAtual = { ...payload, visitas: [] }
    rerender(<QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>)

    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('depois de mover a visita, a vista segue e a seleção continua (não fica presa)', async () => {
    const { rerender, qc } = montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^sáb 19/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { date: '2026-09-19' } }),
    )
    // Simula o refetch (real, depois do `onSuccess`) trazendo a visita já
    // com a data nova.
    payloadAtual = { ...payload, visitas: [visita({ date: '2026-09-19' })] }
    rerender(
      <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
    )
    // (a) a faixa passou a mostrar o dia novo como selecionado
    expect(screen.getByRole('button', { name: /^sáb 19/i })).toHaveAttribute('aria-pressed', 'true')
    // (b) o card continua visível e ainda em ajuste — "Concluir", não "Ajustar"
    expect(screen.getByRole('button', { name: /Concluir/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Ajustar$/ })).toBeNull()
  })

  it('ligar Q001, depois ligar Q002 (Q001 continua ligado), depois desligar Q001', async () => {
    const { rerender, qc } = montar()
    const refresh = () => rerender(
      <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
    )
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^Instrumento$/ }))

    fireEvent.click(screen.getByRole('button', { name: /Q001/ }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { instrument_ids: [1] } }),
    )
    // Simula o refetch (real, depois do `onSuccess`) trazendo a visita já
    // com Q001 ligado — `useAgenda` aqui é mock estático, então só um
    // `rerender` explícito faz o componente reler `payloadAtual`.
    payloadAtual = { ...payload, visitas: [visita({ instrument_ids: [1] })] }
    refresh()

    // A cena que motivou o `emAjusteAtual`: ligar um SEGUNDO instrumento
    // diferente não pode apagar o primeiro.
    mutateUpdate.mockClear()
    fireEvent.click(screen.getByRole('button', { name: /Q002/ }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { instrument_ids: [1, 2] } }),
    )

    payloadAtual = { ...payload, visitas: [visita({ instrument_ids: [1, 2] })] }
    refresh()

    mutateUpdate.mockClear()
    fireEvent.click(screen.getByRole('button', { name: /Q001/ }))
    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { instrument_ids: [2] } }),
    )
  })

  it('erro do servidor ao confirmar mudança de data aparece em tarja e a seleção não se perde', async () => {
    mutateUpdate.mockRejectedValue(
      new Error('Não é possível programar uma visita para uma data passada'),
    )
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^sáb 19/i }))
    const dialogo = screen.getByRole('dialog', { name: 'Mudar data da visita' })
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(screen.getByText(/data passada/)).toBeInTheDocument(),
    )
    // O diálogo já fechou (o "Confirmar" fecha antes do resultado do
    // `mutateAsync` voltar) e a visita continua armada — mesmo
    // comportamento do caminho de técnico/instrumento, só que atravessando
    // o gate novo.
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('button', { name: /Concluir/ })).toBeInTheDocument()
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

  it('tocar Concluir depois de um erro limpa a tarja', async () => {
    mutateUpdate.mockRejectedValueOnce(
      new Error('Não é possível programar uma visita para uma data passada'),
    )
    montar()
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /Bruno/ }))
    await waitFor(() =>
      expect(screen.getByText(/data passada/)).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: /Concluir/ }))
    expect(screen.queryByText(/data passada/)).toBeNull()
  })

  it('rede de segurança: visita em ajuste que SOME do payload encerra o ajuste', async () => {
    mutateUpdate.mockRejectedValueOnce(new Error('falha qualquer'))
    const { rerender, qc } = montar()
    const refresh = () => rerender(
      <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
    )
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /Bruno/ }))
    await waitFor(() => expect(screen.getByText(/falha qualquer/)).toBeInTheDocument())

    // A visita é apagada em outro lugar (ou sai da janela): some do payload.
    payloadAtual = { ...payload, visitas: [] }
    refresh()

    expect(screen.queryByText(/falha qualquer/)).toBeNull()
    expect(screen.queryByRole('button', { name: /Bruno/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Concluir/ })).toBeNull()
  })

  it('rede de segurança: visita que TRAVA (editable:false) durante o ajuste também encerra — sem armadilha sem saída', () => {
    const { rerender, qc } = montar()
    const refresh = () => rerender(
      <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
    )
    irParaSemana()
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    expect(screen.getByRole('button', { name: /Concluir/ })).toBeInTheDocument()

    // Outro usuário tirou a OS de `scheduled` enquanto a visita estava
    // selecionada: o refetch traz `editable: false`. Sem a rede de
    // segurança estendida, `alvoAtivo` continuaria ligado e cada toque na
    // faixa/painel dispararia uma gravação que o servidor recusa — sem
    // saída a não ser trocar de modo.
    payloadAtual = {
      ...payload,
      visitas: [visita({
        editable: false, lock_reason: 'OS em execução (Em execução).',
      })],
    }
    refresh()

    expect(screen.queryByRole('button', { name: /Concluir/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Bruno/ })).toBeNull()
    expect(screen.getByText(/OS em execução/)).toBeInTheDocument()
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
