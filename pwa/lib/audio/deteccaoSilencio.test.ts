import { describe, it, expect } from 'vitest'
import {
  calcularRms,
  criarEstadoRajada,
  avaliarRajada,
  LIMIARES_RAJADA_PADRAO,
  type LimiaresRajada,
  type EstadoRajada,
} from './deteccaoSilencio'

describe('calcularRms', () => {
  it('sinal nulo (silêncio total) dá RMS zero', () => {
    const amostras = new Float32Array(256) // já nasce zerado
    expect(calcularRms(amostras)).toBe(0)
  })

  it('senóide de amplitude cheia bate com o valor fechado 1/√2', () => {
    // Valor esperado NÃO vem de rodar a implementação: é a identidade
    // clássica RMS de seno = amplitude/√2. Para não depender de
    // aproximação numérica de uma janela qualquer, a amostragem usa N=800
    // amostras cobrindo exatamente f=100 ciclos. Isso faz
    // Σ sin²(2π·f·k/N) = N/2 EXATO (não aproximado): a soma dos termos
    // cos(2·2π·f·k/N) sobre um período completo é zero sempre que
    // 2f não é múltiplo de N — aqui 2f=200, que não divide N=800 — pela
    // identidade Σ_{k=0}^{N-1} cos(2πmk/N) = 0 para m não múltiplo de N.
    // Logo RMS = √(1/2) = Math.SQRT1_2, com a única imprecisão sendo a do
    // ponto flutuante, não do método.
    const N = 800
    const f = 100
    const amostras = new Float32Array(N)
    for (let k = 0; k < N; k++) {
      amostras[k] = Math.sin((2 * Math.PI * f * k) / N)
    }
    expect(calcularRms(amostras)).toBeCloseTo(Math.SQRT1_2, 4)
  })
})

describe('avaliarRajada', () => {
  // Limiar de silêncio bem acima do ruído de RMS zero e bem abaixo do RMS
  // de voz usado nos testes — a leitura "silêncio" e a leitura "voz" nunca
  // ficam ambíguas perto do limiar.
  const VOZ = 0.5
  const SILENCIO = 0.001

  it('vírgula: silêncio curto no meio da fala não fecha a rajada, e a pausa seguinte não herda o instante da pausa anterior', () => {
    let estado = criarEstadoRajada(0)

    // fala normalmente até passar o piso mínimo da rajada
    let r = avaliarRajada(estado, VOZ, 0)
    expect(r.fecharRajada).toBe(false)
    estado = r.estado

    r = avaliarRajada(estado, VOZ, 1600) // > minRajadaMs (1500)
    expect(r.fecharRajada).toBe(false)
    estado = r.estado

    // vírgula: 300ms de silêncio, abaixo dos 700ms de silencioMs
    r = avaliarRajada(estado, SILENCIO, 1900)
    expect(r.fecharRajada).toBe(false)
    estado = r.estado
    r = avaliarRajada(estado, SILENCIO, 2200) // 300ms de silêncio acumulado
    expect(r.fecharRajada).toBe(false)
    estado = r.estado

    // fala retoma antes de bater silencioMs — a pausa foi só a vírgula
    r = avaliarRajada(estado, VOZ, 2250)
    expect(r.fecharRajada).toBe(false)
    // Hazard: se o início do silêncio não for limpo aqui, uma pausa CURTA
    // seguinte começaria a contar a partir do instante da vírgula anterior
    // em vez de do zero — e fecharia cedo demais, achando que o silêncio
    // já vinha se arrastando desde antes da fala retomar.
    expect(r.estado.silencioDesdeMs).toBeNull()
    estado = r.estado

    // nova pausa curta (outra vírgula), também abaixo de silencioMs: se o
    // reset acima não tivesse acontecido, esta chamada teria "herdado"
    // silêncio desde 1900 (duração > 700ms) e fecharia — não deve.
    r = avaliarRajada(estado, SILENCIO, 2500)
    expect(r.fecharRajada).toBe(false)
  })

  it('silêncio sustentado acima de silencioMs fecha (rajada já passou do mínimo)', () => {
    let estado = criarEstadoRajada(0)
    let r = avaliarRajada(estado, VOZ, 0)
    estado = r.estado
    r = avaliarRajada(estado, VOZ, 1600) // rajada já > minRajadaMs (1500)
    estado = r.estado

    r = avaliarRajada(estado, SILENCIO, 1600) // silêncio começa aqui
    expect(r.fecharRajada).toBe(false)
    estado = r.estado

    // 750ms de silêncio > silencioMs (700) e rajada (2350ms) > minRajadaMs
    r = avaliarRajada(estado, SILENCIO, 2350)
    expect(r.fecharRajada).toBe(true)
  })

  it('silêncio sustentado ANTES de minRajadaMs não fecha — senão toda respiração vira uma requisição', () => {
    let estado = criarEstadoRajada(0)
    // silêncio desde o instante zero da rajada (ex.: gestor demorou a
    // começar a falar depois de clicar no mic)
    let r = avaliarRajada(estado, SILENCIO, 0)
    expect(r.fecharRajada).toBe(false)
    estado = r.estado

    // 750ms de silêncio (> silencioMs=700) mas a rajada só tem 750ms de
    // vida (< minRajadaMs=1500): não pode fechar aqui, ou uma respiração
    // isolada logo no início vira burst+requisição sozinha.
    r = avaliarRajada(estado, SILENCIO, 750)
    expect(r.fecharRajada).toBe(false)
    estado = r.estado

    // o mesmo silêncio, agora que a rajada finalmente bateu o piso, fecha
    // — prova que a rajada não ficou travada para sempre, só esperou o
    // piso mínimo.
    r = avaliarRajada(estado, SILENCIO, 1500)
    expect(r.fecharRajada).toBe(true)
  })

  it('fala contínua sem pausa fecha ao bater maxRajadaMs, mesmo sem nenhum silêncio', () => {
    let estado = criarEstadoRajada(0)
    let r = avaliarRajada(estado, VOZ, 0)
    estado = r.estado
    r = avaliarRajada(estado, VOZ, 4000)
    expect(r.fecharRajada).toBe(false)
    estado = r.estado

    // um instante antes do teto: ainda não fecha
    r = avaliarRajada(estado, VOZ, 7999)
    expect(r.fecharRajada).toBe(false)
    estado = r.estado

    // bateu o teto exato (maxRajadaMs=8000): fecha por duração, não por
    // silêncio (nunca houve silêncio nesta sequência)
    r = avaliarRajada(estado, VOZ, 8000)
    expect(r.fecharRajada).toBe(true)
  })

  it('depois de fechar, o estado reinicia — a rajada seguinte não herda os contadores da anterior', () => {
    let estado = criarEstadoRajada(0)
    let r = avaliarRajada(estado, VOZ, 0)
    estado = r.estado
    r = avaliarRajada(estado, VOZ, 1600)
    estado = r.estado
    r = avaliarRajada(estado, SILENCIO, 1600)
    estado = r.estado
    r = avaliarRajada(estado, SILENCIO, 2350) // fecha aqui (caso já coberto acima)
    expect(r.fecharRajada).toBe(true)
    estado = r.estado

    // Hazard: se `inicioMs`/`silencioDesdeMs` não voltarem a zero neste
    // ponto, a PRÓXIMA leitura (10ms depois, já em silêncio) herdaria uma
    // rajada "de 2360ms" e um silêncio "já sustentado" da rajada anterior
    // — e fecharia de novo, imediatamente, sem nunca ter havido fala.
    expect(estado.inicioMs).toBe(2350)
    expect(estado.silencioDesdeMs).toBeNull()

    r = avaliarRajada(estado, SILENCIO, 2360)
    expect(r.fecharRajada).toBe(false)
  })

  it('limiares são sobrescrevíveis — override customizado muda a decisão em relação ao default', () => {
    const limiaresCurtos: LimiaresRajada = {
      ...LIMIARES_RAJADA_PADRAO,
      minRajadaMs: 100,
      silencioMs: 50,
    }
    let estado = criarEstadoRajada(0)
    let r = avaliarRajada(estado, VOZ, 0, limiaresCurtos)
    estado = r.estado
    r = avaliarRajada(estado, SILENCIO, 150) // rajada já > 100ms (override)
    estado = r.estado
    // 60ms de silêncio > silencioMs=50 (override); com os defaults (700ms)
    // esta mesma leitura NÃO fecharia — é o override que muda o resultado.
    r = avaliarRajada(estado, SILENCIO, 210, limiaresCurtos)
    expect(r.fecharRajada).toBe(true)

    // confirma que, com os thresholds default, a mesma sequência de tempo
    // não fecharia (750ms totais de rajada, mas só 60ms de silêncio).
    let estadoPadrao = criarEstadoRajada(0)
    let rPadrao = avaliarRajada(estadoPadrao, VOZ, 0)
    estadoPadrao = rPadrao.estado
    rPadrao = avaliarRajada(estadoPadrao, SILENCIO, 150)
    estadoPadrao = rPadrao.estado
    rPadrao = avaliarRajada(estadoPadrao, SILENCIO, 210)
    expect(rPadrao.fecharRajada).toBe(false)
  })

  it('valores default batem com o acordado: silencioMs=700, minRajadaMs=1500, maxRajadaMs=8000', () => {
    expect(LIMIARES_RAJADA_PADRAO.limiarSilencio).toBe(0.01)
    expect(LIMIARES_RAJADA_PADRAO.silencioMs).toBe(700)
    expect(LIMIARES_RAJADA_PADRAO.minRajadaMs).toBe(1500)
    expect(LIMIARES_RAJADA_PADRAO.maxRajadaMs).toBe(8000)
  })

  it('leitura exatamente NO limiar conta como voz — um limiar que "vaza" pra cima classifica fala baixinho como silêncio e corta no meio da palavra', () => {
    const estadoEmVoz: EstadoRajada = { inicioMs: 0, silencioDesdeMs: null }

    const noLimiar = avaliarRajada(estadoEmVoz, LIMIARES_RAJADA_PADRAO.limiarSilencio, 100)
    // no limiar exato: ainda é voz (corte é `rms < limiar`, não `<=`)
    expect(noLimiar.estado.silencioDesdeMs).toBeNull()
    expect(noLimiar.fecharRajada).toBe(false)

    const logoAbaixo = avaliarRajada(
      estadoEmVoz,
      LIMIARES_RAJADA_PADRAO.limiarSilencio - 0.0001,
      100,
    )
    // um fio abaixo: já é silêncio, e o início da contagem é este instante
    expect(logoAbaixo.estado.silencioDesdeMs).toBe(100)
  })
})
