// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

// `vi.hoisted`: as fábricas de `vi.mock` abaixo são hoisted acima de
// qualquer `const` deste arquivo — sem isso, `_ChatAgenda` (importado logo
// adiante) puxa `lib/chat/machine` antes de `runTurnMock` etc. existirem, e
// a fábrica do mock estoura "Cannot access before initialization".
const { runTurnMock, confirmarEscritaMock, runToolMock } = vi.hoisted(() => ({
  runTurnMock: vi.fn(),
  confirmarEscritaMock: vi.fn(),
  runToolMock: vi.fn(),
}))

vi.mock('@/lib/chat/machine', async () => {
  const real = await vi.importActual<typeof import('@/lib/chat/machine')>('@/lib/chat/machine')
  return { ...real, runTurn: runTurnMock, confirmarEscrita: confirmarEscritaMock }
})
vi.mock('@/lib/chat/tools', () => ({ runTool: runToolMock }))

import { ChatAgenda } from '../agenda/_ChatAgenda'

const payload = {
  server_today: '2026-10-14',
  date_from: '2026-10-01',
  date_to: '2026-10-31',
  my_employee_id: 441 as number | false,
  can_manage: true,
  visitas: [{
    id: 87, date: '2026-10-15', time_start: 8, time_stop: 17, planned_hours: 9,
    os_id: 4, os_name: 'OS26-06-0002', os_state: 'draft',
    partner_name: 'Hospital Central', city: 'São Luís', equipment_list: [],
    instrument_ids: [], instrument_list: [], tecnico_id: 3,
    tecnico_name: 'João Silva', is_mine: false, state: 'draft', overflow: false,
    editable: true, lock_reason: false as const, conflict: false,
    conflict_msg: '', note: '',
  }],
}

function montar(props: Partial<React.ComponentProps<typeof ChatAgenda>> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ChatAgenda open onClose={() => {}} payload={payload as never} {...props} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.sessionStorage?.clear()
})

describe('ChatAgenda', () => {
  it('não renderiza quando o payload diz que o usuário não gerencia', () => {
    montar({ payload: { ...payload, can_manage: false } as never })
    expect(screen.queryByPlaceholderText(/escreva/i)).toBeNull()
  })

  it('mostra a resposta de texto do assistente', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'text', messages: [], text: 'Você tem 1 visita quinta-feira.',
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'o que tenho quinta?')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/1 visita quinta-feira/i)).toBeTruthy()
  })

  it('escrita proposta aparece como card com o resumo e dois botões', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'atualizar_visita',
        args: { visita_id: 87, date: '2026-10-16' },
        resumo: 'Alterar a visita 87: data → 2026-10-16.',
      },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'remarca pra sexta')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/Alterar a visita 87/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /confirmar/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeTruthy()
  })

  it('o card mostra o contexto da visita alvo, não só o id', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'atualizar_visita',
        args: { visita_id: 87, date: '2026-10-16' }, resumo: 'Alterar a visita 87.',
      },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/OS26-06-0002/)).toBeTruthy()
    expect(screen.getByText(/Hospital Central/)).toBeTruthy()
  })

  it('Cancelar não executa a escrita', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    await userEvent.click(await screen.findByRole('button', { name: /cancelar/i }))
    expect(confirmarEscritaMock).not.toHaveBeenCalled()
    expect(runToolMock).not.toHaveBeenCalled()
  })

  it('Confirmar executa a escrita uma vez só', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' },
    })
    // Promessa controlada à mão: sem isso, o mock resolve na mesma
    // microtask e o `act()` do userEvent drena a escrita inteira (inclusive
    // o desmonte do card) antes do segundo clique acontecer — o toque duplo
    // nunca chegaria a correr CONCORRENTE com a escrita em trânsito, só em
    // sequência com ela já terminada. Resolver só depois dos dois cliques
    // dispachados é o que faz a corrida existir de verdade.
    let resolverEscrita!: (v: unknown) => void
    const escritaEmTransito = new Promise((resolve) => {
      resolverEscrita = resolve
    })
    confirmarEscritaMock.mockReturnValue(escritaEmTransito)
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    const btn = await screen.findByRole('button', { name: /confirmar/i })
    // Dois toques SEM aguardar a escrita da primeira resolver — a segunda
    // dispara (ou tenta disparar) enquanto a primeira ainda está pendente.
    userEvent.click(btn)
    await userEvent.click(btn).catch(() => {})
    resolverEscrita({ kind: 'text', messages: [], text: 'pronto' })
    await waitFor(() => expect(confirmarEscritaMock).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/pronto/)).toBeTruthy()
  })

  it('erro da máquina aparece na conversa sem derrubar a tela', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'error', messages: [], erro: 'IA indisponível no momento — use a agenda manual.',
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/IA indisponível/)).toBeTruthy()
  })
})
