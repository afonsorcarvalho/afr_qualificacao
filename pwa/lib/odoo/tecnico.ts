/**
 * F7.0 — RPC helpers tipados pra PWA Técnico de Campo.
 * Reusa odooClient global. Não cria controllers backend novos.
 */
import odooClient from './client'

function toOdooDatetime(d: Date): string {
  return d.toISOString().slice(0, 19).replace('T', ' ')
}

export interface OsTecnicoSummary {
  id: number
  name: string
  partner_id: [number, string]
  state: 'draft' | 'scheduled' | 'in_progress' | 'in_approved' | 'approved' | 'done' | 'cancelled'
  date_planned_start: string | false
  collect_pending_count: number
  collect_collected_count: number
  collect_total_count: number
  tecnico_default_id: [number, string] | false
  tecnico_default_user_id: [number, string] | false
  equipment_count?: number
}

export interface ColetaItemDetail {
  id: number
  name: string
  kind: 'foto' | 'excel' | 'pdf' | 'qualificador_data' | 'outro'
  required: boolean
  state: 'pending' | 'collected' | 'skipped'
  description: string | false
  instruction: string | false
  requires_instrument: boolean
  docx_section: string | false
  qualif_id: [number, string]
  cycle_id: [number, string] | false
  malha_id: [number, string] | false
  equipment_id: [number, string] | false
  standard_instrument_ids: number[]
  file: string | false
  filename: string | false
  mimetype: string | false
  captured_at: string | false
  captured_by: [number, string] | false
}

export interface InstrumentInfo {
  id: number
  name: string
  tag: string | false
  id_number: string | false
  marca: string | false
  modelo: string | false
  has_valid_certificate: boolean
}

export interface EquipmentInfo {
  id: number
  name: string
  apelido: string | false
  tag: string | false
  model: string | false
  serial_number: string | false
  marca_id: [number, string] | false
}

export interface RelatorioHistorico {
  id: number
  name: string
  os_id: [number, string]
  state: 'draft' | 'done' | 'cancel'
  data_inicio: string | false
  data_fim: string | false
  signature_technician_date: string | false
  time_execution: number
  pending_collect_count: number
  collect_item_ids: number[]
}

export interface HistoricoSummary {
  hoje_coletas: number
  hoje_oss: number
  hoje_relatorios_fechados: number
}

export interface RelatorioDetail {
  id: number
  name: string
  os_id: [number, string]
  state: 'draft' | 'done' | 'cancel'
  data_inicio: string | false
  data_fim: string | false
  signature_technician_date: string | false
  time_execution: number
  pending_collect_count: number
  descricao: string | false
  signature_technician: string | false
  collect_item_ids: number[]
}

export interface RelatorioFullDetail {
  relatorio: RelatorioDetail
  collect_items: ColetaItemDetail[]
}

const OS_FIELDS = [
  'name', 'partner_id', 'state', 'date_planned_start',
  'collect_pending_count', 'collect_collected_count', 'collect_total_count',
  'tecnico_default_id', 'tecnico_default_user_id',
]

export async function listOsMine(
  userId: number,
  filterMine: boolean,
): Promise<OsTecnicoSummary[]> {
  const baseDomain: unknown[] = [
    ['state', 'in', ['draft', 'scheduled', 'in_progress', 'in_approved']],
  ]
  // Espelho stored na OS (v16.0.6.4.0). O domain antigo
  // `tecnico_default_id.user_id` sub-busca hr.employee, que o grupo Técnico
  // não lê no Odoo 16 — retornava vazio pro próprio técnico.
  const domain = filterMine
    ? [...baseDomain, ['tecnico_default_user_id', '=', userId]]
    : baseDomain
  const os = await odooClient.searchRead<OsTecnicoSummary>(
    'afr.qualificacao.os',
    domain,
    OS_FIELDS,
  )
  if (os.length === 0) return os
  const ids = os.map((o) => o.id)
  const items = await odooClient.searchRead<{ os_id: [number, string]; equipment_id: [number, string] | false }>(
    'afr.qualificacao.collect.item',
    [['os_id', 'in', ids]],
    ['os_id', 'equipment_id'],
  )
  const byOs = new Map<number, Set<number>>()
  for (const it of items) {
    if (!it.equipment_id) continue
    const osId = Array.isArray(it.os_id) ? it.os_id[0] : 0
    if (!osId) continue
    if (!byOs.has(osId)) byOs.set(osId, new Set())
    byOs.get(osId)!.add(it.equipment_id[0])
  }
  return os.map((o) => ({ ...o, equipment_count: byOs.get(o.id)?.size ?? 0 }))
}

export async function getOsDetail(
  osId: number,
  // Não é mais usado pra achar o relatório do dia (o servidor resolve isso
  // via `action_get_daily_relatorio`, filtrando por `tecnico_ids` de
  // verdade) — mantido na assinatura porque entra na query key do React
  // Query, pra não servir cache de um usuário pra outro.
  userId: number,
): Promise<{
  os: OsTecnicoSummary
  collect_items: ColetaItemDetail[]
  open_relatorio_id: number | null
  equipments: Record<number, EquipmentInfo>
  instruments: Record<number, InstrumentInfo>
}> {
  const [os] = await odooClient.searchRead<OsTecnicoSummary>(
    'afr.qualificacao.os',
    [['id', '=', osId]],
    OS_FIELDS,
  )
  const collect_items = await odooClient.searchRead<ColetaItemDetail>(
    'afr.qualificacao.collect.item',
    [['os_id', '=', osId]],
    [
      'name', 'kind', 'required', 'state', 'description', 'instruction',
      'requires_instrument', 'docx_section', 'qualif_id', 'cycle_id',
      'malha_id', 'equipment_id', 'standard_instrument_ids',
      'file', 'filename', 'mimetype',
      'captured_at', 'captured_by',
    ],
  )
  // Quem resolve "o relatório do dia" é o servidor (relógio + fuso do
  // usuário Odoo), não o front — ver `action_get_daily_relatorio` no backend.
  const openRelId: number | false = await odooClient.callKw(
    'afr.qualificacao.os',
    'action_get_daily_relatorio',
    [[osId]],
  )
  const equipmentIds = Array.from(
    new Set(
      collect_items
        .map((i) => (i.equipment_id ? i.equipment_id[0] : null))
        .filter((v): v is number => v !== null),
    ),
  )
  let equipments: Record<number, EquipmentInfo> = {}
  if (equipmentIds.length > 0) {
    const eqRecords = await odooClient.searchRead<EquipmentInfo>(
      'engc.equipment',
      [['id', 'in', equipmentIds]],
      ['name', 'apelido', 'tag', 'model', 'serial_number', 'marca_id'],
    )
    equipments = Object.fromEntries(eqRecords.map((e) => [e.id, e]))
  }
  const instrumentIds = Array.from(
    new Set(collect_items.flatMap((i) => i.standard_instrument_ids ?? [])),
  )
  let instruments: Record<number, InstrumentInfo> = {}
  if (instrumentIds.length > 0) {
    const records = await odooClient.searchRead<InstrumentInfo>(
      'engc.calibration.instruments',
      [['id', 'in', instrumentIds]],
      ['name', 'tag', 'id_number', 'marca', 'modelo', 'has_valid_certificate'],
    )
    instruments = Object.fromEntries(records.map((r) => [r.id, r]))
  }
  return {
    os,
    collect_items,
    open_relatorio_id: openRelId || null,
    equipments,
    instruments,
  }
}

function todayRangeOdoo(): { from: string; to: string } {
  const t = new Date()
  t.setHours(0, 0, 0, 0)
  const tomorrow = new Date(t.getTime() + 86400000)
  return { from: toOdooDatetime(t), to: toOdooDatetime(tomorrow) }
}

export async function listRelatoriosFechados(
  userId: number,
  limit = 50,
): Promise<RelatorioHistorico[]> {
  return odooClient.searchRead<RelatorioHistorico>(
    'afr.qualificacao.os.relatorio',
    [
      ['state', '=', 'done'],
      ['create_uid', '=', userId],
    ],
    [
      'name', 'os_id', 'state', 'data_inicio', 'data_fim',
      'signature_technician_date', 'time_execution',
      'pending_collect_count', 'collect_item_ids',
    ],
    { limit, order: 'data_fim desc, id desc' },
  )
}

export async function getHistoricoSummary(userId: number): Promise<HistoricoSummary> {
  const { from, to } = todayRangeOdoo()
  const items = await odooClient.searchRead<{ os_id: [number, string] | false }>(
    'afr.qualificacao.collect.item',
    [
      ['captured_by', '=', userId],
      ['captured_at', '>=', from],
      ['captured_at', '<', to],
    ],
    ['os_id'],
  )
  const hoje_coletas = items.length
  const hoje_oss = new Set(items.map((i) => (i.os_id ? i.os_id[0] : 0)).filter(Boolean)).size
  const hoje_relatorios_fechados = await odooClient.searchCount(
    'afr.qualificacao.os.relatorio',
    [
      ['state', '=', 'done'],
      ['create_uid', '=', userId],
      ['signature_technician_date', '>=', from],
      ['signature_technician_date', '<', to],
    ],
  )
  return { hoje_coletas, hoje_oss, hoje_relatorios_fechados }
}

export async function getRelatorioDetail(relId: number): Promise<RelatorioFullDetail> {
  const [relatorio] = await odooClient.searchRead<RelatorioDetail>(
    'afr.qualificacao.os.relatorio',
    [['id', '=', relId]],
    [
      'name', 'os_id', 'state', 'data_inicio', 'data_fim',
      'signature_technician_date', 'time_execution',
      'pending_collect_count', 'descricao', 'signature_technician',
      'collect_item_ids',
    ],
  )
  if (!relatorio) {
    throw new Error(`Relatório ${relId} não encontrado`)
  }
  const collect_items = await odooClient.searchRead<ColetaItemDetail>(
    'afr.qualificacao.collect.item',
    [['relatorio_id', '=', relId]],
    [
      'name', 'kind', 'required', 'state', 'description', 'instruction',
      'requires_instrument', 'docx_section', 'qualif_id', 'cycle_id',
      'malha_id', 'equipment_id', 'standard_instrument_ids',
      'file', 'filename', 'mimetype',
      'captured_at', 'captured_by',
    ],
    { order: 'captured_at desc, id desc' },
  )
  return { relatorio, collect_items }
}

export async function startDailyRelatorio(osId: number): Promise<number> {
  // Sem day_start/day_end: quem decide a janela do dia é o servidor (fuso
  // do usuário Odoo + relógio do servidor), não o relógio do dispositivo —
  // ver `action_get_daily_relatorio`/`_janela_do_dia` no backend.
  return odooClient.callKw(
    'afr.qualificacao.os',
    'action_start_daily_relatorio',
    [[osId]],
  )
}

export interface CollectItemPayload {
  file_b64?: string
  filename?: string
  mimetype?: string
  description?: string
  standard_instrument_ids?: number[]
  relatorio_id: number
  state?: 'collected' | 'skipped'
}

export async function collectItem(itemId: number, payload: CollectItemPayload): Promise<void> {
  const vals: Record<string, unknown> = {
    relatorio_id: payload.relatorio_id,
    state: payload.state ?? 'collected',
  }
  if (payload.file_b64) {
    vals.file = payload.file_b64
    vals.filename = payload.filename
    vals.mimetype = payload.mimetype
  }
  if (payload.description !== undefined) {
    vals.description = payload.description
  }
  if (payload.standard_instrument_ids !== undefined) {
    vals.standard_instrument_ids = [[6, 0, payload.standard_instrument_ids]]
  }
  await odooClient.write('afr.qualificacao.collect.item', [itemId], vals)
}

export interface FinalizeRelatorioPayload {
  descricao: string
  signature_b64: string
}

export async function finalizeRelatorio(
  relId: number,
  payload: FinalizeRelatorioPayload,
): Promise<void> {
  const now = toOdooDatetime(new Date())
  // 1º RPC: grava o conteúdo. `data_fim` precisa estar persistido antes do
  // action_done, porque `time_execution` é stored/computed e o gate exige > 0.
  await odooClient.write('afr.qualificacao.os.relatorio', [relId], {
    data_fim: now,
    descricao: payload.descricao,
    signature_technician: payload.signature_b64,
    signature_technician_date: now,
  })
  // 2º RPC: transição oficial (valida descrição, tempo > 0 e técnicos).
  // Nunca escrever state='done' direto — pularia essas validações.
  await odooClient.callKw('afr.qualificacao.os.relatorio', 'action_done', [[relId]])
}
