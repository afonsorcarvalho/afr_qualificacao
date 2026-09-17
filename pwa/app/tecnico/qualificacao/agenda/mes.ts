/**
 * Grade mensal da agenda — funções puras, sem React e sem relógio local.
 *
 * Tudo aqui trabalha em cima de datas ISO (`YYYY-MM-DD`) e usa só
 * `Date.UTC`/`setUTCDate`/`getUTCDay`: nenhuma função lê `new Date()` sem
 * argumento nem o fuso local do aparelho, pelo mesmo motivo de `carga.ts` e
 * `janela.ts` — quem decide "hoje" é o servidor, o front só soma dias sobre
 * uma data que já veio pronta.
 */
import type { VisitaAgenda, Opcao } from '@/lib/odoo/agenda'

export interface PontoTecnico {
  /** `false` = visita sem técnico atribuído. */
  id: number | false
  name: string // "Sem técnico" quando id === false
  cor: string
  visitas: number
}

export interface PontosDia {
  date: string
  pontos: PontoTecnico[]
  /** Soma das visitas do dia (≥ soma dos pontos quando um técnico tem duas). */
  total: number
  conflito: boolean
}

/** "2026-09-17" → "2026-09-01". Normaliza qualquer dia para o 1º do mês. */
export function primeiroDiaDoMes(iso: string): string {
  return `${iso.slice(0, 7)}-01`
}

/**
 * Soma `n` meses ao 1º do mês da âncora. `n` pode ser negativo. Sempre
 * devolve o dia 1 do mês resultante — nunca estoura para o mês seguinte
 * (o bug clássico de somar mês em cima de um dia 31, tipo
 * `new Date(2026, 0, 31).setMonth(1)` virar março). Construir o `Date.UTC`
 * já com dia 1 evita o estouro por completo: não existe "dia 31 de
 * fevereiro" pra transbordar.
 */
export function deslocarMes(iso: string, n: number): string {
  const [a, m] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(a, m - 1 + n, 1))
  return dt.toISOString().slice(0, 10)
}

/**
 * Grade de 6×7 = 42 dias ISO, começando no domingo anterior (ou igual) ao
 * dia 1 do mês da âncora. Sempre 42, mesmo quando o mês cabe em 5 semanas —
 * uma grade de tamanho variável faz a UI pular de altura ao trocar de mês;
 * mês curto sobra dia no fim, mês que atravessa 6 semanas (começa perto do
 * fim de uma semana e tem 31 dias) cabe sem cortar o último dia.
 */
export function gradeDoMes(iso: string): string[] {
  const primeiro = primeiroDiaDoMes(iso)
  const [a, m, d] = primeiro.split('-').map(Number)
  const diaSemana = new Date(Date.UTC(a, m - 1, d)).getUTCDay() // 0 = domingo
  const inicio = new Date(Date.UTC(a, m - 1, d - diaSemana))
  return Array.from({ length: 42 }, (_, i) => {
    const dt = new Date(inicio)
    dt.setUTCDate(dt.getUTCDate() + i)
    return dt.toISOString().slice(0, 10)
  })
}

/**
 * `true` se a data ISO pertence ao mês da âncora (para esmaecer as células
 * de fora sem escondê-las — a grade sempre mostra as pontas do mês
 * anterior/seguinte, é só a cor que muda).
 */
export function noMes(iso: string, ancora: string): boolean {
  return iso.slice(0, 7) === ancora.slice(0, 7)
}

/** "setembro de 2026", pt-BR, `timeZone: 'UTC'`. */
export function rotuloMes(iso: string): string {
  const [a, m] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(a, m - 1, 1))
  return new Intl.DateTimeFormat('pt-BR', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(dt)
}

// Paleta de 12 tons — cresceu de 8 no fix round 2 (achado 5): `corDoTecnico`
// indexa por `id % PALETA.length` com id de BANCO, então com 8 cores nove
// técnicos já colidiam garantido, e ids arbitrários colidiam bem antes (3 e
// 11 caíam na mesma). Dois chips iguais na legenda e dois pontinhos
// indistinguíveis na célula derrubam a única coisa que o modo Mês entrega:
// ver de relance DE QUEM é a visita.
//
// Nenhuma cor é livre: cada uma passa 3:1 (piso da WCAG 1.4.11 para
// elemento gráfico que carrega informação) sobre o `--card` dos DOIS temas —
// quase branco no claro, quase preto no escuro —, o que descarta metade do
// catálogo do Tailwind (os amarelos claros somem no claro, os tons 800+
// somem no escuro). Medido em `mes.test.ts`, que quebra se alguém trocar um
// tom por um mais bonito e menos legível.
//
// A ORDEM também é escolhida: os matizes não entram em roda-cromática, e sim
// intercalados (passo 5 sobre a roda), porque ids consecutivos são o caso
// comum num cadastro — e matizes vizinhos em índices vizinhos seriam
// justamente as duas cores parecidas na mesma célula.
export const PALETA: string[] = [
  '#db2777', // pink-600
  '#16a34a', // green-600
  '#7c3aed', // violet-600
  '#a16207', // yellow-700
  '#0369a1', // sky-700
  '#e11d48', // rose-600
  '#0d9488', // teal-600
  '#c026d3', // fuchsia-600
  '#4d7c0f', // lime-700
  '#6366f1', // indigo-500
  '#ea580c', // orange-600
  '#0891b2', // cyan-600
]

export const COR_SEM_TECNICO = '#6b7280' // gray-500

/**
 * Cor estável por id de técnico. `false` (visita sem técnico) devolve o
 * cinza neutro. A estabilidade é por id, não por posição no roster: o
 * roster muda de tamanho entre janelas (ver `rosterTecnicos` em
 * `carga.ts`) e cores que dançam a cada troca de mês mentem sobre quem é
 * quem na grade.
 */
export function corDoTecnico(id: number | false): string {
  if (id === false) return COR_SEM_TECNICO
  return PALETA[id % PALETA.length]
}

/**
 * Um item por técnico distinto com visita no dia, na ordem do roster (que
 * já vem ordenado por nome em `rosterTecnicos`), seguido do balde "sem
 * técnico" quando houver visita sem `tecnico_id`. Técnico do roster sem
 * visita no dia não vira ponto — a célula do mês só tem espaço pra quem
 * está de fato ali, ao contrário do painel de carga da semana que lista
 * todo mundo pra mostrar quem está livre.
 */
export function tecnicosPorDia(
  visitas: VisitaAgenda[],
  dias: string[],
  roster: Opcao[],
): PontosDia[] {
  return dias.map((date) => {
    const doDia = visitas.filter((v) => v.date === date)
    const pontos: PontoTecnico[] = []

    for (const t of roster) {
      const doTecnico = doDia.filter((v) => v.tecnico_id === t.id)
      if (doTecnico.length === 0) continue
      pontos.push({
        id: t.id,
        name: t.name,
        cor: corDoTecnico(t.id),
        visitas: doTecnico.length,
      })
    }

    const semTecnico = doDia.filter((v) => v.tecnico_id === false)
    if (semTecnico.length > 0) {
      pontos.push({
        id: false,
        name: 'Sem técnico',
        cor: COR_SEM_TECNICO,
        visitas: semTecnico.length,
      })
    }

    return {
      date,
      pontos,
      total: doDia.length,
      conflito: doDia.some((v) => v.conflict),
    }
  })
}
