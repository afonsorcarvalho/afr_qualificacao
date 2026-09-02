import odooClient from './client'
import { useSchemaStore, type FieldMeta, type AccessRights } from '../store/schemaStore'

/**
 * Models usados pela aplicação. Pré-carregados no login.
 * Adicione novos models aqui quando a UI passar a consumi-los.
 */
export const APP_MODELS = [
  'res.partner',
  'res.country',
  'res.partner.category',
  'afr.supervisorio.ciclos',
  'afr.supervisorio.cycle.materials.lines',
  'afr.indicador.biologico',
  'afr.ciclo.fotos',
  'afr.supervisorio.materials',
  'engc.equipment',
  'afr.cycle.type',
  'ir.actions.report',
  // OS
  'engc.os',
  'engc.os.verify.checklist',
  'engc.os.relatorios',
  'engc.os.request.parts',
  'product.product',
  'hr.employee',
  'hr.department',
] as const

type Operation = 'read' | 'write' | 'create' | 'unlink'
const OPERATIONS: Operation[] = ['read', 'write', 'create', 'unlink']

/**
 * Carrega `fields_get` + `check_access_rights` de um único model e grava no store.
 * Tolera falhas individuais — se o user não tem read, grava access=false e fields={}.
 */
export async function loadModelSchema(model: string): Promise<void> {
  let fields: Record<string, FieldMeta> = {}
  let access: AccessRights = { read: false, write: false, create: false, unlink: false }

  // 1) Access rights — pode ser negado em qualquer operação sem erro
  const checks = await Promise.all(
    OPERATIONS.map(async (op) => {
      try {
        const ok = await odooClient.callKw<boolean>(
          model, 'check_access_rights', [op], { raise_exception: false }
        )
        return [op, Boolean(ok)] as const
      } catch {
        return [op, false] as const
      }
    })
  )
  access = Object.fromEntries(checks) as unknown as AccessRights

  // 2) fields_get — só se tivermos read
  if (access.read) {
    try {
      fields = await odooClient.callKw<Record<string, FieldMeta>>(
        model, 'fields_get', [],
        { attributes: ['string', 'type', 'required', 'readonly', 'selection', 'relation'] }
      )
    } catch {
      fields = {}
    }
  }

  useSchemaStore.getState().setModel(model, fields, access)
}

const SCHEMA_TTL_MS = 24 * 60 * 60 * 1000

/**
 * Carrega em paralelo os schemas de todos os models usados pela app.
 * Pula models já carregados (store persistido) dentro da TTL.
 * Tolera falhas individuais; retorna contador de sucesso/falha para diagnóstico.
 */
export async function preloadSchemas(): Promise<{ ok: number; failed: number; skipped: number }> {
  const state = useSchemaStore.getState()
  const fresh = Date.now() - state.loadedAt < SCHEMA_TTL_MS
  const pending = APP_MODELS.filter((m) => !fresh || !state.isLoaded(m))
  const skipped = APP_MODELS.length - pending.length
  if (pending.length === 0) return { ok: 0, failed: 0, skipped }
  const results = await Promise.allSettled(pending.map((m) => loadModelSchema(m)))
  const ok = results.filter((r) => r.status === 'fulfilled').length
  const failed = results.length - ok
  return { ok, failed, skipped }
}
