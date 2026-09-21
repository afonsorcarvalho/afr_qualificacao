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

  // O round 3 corrigiu a contaminação (A vazando pra transcrição), mas
  // trocou um booleano único por um contador de geração — e um
  // contador não distingue "existe uma tentativa mais nova" de "esta
  // tentativa foi cancelada". `parar()` (segundo toque no mic, o
  // gestor QUER a transcrição) não muda a geração, mas o próximo
  // `alternar()` que começa do zero muda — então: A pára (pedido
  // legítimo), o botão fica com cara de ocioso enquanto o `onstop`
  // assíncrono de A ainda não chegou, o gestor toca de novo achando
  // que nada aconteceu, B nasce e avança a geração, e quando o
  // `onstop` de A finalmente chega, a checagem de geração descarta o
  // áudio de A — mesmo ele tendo sido parado de propósito.
  it('parar() legítimo transcreve o áudio de A mesmo com uma gravação nova (B) já em andamento quando o onstop atrasado de A chega', async () => {
    ;(globalThis as any).MediaRecorder = FakeRecorderAtrasado
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })
    const respostas = ['texto de A', 'texto de B']
    let chamadasFetch = 0
    const fetchMock = vi.fn().mockImplementation(() => {
      const texto = respostas[chamadasFetch] ?? 'resposta inesperada'
      chamadasFetch += 1
      return Promise.resolve(new Response(JSON.stringify({ text: texto }), { status: 200 }))
    })
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    // A começa, recebe áudio, e é parada NORMALMENTE — o gestor quer a
    // transcrição (não é `pararEDescartar()`, é o segundo toque no
    // mic, via `alternar()`).
    await act(async () => { await result.current.alternar() })
    const mrA = FakeRecorderAtrasado.instancias[0]
    mrA.ondataavailable?.({ data: new Blob(['audio de A'], { type: 'audio/webm' }) })
    await act(async () => { await result.current.alternar() }) // pede pra parar A

    // Sem esperar o onstop de A (que ainda não chegou), o gestor toca
    // de novo — B começa.
    await act(async () => { await result.current.alternar() })
    const mrB = FakeRecorderAtrasado.instancias[1]
    mrB.ondataavailable?.({ data: new Blob(['audio de B'], { type: 'audio/webm' }) })

    // SÓ AGORA o onstop atrasado de A chega — ele TEM que transcrever,
    // mesmo com B já em andamento.
    await act(async () => { await mrA.onstop?.() })
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('texto de A'))

    // B não foi afetada — continua gravando e termina normalmente.
    expect(result.current.gravando).toBe(true)
    await act(async () => { await result.current.alternar() }) // pede o stop de B
    await act(async () => { await mrB.onstop?.() })
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('texto de B'))
  })

  // O teste acima não cobre a janela que `parar()` limpando
  // `tentativaAtual` de fato protege: ali, uma gravação NOVA (B) nasce
  // antes do `onstop` de A chegar, e o próprio início de B já
  // sobrescreve `tentativaAtual.current` — a limpeza feita por
  // `parar()` nem chega a ser necessária nesse caminho específico
  // (confirmado por mutação: remover só aquela linha não derruba o
  // teste acima). O caso que ela protege é este: `pararEDescartar()`
  // chamado DEPOIS de `parar()` mas ANTES de qualquer gravação nova
  // nascer — sem limpar a referência, `pararEDescartar()` encontraria
  // `tentativaAtual` ainda apontando pra A e cancelaria um pedido de
  // transcrição que o gestor fez de propósito.
  it('fechar a folha logo depois de parar() não cancela a transcrição que o gestor pediu de propósito', async () => {
    ;(globalThis as any).MediaRecorder = FakeRecorderAtrasado
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'texto de A' }), { status: 200 }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    // A começa, recebe áudio, e é parada NORMALMENTE.
    await act(async () => { await result.current.alternar() })
    const mrA = FakeRecorderAtrasado.instancias[0]
    mrA.ondataavailable?.({ data: new Blob(['audio de A'], { type: 'audio/webm' }) })
    await act(async () => { await result.current.alternar() }) // pede pra parar A

    // A folha fecha logo em seguida — SEM nenhuma gravação nova ter
    // nascido ainda. `recorder.current` já é `null` (zerado por
    // `parar()`), mas `streamRef.current` ainda aponta pro stream de A
    // até o `onstop` dela rodar — é essa janela que este teste alveja.
    act(() => { result.current.pararEDescartar() })

    // O onstop atrasado de A finalmente chega — tem que transcrever,
    // porque o pedido veio de `parar()`, não de `pararEDescartar()`.
    await act(async () => { await mrA.onstop?.() })
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('texto de A'))
  })

  it('transcrevendo vira true na hora que o gestor pede pra parar, e volta a false quando a transcrição termina (sucesso e falha)', async () => {
    // Usa o gravador atrasado de propósito: sem ele, `FakeRecorder`
    // dispara `onstop` (e toda a cadeia até o `fetch`) na mesma
    // chamada síncrona de `.stop()`, e não haveria como observar o
    // instante EM QUE `parar()` liga `transcrevendo`, separado do
    // instante em que a transcrição finalmente termina.
    ;(globalThis as any).MediaRecorder = FakeRecorderAtrasado
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    // --- caminho de sucesso ---
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'ok' }), { status: 200 }),
    ) as unknown as typeof fetch

    await act(async () => { await result.current.alternar() }) // inicia
    const mr1 = FakeRecorderAtrasado.instancias[FakeRecorderAtrasado.instancias.length - 1]
    mr1.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })
    expect(result.current.transcrevendo).toBe(false) // só gravando, ainda não parou

    await act(async () => { await result.current.alternar() }) // pede pra parar
    // Síncrono: nada disparou `onstop` ainda (o dublê não dispara
    // sozinho) — se `transcrevendo` é `true` aqui, foi `parar()` quem
    // ligou, não uma transcrição que já rodou e voltou.
    expect(result.current.transcrevendo).toBe(true)

    await act(async () => { await mr1.onstop?.() }) // só agora a transcrição roda
    expect(result.current.transcrevendo).toBe(false)
    expect(onTexto).toHaveBeenCalledWith('ok')

    // --- caminho de falha ---
    onTexto.mockClear()
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: 'IA não configurada' }), { status: 503 }),
    ) as unknown as typeof fetch

    await act(async () => { await result.current.alternar() }) // inicia de novo
    const mr2 = FakeRecorderAtrasado.instancias[FakeRecorderAtrasado.instancias.length - 1]
    mr2.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })

    await act(async () => { await result.current.alternar() }) // pede pra parar
    expect(result.current.transcrevendo).toBe(true)

    await act(async () => { await mr2.onstop?.() })
    expect(result.current.transcrevendo).toBe(false)
    expect(onTexto).not.toHaveBeenCalled()
  })

  it('onstop atrasado de A não pode impedir pararEDescartar() de desligar o mic de B na hora (streamRef ainda tem que apontar pro stream de B)', async () => {
    // Round 3 acrescentou uma checagem de identidade em `streamRef`
    // (só zera a ref se ela ainda for O STREAM desta tentativa) sem
    // nenhum teste dedicado. Sem essa checagem, o `onstop` atrasado de
    // A apagaria a referência viva do stream de B, e o desligamento
    // SÍNCRONO do mic de `pararEDescartar()` (que depende de
    // `streamRef.current` pra parar as tracks na hora, sem esperar o
    // `onstop` de B) ficaria sem efeito nenhum — uma variante
    // "desligamento atrasado" do vazamento de privacidade do round 1.
    ;(globalThis as any).MediaRecorder = FakeRecorderAtrasado
    const pararTrackB = vi.fn()
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValueOnce({ getTracks: () => [{ stop: vi.fn() }] }) // A
      .mockResolvedValueOnce({ getTracks: () => [{ stop: pararTrackB }] }) // B
    const { result } = renderHook(() => useDitado(vi.fn()))

    // A começa e é descartada (folha fecha durante a gravação) — o
    // `onstop` dela ainda não chegou.
    await act(async () => { await result.current.alternar() })
    const mrA = FakeRecorderAtrasado.instancias[0]
    act(() => { result.current.pararEDescartar() })

    // B começa ANTES do onstop atrasado de A chegar.
    await act(async () => { await result.current.alternar() })

    // O onstop atrasado de A finalmente chega — NÃO pode apagar a
    // referência viva do stream de B.
    await act(async () => { await mrA.onstop?.() })

    // Fecha a folha de novo, agora com B gravando: o desligamento
    // síncrono do mic (via `streamRef`, ANTES do onstop de B rodar)
    // tem que continuar funcionando.
    act(() => { result.current.pararEDescartar() })
    expect(pararTrackB).toHaveBeenCalled()
  })

  // Cobertura extra, além dos 4 testes pedidos: "todo caminho de
  // saída" do onstop inclui o blob vazio (gravação parada rápido
  // demais pra capturar qualquer áudio) — `setTranscrevendo(true)`
  // agora roda em `parar()`, então esse caminho também precisa
  // devolver a false, senão o mic fica com cara de "ocupado" pra
  // sempre depois de uma gravação vazia.
  it('gravação sem áudio nenhum (blob vazio) também devolve transcrevendo a false', async () => {
    ;(globalThis as any).MediaRecorder = FakeRecorderAtrasado
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => { await result.current.alternar() }) // inicia — sem ondataavailable nenhum
    const mr = FakeRecorderAtrasado.instancias[FakeRecorderAtrasado.instancias.length - 1]
    await act(async () => { await result.current.alternar() }) // pede pra parar
    expect(result.current.transcrevendo).toBe(true)

    await act(async () => { await mr.onstop?.() }) // sem dados — blob vazio
    expect(result.current.transcrevendo).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
