// lib/hooks/useDitado.ts
// Ditado por voz reusando a rota Whisper que já serve a coleta. O texto
// cai no campo de entrada e NÃO é enviado sozinho: o gestor revisa antes,
// porque transcrição errada de nome próprio é comum.
'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { mensagemDoErro } from '@/lib/utils/erro'

// A OpenRouter documenta que os provedores upstream cortam por volta de
// 60s por requisição — uma gravação sem limite vira, mais cedo ou mais
// tarde, um pedido que o provedor recusa por tempo, não pelo conteúdo.
// Mesmo valor de `MAX_DURATION_MS` do `MicButton.tsx` (coleta), mas aqui
// o botão não mostra cronômetro na tela: sem avisar o gestor, a parada
// automática pareceria o botão mudando sozinho, do nada.
const MAX_DURATION_MS = 60_000

// Fato de uma tentativa específica: "fui descartada". Cada `alternar()`
// que começa uma gravação nova cria o seu próprio objeto — nunca
// compartilhado, nunca reaproveitado — e é só ESSE objeto que
// `pararEDescartar()` pode marcar. Ver o comentário em cima de
// `tentativaAtual` pra saber por que isto substitui um contador de
// geração.
type ControleDaTentativa = { descartado: boolean }

export function useDitado(onTexto: (t: string) => void) {
  const [gravando, setGravando] = useState(false)
  const [transcrevendo, setTranscrevendo] = useState(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
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
  // Tentativa que `pararEDescartar()` pode cancelar AGORA, se for
  // chamada. Cada `alternar()` que começa do zero cria seu próprio
  // `ControleDaTentativa` e aponta esta ref pra ele; `parar()` (o
  // gestor pedindo a transcrição de propósito) APAGA essa referência
  // antes de devolver o controle — a partir daí aquela tentativa está
  // fora do alcance de `pararEDescartar()`, comprometida a transcrever
  // não importa o que aconteça depois.
  //
  // Isto substitui um contador de geração (usado no round anterior): um
  // contador incremental confunde "existe uma tentativa mais nova" com
  // "esta tentativa foi cancelada" — são fatos DIFERENTES. Uma
  // gravação nova pode nascer sem que isso, por si só, signifique que
  // a anterior deveria ser jogada fora: se o gestor pediu
  // explicitamente pra parar e transcrever (`parar()`), e só DEPOIS
  // disso uma gravação nova começar antes do `onstop` (assíncrono,
  // pode atrasar por thread ocupada, pausa de GC, celular lento — não
  // é borda numa PWA) chegar, o contador achava (errado) que a
  // tentativa velha tinha sido "superada" e descartava um pedido de
  // transcrição legítimo, em silêncio. Um fato POR TENTATIVA
  // (`descartado`, só setado por um cancelamento explícito) não tem
  // essa ambiguidade: nascer uma tentativa nova nunca, por si só, marca
  // NENHUMA outra tentativa como descartada.
  const tentativaAtual = useRef<ControleDaTentativa | null>(null)

  const parar = useCallback(() => {
    // Pode ser o gestor tocando de novo OU o auto-stop de 60s chegando —
    // nos dois casos o limite deixa de valer pra esta tentativa (ela já
    // está parando), então desarma antes de qualquer outra coisa.
    if (autoStopRef.current) {
      clearTimeout(autoStopRef.current)
      autoStopRef.current = null
    }
    // O gestor pediu a transcrição (segundo toque no mic) — a partir
    // daqui esta tentativa está comprometida a transcrever, não importa
    // o que aconteça depois (uma gravação nova pode até começar antes
    // do `onstop` assíncrono chegar): tirar a referência de
    // `tentativaAtual` agora é o que garante que nenhum
    // `pararEDescartar()` futuro consiga alcançar ESTA tentativa.
    tentativaAtual.current = null
    recorder.current?.stop()
    recorder.current = null
    setGravando(false)
    // Liga `transcrevendo` JÁ, síncrono — não só quando o `onstop`
    // (assíncrono, pode demorar) finalmente rodar. Sem isto a tela
    // fica com cara de ociosa entre o toque de parar e a transcrição
    // realmente começar, e é essa janela "vazia" que convida o gestor
    // a tocar de novo achando que nada aconteceu (foi exatamente essa
    // falta de sinal que abriu espaço pra uma gravação nova nascer
    // achando que a anterior tinha sumido).
    setTranscrevendo(true)
  }, [])

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
    if (tentativaAtual.current) tentativaAtual.current.descartado = true
    recorder.current?.stop()
    recorder.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setGravando(false)
  }, [])

  const alternar = useCallback(async () => {
    if (gravando) {
      parar()
      return
    }
    if (iniciando.current) return
    iniciando.current = true
    const controle: ControleDaTentativa = { descartado: false }
    tentativaAtual.current = controle
    // Buffer PRÓPRIO desta tentativa — nunca compartilhado com nenhuma
    // outra, passada ou futura. Não existe "limpar no início" porque
    // não existe nada global pra limpar: cada `alternar()` que começa
    // do zero cria o seu, isolado por closure.
    const pedacos: Blob[] = []
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      iniciando.current = false
      setGravando(false)
      return
    }
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
    // Cascata igual à do MicButton.tsx (coleta): Safari/iOS não
    // produzem webm, então testar suporte é obrigatório, não só uma
    // preferência — sem isso o blob final fica com um tipo que o
    // gravador de fato não usou.
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/mp4'
    const mr = new MediaRecorder(stream, { mimeType })
    recorder.current = mr
    iniciando.current = false
    mr.ondataavailable = (e) => {
      if (e.data && e.data.size) pedacos.push(e.data)
    }
    mr.onstop = async () => {
      // Sempre libera as tracks desta tentativa, atrasada ou não — os
      // cinco caminhos de parada continuam liberando o microfone
      // incondicionalmente, independente do que vier a seguir.
      stream.getTracks().forEach((t) => t.stop())
      // Só limpa a ref se ela ainda apontar pro stream DESTA tentativa
      // — se este evento atrasou o bastante, uma tentativa mais nova
      // pode já ter posto o próprio stream em `streamRef.current`, e
      // não é este evento velho quem deveria apagar isso (senão o
      // desligamento síncrono de um `pararEDescartar()` futuro, que
      // depende de `streamRef.current` pra agir sem esperar o `onstop`
      // da tentativa nova, ficaria sem efeito nenhum).
      if (streamRef.current === stream) streamRef.current = null
      if (controle.descartado) {
        // `pararEDescartar()` cancelou ESTA tentativa especificamente
        // (fechar a folha, desmontar) — não importa se foi enquanto
        // gravava ou enquanto a permissão ainda estava pendente. Não
        // toca em nenhum buffer, não transcreve. Uma tentativa nova
        // ter nascido depois NÃO é, por si só, motivo pra descartar —
        // só a passagem por aqui com `descartado === true` é.
        return
      }
      const ext = mimeType.includes('mp4') ? 'mp4' : 'webm'
      const blob = new Blob(pedacos, { type: mimeType })
      if (!blob.size) {
        setTranscrevendo(false)
        return
      }
      try {
        const form = new FormData()
        // Campo "audio": é o que a rota /api/groq/transcribe de fato lê
        // (ver app/api/groq/transcribe/route.ts e MicButton.tsx, que já
        // consome essa rota na coleta) — não "file".
        form.append('audio', blob, `audio.${ext}`)
        const res = await fetch('/api/groq/transcribe', { method: 'POST', body: form })
        let json: { text?: string; error?: string } | null = null
        try { json = await res.json() } catch { /* sem json: proxy, 502, corpo vazio */ }
        if (!res.ok) throw new Error(json?.error || `HTTP ${res.status}`)
        // Um 200 com `text` vazio/ausente (silêncio na gravação, só ruído
        // de fundo, corpo sem o campo) é o MESMO sintoma relatado ("cliquei
        // no mic e não aconteceu nada") como um 503 seria — `res.ok` sendo
        // `true` não é garantia de que sobrou transcrição nenhuma pra
        // devolver. Mesmo texto do `MicButton.tsx:68`, pra os dois mics não
        // divergirem no que dizem pro gestor.
        if (typeof json?.text === 'string' && json.text.trim()) {
          onTexto(json.text.trim())
        } else {
          toast.error('Transcrição vazia')
        }
      } catch (e) {
        // Avisa, não trava: nem um 503 (sem chave configurada) nem uma
        // exceção de rede podem sumir sem passar por lugar nenhum — foi
        // exatamente esse silêncio que fez o defeito relatado ("o mic não
        // faz nada") passar despercebido em produção. O que o comentário
        // antigo ("Silencioso de propósito") protegia de verdade era só
        // "não travar o campo de texto" — o gestor continua podendo
        // digitar normalmente, um toast não tira essa saída.
        toast.error(`IA: ${mensagemDoErro(e, 'indisponível')}`)
      } finally {
        setTranscrevendo(false)
      }
    }
    mr.start()
    setGravando(true)
    // Auto-stop em MAX_DURATION_MS (ver comentário no topo do arquivo): o
    // gestor não pediu pra parar, então avisa por quê antes de chamar
    // `parar()` — sem isso o botão trocaria de "Parar gravação" pra
    // "Ditar" sozinho, do nada.
    autoStopRef.current = setTimeout(() => {
      autoStopRef.current = null
      toast('Gravação parada automaticamente após 60s')
      parar()
    }, MAX_DURATION_MS)
  }, [gravando, parar, onTexto])

  // Cleanup ao desmontar: sem isso, navegar pra outra tela (ou a troca
  // de instância do componente) com o mic ligado deixa o stream aberto
  // e a luz do microfone acesa sem NENHUM controle na tela pro gestor
  // desligar — o botão que gravava não existe mais.
  useEffect(() => {
    return () => {
      pararEDescartar()
    }
  }, [pararEDescartar])

  return { gravando, transcrevendo, alternar, pararEDescartar }
}
