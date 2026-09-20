// lib/chat/tools.ts
// Dispatch das ferramentas do chat. Cada uma cai numa função que já existe
// em `lib/odoo/agenda.ts`, portanto numa RPC `pwa_*` com ACL, whitelist de
// campos e trava de estado da OS. Nenhum caminho de escrita novo.
import {
  fetchAgenda,
  updateVisita,
  createVisita,
  listTecnicoOptions,
  listOsOptions,
  listInstrumentoOptions,
  type VisitaVals,
} from '@/lib/odoo/agenda'

export class ToolNotFoundError extends Error {
  constructor(name: string) {
    super(`Ferramenta desconhecida: ${name}`)
    this.name = 'ToolNotFoundError'
  }
}

/** Espelha `_PWA_WRITABLE_FIELDS` do servidor. Chave fora disto é descartada. */
const CAMPOS_GRAVAVEIS = [
  'date', 'time_start', 'time_stop', 'tecnico_id', 'note', 'instrument_ids',
] as const

function montarVals(args: Record<string, unknown>): VisitaVals {
  const vals: Record<string, unknown> = {}
  for (const campo of CAMPOS_GRAVAVEIS) {
    if (args[campo] !== undefined) vals[campo] = args[campo]
  }
  return vals as VisitaVals
}

export async function runTool(
  name: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  switch (name) {
    case 'buscar_agenda':
      // `only_mine` é sempre false: o chat é do Gestor, que enxerga a
      // equipe inteira. A ACL do servidor continua decidindo o que volta.
      return fetchAgenda(
        String(args.date_from ?? ''),
        String(args.date_to ?? ''),
        false,
      )
    case 'listar_tecnicos':
      return listTecnicoOptions()
    case 'listar_os':
      return listOsOptions()
    case 'listar_instrumentos':
      return listInstrumentoOptions()
    case 'criar_visita':
      return createVisita(
        Number(args.os_id),
        Number(args.tecnico_id),
        String(args.date),
      )
    case 'atualizar_visita':
      return updateVisita(Number(args.visita_id), montarVals(args))
    default:
      throw new ToolNotFoundError(name)
  }
}
