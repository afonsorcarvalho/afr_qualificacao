/**
 * Carga e ocupação da semana — funções puras, sem React e sem relógio local.
 *
 * O servidor decide a janela (`server_today` no payload) e devolve as visitas;
 * tudo aqui é agregação do que já veio. Nenhuma chamada de rede, para que o
 * painel possa ser testado sem montar componente.
 */
import { horaOdoo } from '../_components/VisitaCard'
import type { VisitaAgenda, Opcao, InstrumentoOpcao } from '@/lib/odoo/agenda'

// `InstrumentoOpcao` vem da camada de dados (Task 4), não é redefinido aqui:
// duas interfaces com o mesmo nome divergem na primeira mudança.
export type { Opcao, InstrumentoOpcao }

export interface CargaDia {
  date: string
  horas: number
  conflito: boolean
}

export interface CargaTecnico {
  id: number
  name: string
  horas: number
}

export interface UsoInstrumento {
  id: number
  name: string
  vencido: boolean
  usos: {
    visitaId: number
    osName: string
    tecnicoName: string
    faixa: string
  }[]
}

/** Sete dias ISO a partir de `inicio`, em UTC — nunca lê o relógio do aparelho. */
export function diasDaSemana(inicio: string): string[] {
  const [a, m, d] = inicio.split('-').map(Number)
  const base = Date.UTC(a, m - 1, d)
  return Array.from({ length: 7 }, (_, i) => {
    const dt = new Date(base)
    dt.setUTCDate(dt.getUTCDate() + i)
    return dt.toISOString().slice(0, 10)
  })
}

export function cargaPorDia(
  visitas: VisitaAgenda[],
  dias: string[],
): CargaDia[] {
  return dias.map((date) => {
    const doDia = visitas.filter((v) => v.date === date)
    return {
      date,
      horas: doDia.reduce((s, v) => s + (v.planned_hours || 0), 0),
      conflito: doDia.some((v) => v.conflict),
    }
  })
}

/**
 * Inclui TODO técnico do roster, mesmo sem visita — é justamente para quem
 * está livre que se quer mover.
 */
export function cargaPorTecnico(
  visitas: VisitaAgenda[],
  dia: string,
  tecnicos: Opcao[],
): CargaTecnico[] {
  return tecnicos.map((t) => ({
    id: t.id,
    name: t.name,
    horas: visitas
      .filter((v) => v.date === dia && v.tecnico_id === t.id)
      .reduce((s, v) => s + (v.planned_hours || 0), 0),
  }))
}

/**
 * União do roster oficial (`pwa_tecnico_options`, filtrado por
 * `is_tecnico=True`) com os técnicos que aparecem nas visitas da janela mas
 * não têm a flag — `tecnico_id` na visita não é restrito a `is_tecnico`, e
 * um painel de capacidade que só mostra o roster oficial esconderia carga
 * real de quem tem visita, mentindo sobre capacidade. Sem duplicar por id;
 * ordenado por nome para a lista não dançar ao trocar de dia.
 */
export function rosterTecnicos(
  oficiais: Opcao[],
  visitas: VisitaAgenda[],
): Opcao[] {
  const porId = new Map<number, string>()
  for (const t of oficiais) porId.set(t.id, t.name)
  for (const v of visitas) {
    if (v.tecnico_id !== false && !porId.has(v.tecnico_id)) {
      porId.set(v.tecnico_id, v.tecnico_name)
    }
  }
  return Array.from(porId, ([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))
}

/**
 * Pico de horas de um único técnico-dia, na semana visível inteira — não só
 * no dia selecionado. A escala da barra de carga precisa ser comparável
 * entre dois dias distintos ("proporcional ao técnico-dia mais cheio da
 * semana visível"); calculada só sobre o dia atual, as barras reescalam a
 * cada troca de dia e dois dias não são comparáveis de relance.
 */
export function picoDaSemana(
  visitas: VisitaAgenda[],
  dias: string[],
  tecnicos: Opcao[],
): number {
  let max = 0
  for (const dia of dias) {
    for (const t of cargaPorTecnico(visitas, dia, tecnicos)) {
      if (t.horas > max) max = t.horas
    }
  }
  return Math.max(1, max)
}

export function usoPorInstrumento(
  visitas: VisitaAgenda[],
  dia: string,
  instrumentos: InstrumentoOpcao[],
): UsoInstrumento[] {
  const doDia = visitas.filter((v) => v.date === dia)
  return instrumentos.map((i) => ({
    id: i.id,
    name: i.name,
    // Sem certificado conta como vencido: não há data que alcance o dia.
    // Validade igual ao dia ainda vale — é o mesmo `>=` do
    // `_instrument_valid_on` no servidor.
    vencido: !i.validade || i.validade < dia,
    // Ordenado por horário, não pela ordem de chegada da API: o backend por
    // acaso já devolve `date, time_start, id`, mas depender de ordenação
    // incidental é a mesma fragilidade que já custou fix rounds nesta
    // feature, e o painel lê isto de relance ("8–12, depois 13–17").
    usos: doDia
      .filter((v) => v.instrument_ids.includes(i.id))
      .slice()
      .sort((a, b) => a.time_start - b.time_start)
      .map((v) => ({
        visitaId: v.id,
        osName: v.os_name,
        tecnicoName: v.tecnico_name,
        faixa: `${horaOdoo(v.time_start)}–${horaOdoo(v.time_stop)}`,
      })),
  }))
}
