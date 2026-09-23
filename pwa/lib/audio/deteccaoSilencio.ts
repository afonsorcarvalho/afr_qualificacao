// lib/audio/deteccaoSilencio.ts
// Decide ONDE cortar uma gravação de ditado em rajadas, sem depender de
// `MediaRecorder`, `AudioContext` ou React — é aritmética pura sobre
// `Float32Array` e sobre uma linha do tempo que quem chama fornece.
//
// O corte só é seguro porque acontece no silêncio (poucos ms de áudio se
// perdem ao parar/recomeçar o gravador entre rajadas — ver o plano em
// `docs/superpowers/plans/2026-09-22-ditado-em-rajadas.md`). Se o corte
// caísse no meio de uma palavra, as DUAS rajadas vizinhas saem degradadas.
// Por isso a máquina de decisão não lê o relógio: quem chama (a Task 2,
// dona do loop de áudio) é quem tem o `Date.now()` de verdade, e passa o
// instante como argumento. Isso torna o teste aritmética — soma de
// milissegundos — em vez de espera real, e evita que a máquina fique
// flaky numa máquina carregada.

/**
 * RMS (root mean square) de um bloco de amostras de áudio, no intervalo
 * [-1, 1] típico de `AnalyserNode.getFloatTimeDomainData`. É a medida de
 * "quão alto" o bloco é, usada como proxy de "tem fala aqui ou não".
 */
export function calcularRms(amostras: Float32Array): number {
  let somaDosQuadrados = 0
  for (let i = 0; i < amostras.length; i++) {
    somaDosQuadrados += amostras[i] * amostras[i]
  }
  return Math.sqrt(somaDosQuadrados / amostras.length)
}

export interface LimiaresRajada {
  /** RMS abaixo disto conta como silêncio. Piso de ruído de mic comum,
   * bem abaixo do RMS de fala normal — ajustável por quem chama conforme
   * o microfone/ambiente real se mostrar mais ruidoso. */
  limiarSilencio: number
  /** Quanto tempo de silêncio CONTÍNUO fecha a rajada. */
  silencioMs: number
  /** Piso: sem isto, toda respiração entre palavras vira uma rajada (e uma
   * requisição HTTP) sozinha. */
  minRajadaMs: number
  /** Teto: fala contínua sem nenhuma pausa também tem que fechar em algum
   * ponto — o provedor STT estoura por volta de 60s por requisição. */
  maxRajadaMs: number
}

export const LIMIARES_RAJADA_PADRAO: LimiaresRajada = {
  limiarSilencio: 0.01,
  silencioMs: 700,
  minRajadaMs: 1500,
  maxRajadaMs: 8000,
}

/**
 * Estado mínimo que a máquina carrega entre leituras: desde quando a
 * rajada atual começou, desde quando (se houver) o silêncio atual vem
 * durando sem interrupção, e se alguma leitura desta rajada já foi voz.
 * `silencioDesdeMs: null` significa "a leitura mais recente foi voz", não
 * "nunca houve silêncio nesta rajada".
 *
 * `houveVoz` existe apesar do pedido de "estado mínimo" do desenho
 * original porque, sem ele, uma rajada inteiramente silenciosa (o gestor
 * clica o mic e não chega a falar) fecha do mesmo jeito — e quem chama não
 * tinha como saber, antes de mandar pro Whisper, que não havia nada pra
 * transcrever. `MIN_BLOB_BYTES` não pega isso (o blob de ~2.2s de silêncio
 * codificado não é minúsculo) e "transcrição vazia" também não (medido: um
 * tom puro sem fala pode voltar HTTP 200 com texto alucinado, não string
 * vazia). Um campo é mais barato que uma chamada de API desperdiçada e um
 * texto inventado na caixa do gestor.
 */
export interface EstadoRajada {
  inicioMs: number
  silencioDesdeMs: number | null
  houveVoz: boolean
}

/** Estado de uma rajada nova, começando em `instanteMs`. */
export function criarEstadoRajada(instanteMs: number): EstadoRajada {
  return { inicioMs: instanteMs, silencioDesdeMs: null, houveVoz: false }
}

export interface AvaliacaoRajada {
  /** Sempre o próximo estado a usar na chamada seguinte — inclusive
   * quando `fecharRajada` é `true`: já vem reiniciado para a rajada
   * seguinte, para quem chama não precisar (e não poder esquecer de)
   * montar `criarEstadoRajada` de novo na mão. */
  estado: EstadoRajada
  fecharRajada: boolean
  /** Verdadeiro se alguma leitura desta rajada — incluindo a leitura
   * atual — teve RMS >= `limiarSilencio`. Espelha `estado.houveVoz` ANTES
   * do reset, então no instante do fechamento é o valor da rajada que
   * está fechando (não da próxima, já zerada). Ver o comentário em
   * `EstadoRajada.houveVoz` para o porquê deste campo existir. */
  houveVoz: boolean
}

/**
 * Uma leitura de RMS no instante `instanteMs`. Devolve a decisão ("fecha
 * agora" ou "continua") e o estado a usar na próxima chamada.
 *
 * Fechar por silêncio exige DUAS condições ao mesmo tempo: silêncio
 * sustentado por `silencioMs` **e** a rajada já ter vivido `minRajadaMs`
 * — sem a segunda, silêncio bem no início da rajada (o gestor demorou a
 * começar a falar) fecharia uma rajada vazia. Fechar por duração
 * (`maxRajadaMs`) não exige silêncio nenhum: é o piso de fala contínua
 * sem pausa.
 */
export function avaliarRajada(
  estado: EstadoRajada,
  rms: number,
  instanteMs: number,
  limiares: LimiaresRajada = LIMIARES_RAJADA_PADRAO,
): AvaliacaoRajada {
  const duracaoRajadaMs = instanteMs - estado.inicioMs
  const emSilencio = rms < limiares.limiarSilencio
  // Calculado uma vez e reusado nos três retornos: "houve voz" inclui a
  // leitura ATUAL, não só o histórico — uma leitura de voz que por acaso
  // coincide com o instante do fechamento por `maxRajadaMs` ainda conta.
  const houveVoz = estado.houveVoz || !emSilencio

  if (duracaoRajadaMs >= limiares.maxRajadaMs) {
    return { estado: criarEstadoRajada(instanteMs), fecharRajada: true, houveVoz }
  }

  if (!emSilencio) {
    // Voz (de novo ou ainda): zera o início do silêncio. É este reset que
    // faz uma vírgula (pausa curta) não se somar a uma pausa futura — sem
    // ele, duas pausas curtas separadas por fala poderiam ultrapassar
    // `silencioMs` juntas e fechar a rajada no meio de uma frase.
    return {
      estado: { ...estado, silencioDesdeMs: null, houveVoz },
      fecharRajada: false,
      houveVoz,
    }
  }

  const silencioDesdeMs = estado.silencioDesdeMs ?? instanteMs
  const duracaoSilencioMs = instanteMs - silencioDesdeMs
  const silencioSustentado = duracaoSilencioMs >= limiares.silencioMs
  const rajadaJaAtingiuOPiso = duracaoRajadaMs >= limiares.minRajadaMs

  if (silencioSustentado && rajadaJaAtingiuOPiso) {
    return { estado: criarEstadoRajada(instanteMs), fecharRajada: true, houveVoz }
  }

  return { estado: { ...estado, silencioDesdeMs, houveVoz }, fecharRajada: false, houveVoz }
}
