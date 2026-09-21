// lib/hooks/useDitado.ts
// Ditado por voz reusando a rota Whisper que já serve a coleta. O texto
// cai no campo de entrada e NÃO é enviado sozinho: o gestor revisa antes,
// porque transcrição errada de nome próprio é comum.
'use client'
import { useCallback, useEffect, useRef, useState } from 'react'

export function useDitado(onTexto: (t: string) => void) {
  const [gravando, setGravando] = useState(false)
  const [transcrevendo, setTranscrevendo] = useState(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  // Início em andamento: sem isso, um segundo clique enquanto o
  // getUserMedia da primeira chamada ainda não resolveu reentra em
  // `alternar` (gravando ainda é `false` nesse closure), abre um
  // SEGUNDO stream de microfone e sobrescreve `recorder.current` — o
  // primeiro stream fica órfão, sem referência, com as tracks nunca
  // paradas. Mesma proteção que `MicButton.tsx` (`pressedRef`) usa.
  const iniciando = useRef(false)
  // Geração: cada tentativa de gravação ganha um número, incrementado
  // no início de `alternar()` (quando começa do zero) e também em
  // `pararEDescartar()`. Cada tentativa captura o número vigente no
  // instante em que nasce e só age (criar o MediaRecorder, transcrever)
  // se esse número ainda for o atual quando o momento chega.
  //
  // Isto substitui o booleano único (`descartarRef`) que os rounds
  // anteriores usavam. Um booleano não distingue "isto é o que estou
  // descartando agora" de "isto é uma tentativa NOVA, sem nenhuma
  // relação com aquele descarte": `MediaRecorder.stop()` só ENFILEIRA
  // o evento `stop` — ele não é síncrono — e se a thread principal
  // estiver ocupada, ou houver uma pausa de GC (celular lento: comum
  // numa PWA, não é borda), esse evento pode chegar DEPOIS que uma
  // gravação nova já zerou a flag. A gravação antiga então segue
  // adiante achando que está liberada pra transcrever — só que o texto
  // que sai é da fala ERRADA, entregue como se fosse a atual. Um
  // contador por tentativa não tem essa ambiguidade: o evento atrasado
  // carrega consigo o número da geração a que pertence.
  const geracao = useRef(0)

  const parar = useCallback(() => {
    // Pára a gravação ATUAL a pedido do próprio gestor (segundo toque
    // no mic) — ele quer a transcrição, então a geração NÃO muda: o
    // `onstop` que vai rodar em seguida é exatamente quem deve
    // transcrever.
    recorder.current?.stop()
    recorder.current = null
    setGravando(false)
  }, [])

  // Pára AGORA e descarta — nunca transcreve. Chamada ao desmontar o
  // hook ou quando a folha do chat fecha com o mic ligado. Não espera
  // o evento assíncrono `stop` do MediaRecorder: solta as tracks do
  // stream na hora, para a luz do microfone apagar imediatamente,
  // mesmo que o `onstop` (que também tenta parar as tracks, de forma
  // idempotente) só rode depois.
  const pararEDescartar = useCallback(() => {
    // Sem nada em voo (nenhum início pendente, nenhum gravador, nenhum
    // stream), não há o que descartar — avançar a geração mesmo assim
    // não quebraria nada hoje (nada capturou o valor antigo), mas sair
    // cedo deixa a intenção explícita e evita um `setGravando(false)`
    // supérfluo: `gravando === true` só é possível com
    // `recorder.current` setado, então se ele é `null` aqui, `gravando`
    // já era `false`.
    if (!iniciando.current && !recorder.current && !streamRef.current) return
    geracao.current += 1
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
    geracao.current += 1
    const minhaGeracao = geracao.current
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
    if (minhaGeracao !== geracao.current) {
      // A folha fechou (ou o hook desmontou) enquanto a permissão
      // ainda estava pendente: descarta o stream recém-obtido sem
      // nunca criar o MediaRecorder nem marcar gravando=true — do
      // contrário o mic ficaria ligado atrás de uma tela invisível.
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
      // não é este evento velho quem deveria apagar isso.
      if (streamRef.current === stream) streamRef.current = null
      if (minhaGeracao !== geracao.current) {
        // Evento `stop` atrasado de uma tentativa já superada — uma
        // gravação nova já começou (ou esta foi descartada e nada
        // nasceu no lugar). Não toca nos buffers de ninguém, não
        // transcreve o áudio ERRADO.
        return
      }
      const ext = mimeType.includes('mp4') ? 'mp4' : 'webm'
      const blob = new Blob(pedacos, { type: mimeType })
      if (!blob.size) return
      setTranscrevendo(true)
      try {
        const form = new FormData()
        // Campo "audio": é o que a rota /api/groq/transcribe de fato lê
        // (ver app/api/groq/transcribe/route.ts e MicButton.tsx, que já
        // consome essa rota na coleta) — não "file".
        form.append('audio', blob, `audio.${ext}`)
        const res = await fetch('/api/groq/transcribe', { method: 'POST', body: form })
        if (res.ok) {
          const j = (await res.json()) as { text?: string }
          if (j.text) onTexto(j.text)
        }
      } catch {
        // Silencioso de propósito: o gestor ainda pode digitar.
      } finally {
        setTranscrevendo(false)
      }
    }
    mr.start()
    setGravando(true)
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
