'use client'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { VisitaCard } from '../_components/VisitaCard'
import { VisitaSheet } from '../_components/VisitaSheet'
import { LoadingState } from '@/components/ui/LoadingState'
import { useAgenda, useAgendaDisponivel, useTecnicoOptions, useInstrumentoOptions, useUpdateVisita } from '@/lib/hooks/useAgenda'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import type { VisitaAgenda, VisitaVals } from '@/lib/odoo/agenda'
import { mensagemDeFalha } from '@/lib/odoo/client'
import { clsx } from 'clsx'
import { agruparPorDia, deslocarJanela } from './janela'
import { FaixaDias } from './_FaixaDias'
import { PainelRecursos, type Dimensao } from './_PainelRecursos'
import { VistaMes } from './_VistaMes'
import { ConfirmarMudancaData } from './_ConfirmarMudancaData'
import { cargaPorDia, cargaPorTecnico, usoPorInstrumento, instrumentosDoDia, diasDaSemana, rosterTecnicos, picoDaSemana } from './carga'
import { primeiroDiaDoMes, deslocarMes, gradeDoMes, noMes, rotuloMes, tecnicosPorDia, instrumentosPorDia, conflitosPorDia, ordenarInstrumentos, corDoTecnico, COR_SEM_TECNICO } from './mes'
import type { PontoInstrumento } from './mes'

function rotuloDia(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number)
  return new Intl.DateTimeFormat('pt-BR', {
    weekday: 'short', day: '2-digit', month: 'short', timeZone: 'UTC',
  }).format(new Date(Date.UTC(a, m - 1, d)))
}

export default function AgendaPage() {
  const disponivel = useAgendaDisponivel()
  const { filterMine, setFilterMine, modoAgenda, setModoAgenda } = useTecnicoSettings()
  const semana = modoAgenda === 'semana'
  const mes = modoAgenda === 'mes'
  // Semana e Mês são as duas visões de EQUIPE — "Só minhas" desligado e
  // desabilitado, `onlyMine=false` no fetch, roster carregado pra
  // legenda/painel. Usar esta flag em todos esses pontos (em vez de
  // acrescentar `|| mes` em cada `semana ? ... : ...` já existente) evita
  // que um dos sítios fique para trás — foi exatamente esse o risco
  // apontado no brief.
  const visaoEquipe = modoAgenda !== 'lista'
  // `null` na primeira carga: o servidor decide a janela e devolve
  // `date_from`, que passa a ancorar a navegação.
  const [inicio, setInicio] = useState<string | null>(null)
  const janelaDias = semana ? 7 : 14
  const fim = inicio ? deslocarJanela(inicio, janelaDias - 1) : null
  // `ancoraMes` é o 1º dia do mês visível — estado SEPARADO de `inicio`,
  // que ancora lista/semana. Misturar as duas semânticas no mesmo estado
  // faria o mês virar "14 dias a partir de", não um mês de calendário.
  const [ancoraMes, setAncoraMes] = useState<string | null>(null)
  // Memoizada: `gradeDoMes` monta 42 `Date` a cada chamada, e o resultado é a
  // dependência de quase todo o resto do modo Mês — sem referência estável,
  // nenhum dos `useMemo` abaixo economizaria nada.
  const gradeMes = useMemo(() => (ancoraMes ? gradeDoMes(ancoraMes) : []), [ancoraMes])
  const dateFrom = mes ? (gradeMes[0] ?? null) : inicio
  const dateTo = mes ? (gradeMes[41] ?? null) : fim
  // `disponivel.data` é `undefined` enquanto a query de disponibilidade
  // carrega (não `false`) — só o `false` explícito (módulo ausente) deve
  // segurar o `pwa_agenda_fetch`. Enquanto carrega, a busca segue normal.
  // Em Semana/Mês o filtro "Só minhas" fica sempre desligado (ver o
  // checkbox desabilitado abaixo): a carga é da equipe, não de uma pessoa —
  // passar `filterMine` aqui mostraria uma faixa de dias que contradiz o
  // painel/grade logo abaixo.
  const { data, isLoading, error } = useAgenda(dateFrom, dateTo, visaoEquipe ? false : filterMine, disponivel.data !== false)
  const [selecionada, setSelecionada] = useState<VisitaAgenda | null>(null)
  const [criando, setCriando] = useState(false)
  // Muda a cada abertura: sem isto, os `useState` internos da folha em modo
  // criar sobrevivem a fechar/reabrir e o FAB reabre com OS/data anteriores.
  const [criarSeq, setCriarSeq] = useState(0)
  const [diaSel, setDiaSel] = useState<string | null>(null)
  const [dimensao, setDimensao] = useState<Dimensao>('tecnico')
  const [emAjuste, setEmAjuste] = useState<VisitaAgenda | null>(null)
  const [erroAjuste, setErroAjuste] = useState('')
  // ISO do destino tocado na grade/faixa enquanto o diálogo de confirmação
  // de mudança de DATA está aberto. `null` = nenhum diálogo pendente. Só
  // data pede confirmação (Task 1) — técnico e instrumento continuam
  // gravando direto, por isso este estado é separado de `emAjuste`.
  const [dataPendente, setDataPendente] = useState<string | null>(null)
  /**
   * Alvo de foco pra depois de um "Confirmar" que muda de MÊS (achado
   * minor, review final). Ao fechar o `BottomSheet` da confirmação, o
   * efeito `[open]` dele devolve o foco, síncrono, à célula que abriu o
   * diálogo — mas se a gravação muda `ancoraMes` (a visita foi pra fora do
   * mês visível), as 42 células são re-chaveadas por `date` e a célula
   * recém-focada desmonta: o foco cai pro `<body>` sem aviso nenhum.
   *
   * Antes, o alvo era a própria tarja "Movendo a visita" — ela sobrevivia à
   * troca de mês porque não dependia de `ancoraMes`. Isso parou de valer
   * quando a gravação de DATA pelo diálogo passou a encerrar o ajuste sozinha
   * (pedido do usuário: "não precisa clicar mais lá embaixo o botão salvar"):
   * `encerrarAjuste()` zera `emAjuste` no MESMO lote de estado que muda
   * `ancoraMes`, então a tarja desmonta junto — focar nela só adiaria a queda
   * pro `<body>` em vez de evitar. Por isso o alvo agora é a barra de
   * navegação de período (◀ nome do mês ▶, sempre montada, fora de QUALQUER
   * gate de modo/carregamento/erro — inclusive `mesCarregando`, que pode virar
   * `true` no mesmo render em que `ancoraMes` muda, se o mês de destino ainda
   * não estiver em cache): ela não é rechaveada por data, não depende de
   * `emAjusteAtual` nem de `mesCarregando`, e ainda é semanticamente ligada ao
   * que aconteceu — o Gestor acabou de ser levado para o mês que o rótulo
   * agora mostra. O container da grade (`_GradeMes`) foi cogitado e
   * descartado: ele SOME da árvore sempre que `mesCarregando` fica `true`, e
   * nada garante que o mês de destino já esteja em cache no momento da troca.
   */
  const navegacaoRef = useRef<HTMLDivElement>(null)
  // Badges de filtro das duas faixas de legenda do Mês (Task 2). `null` =
  // "Todos" (sem restrição naquela faixa). Em memória só — nunca persistido,
  // nunca enviado ao servidor: alteram SÓ as marcas da grade (`pontosDiaGrade`/
  // `pontosInstrumentoGrade`), nunca o que é buscado ou o que os cards/seção
  // "Instrumentos do dia" mostram.
  const [tecnicosSel, setTecnicosSel] = useState<Set<number | false> | null>(null)
  const [instrumentosSel, setInstrumentosSel] = useState<Set<number> | null>(null)
  const update = useUpdateVisita()
  const tecnicos = useTecnicoOptions(visaoEquipe)
  // `pwa_instrumento_options` alimenta três telas distintas: o painel de
  // recursos da Semana (só quando a dimensão é "instrumento", pra não gastar
  // fetch enquanto o Gestor olha "Técnico"), e a legenda + lista do dia do
  // Mês (task 3), que precisam da lista inteira sempre que o mês está
  // aberto — daí a expressão única em vez de espalhar `|| mes` pelos sítios
  // que já checavam `semana`.
  const querInstrumentos = mes || (semana && dimensao === 'instrumento')
  const instrumentos = useInstrumentoOptions(querInstrumentos)

  // Rede de segurança: se a visita em ajuste sumir do payload (apagada em
  // outro lugar, saiu da janela) OU continuar lá mas ter travado (outro
  // lugar tirou a OS de `scheduled`, ex. `in_progress`), a seleção não pode
  // ficar presa a um alvo que não aceita mais gravação. Sem o segundo caso,
  // o card passa a renderizar o ramo travado (sem "Concluir"), mas
  // `alvoAtivo` continua ligado — cada toque na faixa/painel dispara uma
  // gravação que o servidor recusa, sem saída a não ser trocar de modo.
  useEffect(() => {
    if (!emAjuste || !data) return
    const atual = data.visitas.find((v) => v.id === emAjuste.id)
    if (!atual || !atual.editable) {
      encerrarAjuste()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, emAjuste])

  // Modo Semana na primeiríssima carga: `inicio` nasce `null`, e sem
  // `date_from`/`date_to` explícitos o servidor aplica a janela padrão de 14
  // dias (`pwa_agenda_fetch`), enquanto a faixa (`diasDaSemana`) sempre
  // mostra 7. Ancorar `inicio` assim que o payload chega alinha cabeçalho e
  // faixa, e evita buscar uma semana inteira de visitas a mais até a
  // próxima navegação.
  useEffect(() => {
    if (semana && inicio === null && data?.date_from) {
      setInicio(data.date_from)
    }
  }, [semana, inicio, data?.date_from])

  // Modo Mês na primeiríssima carga: `ancoraMes` nasce `null`, e sem ele
  // não há faixa (`grade[0]`..`grade[41]`) para pedir — a primeira busca
  // sai sem datas, o servidor aplica a janela padrão e devolve
  // `server_today` (nunca o relógio do aparelho). Assim que o payload
  // chega, ancora `ancoraMes` no 1º dia do mês de `server_today`, e a
  // segunda busca já traz a grade completa. Duas buscas na primeira
  // abertura é o preço aceito (brief 3c) — enquanto isso, `mesCarregando`
  // mais abaixo mantém o `LoadingState` em vez de uma grade meio vazia.
  useEffect(() => {
    if (mes && ancoraMes === null && data?.server_today) {
      setAncoraMes(primeiroDiaDoMes(data.server_today))
    }
  }, [mes, ancoraMes, data?.server_today])

  // Filtro das faixas de legenda do Mês: estado em memória só, zera ao
  // trocar de modo (brief Task 2 — "trocar de modo ou recarregar zera").
  // Roda em toda troca, inclusive AO ENTRAR no Mês (já nasce `null` de
  // qualquer forma) — o alvo real é a saída: sem isto, um filtro deixado
  // restrito na Semana ou na Lista sobreviveria escondido e reapareceria
  // ativo na próxima vez que o Mês abrisse.
  useEffect(() => {
    setTecnicosSel(null)
    setInstrumentosSel(null)
  }, [modoAgenda])

  const ancora = inicio ?? data?.date_from ?? null
  const semEmpregado = data ? !data.my_employee_id : false
  // `useMemo`, não plain: as duas rodam em TODO render, mesmo no Mês — onde
  // os dois resultados são descartados (`janelaVisivel` usa `gradeMes`, não
  // `dias`, quando `mes` é `true`) — e os blocos de filtro/isolar dos rounds
  // anteriores multiplicaram a frequência de render (achado minor, review
  // final). `[data]`/`[ancora]` porque `visitas` (a versão memoizada,
  // estável) só nasce um pouco abaixo — trocar a dependência por ela exigiria
  // mover estas duas linhas pra depois, e não é essa a troca pedida aqui.
  const grupos = useMemo(() => agruparPorDia(data?.visitas ?? []), [data])
  const dias = useMemo(() => (ancora ? diasDaSemana(ancora) : []), [ancora])
  const diaAtual = diaSel && dias.includes(diaSel) ? diaSel : dias[0] ?? ''
  // Referência estável: `data?.visitas ?? []` cria um array novo a cada render
  // quando a busca ainda não respondeu, e isso sozinho invalidaria todos os
  // `useMemo` abaixo que dependem das visitas.
  const visitas = useMemo(() => data?.visitas ?? [], [data])
  const doDia = visitas.filter((v) => v.date === diaAtual)
  // `pwa_tecnico_options` filtra por `is_tecnico=True`, mas `tecnico_id` na
  // visita não é restrito a isso — um painel de capacidade que só mostra o
  // roster oficial esconderia carga real de quem tem visita mas não a flag.
  // União com quem aparece nas visitas da janela, sem duplicar por id. Este
  // roster já unificado é o que `tecnicosPorDia` (mês) e `cargaPorTecnico`
  // (semana) exigem — passar o retorno cru de `useTecnicoOptions` faria uma
  // visita de técnico sem a flag `is_tecnico` contar no `total` do dia sem
  // gerar pontinho, silenciosamente.
  const roster = useMemo(
    () => rosterTecnicos(tecnicos.data ?? [], visitas),
    [tecnicos.data, visitas],
  )
  const hoje = data?.server_today ?? null
  // Catálogo de instrumentos e o conjunto de ids que ele conhece. O conjunto
  // é o que separa "instrumento de cadastro" de "id fabricado
  // (`Instrumento #<id>`)" na hora de ordenar — ver `ordenarInstrumentos`.
  const opcoesInstrumento = useMemo(() => instrumentos.data ?? [], [instrumentos.data])
  const idsInstrumentoConhecidos = useMemo(
    () => new Set(opcoesInstrumento.map((o) => o.id)),
    [opcoesInstrumento],
  )
  // `pwa_instrumento_options` pode falhar sozinho (RPC 500, sessão expirada,
  // ou falta de permissão de leitura em `engc.calibration.instruments` — a
  // chamada no servidor é sem `sudo`), sem que a busca da agenda falhe junto.
  // Antes do fix final isso era INVISÍVEL: `instrumentos.data` ficava
  // `undefined` pra sempre, todo instrumento usado virava `Instrumento #101`
  // na grade, na legenda e nos 42 `aria-label` — identificadores fabricados
  // apresentados como se fossem nome de cadastro —, e a seção "Instrumentos
  // do dia" sumia por completo, sem nenhuma mensagem.
  //
  // Agora a falha degrada como a dos técnicos: o Mês continua utilizável
  // (dias, pontinhos, cards), mas SEM nenhum triângulo, sem a faixa de
  // instrumentos e sem a seção do dia — as três superfícies concordam em não
  // afirmar nada —, e com uma tarja de erro explícita mais abaixo.
  //
  // `data === undefined` é o que restringe isso ao caso que importa: um
  // REFETCH que falha (foco de janela, ou depois do `staleTime` de 5min)
  // deixa `isError` true COM o último catálogo bom ainda em `data`. Blanquear
  // ali tiraria informação boa da tela por causa de uma falha de fundo
  // passageira — e não há nome fabricado nenhum pra suprimir, que é a única
  // coisa que a tarja existe pra impedir.
  const instrumentosComFalha = instrumentos.isError && instrumentos.data === undefined
  // Enquanto `ancoraMes` não ancorou (primeiríssima carga do mês) OU a
  // busca da faixa completa ainda está em voo (2ª busca, cada toque em
  // ◀ ▶ com `queryKey` novo), não há grade utilizável pra mostrar —
  // `mesCarregando` segura o `LoadingState` mais abaixo em vez de uma
  // grade meio vazia (42 células sem pontinho, sem anel de "hoje", sob o
  // spinner). Fix round 1 (achado 1): o gate original só cobria a 1ª
  // busca; `isLoading` sozinho já cobre as duas, porque também é `true`
  // durante a 1ª.
  //
  // `!error` é do fix round 2 (achado 1): com a busca falhando, `data` fica
  // `undefined`, o `useEffect` de ancoragem acima nunca roda e `ancoraMes`
  // fica `null` PARA SEMPRE — o gate ficava `true` para sempre junto, e a
  // tela mostrava o spinner e "Erro ao carregar a agenda" ao mesmo tempo,
  // indefinidamente, sem saída a não ser sair do modo.
  //
  // `instrumentos.isPending` é do fix final: as duas buscas saem em PARALELO
  // na primeira abertura do Mês, e sem isto a grade aparecia com
  // `Instrumento #N` nos rótulos e os nomes "pulavam" quando o catálogo
  // chegava depois. Só entra aqui porque `querInstrumentos` garante a query
  // habilitada sempre que `mes` é true (query desabilitada fica `pending` pra
  // sempre no react-query v5, o que travaria o spinner); e no erro o status
  // vira `error`, não `pending`, então a tarja aparece em vez do spinner.
  const mesCarregando =
    mes && !error && (ancoraMes === null || isLoading || instrumentos.isPending)
  // Um gate só, sem redundância: `mesCarregando` já embute `isLoading`, mas
  // só vale no mês — `mes && ...` é `false` na Lista e na Semana, onde o
  // spinner continua sendo o `isLoading` cru.
  const carregando = mes ? mesCarregando : isLoading
  // Duas versões de cada agregação da grade do mês, desde a Task 2 (badges
  // de filtro): a UNFILTRADA (sufixo `Janela`) cobre as 42 dias com TODAS as
  // visitas, e é a fonte das duas faixas de legenda/filtro e da seção
  // "Instrumentos do dia" — que precisam listar/mostrar o universo inteiro,
  // ligado ou desligado, senão não haveria como religar quem foi desligado
  // (brief: "as faixas continuam listando todos os recursos da janela") nem
  // a seção do dia contradiria o brief ("filtro altera SÓ as marcas da
  // grade"). A FILTRADA (sufixo `Grade`) roda sobre `visitasVisiveis` e
  // alimenta só as marcas (`dias`/`instrumentos` da `_GradeMes`).
  // Conjunto de ids de técnico com visita na janela (os 42 dias da grade) —
  // é só isso que `legendaTecnicos` abaixo precisa. Fix round 1 (achado 6,
  // evitável): antes rodava `tecnicosPorDia` (agregação 42 dias × roster)
  // só pra depois jogar fora tudo menos os ids — em modo Mês `visitas` JÁ É
  // a janela inteira (o fetch usa `gradeMes[0]`/`gradeMes[41]` como
  // `date_from`/`date_to`), e `roster` já é a união de quem tem visita, tão
  // basta uma varredura O(V) direto sobre `visitas`.
  const idsTecnicoNaJanela = useMemo(() => {
    const ids = new Set<number | false>()
    if (!mes) return ids
    for (const v of visitas) ids.add(v.tecnico_id)
    return ids
  }, [mes, visitas])
  // Instrumentos da grade do mês — FONTE ÚNICA (versão `Janela`) das
  // superfícies que precisam do universo inteiro: a faixa de legenda e a
  // seção "Instrumentos do dia". Com o catálogo em falha devolve `[]`: nada
  // de 42 dias de `Instrumento #<id>` posando de nome.
  const pontosInstrumentoJanela = useMemo(
    () => (mes && !instrumentosComFalha ? instrumentosPorDia(visitas, gradeMes, opcoesInstrumento) : []),
    [mes, instrumentosComFalha, visitas, gradeMes, opcoesInstrumento],
  )
  // `true` quando NENHUMA visita da janela usa instrumento nenhum — seja
  // porque o catálogo está em falha (`pontosInstrumentoJanela` já vem `[]`),
  // seja porque simplesmente ninguém usou instrumento neste mês (navegar
  // pra um mês sem nenhuma visita instrumentada). Nos dois casos
  // `legendaInstrumentos` fica `[]` — a faixa não tem NENHUM item pra
  // mostrar, e um `instrumentosSel` restrito de um mês/momento anterior não
  // tem contra o que ser aplicado aqui.
  const semInstrumentoNaJanela = pontosInstrumentoJanela.every((d) => d.instrumentos.length === 0)
  // As duas faixas (Task 2): uma visita contribui com marca se passa nas
  // DUAS camadas — interseção (E), não união —, e a restrição de
  // instrumentos por si só já exclui visita sem instrumento nenhum
  // (consequência aceita no brief). Alimenta SÓ as agregações `*Grade`
  // abaixo — `doDia` (os `VisitaCard`s) e `instrumentosDoDiaSel` continuam
  // lendo `visitas`/`pontosInstrumentoJanela`, a lista completa.
  //
  // `semInstrumentoNaJanela` ignora uma restrição de instrumento já armada
  // quando ela não tem NADA contra o que ser aplicada nesta janela (achado
  // 1 da review, fix round 1 — generalizado a partir do achado anterior do
  // advisor, que só cobria `instrumentosComFalha`): sem esta cláusula, um
  // `instrumentosSel` restrito de um mês/momento anterior continuava
  // suprimindo TODAS as marcas do mês (inclusive as de técnico, por causa
  // da interseção) sem nenhum controle visível pra limpar — a mesma forma
  // de armadilha ("sem saída a não ser trocar de modo") que este arquivo já
  // corrigiu várias vezes para outros gatilhos. Alcançável por NAVEGAÇÃO
  // pura, sem nenhuma falha: restringir instrumentos em setembro e tocar ▶
  // pra um mês sem visita instrumentada bastava.
  const visitasVisiveis = useMemo(() => {
    if (!mes || (tecnicosSel === null && instrumentosSel === null)) return visitas
    return visitas.filter((v) => {
      const passaTecnico = tecnicosSel === null || tecnicosSel.has(v.tecnico_id)
      const passaInstrumento =
        instrumentosSel === null || semInstrumentoNaJanela ||
        v.instrument_ids.some((id) => instrumentosSel.has(id))
      return passaTecnico && passaInstrumento
    })
  }, [mes, visitas, tecnicosSel, instrumentosSel, semInstrumentoNaJanela])
  const pontosDiaGrade = useMemo(
    () => (mes ? tecnicosPorDia(visitasVisiveis, gradeMes, roster) : []),
    [mes, visitasVisiveis, gradeMes, roster],
  )
  // Barra de estado por dia (Task 1): fonte NÃO FILTRADA de propósito —
  // `visitas`, nunca `visitasVisiveis`. O filtro das duas faixas de legenda
  // altera só as MARCAS da grade (`pontosDiaGrade`/`pontosInstrumentoGrade`,
  // acima); conflito é fato do dia inteiro e não pode ficar escondido só
  // porque o Gestor restringiu técnico/instrumento (decisão fechada com o
  // user, brief). `[]` fora do mês — mesmo raciocínio de `idsTecnicoNaJanela`
  // — mas devolvendo sempre a mesma REFERÊNCIA (`Set` vazio memoizado por
  // `useMemo`, não um literal por render) para não invalidar à toa quem
  // consome esta prop.
  const conflitosGrade = useMemo(
    () => (mes ? conflitosPorDia(visitas, gradeMes) : new Set<string>()),
    [mes, visitas, gradeMes],
  )
  // Sem NENHUMA das duas faixas restrita, `visitasVisiveis` devolve a mesma
  // REFERÊNCIA de `visitas` (ver o early return do memo acima) — e aí esta
  // agregação produziria byte a byte a mesma coisa que `pontosInstrumentoJanela`:
  // Map sobre o catálogo, laço de 42 dias e um `sort` por dia, pagos duas
  // vezes a cada troca de `visitas`, que é o caso COMUM (o filtro é
  // opcional). O atalho pode vir antes das outras condições: com `!mes` ou
  // catálogo em falha, `pontosInstrumentoJanela` já é `[]`, que é
  // exatamente o que este memo devolveria. Compartilhar a referência é
  // seguro porque ninguém ordena/muta esses arrays no lugar —
  // `ordenarInstrumentos` faz `.slice().sort()` e `instrumentosDoDia` só
  // mapeia.
  //
  // CAMADA 2 (bugfix): a camada 1, acima, já decide quais VISITAS sobrevivem
  // — mas uma visita sobrevivente pode usar vários instrumentos, alguns
  // ligados e outros desligados (ex. Q001 e Q002 na mesma visita, só Q001
  // desligado), e até este fix `instrumentosPorDia` desenhava TODOS eles.
  // `ligadosNaGrade` só restringe quando há restrição ativa E ela tem contra
  // o que valer nesta janela (`!semInstrumentoNaJanela`, mesma condição da
  // camada 1 logo acima) — nos outros casos é `undefined`, e
  // `instrumentosPorDia` se comporta como sempre.
  const ligadosNaGrade = instrumentosSel !== null && !semInstrumentoNaJanela ? instrumentosSel : undefined
  const pontosInstrumentoGrade = useMemo(
    () => {
      // `&& !ligadosNaGrade` é hoje inalcançável (`ligadosNaGrade` truthy
      // exige `instrumentosSel !== null`, e nesse caso `visitasVisiveis`
      // NUNCA é a mesma referência de `visitas` — o early return do memo
      // acima só devolve a própria `visitas` quando as duas faixas estão em
      // "Todos"). Fica como guarda explícita da invariante, não como atalho
      // que hoje dispara: se a lógica de `visitasVisiveis` mudar um dia e
      // parar de garantir isso, este `if` evita voltar a mostrar o universo
      // inteiro (sem camada 2) por engano.
      if (visitasVisiveis === visitas && !ligadosNaGrade) return pontosInstrumentoJanela
      return mes && !instrumentosComFalha
        ? instrumentosPorDia(visitasVisiveis, gradeMes, opcoesInstrumento, ligadosNaGrade)
        : []
    },
    [
      mes, instrumentosComFalha, visitasVisiveis, visitas, pontosInstrumentoJanela, gradeMes, opcoesInstrumento,
      ligadosNaGrade,
    ],
  )
  // Legenda de instrumentos: os distintos da janela de 42 dias (mesmo escopo
  // da faixa de técnicos, que cobre a grade desenhada e não o mês estrito),
  // deduplicados por id e ordenados pela MESMA função que ordena a célula
  // (`ordenarInstrumentos`) — daí a montagem viver aqui, onde
  // `idsInstrumentoConhecidos` está à mão, e não dentro da `_VistaMes`, que
  // por ruling do controlador só recebe dado já agregado. Fonte
  // `pontosInstrumentoJanela` (não filtrada): a faixa lista todo mundo,
  // ligado ou desligado (Task 2).
  const legendaInstrumentos = useMemo(() => {
    const vistos = new Set<number>()
    const itens: PontoInstrumento[] = []
    for (const d of pontosInstrumentoJanela) {
      for (const inst of d.instrumentos) {
        if (vistos.has(inst.id)) continue
        vistos.add(inst.id)
        itens.push(inst)
      }
    }
    return ordenarInstrumentos(itens, idsInstrumentoConhecidos)
  }, [pontosInstrumentoJanela, idsInstrumentoConhecidos])
  // Legenda de técnicos (Task 2): mesmo raciocínio de `legendaInstrumentos`
  // acima, movido de dentro de `_VistaMes` pra cá pra poder alimentar tanto
  // a faixa (universo inteiro) quanto o filtro (que precisa do universo pra
  // inicializar o `Set` ao desligar o primeiro item a partir de "Todos", ver
  // `alternarTecnico` abaixo). Ordem do roster (por nome), "Sem técnico" no
  // fim — mesma ordem que `_VistaMes` produzia antes desta task.
  const legendaTecnicos = useMemo(() => {
    const itens: { chave: string | number; id: number | false; cor: string; nome: string }[] = roster
      .filter((t) => idsTecnicoNaJanela.has(t.id))
      .map((t) => ({ chave: t.id, id: t.id as number | false, cor: corDoTecnico(t.id, t.color), nome: t.name }))
    if (idsTecnicoNaJanela.has(false)) {
      itens.push({ chave: 'sem-tecnico', id: false, cor: COR_SEM_TECNICO, nome: 'Sem técnico' })
    }
    return itens
  }, [idsTecnicoNaJanela, roster])
  // Dia default quando não há seleção válida na grade: primeiro tenta
  // `hoje` (server_today) — mesmo critério da Semana, que nasce ancorada
  // em `data.date_from` = hoje — e só cai no 1º dia do mês quando "hoje"
  // está fora da grade visível (mês diferente do atual). Cair direto no
  // dia 1 (fix round 1, achado 4) marcava dois dias ao mesmo tempo na
  // primeira abertura: o anel de "hoje" no dia certo e o fundo de seleção
  // no dia 1, com a lista de cards dizendo "Nenhuma visita neste dia."
  const diaSelMes = diaSel && gradeMes.includes(diaSel)
    ? diaSel
    : (hoje && gradeMes.includes(hoje) ? hoje : (ancoraMes ?? ''))
  // "Instrumentos do dia" (brief 3c): sai da ENTRADA de
  // `pontosInstrumentoJanela` (não filtrada — Task 2) do dia selecionado,
  // casada por `date`, acrescida dos usos (OS, técnico, faixa de horário).
  // Desde a Task 2 esta fonte pode DIVERGIR do triângulo da célula quando o
  // filtro está ativo — de propósito: o brief é explícito que o filtro
  // altera SÓ as marcas da grade, e esta seção continua sobre a lista
  // completa de visitas. Até o fix final esta seção mapeava sobre
  // `pwa_instrumento_options` via `usoPorInstrumento`: a interseção entre
  // usado e catalogado, enquanto a grade mostrava a união. Um instrumento
  // arquivado depois de usado (`pwa_instrumento_options` faz `search([])`,
  // com `active_test` ligado) bastava pra grade afirmar que o dia tem o
  // instrumento e a lista negar, em silêncio.
  const instrumentosDoDiaSel = useMemo(
    () => (mes
      ? instrumentosDoDia(
          visitas,
          diaSelMes,
          pontosInstrumentoJanela.find((p) => p.date === diaSelMes)?.instrumentos ?? [],
        )
      : []),
    [mes, visitas, diaSelMes, pontosInstrumentoJanela],
  )
  // `emAjuste` guarda a visita como ela estava ao ser selecionada. Depois de
  // cada gravação bem-sucedida, o `onSuccess` do `useUpdateVisita` invalida a
  // busca e o payload volta atualizado — mas `emAjuste` continua com a cópia
  // velha. Ressincronizar a partir do payload evita que ligar dois
  // instrumentos em sequência desligue o primeiro.
  const emAjusteAtual = emAjuste
    ? visitas.find((v) => v.id === emAjuste.id) ?? emAjuste
    : null
  // A visita armada só é ALVO de gravação enquanto ela própria está visível
  // na janela atual (fix round 2, achado 2). Sem isto, navegar de mês (ou
  // trocar de modo) tirava o card da tela sem desarmar nada, e o toque
  // seguinte num dia qualquer reagendava a visita em silêncio — três toques
  // e a visita tinha mudado de mês sem ninguém pedir. O que a janela mostra
  // e o que o toque grava passam a ser a mesma coisa.
  const janelaVisivel = mes ? gradeMes : dias
  const alvoVisivel = !!emAjusteAtual && janelaVisivel.includes(emAjusteAtual.date)

  // Rede de segurança (achado 1 da review da Task 1): o diálogo de
  // confirmação de DATA pendente (`dataPendente`) não pode sobreviver ao
  // alvo SAIR DA JANELA VISÍVEL. Cenário: o Gestor arma o diálogo (toca um
  // dia diferente, `dataPendente` fica setado) e, antes de tocar
  // "Confirmar", a visita deixa de estar à vista — seja porque ele navegou
  // de mês/semana, seja porque um refetch em background a moveu para FORA
  // dos 42 dias desenhados. Nos dois casos o diálogo continuava aberto,
  // pronto pra gravar num alvo que `alvoVisivel` existe justamente pra
  // proibir (ver comentário dele acima). O `useEffect` anterior não cobre
  // isto: ele só olha "sumiu do payload" ou "travou".
  //
  // O que este efeito NÃO cobre, de propósito: um refetch que move a visita
  // para outra data DENTRO da janela (17/09 → 25/09 com o diálogo armado
  // para 19/09). `alvoVisivel` continua `true` e nada dispara — e não
  // precisa: o texto do diálogo re-renderiza com a data nova, então o que o
  // Gestor lê antes de confirmar é o que vai ser gravado. É autocorrigível,
  // não um buraco.
  //
  // `confirmarData` abaixo repete o mesmo check por defesa em profundidade
  // (mesmo clique, mesmo tick).
  useEffect(() => {
    if (dataPendente !== null && !alvoVisivel) {
      setDataPendente(null)
    }
  }, [dataPendente, alvoVisivel])

  // O early return fica DEPOIS das derivações de propósito: todo `useMemo`
  // acima é um hook, e hook depois de `return` condicional quebra a ordem de
  // hooks entre renders.
  if (disponivel.data === false) {
    return (
      <p className="mx-auto max-w-[880px] p-4 text-center text-muted-foreground">
        Agenda de visitas indisponível: o módulo de agendamento não está
        instalado neste servidor.
      </p>
    )
  }

  /** A seleção termina (toque em "Concluir", ou a visita some do payload):
   * nada de tarja de erro sobrevivendo a uma seleção que já acabou, e nada
   * de diálogo de confirmação de data perguntando sobre uma visita que não
   * aceita mais gravação. */
  function encerrarAjuste() {
    setEmAjuste(null)
    setErroAjuste('')
    setDataPendente(null)
  }

  /** Toque em "Ajustar"/"Concluir" no card: liga/desliga o ajuste daquela
   * visita. Trocar de alvo limpa qualquer diálogo de data pendente do alvo
   * anterior — mesmo raciocínio de `encerrarAjuste`, aplicado à troca. */
  function alternarAjuste(visita: VisitaAgenda) {
    if (emAjuste?.id === visita.id) {
      encerrarAjuste()
      return
    }
    setDataPendente(null)
    setEmAjuste(visita)
  }

  /**
   * Toque num dia da grade/faixa com visita armada: mesmo dia não abre
   * diálogo nenhum (não há o que confirmar) — mas ainda seleciona o dia
   * (`setDiaSel`), em vez de não fazer nada, pra manter a mesma resposta ao
   * toque que o caminho sem visita armada já dá (todo toque num dia
   * seleciona aquele dia); um toque silenciosamente inerte só porque há uma
   * visita armada seria uma exceção sem motivo visível pro Gestor. Dia
   * diferente arma `dataPendente`, que abre o diálogo de confirmação — só
   * `ajustar` grava de fato, depois do "Confirmar".
   */
  function armarData(date: string) {
    if (!emAjusteAtual) return
    if (date === emAjusteAtual.date) {
      setDiaSel(date)
      return
    }
    setDataPendente(date)
  }

  /** "Confirmar" do diálogo: grava pelo `ajustar` que já existe (âncora do
   * mês, `setDiaSel`, tarja de erro) e fecha o diálogo. `alvoVisivel`
   * checado de novo aqui (achado 1 da review da Task 1): o `useEffect` logo
   * acima já fecha o diálogo reativamente assim que o alvo sai da janela,
   * mas o clique e o efeito não são a mesma coisa — esta segunda checagem é
   * o que garante que NENHUM clique em "Confirmar" grava fora da janela,
   * mesmo numa corrida entre o efeito e o clique. */
  function confirmarData() {
    if (dataPendente && alvoVisivel) ajustar({ date: dataPendente })
    setDataPendente(null)
  }

  /** "Cancelar" do diálogo: fecha sem gravar — a visita continua armada. */
  function cancelarData() {
    setDataPendente(null)
  }

  /**
   * Cada toque no painel grava UM campo. A visita em ajuste continua
   * selecionada depois do erro: o Gestor precisa poder tentar outro alvo sem
   * recomeçar.
   */
  async function ajustar(vals: VisitaVals) {
    if (!emAjuste) return
    setErroAjuste('')
    try {
      await update.mutateAsync({ id: emAjuste.id, vals })
      // A vista segue a visita: sem isto, mover para outro dia tirava o
      // card de `doDia` (some o "Concluir" junto), e cada novo toque na
      // faixa reaplicava o mesmo `date` — sem jeito de navegar ou
      // desselecionar sem sair do modo Semana.
      if (typeof vals.date === 'string') {
        setDiaSel(vals.date)
        // Mês: mover a visita pra fora do mês visível tira o card da
        // grade (ela mudou de mês), mas a âncora sozinha não segue — sem
        // isto a seleção fica presa olhando pro mês errado. É estado da
        // PÁGINA (`ancoraMes`), não da `_VistaMes`: passar a âncora pra
        // baixo só pro filho escrever de volta inverteria o fluxo de dados
        // dos outros modos (ruling do controlador, brief 3d).
        if (mes && ancoraMes && !noMes(vals.date, ancoraMes)) {
          setAncoraMes(primeiroDiaDoMes(vals.date))
          // A célula que tinha o foco (a do diálogo de confirmação, já
          // devolvido pelo `BottomSheet` ao fechar) está prestes a
          // desmontar — as 42 células da grade nova são outras (achado
          // minor, review final). Sem isto, o foco cai pro `<body>` assim
          // que este re-render troca a grade pro mês novo. Alvo é a barra
          // de navegação (`navegacaoRef`), não a tarja — ver o comentário
          // dela: a tarja está prestes a desmontar NESTE MESMO lote, pelo
          // `encerrarAjuste()` logo abaixo.
          navegacaoRef.current?.focus()
        }
        // Pedido do usuário: confirmar a mudança de DATA pelo diálogo já é
        // "aplicar o ajuste" — não faz sentido exigir mais um toque em
        // "Concluir" só pra desarmar. Encerra sozinho, mesmo efeito de
        // `encerrarAjuste()` (tarja e "Concluir" somem). SÓ este caminho:
        // técnico e instrumento (`onTocarTecnico`/`onTocarInstrumento`) nunca
        // passam `vals.date`, e continuam armados de propósito — são toques
        // sucessivos por natureza, o Gestor liga vários instrumentos em
        // sequência sem procurar "Concluir" a cada um. E só no SUCESSO: se
        // `mutateAsync` rejeitar, o `catch` abaixo roda no lugar deste bloco
        // — a visita continua armada e a tarja de erro do servidor continua
        // visível, pra tentar outro dia.
        encerrarAjuste()
      }
    } catch (e) {
      setErroAjuste(e instanceof Error && e.message ? e.message : mensagemDeFalha(e))
    }
  }

  /**
   * Toque num chip da faixa "Técnicos:" (Task 2). Partindo de "Todos"
   * (`null`), o primeiro toque desliga UM item — o `Set` de trabalho nasce
   * com TODOS os ids hoje na faixa (`legendaTecnicos`, o universo da janela
   * visível) e o toque remove só o tocado; ficar sem essa base faria o
   * primeiro toque "restringir a um só" em vez de "desligar um".
   */
  function alternarTecnico(id: number | false) {
    setTecnicosSel((atual) => {
      const base = atual ?? new Set(legendaTecnicos.map((t) => t.id))
      const novo = new Set(base)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })
  }

  /** Mesmo raciocínio de `alternarTecnico`, para a faixa "Instrumentos:". */
  function alternarInstrumento(id: number) {
    setInstrumentosSel((atual) => {
      const base = atual ?? new Set(legendaInstrumentos.map((i) => i.id))
      const novo = new Set(base)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })
  }

  /** Badge "Todos" de qualquer uma das duas faixas: limpa a restrição SÓ
   *  daquela faixa — a outra continua com o que estava. */
  function todosTecnicos() {
    setTecnicosSel(null)
  }
  function todosInstrumentos() {
    setInstrumentosSel(null)
  }

  /**
   * Toque longo (Task 1) num chip da faixa "Técnicos:": isola aquele
   * técnico — o `Set` passa a ter só ele. Tocar de novo no chip que JÁ é o
   * único ligado reverte pra "Todos" (`null`) — o gesto é reversível por si
   * mesmo, sem obrigar a caçar o badge "Todos" (brief). Só quem sabe se o
   * `id` tocado é o único ligado é quem detém o `Set` — por isso a decisão
   * mora aqui, não na `FaixaLegenda`, que só avisa qual `id` foi tocado.
   */
  function isolarTecnico(id: number | false) {
    setTecnicosSel((atual) => (atual !== null && atual.size === 1 && atual.has(id) ? null : new Set([id])))
  }
  /** Mesmo raciocínio de `isolarTecnico`, para a faixa "Instrumentos:" — as
   *  duas faixas são independentes no gesto: isolar uma nunca toca no `Set`
   *  da outra. */
  function isolarInstrumento(id: number) {
    setInstrumentosSel((atual) => (atual !== null && atual.size === 1 && atual.has(id) ? null : new Set([id])))
  }

  return (
    <div className="mx-auto w-full max-w-[880px] space-y-4">
      <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
        {(['lista', 'semana', 'mes'] as const).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={modoAgenda === m}
            onClick={() => setModoAgenda(m)}
            className={clsx(
              'min-h-[44px] flex-1 rounded-md text-sm',
              modoAgenda === m ? 'bg-accent font-semibold' : 'text-muted-foreground',
            )}
          >
            {m === 'lista' ? 'Lista' : m === 'semana' ? 'Semana' : 'Mês'}
          </button>
        ))}
      </div>

      {/* `ref={navegacaoRef}` + `tabIndex={-1}`: alvo de foco depois de um
          "Confirmar" de data que muda de mês (ver comentário de
          `navegacaoRef` acima) — nunca entra no ciclo de Tab normal, só
          recebe foco por `.focus()` imperativo. */}
      <div
        ref={navegacaoRef}
        tabIndex={-1}
        className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-2 py-1"
      >
        <button
          type="button"
          aria-label="Período anterior"
          className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          onClick={() => {
            // Mês navega de calendário (±1 mês), não ±N dias — misturar as
            // duas aritméticas aqui é o mesmo erro que motivou `ancoraMes`
            // ser um estado à parte de `inicio`.
            if (mes) {
              if (ancoraMes) setAncoraMes(deslocarMes(ancoraMes, -1))
            } else if (ancora) {
              setInicio(deslocarJanela(ancora, -janelaDias))
            }
          }}
        >
          <ChevronLeft className="h-5 w-5" aria-hidden />
        </button>
        <span className="text-sm font-medium">
          {mes
            // "setembro de 2026", não `date_from`–`date_to` do payload — a
            // grade de 42 dias transborda pro mês vizinho nas duas pontas, e
            // "dom 30 ago – sáb 10 out" mentiria sobre qual mês está aberto.
            ? (ancoraMes ? rotuloMes(ancoraMes) : '—')
            : (data ? `${rotuloDia(data.date_from)} – ${rotuloDia(data.date_to)}` : '—')}
        </span>
        <button
          type="button"
          aria-label="Próximo período"
          className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          onClick={() => {
            if (mes) {
              if (ancoraMes) setAncoraMes(deslocarMes(ancoraMes, 1))
            } else if (ancora) {
              setInicio(deslocarJanela(ancora, janelaDias))
            }
          }}
        >
          <ChevronRight className="h-5 w-5" aria-hidden />
        </button>
      </div>

      <label
        htmlFor="agenda-filter-mine"
        className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2"
      >
        <span className="text-sm font-medium">
          Só minhas
          <span className="block text-xs font-normal text-muted-foreground">
            {visaoEquipe
              ? (mes ? 'Desligado no mês: a carga é da equipe' : 'Desligado na semana: a carga é da equipe')
              : semEmpregado
                ? 'Seu usuário não tem técnico vinculado'
                : filterMine
                  ? 'Visitas atribuídas a você'
                  : 'Visitas de toda a equipe'}
          </span>
        </span>
        <input
          id="agenda-filter-mine"
          type="checkbox"
          checked={visaoEquipe ? false : filterMine && !semEmpregado}
          disabled={visaoEquipe || semEmpregado}
          onChange={(e) => setFilterMine(e.target.checked)}
          className="h-6 w-6 shrink-0 cursor-pointer accent-ok disabled:opacity-40"
        />
      </label>

      {/* Tarja de ajuste em curso — FORA dos ramos de modo de propósito
          (ruling do controlador): o indicador de "tem visita armada" não
          pode depender do `VisitaCard`, que só é renderizado quando a visita
          cai no dia selecionado. Vale para Semana E Mês, e carrega o
          identificador da visita e uma saída explícita — nada aqui depende
          de cor.

          `sticky top-0`: o botão "Ajustar" que arma o ajuste mora no
          `VisitaCard`, ABAIXO da grade — no celular, onde a grade sozinha já
          ocupa quase a tela, a tarja nascia num ponto da página que a rolagem
          da grade já tinha deixado pra trás (medido a 390px: `top: -173px`,
          fora da viewport). `<main overflow-auto>` (`layout.tsx`) é o único
          ancestral com rolagem — o mesmo container que já sustenta o
          cabeçalho de dia do modo Lista com `sticky top-0` mais abaixo — por
          isso gruda aqui sem precisar de nenhum ajuste no layout. `z-20`
          fica acima desse cabeçalho (`z-10`) pra nunca ficar por baixo das
          células ao rolar, e `bg-muted` (já existente, cor sólida) garante o
          fundo opaco.

          `border-2 border-info` (pedido do usuário): a tarja precisa chamar
          mais atenção. `--info` (não uma cor crua) já existe nos dois temas —
          cyan-800 no claro, `#22d3ee` no escuro — e mede bem contra
          `bg-muted`: 6.55:1 no claro, 10.08:1 no escuro (calculado com
          `hsl2rgb`/`contraste` de `tests/contraste.ts`, mesmo utilitário do
          guard `temaTokens.test.ts` — bem acima do piso de 3:1 da WCAG
          1.4.11 pra contorno de componente). A cor NUNCA é o único
          portador aqui — o texto "Movendo a visita {OS} de {data}" continua
          dizendo o que está acontecendo; a borda só chama o olho pra tarja.
          `border-2` em vez de `border` (mais grossa, pedido do usuário) não
          desloca nada ao redor: a tarja monta/desmonta inteira com
          `emAjusteAtual`, nunca troca de espessura de borda enquanto já está
          na tela. */}
      {emAjusteAtual && (
        <div className="sticky top-0 z-20 flex items-center justify-between gap-2 rounded-lg border-2 border-info bg-muted px-3 py-2">
          <span className="min-w-0 text-sm">
            Movendo a visita {emAjusteAtual.os_name} de {rotuloDia(emAjusteAtual.date)}
            <span className="block text-xs text-muted-foreground">
              {alvoVisivel
                ? 'Toque num dia para mover.'
                : 'Fora do período visível: volte ao período dela ou cancele.'}
            </span>
          </span>
          <button
            type="button"
            onClick={encerrarAjuste}
            className="min-h-[44px] shrink-0 rounded-md border border-border px-3 text-sm font-medium"
          >
            Cancelar
          </button>
        </div>
      )}

      {carregando && <LoadingState label="Carregando sua agenda..." />}
      {error && (
        <p className="text-center text-danger">
          Erro ao carregar a agenda. Verifique conexão.
        </p>
      )}
      {/* Falha SÓ do catálogo de instrumentos (a agenda em si carregou). Sem
          esta tarja, a queda era muda: a grade continuava desenhando, e o
          Gestor não tinha como saber que os triângulos e a lista do dia
          sumiram por falha, e não porque nenhuma visita usa instrumento.
          `!error` porque sessão expirada / conexão caída derruba as DUAS
          buscas: sem ele, a tela mostrava "Erro ao carregar a agenda" mais uma
          segunda tarja falando de triângulos e lista de uma `VistaMes` que
          nem chega a ser renderizada (o gate dela também tem `!error`). */}
      {mes && !error && instrumentosComFalha && (
        <p className="text-center text-danger">
          Erro ao carregar os instrumentos. O mês está sem os triângulos, sem a
          faixa de instrumentos e sem a lista do dia. Verifique conexão ou suas
          permissões.
        </p>
      )}
      {!isLoading && !error && modoAgenda === 'lista' && grupos.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">
          Nenhuma visita neste período.
        </p>
      )}

      {modoAgenda === 'lista' && grupos.map((g) => (
        <section key={g.date} className="space-y-2">
          <h2 className="sticky top-0 z-10 bg-background py-1 text-sm font-semibold uppercase text-muted-foreground">
            {rotuloDia(g.date)}
          </h2>
          {g.visitas.map((v) => (
            <VisitaCard key={v.id} visita={v} onSelect={setSelecionada} />
          ))}
        </section>
      ))}

      {semana && (
        <>
          <FaixaDias
            dias={cargaPorDia(visitas, dias)}
            selecionado={diaAtual}
            onSelecionar={(d) => (alvoVisivel ? armarData(d) : setDiaSel(d))}
          />
          {erroAjuste && <p className="text-sm text-danger">{erroAjuste}</p>}
          <PainelRecursos
            dimensao={dimensao}
            onTrocarDimensao={setDimensao}
            tecnicos={cargaPorTecnico(visitas, diaAtual, roster)}
            pico={picoDaSemana(visitas, dias, roster)}
            instrumentos={usoPorInstrumento(visitas, diaAtual, instrumentos.data ?? [])}
            instrumentoIdsDaVisita={emAjusteAtual?.instrument_ids ?? []}
            tecnicoIdDaVisita={emAjusteAtual && emAjusteAtual.tecnico_id !== false ? emAjusteAtual.tecnico_id : undefined}
            alvoAtivo={alvoVisivel}
            onTocarTecnico={(id) => ajustar({ tecnico_id: id })}
            onTocarInstrumento={(id) => {
              const atuais = emAjusteAtual?.instrument_ids ?? []
              ajustar({
                instrument_ids: atuais.includes(id)
                  ? atuais.filter((x) => x !== id)
                  : [...atuais, id],
              })
            }}
          />
          {doDia.map((v) => (
            <VisitaCard
              key={v.id}
              visita={v}
              onSelect={setSelecionada}
              onAjustar={data?.can_manage ? alternarAjuste : undefined}
              emAjuste={emAjuste?.id === v.id}
            />
          ))}
          {doDia.length === 0 && (
            <p className="py-6 text-center text-muted-foreground">Nenhuma visita neste dia.</p>
          )}
        </>
      )}

      {/* `!error` e `ancoraMes !== null`: com `mesCarregando` agora falso no
          erro (achado 1), sem estes dois a grade vazaria vazia — 0 células,
          âncora '' e "Nenhuma visita neste dia." — por baixo da mensagem de
          falha. */}
      {mes && !mesCarregando && !error && ancoraMes !== null && (
        <VistaMes
          visitas={visitas}
          dias={pontosDiaGrade}
          instrumentos={pontosInstrumentoGrade}
          conflitos={conflitosGrade}
          legendaTecnicos={legendaTecnicos}
          legendaInstrumentos={legendaInstrumentos}
          tecnicosSel={tecnicosSel}
          // Durante a falha do catálogo (não a navegação sem uso), a faixa
          // precisa FICAR escondida — `legendaInstrumentos` já é `[]`, e sem
          // forçar `null` aqui um `instrumentosSel` restrito de antes da
          // falha faria `FaixaLegenda` renderizar (itens vazios, mas
          // `selecionado !== null`), quebrando a garantia de que a falha do
          // catálogo apaga a faixa inteira. Fora da falha (navegação pura
          // pra um mês sem uso), passa o `Set` real — é o que dá a
          // `FaixaLegenda` o "Todos" desligado como escape visível.
          instrumentosSel={instrumentosComFalha ? null : instrumentosSel}
          onAlternarTecnico={alternarTecnico}
          onAlternarInstrumento={alternarInstrumento}
          onTodosTecnicos={todosTecnicos}
          onTodosInstrumentos={todosInstrumentos}
          onIsolarTecnico={isolarTecnico}
          onIsolarInstrumento={isolarInstrumento}
          instrumentosDoDia={instrumentosDoDiaSel}
          ancora={ancoraMes ?? ''}
          hoje={hoje}
          diaSel={diaSelMes}
          onSelecionarDia={setDiaSel}
          podeAjustar={!!data?.can_manage}
          emAjuste={emAjusteAtual}
          alvoAtivo={alvoVisivel}
          onAjustar={(vals) => { if (typeof vals.date === 'string') armarData(vals.date) }}
          onAlternarAjuste={alternarAjuste}
          erroAjuste={erroAjuste}
          onSelecionarVisita={setSelecionada}
        />
      )}

      <ConfirmarMudancaData
        open={dataPendente !== null && !!emAjusteAtual}
        osName={emAjusteAtual?.os_name ?? ''}
        dataAtual={emAjusteAtual?.date ?? ''}
        dataNova={dataPendente ?? ''}
        onConfirmar={confirmarData}
        onCancelar={cancelarData}
      />

      {data?.can_manage && (
        <button
          type="button"
          onClick={() => {
            setCriarSeq((s) => s + 1)
            setCriando(true)
          }}
          className="fixed bottom-20 right-4 z-40 flex h-14 items-center gap-2 rounded-full bg-primary px-5 font-semibold text-primary-foreground shadow-[0_8px_24px_rgba(0,0,0,0.45)] lg:bottom-6"
        >
          <Plus className="h-5 w-5" aria-hidden />
          Nova visita
        </button>
      )}

      <VisitaSheet
        key={selecionada?.id ?? 'nenhuma'}
        open={!!selecionada}
        modo="editar"
        visita={selecionada}
        onClose={() => setSelecionada(null)}
      />
      <VisitaSheet
        key={`criar-${criarSeq}`}
        open={criando}
        modo="criar"
        visita={null}
        onClose={() => setCriando(false)}
      />
    </div>
  )
}
