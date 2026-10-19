/**
 * Levantamento de campo — transporte RPC puro (model `afr.survey.op`).
 * Sem regra de negócio: o servidor valida; o offline/outbox mora em
 * `lib/levantamento`.
 */
import odooClient from './client'
import type { PushResponse, SurveyOp } from '../levantamento/engine'

export const SURVEY_MODEL = 'afr.survey.op'

export interface CatalogItem {
  id: number
  name: string
}
export interface SurveyCatalog {
  categories: CatalogItem[]
  marcas: CatalogItem[]
  cycle_types: CatalogItem[]
  /** Locais (company-scoped) para o seletor da ficha. */
  locations: CatalogItem[]
  selections: {
    load_type: [string, string][]
    thermocouple_access: [string, string][]
    survey_kind: [string, string][]
  }
}

export interface PartnerSummary {
  id: number
  name: string
  vat: string | false
  city: string | false
}
export interface PartnersPage {
  records: PartnerSummary[]
  total: number
}

/** `[id, display_name]` ou `false`, como o Odoo serializa many2one. */
export type M2o = [number, string] | false

export interface RemotePicture {
  id: number
  write_date?: string | false
  survey_kind: string
  cycle_id: number | false
  name: string | false
  thumb_b64: string | false
}
export interface RemoteCycle {
  id: number
  write_date: string | false
  cycle_type_id: M2o
  temperature: number
  duration: number
  load_type: string | false
  note: string | false
  pictures: RemotePicture[]
}
export interface RemoteEquipment {
  id: number
  write_date: string | false
  cycles: RemoteCycle[]
  /** Só fotos do equipamento; as de ciclo vêm em `cycles[].pictures`. */
  pictures: RemotePicture[]
  [campo: string]: unknown
}
export interface RemotePartnerData {
  partner: PartnerSummary
  equipments: RemoteEquipment[]
}

export const pullCatalog = () => odooClient.callKw<SurveyCatalog>(SURVEY_MODEL, 'survey_pull_catalog', [])

export const pullPartners = (query: string, offset = 0, limit = 50) =>
  odooClient.callKw<PartnersPage>(SURVEY_MODEL, 'survey_pull_partners', [query, offset, limit])

export const pullPartner = (id: number) =>
  odooClient.callKw<RemotePartnerData>(SURVEY_MODEL, 'survey_pull_partner', [id])

export const push = (ops: SurveyOp[]) =>
  odooClient.callKw<PushResponse>(SURVEY_MODEL, 'survey_push', [ops])

/**
 * O usuário logado pertence ao grupo `xmlid`? `res.users.has_group` é
 * `@api.model` no Odoo 16 e usa o uid da sessão, então é chamável via call_kw.
 */
export const hasGroup = (xmlid: string) =>
  odooClient.callKw<boolean>('res.users', 'has_group', [xmlid])
