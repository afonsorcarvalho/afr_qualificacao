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
  const pedacos = useRef<Blob[]>([])
  // Início em andamento: sem isso, um segundo clique enquanto o
  // getUserMedia da primeira chamada ainda não resolveu reentra em
  // `alternar` (gravando ainda é `false` nesse closure), abre um
  // SEGUNDO stream de microfone e sobrescreve `recorder.current` — o
  // primeiro stream fica órfão, sem referência, com as tracks nunca
  // paradas. Mesma proteção que `MicButton.tsx` (`pressedRef`) usa.
  const iniciando = useRef(false)
  // Descartar: sinaliza que a gravação em andamento (ou a permissão
  // ainda pendente) deve ser interrompida SEM transcrever — o gestor
  // fechou a folha do chat ou saiu da tela, não pediu o texto. É
  // consumida em um de dois lugares: logo após o `await` do
  // `getUserMedia` (se a interrupção chegou enquanto a permissão ainda
  // estava pendente) ou dentro do `onstop` (se já havia um
  // MediaRecorder gravando).
  const descartarRef = useRef(false)

  const parar = useCallback(() => {
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
    // `descartarRef` significa "descarte o que está em voo agora". Sem
    // nada em voo (nenhum início pendente, nenhum gravador, nenhum
    // stream), não há o que descartar — e armar a flag mesmo assim é
    // exatamente o bug que vazou pro PRÓXIMO clique legítimo no mic: o
    // efeito de `_ChatAgenda.tsx` chama `pararEDescartar()` toda vez
    // que `open` é `false`, inclusive na montagem inicial (folha
    // fechada por padrão) e em qualquer fechamento com o chat ocioso.
    // Sem esta guarda, a flag ficava setada, sobrevivia até o gestor
    // finalmente tocar o mic, e o primeiro toque legítimo era
    // descartado em silêncio — `gravando` nunca virava `true`, sem
    // erro nenhum na tela.
    if (!iniciando.current && !recorder.current && !streamRef.current) return
    descartarRef.current = true
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
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      iniciando.current = false
      descartarRef.current = false
      setGravando(false)
      return
    }
    if (descartarRef.current) {
      // A folha fechou (ou o hook desmontou) enquanto a permissão
      // ainda estava pendente: descarta o stream recém-obtido sem
      // nunca criar o MediaRecorder nem marcar gravando=true — do
      // contrário o mic ficaria ligado atrás de uma tela invisível.
      descartarRef.current = false
      iniciando.current = false
      stream.getTracks().forEach((t) => t.stop())
      return
    }
    pedacos.current = []
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
      if (e.data && e.data.size) pedacos.current.push(e.data)
    }
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      if (descartarRef.current) {
        descartarRef.current = false
        return
      }
      const ext = mimeType.includes('mp4') ? 'mp4' : 'webm'
      const blob = new Blob(pedacos.current, { type: mimeType })
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
