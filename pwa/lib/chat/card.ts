// lib/chat/card.ts
// Traduz uma proposta de escrita (args crus do modelo) para um card que o
// gestor confere sem precisar saber o que é um id de visita.
//
// `resumir()` em `machine.ts` continua existindo separado — aquele texto
// vai PRO MODELO (a próxima volta do loop lê o resumo de volta como
// contexto), este arquivo é só PRA TELA. Nunca confundir os dois nem fundir
// as duas funções: um id interno serve o modelo bem e o gestor mal.
import type { AgendaPayload, VisitaAgenda } from '@/lib/odoo/agenda'
import { horaOdoo } from '@/app/tecnico/qualificacao/_components/VisitaCard'
import type { Proposta } from './machine'

export interface LinhaCardProposta {
  rotulo: string
  /** Ausente = linha de CONTEXTO (sem seta): não houve "de", só o valor atual. */
  de?: string
  para: string
}

export interface CardProposta {
  titulo: string
  subtitulo?: string
  /** Presente só quando a visita alvo não está na janela carregada na tela. */
  aviso?: string
  linhas: LinhaCardProposta[]
}

const DIAS_SEMANA_ABREV = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']

/**
 * "2026-09-24" → "qui, 24/09/2026". Sigla de 3 letras sem ponto — é o que
 * prova pro gestor que "mesmo dia da semana" bateu num pedido como
 * "remarca pro mesmo dia da semana que vem".
 *
 * Não reusa `Intl.DateTimeFormat('pt-BR', { weekday: 'short' })`: o CLDR
 * pt-BR devolve "qui." COM ponto, formato diferente do pedido. Não reusa
 * `FORMATADOR_ROTULO_DIA` de `agenda/_GradeMes.tsx` porque aquele não leva
 * dia da semana (é "24 de setembro", pensado pra célula do calendário, não
 * pra frase de confirmação).
 */
export function formatarDataHumana(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(a, m - 1, d))
  const dia = DIAS_SEMANA_ABREV[dt.getUTCDay()]
  const dd = String(d).padStart(2, '0')
  const mm = String(m).padStart(2, '0')
  return `${dia}, ${dd}/${mm}/${a}`
}

/** Mesma coerção de `alvoDaProposta` (antigo `_ChatAgenda.tsx`): o modelo às
 * vezes manda id inteiro como string, e rejeitar aqui perde a única defesa
 * visual do gestor bem na hora em que ela mais importa. */
function coagirId(bruto: unknown): number | null {
  if (typeof bruto !== 'number' && typeof bruto !== 'string') return null
  const id = Number(bruto)
  return Number.isInteger(id) ? id : null
}

function encontrarVisita(payload: AgendaPayload, bruto: unknown): VisitaAgenda | null {
  const id = coagirId(bruto)
  if (id === null) return null
  return payload.visitas.find((v) => v.id === id) ?? null
}

/** Resolve pelo que já está em mãos (visitas da janela aberta); sem isso, cai
 * no id cru — melhor que travar o card por falta de um `listar_tecnicos`. */
function nomeTecnico(payload: AgendaPayload, bruto: unknown): string {
  const id = coagirId(bruto)
  if (id === null) return String(bruto)
  const v = payload.visitas.find((x) => x.tecnico_id === id)
  return v ? v.tecnico_name : `técnico ${id}`
}

function nomeOs(payload: AgendaPayload, bruto: unknown): string {
  const id = coagirId(bruto)
  if (id === null) return String(bruto)
  const v = payload.visitas.find((x) => x.os_id === id)
  return v ? v.os_name : `OS ${id}`
}

function juntarSubtitulo(...partes: Array<string | false | undefined>): string | undefined {
  const validas = partes.filter((p): p is string => Boolean(p))
  return validas.length ? validas.join(' · ') : undefined
}

/**
 * Horário: só a metade que o modelo mandou muda; a outra ponta do intervalo
 * herda do valor atual da visita (mesma regra de negócio de `tools.ts`,
 * comentário de `updateVisita` em `lib/odoo/agenda.ts`).
 */
function linhaHorario(alvo: VisitaAgenda, args: Record<string, unknown>): LinhaCardProposta {
  const deIni = horaOdoo(alvo.time_start)
  const deFim = horaOdoo(alvo.time_stop)
  const paraIni = args.time_start !== undefined ? horaOdoo(Number(args.time_start)) : deIni
  const paraFim = args.time_stop !== undefined ? horaOdoo(Number(args.time_stop)) : deFim
  return { rotulo: 'Horário', de: `${deIni}–${deFim}`, para: `${paraIni}–${paraFim}` }
}

function linhasComAlvo(payload: AgendaPayload, alvo: VisitaAgenda, args: Record<string, unknown>): LinhaCardProposta[] {
  const linhas: LinhaCardProposta[] = []
  const horarioMuda = args.time_start !== undefined || args.time_stop !== undefined

  if (typeof args.date === 'string') {
    linhas.push({ rotulo: 'Data', de: formatarDataHumana(alvo.date), para: formatarDataHumana(args.date) })
  } else if (horarioMuda) {
    // Só o horário muda: mostra a data como CONTEXTO (sem seta) — decisão
    // do controlador (task brief, MUDANÇA A item 5). Saber qual dia está
    // sendo mexido importa mesmo quando o dia em si não muda.
    linhas.push({ rotulo: 'Data', para: formatarDataHumana(alvo.date) })
  }

  if (horarioMuda) linhas.push(linhaHorario(alvo, args))

  if (args.tecnico_id !== undefined) {
    linhas.push({ rotulo: 'Técnico', de: alvo.tecnico_name || undefined, para: nomeTecnico(payload, args.tecnico_id) })
  }

  if (Array.isArray(args.instrument_ids)) {
    // Ids, não nomes: `instrument_list` do servidor filtra tag/id_number/name
    // vazios (`_pwa_serialize`, `os_visita.py`), então o índice NÃO alinha
    // de forma garantida com `instrument_ids` — resolver por posição podia
    // mostrar o instrumento errado. Id cru aqui é honesto; nome errado não
    // seria. Ver relatório da task para a evidência no backend.
    linhas.push({
      rotulo: 'Instrumentos (ids)',
      de: alvo.instrument_ids.join(', '),
      para: (args.instrument_ids as unknown[]).join(', '),
    })
  }

  if (args.note !== undefined) {
    // Sem "de"/conteúdo cru: observação pode ser texto longo, e o card não
    // é lugar de diff de texto livre — só avisa que mudou.
    linhas.push({ rotulo: 'Observação', para: 'alterada' })
  }

  return linhas
}

/** Mesmo formato de `linhasComAlvo`, mas sem nenhum "de" — usado quando a
 * visita não está na janela carregada e não há como saber o valor atual. */
function linhasSemAlvo(payload: AgendaPayload, args: Record<string, unknown>): LinhaCardProposta[] {
  const linhas: LinhaCardProposta[] = []
  if (typeof args.date === 'string') linhas.push({ rotulo: 'Data', para: formatarDataHumana(args.date) })
  if (args.time_start !== undefined || args.time_stop !== undefined) {
    const paraIni = args.time_start !== undefined ? horaOdoo(Number(args.time_start)) : '?'
    const paraFim = args.time_stop !== undefined ? horaOdoo(Number(args.time_stop)) : '?'
    linhas.push({ rotulo: 'Horário', para: `${paraIni}–${paraFim}` })
  }
  if (args.tecnico_id !== undefined) {
    // `nomeTecnico` procura em TODAS as visitas do payload, não só na
    // visita alvo (que aqui nem existe) — resolve o nome sempre que o
    // técnico aparece em alguma visita da janela aberta na tela, mesmo sem
    // o alvo. Id cru só sobra quando nem isso acha.
    linhas.push({ rotulo: 'Técnico', para: nomeTecnico(payload, args.tecnico_id) })
  }
  if (Array.isArray(args.instrument_ids)) {
    linhas.push({ rotulo: 'Instrumentos (ids)', para: (args.instrument_ids as unknown[]).join(', ') })
  }
  if (args.note !== undefined) linhas.push({ rotulo: 'Observação', para: 'alterada' })
  return linhas
}

function cardAtualizarVisita(payload: AgendaPayload, args: Record<string, unknown>): CardProposta {
  const verbo = typeof args.date === 'string' ? 'Remarcar' : 'Alterar'
  const alvo = encontrarVisita(payload, args.visita_id)

  if (!alvo) {
    const id = coagirId(args.visita_id)
    return {
      titulo: `${verbo} visita`,
      aviso: id !== null
        ? `visita ${id} · fora do período aberto na agenda`
        : 'visita não identificada nesta conversa',
      linhas: linhasSemAlvo(payload, args),
    }
  }

  return {
    titulo: `${verbo} visita da ${alvo.os_name}`,
    subtitulo: juntarSubtitulo(alvo.tecnico_name, alvo.partner_name, alvo.city),
    linhas: linhasComAlvo(payload, alvo, args),
  }
}

function cardCriarVisita(payload: AgendaPayload, args: Record<string, unknown>): CardProposta {
  const linhas: LinhaCardProposta[] = []
  if (typeof args.date === 'string') linhas.push({ rotulo: 'Data', para: formatarDataHumana(args.date) })
  if (args.tecnico_id !== undefined) linhas.push({ rotulo: 'Técnico', para: nomeTecnico(payload, args.tecnico_id) })
  return {
    titulo: `Criar visita para ${nomeOs(payload, args.os_id)}`,
    linhas,
  }
}

/** Monta o card que o gestor vê antes de confirmar. Nunca lança: uma
 * ferramenta de escrita desconhecida cai no `resumo` cru de `resumir()`
 * (fallback deliberado, ver comentário da task) em vez de quebrar a tela. */
export function montarCardProposta(payload: AgendaPayload, proposta: Proposta): CardProposta {
  if (proposta.name === 'criar_visita') return cardCriarVisita(payload, proposta.args)
  if (proposta.name === 'atualizar_visita') return cardAtualizarVisita(payload, proposta.args)
  return { titulo: proposta.resumo, linhas: [] }
}
