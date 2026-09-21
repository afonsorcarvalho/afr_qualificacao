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

  it('escrita proposta aparece como card falando humano: título pela OS, não pelo id', async () => {
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
    // Título fala a OS, não o id cru — o id "87" não pode aparecer sozinho
    // na linha principal (é exatamente o achado do bug original).
    expect(await screen.findByText(/Remarcar visita da OS26-06-0002/)).toBeTruthy()
    expect(screen.queryByText(/^Alterar a visita 87/)).toBeNull()
    // Data em pt-BR com dia da semana, "de → para".
    expect(screen.getByText(/→ .*16\/10\/2026/)).toBeTruthy()
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

  it('o card mostra o contexto da visita alvo mesmo quando visita_id chega como string', async () => {
    // Mesma quirk do achado 1: o modelo às vezes devolve id inteiro como
    // string. Sem coagir em `alvoDaProposta`, o card perde a linha de
    // OS/cliente/cidade — a única defesa do gestor contra um alvo errado —
    // bem na mensagem em que ela mais importa.
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'atualizar_visita',
        args: { visita_id: '91', date: '2026-10-16' }, resumo: 'Alterar a visita 91.',
      },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/OS26-06-0009/)).toBeTruthy()
    expect(screen.getByText(/Clínica Oceano/)).toBeTruthy()
  })

  it('visita fora da janela carregada: o card avisa explicitamente, não finge que informou', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'atualizar_visita',
        args: { visita_id: 2126, date: '2026-10-16' }, resumo: 'Alterar a visita 2126.',
      },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/visita 2126.*fora do período/)).toBeTruthy()
    // Nenhuma das duas visitas do payload é a 2126 — nada de OS/cliente
    // inventado por engano.
    expect(screen.queryByText(/OS26-06-0002/)).toBeNull()
    expect(screen.queryByText(/OS26-06-0009/)).toBeNull()
  })

  it('quando só o horário muda, a linha Data aparece sem seta e a linha Horário aparece com seta', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'atualizar_visita',
        args: { visita_id: 87, time_start: 9, time_stop: 12 }, resumo: 'r',
      },
    })
    const { container } = montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    await screen.findByRole('button', { name: /confirmar/i })
    const linhas = Array.from(container.querySelectorAll('p')).map((p) => p.textContent ?? '')
    const linhaData = linhas.find((t) => t.startsWith('Data'))
    const linhaHorario = linhas.find((t) => t.startsWith('Horário'))
    expect(linhaData).toBeTruthy()
    expect(linhaData).not.toMatch(/→/)
    expect(linhaHorario).toBeTruthy()
    expect(linhaHorario).toMatch(/→/)
  })

  it('criar_visita mostra um card equivalente: OS resolvida, data em pt-BR e técnico', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'criar_visita',
        args: { os_id: 9, tecnico_id: 5, date: '2026-10-16' }, resumo: 'r',
      },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/Criar visita para OS26-06-0009/)).toBeTruthy()
    expect(screen.getByText(/Maria Souza/)).toBeTruthy()
  })

  // Transcript realista de uma proposta pendente: mensagem "assistant" com
  // `tool_calls=[c1]` e SEM resposta "tool" para c1 — exatamente o shape
  // que `runTurn` devolve quando para por causa de uma escrita (ver
  // `machine.ts`, `propostaPendente`). Os testes de mock anteriores
  // usavam `messages: []`, o que faria a asserção de invariante abaixo
  // passar mesmo com o bug: iterar zero `tool_calls` não prova nada.
  const transcriptComPropostaPendente = [
    { role: 'system' as const, content: 's' },
    { role: 'user' as const, content: 'remarca pra sexta' },
    {
      role: 'assistant' as const, content: null,
      tool_calls: [{ id: 'c1', type: 'function' as const, function: { name: 'atualizar_visita', arguments: '{"visita_id":87}' } }],
    },
  ]

  // Reaproveita a forma de asserção de `machine.test.ts:133-142`
  // ("turno [escrita, escrita]"): toda `tool_call_id` de toda mensagem
  // assistant no transcript enviado precisa ter exatamente uma resposta
  // "tool" — senão a próxima chamada ao modelo é rejeitada pela API. O
  // `toBeGreaterThan(0)` é a guarda anti-vácuo: sem ela, um transcript sem
  // nenhuma tool_call faria o loop `for` não rodar e a asserção "passaria"
  // sem checar nada.
  function assertTranscriptBemFormado(mensagens: unknown[]) {
    const assistentes = (mensagens as Array<{ role: string; tool_calls?: Array<{ id: string }> }>)
      .filter((m) => m.role === 'assistant' && m.tool_calls && m.tool_calls.length > 0)
    expect(assistentes.length).toBeGreaterThan(0)
    for (const a of assistentes) {
      for (const call of a.tool_calls!) {
        const respostas = (mensagens as Array<{ role: string; tool_call_id?: string }>)
          .filter((m) => m.role === 'tool' && m.tool_call_id === call.id)
        expect(respostas.length).toBe(1)
      }
    }
  }

  it('Cancelar repara o transcript: a mensagem seguinte não carrega tool_call sem resposta', async () => {
    runTurnMock.mockResolvedValueOnce({
      kind: 'proposal', messages: transcriptComPropostaPendente,
      proposta: { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' },
    })
    runTurnMock.mockResolvedValueOnce({ kind: 'text', messages: [], text: 'ok' })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'remarca pra sexta')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    await userEvent.click(await screen.findByRole('button', { name: /cancelar/i }))

    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'e amanhã?')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))

    await waitFor(() => expect(runTurnMock).toHaveBeenCalledTimes(2))
    const enviados = runTurnMock.mock.calls[1][0]
    assertTranscriptBemFormado(enviados)
    // A mensagem de reparo também deve avisar o modelo do cancelamento —
    // sem isso o modelo nunca sabe que o gestor disse não.
    const respostaC1 = (enviados as Array<{ role: string; tool_call_id?: string; content?: string }>)
      .find((m) => m.role === 'tool' && m.tool_call_id === 'c1')
    expect(respostaC1?.content).toMatch(/cancel/i)
  })

  it('enviar nova mensagem com proposta pendente (sem clicar Cancelar) também repara o transcript', async () => {
    runTurnMock.mockResolvedValueOnce({
      kind: 'proposal', messages: transcriptComPropostaPendente,
      proposta: { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' },
    })
    runTurnMock.mockResolvedValueOnce({ kind: 'text', messages: [], text: 'ok' })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'remarca pra sexta')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    await screen.findByRole('button', { name: /confirmar/i }) // card pendente, NÃO clica em cancelar

    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'esquece, marca pra outro dia')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))

    await waitFor(() => expect(runTurnMock).toHaveBeenCalledTimes(2))
    const enviados = runTurnMock.mock.calls[1][0]
    assertTranscriptBemFormado(enviados)
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

  it('sequência de produção — monta com a folha fechada, abre, e o primeiro toque no mic grava normalmente', async () => {
    // `page.tsx` monta `ChatAgenda` com `chatAberto` inicial `false` —
    // o componente nunca desmonta, só a folha some por dentro do
    // BottomSheet. O efeito que observa `open` roda já na montagem
    // (open=false) e chamava `pararEDescartar()` incondicionalmente;
    // sem uma guarda de "nada em voo", isso armava a flag de descarte
    // ANTES de qualquer gravação existir. O gestor então abria a
    // folha e o PRIMEIRO toque legítimo no mic era descartado em
    // silêncio — `gravando` nunca virava `true`, sem erro nenhum.
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

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = montar({ open: false }, qc) // como em produção: monta fechado

    rerender(
      <QueryClientProvider client={qc}>
        <ChatAgenda open onClose={() => {}} payload={payload as never} />
      </QueryClientProvider>,
    )

    const mic = screen.getByRole('button', { name: /ditar/i })
    await userEvent.click(mic) // primeiro toque, depois de abrir
    await userEvent.click(await screen.findByRole('button', { name: /parar gravação/i }))

    const input = screen.getByPlaceholderText(/escreva/i) as HTMLInputElement
    await waitFor(() => expect(input.value).toBe('remarca a visita do João'))
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

  describe('markdown na bolha do assistente', () => {
    it('**negrito** vira elemento de negrito de verdade, sem asterisco visível', async () => {
      runTurnMock.mockResolvedValue({
        kind: 'text', messages: [], text: 'Isso é **importante** para você.',
      })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      // Precisa achar um ELEMENTO de negrito de verdade (não só o texto
      // "importante" solto) — um teste que só checasse presença de texto
      // passaria igual sem nenhuma renderização de markdown.
      const negrito = await screen.findByText('importante')
      expect(negrito.tagName).toBe('STRONG')
      // `**`, não `*` solto: um asterisco isolado pode legitimamente
      // aparecer em copy futura (marcador de campo obrigatório etc.) sem
      // relação nenhuma com este teste — checar o par é o que prova
      // markdown cru sobrando, sem depender de nunca haver um `*` solto
      // em lugar nenhum da tela.
      expect(container.textContent).not.toContain('**')
    })

    it('lista com marcador e lista numerada viram listas de verdade (<ul>/<ol>/<li>)', async () => {
      runTurnMock.mockResolvedValue({
        kind: 'text', messages: [],
        text: '- primeiro item\n- segundo item\n\n1. passo um\n2. passo dois',
      })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText('primeiro item')
      const ul = container.querySelector('ul')
      const ol = container.querySelector('ol')
      expect(ul).toBeTruthy()
      expect(ol).toBeTruthy()
      expect(ul?.querySelectorAll('li').length).toBe(2)
      expect(ol?.querySelectorAll('li').length).toBe(2)
      // Marcador/numeração real, não texto cru "- primeiro item".
      expect(container.textContent).not.toContain('- primeiro item')
      expect(container.textContent).not.toContain('1. passo um')
    })

    it('a bolha do PRÓPRIO GESTOR não passa por markdown: os asteriscos continuam visíveis', async () => {
      // Manda **x** como mensagem do usuário (não do modelo) e afirma que
      // vira texto cru na tela — se algum dia a bolha do gestor passar a
      // ser renderizada como markdown por engano, este teste quebra.
      runTurnMock.mockResolvedValue({ kind: 'text', messages: [], text: 'ok' })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), '**x**')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      expect(await screen.findByText('**x**')).toBeTruthy()
      // Nenhum <strong> na tela pode ter vindo da bolha do gestor — a
      // resposta mockada do assistente ("ok") não tem markdown nenhum, então
      // qualquer <strong> encontrado só poderia vir de uma renderização
      // indevida da bolha do próprio gestor.
      expect(container.querySelector('strong')).toBeNull()
    })

    it('link em markdown NÃO vira âncora — teste de segurança', async () => {
      // Este é o teste que tem que quebrar de verdade se alguém reabilitar
      // links depois: afirma ausência de QUALQUER elemento <a> na bolha,
      // não presença de texto (que passaria mesmo com um <a> renderizado).
      runTurnMock.mockResolvedValue({
        kind: 'text', messages: [],
        text: 'Veja mais em [clique aqui](https://exemplo.com/malicioso).',
      })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText(/clique aqui/)
      expect(container.querySelector('a')).toBeNull()
    })

    it('imagem em markdown NÃO renderiza <img> — teste de segurança (espelha o de link acima)', async () => {
      // A spec chama link E imagem de inegociáveis, mas só o de link tinha
      // teste — assimetria: se `'img'` fosse acrescentado por engano a
      // `ELEMENTOS_PERMITIDOS`, nada aqui acusaria. `alt` não vira texto
      // visível quando `unwrapDisallowed` descarta a `img` (a tag não tem
      // filho de texto), então a espera usa texto ao redor da imagem.
      runTurnMock.mockResolvedValue({
        kind: 'text', messages: [],
        text: 'Veja a imagem: ![foto do equipamento](https://exemplo.com/malicioso.png) já anexada.',
      })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText(/já anexada/)
      expect(container.querySelector('img')).toBeNull()
    })

    it('HTML cru no texto do modelo aparece escapado, não interpretado', async () => {
      runTurnMock.mockResolvedValue({
        kind: 'text', messages: [],
        text: 'Antes <script>alert(1)</script> e <b>depois</b>.',
      })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await waitFor(() => expect(container.textContent).toContain('depois'))
      // Nenhum elemento real criado a partir do HTML cru.
      expect(container.querySelector('script')).toBeNull()
      expect(container.querySelector('b')).toBeNull()
      // O texto continua visível na tela, só não interpretado — os
      // ângulos aparecem como texto literal, não como tag.
      expect(container.textContent).toContain('<script>alert(1)</script>')
      expect(container.textContent).toContain('<b>depois</b>')
    })

    it('bloco de código não duplica o fundo do código inline (pre sobrescreve o code aninhado)', async () => {
      // Achado de review: um bloco ``` vira `<pre><code>...</code></pre>` —
      // o MESMO componente `code` usado pro código inline se aplica aqui
      // dentro também. Sem neutralizar o fundo/padding dele dentro do
      // `pre`, o bloco duplicava o "quadradinho" do inline dentro do fundo
      // do próprio bloco.
      runTurnMock.mockResolvedValue({ kind: 'text', messages: [], text: '```\nfoo bar\n```' })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText('foo bar')
      const pre = container.querySelector('pre')
      const code = pre?.querySelector('code')
      expect(pre).toBeTruthy()
      expect(code).toBeTruthy()
      // O `pre` precisa neutralizar via CSS descendente o fundo/padding do
      // `code` aninhado — sem isso o fundo dobra visualmente.
      expect(pre?.className).toContain('[&_code]:bg-transparent')
    })
  })

  describe('painel de debug (tokens e chamadas da IA)', () => {
    it('a resposta do assistente traz um dobrável fechado com os argumentos crus da ferramenta chamada', async () => {
      runTurnMock.mockResolvedValue({
        kind: 'text', messages: [], text: 'Você tem 7 visitas.',
        tracos: [
          {
            modelo: 'gemma-4-31b-it', duracaoMs: 2000,
            usage: { prompt_tokens: 4000, completion_tokens: 150, total_tokens: 4150 },
            chamadas: [{
              nome: 'buscar_agenda',
              argumentos: '{"date_from":"2026-09-23","date_to":"2026-09-30"}',
              resultado: '7 visitas (2126, 2128, 2130…)',
            }],
          },
          { modelo: 'gemma-4-31b-it', duracaoMs: 1400, chamadas: [{ nome: 'texto' }] },
        ],
      })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'o que tenho essa semana?')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText(/7 visitas\./)

      const details = container.querySelector('details')
      expect(details).toBeTruthy()
      expect(details?.hasAttribute('open')).toBe(false)
      // Fechado ou não, o conteúdo estrutural existe no DOM (o navegador
      // que decide o que fica visível) — os argumentos crus que provam se
      // o modelo mandou a data certa têm que estar lá.
      expect(container.textContent).toContain('{"date_from":"2026-09-23","date_to":"2026-09-30"}')
    })

    it('o card de proposta também mostra o painel de debug com os argumentos que geraram a proposta', async () => {
      runTurnMock.mockResolvedValue({
        kind: 'proposal', messages: [],
        proposta: {
          toolCallId: 'c1', name: 'atualizar_visita',
          args: { visita_id: 87, date: '2026-10-16' }, resumo: 'r',
          tracos: [{
            modelo: 'gemma-4-31b-it', duracaoMs: 900,
            chamadas: [{
              nome: 'atualizar_visita',
              argumentos: '{"visita_id":87,"date":"2026-10-16"}',
              resultado: 'aguardando confirmação do gestor',
            }],
          }],
        },
      })
      const { container } = montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'remarca pra sexta')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByRole('button', { name: /confirmar/i })
      expect(container.querySelector('details')).toBeTruthy()
      expect(container.textContent).toContain('{"visita_id":87,"date":"2026-10-16"}')
    })

    it('o rodapé da sessão acumula chamadas e tokens ao longo de várias mensagens', async () => {
      runTurnMock
        .mockResolvedValueOnce({
          kind: 'text', messages: [], text: 'primeira resposta',
          tracos: [{ duracaoMs: 100, usage: { prompt_tokens: 100, completion_tokens: 10, total_tokens: 110 }, chamadas: [{ nome: 'texto' }] }],
        })
        .mockResolvedValueOnce({
          kind: 'text', messages: [], text: 'segunda resposta',
          tracos: [{ duracaoMs: 100, usage: { prompt_tokens: 50, completion_tokens: 5, total_tokens: 55 }, chamadas: [{ nome: 'texto' }] }],
        })
      montar()
      // Sem rodapé antes da primeira resposta.
      expect(screen.queryByText(/chamadas ·/)).toBeNull()

      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'oi')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText('primeira resposta')
      expect(await screen.findByText(/1 chamada ·/)).toBeTruthy()

      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'e agora?')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText('segunda resposta')
      // 100+50 = 150 entrada, 10+5 = 15 saída → 165 tokens no total.
      expect(await screen.findByText(/2 chamadas · 165 tokens/)).toBeTruthy()
    })

    it('rodapé mostra custo só quando alguma volta trouxe usage.cost; sem isso, só tokens', async () => {
      runTurnMock.mockResolvedValue({
        kind: 'text', messages: [], text: 'resposta',
        tracos: [{ duracaoMs: 100, usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 }, chamadas: [{ nome: 'texto' }] }],
      })
      montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'oi')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText('resposta')
      expect(screen.queryByText(/US\$/)).toBeNull()
    })

    it('rodapé mostra o custo acumulado com vírgula (pt-BR), não ponto — consistente com o resto do painel', async () => {
      runTurnMock.mockResolvedValue({
        kind: 'text', messages: [], text: 'resposta',
        tracos: [{
          duracaoMs: 100,
          usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15, cost: 2.78e-6 },
          chamadas: [{ nome: 'texto' }],
        }],
      })
      montar()
      await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'oi')
      await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
      await screen.findByText('resposta')
      // Vírgula, não ponto — e 6 casas pra não sumir em "0,0000".
      expect(await screen.findByText(/US\$ 0,000003/)).toBeTruthy()
      expect(screen.queryByText(/US\$ 0\.000003/)).toBeNull()
    })
  })
})
