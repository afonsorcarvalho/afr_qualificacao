// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
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
  // Duas visitas de propósito (id, os_name, partner_name e city diferentes
  // em cada uma): com uma só, `alvoDaProposta` acertando por `find(id)` e
  // uma regressão para `payload.visitas[0]` ficam indistinguíveis — as duas
  // dão o mesmo resultado quando só existe um elemento.
  visitas: [{
    id: 87, date: '2026-10-15', time_start: 8, time_stop: 17, planned_hours: 9,
    os_id: 4, os_name: 'OS26-06-0002', os_state: 'draft',
    partner_name: 'Hospital Central', city: 'São Luís', equipment_list: [],
    instrument_ids: [], instrument_list: [], tecnico_id: 3,
    tecnico_name: 'João Silva', is_mine: false, state: 'draft', overflow: false,
    editable: true, lock_reason: false as const, conflict: false,
    conflict_msg: '', note: '',
  }, {
    id: 91, date: '2026-10-16', time_start: 9, time_stop: 16, planned_hours: 7,
    os_id: 9, os_name: 'OS26-06-0009', os_state: 'draft',
    partner_name: 'Clínica Oceano', city: 'Imperatriz', equipment_list: [],
    instrument_ids: [], instrument_list: [], tecnico_id: 5,
    tecnico_name: 'Maria Souza', is_mine: false, state: 'draft', overflow: false,
    editable: true, lock_reason: false as const, conflict: false,
    conflict_msg: '', note: '',
  }],
}

// `qcExterno`: opcional, só para o teste de revalidação poder espionar
// `invalidateQueries` no MESMO client que o componente usa — sem isso não
// há como saber se `confirmar()` de fato notificou a agenda.
function montar(props: Partial<React.ComponentProps<typeof ChatAgenda>> = {}, qcExterno?: QueryClient) {
  const qc = qcExterno ?? new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ChatAgenda open onClose={() => {}} payload={payload as never} {...props} />
    </QueryClientProvider>,
  )
}

// O teste de ditado abaixo substitui `fetch`, `MediaRecorder` e
// `navigator.mediaDevices` em `globalThis` para simular o fluxo de
// gravação. `vi.clearAllMocks()` só limpa histórico de chamadas — não
// desfaz essas atribuições — então sem restaurar aqui os testes
// seguintes do arquivo herdariam um `fetch` mockado e passariam por
// motivo errado (ou quebrariam sem relação com o que testam).
const fetchOriginal = globalThis.fetch
const mediaDevicesOriginal = (globalThis as any).navigator.mediaDevices
const mediaRecorderOriginal = (globalThis as any).MediaRecorder

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.sessionStorage?.clear()
})

afterEach(() => {
  globalThis.fetch = fetchOriginal
  ;(globalThis as any).navigator.mediaDevices = mediaDevicesOriginal
  ;(globalThis as any).MediaRecorder = mediaRecorderOriginal
})

describe('ChatAgenda', () => {
  it('não renderiza quando o payload diz que o usuário não gerencia', () => {
    // `container` vazio, não só o `<input>` ausente: checar só o campo de
    // texto passaria mesmo se um regressão deixasse escapar o título, o
    // texto de intro ou as bolhas da folha — exatamente o vazamento que a
    // spec proíbe (um técnico não pode ver ESTE chat, nem parcialmente).
    const { container } = montar({ payload: { ...payload, can_manage: false } as never })
    expect(container).toBeEmptyDOMElement()
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
    // Alvo é a SEGUNDA visita (id 91) — com duas visitas no payload, um
    // `find(id)` correto e uma regressão para `visitas[0]` (que pegaria a
    // 87) divergem de verdade: a primeira mostra Clínica Oceano/Imperatriz,
    // a segunda mostraria Hospital Central/São Luís por engano.
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'atualizar_visita',
        args: { visita_id: 91, date: '2026-10-16' }, resumo: 'Alterar a visita 91.',
      },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/OS26-06-0009/)).toBeTruthy()
    expect(screen.getByText(/Clínica Oceano/)).toBeTruthy()
    expect(screen.queryByText(/OS26-06-0002/)).toBeNull()
    expect(screen.queryByText(/Hospital Central/)).toBeNull()
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

  it('Confirmar revalida a agenda e as OS do técnico', async () => {
    // Sem isso, o gestor confirma um reagendamento e o board continua
    // mostrando a data velha — a mudança parece ter falhado. `confirmar()`
    // já chama `qc.invalidateQueries` para os dois queryKeys; este teste
    // espiona o QueryClient real do componente para provar que roda.
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' },
    })
    confirmarEscritaMock.mockResolvedValue({ kind: 'text', messages: [], text: 'pronto' })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    montar({}, qc)
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    await userEvent.click(await screen.findByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(confirmarEscritaMock).toHaveBeenCalledTimes(1))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['agenda'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['tecnico-os'] })
  })

  it('tem botão de ditar que não envia sozinho', async () => {
    montar()
    const mic = screen.getByRole('button', { name: /ditar/i })
    expect(mic).toBeTruthy()
    expect(runTurnMock).not.toHaveBeenCalled()
  })

  it('texto ditado cai no campo mas não dispara envio automático', async () => {
    // O teste acima só confere que o botão existe e que montar a tela não
    // dispara `runTurn` — isso seria verdade mesmo se o callback de ditado
    // chamasse `enviar()` por engano, porque nenhuma transcrição rodou.
    // Este aqui aciona o fluxo de ditado de ponta a ponta (grava, para,
    // transcreve) e prova que o texto chega ao `<input>` sem `runTurn` ser
    // chamado.
    class FakeRecorder {
      static isTypeSupported() { return true }
      ondataavailable: ((e: { data: Blob }) => void) | null = null
      onstop: (() => void) | null = null
      constructor(public stream: unknown) {}
      start() {}
      stop() {
        this.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })
        this.onstop?.()
      }
    }
    ;(globalThis as any).MediaRecorder = FakeRecorder
    ;(globalThis as any).navigator.mediaDevices = {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }),
    }
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'remarca a visita do João' }), { status: 200 }),
    ) as unknown as typeof fetch

    montar()
    const mic = screen.getByRole('button', { name: /ditar/i })
    await userEvent.click(mic) // inicia gravação
    await userEvent.click(await screen.findByRole('button', { name: /parar gravação/i })) // para e transcreve

    const input = screen.getByPlaceholderText(/escreva/i) as HTMLInputElement
    await waitFor(() => expect(input.value).toBe('remarca a visita do João'))
    expect(runTurnMock).not.toHaveBeenCalled()
  })

  it('fechar a folha do chat com o mic ligado descarta a gravação em andamento', async () => {
    // `ChatAgenda` não desmonta quando a folha fecha — é o `BottomSheet`
    // que se esconde por dentro. Sem parar a gravação nesse momento, o
    // mic continuaria ligado atrás de uma tela invisível, sem nenhum
    // controle visível pro gestor desligar. Fechar deve descartar, não
    // transcrever: o gestor não pediu o texto, só fechou a tela.
    class FakeRecorder {
      static isTypeSupported() { return true }
      ondataavailable: ((e: { data: Blob }) => void) | null = null
      onstop: (() => void) | null = null
      constructor(public stream: unknown) {}
      start() {}
      stop() {
        this.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })
        this.onstop?.()
      }
    }
    ;(globalThis as any).MediaRecorder = FakeRecorder
    const pararTrack = vi.fn()
    ;(globalThis as any).navigator.mediaDevices = {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: pararTrack }] }),
    }
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = montar({}, qc)

    const mic = screen.getByRole('button', { name: /ditar/i })
    await userEvent.click(mic) // inicia gravação, sem clicar em "parar"
    await screen.findByRole('button', { name: /parar gravação/i })

    rerender(
      <QueryClientProvider client={qc}>
        <ChatAgenda open={false} onClose={() => {}} payload={payload as never} />
      </QueryClientProvider>,
    )

    await waitFor(() => expect(pararTrack).toHaveBeenCalled())
    expect(fetchMock).not.toHaveBeenCalled()
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
