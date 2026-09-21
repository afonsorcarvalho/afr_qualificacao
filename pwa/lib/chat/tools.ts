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

export class ToolArgumentError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ToolArgumentError'
  }
}

/** Espelha `_PWA_WRITABLE_FIELDS` do servidor. Chave fora disto é descartada. */
const CAMPOS_GRAVAVEIS = [
  'date', 'time_start', 'time_stop', 'tecnico_id', 'note', 'instrument_ids',
] as const

function montarVals(args: Record<string, unknown>): VisitaVals {
  const vals: Record<string, unknown> = {}
  for (const campo of CAMPOS_GRAVAVEIS) {
    if (args[campo] === undefined) continue

    // Coerção de tipos para garantir shape correto de VisitaVals
    if (campo === 'date' || campo === 'note') {
      vals[campo] = String(args[campo])
    } else if (campo === 'time_start' || campo === 'time_stop') {
      // Float, não inteiro: 8.5 é 08:30. Mensagem errada aqui manda o
      // modelo truncar pra "8" e a visita grava com o horário errado —
      // silenciosamente, porque o código já aceita float corretamente e só
      // o texto do erro desviava. `tecnico_id` (abaixo) é o único inteiro
      // de fato deste bloco.
      const num = Number(args[campo])
      if (!Number.isFinite(num)) {
        throw new ToolArgumentError(
          `atualizar_visita: "${campo}" precisa ser um número (use fração para minutos: 8.5 = 08:30); recebi "${args[campo]}"`,
        )
      }
      vals[campo] = num
    } else if (campo === 'tecnico_id') {
      const num = Number(args[campo])
      if (!Number.isFinite(num)) {
        throw new ToolArgumentError(
          `atualizar_visita: "${campo}" precisa ser um número inteiro; recebi "${args[campo]}"`,
        )
      }
      vals[campo] = num
    } else if (campo === 'instrument_ids') {
      if (!Array.isArray(args[campo])) {
        throw new ToolArgumentError(
          `atualizar_visita: "instrument_ids" precisa ser uma lista; recebi "${typeof args[campo]}"`,
        )
      }
      vals[campo] = (args[campo] as unknown[]).map((id) => {
        const num = Number(id)
        if (!Number.isFinite(num)) {
          throw new ToolArgumentError(
            `atualizar_visita: "instrument_ids" contém um valor inválido: "${id}"`,
          )
        }
        return num
      })
    }
  }
  return vals as VisitaVals
}

export async function runTool(
  name: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  switch (name) {
    case 'buscar_agenda': {
      // `only_mine` é sempre false: o chat é do Gestor, que enxerga a
      // equipe inteira. A ACL do servidor continua decidindo o que volta.
      const dateFrom = String(args.date_from ?? '').trim()
      const dateTo = String(args.date_to ?? '').trim()
      if (!dateFrom) {
        throw new ToolArgumentError(
          'buscar_agenda: "date_from" é obrigatório; recebi vazio ou ausente',
        )
      }
      if (!dateTo) {
        throw new ToolArgumentError(
          'buscar_agenda: "date_to" é obrigatório; recebi vazio ou ausente',
        )
      }
      return fetchAgenda(dateFrom, dateTo, false)
    }
    case 'listar_tecnicos':
      return listTecnicoOptions()
    case 'listar_os':
      return listOsOptions()
    case 'listar_instrumentos':
      return listInstrumentoOptions()
    case 'criar_visita': {
      const osId = Number(args.os_id)
      const tecnicoId = Number(args.tecnico_id)
      const date = String(args.date ?? '').trim()

      if (!Number.isFinite(osId)) {
        throw new ToolArgumentError(
          `criar_visita: "os_id" precisa ser um número inteiro; recebi "${args.os_id}"`,
        )
      }
      if (!Number.isFinite(tecnicoId)) {
        throw new ToolArgumentError(
          `criar_visita: "tecnico_id" precisa ser um número inteiro; recebi "${args.tecnico_id}"`,
        )
      }
      if (!date) {
        throw new ToolArgumentError(
          'criar_visita: "date" é obrigatório; recebi vazio ou ausente',
        )
      }

      return createVisita(osId, tecnicoId, date)
    }
    case 'atualizar_visita': {
      const visitaId = Number(args.visita_id)
      if (!Number.isFinite(visitaId)) {
        throw new ToolArgumentError(
          `atualizar_visita: "visita_id" precisa ser um número inteiro; recebi "${args.visita_id}"`,
        )
      }

      const vals = montarVals(args)

      // Verifica se há algo para atualizar após filtrar a whitelist
      if (Object.keys(vals).length === 0) {
        throw new ToolArgumentError(
          'atualizar_visita: nenhum campo gravável foi fornecido',
        )
      }

      return updateVisita(visitaId, vals)
    }
    default:
      throw new ToolNotFoundError(name)
  }
}
