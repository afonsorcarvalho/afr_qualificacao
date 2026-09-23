// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useDitado } from './useDitado'

// `toast` (default export) é usado tanto como função (`toast(msg)`, aviso
// neutro do auto-stop) quanto com `.error` (falha de transcrição) — o dublê
// precisa ser as duas coisas ao mesmo tempo, não só um objeto com `.error`.
const { toastMock } = vi.hoisted(() => ({
  toastMock: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}))
vi.mock('react-hot-toast', () => ({ default: toastMock }))

class FakeRecorder {
  static ultima: FakeRecorder | null = null
  // A cascata de mimeType em useDitado.ts chama isTypeSupported antes de
  // instanciar o gravador — sem esse stub, `new MediaRecorder(...)`
  // nunca roda: quebra com "isTypeSupported is not a function".
  static isTypeSupported() { return true }
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  state = 'inactive'
  // >= MIN_BLOB_BYTES por padrão de propósito: este dublê serve o caminho
  // feliz da maioria dos testes deste arquivo — um blob de 1 byte cairia no
  // piso de "gravação muito curta" assim que ele existisse, e derrubaria
  // toda transcrição esperada nesses testes por um motivo que não é o que
  // eles querem exercitar. Testes do piso (agora por RAJADA, não mais só
  // por gravação) setam `bytesAoParar` num valor pequeno antes de fechar a
  // rajada que querem sub-piso.
  bytesAoParar = 2000
  constructor(public stream: unknown) {
    FakeRecorder.ultima = this
  }
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['x'.repeat(this.bytesAoParar)], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

// Dublê do nível de áudio: por padrão fica ACIMA do limiar de silêncio
// (0.01 em deteccaoSilencio.ts) — "tem voz" é o default seguro, porque a
// maioria dos testes deste arquivo não mexe em rajadas/silêncio nenhuma, e
// um RMS 0 por padrão marcaria toda rajada como `houveVoz: false` e
// quebraria a suíte inteira de um jeito que pareceria bug de lógica, não
// fixture. Só os testes de rajada pedem silêncio explicitamente, setando
// `nivel` antes de avançar o relógio falso.
class FakeAnalyserNode {
  fftSize = 2048
  nivel = 0.5
  getFloatTimeDomainData(buffer: Float32Array) {
    buffer.fill(this.nivel)
  }
}

class FakeAudioContext {
  static ultima: FakeAudioContext | null = null
  closed = false
  // 'running' por padrão (não 'suspended'): a maioria dos testes deste
  // arquivo não tem nada a ver com o resume() do item 2 — se o padrão
  // fosse 'suspended', TODO teste passaria a await um resume() extra,
  // mudando quando exatamente o `MediaRecorder`/analyser ficam prontos e
  // quebrando timing que os outros 36 testes já assumem. Só o teste
  // dedicado do resume usa um contexto suspenso, com uma classe própria.
  state: 'suspended' | 'running' | 'closed' = 'running'
  analyser: FakeAnalyserNode | null = null
  constructor() {
    FakeAudioContext.ultima = this
  }
  createMediaStreamSource(_stream: unknown) {
    return { connect: () => {} }
  }
  createAnalyser() {
    this.analyser = new FakeAnalyserNode()
    return this.analyser
  }
  close() {
    this.closed = true
    return Promise.resolve()
  }
}

/** Mesmo `name`/`message` que um erro real de `getUserMedia` negado/bloqueado
 *  traz — é o `name`, não a `message`, que `nomeDoErro`/`useDitado` usam para
 *  distinguir "permissão negada" de "falha genérica" (ver lib/utils/erro.ts). */
function erroComNome(name: string, message = name) {
  const e = new Error(message)
  e.name = name
  return e
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
  FakeAudioContext.ultima = null
  toastMock.mockClear()
  toastMock.error.mockClear()
  ;(globalThis as any).MediaRecorder = FakeRecorder
  ;(globalThis as any).AudioContext = FakeAudioContext
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

  it('falha de transcrição (503) não deixa o hook travado em gravando, não chama onTexto, e AVISA o gestor', async () => {
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
    // Requisito B: um 503 não pode mais sumir em silêncio — o toast usa o
    // `{error}` do corpo da resposta, mesmo formato do MicButton.tsx.
    expect(toastMock.error).toHaveBeenCalledWith('IA: IA não configurada')
  })

  it('falha de rede (fetch lança) também avisa o gestor — o catch não é mais "silencioso de propósito"', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch')) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(result.current.transcrevendo).toBe(false))
    expect(onTexto).not.toHaveBeenCalled()
    expect(toastMock.error).toHaveBeenCalledWith('IA: Failed to fetch')
  })

  it('sucesso não dispara nenhum toast de erro — a regressão que importa é o caminho feliz virar barulhento', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'remarca a visita do João' }), { status: 200 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('remarca a visita do João'))
    expect(toastMock.error).not.toHaveBeenCalled()
  })

  it('200 com text vazio (só ruído/silêncio na gravação) avisa "Transcrição vazia" e NÃO chama onTexto', async () => {
    // Fix round 1: este é o sintoma relatado de verdade — a resposta veio
    // ok (`res.ok === true`), então o caminho de erro do requisito B nunca
    // roda. Sem este `else`, um 200 com `text: ''` cai no mesmo silêncio
    // que motivou a task inteira. Mesmo aviso do `MicButton.tsx:68`.
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: '' }), { status: 200 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(result.current.transcrevendo).toBe(false))
    expect(onTexto).not.toHaveBeenCalled()
    expect(toastMock.error).toHaveBeenCalledWith('Transcrição vazia')
  })

  it('200 sem o campo text nenhum também avisa "Transcrição vazia" e NÃO chama onTexto', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(result.current.transcrevendo).toBe(false))
    expect(onTexto).not.toHaveBeenCalled()
    expect(toastMock.error).toHaveBeenCalledWith('Transcrição vazia')
  })

  it('permissão de microfone negada (NotAllowedError) avisa com o texto de permissão, e o mic continua utilizável depois', async () => {
    // Antes deste fix: catch fazia `iniciando=false; setGravando(false);
    // return` sem toast nenhum — clicar no mic e a permissão ser negada não
    // produzia texto, erro nem qualquer pista na tela. Requisito: mesma
    // mensagem que `MicButton.tsx:137` usa para o mesmo `name` de erro, os
    // dois mics não podem divergir no que dizem pro gestor.
    const getUserMediaMock = vi.fn().mockRejectedValue(erroComNome('NotAllowedError'))
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = getUserMediaMock
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => { await result.current.alternar() })

    expect(toastMock.error).toHaveBeenCalledWith('Permita microfone nas configurações do navegador')
    expect(result.current.gravando).toBe(false)
    expect(getUserMediaMock).toHaveBeenCalledTimes(1)

    // Não basta não travar em `gravando=true` — o `iniciando` guard (usado
    // pra bloquear reentrância) tem que ter sido limpo também, senão o botão
    // fica morto pra sempre depois da primeira negação. Prova: uma tentativa
    // seguinte, agora concedida, tem que conseguir gravar.
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })
    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)
  })

  it('getUserMedia rejeitando com outro erro (não permissão) avisa com o texto genérico', async () => {
    ;(globalThis as any).navigator.mediaDevices.getUserMedia =
      vi.fn().mockRejectedValue(new Error('dispositivo ocupado'))
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => { await result.current.alternar() })

    expect(toastMock.error).toHaveBeenCalledWith('Falha ao acessar microfone')
    expect(result.current.gravando).toBe(false)
  })

  it('MediaRecorder lançando na construção avisa (não vira unhandled rejection) e para as tracks do stream já obtido', async () => {
    // O achado do review final: getUserMedia já tinha resolvido e
    // `streamRef.current` já apontava pro stream quando a escolha de
    // mimeType/`new MediaRecorder(...)` rodava FORA de qualquer try — uma
    // exceção ali virava unhandled rejection de um onClick, e a luz do
    // microfone ficava acesa sem nenhum controle na tela pra apagar.
    class FakeRecorderQuebrado {
      static isTypeSupported() { return true }
      constructor() {
        throw new Error('mimeType não suportado')
      }
    }
    ;(globalThis as any).MediaRecorder = FakeRecorderQuebrado
    const pararTrack = vi.fn()
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: pararTrack }] })
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => { await result.current.alternar() })

    expect(toastMock.error).toHaveBeenCalledWith('Falha ao acessar microfone')
    expect(result.current.gravando).toBe(false)
    // A asserção que importa de verdade: o stream JÁ obtido não pode ficar
    // órfão — assert no stop de verdade, não só na flag `gravando`.
    expect(pararTrack).toHaveBeenCalled()
    // O AudioContext é criado ANTES do `new MediaRecorder(...)` (Task 2) —
    // se a construção do gravador falhar depois disso, o contexto já
    // existente não pode ficar pendurado. `close()` é chamado pelo catch
    // de `alternar()`, o mesmo que solta a track.
    expect(FakeAudioContext.ultima?.closed).toBe(true)

    // Nenhuma ref pode ficar pendurada: `pararEDescartar()` (que roda no
    // unmount / fechar a folha) tem que encontrar "nada em voo" e não tentar
    // parar a mesma track de novo.
    act(() => { result.current.pararEDescartar() })
    expect(pararTrack).toHaveBeenCalledTimes(1)
  })

  it('navegador sem MediaRecorder avisa "não suportado" e nunca chama getUserMedia', async () => {
    ;(globalThis as any).MediaRecorder = undefined
    const getUserMediaMock = (globalThis as any).navigator.mediaDevices.getUserMedia
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => { await result.current.alternar() })

    expect(toastMock.error).toHaveBeenCalledWith('Gravação não suportada neste navegador')
    expect(getUserMediaMock).not.toHaveBeenCalled()
    expect(result.current.gravando).toBe(false)
  })

  it('sem internet (navigator.onLine === false) avisa e nunca chama getUserMedia', async () => {
    // Não adianta gravar se a transcrição não vai conseguir ser enviada —
    // mesmo pré-check que `MicButton.tsx:85-88` já faz antes de pedir o mic.
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    const getUserMediaMock = (globalThis as any).navigator.mediaDevices.getUserMedia
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => { await result.current.alternar() })

    expect(toastMock.error).toHaveBeenCalledWith('Sem internet — IA indisponível')
    expect(getUserMediaMock).not.toHaveBeenCalled()
    expect(result.current.gravando).toBe(false)
  })

  it('blob abaixo de MIN_BLOB_BYTES (clique duplo, sem tempo de capturar áudio) avisa "muito curta" e NÃO chama onTexto', async () => {
    // Diferente do MicButton (segurar-para-falar, com cronômetro visível): o
    // mic do chat é clicar-pra-alternar, e um clique duplo (começa, pára na
    // hora) é interação NORMAL aqui — sem o mesmo piso que MicButton.tsx:114
    // já usa, isso cai direto no silêncio que a task inteira existe pra
    // fechar.
    ;(globalThis as any).MediaRecorder = FakeRecorderAtrasado
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() }) // inicia
    const mr = FakeRecorderAtrasado.instancias[FakeRecorderAtrasado.instancias.length - 1]
    mr.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) }) // 1 byte, < MIN_BLOB_BYTES
    await act(async () => { await result.current.alternar() }) // pede pra parar

    await act(async () => { await mr.onstop?.() })

    expect(toastMock.error).toHaveBeenCalledWith('Gravação muito curta, segure mais tempo')
    expect(onTexto).not.toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.transcrevendo).toBe(false)
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
    // >= MIN_BLOB_BYTES: este teste segue até B transcrever de verdade lá
    // embaixo, não é o teste do piso.
    mrB.ondataavailable?.({ data: new Blob(['audio de B'.repeat(200)], { type: 'audio/webm' }) })

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
    // >= MIN_BLOB_BYTES: A e B são transcritas de verdade neste teste, não é
    // o teste do piso.
    mrA.ondataavailable?.({ data: new Blob(['audio de A'.repeat(200)], { type: 'audio/webm' }) })
    await act(async () => { await result.current.alternar() }) // pede pra parar A

    // Sem esperar o onstop de A (que ainda não chegou), o gestor toca
    // de novo — B começa.
    await act(async () => { await result.current.alternar() })
    const mrB = FakeRecorderAtrasado.instancias[1]
    mrB.ondataavailable?.({ data: new Blob(['audio de B'.repeat(200)], { type: 'audio/webm' }) })

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
    // >= MIN_BLOB_BYTES: este teste espera transcrição de verdade lá
    // embaixo, não é o teste do piso.
    mrA.ondataavailable?.({ data: new Blob(['audio de A'.repeat(200)], { type: 'audio/webm' }) })
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
    // >= MIN_BLOB_BYTES: este teste precisa passar pelo fetch de verdade
    // (sucesso e falha), não pelo piso de "muito curta".
    mr1.ondataavailable?.({ data: new Blob(['x'.repeat(2000)], { type: 'audio/webm' }) })
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
    mr2.ondataavailable?.({ data: new Blob(['x'.repeat(2000)], { type: 'audio/webm' }) })

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

  // Requisito C: diferente do MicButton (segurar-para-falar, com cronômetro
  // visível na tela), o mic do chat é clicar-pra-alternar e não mostra
  // duração nenhuma — sem um limite, o gestor pode deixar gravando por
  // minutos. A OpenRouter documenta ~60s de timeout por requisição nos
  // provedores upstream: uma gravação mais longa que isso vira, cedo ou
  // tarde, um pedido recusado por tempo. `MicButton.tsx` já usa o mesmo
  // `MAX_DURATION_MS` pro mesmo motivo.
  it('gravação sem soltar o mic pára sozinha aos 60s, avisa o gestor, e ainda transcreve o que foi gravado', async () => {
    vi.useFakeTimers()
    try {
      // `mockImplementation` (não `mockResolvedValue`): o nível de áudio
      // padrão do dublê é "voz" (ver FakeAnalyserNode), então ao longo de
      // 60s a rajada fecha várias vezes pelo TETO de duração (8s, ver
      // `deteccaoSilencio.ts`) — cada fechamento chama fetch de novo, e um
      // único objeto `Response` reaproveitado só deixa o corpo ser lido
      // (`.json()`) uma vez; da segunda chamada em diante ele quebraria
      // silenciosamente e a rajada cairia no balde de "Transcrição vazia".
      globalThis.fetch = vi.fn().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ text: 'fala de mais de 60 segundos' }), { status: 200 })),
      ) as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      expect(result.current.gravando).toBe(true)

      // Só 59.9s: ainda não pode ter parado sozinho.
      await act(async () => { await vi.advanceTimersByTimeAsync(59_900) })
      expect(result.current.gravando).toBe(true)
      expect(toastMock).not.toHaveBeenCalled()

      // Cruza os 60s: auto-stop dispara.
      await act(async () => { await vi.advanceTimersByTimeAsync(100) })

      expect(result.current.gravando).toBe(false)
      // Avisa o gestor — sem cronômetro na tela, a parada sozinha seria
      // indistinguível de um bug.
      expect(toastMock).toHaveBeenCalled()
      // `waitFor` não serve sob fake timers (seu polling também depende de
      // `setTimeout`, que está congelado) — `advanceTimersByTimeAsync` já
      // drena a cadeia inteira (parar → onstop → fetch → onTexto), então a
      // asserção é direta, sem espera.
      expect(onTexto).toHaveBeenCalledWith('fala de mais de 60 segundos')
    } finally {
      vi.useRealTimers()
    }
  })

  it('parar manualmente antes dos 60s desarma o auto-stop (não dispara um segundo stop/aviso depois)', async () => {
    // Sem desarmar, o timer de 60s da tentativa A dispararia mais tarde e
    // chamaria `parar()` de novo — inofensivo pro `recorder.current` (já é
    // `null`), mas dispararia um toast de auto-stop sobre uma gravação que
    // já tinha sido parada pelo próprio gestor, confundindo mais do que
    // ajudando.
    vi.useFakeTimers()
    try {
      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ text: 'ok' }), { status: 200 }),
      ) as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() }) // inicia
      await act(async () => { await result.current.alternar() }) // gestor pára em seguida
      expect(result.current.gravando).toBe(false)
      toastMock.mockClear()

      await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
      expect(toastMock).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('fechar a folha (pararEDescartar) antes dos 60s também desarma o auto-stop', async () => {
    // Mesmo risco do teste acima, outro gatilho: `pararEDescartar()` zera
    // `recorder.current`/`streamRef.current`, mas se o timer de auto-stop
    // sobreviver, ele dispara depois sobre uma tentativa já descartada —
    // `parar()` chamaria `setTranscrevendo(true)` sem nenhum `onstop` vindo
    // pra devolver a `false` depois (a tentativa já foi cancelada, não vai
    // transcrever nada), deixando o botão "ocupado" pra sempre. Como
    // `ChatAgenda` nunca desmonta quando a folha fecha, essa é exatamente a
    // classe de falha muda que esta task existe pra fechar.
    vi.useFakeTimers()
    try {
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() }) // inicia
      act(() => { result.current.pararEDescartar() }) // folha fecha com o mic ligado
      expect(result.current.gravando).toBe(false)
      toastMock.mockClear()

      await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })

      expect(toastMock).not.toHaveBeenCalled()
      // A asserção que importa de verdade: sem isso, `transcrevendo` fica
      // `true` pra sempre e o botão de mic nunca mais sai do estado
      // "ocupado" — travado, não só sem aviso.
      expect(result.current.transcrevendo).toBe(false)
      expect(onTexto).not.toHaveBeenCalled()
      // AudioContext fechado neste caminho de parada também — senão cada
      // "fechar a folha com o mic ligado" vaza um contexto de áudio.
      expect(FakeAudioContext.ultima?.closed).toBe(true)
    } finally {
      vi.useRealTimers()
    }
  })

  // --- Task 2: gravação em rajadas ---

  it('fecha rajada por silêncio, envia o áudio, e a gravação continua sozinha (sem segundo clique)', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = vi.fn().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ text: 'primeira rajada' }), { status: 200 })),
      )
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      expect(result.current.gravando).toBe(true)

      // O nível padrão do dublê já é "voz" (ver FakeAnalyserNode) — uma
      // amostra assim garante `houveVoz: true` antes de cair pro silêncio.
      const analyser = FakeAudioContext.ultima!.analyser!
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      // Silêncio sustentado por tempo suficiente (minRajadaMs 1500 +
      // silencioMs 700, com folga) fecha a rajada sozinha.
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(onTexto).toHaveBeenCalledWith('primeira rajada')
      // Nem clicou de novo, nem a gravação parou — é exatamente o ponto da
      // task: pra quem está falando, a gravação nunca para.
      expect(result.current.gravando).toBe(true)
      expect(FakeRecorder.ultima).not.toBeNull()
      expect(FakeRecorder.ultima?.state).toBe('recording')
    } finally {
      vi.useRealTimers()
    }
  })

  it('rajada sem nenhuma leitura de voz nunca é enviada pro servidor (hazard de alucinação do Whisper)', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = vi.fn().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ text: 'segunda rajada' }), { status: 200 })),
      )
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!
      // Silêncio DESDE O INÍCIO — nenhuma leitura desta rajada é voz.
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) }) // fecha a 1ª rajada

      expect(fetchMock).not.toHaveBeenCalled()

      // A sessão continua viva: uma rajada seguinte COM voz sobe normal.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(onTexto).toHaveBeenCalledWith('segunda rajada')
    } finally {
      vi.useRealTimers()
    }
  })

  it('rajada abaixo do piso no meio da sessão é descartada sem aviso, e a rajada seguinte entrega texto normalmente', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = vi.fn().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ text: 'segunda rajada' }), { status: 200 })),
      )
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Uma leitura de voz (pra `houveVoz` ficar `true` e a rajada ganhar
      // número/tentar subir), mas o gravador só captura 1 byte quando a
      // rajada fechar — sub-piso, "clicou e não deu tempo de captar áudio".
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(50) })
      FakeRecorder.ultima!.bytesAoParar = 1
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) }) // fecha a 1ª rajada

      expect(fetchMock).not.toHaveBeenCalled()
      expect(toastMock.error).not.toHaveBeenCalled()

      // Segunda rajada: tamanho normal (default do dublê), fecha por
      // silêncio de novo, e desta vez sobra texto de verdade.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(onTexto).toHaveBeenCalledWith('segunda rajada')
      expect(toastMock.error).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('respostas fora de ordem são entregues na ordem certa (rajada 2 responde antes da 1)', async () => {
    vi.useFakeTimers()
    try {
      const resolvers: Array<(r: Response) => void> = []
      const fetchMock = vi.fn().mockImplementation(() => new Promise<Response>((resolve) => resolvers.push(resolve)))
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Fecha a rajada 1 por silêncio (dispara o fetch #1, ainda pendente).
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      // Fecha a rajada 2 por silêncio (dispara o fetch #2, ainda pendente).
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      expect(fetchMock).toHaveBeenCalledTimes(2)

      // A rajada 2 responde PRIMEIRO.
      await act(async () => {
        resolvers[1](new Response(JSON.stringify({ text: 'dois' }), { status: 200 }))
        for (let i = 0; i < 5; i++) await Promise.resolve()
      })
      // Ainda represada: não é a vez dela — a rajada 1 não respondeu ainda.
      expect(onTexto).not.toHaveBeenCalled()

      // A rajada 1 responde por último.
      await act(async () => {
        resolvers[0](new Response(JSON.stringify({ text: 'um' }), { status: 200 }))
        for (let i = 0; i < 5; i++) await Promise.resolve()
      })

      expect(onTexto.mock.calls.map((c) => c[0])).toEqual(['um', 'dois'])
    } finally {
      vi.useRealTimers()
    }
  })

  it('falha de uma rajada não derruba a sessão, e avisa só uma vez mesmo que mais de uma rajada falhe', async () => {
    vi.useFakeTimers()
    try {
      let chamada = 0
      const fetchMock = vi.fn().mockImplementation(() => {
        chamada += 1
        if (chamada <= 2) return Promise.reject(new Error('Failed to fetch'))
        return Promise.resolve(new Response(JSON.stringify({ text: 'terceira rajada' }), { status: 200 }))
      })
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Três rajadas seguidas, cada uma fechando por silêncio.
      for (let i = 0; i < 3; i++) {
        analyser.nivel = 0.5
        await act(async () => { await vi.advanceTimersByTimeAsync(400) })
        analyser.nivel = 0
        await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      }

      expect(fetchMock).toHaveBeenCalledTimes(3)
      // Duas falharam, uma só é avisada — não é chuva de toast por rajada.
      expect(toastMock.error).toHaveBeenCalledTimes(1)
      expect(toastMock.error).toHaveBeenCalledWith('IA: Failed to fetch')
      expect(onTexto).toHaveBeenCalledWith('terceira rajada')
      // A sessão não foi derrubada pelas falhas — continua gravando.
      expect(result.current.gravando).toBe(true)
    } finally {
      vi.useRealTimers()
    }
  })

  it('sessão inteira sem texto nenhum avisa "Gravação muito curta" uma única vez, mesmo com várias rajadas', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = vi.fn()
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Duas rajadas sem voz nenhuma: fecham por silêncio, nunca sobem.
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      // Clica pra parar: a rajada final sobe SEMPRE, mas sai sub-piso.
      FakeRecorder.ultima!.bytesAoParar = 1
      await act(async () => { await result.current.alternar() })

      expect(fetchMock).not.toHaveBeenCalled()
      expect(toastMock.error).toHaveBeenCalledTimes(1)
      expect(toastMock.error).toHaveBeenCalledWith('Gravação muito curta, segure mais tempo')
      expect(result.current.transcrevendo).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  // Fix round 1 (review): a guarda de `houveVoz` inicialmente pulava a
  // rajada FINAL incondicionalmente ("clique manual sempre sobe") — sem
  // teste nenhum cobrindo o caso comum: o gestor termina de falar, o
  // detector fecha a penúltima rajada ~700ms depois (silêncio sustentado),
  // uma rajada nova nasce, e o clique de "parar" chega um pouco depois —
  // essa última rajada é só o rabo de silêncio entre a fala e o clique,
  // sem nenhuma leitura de voz. Sem a guarda, ela subia mesmo assim, e o
  // hazard medido na Task 1 (Whisper alucinando texto tipo "E aí"/"." pra
  // áudio sem fala, com HTTP 200) chegava na caixa de texto do gestor por
  // cima do que ele já tinha ditado de verdade. A rajada final só tem
  // direito a subir sem voz quando é a ÚLTIMA chance da sessão (nenhum
  // texto foi entregue ainda) — ver o teste de "sessão inteira sem texto"
  // logo acima, que cobre esse outro lado da mesma guarda.
  it('rajada final sem nenhuma leitura de voz não é enviada quando a sessão já entregou texto (tail de silêncio depois da fala)', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = vi.fn().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ text: 'primeiro texto' }), { status: 200 })),
      )
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Rajada 1: fala de verdade, fecha por silêncio, entrega texto —
      // `textoEntregue` fica `true` a partir daqui.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(onTexto).toHaveBeenCalledWith('primeiro texto')

      // Rajada 2 nasce automaticamente (silêncio contínuo desde o início
      // dela) — o gestor não fala mais nada, só demora um pouco pra
      // clicar em "parar". Nenhuma leitura desta rajada é voz.
      await act(async () => { await result.current.alternar() }) // clique manual de parar

      // A rajada final (só silêncio, sessão já com texto) NÃO pode subir.
      expect(fetchMock).toHaveBeenCalledTimes(1) // nenhuma chamada NOVA
      expect(result.current.transcrevendo).toBe(false)
      // E não é tratada como "sessão sem texto" — já tinha texto.
      expect(toastMock.error).not.toHaveBeenCalledWith('Gravação muito curta, segure mais tempo')
    } finally {
      vi.useRealTimers()
    }
  })

  // Fix round 2 (review): o teste acima cobre a metade "não sobe" do
  // `ultima ? (houveVoz || !textoEntregue) : houveVoz`. Esta é a OUTRA
  // metade, sem cobertura nenhuma até agora — e sem ela, o teste "sessão
  // inteira sem texto" (logo acima) passa pelo motivo ERRADO: ele seta
  // `bytesAoParar = 1` antes do clique final, então `expect(fetchMock).
  // not.toHaveBeenCalled()` passa por causa do PISO de tamanho
  // (`MIN_BLOB_BYTES`), não por causa do gate — passaria idêntico se
  // `!textoEntregue` fosse apagado da fórmula. Aqui o piso fica no default
  // da fixture (2000 bytes, bem acima do piso), de propósito, pra garantir
  // que só o GATE pode estar barrando (ou liberando) a chamada.
  //
  // Por que a branch importa: é o carve-out que protege a interação mais
  // comum do produto — clique, uma frase curta, clique de novo. Se o
  // detector nunca pegou uma leitura de RMS acima do limiar (fala baixa,
  // ou a frase inteira coube entre duas amostras de ~50ms — o caso comum
  // em qualquer sessão de um clique só, inclusive quase todos os 26 testes
  // originais deste arquivo), a rajada única da sessão TEM que subir —
  // sem isso, o gestor clica, fala, clica de novo, e não acontece nada,
  // sem erro nenhum na tela.
  it('rajada final sem nenhuma leitura de voz É ENVIADA quando a sessão ainda não produziu texto nenhum (última chance)', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ text: 'frase curta' }), { status: 200 }),
      )
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!
      // Silêncio DESDE O INÍCIO — nenhuma leitura desta rajada (a única da
      // sessão) é voz. Menos que minRajadaMs+silencioMs: não fecha por
      // conta própria, o clique de parar é quem fecha.
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(300) })

      // Sanity do próprio teste: se isto falhar, o teste não estaria
      // isolando o gate do piso de tamanho.
      expect(FakeRecorder.ultima!.bytesAoParar).toBe(2000)

      await act(async () => { await result.current.alternar() }) // clique manual de parar

      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(onTexto).toHaveBeenCalledWith('frase curta')
      expect(toastMock.error).not.toHaveBeenCalledWith('Gravação muito curta, segure mais tempo')
    } finally {
      vi.useRealTimers()
    }
  })

  it('AudioContext é fechado ao parar normalmente (segundo clique)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'ok' }), { status: 200 }),
    ) as unknown as typeof fetch
    const { result } = renderHook(() => useDitado(vi.fn()))

    await act(async () => { await result.current.alternar() })
    expect(FakeAudioContext.ultima?.closed).toBe(false)

    await act(async () => { await result.current.alternar() }) // segundo clique: pára
    expect(FakeAudioContext.ultima?.closed).toBe(true)
  })

  it('expõe o nível de áudio (RMS) da amostra mais recente, e zera ao parar', async () => {
    vi.useFakeTimers()
    try {
      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ text: 'ok' }), { status: 200 }),
      ) as unknown as typeof fetch
      const { result } = renderHook(() => useDitado(vi.fn()))

      expect(result.current.nivelAudio).toBe(0)

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!
      analyser.nivel = 0.3
      // Uma amostra (50ms) é suficiente pra atualizar o nível exposto.
      await act(async () => { await vi.advanceTimersByTimeAsync(50) })
      expect(result.current.nivelAudio).toBeCloseTo(0.3, 5)

      await act(async () => { await result.current.alternar() }) // pára
      expect(result.current.nivelAudio).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  // --- Onda de fix (2026-09-22-ditado-em-rajadas, review final) ---

  // Item 1 (crítico): ✕ / fechar a folha / desmontar não descartavam de
  // verdade uma rajada já em voo — o `controle.descartado` só era lido
  // ANTES do `await fetch`, então o texto ainda chegava um segundo depois
  // do clique em ✕, com o botão já dizendo "Descartar gravação".
  it('fix item 1: ✕ (pararEDescartar) enquanto uma rajada está em voo descarta de verdade — o texto dela nunca chega, mesmo que o fetch resolva depois', async () => {
    vi.useFakeTimers()
    try {
      const resolvers: Array<(r: Response) => void> = []
      const fetchMock = vi.fn().mockImplementation(() => new Promise<Response>((resolve) => resolvers.push(resolve)))
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Fecha a rajada 1 por silêncio — dispara o fetch, que fica em voo
      // (o dublê não resolve sozinho).
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // ✕ — AINDA gravando, o fetch da rajada 1 continua em voo.
      act(() => { result.current.pararEDescartar() })
      expect(result.current.gravando).toBe(false)

      // O fetch só agora resolve — um segundo (ou mais) depois do clique.
      await act(async () => {
        resolvers[0](new Response(JSON.stringify({ text: 'não pode aparecer' }), { status: 200 }))
        for (let i = 0; i < 5; i++) await Promise.resolve()
      })

      expect(onTexto).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('fix item 1: depois de descartar, uma sessão NOVA não recebe o texto da sessão antiga que ainda estava em voo (não vaza pro campo errado)', async () => {
    vi.useFakeTimers()
    try {
      const resolvers: Array<(r: Response) => void> = []
      const fetchMock = vi.fn().mockImplementation(() => new Promise<Response>((resolve) => resolvers.push(resolve)))
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      // Sessão A: fecha uma rajada por silêncio, fetch fica em voo.
      await act(async () => { await result.current.alternar() })
      const analyserA = FakeAudioContext.ultima!.analyser!
      analyserA.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyserA.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // ✕ descarta a sessão A ainda com o fetch dela em voo.
      act(() => { result.current.pararEDescartar() })

      // Sessão B começa — antes do fetch atrasado de A responder.
      await act(async () => { await result.current.alternar() })
      expect(result.current.gravando).toBe(true)

      // O fetch atrasado de A só resolve agora, com B já rodando.
      await act(async () => {
        resolvers[0](new Response(JSON.stringify({ text: 'texto de A, não pode vazar pra B' }), { status: 200 }))
        for (let i = 0; i < 5; i++) await Promise.resolve()
      })

      expect(onTexto).not.toHaveBeenCalled()
      // B não foi afetada pela contaminação.
      expect(result.current.gravando).toBe(true)
    } finally {
      vi.useRealTimers()
    }
  })

  // Item 2 (importante): o AudioContext nunca era resumido — em Safari/iOS
  // ele nasce `suspended` (foi construído fora do gesto original do
  // usuário, depois do `await getUserMedia`), e um contexto suspenso
  // devolve zeros em `getFloatTimeDomainData`: RMS travado em 0, nenhuma
  // rajada detecta voz, nada sobe no meio da sessão.
  it('fix item 2: AudioContext suspenso (iOS) é resumido — senão o RMS fica travado em 0 e nenhuma rajada detecta voz', async () => {
    class FakeAnalyserSuspenso {
      fftSize = 2048
      nivel = 0.5
      getFloatTimeDomainData(buffer: Float32Array) {
        // Enquanto suspenso, um AudioContext de verdade devolve SEMPRE
        // zero aqui — é esse o sintoma que o fix existe pra evitar.
        buffer.fill(CtxSuspenso.instancia!.state === 'suspended' ? 0 : this.nivel)
      }
    }
    class CtxSuspenso {
      static instancia: CtxSuspenso | null = null
      state: 'suspended' | 'running' = 'suspended'
      analyser: FakeAnalyserSuspenso | null = null
      resume = vi.fn().mockImplementation(() => {
        this.state = 'running'
        return Promise.resolve()
      })
      constructor() {
        CtxSuspenso.instancia = this
      }
      createMediaStreamSource() {
        return { connect: () => {} }
      }
      createAnalyser() {
        this.analyser = new FakeAnalyserSuspenso()
        return this.analyser
      }
      close() {
        return Promise.resolve()
      }
    }
    ;(globalThis as any).AudioContext = CtxSuspenso
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useDitado(vi.fn()))

      await act(async () => { await result.current.alternar() })

      expect(CtxSuspenso.instancia!.resume).toHaveBeenCalledTimes(1)
      expect(CtxSuspenso.instancia!.state).toBe('running')

      // O sintoma de verdade: sem o resume, o nível exposto ficaria preso
      // em 0 pra sempre, mesmo com "voz" no dublê.
      await act(async () => { await vi.advanceTimersByTimeAsync(50) })
      expect(result.current.nivelAudio).toBeGreaterThan(0)
    } finally {
      vi.useRealTimers()
    }
  })

  // Item 4 (importante): `MediaRecorder.stop()` supõe um gravador
  // `recording`/`paused` — se o stream morreu sozinho por fora (chamada
  // entrando, Bluetooth caindo, iOS pausando o app), o gravador já está
  // `inactive` e `stop()` lança `InvalidStateError`. Sem tratar, a sessão
  // trava pra sempre: `transcrevendo` nunca volta a `false`.
  it('fix item 4: MediaRecorder.stop() lançando (stream morto por fora) não trava a sessão — transcrevendo volta a false', async () => {
    class FakeRecorderQuebraNoStop {
      static isTypeSupported() { return true }
      ondataavailable: ((e: { data: Blob }) => void) | null = null
      onstop: (() => void) | null = null
      state = 'inactive' // já morreu sozinho antes do clique
      constructor(public stream: unknown) {}
      start() { this.state = 'recording' }
      stop() {
        throw new DOMException('already inactive', 'InvalidStateError')
      }
    }
    ;(globalThis as any).MediaRecorder = FakeRecorderQuebraNoStop
    const pararTrack = vi.fn()
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: pararTrack }] })
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() }) // inicia
    expect(result.current.gravando).toBe(true)

    // Clica em ✓ — parar() chama fecharRajadaAtual(..., true), que tenta
    // stop() e apanha o InvalidStateError.
    await act(async () => { await result.current.alternar() })

    expect(result.current.gravando).toBe(false)
    // A asserção que importa: sem o fix, isto ficava `true` pra sempre.
    expect(result.current.transcrevendo).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
    expect(onTexto).not.toHaveBeenCalled()
    // Track liberada mesmo sem o onstop normal ter rodado (era a ÚLTIMA
    // rajada da sessão).
    expect(pararTrack).toHaveBeenCalled()

    // O mic continua utilizável depois — não fica morto até recarregar.
    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)
  })

  // Item 5 (importante): o carve-out da rajada final usava `!textoEntregue`
  // ("já ENTREGOU texto?"), que depende de a resposta de rede ter voltado —
  // numa conexão de campo lenta, o gestor pode tocar ✓ antes de qualquer
  // rajada ter respondido, mesmo já tendo enviado uma de verdade. O fix
  // troca por "nenhuma rajada foi ENVIADA ainda nesta sessão", que não
  // depende de timing de rede.
  it('fix item 5: rajada final sem voz NÃO sobe quando outra rajada já foi enviada mas ainda não respondeu (rede lenta) — não duplica com alucinação', async () => {
    vi.useFakeTimers()
    try {
      let resolveBurst1: ((r: Response) => void) | null = null
      let chamada = 0
      const fetchMock = vi.fn().mockImplementation(() => {
        chamada += 1
        if (chamada === 1) return new Promise<Response>((resolve) => { resolveBurst1 = resolve })
        return Promise.resolve(new Response(JSON.stringify({ text: 'resposta inesperada' }), { status: 200 }))
      })
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Rajada 1: fala de verdade, fecha por silêncio — sobe (fetch #1),
      // mas a rede é lenta e a resposta NÃO chega ainda.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(onTexto).not.toHaveBeenCalled() // ainda não respondeu

      // Gestor clica em ✓ — a rajada final é só o silêncio desde o
      // fechamento da 1ª (nenhuma leitura de voz nela).
      await act(async () => { await result.current.alternar() })

      // A rajada final NÃO pode subir: já existe uma rajada enviada nesta
      // sessão (só ainda não respondeu — diferente de "nunca enviou").
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // Agora a rajada 1 responde de verdade.
      await act(async () => {
        resolveBurst1!(new Response(JSON.stringify({ text: 'texto real' }), { status: 200 }))
        for (let i = 0; i < 5; i++) await Promise.resolve()
      })

      expect(onTexto).toHaveBeenCalledWith('texto real')
      expect(onTexto).toHaveBeenCalledTimes(1) // nunca um segundo call (alucinação)
      expect(result.current.transcrevendo).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  // Item 6 (importante): sem timeout, um fetch que trava prende a rajada
  // (e, por causa da entrega estritamente em ordem, TODAS as seguintes)
  // pra sempre — `transcrevendo` nunca volta a `false`.
  it('fix item 6: fetch pendurado (rede travada) usa timeout — não prende as rajadas seguintes nem trava transcrevendo', async () => {
    vi.useFakeTimers()
    try {
      let chamada = 0
      const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        chamada += 1
        if (chamada === 1) {
          // Rajada 1: nunca resolve sozinha — só quando o AbortController
          // interno do próprio hook disparar (o timeout).
          return new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => {
              reject(new DOMException('The operation was aborted', 'AbortError'))
            })
          })
        }
        return Promise.resolve(new Response(JSON.stringify({ text: 'segunda rajada' }), { status: 200 }))
      })
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Fecha a rajada 1 por silêncio — dispara o fetch que vai travar.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // Fecha a rajada 2 por silêncio — não espera a 1ª pra subir.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      expect(fetchMock).toHaveBeenCalledTimes(2)

      // Encerra a sessão — a 2ª já teria resposta, mas fica represada
      // atrás da 1ª (entrega estritamente em ordem) até ela se resolver.
      await act(async () => { await result.current.alternar() })
      expect(onTexto).not.toHaveBeenCalled()
      expect(result.current.transcrevendo).toBe(true)

      // Passam os ~30s do timeout interno da rajada 1.
      await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })

      expect(onTexto).toHaveBeenCalledWith('segunda rajada')
      expect(result.current.transcrevendo).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  // Item 8 (minor): "Transcrição vazia" disparava POR RAJADA — podia
  // interromper uma sessão que, no fim das contas, ia funcionar (rajada 1
  // vazia, rajada 2 com a fala de verdade), e ainda roubava a vez do
  // "Gravação muito curta" no fim de uma sessão de verdade vazia.
  it('fix item 8: "Transcrição vazia" não interrompe uma sessão que ainda vai produzir texto — só decide no fim da sessão', async () => {
    vi.useFakeTimers()
    try {
      let chamada = 0
      const fetchMock = vi.fn().mockImplementation(() => {
        chamada += 1
        const texto = chamada === 1 ? '' : 'fala de verdade'
        return Promise.resolve(new Response(JSON.stringify({ text: texto }), { status: 200 }))
      })
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Rajada 1: leitura de voz, mas o Whisper devolve 200 com text vazio.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      // Sem o fix: dispararia 'Transcrição vazia' JÁ AQUI, no meio de uma
      // sessão que ainda vai funcionar.
      expect(toastMock.error).not.toHaveBeenCalled()

      // Rajada 2: fala de verdade, entrega texto.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      expect(onTexto).toHaveBeenCalledWith('fala de verdade')
      // Sessão produziu texto — nenhum aviso de "vazia" nem "muito curta".
      expect(toastMock.error).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('fix item 8: sessão inteira sem texto, mas com pelo menos uma rajada 200-vazia, avisa "Transcrição vazia" (não "muito curta")', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ text: '' }), { status: 200 }),
      )
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      await act(async () => { await result.current.alternar() }) // ✓ encerra

      expect(onTexto).not.toHaveBeenCalled()
      expect(toastMock.error).toHaveBeenCalledTimes(1)
      expect(toastMock.error).toHaveBeenCalledWith('Transcrição vazia')
      expect(result.current.transcrevendo).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  // --- Onda de resíduos (2026-09-22-ditado-em-rajadas, residuos-report) ---

  // Resíduo 1 (crítico): `pararEDescartar()` não abortava o
  // `AbortController` de 30s da rajada em voo — o timer corria até o fim e,
  // MEIO MINUTO depois do ✕, disparava `avisarFalhaUmaVez('IA: demorou
  // demais...')`. Por essa hora uma sessão nova plausivelmente já está em
  // andamento, com seu próprio `avisoFalhaMostrado` (closure separado, não
  // suprime nada) — um erro vermelho no meio de uma gravação que funciona.
  it('resíduo 1: descartar (✕) uma rajada em voo não deixa o timeout de 30s disparar um toast de erro depois, mesmo que o fetch acabe rejeitando', async () => {
    vi.useFakeTimers()
    try {
      // Fetch que só rejeita quando o `AbortController` INTERNO do hook
      // disparar (o timeout de 30s) — mesmo padrão do teste do item 6.
      const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            reject(new DOMException('The operation was aborted', 'AbortError'))
          })
        })
      })
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Fecha uma rajada por silêncio — dispara o fetch, que fica em voo
      // (só resolve/rejeita quando o timeout interno abortar).
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // ✕ — descarta a sessão AINDA com a rajada em voo.
      act(() => { result.current.pararEDescartar() })
      expect(result.current.gravando).toBe(false)
      toastMock.error.mockClear()

      // Passam os 30s do timeout interno da rajada — sem o fix, é agora
      // que o toast de erro dispararia, meio minuto depois do ✕.
      await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })

      expect(toastMock.error).not.toHaveBeenCalled()
      expect(onTexto).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  // Resíduo 2 (crítico): um `MediaRecorder` de verdade cujas tracks morrem
  // por fora vira `state='inactive'` SINCRONAMENTE e `stop()` lança — mas o
  // browser AINDA enfileira os eventos `dataavailable`/`stop`, que chegam
  // como uma task separada, atrasada. O catch de `fecharRajadaAtual` (item
  // 4) já trata o throw como falha, mas sem zerar `fechamento.numero`/
  // `contabilizada`, o `onstop` enfileirado que chega depois encontra os
  // dois ainda "vivos" e REENVIA a rajada pro servidor — e o `finally` dele
  // decrementa `rajadasEmVoo` uma SEGUNDA vez, o que pode fazer a sessão
  // finalizar cedo demais enquanto uma rajada legítima ainda está em voo.
  it('resíduo 2: MediaRecorder cujo stop() lança E AINDA ASSIM dispara onstop depois não reenvia a rajada, e rajadasEmVoo não vai a negativo (a sessão finaliza uma única vez, no momento certo)', async () => {
    class FakeRecorderPrimeiraQuebraDepoisDisparaOnstop {
      static instancias: FakeRecorderPrimeiraQuebraDepoisDisparaOnstop[] = []
      static isTypeSupported() { return true }
      ondataavailable: ((e: { data: Blob }) => void) | null = null
      onstop: (() => void) | null = null
      state = 'recording'
      ehPrimeira: boolean
      constructor(public stream: unknown) {
        this.ehPrimeira = FakeRecorderPrimeiraQuebraDepoisDisparaOnstop.instancias.length === 0
        FakeRecorderPrimeiraQuebraDepoisDisparaOnstop.instancias.push(this)
      }
      start() { this.state = 'recording' }
      stop() {
        // A 1ª rajada simula o hazard de verdade: `state` vira 'inactive'
        // SINCRONAMENTE e `stop()` lança — mas o browser real AINDA
        // enfileira `dataavailable`/`stop`, que o teste dispara manualmente
        // mais tarde (`instancias[0].ondataavailable?.(...)` + `.onstop?.()`),
        // simulando essa task atrasada. As rajadas seguintes se comportam
        // como um `MediaRecorder` normal (mesmo formato do `FakeRecorder`
        // do topo do arquivo).
        if (this.ehPrimeira) {
          this.state = 'inactive'
          throw new DOMException('already inactive', 'InvalidStateError')
        }
        this.state = 'inactive'
        this.ondataavailable?.({ data: new Blob(['x'.repeat(2000)], { type: 'audio/webm' }) })
        this.onstop?.()
      }
    }
    ;(globalThis as any).MediaRecorder = FakeRecorderPrimeiraQuebraDepoisDisparaOnstop
    ;(globalThis as any).navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })

    // A 2ª rajada (legítima) fica PENDENTE até o teste resolver na mão — é
    // essa janela em voo que expõe o contador indo a negativo.
    let resolveBurst2: ((r: Response) => void) | null = null
    const fetchMock = vi.fn().mockImplementation(() => new Promise<Response>((resolve) => { resolveBurst2 = resolve }))
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const onTexto = vi.fn()
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      // Fecha a 1ª rajada por silêncio — cai em `fecharRajadaAtual`, que
      // tenta `stop()` e apanha o throw. O catch (item 4) trata como falha;
      // como não é a última rajada, a 2ª (legítima) já começa sozinha.
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })

      expect(FakeRecorderPrimeiraQuebraDepoisDisparaOnstop.instancias).toHaveLength(2)
      expect(fetchMock).not.toHaveBeenCalled() // 1ª rajada falhou, nada subiu ainda

      // Dá voz pra 2ª rajada antes de encerrar a sessão (senão o carve-out
      // da rajada final sem voz entra em jogo e ela nunca sobe).
      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })

      // Clica em ✓: encerra a sessão com a 2ª rajada ainda em voo (fetch
      // pendente, controlado pelo teste).
      await act(async () => { await result.current.alternar() })
      expect(fetchMock).toHaveBeenCalledTimes(1) // só a 2ª rajada, de verdade
      expect(result.current.transcrevendo).toBe(true) // ainda tem rajada em voo

      // SÓ AGORA a task enfileirada da 1ª rajada (throw + onstop atrasado)
      // finalmente chega — com áudio de verdade, como um MediaRecorder
      // real entregaria mesmo depois do throw.
      // Sem `await` direto em `mr1.onstop?.()`: sem o fix, esse onstop
      // atrasado chama `fetch` de novo, e o dublê reatribui o resolver
      // capturado a ESSA chamada — esperar essa promise resolver aqui
      // travaria o teste pra sempre (é a própria manifestação do bug: a
      // rajada 1 nunca deveria ter voltado a depender de rede nenhuma).
      // Só drena as microtasks já agendadas, como o teste de "fora de
      // ordem" já faz.
      const mr1 = FakeRecorderPrimeiraQuebraDepoisDisparaOnstop.instancias[0]
      await act(async () => {
        mr1.ondataavailable?.({ data: new Blob(['x'.repeat(2000)], { type: 'audio/webm' }) })
        mr1.onstop?.()
        for (let i = 0; i < 5; i++) await Promise.resolve()
      })

      // O ponto central do fix: a 1ª rajada já tinha sido dada como falha
      // pelo catch — o evento atrasado NÃO pode reenviá-la pro servidor.
      expect(fetchMock).toHaveBeenCalledTimes(1) // continua só a 2ª — sem o fix, viraria 2
      // E o contador não foi a negativo: a sessão NÃO finalizou ainda,
      // porque a 2ª rajada (legítima) continua em voo.
      expect(result.current.transcrevendo).toBe(true)
      expect(toastMock.error).not.toHaveBeenCalled()

      // A 2ª rajada finalmente responde — a sessão finaliza UMA ÚNICA vez,
      // com o texto de verdade entregue.
      await act(async () => {
        resolveBurst2!(new Response(JSON.stringify({ text: 'segunda rajada' }), { status: 200 }))
        for (let i = 0; i < 5; i++) await Promise.resolve()
      })

      expect(onTexto).toHaveBeenCalledWith('segunda rajada')
      expect(result.current.transcrevendo).toBe(false)
      expect(toastMock.error).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  // Resíduo 3 (importante): o `clearTimeout` do timeout de 30s ficava num
  // `finally` que envolvia só o `fetch` — o timer era desarmado ANTES de
  // `res.json()` rodar. Um proxy que devolve cabeçalhos 200 e trava o corpo
  // (sem nunca fechar a conexão) passava incólume pelo `fetch` e travava
  // pra sempre em `res.json()`, sem o abort nunca disparar — a mesma classe
  // de falha que o item 6 original queria fechar, só que numa forma mais
  // estreita.
  it('resíduo 3: fetch cujo header resolve mas o corpo (json()) trava usa o abort — não fica pendurado pra sempre', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        // Cabeçalhos resolvem NA HORA (200 ok) — só o corpo trava, até o
        // abort (interno, 30s) disparar.
        const res = {
          ok: true,
          status: 200,
          json: () =>
            new Promise((_resolve, reject) => {
              init?.signal?.addEventListener('abort', () => {
                reject(new DOMException('The operation was aborted', 'AbortError'))
              })
            }),
        } as unknown as Response
        return Promise.resolve(res)
      })
      globalThis.fetch = fetchMock as unknown as typeof fetch
      const onTexto = vi.fn()
      const { result } = renderHook(() => useDitado(onTexto))

      await act(async () => { await result.current.alternar() })
      const analyser = FakeAudioContext.ultima!.analyser!

      analyser.nivel = 0.5
      await act(async () => { await vi.advanceTimersByTimeAsync(400) })
      analyser.nivel = 0
      await act(async () => { await vi.advanceTimersByTimeAsync(2_300) })
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // Encerra a sessão — a rajada fica represada em `res.json()`.
      await act(async () => { await result.current.alternar() })
      expect(result.current.transcrevendo).toBe(true) // ainda travada no corpo

      // Sem o fix, o `clearTimeout` já rodou (no finally do fetch) e este
      // avanço não teria efeito nenhum — a rajada ficaria pendurada pra
      // sempre, `transcrevendo` travado em `true`.
      await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })

      // O `catch` em volta de `res.json()` (linha ~508, pré-existente,
      // fora do escopo deste fix) já engole QUALQUER erro de leitura do
      // corpo — inclusive o `AbortError` que o abort produz — tratando
      // como "sem json: proxy, 502, corpo vazio". Por isso a rajada cai no
      // balde de "transcrição vazia", não no de falha de rede: o que
      // importa pra este item é que ela CAI em algum balde terminal (não
      // fica pendurada pra sempre, nem finge sucesso).
      expect(result.current.transcrevendo).toBe(false)
      expect(onTexto).not.toHaveBeenCalled()
      expect(toastMock.error).toHaveBeenCalledWith('Transcrição vazia')
    } finally {
      vi.useRealTimers()
    }
  })
})
