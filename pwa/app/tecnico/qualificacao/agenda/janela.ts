import type { VisitaAgenda } from '@/lib/odoo/agenda'

export interface GrupoDia {
  date: string
  visitas: VisitaAgenda[]
}

/** Agrupa preservando a ordem em que o servidor mandou. */
export function agruparPorDia(visitas: VisitaAgenda[]): GrupoDia[] {
  const grupos: GrupoDia[] = []
  for (const v of visitas) {
    const ultimo = grupos[grupos.length - 1]
    if (ultimo && ultimo.date === v.date) ultimo.visitas.push(v)
    else grupos.push({ date: v.date, visitas: [v] })
  }
  return grupos
}

/**
 * Soma dias a uma data ISO sem tocar no relógio do aparelho. `Date.UTC` evita
 * que o fuso local mude o dia — o servidor é quem diz que dia é hoje.
 */
export function deslocarJanela(dateFrom: string, dias: number): string {
  const [a, m, d] = dateFrom.split('-').map(Number)
  const base = new Date(Date.UTC(a, m - 1, d))
  base.setUTCDate(base.getUTCDate() + dias)
  return base.toISOString().slice(0, 10)
}
