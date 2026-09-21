'use client'
import { useEffect, useState } from 'react'
import { Send, Mic } from 'lucide-react'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { useChatAgenda } from '@/lib/hooks/useChatAgenda'
import { useDitado } from '@/lib/hooks/useDitado'
import type { AgendaPayload } from '@/lib/odoo/agenda'

/**
 * Contexto da visita alvo, para o gestor conferir antes de confirmar.
 *
 * `visita_id` pode chegar como string do modelo (mesma quirk que o guard de
 * `machine.ts` trata) — sem coagir aqui, o card perde a linha de
 * OS/cliente/cidade bem na mensagem em que ela mais importa: um id
 * alucinado do formato "999" em vez de 999.
 */
function alvoDaProposta(payload: AgendaPayload, args: Record<string, unknown>) {
  const bruto = args.visita_id
  if (typeof bruto !== 'number' && typeof bruto !== 'string') return null
  const id = Number(bruto)
  if (!Number.isInteger(id)) return null
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
  const ditado = useDitado((t) => setTexto((antes) => (antes ? `${antes} ${t}` : t)))

  // `ChatAgenda` nunca desmonta quando a folha fecha — é o `BottomSheet`
  // que se esconde por dentro (ver o achado da review). Sem isto, fechar
  // a folha com o mic ligado deixa a gravação correndo atrás de uma tela
  // invisível, sem nenhum controle visível pro gestor parar. `open` vira
  // `false` → descarta a gravação em andamento, nunca transcreve: o
  // gestor fechou o chat, não pediu o texto.
  useEffect(() => {
    if (!open) {
      ditado.pararEDescartar()
    }
  }, [open, ditado.pararEDescartar])

  if (!payload?.can_manage) return null

  const alvo = proposta ? alvoDaProposta(payload, proposta.args) : null

  async function submeter(e: React.FormEvent) {
    e.preventDefault()
    // Só limpar o campo se o envio for mesmo acontecer: `enviar` tem seu
    // próprio guard (texto vazio, ocupado, sem payload) e retorna cedo
    // sem mandar nada — limpar `texto` ANTES desse guard perde o que o
    // gestor escreveu, sem enviar e sem devolver o texto pra tela.
    if (ocupado || !texto.trim()) return
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
          type="button"
          aria-label={ditado.gravando ? 'Parar gravação' : 'Ditar'}
          onClick={ditado.alternar}
          disabled={ocupado || ditado.transcrevendo}
          className={`min-h-[44px] min-w-[44px] rounded-md border border-border ${
            ditado.gravando ? 'bg-destructive text-destructive-foreground' : ''
          }`}
        >
          <Mic className="mx-auto h-4 w-4" />
        </button>
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
