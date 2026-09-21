// lib/hooks/useChatAgenda.ts
'use client'
import { useCallback, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { LlmMessage, LlmTurn } from '@/lib/llm/client'
import type { AgendaPayload } from '@/lib/odoo/agenda'
import { runTurn, confirmarEscrita, coletarIds, type Proposta, type PassoResultado } from '@/lib/chat/machine'
import { runTool } from '@/lib/chat/tools'
import { buildSystemPrompt, resumirVisitas } from '@/lib/chat/prompt'

export interface Bolha {
  autor: 'user' | 'assistente' | 'erro'
  texto: string
}

const CHAVE_SESSAO = 'chat-agenda-transcript'

function lerSessao(): Bolha[] {
  try {
    const cru = sessionStorage.getItem(CHAVE_SESSAO)
    return cru ? (JSON.parse(cru) as Bolha[]) : []
  } catch {
    return []
  }
}

function gravarSessao(bolhas: Bolha[]): void {
  try {
    sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(bolhas))
  } catch {
    // Janela anônima ou storage bloqueado: a conversa só não persiste.
  }
}

async function chamarModelo(messages: LlmMessage[]) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  })
  if (!res.ok) {
    const j = await res.json().catch(() => ({}))
    throw new Error(j?.error || 'Falha ao falar com a IA')
  }
  return (await res.json()) as LlmTurn
}

export function useChatAgenda(payload: AgendaPayload | undefined) {
  const qc = useQueryClient()
  const [bolhas, setBolhas] = useState<Bolha[]>(() =>
    typeof window === 'undefined' ? [] : lerSessao(),
  )
  const [proposta, setProposta] = useState<Proposta | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const historico = useRef<LlmMessage[]>([])
  // O conjunto de ids vive pela conversa inteira, não por pedido: um id
  // visto na primeira pergunta continua válido na terceira.
  const idsVistos = useRef<Set<number>>(new Set())

  const systemPrompt = useMemo(() => {
    if (!payload) return ''
    coletarIds(payload.visitas, idsVistos.current)
    return buildSystemPrompt({
      serverToday: payload.server_today,
      // `Array.from`, não spread do Map: o tsconfig do projeto não define
      // `target`, e espalhar um iterador exige `es2015`+ ou
      // `downlevelIteration` (ver CLAUDE.md/constraints desta task).
      tecnicos: Array.from(
        new Map(
          payload.visitas
            .filter((v) => v.tecnico_id)
            .map((v) => [v.tecnico_id as number, { id: v.tecnico_id as number, name: v.tecnico_name }]),
        ).values(),
      ),
      visitas: resumirVisitas(payload.visitas),
    })
  }, [payload])

  const empilhar = useCallback((b: Bolha) => {
    setBolhas((antigas) => {
      const novas = [...antigas, b]
      gravarSessao(novas)
      return novas
    })
  }, [])

  const aplicar = useCallback((r: PassoResultado) => {
    historico.current = r.messages
    if (r.kind === 'text') {
      setProposta(null)
      if (r.text) empilhar({ autor: 'assistente', texto: r.text })
    } else if (r.kind === 'proposal') {
      setProposta(r.proposta)
    } else {
      setProposta(null)
      empilhar({ autor: 'erro', texto: r.erro })
    }
  }, [empilhar])

  const deps = useMemo(
    () => ({ callModel: chamarModelo, runTool, idsVistos: idsVistos.current }),
    [],
  )

  const enviar = useCallback(async (texto: string) => {
    if (!texto.trim() || ocupado || !payload) return
    empilhar({ autor: 'user', texto })
    setOcupado(true)
    const base: LlmMessage[] = historico.current.length
      ? historico.current
      : [{ role: 'system', content: systemPrompt }]
    try {
      aplicar(await runTurn([...base, { role: 'user', content: texto }], deps))
    } finally {
      setOcupado(false)
    }
  }, [ocupado, payload, empilhar, systemPrompt, aplicar, deps])

  const confirmar = useCallback(async () => {
    if (!proposta || ocupado) return
    setOcupado(true)
    // Some com o card antes de executar: sem isso, um duplo toque dispara
    // a escrita duas vezes.
    const alvo = proposta
    setProposta(null)
    try {
      aplicar(await confirmarEscrita(historico.current, alvo, deps))
      qc.invalidateQueries({ queryKey: ['agenda'] })
      qc.invalidateQueries({ queryKey: ['tecnico-os'] })
    } finally {
      setOcupado(false)
    }
  }, [proposta, ocupado, aplicar, deps, qc])

  const cancelar = useCallback(() => {
    setProposta(null)
    empilhar({ autor: 'erro', texto: 'Alteração cancelada.' })
  }, [empilhar])

  return { bolhas, proposta, ocupado, enviar, confirmar, cancelar }
}
