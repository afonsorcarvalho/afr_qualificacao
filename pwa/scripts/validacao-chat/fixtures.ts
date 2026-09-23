// scripts/validacao-chat/fixtures.ts
// As dez fixtures da "Validação empírica antes de fechar o modelo"
// (docs/superpowers/specs/2026-09-20-chat-agendamento-design.md).
//
// As expectativas são PRÉ-REGISTRADAS de propósito: pontuar depois de ver a
// resposta convida a racionalizar ("listar_os também serviria aqui"). Quem
// mudar uma expectativa depois de rodar tem que dizer por quê no relatório.

/**
 * Segunda-feira, e deliberadamente DIFERENTE do hoje real da máquina — é
 * assim que "derivou do server_today" se distingue de "deduziu do relógio".
 * Sobrescrevível por env para reproduzir um defeito numa data específica
 * (o do item 1 do TODO foi observado com hoje = 2026-09-21).
 */
export const SERVER_TODAY = process.env.SERVER_TODAY ?? '2026-09-14'

/**
 * A janela que a tela da agenda estaria mostrando sob `SERVER_TODAY` —
 * semana corrente, segunda a domingo (convenção do app).
 */
export const JANELA_NA_TELA = {
  from: process.env.JANELA_FROM ?? '2026-09-14',
  to: process.env.JANELA_TO ?? '2026-09-20',
}

export type Grupo =
  /** Capacidade central: escolha de ferramenta, ids, encadeamento. */
  | 'nucleo'
  /** Depende de como o prompt define o início da semana — item 1 do TODO. */
  | 'semana-relativa'

export interface Fixture {
  id: string
  grupo: Grupo
  /** Pedido em pt-BR coloquial, como o gestor escreveria. */
  pedido: string
  /** Ferramenta esperada na PRIMEIRA chamada do turno. `null` = nenhuma (texto). */
  ferramentaEsperada: string | null
  /**
   * Datas ISO que só existem se o modelo derivou de `SERVER_TODAY`.
   * Vazio = a fixture não pontua o critério de data.
   */
  datasEsperadas?: string[]
  /**
   * Datas que denunciam dedução pelo relógio real (hoje = 2026-09-21) em vez
   * do `server_today` injetado.
   */
  datasDeDeducao?: string[]
  /** Espera-se que o turno termine em proposta de escrita. */
  esperaProposta?: boolean
  /** Espera-se pergunta de desambiguação, e NUNCA uma escrita. */
  esperaPergunta?: boolean
  /** Espera-se pelo menos duas chamadas, a segunda usando a primeira. */
  esperaEncadeamento?: boolean
  /** O que esta fixture existe para provar. */
  proposito: string
}

export const FIXTURES: Fixture[] = [
  {
    id: 'F01',
    grupo: 'nucleo',
    pedido: 'me mostra a agenda de amanhã',
    ferramentaEsperada: 'buscar_agenda',
    datasEsperadas: ['2026-09-15'],
    datasDeDeducao: ['2026-09-22'],
    proposito:
      'O caso mais simples de data absoluta: "amanhã" só vira 15/09 se o modelo partiu do server_today injetado.',
  },
  {
    id: 'F02',
    grupo: 'nucleo',
    pedido: 'quais técnicos a gente tem?',
    ferramentaEsperada: 'listar_tecnicos',
    proposito:
      'Ferramenta de consulta pura, sem data nem id. Se falhar aqui, o parser de tool call da stack de serving é o problema, não o prompt.',
  },
  {
    id: 'F03',
    grupo: 'nucleo',
    pedido: 'lista pra mim as OS que dá pra agendar',
    ferramentaEsperada: 'listar_os',
    proposito: 'Escolha entre duas ferramentas de listagem parecidas (OS x técnicos).',
  },
  {
    id: 'F04',
    grupo: 'semana-relativa',
    pedido: 'como tá a agenda da semana que vem?',
    ferramentaEsperada: 'buscar_agenda',
    datasEsperadas: ['2026-09-21', '2026-09-27'],
    datasDeDeducao: ['2026-09-20', '2026-09-26', '2026-09-28', '2026-10-04'],
    proposito:
      'O defeito já conhecido do item 1 do TODO: o modelo tende a segunda-a-domingo errado (dom–sáb). Falha aqui é RE-OBSERVAÇÃO, não achado novo.',
  },
  {
    id: 'F04b',
    grupo: 'semana-relativa',
    pedido: 'como tá a agenda da semana que vem?',
    ferramentaEsperada: 'buscar_agenda',
    // Fixada para SERVER_TODAY=2026-09-21, a data em que o defeito aparecia.
    // A F04 acima roda na data padrão (2026-09-14); esta existe para o GATE,
    // e por isso só faz sentido com `SERVER_TODAY=2026-09-21` — rodá-la na
    // data padrão reprova de propósito, em vez de enganar.
    datasEsperadas: ['2026-09-28', '2026-10-04'],
    // As duas janelas erradas OBSERVADAS, não hipotéticas: 22/09–28/09
    // (terça a segunda) e 27/09–03/10 (domingo a sábado).
    datasDeDeducao: ['2026-09-22', '2026-09-27', '2026-10-03'],
    proposito:
      'Gate de regressão do defeito da semana. Roda com SERVER_TODAY=2026-09-21, cinco vezes: com o defeito intacto, UMA execução tinha ~1/3 de chance de passar.',
  },
  {
    id: 'F05',
    grupo: 'nucleo',
    pedido: 'agenda a QOS00011 pro Bruno na quarta-feira',
    ferramentaEsperada: 'listar_os',
    datasEsperadas: ['2026-09-16'],
    datasDeDeducao: ['2026-09-23'],
    esperaProposta: true,
    esperaEncadeamento: true,
    proposito:
      'Caminho completo de escrita: consultar OS e técnico, pegar equipamento/instrumento do resultado, e só então propor. Nenhum id pode ser inventado.',
  },
  {
    id: 'F06',
    grupo: 'nucleo',
    pedido: 'quantas horas a QOS00013 precisa? cabe num dia só?',
    ferramentaEsperada: 'listar_os',
    proposito:
      'Usa horas_previstas/jornada_horas_dia do resultado da ferramenta — o campo novo do pwa_os_options — para responder em texto.',
  },
  {
    id: 'F07',
    grupo: 'nucleo',
    pedido: 'tem alguma visita do Paulo essa semana?',
    ferramentaEsperada: 'buscar_agenda',
    datasEsperadas: ['2026-09-14', '2026-09-20'],
    datasDeDeducao: ['2026-09-21', '2026-09-27'],
    proposito:
      'Filtro por pessoa sobre resultado de ferramenta, e a regra de citar visita por OS+data na prosa (nunca pelo id interno).',
  },
  {
    id: 'F08',
    grupo: 'nucleo',
    pedido: 'remarca a visita do hospital pra sexta',
    ferramentaEsperada: 'buscar_agenda',
    esperaPergunta: true,
    proposito:
      'AMBIGUIDADE: há várias visitas do UITest Hospital. O modelo deve perguntar qual, e nunca escolher sozinho nem gravar.',
  },
  {
    id: 'F09',
    grupo: 'nucleo',
    pedido: 'cancela a visita 999',
    ferramentaEsperada: null,
    proposito:
      'Trava de id: 999 nunca apareceu em resultado nenhum. O esperado é o modelo consultar ou avisar — jamais uma escrita com id inventado passando.',
  },
  {
    id: 'F10',
    grupo: 'semana-relativa',
    pedido: 'na segunda que vem quem tá disponível?',
    ferramentaEsperada: 'buscar_agenda',
    datasEsperadas: ['2026-09-21'],
    datasDeDeducao: ['2026-09-28'],
    proposito:
      'Dia nomeado dentro da semana seguinte — separa "erra a semana inteira" (F04) de "erra só a borda".',
  },
]
