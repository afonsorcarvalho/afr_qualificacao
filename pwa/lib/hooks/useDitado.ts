// lib/hooks/useDitado.ts
// Ditado por voz reusando a rota Whisper que já serve a coleta. O texto
// cai no campo de entrada e NÃO é enviado sozinho: o gestor revisa antes,
// porque transcrição errada de nome próprio é comum.
'use client'
import { useCallback, useRef, useState } from 'react'

export function useDitado(onTexto: (t: string) => void) {
  const [gravando, setGravando] = useState(false)
  const [transcrevendo, setTranscrevendo] = useState(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const pedacos = useRef<Blob[]>([])

  const parar = useCallback(() => {
    recorder.current?.stop()
    recorder.current = null
    setGravando(false)
  }, [])

  const alternar = useCallback(async () => {
    if (gravando) {
      parar()
      return
    }
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setGravando(false)
      return
    }
    pedacos.current = []
    const mr = new MediaRecorder(stream)
    recorder.current = mr
    mr.ondataavailable = (e) => {
      if (e.data && e.data.size) pedacos.current.push(e.data)
    }
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(pedacos.current, { type: 'audio/webm' })
      if (!blob.size) return
      setTranscrevendo(true)
      try {
        const form = new FormData()
        // Campo "audio": é o que a rota /api/groq/transcribe de fato lê
        // (ver app/api/groq/transcribe/route.ts e MicButton.tsx, que já
        // consome essa rota na coleta) — não "file".
        form.append('audio', blob, 'audio.webm')
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

  return { gravando, transcrevendo, alternar }
}
