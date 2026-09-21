// lib/chat/toolDefs.ts
// Só os schemas. Nenhum import de `lib/odoo` pode entrar aqui: a rota
// `/api/chat` importa este arquivo, e a fronteira "o servidor não fala com
// o Odoo" é testada. O dispatch mora em `lib/chat/tools.ts`.
import type { LlmToolDef } from '@/lib/llm/client'

const DATA = 'Data absoluta no formato AAAA-MM-DD. Nunca use datas relativas.'

export const TOOL_DEFS: LlmToolDef[] = [
  {
    type: 'function',
    function: {
      name: 'buscar_agenda',
      description:
        'Lista as visitas de campo agendadas numa janela de datas. Use antes de propor qualquer alteração, para descobrir o id da visita.',
      parameters: {
        type: 'object',
        properties: {
          date_from: { type: 'string', description: `Início da janela. ${DATA}` },
          date_to: { type: 'string', description: `Fim da janela. ${DATA}` },
        },
        required: ['date_from', 'date_to'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'listar_tecnicos',
      description:
        'Lista os técnicos disponíveis, com id e nome. Use para converter um nome dito pelo gestor no id correspondente.',
      parameters: { type: 'object', properties: {} },
    },
  },
  {
    type: 'function',
    function: {
      name: 'listar_instrumentos',
      description:
        'Lista os instrumentos de medição disponíveis, com id, tag e validade de calibração.',
      parameters: { type: 'object', properties: {} },
    },
  },
  {
    type: 'function',
    function: {
      name: 'listar_os',
      description:
        'Lista as ordens de serviço de qualificação que aceitam visita nova (rascunho ou agendada). Cada OS já vem com os equipamentos vinculados (equipment_list) e, quando o plano de recursos da OS já foi calculado, os instrumentos sugeridos (instrument_suggestions) — ambos com id e rótulo legível. Uma OS sem instrument_suggestions é normal (plano ainda não calculado); nesse caso use listar_instrumentos para escolher manualmente.',
      parameters: { type: 'object', properties: {} },
    },
  },
  {
    type: 'function',
    function: {
      name: 'criar_visita',
      description:
        'Cria uma visita nova para uma OS, com técnico, data, equipamentos e instrumentos — os quatro são obrigatórios. Esta ação grava: será mostrada ao gestor para confirmação antes de executar. O servidor pode recusar a OS se seu estado não permitir novas visitas; comunique o erro ao gestor em vez de tentar novamente.',
      parameters: {
        type: 'object',
        properties: {
          os_id: { type: 'integer', description: 'Id da OS, vindo de listar_os.' },
          tecnico_id: { type: 'integer', description: 'Id do técnico, vindo de listar_tecnicos.' },
          date: { type: 'string', description: `Data da visita. ${DATA}` },
          equipment_ids: {
            type: 'array',
            items: { type: 'integer' },
            description: 'Obrigatório, não pode ser vazio. Ids dos equipamentos da visita — tire do campo equipment_list da própria OS em listar_os (são os equipamentos vinculados a ela).',
          },
          instrument_ids: {
            type: 'array',
            items: { type: 'integer' },
            description: 'Obrigatório, não pode ser vazio. Ids dos instrumentos da visita — prefira instrument_suggestions da OS em listar_os quando a lista não vier vazia; se vier vazia (plano de recursos ainda não calculado), escolha em listar_instrumentos.',
          },
        },
        required: ['os_id', 'tecnico_id', 'date', 'equipment_ids', 'instrument_ids'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'atualizar_visita',
      description:
        'Altera uma visita existente: data, horário, técnico, instrumentos ou observação. Informe apenas os campos que mudam. Esta ação grava: será mostrada ao gestor para confirmação antes de executar.',
      parameters: {
        type: 'object',
        properties: {
          visita_id: { type: 'integer', description: 'Id da visita, vindo de buscar_agenda.' },
          date: { type: 'string', description: `Nova data. ${DATA}` },
          time_start: { type: 'number', description: 'Hora de início como float, ex.: 8.5 para 08:30.' },
          time_stop: { type: 'number', description: 'Hora de fim como float, ex.: 17.0 para 17:00.' },
          tecnico_id: { type: 'integer', description: 'Id do novo técnico, vindo de listar_tecnicos.' },
          note: { type: 'string', description: 'Observação da visita.' },
          instrument_ids: {
            type: 'array',
            items: { type: 'integer' },
            description: 'Lista completa de ids de instrumentos da visita; substitui a anterior.',
          },
        },
        required: ['visita_id'],
      },
    },
  },
]

export const TOOL_KINDS: Record<string, 'read' | 'write'> = {
  buscar_agenda: 'read',
  listar_tecnicos: 'read',
  listar_instrumentos: 'read',
  listar_os: 'read',
  criar_visita: 'write',
  atualizar_visita: 'write',
}

export const WRITE_TOOLS = ['criar_visita', 'atualizar_visita'] as const

export function isWriteTool(name: string): boolean {
  return TOOL_KINDS[name] === 'write'
}
