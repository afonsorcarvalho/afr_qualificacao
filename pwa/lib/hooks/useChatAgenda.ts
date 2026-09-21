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
  // `useState` puro, sem `sessionStorage`: `ChatAgenda` fica montado o
  // tempo todo que `can_manage && enabled` (a folha só esconde via `open`
  // do `BottomSheet`), então fechar e reabrir já preserva a conversa sem
  // precisar de storage — e um F5 limpa tudo de uma vez, transcript E
  // memória do modelo juntos. Persistir só `bolhas` deixava as bolhas na
  // tela sobreviverem ao F5 enquanto `historico.current`/`idsVistos`
  // (que não persistem) voltavam a zero: um "remarca essa aí" depois de
  // recarregar a página batia num modelo sem contexto nenhum, apesar da
  // tela mostrar a pergunta anterior. Bônus: tira o risco de estourar a
  // cota do `sessionStorage` com resultado de ferramenta grande (até
  // 120000 caracteres, ver `MAX_CHARS_CONTEUDO_MAQUINA` em `app/api/chat`).
  const [bolhas, setBolhas] = useState<Bolha[]>([])
  const [proposta, setProposta] = useState<Proposta | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const historico = useRef<LlmMessage[]>([])
  // O conjunto de ids vive pela conversa inteira, não por pedido: um id
  // visto na primeira pergunta continua válido na terceira.
  const idsVistos = useRef<Set<number>>(new Set())

  const systemPrompt = useMemo(() => {
    if (!payload) return ''
    // `coletarIds` muta `idsVistos.current` (um `Set`) aqui dentro de um
    // `useMemo` — impuro de propósito, não descuido. É seguro porque
    // `Set.add` é idempotente: React pode rodar este corpo mais de uma vez
    // (StrictMode, remontagem) e o resultado do `Set` é o mesmo de qualquer
    // jeito, nunca duplica nem perde id. Não virou `useEffect` porque isso
    // atrasaria a disponibilidade dos ids para depois do primeiro render —
    // e `enviar()` pode disparar antes desse efeito rodar.
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
    setBolhas((antigas) => [...antigas, b])
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

  // Repara `historico.current` antes de descartar uma proposta pendente:
  // a mensagem "assistant" que a gerou tem um `tool_calls` esperando por
  // uma resposta "tool" com este `tool_call_id" — sem ela, o transcript
  // fica malformado e, como `historico` é append-only (só cresce via
  // `aplicar`), TODA mensagem seguinte reenvia o mesmo transcript quebrado
  // e falha do mesmo jeito. Mesma obrigação que `machine.ts:198-204` já
  // cumpre para as chamadas paralelas de uma mesma volta — aqui é a mesma
  // invariante, só que pelo lado do cancelamento do gestor em vez do lado
  // do loop do modelo. A mensagem de conteúdo também importa: sem ela, o
  // modelo nunca fica sabendo que o gestor disse não, e pode narrar a
  // mudança como feita no próximo turno.
  const descartarPropostaPendente = useCallback((motivo: string) => {
    if (!proposta) return
    historico.current = [
      ...historico.current,
      { role: 'tool', content: motivo, tool_call_id: proposta.toolCallId },
    ]
    setProposta(null)
  }, [proposta])

  const enviar = useCallback(async (texto: string) => {
    if (!texto.trim() || ocupado || !payload) return
    // O card de proposta não bloqueia o campo de texto (redirecionar no
    // meio de uma proposta é comportamento válido); mas mandar uma
    // mensagem nova sem resolver a proposta pendente deixaria o mesmo
    // `tool_calls` sem resposta que `cancelar` corrige — mesmo reparo,
    // outro gatilho.
    descartarPropostaPendente(
      'O gestor enviou uma nova mensagem antes de confirmar; esta alteração foi cancelada e nada foi executado.',
    )
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
  }, [ocupado, payload, descartarPropostaPendente, empilhar, systemPrompt, aplicar, deps])

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
    descartarPropostaPendente('O gestor cancelou esta alteração; nada foi executado.')
    empilhar({ autor: 'erro', texto: 'Alteração cancelada.' })
  }, [descartarPropostaPendente, empilhar])

  return { bolhas, proposta, ocupado, enviar, confirmar, cancelar }
}
