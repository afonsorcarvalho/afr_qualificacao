'use client'
import { useState } from 'react'
import { Sparkles, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useGroqStatus } from '@/lib/hooks/useGroqStatus'
import toast from 'react-hot-toast'
import type { SummaryRequestBody } from '@/app/api/groq/summary/route'

interface SummaryButtonProps {
  onGenerate: (summary: string) => void
  buildContext: () => SummaryRequestBody
  label?: string
  confirmOverwrite?: boolean
  disabled?: boolean
  className?: string
}

export function SummaryButton({
  onGenerate,
  buildContext,
  label = '✨ Gerar resumo',
  confirmOverwrite = false,
  disabled,
  className,
}: SummaryButtonProps) {
  const { enabled } = useGroqStatus()
  const [loading, setLoading] = useState(false)

  if (!enabled) return null

  const handleClick = async () => {
    if (confirmOverwrite) {
      const ok = typeof window !== 'undefined'
        ? window.confirm('Substituir texto atual?')
        : true
      if (!ok) return
    }
    setLoading(true)
    try {
      const ctx = buildContext()
      const res = await fetch('/api/groq/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ctx),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json?.error || 'Falha ao gerar resumo')
      if (typeof json.summary === 'string') {
        onGenerate(json.summary)
      } else {
        toast.error('Resumo vazio')
      }
    } catch (e: any) {
      toast.error(`IA: ${e.message || 'indisponível'}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      disabled={disabled || loading}
      onClick={handleClick}
      className={className}
    >
      {loading ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Gerando...
        </>
      ) : (
        <>
          <Sparkles className="mr-2 h-4 w-4" />
          {label}
        </>
      )}
    </Button>
  )
}
