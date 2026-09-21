// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useDitado } from './useDitado'

class FakeRecorder {
  static ultima: FakeRecorder | null = null
  // A cascata de mimeType em useDitado.ts chama isTypeSupported antes de
  // instanciar o gravador — sem esse stub, `new MediaRecorder(...)`
  // nunca roda: quebra com "isTypeSupported is not a function".
  static isTypeSupported() { return true }
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  state = 'inactive'
  constructor(public stream: unknown) {
    FakeRecorder.ultima = this
  }
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

// Gravador cujo `stop()` NÃO dispara `onstop` sozinho — o teste dispara
// manualmente, mais tarde, simulando o evento `stop` atrasado de um
// MediaRecorder real (thread principal ocupada, pausa de GC, celular
// lento). Serve só aos testes de corrida entre gerações; os demais usam
// o `FakeRecorder` de cima, que dispara na hora.
class FakeRecorderAtrasado {
  static instancias: FakeRecorderAtrasado[] = []
  static isTypeSupported() { return true }
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  constructor(public stream: unknown) {
    FakeRecorderAtrasado.instancias.push(this)
  }
  start() {}
  stop() {
    // de propósito: nada acontece aqui. O teste chama `onstop` quando
    // quiser simular a chegada do evento atrasado.
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  FakeRecorder.ultima = null
  FakeRecorderAtrasado.instancias = []
  ;(globalThis as any).MediaRecorder = FakeRecorder
  ;(globalThis as any).navigator.mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }),
  }
})

describe('useDitado', () => {
  it('grava, transcreve e entrega o texto pelo callback', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'remarca a visita do João' }), { status: 200 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)

    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('remarca a visita do João'))
    expect(result.current.gravando).toBe(false)
  })

  it('falha de transcrição não deixa o hook travado em gravando', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: 'IA não configurada' }), { status: 503 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(result.current.transcrevendo).toBe(false))
    expect(result.current.gravando).toBe(false)
    expect(onTexto).not.toHaveBeenCalled()
  })

  it('permissão de microfone negada não quebra', async () => {
    ;(globalThis as any).navigator.mediaDevices.getUserMedia =
      vi.fn().mockRejectedValue(new Error('NotAllowedError'))
    const { result } = renderHook(() => useDitado(vi.fn()))
    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(false)
  })

  it('dois cliques sem esperar o primeiro abrem só um stream de microfone', async () => {
    // Sem a proteção de reentrância, o segundo `alternar()` reentra no
    // ramo de início (gravando ainda é `false` nesse closure, o
    // primeiro `getUserMedia` ainda não resolveu), chama getUserMedia
    // de novo e sobrescreve `recorder.current` — o primeiro stream fica
    // órfão, com as tracks nunca paradas (mic ligado sem controle).
    const getUserMediaMock = (globalThis as any).navigator.mediaDevices.getUserMedia
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => {
      const p1 = result.current.alternar()
      const p2 = result.current.alternar() // reentra ANTES do primeiro await resolver
      await Promise.all([p1, p2])
    })

    expect(getUserMediaMock).toHaveBeenCalledTimes(1)
    expect(result.current.gravando).toBe(true)
  })

  it('desmontar durante a gravação para as tracks do stream (não fica com o mic ligado atrás de uma tela que já foi embora)', async () => {
    const pararTrack = vi.fn()
    // `getTracks()` devolve um array novo a cada chamada — o que importa
    // pra asserção é que `stop` seja SEMPRE a mesma referência de mock.
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: pararTrack }] })
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result, unmount } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)

    unmount()

    expect(pararTrack).toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled() // desmontar descarta, não transcreve
    expect(onTexto).not.toHaveBeenCalled()
  })

  it('fechar a tela com a permissão do microfone ainda pendente descarta o stream sem nunca gravar', async () => {
    // Janela diferente da anterior: aqui NÃO existe MediaRecorder ainda
    // — a interrupção chega enquanto `getUserMedia` está em voo. Sem
    // tratar esse caso, o stream recém-concedido vira um gravador
    // completo depois que a tela já "fechou".
    const pararTrack = vi.fn()
    let resolverGetUserMedia!: (v: unknown) => void
    const getUserMediaPendente = new Promise((resolve) => {
      resolverGetUserMedia = resolve
    })
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockReturnValue(getUserMediaPendente)
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { result } = renderHook(() => useDitado(vi.fn()))

    let alternarPromise!: Promise<void>
    act(() => {
      alternarPromise = result.current.alternar()
    })
    expect(result.current.gravando).toBe(false) // ainda pendente

    act(() => {
      result.current.pararEDescartar()
    })

    await act(async () => {
      resolverGetUserMedia({ getTracks: () => [{ stop: pararTrack }] })
      await alternarPromise
    })

    expect(result.current.gravando).toBe(false)
    expect(pararTrack).toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()

    // Não basta descartar sem quebrar — o mic tem que continuar
    // utilizável depois. Se `iniciando` não for limpo nesse ramo de
    // descarte, o botão fica morto pra sempre depois de um único
    // "fechar enquanto pedia permissão", em silêncio, sem nenhum dos
    // outros testes deste arquivo notar.
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })
    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)
  })

  it('pararEDescartar() ocioso (nada gravando, nada pendente) não envenena a próxima gravação legítima', async () => {
    // Reproduz a sequência de produção: `_ChatAgenda.tsx` chama
    // `pararEDescartar()` toda vez que `open` é `false` — inclusive na
    // montagem inicial, com a folha fechada e NADA acontecendo ainda.
    // Sem uma guarda de "nada em voo", isso armava `descartarRef`
    // incondicionalmente; a flag sobrevivia até o primeiro toque
    // legítimo no mic, que era descartado em silêncio — `gravando`
    // nunca virava `true`, sem nenhum erro na tela.
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    act(() => {
      result.current.pararEDescartar() // ocioso: nada gravando, nada pendente
    })
    expect(result.current.gravando).toBe(false)

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'remarca a visita do João' }), { status: 200 }),
    ) as unknown as typeof fetch

    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)

    await act(async () => { await result.current.alternar() }) // pára e transcreve
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('remarca a visita do João'))
  })

  // Sequência que o coordinator apontou como alcançável em qualquer
  // celular lento, sem precisar de timing sub-milissegundo: fechar a
  // folha durante uma gravação só PEDE pro MediaRecorder parar — o
  // evento `stop` fica na fila. Se a thread principal estiver ocupada
  // (ou houver uma pausa de GC) tempo suficiente, o gestor consegue
  // reabrir a folha e começar uma gravação NOVA antes desse evento
  // atrasado chegar. Sem um jeito de cada tentativa se identificar, o
  // `onstop` atrasado da tentativa A encontra o sinal de descarte já
  // consumido pela tentativa B e segue adiante — só que os bytes que
  // ele tem em mãos são os de A. O texto que chega no campo é de uma
  // fala que o gestor nem fez nessa gravação.
  it('onstop atrasado da gravação A não transcreve o áudio de A, e a gravação B (já em andamento) segue normal', async () => {
    ;(globalThis as any).MediaRecorder = FakeRecorderAtrasado
    const pararTrackA = vi.fn()
    const pararTrackB = vi.fn()
    let chamadas = 0
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi.fn().mockImplementation(() => {
      chamadas += 1
      const pararTrack = chamadas === 1 ? pararTrackA : pararTrackB
      return Promise.resolve({ getTracks: () => [{ stop: pararTrack }] })
    })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'texto da gravação B' }), { status: 200 }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    // Gravação A começa e recebe áudio.
    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)
    const mrA = FakeRecorderAtrasado.instancias[0]
    mrA.ondataavailable?.({ data: new Blob(['audio de A, não pode vazar'], { type: 'audio/webm' }) })

    // A folha fecha com A ainda gravando: pede o stop, mas o evento
    // NÃO chega ainda (é justamente isso que este teste controla).
    act(() => { result.current.pararEDescartar() })
    expect(result.current.gravando).toBe(false)

    // O gestor reabre e grava de novo — B começa ANTES do onstop
    // atrasado de A aparecer.
    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)
    const mrB = FakeRecorderAtrasado.instancias[1]
    mrB.ondataavailable?.({ data: new Blob(['audio de B'], { type: 'audio/webm' }) })

    // SÓ AGORA o evento atrasado de A finalmente chega.
    await act(async () => { await mrA.onstop?.() })

    // Nem o fetch nem o callback podem ter rodado por causa do evento
    // atrasado de A — nenhum dos dois, em nenhuma hipótese.
    expect(fetchMock).not.toHaveBeenCalled()
    expect(onTexto).not.toHaveBeenCalled()
    expect(pararTrackA).toHaveBeenCalled() // track ainda tem que ser liberada

    // B não foi afetada — continua gravando, e termina normalmente.
    // `FakeRecorderAtrasado.stop()` também não dispara `onstop`
    // sozinho (a mesma classe serve os dois gravadores deste teste),
    // então o evento de B precisa ser simulado explicitamente, como o
    // de A — a diferença é que aqui ele chega LOGO em seguida, sem
    // atraso nenhum, exatamente como o caminho feliz de parar-e-transcrever.
    expect(result.current.gravando).toBe(true)
    await act(async () => { await result.current.alternar() }) // pede o stop de B
    await act(async () => { await mrB.onstop?.() }) // evento de B chega, sem atraso
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('texto da gravação B'))
    expect(pararTrackB).toHaveBeenCalled()
  })

  it('onstop atrasado da gravação A não dispara fetch com os chunks de A', async () => {
    ;(globalThis as any).MediaRecorder = FakeRecorderAtrasado
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'não deveria nem ser chamado' }), { status: 200 }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => { await result.current.alternar() }) // A
    const mrA = FakeRecorderAtrasado.instancias[0]
    mrA.ondataavailable?.({ data: new Blob(['audio de A'], { type: 'audio/webm' }) })

    act(() => { result.current.pararEDescartar() })

    await act(async () => { await result.current.alternar() }) // B, antes do onstop de A chegar

    await act(async () => { await mrA.onstop?.() }) // onstop atrasado de A

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
