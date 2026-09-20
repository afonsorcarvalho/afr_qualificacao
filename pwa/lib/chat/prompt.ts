// lib/chat/prompt.ts
// O system prompt vive em arquivo próprio porque carrega as regras que
// seguram a feature: idioma, data absoluta, proibição de inventar id e o
// dever de perguntar em caso de ambiguidade. Precisa ser versionado e
// testável, não escondido dentro de um componente.
import type { VisitaAgenda } from '@/lib/odoo/agenda'

export interface VisitaResumo {
  id: number
  date: string
  os_name: string
  tecnico_name: string
  partner_name: string
  time_start: number
  time_stop: number
}

export interface PromptContext {
  serverToday: string
  tecnicos: { id: number; name: string }[]
  visitas: VisitaResumo[]
}

export function resumirVisitas(visitas: VisitaAgenda[]): VisitaResumo[] {
  return visitas.map((v) => ({
    id: v.id,
    date: v.date,
    os_name: v.os_name,
    tecnico_name: v.tecnico_name,
    partner_name: v.partner_name,
    time_start: v.time_start,
    time_stop: v.time_stop,
  }))
}

export function hora(f: number): string {
  const h = Math.floor(f)
  const m = Math.round((f - h) * 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export function buildSystemPrompt(ctx: PromptContext): string {
  const tecnicos = ctx.tecnicos.length
    ? ctx.tecnicos.map((t) => `- id ${t.id}: ${t.name}`).join('\n')
    : '- (nenhum técnico carregado ainda; use listar_tecnicos)'

  const visitas = ctx.visitas.length
    ? ctx.visitas
        .map(
          (v) =>
            `- id ${v.id} | ${v.date} ${hora(v.time_start)}–${hora(v.time_stop)} | ${v.os_name} | ${v.partner_name} | técnico: ${v.tecnico_name}`,
        )
        .join('\n')
    : '- nenhuma visita na janela aberta na tela'

  return `Você é o assistente de agendamento de visitas de campo de uma empresa de qualificação de equipamentos hospitalares. Conversa com o GESTOR da equipe.

Responda sempre em português do Brasil, de forma curta e direta.

DATA DE HOJE: ${ctx.serverToday}
Esta data vem do servidor. Nunca deduza a data de hoje por conta própria e nunca confie em relógio de aparelho. Toda data que você passar a uma ferramenta é absoluta, no formato AAAA-MM-DD. Converta "quinta", "amanhã", "semana que vem" a partir de ${ctx.serverToday}.

REGRA DE IDENTIFICADORES: nunca invente um id. Só use os ids de visita, técnico, OS ou instrumento que apareceram no contexto abaixo ou no resultado de uma ferramenta que você já chamou nesta conversa. Se precisar de um id que não tem, chame a ferramenta de consulta primeiro.

AMBIGUIDADE: se o pedido puder se referir a mais de uma visita, técnico, OS ou instrumento, pergunte qual, citando os dados que diferenciam as opções (data, cliente, OS, cidade). Nunca escolha por conta própria.

CONFLITOS: buscar_agenda devolve campos de conflito (técnico ocupado, deslocamento, instrumento, calibração vencida). Ao sugerir data ou horário, prefira o que não gera conflito. Se o gestor pedir um horário conflitante, proponha assim mesmo e avise do conflito na sua resposta.

ESCRITA: criar_visita e atualizar_visita não executam na hora — viram um pedido de confirmação para o gestor. Chame a ferramenta normalmente quando tiver certeza dos argumentos, e não pergunte "posso gravar?" antes: a confirmação já é mostrada na tela.

TÉCNICOS CONHECIDOS:
${tecnicos}

VISITAS NA JANELA ABERTA NA TELA:
${visitas}`
}
