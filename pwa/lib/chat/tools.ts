// lib/chat/tools.ts
// Dispatch das ferramentas do chat. Cada uma cai numa função que já existe
// em `lib/odoo/agenda.ts`, portanto numa RPC `pwa_*` com ACL, whitelist de
// campos e trava de estado da OS. Nenhum caminho de escrita novo.
import {
  fetchAgenda,
  updateVisita,
  createVisita,
  listTecnicoOptions,
  fetchOsOptions,
  listInstrumentoOptions,
  type VisitaVals,
  type VisitaAgenda,
  type AgendaPayload,
} from '@/lib/odoo/agenda'
import { formatarDataHumana } from './card'
import { horaOdoo } from '@/app/tecnico/qualificacao/_components/VisitaCard'

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

/**
 * Visita com um rótulo pronto pra prosa do modelo — ver regra "IDENTIFICAÇÃO
 * NA PROSA" em `prompt.ts`. Estende `VisitaAgenda` (não substitui nenhum
 * campo: `id`, `os_name`, `date` etc. continuam onde estavam) porque a
 * máquina (`machine.ts`, trava de id) e o card de confirmação (`card.ts`)
 * dependem do formato original.
 */
export interface VisitaComRotulo extends VisitaAgenda {
  rotulo: string
}

export interface AgendaPayloadComRotulo extends Omit<AgendaPayload, 'visitas'> {
  visitas: VisitaComRotulo[]
}

/**
 * "OS26-08-0005 · qua, 23/09/2026 · Bruno Neves 08:00–12:00" — o texto que o
 * modelo deve citar na prosa pro gestor em vez do id interno. Caso real que
 * motivou isto: duas visitas da MESMA OS no MESMO dia, do MESMO técnico,
 * diferenciadas só pelo horário (ver relatório da task). Por isso o rótulo
 * sempre carrega técnico + horário, não só quando "parece" necessário —
 * mais simples e nunca sub-desambigua.
 */
function montarRotulo(v: VisitaAgenda): string {
  const data = formatarDataHumana(v.date)
  const horario = `${horaOdoo(v.time_start)}–${horaOdoo(v.time_stop)}`
  const tecnico = v.tecnico_name ? `${v.tecnico_name} ${horario}` : horario
  // Mesmo padrão condicional do técnico acima: `os_id` é tipado
  // `number | false` (ver `lib/odoo/agenda.ts`) — uma visita sem OS
  // vinculada chega com `os_name` vazio. Sem este guard o rótulo começava
  // com `" · qua, ..."`, separador solto — o mesmo defeito que o card já
  // evita do outro lado da tela (ver `juntarSubtitulo` em `card.ts`).
  const os = v.os_name ? v.os_name : 'sem OS'
  return `${os} · ${data} · ${tecnico}`
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

/**
 * Valida uma lista de ids OBRIGATÓRIA e não-vazia para `criar_visita`
 * (equipment_ids/instrument_ids) — ao contrário de `instrument_ids` em
 * `atualizar_visita`, que é opcional e aceita lista vazia (desliga todos).
 * `ondeAchar` vai na mensagem porque quem lê o erro é o MODELO, não o
 * gestor: ele precisa saber que ferramenta chamar a seguir, não só que
 * errou.
 */
function paraListaDeIdsObrigatoria(
  ferramenta: string,
  campo: string,
  valor: unknown,
  ondeAchar: string,
): number[] {
  if (!Array.isArray(valor) || valor.length === 0) {
    throw new ToolArgumentError(
      `${ferramenta}: "${campo}" é obrigatório e não pode ser vazio — ${ondeAchar}.`,
    )
  }
  return valor.map((id) => {
    const num = Number(id)
    if (!Number.isFinite(num)) {
      throw new ToolArgumentError(
        `${ferramenta}: "${campo}" contém um valor inválido: "${id}"`,
      )
    }
    return num
  })
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
      const payload = await fetchAgenda(dateFrom, dateTo, false)
      const comRotulo: AgendaPayloadComRotulo = {
        ...payload,
        visitas: payload.visitas.map((v) => ({ ...v, rotulo: montarRotulo(v) })),
      }
      return comRotulo
    }
    case 'listar_tecnicos':
      return listTecnicoOptions()
    case 'listar_os':
      return fetchOsOptions()
    case 'listar_instrumentos':
      return listInstrumentoOptions()
    case 'criar_visita': {
      const osId = Number(args.os_id)
      const tecnicoId = Number(args.tecnico_id)
      const date = String(args.date ?? '').trim()

      if (!Number.isFinite(osId)) {
        throw new ToolArgumentError(
          `criar_visita: "os_id" precisa ser um número inteiro, vindo de listar_os; recebi "${args.os_id}"`,
        )
      }
      if (!Number.isFinite(tecnicoId)) {
        throw new ToolArgumentError(
          `criar_visita: "tecnico_id" precisa ser um número inteiro, vindo de listar_tecnicos; recebi "${args.tecnico_id}"`,
        )
      }
      if (!date) {
        throw new ToolArgumentError(
          'criar_visita: "date" é obrigatório; recebi vazio ou ausente',
        )
      }

      // Trava dos dentes (não depender só do prompt): toda visita criada
      // pelo chat precisa sair com técnico, equipamento(s) e instrumento(s)
      // — ao contrário da folha manual, que o servidor deixa criar sem
      // nenhum dos dois (`pwa_visita_create` continua permissivo).
      const equipmentIds = paraListaDeIdsObrigatoria(
        'criar_visita', 'equipment_ids', args.equipment_ids,
        'tire do campo equipment_list da OS em listar_os',
      )
      const instrumentIds = paraListaDeIdsObrigatoria(
        'criar_visita', 'instrument_ids', args.instrument_ids,
        'use instrument_suggestions da OS em listar_os quando houver, senão escolha em listar_instrumentos',
      )

      return createVisita(osId, tecnicoId, date, equipmentIds, instrumentIds)
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
