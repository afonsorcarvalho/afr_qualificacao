/**
 * Grade mensal da agenda — funções puras, sem React e sem relógio local.
 *
 * Tudo aqui trabalha em cima de datas ISO (`YYYY-MM-DD`) e usa só
 * `Date.UTC`/`setUTCDate`/`getUTCDay`: nenhuma função lê `new Date()` sem
 * argumento nem o fuso local do aparelho, pelo mesmo motivo de `carga.ts` e
 * `janela.ts` — quem decide "hoje" é o servidor, o front só soma dias sobre
 * uma data que já veio pronta.
 */
import type { VisitaAgenda, Opcao, InstrumentoOpcao } from '@/lib/odoo/agenda'

// Escopo de MÓDULO: `String.prototype.localeCompare(..., locale, opts)`
// constrói um `Intl.Collator` novo por CHAMADA — dentro de um comparador de
// `sort`, isso é pago em cada uma das ~42 comparações de CADA agregação de
// `ordenarInstrumentos` por render (achado minor, review final). Um
// `Intl.Collator` construído uma vez e reusado via `.compare(a, b)` é a
// mesma otimização, só que explícita.
const COLATOR_PT_BR_NUMERICO = new Intl.Collator('pt-BR', { numeric: true })

export interface PontoTecnico {
  /** `false` = visita sem técnico atribuído. */
  id: number | false
  name: string // "Sem técnico" quando id === false
  cor: string
  visitas: number
}

export interface PontosDia {
  date: string
  pontos: PontoTecnico[]
  /** Soma das visitas do dia (≥ soma dos pontos quando um técnico tem duas). */
  total: number
  conflito: boolean
}

/** "2026-09-17" → "2026-09-01". Normaliza qualquer dia para o 1º do mês. */
export function primeiroDiaDoMes(iso: string): string {
  return `${iso.slice(0, 7)}-01`
}

/**
 * Soma `n` meses ao 1º do mês da âncora. `n` pode ser negativo. Sempre
 * devolve o dia 1 do mês resultante — nunca estoura para o mês seguinte
 * (o bug clássico de somar mês em cima de um dia 31, tipo
 * `new Date(2026, 0, 31).setMonth(1)` virar março). Construir o `Date.UTC`
 * já com dia 1 evita o estouro por completo: não existe "dia 31 de
 * fevereiro" pra transbordar.
 */
export function deslocarMes(iso: string, n: number): string {
  const [a, m] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(a, m - 1 + n, 1))
  return dt.toISOString().slice(0, 10)
}

/**
 * Grade de 6×7 = 42 dias ISO, começando no domingo anterior (ou igual) ao
 * dia 1 do mês da âncora. Sempre 42, mesmo quando o mês cabe em 5 semanas —
 * uma grade de tamanho variável faz a UI pular de altura ao trocar de mês;
 * mês curto sobra dia no fim, mês que atravessa 6 semanas (começa perto do
 * fim de uma semana e tem 31 dias) cabe sem cortar o último dia.
 */
export function gradeDoMes(iso: string): string[] {
  const primeiro = primeiroDiaDoMes(iso)
  const [a, m, d] = primeiro.split('-').map(Number)
  const diaSemana = new Date(Date.UTC(a, m - 1, d)).getUTCDay() // 0 = domingo
  const inicio = new Date(Date.UTC(a, m - 1, d - diaSemana))
  return Array.from({ length: 42 }, (_, i) => {
    const dt = new Date(inicio)
    dt.setUTCDate(dt.getUTCDate() + i)
    return dt.toISOString().slice(0, 10)
  })
}

/**
 * `true` se a data ISO pertence ao mês da âncora (para esmaecer as células
 * de fora sem escondê-las — a grade sempre mostra as pontas do mês
 * anterior/seguinte, é só a cor que muda).
 */
export function noMes(iso: string, ancora: string): boolean {
  return iso.slice(0, 7) === ancora.slice(0, 7)
}

/** "setembro de 2026", pt-BR, `timeZone: 'UTC'`. */
export function rotuloMes(iso: string): string {
  const [a, m] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(a, m - 1, 1))
  return new Intl.DateTimeFormat('pt-BR', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(dt)
}

// Paleta de 12 tons — cresceu de 8 no fix round 2 (achado 5): `corDoTecnico`
// indexa por `id % PALETA.length` com id de BANCO, então com 8 cores nove
// técnicos já colidiam garantido, e ids arbitrários colidiam bem antes (3 e
// 11 caíam na mesma). Dois chips iguais na legenda e dois pontinhos
// indistinguíveis na célula derrubam a única coisa que o modo Mês entrega:
// ver de relance DE QUEM é a visita.
//
// Nenhuma cor é livre: cada uma passa 3:1 (piso da WCAG 1.4.11 para
// elemento gráfico que carrega informação) sobre os QUATRO fundos em que um
// pontinho pode sentar — `--card` dos dois temas (célula comum) e
// `--primary` dos dois temas (célula do dia selecionado, que ganhou tinta
// sólida no achado 4, e que por default é justamente o dia de hoje). Isso
// descarta boa parte do catálogo do Tailwind: os tons claros somem sobre o
// cartão branco do tema claro, e os escuros somem sobre o `--primary` navy
// do mesmo tema — sobra uma faixa estreita de luminância, e é por isso que
// a paleta puxa para os matizes médios. Medido em `mes.test.ts`, que quebra
// se alguém trocar um tom por um mais bonito e menos legível.
//
// A ORDEM também é escolhida: os matizes não entram em roda-cromática, e sim
// intercalados (passo 5 sobre a roda), porque ids consecutivos são o caso
// comum num cadastro — e matizes vizinhos em índices vizinhos seriam
// justamente as duas cores parecidas na mesma célula.
export const PALETA: string[] = [
  '#db2777', // pink-600
  '#059669', // emerald-600
  '#8b5cf6', // violet-500
  '#ea580c', // orange-600
  '#0284c7', // sky-600
  '#f43f5e', // rose-500
  '#0d9488', // teal-600
  '#c026d3', // fuchsia-600
  '#16a34a', // green-600
  '#3b82f6', // blue-500
  '#dc2626', // red-600
  '#0891b2', // cyan-600
]

export const COR_SEM_TECNICO = '#6b7280' // gray-500

/**
 * Cor estável por id de técnico. `false` (visita sem técnico) devolve o
 * cinza neutro. A estabilidade é por id, não por posição no roster: o
 * roster muda de tamanho entre janelas (ver `rosterTecnicos` em
 * `carga.ts`) e cores que dançam a cada troca de mês mentem sobre quem é
 * quem na grade.
 */
export function corDoTecnico(id: number | false): string {
  if (id === false) return COR_SEM_TECNICO
  return PALETA[id % PALETA.length]
}

/**
 * Índice `data -> visitas do dia`, montado numa passada só. As agregações da
 * grade rodam sobre 42 dias; varrer a lista inteira de visitas dentro do laço
 * (`visitas.filter(v => v.date === date)`) custava 42×V comparações por
 * função, 84×V somando as duas — com o teto de 500 visitas do fetch, ~42 mil
 * comparações por render. É local a cada função de propósito: as assinaturas
 * públicas (com testes em cima) continuam recebendo `visitas` cru, e nenhuma
 * das duas passa a depender de um índice montado pelo chamador.
 */
function agruparPorData(visitas: VisitaAgenda[]): Map<string, VisitaAgenda[]> {
  const porData = new Map<string, VisitaAgenda[]>()
  for (const v of visitas) {
    const atual = porData.get(v.date)
    if (atual) atual.push(v)
    else porData.set(v.date, [v])
  }
  return porData
}

/**
 * Um item por técnico distinto com visita no dia, na ordem do roster (que
 * já vem ordenado por nome em `rosterTecnicos`), seguido do balde "sem
 * técnico" quando houver visita sem `tecnico_id`. Técnico do roster sem
 * visita no dia não vira ponto — a célula do mês só tem espaço pra quem
 * está de fato ali, ao contrário do painel de carga da semana que lista
 * todo mundo pra mostrar quem está livre.
 */
export function tecnicosPorDia(
  visitas: VisitaAgenda[],
  dias: string[],
  roster: Opcao[],
): PontosDia[] {
  const porData = agruparPorData(visitas)

  return dias.map((date) => {
    const doDia = porData.get(date) ?? []

    // Contagem por técnico numa passada, em vez de um `filter` do dia inteiro
    // por técnico do roster (roster×V_dia): a ORDEM continua sendo a do
    // roster, é só a contagem que deixou de varrer.
    const contagem = new Map<number | false, number>()
    for (const v of doDia) {
      contagem.set(v.tecnico_id, (contagem.get(v.tecnico_id) ?? 0) + 1)
    }

    const pontos: PontoTecnico[] = []
    for (const t of roster) {
      const visitasCount = contagem.get(t.id)
      if (!visitasCount) continue
      pontos.push({
        id: t.id,
        name: t.name,
        cor: corDoTecnico(t.id),
        visitas: visitasCount,
      })
    }

    const semTecnico = contagem.get(false) ?? 0
    if (semTecnico > 0) {
      pontos.push({
        id: false,
        name: 'Sem técnico',
        cor: COR_SEM_TECNICO,
        visitas: semTecnico,
      })
    }

    return {
      date,
      pontos,
      total: doDia.length,
      conflito: doDia.some((v) => v.conflict),
    }
  })
}

export interface PontoInstrumento {
  id: number
  /** Nome de `pwa_instrumento_options`; `Instrumento #<id>` quando o id não
   *  está nas opções — NUNCA pareado com `instrument_list`, que pode estar
   *  desalinhado com `instrument_ids` (ver cabeçalho de `instrumentosPorDia`). */
  name: string
  cor: string
  /** Quantas visitas do dia usam este instrumento. */
  visitas: number
}

export interface PontosInstrumentoDia {
  date: string
  instrumentos: PontoInstrumento[]
}

/**
 * Cor estável por id de instrumento, da mesma `PALETA` de `corDoTecnico`.
 * Técnico e instrumento podem cair na mesma cor — o que separa os dois
 * domínios na grade é a FORMA (bolinha x triângulo), não o matiz.
 */
export function corDoInstrumento(id: number): string {
  return PALETA[id % PALETA.length]
}

/**
 * ORDEM ÚNICA dos instrumentos, usada pela célula da grade E pela legenda.
 *
 * As duas metades da tela do Mês desenham o mesmo conjunto: se cada uma
 * ordenasse do seu jeito, a célula desenharia os triângulos numa sequência e
 * a legenda listaria noutra, e o leitor teria de casar por cor — que é
 * justamente o portador que a a11y proíbe usar sozinho. Pior: como a célula
 * CORTA a lista quando estoura o número de marcas (`_GradeMes`), a ordem
 * decide quais triângulos sobrevivem.
 *
 * Regra:
 * 1. Instrumentos conhecidos (id presente em `pwa_instrumento_options`)
 *    primeiro, por nome, com colação NUMÉRICA pt-BR — sem
 *    `{ numeric: true }`, "TAG-10" vem antes de "TAG-2" porque a comparação
 *    é caractere a caractere.
 * 2. Desconhecidos (`Instrumento #<id>`, instrumento arquivado ou sem
 *    permissão de leitura) por último, em id crescente. Um identificador
 *    fabricado não pode encabeçar a lista por ordem alfabética como se fosse
 *    um nome de cadastro.
 * 3. Empate de nome → id crescente, pra ordem nunca depender da ordem de
 *    chegada.
 */
export function ordenarInstrumentos<T extends { id: number; name: string }>(
  itens: T[],
  conhecidos: ReadonlySet<number>,
): T[] {
  return itens.slice().sort((a, b) => {
    const aConhecido = conhecidos.has(a.id)
    const bConhecido = conhecidos.has(b.id)
    if (aConhecido !== bConhecido) return aConhecido ? -1 : 1
    if (!aConhecido) return a.id - b.id
    const porNome = COLATOR_PT_BR_NUMERICO.compare(a.name, b.name)
    return porNome !== 0 ? porNome : a.id - b.id
  })
}

/**
 * Um item por instrumento distinto usado no dia, na ordem de
 * `ordenarInstrumentos` (nome com colação numérica; desconhecidos no fim por
 * id) — a MESMA ordem da legenda, montada pela página com a mesma função.
 *
 * Até o fix final a ordem era a de `opcoes` (o `order="tag, id_number, name"`
 * do servidor). Trocada de propósito: a legenda não recebe `opcoes` (ruling do
 * controlador: `_VistaMes` só vê dado já agregado), então "ordem do servidor"
 * era uma regra que só uma das duas metades conseguia aplicar.
 *
 * A contagem e o nome vêm de fontes diferentes de propósito: no servidor,
 * `instrument_list` é `list(filter(None, ...mapped('name')))`, então um
 * instrumento sem nome cadastrado some da lista mas permanece em
 * `instrument_ids` — os dois arrays podem ficar DESALINHADOS em tamanho e
 * posição. Pareando por índice, um instrumento roubaria o nome do outro.
 * Por isso o nome vem sempre de `opcoes` (o parâmetro `pwa_instrumento_options`),
 * nunca de `instrument_list`.
 *
 * `ligados` é a CAMADA 2 do filtro da faixa de instrumentos (bugfix): a
 * camada 1 (`visitasVisiveis`, montada pelo chamador) já decide QUAIS
 * visitas sobrevivem — mas uma visita sobrevivente pode usar vários
 * instrumentos, alguns ligados e outros desligados, e sem este parâmetro
 * TODOS eles viravam marca. `undefined`/`null` (o default, usado por
 * `pontosInstrumentoJanela` em `page.tsx`) preserva o comportamento de
 * sempre — universo inteiro, sem filtro —, porque a legenda e a seção
 * "Instrumentos do dia" precisam continuar mostrando todo instrumento da
 * janela (senão não haveria como religar um chip desligado). Só a
 * agregação que alimenta as marcas da GRADE (`pontosInstrumentoGrade`)
 * passa um `Set`.
 */
export function instrumentosPorDia(
  visitas: VisitaAgenda[],
  dias: string[],
  opcoes: InstrumentoOpcao[],
  ligados?: ReadonlySet<number> | null,
): PontosInstrumentoDia[] {
  const porData = agruparPorData(visitas)
  const nomePorId = new Map(opcoes.map((o) => [o.id, o.name]))
  // Fora do laço dos 42 dias: o conjunto de ids conhecidos é o mesmo em todos.
  const conhecidos = new Set(nomePorId.keys())

  return dias.map((date) => {
    const doDia = porData.get(date) ?? []

    // Conta visitas por id de instrumento, direto de `instrument_ids` — nunca
    // de `instrument_list`, que pode estar desalinhada (ver comentário acima).
    // `ligados` (camada 2) descarta o id ANTES de entrar na contagem: um
    // instrumento desligado não pode virar marca nem aparecer no
    // `aria-label`, então nem entra no Map.
    const contagem = new Map<number, number>()
    for (const v of doDia) {
      for (const id of v.instrument_ids) {
        if (ligados && !ligados.has(id)) continue
        contagem.set(id, (contagem.get(id) ?? 0) + 1)
      }
    }

    const instrumentos: PontoInstrumento[] = Array.from(contagem, ([id, visitas]) => ({
      id,
      name: nomePorId.get(id) ?? `Instrumento #${id}`,
      cor: corDoInstrumento(id),
      visitas,
    }))

    return { date, instrumentos: ordenarInstrumentos(instrumentos, conhecidos) }
  })
}
