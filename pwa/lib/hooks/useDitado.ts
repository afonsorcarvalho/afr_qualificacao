// lib/hooks/useDitado.ts
// Ditado por voz reusando a rota Whisper que já serve a coleta. O texto
// cai no campo de entrada e NÃO é enviado sozinho: o gestor revisa antes,
// porque transcrição errada de nome próprio é comum.
//
// GRAVAÇÃO EM RAJADAS (Task 2 de docs/superpowers/plans/2026-09-22-ditado-em
// -rajadas.md): um clique liga o mic, e o texto vai aparecendo em pedaços
// ENQUANTO o gestor continua falando — não só depois do segundo clique. A
// decisão de ONDE cortar cada pedaço (rajada) vive em `lib/audio/
// deteccaoSilencio.ts` (Task 1, já revisada): aqui só ligamos um
// `AnalyserNode` sobre o MESMO `MediaStream` do `MediaRecorder`, amostramos
// o RMS a cada ~50ms, e alimentamos a máquina de decisão de lá.
//
// O truque técnico: `MediaRecorder` com `timeslice` entrega pedaços onde só
// o PRIMEIRO tem o cabeçalho do contêiner — um pedaço isolado não é um
// arquivo válido, o provedor recusa. Por isso, em vez de usar `timeslice`,
// cada rajada é o seu PRÓPRIO `MediaRecorder`: quando a máquina de silêncio
// manda fechar, paramos o gravador atual (isso produz um arquivo completo e
// válido) e IMEDIATAMENTE começamos um gravador novo sobre o mesmo stream —
// o gestor não percebe a troca, pra ele a gravação é contínua até o
// segundo clique. Isso custa uns poucos ms de áudio a cada troca (o tempo
// entre `stop()` e o `start()` seguinte), e só é aceitável porque o corte
// cai DENTRO de um silêncio — a máquina de decisão só fecha rajada depois
// de silêncio sustentado (ou do teto de duração). Se o corte caísse no meio
// de uma palavra, as duas rajadas vizinhas saem degradadas; por isso a
// máquina de silêncio não lê o relógio, quem chama aqui passa o instante.
//
// ORDEM DAS RESPOSTAS NÃO É A ORDEM DE CHEGADA: a rajada 3 pode responder
// antes da 2 (a rede não garante nada sobre isso). Cada rajada que de fato
// sobe pro servidor ganha um NÚMERO sequencial no momento em que é fechada
// (não quando a resposta chega) — os números refletem a ordem real em que
// as rajadas aconteceram, porque só existe UM gravador ativo por vez, então
// o fechamento delas é sempre sequencial, mesmo que a resolução da
// transcrição não seja. `onTexto` só é chamado respeitando essa ordem: uma
// resposta que chega fora de ordem fica retida (`pendentes`) até a(s)
// anterior(es) também terem resolvido.
'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { mensagemDoErro, nomeDoErro } from '@/lib/utils/erro'
import { avaliarRajada, calcularRms, criarEstadoRajada, type EstadoRajada } from '@/lib/audio/deteccaoSilencio'

// A OpenRouter documenta que os provedores upstream cortam por volta de
// 60s por requisição — uma gravação sem limite vira, mais cedo ou mais
// tarde, um pedido que o provedor recusa por tempo, não pelo conteúdo.
// Mesmo valor de `MAX_DURATION_MS` do `MicButton.tsx` (coleta), mas aqui
// o botão não mostra cronômetro na tela: sem avisar o gestor, a parada
// automática pareceria o botão mudando sozinho, do nada. Continua sendo um
// teto de SESSÃO (clique a clique), não de rajada — uma rajada individual
// já tem o próprio teto, bem mais curto, em `deteccaoSilencio.ts`
// (`maxRajadaMs`).
const MAX_DURATION_MS = 60_000

// Mesmo piso do `MicButton.tsx:18`: um blob menor que isto não é fala, é
// ruído de abrir/fechar o gravador. Continua valendo POR RAJADA (uma rajada
// sub-piso é descartada, nunca sobe pro servidor) — o que mudou é o AVISO:
// com rajadas, a última costuma ser um resto de silêncio entre o fim da
// fala e o clique de parar, e um "Gravação muito curta" por rajada viraria
// ruído em toda sessão. O aviso agora só dispara se a SESSÃO inteira não
// entregou texto nenhum (ver `finalizarSessaoSeAcabou` mais abaixo).
const MIN_BLOB_BYTES = 1024

// Fato de uma SESSÃO específica (clique a clique — pode abranger várias
// rajadas): "fui descartada". Cada `alternar()` que começa uma sessão nova
// cria o seu próprio objeto — nunca compartilhado, nunca reaproveitado — e
// é só ESSE objeto que `pararEDescartar()` pode marcar. Todas as rajadas
// da mesma sessão fecham sobre o MESMO `controle`, porque "esta sessão foi
// descartada" é um fato da sessão inteira, não de uma rajada isolada.
//
// Isto substitui um contador de geração: um contador incremental confunde
// "existe uma sessão mais nova" com "esta sessão foi cancelada" — são
// fatos DIFERENTES. Ver o comentário em cima de `tentativaAtual` pra mais
// detalhe (a razão é a mesma de antes da Task 2, só que agora "tentativa"
// é a sessão inteira, não uma gravação única).
type ControleDaTentativa = { descartado: boolean }

export function useDitado(onTexto: (t: string) => void) {
  const [gravando, setGravando] = useState(false)
  const [transcrevendo, setTranscrevendo] = useState(false)
  // Nível de áudio (RMS) da amostra mais recente, 0 quando não está
  // gravando. Existe só pra alimentar uma UI futura (barra de gravação com
  // forma de onda animada) — um valor só, atualizado a cada amostra; não
  // guarda histórico nenhum, quem quiser desenhar uma forma de onda de
  // verdade guarda o próprio buffer do lado de quem consome.
  const [nivelAudio, setNivelAudio] = useState(0)
  const recorder = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  // Roda a cada ~50ms enquanto uma sessão está ativa: lê o `AnalyserNode` e
  // alimenta a máquina de decisão de `deteccaoSilencio.ts`.
  const amostraIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const estadoRajadaRef = useRef<EstadoRajada>(criarEstadoRajada(0))
  // Ponte entre o fechamento MANUAL de rajada (`parar()`, que vive fora do
  // closure da tentativa) e a função que sabe fechar a rajada atual e
  // decidir se reinicia (`fecharRajadaAtual`, definida DENTRO do closure de
  // `alternar()`, porque só lá existem `stream`/`mimeType`/`controle`).
  // Setada uma vez por sessão, dentro de `alternar()`.
  const fecharRajadaRef = useRef<((houveVoz: boolean, ultima: boolean) => void) | null>(null)
  // Agendado só enquanto uma gravação está de fato em andamento; qualquer
  // caminho que pára antes do limite (segundo toque no mic, folha
  // fechando) tem que desarmar — senão o timer dispara depois, sobre uma
  // tentativa que já não é mais "a gravação atual".
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Início em andamento: sem isso, um segundo clique enquanto o
  // getUserMedia da primeira chamada ainda não resolveu reentra em
  // `alternar` (gravando ainda é `false` nesse closure), abre um
  // SEGUNDO stream de microfone e sobrescreve `recorder.current` — o
  // primeiro stream fica órfão, sem referência, com as tracks nunca
  // paradas. Mesma proteção que `MicButton.tsx` (`pressedRef`) usa.
  const iniciando = useRef(false)
  // Tentativa (= sessão) que `pararEDescartar()` pode cancelar AGORA, se
  // for chamada. Cada `alternar()` que começa do zero cria seu próprio
  // `ControleDaTentativa` e aponta esta ref pra ele; `parar()` (o
  // gestor pedindo a transcrição de propósito) APAGA essa referência
  // antes de devolver o controle — a partir daí a sessão está fora do
  // alcance de `pararEDescartar()`, comprometida a transcrever a rajada
  // final não importa o que aconteça depois. Ver comentário no tipo
  // `ControleDaTentativa` acima pro porquê disto não ser um contador.
  const tentativaAtual = useRef<ControleDaTentativa | null>(null)
  // Dados de fechamento da rajada CORRENTE — preenchidos por
  // `fecharRajadaAtual` (dentro do closure de `alternar()`) no instante em
  // que ela decide fechar, e lidos pelo `onstop` daquele mesmo gravador.
  // Não dá pra saber o número (ou se a rajada vai subir) no momento em que
  // o gravador começa, só quando termina — por isso é preenchido tarde,
  // não na criação.
  const infoFechamentoRef = useRef<{ numero: number | null; ultima: boolean; contabilizada: boolean } | null>(null)

  // Fecha (idempotente) o AudioContext desta sessão, se houver. Chamado em
  // TODO caminho de parada — `parar()`, `pararEDescartar()` e o catch de
  // `alternar()` — senão cada ditado vaza um AudioContext. `close()` é
  // assíncrono e pode rejeitar se o contexto já estiver fechando; não há
  // nada a fazer com esse erro, mas ele não pode virar unhandled rejection.
  const fecharAudioContext = useCallback(() => {
    const ctx = audioContextRef.current
    audioContextRef.current = null
    analyserRef.current = null
    if (!ctx) return
    try {
      ctx.close()?.catch(() => {})
    } catch {
      // Já fechando/fechado — idempotente o bastante pra ignorar.
    }
  }, [])

  const parar = useCallback(() => {
    // Pode ser o gestor tocando de novo OU o auto-stop de 60s chegando —
    // nos dois casos o limite deixa de valer pra esta sessão (ela já
    // está parando), então desarma antes de qualquer outra coisa.
    if (autoStopRef.current) {
      clearTimeout(autoStopRef.current)
      autoStopRef.current = null
    }
    if (amostraIntervalRef.current) {
      clearInterval(amostraIntervalRef.current)
      amostraIntervalRef.current = null
    }
    fecharAudioContext()
    // O gestor pediu a transcrição (segundo toque no mic) — a partir
    // daqui esta sessão está comprometida a transcrever a rajada final,
    // não importa o que aconteça depois (uma sessão nova pode até
    // começar antes do `onstop` assíncrono chegar): tirar a referência de
    // `tentativaAtual` agora é o que garante que nenhum
    // `pararEDescartar()` futuro consiga alcançar ESTA sessão.
    tentativaAtual.current = null
    // Liga `transcrevendo` JÁ, síncrono, e ANTES de fechar a rajada final
    // — em cima de gravadores síncronos (dublês de teste, ou um provedor
    // rápido o bastante), fechar a rajada pode resolver a sessão inteira
    // dentro desta mesma chamada, e é ela quem desliga `transcrevendo` no
    // fim. Se ligássemos DEPOIS, apagaríamos esse desligamento por cima.
    setGravando(false)
    setTranscrevendo(true)
    setNivelAudio(0)
    // Fecha a rajada em andamento como a ÚLTIMA da sessão: sobe sempre
    // (ver comentário grande dentro de `fecharRajadaAtual` sobre a
    // assimetria da guarda de `houveVoz`), e não reinicia gravador nenhum
    // depois. Se por algum motivo a sessão não tinha rajada nenhuma em
    // andamento (não deveria acontecer com `gravando=true`), a ref é nula
    // e não há o que fazer.
    fecharRajadaRef.current?.(estadoRajadaRef.current.houveVoz, true)
  }, [fecharAudioContext])

  // Pára AGORA e descarta — nunca transcreve. Chamada ao desmontar o
  // hook ou quando a folha do chat fecha com o mic ligado. Não espera
  // o evento assíncrono `stop` do MediaRecorder: solta as tracks do
  // stream na hora, para a luz do microfone apagar imediatamente,
  // mesmo que o `onstop` (que também tenta parar as tracks, de forma
  // idempotente) só rode depois.
  const pararEDescartar = useCallback(() => {
    // Sem nada em voo (nenhum início pendente, nenhum gravador, nenhum
    // stream), não há o que descartar. O disjunto `streamRef.current`
    // aqui NÃO é preenchimento defensivo: depois de `parar()`,
    // `recorder.current` já é `null` mas `streamRef.current` ainda
    // aponta pro stream até o `onstop` correspondente rodar — é esse
    // disjunto que garante que um desmonte NESSA janela ainda desliga
    // o mic.
    if (!iniciando.current && !recorder.current && !streamRef.current) return
    if (autoStopRef.current) {
      clearTimeout(autoStopRef.current)
      autoStopRef.current = null
    }
    if (amostraIntervalRef.current) {
      clearInterval(amostraIntervalRef.current)
      amostraIntervalRef.current = null
    }
    fecharAudioContext()
    setNivelAudio(0)
    if (tentativaAtual.current) tentativaAtual.current.descartado = true
    try {
      recorder.current?.stop()
    } catch {
      // Mesmo hazard de `fecharRajadaAtual` (stream morto por fora vira
      // `InvalidStateError` em `stop()`) — aqui não tem rajada pra
      // "settle": esta é a rajada AINDA ativa que `pararEDescartar()`
      // interrompe direto, sem passar por `fecharRajadaAtual`, então
      // `infoFechamentoRef.current.contabilizada` continua `false` (ver
      // comentário no tipo `fechamento` lá em cima) — não há
      // `rajadasEmVoo`/`pendentes` pra ajustar. Só evita que a exceção
      // corte a limpeza síncrona logo abaixo (soltar as tracks,
      // `setGravando(false)`), que é o que de fato desliga o mic.
    }
    recorder.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setGravando(false)
  }, [fecharAudioContext])

  const alternar = useCallback(async () => {
    if (gravando) {
      parar()
      return
    }
    if (iniciando.current) return
    // Guarda de suporte, avaliada AQUI (não memoizada no corpo do hook):
    // igual à do `MicButton.tsx:37-40`, mas lida na hora do clique em vez
    // de uma vez só na montagem — um teste (ou um navegador real) que muda
    // `MediaRecorder`/`getUserMedia` depois de montar não pode ficar preso
    // a um valor capturado no primeiro render.
    const suportado =
      typeof MediaRecorder !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
    if (!suportado) {
      toast.error('Gravação não suportada neste navegador')
      return
    }
    // Sem internet não há pra onde mandar a transcrição depois — mesmo
    // pré-check do `MicButton.tsx:85-88`, antes de sequer pedir o mic.
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      toast.error('Sem internet — IA indisponível')
      return
    }
    iniciando.current = true
    const controle: ControleDaTentativa = { descartado: false }
    tentativaAtual.current = controle
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (controle.descartado) {
        // A folha fechou (ou o hook desmontou) enquanto a permissão
        // ainda estava pendente: descarta o stream recém-obtido sem
        // nunca criar o MediaRecorder nem marcar gravando=true — do
        // contrário o mic ficaria ligado atrás de uma tela invisível.
        // Enquanto a permissão está pendente, `iniciando` impede QUALQUER
        // outra tentativa de nascer (reentrância), então o único jeito de
        // `controle.descartado` virar `true` aqui é um
        // `pararEDescartar()` — nunca uma tentativa nova.
        iniciando.current = false
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      streamRef.current = stream
      // Cascata igual à do MicButton.tsx (coleta): Safari/iOS não produzem
      // webm, então testar suporte é obrigatório, não só uma preferência —
      // sem isso o blob final fica com um tipo que o gravador de fato não
      // usou. Igual ao achado do review: isto agora mora DENTRO do try,
      // junto com `new MediaRecorder(...)` logo abaixo — antes ficavam fora
      // de qualquer captura, e uma exceção ali (mimeType não suportado, sem
      // MediaRecorder de verdade) virava unhandled rejection de um onClick,
      // com o stream já em `streamRef.current` e a luz do mic acesa sem
      // nenhum controle na tela pra apagar.
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/mp4'

      // Web Audio: OUTRO consumidor do MESMO stream, só pra observar o
      // nível — não interfere no que o MediaRecorder grava. Criado uma
      // única vez por SESSÃO (não por rajada): as rajadas trocam de
      // MediaRecorder, mas o AnalyserNode continua o mesmo, olhando pro
      // stream inteiro.
      type JanelaComAudioContext = Window & { webkitAudioContext?: typeof AudioContext }
      const AudioContextCtor =
        typeof window !== 'undefined'
          ? window.AudioContext ?? (window as JanelaComAudioContext).webkitAudioContext
          : undefined
      if (!AudioContextCtor) throw new Error('AudioContext indisponível neste navegador')
      const audioCtx = new AudioContextCtor()
      // Atribuído já aqui (antes de qualquer outro passo que possa
      // lançar) pra garantir que o catch mais abaixo encontre e feche
      // este contexto mesmo que a configuração do analyser falhe.
      audioContextRef.current = audioCtx
      // Safari/iOS constrói o AudioContext FORA do gesto de usuário
      // original (já estamos depois do `await getUserMedia` acima) — ele
      // nasce `suspended`. Um contexto suspenso devolve zeros em
      // `getFloatTimeDomainData`, então o RMS fica travado em 0, nenhuma
      // rajada nunca detecta voz, nada sobe no meio da sessão, e o medidor
      // fica preso no piso — sem nenhum erro na tela, a feature só parece
      // ter voltado ao comportamento de antes da Task 2.
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume()
        if (controle.descartado) {
          // Mesma janela do `controle.descartado` logo após o
          // `getUserMedia` acima: a folha pode ter fechado (ou o hook
          // desmontado) enquanto o `resume()` estava em voo.
          // `pararEDescartar()` já deve ter rodado — ela encontra
          // `iniciando.current` ainda `true` (só `iniciarNovaRajada`,
          // mais abaixo, o zera) e já desliga stream/contexto sozinha;
          // só falta esta função também limpar `iniciando` (ela não mexe
          // nisso) e sair sem criar o MediaRecorder.
          iniciando.current = false
          return
        }
      }
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      source.connect(analyser)
      analyserRef.current = analyser
      const amostras = new Float32Array(analyser.fftSize)

      // --- Estado da SESSÃO (todas as rajadas deste `alternar()` até o
      // próximo `parar()`/`pararEDescartar()`) ---
      // Número da PRÓXIMA rajada a enviar pro servidor — só é incrementado
      // quando uma rajada de fato vai subir (rajadas sem voz não ganham
      // número, nunca sobem). Como só existe um gravador ativo por vez, o
      // fechamento das rajadas é sempre sequencial — atribuir o número no
      // momento do FECHAMENTO (não no momento em que a resposta chega)
      // garante a ordem certa mesmo que as respostas voltem trocadas.
      let proximoNumeroParaEnviar = 1
      // Número da PRÓXIMA rajada a entregar pro `onTexto`, em ordem.
      let proximoNumeroParaEntregar = 1
      // Respostas que já chegaram mas ainda não são a vez de entregar
      // (`null` = rajada resolvida sem texto — sub-piso, transcrição
      // vazia ou falha — ainda assim precisa ocupar a posição, senão o
      // número seguinte fica bloqueado esperando pra sempre).
      const pendentes = new Map<number, string | null>()
      // Quantas rajadas estão em voo (gravador já parado, upload ainda não
      // resolveu). `parar()` só pode desligar `transcrevendo` quando isto
      // chegar a zero E a sessão já tiver sido encerrada.
      let rajadasEmVoo = 0
      // Vira `true` só dentro de `fecharRajadaAtual(..., true)` — a partir
      // daí nenhuma rajada nova nasce mais nesta sessão.
      let sessaoEncerrando = false
      // Requisito B (falha de rede/HTTP) e "transcrição vazia" dividem o
      // mesmo balde de "avisa só uma vez por sessão" — sem isso, uma
      // instabilidade de rede vira um toast por rajada. Cada causa mantém
      // a PRÓPRIA mensagem; só a primeira que acontecer é mostrada.
      let avisoFalhaMostrado = false
      // Se NENHUMA rajada da sessão entregou texto (todas descartadas por
      // silêncio, sub-piso, ou falharam), avisa "Gravação muito curta" —
      // mas só se nenhum outro aviso já explicou o motivo.
      let textoEntregue = false
      // Fato de SESSÃO, não de rajada: alguma rajada respondeu 200 mas sem
      // texto nenhum (silêncio real captado, só ruído de fundo). Não
      // dispara aviso NA HORA — por rajada, isso interrompe uma sessão que
      // no fim das contas funciona (rajada 1 vazia, rajada 2 com a fala de
      // verdade), e ainda rouba a vez do "Gravação muito curta" no fim de
      // uma sessão que nunca produziu nada (`avisoFalhaMostrado` já
      // travado por um toast que não era bem o motivo). Só decide a
      // mensagem quando a sessão inteira termina, em
      // `finalizarSessaoSeAcabou`.
      let algumaTranscricaoVazia = false
      estadoRajadaRef.current = criarEstadoRajada(Date.now())

      const avisarFalhaUmaVez = (mensagem: string) => {
        if (avisoFalhaMostrado) return
        avisoFalhaMostrado = true
        toast.error(mensagem)
      }

      // Entrega pro `onTexto`, EM ORDEM, tudo que já pode ser entregue —
      // ou seja, avança enquanto a próxima posição esperada já tiver
      // resposta (mesmo que seja um `null`, que só é pulado).
      const entregarEmOrdem = () => {
        // Guarda no PRÓPRIO ponto de dreno, não só antes de um
        // `pendentes.set` isolado: QUALQUER rajada desta sessão pode ser a
        // que chama `entregarEmOrdem()` no seu `finally` (a ordem de
        // chegada das respostas não é a ordem das rajadas — ver comentário
        // grande no topo do arquivo), então uma checagem antes de um único
        // `set` não impede as OUTRAS rajadas de drenar o mapa depois que
        // a sessão já foi descartada (✕, folha fechando, unmount). Sem
        // isto, o texto ainda aparecia um segundo depois do descarte — e,
        // pior, uma sessão NOVA já podia ter nascido por cima, herdando o
        // texto da sessão velha no campo errado.
        if (controle.descartado) {
          pendentes.clear()
          return
        }
        while (pendentes.has(proximoNumeroParaEntregar)) {
          const texto = pendentes.get(proximoNumeroParaEntregar) ?? null
          pendentes.delete(proximoNumeroParaEntregar)
          proximoNumeroParaEntregar += 1
          if (texto) {
            textoEntregue = true
            onTexto(texto)
          }
        }
      }

      // Chamado no `finally` de TODA rajada que passou por `onstop`. Só
      // finaliza a sessão (desliga `transcrevendo` e decide o aviso de
      // "sessão sem texto") quando `parar()` já foi chamado E não sobra
      // nenhuma rajada em voo.
      const finalizarSessaoSeAcabou = () => {
        if (!sessaoEncerrando || rajadasEmVoo > 0) return
        setTranscrevendo(false)
        if (!textoEntregue && !avisoFalhaMostrado) {
          // "Transcrição vazia" só se pelo menos uma rajada chegou a
          // responder 200 sem texto — senão (nenhuma rajada nem chegou a
          // subir: tudo ficou preso em silêncio/sub-piso) o motivo certo
          // continua sendo "Gravação muito curta".
          toast.error(algumaTranscricaoVazia ? 'Transcrição vazia' : 'Gravação muito curta, segure mais tempo')
        }
      }

      // Guarda os dados de UMA rajada — criado de novo a cada chamada de
      // `iniciarNovaRajada`, nunca reaproveitado entre rajadas (mesma
      // razão do antigo comentário sobre `pedacos`, agora por rajada em
      // vez de por sessão inteira).
      const iniciarNovaRajada = () => {
        const pedacos: Blob[] = []
        // Preenchido por `fecharRajadaAtual` no instante em que ESTA
        // rajada é fechada — não dá pra saber o número (ou se ela vai
        // subir) no momento em que o gravador começa, só quando termina.
        // `contabilizada` distingue duas causas BEM diferentes de
        // `numero === null` no `onstop`: uma rajada que o DETECTOR fechou
        // sem voz nenhuma (passou por `fecharRajadaAtual`, incrementou
        // `rajadasEmVoo`, só não ganhou número) de uma rajada que nunca
        // chegou a ser fechada por `fecharRajadaAtual` — porque
        // `pararEDescartar()` parou o gravador DIRETAMENTE (sem passar por
        // `fecharRajadaAtual`, que é só o caminho de fechamento NORMAL).
        // Sem esta flag, o `finally` do `onstop` decrementaria
        // `rajadasEmVoo` sem ele nunca ter sido incrementado pra esta
        // rajada — inofensivo hoje (`finalizarSessaoSeAcabou` também exige
        // `sessaoEncerrando`, que um descarte puro nunca liga), mas é uma
        // contagem errada esperando um bug futuro.
        const fechamento: { numero: number | null; ultima: boolean; contabilizada: boolean } = {
          numero: null,
          ultima: false,
          contabilizada: false,
        }
        infoFechamentoRef.current = fechamento

        const mr = new MediaRecorder(stream, { mimeType })
        recorder.current = mr
        iniciando.current = false
        mr.ondataavailable = (e) => {
          if (e.data && e.data.size) pedacos.push(e.data)
        }
        mr.onstop = async () => {
          // Sempre libera as tracks do stream quando esta é a ÚLTIMA
          // rajada da sessão — as rajadas do MEIO da sessão NÃO podem
          // parar as tracks (o stream precisa continuar vivo pra rajada
          // seguinte gravar em cima dele). "Sempre libera, atrasada ou
          // não" continua valendo, só que agora "sempre" é por SESSÃO,
          // não por rajada.
          if (fechamento.ultima) {
            stream.getTracks().forEach((t) => t.stop())
            if (streamRef.current === stream) streamRef.current = null
          }
          const numero = fechamento.numero
          try {
            if (controle.descartado) return
            if (numero === null) return // sem voz nesta rajada — nunca sobe
            const ext = mimeType.includes('mp4') ? 'mp4' : 'webm'
            const blob = new Blob(pedacos, { type: mimeType })
            // Piso por RAJADA (ver MIN_BLOB_BYTES no topo do arquivo): o
            // AVISO virou coisa de sessão, mas o descarte continua aqui,
            // silencioso — evita gastar uma chamada de API com ruído.
            if (blob.size < MIN_BLOB_BYTES) {
              pendentes.set(numero, null)
              return
            }
            const form = new FormData()
            // Campo "audio": é o que a rota /api/groq/transcribe de fato lê
            // (ver app/api/groq/transcribe/route.ts e MicButton.tsx, que já
            // consome essa rota na coleta) — não "file".
            form.append('audio', blob, `audio.${ext}`)
            // Sem isto, um fetch que trava (rede instável em campo, proxy
            // que nunca fecha a conexão) prende esta rajada PRA SEMPRE — e
            // como a entrega é estritamente sequencial (`entregarEmOrdem`,
            // ver comentário no topo do arquivo), toda rajada seguinte
            // fica represada atrás dela, com `rajadasEmVoo` nunca voltando
            // a zero e `transcrevendo` travado em `true`. 30s é generoso
            // (bem acima do tempo normal de uma rajada curta) mas ainda
            // finito.
            const abortCtrl = new AbortController()
            const timeoutId = setTimeout(() => abortCtrl.abort(), 30_000)
            let res: Response
            try {
              res = await fetch('/api/groq/transcribe', {
                method: 'POST',
                body: form,
                signal: abortCtrl.signal,
              })
            } finally {
              clearTimeout(timeoutId)
            }
            let json: { text?: string; error?: string } | null = null
            try {
              json = await res.json()
            } catch {
              /* sem json: proxy, 502, corpo vazio */
            }
            if (!res.ok) throw new Error(json?.error || `HTTP ${res.status}`)
            // Um 200 com `text` vazio/ausente (silêncio na gravação, só ruído
            // de fundo, corpo sem o campo) é o MESMO sintoma relatado ("cliquei
            // no mic e não aconteceu nada") como um 503 seria — `res.ok` sendo
            // `true` não é garantia de que sobrou transcrição nenhuma pra
            // devolver. Mesmo texto do `MicButton.tsx:68`, pra os dois mics não
            // divergirem no que dizem pro gestor.
            if (typeof json?.text === 'string' && json.text.trim()) {
              pendentes.set(numero, json.text.trim())
            } else {
              // Não avisa aqui (ver `algumaTranscricaoVazia` lá em cima) —
              // por rajada, isso interrompia uma sessão que no fim das
              // contas funciona.
              pendentes.set(numero, null)
              algumaTranscricaoVazia = true
            }
          } catch (e) {
            // Avisa (uma vez por sessão — ver `avisarFalhaUmaVez`), não
            // trava: nem um 503 (sem chave configurada) nem uma exceção de
            // rede podem sumir sem passar por lugar nenhum. Diferente de
            // antes da Task 2, uma rajada falhando NÃO derruba a sessão —
            // as próximas continuam normalmente.
            if (numero !== null) pendentes.set(numero, null)
            // `mensagemDoErro` devolveria o texto em inglês do
            // `DOMException` de abort ("The operation was aborted") — foge
            // da convenção pt-BR do resto da UI, então o timeout (item 6)
            // ganha mensagem própria.
            const mensagem =
              nomeDoErro(e) === 'AbortError' ? 'demorou demais, tente de novo' : mensagemDoErro(e, 'indisponível')
            avisarFalhaUmaVez(`IA: ${mensagem}`)
          } finally {
            // Só mexe na contabilidade da sessão (`rajadasEmVoo`) se esta
            // rajada foi de fato CONTADA por `fecharRajadaAtual` — uma
            // rajada que `pararEDescartar()` parou diretamente (sem passar
            // por lá, ver comentário em `fechamento` acima) nunca chegou a
            // incrementar `rajadasEmVoo`, e decrementar aqui destrambelharia
            // a contagem sem nenhum incremento correspondente.
            if (fechamento.contabilizada) {
              // `entregarEmOrdem()` chama `onTexto` (callback de quem
              // consome o hook) — se ELE lançar, o decremento de
              // `rajadasEmVoo`/`finalizarSessaoSeAcabou()` não pode ficar
              // pra trás: sem este `try/finally` aninhado, uma exceção do
              // consumidor deixava `rajadasEmVoo` positivo pra sempre,
              // `transcrevendo` travado em `true`, e o mic sem nenhum
              // controle na tela pra religar — a MESMA classe de falha que
              // já custou uma rodada de review nesta feature.
              try {
                entregarEmOrdem()
              } finally {
                rajadasEmVoo -= 1
                finalizarSessaoSeAcabou()
              }
            }
          }
        }
        mr.start()
      }

      // Fecha a rajada atual e, se não for a última, já começa a próxima —
      // "imediatamente", sem esperar o `onstop` (assíncrono) do gravador
      // que está parando: só assim o gestor não percebe a troca.
      const fecharRajadaAtual = (houveVoz: boolean, ultima: boolean) => {
        const fechamento = infoFechamentoRef.current
        if (fechamento) {
          fechamento.ultima = ultima
          // A guarda de `houveVoz` (ver `EstadoRajada.houveVoz` em
          // `deteccaoSilencio.ts`) vale pra QUALQUER rajada, inclusive a
          // FINAL — é o hazard de alucinação do Whisper que a Task 1 mediu
          // (tom puro sem fala voltando `" E aí"`/`" ."` com HTTP 200, não
          // corpo vazio). Round 1 de review desta task tinha essa guarda
          // pulando a rajada final (clique manual, ou teto de sessão) sob a
          // hipótese de que o gestor podia clicar parar dentro da janela de
          // amostragem antes de qualquer leitura pegar a fala — refeitas as
          // contas, isso não se sustenta: pra perder algo real, a fala
          // teria que começar inteira nesse intervalo (~50ms), e ~40ms de
          // áudio não é um trecho transcrevível. O CUSTO da exceção era
          // rotineiro (a última rajada de toda sessão normal é só o rabo de
          // silêncio entre o fim da fala e o clique de parar — o detector
          // fecha a penúltima rajada ~700ms DEPOIS que a fala parou, então a
          // final quase sempre nasce já em silêncio) — subia lixo em
          // praticamente toda sessão bem-sucedida.
          //
          // A rajada final AINDA tem uma saída, mas só quando faz falta de
          // verdade: se NENHUMA rajada desta sessão foi enviada ainda, a
          // última chance é deixá-la subir mesmo sem leitura de voz —
          // melhor arriscar uma transcrição ruim do que garantir "Gravação
          // muito curta" numa sessão onde o gestor efetivamente falou, só
          // que a fala caiu inteira nesta rajada e a leitura de RMS ainda
          // não tinha pego (o mesmo caso raro do parágrafo acima, agora sem
          // custo pras sessões normais — só se aplica quando não sobrou
          // texto nenhum).
          //
          // `nadaEnviadoAinda` (não `!textoEntregue`): o carve-out original
          // perguntava "o texto já foi ENTREGUE" — mas entrega depende da
          // RESPOSTA da rede chegar, e numa conexão de campo lenta o
          // gestor pode tocar ✓ antes de qualquer rajada ter respondido,
          // mesmo já tendo enviado uma de verdade. Nesse caso o carve-out
          // antigo liberava a rajada final silenciosa mesmo assim — a
          // alucinação do Whisper chegava depois, em cima do texto real
          // que só ainda não tinha voltado. `proximoNumeroParaEnviar` no
          // valor inicial (1) é o fato que não depende de timing: "esta
          // sessão nunca chegou a enviar rajada nenhuma".
          const nadaEnviadoAinda = proximoNumeroParaEnviar === 1
          fechamento.numero =
            (ultima ? houveVoz || nadaEnviadoAinda : houveVoz) ? proximoNumeroParaEnviar++ : null
          fechamento.contabilizada = true
          rajadasEmVoo += 1
        }
        if (ultima) sessaoEncerrando = true
        try {
          recorder.current?.stop()
        } catch {
          // `stop()` pressupõe um gravador `recording`/`paused` — se o
          // stream morreu sozinho por fora (chamada entrando, Bluetooth
          // caindo, iOS pausando o app em segundo plano), o gravador já
          // está `inactive` e `stop()` lança `InvalidStateError`. Sem este
          // catch, a exceção escapava (do clique em ✓, ou do próprio
          // detector de silêncio dentro do `setInterval`), NENHUM `onstop`
          // chega pra fechar esta rajada, e a sessão trava pra sempre:
          // `transcrevendo` nunca volta a `false`, o mic fica morto até
          // recarregar a página. `onstop` nunca vai rodar pra esta
          // rajada — este catch faz na mão o que o `finally` dele faria
          // (mesmo formato do catch de rede do `onstop`, mais abaixo):
          // fecha a rajada como falha e segue a contabilidade da sessão
          // adiante, sem engolir o problema em silêncio.
          if (fechamento) {
            if (fechamento.numero !== null) pendentes.set(fechamento.numero, null)
            try {
              entregarEmOrdem()
            } finally {
              rajadasEmVoo -= 1
              finalizarSessaoSeAcabou()
            }
          }
          // `onstop` também é quem soltaria as tracks quando esta é a
          // ÚLTIMA rajada da sessão (ver dentro de `iniciarNovaRajada`) —
          // como ele nunca vai rodar aqui, este é o único lugar que ainda
          // pode soltá-las. Sem isto, o mic continuaria "ligado" (track
          // viva) apesar da sessão já ter travado.
          if (ultima) {
            stream.getTracks().forEach((t) => t.stop())
            if (streamRef.current === stream) streamRef.current = null
          }
        }
        recorder.current = null
        // Fora do try/catch de propósito: se o stream já morreu, um NOVO
        // `MediaRecorder` sobre ele também lança — e é exatamente esse
        // throw que o `catch` do `setInterval` (mais abaixo) já existe pra
        // pegar, encerrando a sessão pelo caminho de descarte. Engolir a
        // exceção aqui apagaria essa recuperação.
        if (!ultima) iniciarNovaRajada()
      }

      fecharRajadaRef.current = fecharRajadaAtual

      iniciarNovaRajada() // primeira rajada da sessão
      setGravando(true)

      amostraIntervalRef.current = setInterval(() => {
        try {
          const analyser = analyserRef.current
          if (!analyser) return
          analyser.getFloatTimeDomainData(amostras)
          const rms = calcularRms(amostras)
          setNivelAudio(rms)
          const avaliacao = avaliarRajada(estadoRajadaRef.current, rms, Date.now())
          estadoRajadaRef.current = avaliacao.estado
          if (avaliacao.fecharRajada) {
            fecharRajadaAtual(avaliacao.houveVoz, false)
          }
        } catch {
          // Reinício de rajada falhou no meio da sessão (ex.: stream
          // encerrado por fora, mic desconectado) — não pode deixar a
          // exceção morrer silenciosa dentro de um `setInterval`. Encerra
          // a sessão pelo mesmo caminho de descarte, com o mesmo aviso de
          // falha de microfone usado no início.
          toast.error('Falha ao acessar microfone')
          pararEDescartar()
        }
      }, 50)

      // Auto-stop em MAX_DURATION_MS (ver comentário no topo do arquivo): o
      // gestor não pediu pra parar, então avisa por quê antes de chamar
      // `parar()` — sem isso o botão trocaria de "Parar gravação" pra
      // "Ditar" sozinho, do nada. Continua sendo teto de SESSÃO, não de
      // rajada.
      autoStopRef.current = setTimeout(() => {
        autoStopRef.current = null
        toast('Gravação parada automaticamente após 60s')
        parar()
      }, MAX_DURATION_MS)
    } catch (e) {
      // Cobre TUDO que pode falhar desde o pedido de permissão até o
      // gravador começar de fato: getUserMedia negado/indisponível, a
      // escolha de mimeType, a configuração do Web Audio, e
      // `new MediaRecorder(...)`. Achado do review final (pré-Task 2): as
      // últimas ficavam FORA do try antigo — uma exceção ali virava
      // unhandled rejection de um onClick, e como o stream já podia
      // estar em `streamRef.current`, a luz do microfone ficava acesa sem
      // nenhum controle na tela pra apagar. Nenhuma ref pode sobreviver a
      // este catch: é o que garante que `pararEDescartar()` (unmount, folha
      // fechando) encontra "nada em voo" depois de uma falha aqui.
      iniciando.current = false
      if (amostraIntervalRef.current) {
        clearInterval(amostraIntervalRef.current)
        amostraIntervalRef.current = null
      }
      fecharAudioContext()
      recorder.current?.stop()
      recorder.current = null
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      setGravando(false)
      setNivelAudio(0)
      // Mesma distinção do MicButton.tsx:134-140, mesmas frases — os dois
      // mics não podem divergir no que dizem pro gestor. `NotAllowedError`/
      // `SecurityError` são os nomes que getUserMedia usa pra "permissão
      // negada"; qualquer outro nome (ou nenhum, como a construção do
      // MediaRecorder que não é um DOMException) cai no genérico.
      const nome = nomeDoErro(e)
      if (nome === 'NotAllowedError' || nome === 'SecurityError') {
        toast.error('Permita microfone nas configurações do navegador')
      } else {
        toast.error('Falha ao acessar microfone')
      }
    }
  }, [gravando, parar, onTexto, fecharAudioContext, pararEDescartar])

  // Cleanup ao desmontar: sem isso, navegar pra outra tela (ou a troca
  // de instância do componente) com o mic ligado deixa o stream aberto
  // e a luz do microfone acesa sem NENHUM controle na tela pro gestor
  // desligar — o botão que gravava não existe mais.
  useEffect(() => {
    return () => {
      pararEDescartar()
    }
  }, [pararEDescartar])

  return { gravando, transcrevendo, alternar, pararEDescartar, nivelAudio }
}
