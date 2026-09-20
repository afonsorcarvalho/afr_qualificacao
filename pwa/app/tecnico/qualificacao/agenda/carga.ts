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

/** Um uso de um instrumento numa visita: quem, quando, em qual OS. */
export interface UsoDeVisita {
  visitaId: number
  osName: string
  tecnicoName: string
  faixa: string
}

export interface UsoInstrumento {
  id: number
  name: string
  vencido: boolean
  usos: UsoDeVisita[]
}

/**
 * Linha da seção "Instrumentos do dia" do modo Mês. Nasce de um
 * `PontoInstrumento` (a MESMA entrada que virou triângulo na célula e chip na
 * legenda) acrescido dos usos do dia — por isso carrega `cor` e `name` do
 * ponto, em vez de recalcular: é a garantia estrutural de que as duas metades
 * da tela não podem discordar sobre quais instrumentos o dia tem.
 *
 * Sem `vencido`, ao contrário de `UsoInstrumento`: o aviso de certificado
 * vencido está fora de escopo no Mês por escolha do usuário, e um campo à mão
 * é um convite a reintroduzi-lo.
 */
export interface InstrumentoDoDia {
  id: number
  name: string
  cor: string
  usos: UsoDeVisita[]
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

/**
 * Horas de UMA visita, a partir do par início/fim — nunca de `planned_hours`.
 *
 * `planned_hours` é um float comum do backend (`os_visita.py`), preenchido
 * só por onchange no form clássico do Odoo. `pwa_visita_create` cria a
 * visita com `planned_hours = 0` (não está na lista de campos do create), e
 * embora `pwa_visita_update` já recalcule o campo quando o par início/fim
 * muda, a visita nasce zerada e alguns fluxos (ex. edição pelo board, fora
 * do PWA) podem gravar o par sem tocar `planned_hours`. Resultado visto pelo
 * usuário: cards com horário 08:00–12:00 e o painel de recursos acusando
 * "livre" — o card lê o horário, o painel lia o campo. Calculando os dois a
 * partir da MESMA janela, painel e card nunca podem discordar de novo.
 *
 * Caso de virada de dia (`overflow_next_day` do backend, exposto como
 * `overflow`): a visita ainda NÃO foi dividida pelo botão "Dividir em 2
 * dias" (`_split_overflow`) e o turno atravessa a meia-noite. Duas formas
 * chegam ao PWA, e cada uma cai num ramo diferente daqui:
 *
 * - `time_stop > 24` (o onchange clássico do form, `time_start +
 *   planned_hours`, não é limitado a 24h): cai no primeiro `if` como
 *   qualquer janela normal e devolve o valor cheio (ex. 20h–26h → 6h). É o
 *   caso certo a contar assim: antes da divisão não existe AINDA a visita-
 *   continuação do dia seguinte, e truncar aqui faria 2h sumirem da semana
 *   sem aparecer em lugar nenhum — o card mostra a mesma faixa 20:00–02:00,
 *   então a carga tem que bater com o que o card promete.
 * - `time_stop <= time_start` (ex. 22h–2h, quando o horário já foi digitado
 *   "ao contrário" e não há como saber quanto passa da meia-noite só pelo
 *   par): sem como recuperar as horas reais, contamos o que cabe até o fim
 *   do dia — `24 - time_start` (sempre ≥ 0, pois `time_start` é hora do
 *   dia) — em vez de inventar uma duração.
 *
 * Em ambos, a eventual continuação (dia seguinte) é OUTRA visita na lista,
 * com sua própria janela normal, e soma as horas dela por conta própria —
 * sem dupla contagem aqui. Sem o sinal de overflow, uma janela não-crescente
 * é dado inconsistente sem regra conhecida (ex. edição direta malformada
 * fora do PWA): 0h, para nunca inflar nem subtrair carga de ninguém por um
 * dado quebrado, e nunca devolver um número negativo.
 */
export function horasDaVisita(
  v: Pick<VisitaAgenda, 'time_start' | 'time_stop' | 'overflow'>,
): number {
  if (v.time_stop > v.time_start) return v.time_stop - v.time_start
  if (v.overflow) return Math.max(0, 24 - v.time_start)
  return 0
}

export function cargaPorDia(
  visitas: VisitaAgenda[],
  dias: string[],
): CargaDia[] {
  return dias.map((date) => {
    const doDia = visitas.filter((v) => v.date === date)
    return {
      date,
      horas: doDia.reduce((s, v) => s + horasDaVisita(v), 0),
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
      .reduce((s, v) => s + horasDaVisita(v), 0),
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

/**
 * Usos de UM instrumento dentro de uma lista de visitas JÁ filtrada pelo dia.
 * Recebe `doDia`, não `visitas`: quem chama filtra a data uma vez só e reusa
 * — refiltrar por instrumento levaria o painel da Semana de `V + N×V_dia`
 * para `N×V`.
 *
 * Ordenado por horário, não pela ordem de chegada da API: o backend por acaso
 * já devolve `date, time_start, id`, mas depender de ordenação incidental é a
 * mesma fragilidade que já custou fix rounds nesta feature, e o painel lê
 * isto de relance ("8–12, depois 13–17").
 */
function usosNoDia(doDia: VisitaAgenda[], id: number): UsoDeVisita[] {
  return doDia
    .filter((v) => v.instrument_ids.includes(id))
    .slice()
    .sort((a, b) => a.time_start - b.time_start)
    .map((v) => ({
      visitaId: v.id,
      osName: v.os_name,
      tecnicoName: v.tecnico_name,
      faixa: `${horaOdoo(v.time_start)}–${horaOdoo(v.time_stop)}`,
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
    usos: usosNoDia(doDia, i.id),
  }))
}

/**
 * Seção "Instrumentos do dia" do modo Mês.
 *
 * A fonte da lista são os `pontos` — a entrada de `instrumentosPorDia`
 * correspondente ao dia selecionado, a MESMA que desenhou os triângulos da
 * célula e os chips da legenda —, e não o catálogo
 * `pwa_instrumento_options`. Antes do fix final, a seção mapeava sobre o
 * catálogo (a INTERSEÇÃO entre usado e catalogado) enquanto a grade mostrava
 * a UNIÃO: bastava um id usado estar fora das opções (instrumento arquivado,
 * catálogo que falhou de carregar) para as duas metades da tela se
 * contradizerem em silêncio — a grade afirmando que o dia tem o instrumento e
 * a lista negando.
 *
 * `usoPorInstrumento` continua intocada: o painel da Semana precisa listar
 * TODO instrumento do catálogo, inclusive os sem uso, justamente pra mostrar
 * quem está livre. São duas perguntas diferentes sobre o mesmo dia.
 */
export function instrumentosDoDia(
  visitas: VisitaAgenda[],
  dia: string,
  pontos: { id: number; name: string; cor: string }[],
): InstrumentoDoDia[] {
  const doDia = visitas.filter((v) => v.date === dia)
  return pontos.map((p) => ({
    id: p.id,
    name: p.name,
    cor: p.cor,
    usos: usosNoDia(doDia, p.id),
  }))
}
