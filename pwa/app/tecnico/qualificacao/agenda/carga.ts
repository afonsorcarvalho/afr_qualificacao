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
    usos: doDia
      .filter((v) => v.instrument_ids.includes(i.id))
      .map((v) => ({
        visitaId: v.id,
        osName: v.os_name,
        tecnicoName: v.tecnico_name,
        faixa: `${horaOdoo(v.time_start)}–${horaOdoo(v.time_stop)}`,
      })),
  }))
}
