'use client'
import { useState } from 'react'
import { Send } from 'lucide-react'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { useChatAgenda } from '@/lib/hooks/useChatAgenda'
import type { AgendaPayload } from '@/lib/odoo/agenda'

/** Contexto da visita alvo, para o gestor conferir antes de confirmar. */
function alvoDaProposta(payload: AgendaPayload, args: Record<string, unknown>) {
  const id = typeof args.visita_id === 'number' ? args.visita_id : null
  if (id === null) return null
  return payload.visitas.find((v) => v.id === id) ?? null
}

export function ChatAgenda({
  open,
  onClose,
  payload,
}: {
  open: boolean
  onClose: () => void
  payload: AgendaPayload | undefined
}) {
  const [texto, setTexto] = useState('')
  const { bolhas, proposta, ocupado, enviar, confirmar, cancelar } =
    useChatAgenda(payload)

  if (!payload?.can_manage) return null

  const alvo = proposta ? alvoDaProposta(payload, proposta.args) : null

  async function submeter(e: React.FormEvent) {
    e.preventDefault()
    const t = texto
    setTexto('')
    await enviar(t)
  }

  return (
    <BottomSheet open={open} title="Agendar por conversa" onClose={onClose}>
      <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pb-2">
        {bolhas.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Peça em português: “remarca a visita do João de quinta pra sexta”,
            “quem está livre dia 20?”.
          </p>
        )}
        {bolhas.map((b, i) => (
          <div
            key={i}
            className={
              b.autor === 'user'
                ? 'self-end rounded-lg bg-primary/10 px-3 py-2 text-sm'
                : b.autor === 'erro'
                  ? 'self-start rounded-lg bg-destructive/10 px-3 py-2 text-sm'
                  : 'self-start rounded-lg bg-muted px-3 py-2 text-sm'
            }
          >
            {b.texto}
          </div>
        ))}

        {proposta && (
          <div className="rounded-lg border border-primary/40 bg-primary/5 p-3">
            <p className="text-sm font-medium">{proposta.resumo}</p>
            {alvo && (
              <p className="mt-1 text-xs text-muted-foreground">
                {alvo.os_name} · {alvo.partner_name} · {alvo.city} · {alvo.date}
                {alvo.tecnico_name ? ` · ${alvo.tecnico_name}` : ''}
              </p>
            )}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="min-h-[44px] flex-1 rounded-md bg-primary px-3 text-primary-foreground disabled:opacity-50"
                disabled={ocupado}
                onClick={confirmar}
              >
                Confirmar
              </button>
              <button
                type="button"
                className="min-h-[44px] flex-1 rounded-md border border-border px-3"
                onClick={cancelar}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {ocupado && (
          <p className="text-xs text-muted-foreground">consultando a agenda…</p>
        )}
      </div>

      <form onSubmit={submeter} className="mt-3 flex gap-2">
        <input
          className="min-h-[44px] flex-1 rounded-md border border-border bg-background px-3"
          placeholder="Escreva o que precisa"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={ocupado}
        />
        <button
          type="submit"
          aria-label="Enviar"
          className="min-h-[44px] min-w-[44px] rounded-md bg-primary text-primary-foreground disabled:opacity-50"
          disabled={ocupado || !texto.trim()}
        >
          <Send className="mx-auto h-4 w-4" />
        </button>
      </form>
    </BottomSheet>
  )
}
