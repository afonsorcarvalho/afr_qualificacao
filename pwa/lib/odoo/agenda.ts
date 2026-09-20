/**
 * Agenda de visitas — transporte RPC puro. Zero regra de negócio: quem
 * decide o que é editável, e qual é a janela de datas, é o servidor
 * (`pwa_agenda_fetch`).
 */
import odooClient from './client'

export const VISITA_MODEL = 'afr.qualificacao.os.visita'

export interface VisitaAgenda {
  id: number
  date: string
  time_start: number
  time_stop: number
  planned_hours: number
  os_id: number | false
  os_name: string
  os_state: string | false
  partner_name: string
  city: string
  equipment_list: string[]
  instrument_list: string[]
  /** Ids dos instrumentos — a folha marca por eles, o painel casa por eles. */
  instrument_ids: number[]
  tecnico_id: number | false
  tecnico_name: string
  is_mine: boolean
  state: 'planned' | 'done'
  overflow: boolean
  editable: boolean
  /** Frase pronta do servidor quando `editable` é falso. */
  lock_reason: string | false
  conflict: boolean
  conflict_msg: string
  note: string
}

export interface AgendaPayload {
  server_today: string
  date_from: string
  date_to: string
  my_employee_id: number | false
  can_manage: boolean
  visitas: VisitaAgenda[]
}

export interface VisitaVals {
  date?: string
  time_start?: number
  time_stop?: number
  tecnico_id?: number
  note?: string
  /** Lista simples de ids; o servidor monta o `(6, 0, ids)`. */
  instrument_ids?: number[]
}

export interface Opcao {
  id: number
  name: string
  /**
   * Índice do seletor de cor nativo do Odoo (0 = "sem cor" = cor automática
   * na agenda). Opcional porque `rosterTecnicos` (`carga.ts`) une este roster
   * oficial com técnicos vindos das visitas, que não têm índice nenhum —
   * ausente cai na mesma regra de "sem cor" (ver `corDoTecnico` em `mes.ts`).
   */
  color?: number
}

export async function fetchAgenda(
  dateFrom: string | null,
  dateTo: string | null,
  onlyMine: boolean,
): Promise<AgendaPayload> {
  return odooClient.callKw<AgendaPayload>(VISITA_MODEL, 'pwa_agenda_fetch', [], {
    date_from: dateFrom,
    date_to: dateTo,
    only_mine: onlyMine,
  })
}

/**
 * O PWA é publicado dentro de `afr_qualificacao`, mas o modelo de visita vive
 * em `afr_qualificacao_agendamento`, que DEPENDE de `afr_qualificacao`. A
 * dependência aponta ao contrário do uso, então a aba não pode ser assumida.
 */
export async function agendaDisponivel(): Promise<boolean> {
  const n = await odooClient.searchCount('ir.model', [['model', '=', VISITA_MODEL]])
  return n > 0
}

/**
 * Uma visita recém-criada nasce com `time_start = time_stop = 0.0`. O
 * backend recusa um `pwa_visita_update` que mande só `time_start` nesse
 * caso (hora fim ficaria antes da início) — sempre mandar os dois juntos.
 */
export async function updateVisita(id: number, vals: VisitaVals): Promise<VisitaAgenda> {
  return odooClient.callKw<VisitaAgenda>(VISITA_MODEL, 'pwa_visita_update', [id, vals])
}

export async function createVisita(
  osId: number,
  tecnicoId: number,
  date: string,
): Promise<VisitaAgenda> {
  return odooClient.callKw<VisitaAgenda>(VISITA_MODEL, 'pwa_visita_create', [osId, tecnicoId, date])
}

export async function deleteVisita(id: number): Promise<boolean> {
  return odooClient.callKw<boolean>(VISITA_MODEL, 'pwa_visita_delete', [id])
}

/**
 * `board_technician_options` exige leitura de `hr.employee` sem `sudo`, que
 * o Gestor só tem hoje porque os Gestores existentes têm a caixa de HR
 * marcada à mão. `pwa_tecnico_options` espelha o mesmo resultado em `sudo()`
 * no servidor — um Gestor novo sem essa caixa não toma `AccessError` aqui.
 */
export async function listTecnicoOptions(): Promise<Opcao[]> {
  return odooClient.callKw<Opcao[]>(VISITA_MODEL, 'pwa_tecnico_options', [])
}

export async function listOsOptions(): Promise<Opcao[]> {
  return odooClient.callKw<Opcao[]>(VISITA_MODEL, 'board_os_options', [])
}

export interface InstrumentoOpcao {
  id: number
  name: string
  /** Maior `validate_calibration` dos certificados; `false` se não há nenhum. */
  validade: string | false
  /**
   * Índice do seletor de cor nativo do Odoo (0 = "sem cor" = cor automática
   * na agenda). Mesmo papel do `color` de `Opcao`, mas aqui sempre vem do
   * servidor (`pwa_instrumento_options`) — opcional só para não travar
   * construções de teste que montam o objeto à mão.
   */
  color?: number
}

export async function listInstrumentoOptions(): Promise<InstrumentoOpcao[]> {
  return odooClient.callKw<InstrumentoOpcao[]>(
    VISITA_MODEL, 'pwa_instrumento_options', [],
  )
}
