'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useGroqStatus } from '@/lib/hooks/useGroqStatus'
import toast from 'react-hot-toast'

interface MicButtonProps {
  onTranscribe: (text: string) => void
  disabled?: boolean
  className?: string
}

type State = 'idle' | 'recording' | 'uploading' | 'denied'

const MAX_DURATION_MS = 60_000
const MIN_BLOB_BYTES = 1024

export function MicButton({ onTranscribe, disabled, className }: MicButtonProps) {
  const { enabled } = useGroqStatus()
  const [state, setState] = useState<State>('idle')
  const [elapsed, setElapsed] = useState(0)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startedAtRef = useRef<number>(0)
  const tickerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pressedRef = useRef(false)
  const mimeRef = useRef<string>('audio/webm')

  const supported =
    typeof window !== 'undefined' &&
    typeof MediaRecorder !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia

  const cleanup = useCallback(() => {
    if (tickerRef.current) clearInterval(tickerRef.current)
    if (autoStopRef.current) clearTimeout(autoStopRef.current)
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    recorderRef.current = null
    chunksRef.current = []
    setElapsed(0)
  }, [])

  useEffect(() => () => cleanup(), [cleanup])

  const upload = useCallback(
    async (blob: Blob) => {
      setState('uploading')
      try {
        const form = new FormData()
        const ext = mimeRef.current.includes('mp4') ? 'mp4' : 'webm'
        form.append('audio', blob, `audio.${ext}`)
        const res = await fetch('/api/groq/transcribe', { method: 'POST', body: form })
        let json: any = null
        try { json = await res.json() } catch { /* sem json */ }
        if (!res.ok) throw new Error(json?.error || `HTTP ${res.status}`)
        if (typeof json?.text === 'string' && json.text.trim()) {
          onTranscribe(json.text.trim())
        } else {
          toast.error('Transcrição vazia')
        }
      } catch (e: any) {
        toast.error(`IA: ${e.message || 'indisponível'}`)
      } finally {
        setState('idle')
      }
    },
    [onTranscribe],
  )

  const startRecording = useCallback(async () => {
    if (state !== 'idle') return
    if (!supported) {
      toast.error('Gravação não suportada neste navegador')
      return
    }
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      toast.error('Sem internet — IA indisponível')
      return
    }
    pressedRef.current = true
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      if (!pressedRef.current) {
        stream.getTracks().forEach((t) => t.stop())
        streamRef.current = null
        return
      }
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/mp4'
      mimeRef.current = mime
      const rec = new MediaRecorder(stream, { mimeType: mime })
      recorderRef.current = rec
      chunksRef.current = []
      startedAtRef.current = Date.now()
      rec.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data)
      }
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mime })
        cleanup()
        if (blob.size < MIN_BLOB_BYTES) {
          toast.error('Gravação muito curta, segure mais tempo')
          setState('idle')
          return
        }
        void upload(blob)
      }
      rec.start()
      setState('recording')
      tickerRef.current = setInterval(() => {
        setElapsed(Date.now() - startedAtRef.current)
      }, 200)
      autoStopRef.current = setTimeout(() => {
        if (recorderRef.current?.state === 'recording') {
          recorderRef.current.stop()
        }
      }, MAX_DURATION_MS)
    } catch (e: any) {
      pressedRef.current = false
      cleanup()
      if (e?.name === 'NotAllowedError' || e?.name === 'SecurityError') {
        setState('denied')
        toast.error('Permita microfone nas configurações do navegador')
      } else {
        toast.error('Falha ao acessar microfone')
      }
    }
  }, [state, supported, upload, cleanup])

  const stopRecording = useCallback(() => {
    pressedRef.current = false
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
    }
  }, [])

  if (!enabled || !supported || state === 'denied') return null

  const isBusy = state === 'recording' || state === 'uploading'
  const seconds = Math.floor(elapsed / 1000)
  const mmss = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <div className={`inline-flex items-center gap-2 ${className ?? ''}`}>
      <Button
        type="button"
        size="sm"
        variant={state === 'recording' ? 'destructive' : 'outline'}
        disabled={disabled || state === 'uploading'}
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onMouseLeave={state === 'recording' ? stopRecording : undefined}
        onTouchStart={(e) => {
          e.preventDefault()
          startRecording()
        }}
        onTouchEnd={(e) => {
          e.preventDefault()
          stopRecording()
        }}
        className="select-none"
        aria-label="Segurar para gravar"
      >
        {state === 'uploading' ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : state === 'recording' ? (
          <MicOff className="h-4 w-4 animate-pulse" />
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </Button>
      {state === 'recording' && (
        <span className="text-xs font-mono text-red-500">● {mmss}</span>
      )}
      {state === 'uploading' && (
        <span className="text-xs text-muted-foreground">transcrevendo...</span>
      )}
      {state === 'idle' && !isBusy && (
        <span className="text-[10px] text-muted-foreground">segure para falar</span>
      )}
    </div>
  )
}
