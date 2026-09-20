// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AgendaPage from '../agenda/page'
import { gradeDoMes } from '../agenda/mes'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import type { AgendaPayload, InstrumentoOpcao, VisitaAgenda } from '@/lib/odoo/agenda'

const mutateUpdate = vi.fn()

// Espia `instrumentosPorDia` sem trocá-la por um dublê: a agregação real
// continua rodando (os outros testes deste arquivo leem o resultado dela na
// grade), só passa a ser contável. `vi.hoisted` porque a fábrica do
// `vi.mock` roda antes das declarações do módulo.
const { espiaInstrumentosPorDia } = vi.hoisted(() => ({ espiaInstrumentosPorDia: vi.fn() }))
vi.mock('../agenda/mes', async (importOriginal) => {
  const real = await importOriginal<typeof import('../agenda/mes')>()
  return {
    ...real,
    instrumentosPorDia: (...args: Parameters<typeof real.instrumentosPorDia>) => {
      espiaInstrumentosPorDia(...args)
      return real.instrumentosPorDia(...args)
    },
  }
})

function visita(over: Partial<VisitaAgenda> = {}): VisitaAgenda {
  return {
    id: 7, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 4,
    os_id: 4, os_name: 'OS26-02', os_state: 'scheduled',
    partner_name: 'Hospital', city: 'São Luís',
    equipment_list: [], instrument_list: [], instrument_ids: [],
    tecnico_id: 441, tecnico_name: 'Afonso', is_mine: true,
    state: 'planned', overflow: false, editable: true, lock_reason: false,
    conflict: false, conflict_msg: '', note: '',
    ...over,
  }
}

const payload: AgendaPayload = {
  server_today: '2026-09-17',
  date_from: '2026-09-17',
  date_to: '2026-09-23',
  my_employee_id: 441,
  can_manage: true,
  visitas: [visita()],
}

let payloadAtual: AgendaPayload = payload

// Fix round 1 (achado 3a): o dublê original cravava `isLoading: false`
// sempre — nenhum teste do arquivo conseguia representar a 2ª busca (nova
// `queryKey`, nada em cache) em voo, que é exatamente o estado que o achado
// 1 mostrou vazando a grade meio vazia. `isLoadingAtual` deixa um teste
// simular isso sem tocar no resto do dublê.
let isLoadingAtual = false

// Fix round 2 (buraco estrutural apontado na review final): o dublê devolvia
// `error: null` incondicionalmente, então NENHUM teste deste arquivo
// alcançava o ramo de erro — e era exatamente lá que o modo Mês travava com
// spinner eterno colado na mensagem de falha. Erro representável é
// pré-requisito do teste do achado 1.
let erroAtual: Error | null = null

// Task 3: `instrumentoOptionsAtual` deixa cada teste controlar o
// `pwa_instrumento_options` que chega, e `mockUseInstrumentoOptions` (um
// `vi.fn` que preserva o argumento, mesmo raciocínio do `mockUseAgenda`
// acima) permite provar que o modo Mês liga o hook com `enabled=true`
// (brief 3a) sem depender de string mágica nenhuma.
let instrumentoOptionsAtual: InstrumentoOpcao[] = []

// Fix final (bloqueador I-1): o dublê devolvia `{ data }` PRONTO e nada mais —
// nenhum teste deste arquivo conseguia representar a query de instrumentos em
// voo ou em falha, que são exatamente os dois estados em que a tela se
// contradizia (grade dizendo `Instrumento #101`, seção do dia sumindo, sem
// nenhuma mensagem). `estadoInstrumentos` torna os três estados
// representáveis; o default é SETTLED, pra não jogar os ~20 testes do arquivo
// dentro do gate de carregamento novo.
type EstadoInstrumentos = 'ok' | 'pending' | 'error' | 'erro-com-cache'
let estadoInstrumentos: EstadoInstrumentos = 'ok'
const mockUseInstrumentoOptions = vi.fn((_enabled: boolean) => {
  if (estadoInstrumentos === 'pending') {
    return { data: undefined, isPending: true, isError: false }
  }
  if (estadoInstrumentos === 'error') {
    // react-query v5: no erro o status vira `error`, não `pending`.
    return { data: undefined, isPending: false, isError: true }
  }
  if (estadoInstrumentos === 'erro-com-cache') {
    // Refetch que falhou (foco de janela, ou depois do `staleTime`): `isError`
    // true MAS com o último catálogo bom ainda em `data`.
    return { data: instrumentoOptionsAtual, isPending: false, isError: true }
  }
  return { data: instrumentoOptionsAtual, isPending: false, isError: false }
})

// Mesmo raciocínio do `ModoSemana.test.tsx`: `vi.fn` que NÃO descarta os
// argumentos — é o que permite provar a faixa de datas pedida (`date_from`/
// `date_to` = grade[0]/grade[41]) e o `onlyMine`.
const mockUseAgenda = vi.fn(
  (_dateFrom: string | null, _dateTo: string | null, _onlyMine: boolean, _enabled: boolean) => (
    erroAtual
      ? { data: undefined, isLoading: false, error: erroAtual }
      : isLoadingAtual
        ? { data: undefined, isLoading: true, error: null }
        : { data: payloadAtual, isLoading: false, error: null }
  ),
)

vi.mock('@/lib/hooks/useAgenda', () => ({
  useAgendaDisponivel: () => ({ data: true }),
  useAgenda: (...args: [string | null, string | null, boolean, boolean]) => mockUseAgenda(...args),
  useUpdateVisita: () => ({ mutateAsync: mutateUpdate, isPending: false }),
  useCreateVisita: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteVisita: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useTecnicoOptions: () => ({ data: [{ id: 441, name: 'Afonso' }, { id: 9, name: 'Bruno' }] }),
  useOsOptions: () => ({ data: [] }),
  useInstrumentoOptions: (enabled: boolean) => mockUseInstrumentoOptions(enabled),
}))

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
  )
  return { qc, ...utils }
}

function irParaMes() {
  fireEvent.click(screen.getByRole('button', { name: /^Mês$/ }))
}

describe('Modo Mês', () => {
  beforeEach(() => {
    payloadAtual = payload
    isLoadingAtual = false
    erroAtual = null
    instrumentoOptionsAtual = []
    estadoInstrumentos = 'ok'
    mutateUpdate.mockReset().mockResolvedValue(visita())
    mockUseAgenda.mockClear()
    mockUseInstrumentoOptions.mockClear()
    espiaInstrumentosPorDia.mockClear()
    // Mesma razão do `ModoSemana.test.tsx`: o store é singleton (zustand +
    // persist) e vaza entre testes sem reset explícito.
    useTecnicoSettings.setState({ modoAgenda: 'lista', filterMine: true })
  })

  it('selecionar "Mês" renderiza a grade e o cabeçalho com o nome do mês', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())
    // 42 células da grade (6×7).
    expect(screen.getAllByRole('button', { name: /de (setembro|agosto|outubro)/ })).toHaveLength(42)
  })

  it('▶ avança um mês de calendário: cabeçalho muda e o fetch pede a faixa da grade de outubro', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Próximo período' }))

    await waitFor(() => expect(screen.getByText('outubro de 2026')).toBeInTheDocument())

    const gradeOutubro = gradeDoMes('2026-10-01')
    const ultimaChamada = mockUseAgenda.mock.calls.at(-1)
    expect(ultimaChamada?.[0]).toBe(gradeOutubro[0])
    expect(ultimaChamada?.[1]).toBe(gradeOutubro[41])
  })

  it('primeira carga do mês: 1ª busca sai sem datas, 2ª busca já traz a faixa completa da grade (brief 3c)', () => {
    montar()
    irParaMes()

    // As chamadas em modo mês são as com `onlyMine=false` — filtra fora a
    // chamada inicial em modo Lista, que não é o que este teste cobre.
    const chamadasMes = mockUseAgenda.mock.calls.filter((c) => c[2] === false)
    expect(chamadasMes.length).toBeGreaterThanOrEqual(2)

    // 1ª chamada em modo mês: `ancoraMes` ainda é `null`, então sai sem
    // datas — é o que deixa o servidor decidir a janela e devolver
    // `server_today`, único jeito de ancorar sem ler o relógio do aparelho.
    expect(chamadasMes[0]).toEqual([null, null, false, true])

    // O dublê é síncrono (sem gap real de rede), então a âncora já se
    // resolveu no mesmo ciclo de efeitos — mas a ÚLTIMA chamada em modo mês
    // precisa trazer a grade completa de setembro/2026, não a janela
    // default do servidor.
    const gradeSetembro = gradeDoMes('2026-09-01')
    const ultimaChamadaMes = chamadasMes.at(-1)
    expect(ultimaChamadaMes?.[0]).toBe(gradeSetembro[0])
    expect(ultimaChamadaMes?.[1]).toBe(gradeSetembro[41])
  })

  it('enquanto a faixa completa da grade está em voo (isLoading), mostra só o LoadingState — nunca a grade meio vazia (fix achado 1)', async () => {
    const { rerender, qc } = montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Simula a 2ª busca (ou qualquer navegação ◀▶, que troca a `queryKey`)
    // ainda em voo: nada em cache, `data` indefinido.
    isLoadingAtual = true
    rerender(<QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>)

    expect(screen.getByText('Carregando sua agenda...')).toBeInTheDocument()
    // Com o gate antigo (`mesCarregando = mes && ancoraMes === null`) a
    // grade renderizava aqui mesmo — 42 células vazias, sem anel de "hoje"
    // (`hoje` cairia em `null`), sob o spinner. É exatamente a "grade meio
    // vazia" que o brief 3c proíbe.
    expect(screen.queryAllByRole('button', { name: /de (setembro|agosto|outubro)/ })).toHaveLength(0)
  })

  it('"Só minhas" aparece desabilitado no modo mês e o fetch recebe onlyMine=false', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const filtro = screen.getByRole('checkbox') as HTMLInputElement
    expect(filtro.disabled).toBe(true)
    expect(filtro.checked).toBe(false)

    const ultimaChamada = mockUseAgenda.mock.calls.at(-1)
    expect(ultimaChamada?.[2]).toBe(false)
  })

  it('tocar num dia lista as visitas daquele dia; tocar num dia vazio mostra "Nenhuma visita neste dia."', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    expect(screen.getByText('OS26-02')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '18 de setembro, sem visitas' }))
    expect(screen.getByText('Nenhuma visita neste dia.')).toBeInTheDocument()
    expect(screen.queryByText('OS26-02')).toBeNull()
  })

  it('Gestor: selecionar visita para ajuste + tocar outro dia abre diálogo de confirmação; Confirmar chama pwa_visita_update com o date do destino', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^19 de setembro,/ }))

    // Não grava direto — abre a confirmação com as duas datas no texto.
    expect(mutateUpdate).not.toHaveBeenCalled()
    const dialogo = screen.getByRole('dialog', { name: 'Mudar data da visita' })
    expect(within(dialogo).getByText(
      'Tem certeza que deseja mudar a data da visita OS26-02 de 17/09/2026 para 19/09/2026?',
    )).toBeInTheDocument()

    fireEvent.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { date: '2026-09-19' } }),
    )
  })

  it('Cancelar no diálogo de confirmação não grava e mantém a visita armada', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^19 de setembro,/ }))

    const dialogo = screen.getByRole('dialog', { name: 'Mudar data da visita' })
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar' }))

    expect(mutateUpdate).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).toBeNull()
    // A visita continua armada — o Gestor precisa poder escolher outro dia
    // sem recomeçar.
    expect(screen.getByText(/Movendo a visita OS26-02/)).toBeInTheDocument()
  })

  it('tocar no mesmo dia em que a visita já está não abre diálogo', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(mutateUpdate).not.toHaveBeenCalled()
  })

  it('visita armada some do payload fecha o diálogo pendente de confirmação de data', async () => {
    const { rerender, qc } = montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^19 de setembro,/ }))
    expect(screen.getByRole('dialog', { name: 'Mudar data da visita' })).toBeInTheDocument()

    payloadAtual = { ...payload, visitas: [] }
    rerender(<QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>)

    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('mover para célula fora do mês grava e a vista acompanha o destino (a âncora avança para o mês do destino)', async () => {
    const { rerender, qc } = montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))

    // A grade de setembro/2026 transborda pro início de outubro (42 células,
    // sempre 6 semanas) — "3 de outubro" é uma célula "fora do mês"
    // clicável na mesma grade.
    fireEvent.click(screen.getByRole('button', { name: /^fora do mês, 3 de outubro,/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { date: '2026-10-03' } }),
    )
    // A âncora segue o destino mesmo sem esperar o refetch: é o `ajustar`
    // da página que avança `ancoraMes` logo após a gravação (ruling do
    // brief 3d) — sem isto, o card sairia da grade (mudou de mês) e a
    // seleção ficaria presa olhando pro mês errado.
    await waitFor(() => expect(screen.getByText('outubro de 2026')).toBeInTheDocument())

    // O ajuste encerra sozinho assim que a gravação de data (pelo diálogo)
    // teve sucesso — pedido do usuário, Task 1. A tarja já some antes do
    // refetch simulado abaixo.
    expect(screen.queryByText(/Movendo a visita/)).toBeNull()

    // Simula o refetch (real, depois do `onSuccess`) trazendo a visita já
    // com a data nova — o ajuste já está encerrado, então o card volta a
    // mostrar "Ajustar" (não "Concluir").
    payloadAtual = { ...payload, visitas: [visita({ date: '2026-10-03' })] }
    rerender(
      <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
    )
    // A âncora já avançou pra outubro (checado acima) — "3 de outubro"
    // agora é uma célula DENTRO do mês visível, sem o prefixo "fora do mês".
    expect(screen.getByRole('button', { name: /^3 de outubro,/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /^Ajustar$/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Concluir/ })).toBeNull()
  })

  it('foco não cai pro <body> depois de um "Confirmar" que muda de mês — vai pra barra de navegação de período (a tarja já encerrou junto com o ajuste, Task 1)', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    // Mesma célula "fora do mês" do teste acima — cruza pra outubro.
    fireEvent.click(screen.getByRole('button', { name: /^fora do mês, 3 de outubro,/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { date: '2026-10-03' } }),
    )
    // A troca de mês é o gatilho do bug: o `BottomSheet` do diálogo já
    // devolveu o foco, síncrono, pra célula de "3 de outubro" ao fechar —
    // mas essa célula pertencia à grade de SETEMBRO (a de outubro é a
    // versão "fora do mês", célula DIFERENTE da versão "dentro do mês" que
    // a grade de outubro desenha). Assim que a âncora avança, a célula que
    // tinha o foco desmonta.
    await waitFor(() => expect(screen.getByText('outubro de 2026')).toBeInTheDocument())

    // A tarja não é mais o alvo: ela encerra junto com o ajuste (Task 1) no
    // MESMO lote de estado que troca de mês, então focar nela só adiaria a
    // queda pro `<body>`. O alvo estável agora é a barra de navegação de
    // período — sempre montada, nunca rechaveada por data.
    expect(screen.queryByText(/Movendo a visita/)).toBeNull()
    const barraNavegacao = screen.getByText('outubro de 2026').closest('div') as HTMLElement
    // Pina o nó certo: sem isto, `toHaveFocus()` sozinho poderia passar por
    // uma resolução de `closest('div')` acidentalmente diferente do nó que
    // carrega `navegacaoRef` — o `tabIndex={-1}` é exclusivo dele.
    expect(barraNavegacao).toHaveAttribute('tabindex', '-1')
    expect(barraNavegacao).toHaveFocus()
  })

  it('não-gestor (can_manage: false) não vê o gesto de ajuste', async () => {
    // Fix round 1 (achado 2): o payload original acoplava `can_manage:
    // false` com `editable: false` — combinação real (o servidor amarra os
    // dois, `tests/test_pwa_agenda.py:205-207`), mas que faz o `VisitaCard`
    // cair no ramo travado só por causa de `editable`, sem nenhuma
    // dependência de `onAjustar`/`podeAjustar`. Trocar
    // `podeAjustar={!!data?.can_manage}` por um `true` cravado no código
    // passava por esse teste do mesmo jeito — ele não provava nada sobre a
    // fiação que diz testar.
    //
    // Aqui forçamos `editable: true` deliberadamente (payload que o
    // servidor de verdade não produziria) só pra isolar o que SÓ
    // `podeAjustar` controla: com `editable: true` o card cai no ramo
    // normal (mostra o corpo, o `onSelect`), e o único jeito de "Ajustar"
    // sumir é `onAjustar` chegar `undefined` — que é exatamente o que
    // `podeAjustar={false}` produz em `_VistaMes.tsx`.
    payloadAtual = { ...payload, can_manage: false, visitas: [visita({ editable: true })] }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Card no ramo NORMAL (prova que não é o achado travado por `editable`
    // escondendo o botão).
    expect(screen.getByText('OS26-02')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Ajustar$/ })).toBeNull()
  })

  it('ao abrir o mês sem seleção prévia, o dia default é "hoje" (server_today), não o dia 1 do mês', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // `server_today` do payload é 2026-09-17 — precisa nascer selecionado
    // (e mostrando a visita do dia), não o dia 1 vazio (fix round 1,
    // achado 4: antes da correção, o anel de "hoje" marcava o 17 mas o
    // fundo de seleção e a lista de cards ficavam no dia 1, "Nenhuma
    // visita neste dia.", com dois dias marcados ao mesmo tempo).
    expect(screen.getByRole('button', { name: /^17 de setembro,/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('OS26-02')).toBeInTheDocument()
  })

  it('legenda mostra só técnico com visita na janela (Bruno, sem visita, fica de fora), mais "Sem técnico" quando há visita sem tecnico_id', async () => {
    payloadAtual = {
      ...payload,
      visitas: [
        visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso' }),
        visita({ id: 8, date: '2026-09-18', tecnico_id: false, tecnico_name: '' }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Chip de "Afonso" (tem visita na janela) e "Sem técnico" (visita sem
    // tecnico_id) — nenhum dos dois vem de texto de card, já que o dia
    // selecionado por default (hoje, 17) só mostra a visita do Afonso no
    // corpo do card, nunca a palavra "Sem técnico". Escopado ao `group`
    // "Técnicos:" (fix round 1, achado 3): prova que o rótulo está
    // programaticamente ligado à lista via `aria-labelledby`, não só
    // presente em algum lugar da tela.
    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    expect(within(grupoTecnicos).getByText('Afonso')).toBeInTheDocument()
    expect(within(grupoTecnicos).getByText('Sem técnico')).toBeInTheDocument()
    // "Bruno" está no roster (mock de useTecnicoOptions) mas não tem
    // nenhuma visita na janela — não pode virar chip (brief 3d: "não o
    // roster inteiro, 20 chips de gente sem visita é ruído").
    expect(within(grupoTecnicos).queryByText('Bruno')).toBeNull()
  })

  // --- fix round 1: legenda cobre a JANELA de 42 dias, não o mês estrito ---

  it('legenda inclui técnico e instrumento de um dia de transbordo (fora do mês estrito, dentro da janela de 42 dias)', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    // A grade de setembro/2026 vai de 2026-08-30 a 2026-10-10 (42 dias) —
    // "2026-10-05" está fora do mês estrito, mas dentro da janela visível.
    // Se a fonte das legendas fosse trocada por algo filtrado ao mês
    // estrito (ex. `noMes`), este teste quebra; antes desta correção,
    // nenhum teste provava esse limite.
    payloadAtual = {
      ...payload,
      visitas: [visita({
        id: 7, date: '2026-10-05', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
      })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    expect(within(grupoTecnicos).getByText('Afonso')).toBeInTheDocument()
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    expect(within(grupoInstrumentos).getByText('Q001')).toBeInTheDocument()
  })

  // --- fix round 2, achado 1: erro de rede no modo Mês ---

  it('erro na primeira abertura do mês mostra SÓ o erro — sem spinner eterno e sem grade', async () => {
    erroAtual = new Error('Failed to fetch')
    montar()
    irParaMes()

    await waitFor(() =>
      expect(screen.getByText(/Erro ao carregar a agenda/)).toBeInTheDocument(),
    )
    // Sem `data`, o `useEffect` de ancoragem nunca roda e `ancoraMes` fica
    // `null` para sempre: o gate antigo (`mes && (ancoraMes === null ||
    // isLoading)`) ficava `true` para sempre junto, e a tela mostrava
    // spinner E erro ao mesmo tempo, indefinidamente — só sair do modo
    // resolvia.
    expect(screen.queryByText('Carregando sua agenda...')).toBeNull()
    // E o remédio não pode abrir o buraco simétrico: com `mesCarregando`
    // agora `false`, a grade não pode vazar meio vazia (42 células sem
    // âncora) por baixo da mensagem de erro.
    expect(
      screen.queryAllByRole('button', { name: /de (setembro|agosto|outubro)/ }),
    ).toHaveLength(0)
    expect(screen.queryByText('Nenhuma visita neste dia.')).toBeNull()
  })

  // --- fix round 2, achado 2: visita armada invisível fora do dia selecionado ---

  it('visita armada continua anunciada ao navegar de mês, e o toque num dia do novo mês NÃO grava', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    expect(screen.getByText(/Movendo a visita OS26-02/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Próximo período' }))
    await waitFor(() => expect(screen.getByText('outubro de 2026')).toBeInTheDocument())

    // O único indicador de "tem visita armada" era o anel + "Concluir"
    // DENTRO do VisitaCard, que só existe se a visita cair no dia
    // selecionado. Em outubro o card não é renderizado, e sem a tarja a tela
    // não dizia mais nada sobre o ajuste em curso.
    expect(screen.getByText(/Movendo a visita OS26-02/)).toBeInTheDocument()

    mutateUpdate.mockClear()
    fireEvent.click(screen.getByRole('button', { name: /^20 de outubro,/ }))
    // A armadilha de 3 toques: o Gestor tocava 20/out só pra ver o dia e a
    // visita era reagendada um mês adiante, em silêncio.
    expect(mutateUpdate).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /^20 de outubro,/ })).toHaveAttribute('aria-pressed', 'true')

    // E há saída explícita, sem depender do card do dia certo.
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByText(/Movendo a visita/)).toBeNull()
  })

  it('visita armada na Semana continua anunciada depois de trocar para o Mês', async () => {
    montar()
    fireEvent.click(screen.getByRole('button', { name: /^Semana$/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    expect(screen.getByText(/Movendo a visita OS26-02/)).toBeInTheDocument()

    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // A mesma armadilha atravessa modos: a tarja mora FORA dos ramos de
    // modo justamente por isso.
    expect(screen.getByText(/Movendo a visita OS26-02/)).toBeInTheDocument()
  })

  it('tarja "Movendo a visita" fica fixa no topo da área de rolagem enquanto o ajuste está armado', async () => {
    // Bug medido a 390px: o botão "Ajustar" mora no `VisitaCard`, ABAIXO da
    // grade — no celular, quando o técnico arma o ajuste, a tarja nasce num
    // ponto da página já rolado pra fora da viewport (`top: -173px` medido).
    // `sticky top-0` no mesmo container que já sustenta o cabeçalho do dia em
    // modo Lista (`<main overflow-auto>`) resolve — sem isso, este teste
    // falha porque a tarja não carrega nenhuma classe de fixação.
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))

    const tarja = screen.getByText(/Movendo a visita/).closest('div') as HTMLElement
    expect(tarja.className).toMatch(/\bsticky\b/)
    expect(tarja.className).toMatch(/\btop-0\b/)
    // Pedido do usuário: borda no token `--info` (nunca cor crua) pra chamar
    // mais atenção pra tarja.
    expect(tarja.className).toMatch(/\bborder-info\b/)
  })

  it('gravação de data que FALHA no diálogo de confirmação (Mês) mantém a visita armada e mostra o erro — o encerramento automático é só no sucesso', async () => {
    mutateUpdate.mockRejectedValueOnce(
      new Error('Não é possível programar uma visita para uma data passada'),
    )
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^19 de setembro,/ }))
    const dialogo = screen.getByRole('dialog', { name: 'Mudar data da visita' })
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() => expect(screen.getByText(/data passada/)).toBeInTheDocument())
    // A visita continua armada — a falha não pode encerrar o ajuste; o
    // Gestor precisa poder tentar outro dia sem recomeçar.
    expect(screen.getByText(/Movendo a visita/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Concluir/ })).toBeInTheDocument()
  })

  it('sem ajuste armado, a tarja "Movendo a visita" não existe (nada fixo fantasma cobrindo a grade)', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())
    expect(screen.queryByText(/Movendo a visita/)).toBeNull()
  })

  // --- Task 3: legenda e lista do dia de instrumentos ---

  it('useInstrumentoOptions é habilitado no modo Mês', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    expect(mockUseInstrumentoOptions).toHaveBeenCalledWith(true)
  })

  it('legenda mostra o instrumento usado na janela e não mostra o instrumento das opções que ninguém usa', async () => {
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    // A visita usa só Q001, e cai num dia DIFERENTE do selecionado por
    // default (hoje, 17) — isola a legenda (janela inteira) da seção do
    // dia (só o dia selecionado), que este teste não cobre.
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-20', instrument_ids: [101] })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // A faixa carrega um rótulo textual próprio ("Instrumentos:") ligado
    // programaticamente ao grupo via `role="group"` + `aria-labelledby` —
    // escopar por ele prova a ligação, não só que o texto existe em algum
    // lugar da tela (fix round 1, achado 3). O rótulo em si é ganho de
    // clareza de domínio (distingue as duas faixas), não correção de a11y
    // por item: cada chip já carrega o nome em texto puro.
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    expect(within(grupoInstrumentos).getByText('Q001')).toBeInTheDocument()
    expect(within(grupoInstrumentos).queryByText('Q002')).toBeNull()
  })

  it('legenda de instrumentos vem ordenada por nome, não pela ordem de aparição na janela', async () => {
    instrumentoOptionsAtual = [
      { id: 101, name: 'Zebra', validade: '2027-01-01' },
      { id: 102, name: 'Abelha', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        // "Zebra" aparece PRIMEIRO cronologicamente na janela (05/09);
        // "Abelha" só aparece depois (20/09). Ordem de aparição colocaria
        // Zebra antes de Abelha — a ordem alfabética exige o inverso (fix
        // round 1, achado 2).
        visita({ id: 7, date: '2026-09-05', instrument_ids: [101] }),
        visita({ id: 8, date: '2026-09-20', instrument_ids: [102] }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    const nomes = within(grupoInstrumentos)
      .getAllByText(/^(Zebra|Abelha)$/)
      .map((el) => el.textContent)
    expect(nomes).toEqual(['Abelha', 'Zebra'])
  })

  it('sem instrumento usado na janela, a faixa de instrumentos não é renderizada', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    // Payload default: a única visita não usa nenhum instrumento
    // (`instrument_ids: []`).
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    expect(screen.queryByText('Q001')).toBeNull()
    expect(screen.queryByRole('group', { name: 'Instrumentos:' })).toBeNull()
  })

  it('tocar num dia com instrumento mostra a seção "Instrumentos do dia" com nome, OS e faixa de horário', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    payloadAtual = {
      ...payload,
      visitas: [visita({
        id: 7, date: '2026-09-20', instrument_ids: [101],
        time_start: 8, time_stop: 12, os_name: 'OS26-02', tecnico_name: 'Afonso',
      })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^20 de setembro,/ }))

    // O `VisitaCard` do dia também mostra "08:00–12:00" e "OS26-02" no
    // corpo — escopar a busca à seção evita casar com o card em vez da
    // seção de instrumentos.
    const titulo = screen.getByText('Instrumentos do dia')
    const secao = titulo.closest('div') as HTMLElement
    expect(within(secao).getByText('Q001')).toBeInTheDocument()
    expect(within(secao).getByText(/08:00–12:00/)).toBeInTheDocument()
    expect(within(secao).getByText(/OS26-02\/Afonso/)).toBeInTheDocument()
  })

  it('tocar num dia sem instrumento não mostra a seção "Instrumentos do dia"', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-20', instrument_ids: [101] })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Dia selecionado por default é "hoje" (17), sem instrumento.
    expect(screen.queryByText('Instrumentos do dia')).toBeNull()

    // Tocar num dia vazio (18) também não mostra a seção.
    fireEvent.click(screen.getByRole('button', { name: /^18 de setembro,/ }))
    expect(screen.queryByText('Instrumentos do dia')).toBeNull()
  })

  it('nenhum texto de "vencido" aparece, mesmo com validade vencida — guarda do escopo acordado', async () => {
    instrumentoOptionsAtual = [
      // Validade no passado: se algum código reintroduzisse o aviso de
      // certificado vencido, este seria o caso que o dispararia.
      { id: 101, name: 'Q001', validade: '2020-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-20', instrument_ids: [101] })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^20 de setembro,/ }))
    expect(screen.getByText('Instrumentos do dia')).toBeInTheDocument()

    expect(screen.queryByText(/vencid/i)).toBeNull()
  })
  // --- fix final, bloqueador I-1: grade, legenda e lista do dia lendo a
  // mesma fonte, e falha do catálogo de instrumentos visível ---

  it('catálogo de instrumentos em falha: a falha é VISÍVEL e nenhum identificador fabricado é apresentado como nome', async () => {
    estadoInstrumentos = 'error'
    // A visita USA um instrumento: sem isto não haveria nome fabricado para
    // suprimir e o teste passaria mesmo antes da correção.
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', instrument_ids: [101] })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // 1. A falha é dita em pt-BR, não engolida.
    expect(screen.getByText(/Erro ao carregar os instrumentos/)).toBeInTheDocument()

    // 2. Nenhum `Instrumento #101` em lugar nenhum: nem como chip de legenda,
    //    nem no texto da tela. Antes da correção, `instrumentos.data`
    //    indefinido fazia TODO instrumento usado virar um identificador
    //    fabricado apresentado como fato.
    expect(screen.queryByText(/Instrumento #/)).toBeNull()

    // 3. E ele também não vaza pelos 42 `aria-label` das células.
    const celulas = screen.getAllByRole('button', { name: /de (setembro|agosto|outubro)/ })
    expect(celulas.some((c) => (c.getAttribute('aria-label') ?? '').includes('Instrumento #'))).toBe(false)

    // 4. As três superfícies concordam em não afirmar nada: sem faixa de
    //    legenda e sem seção do dia — e não uma dizendo que o dia tem
    //    instrumento enquanto a outra some.
    expect(screen.queryByRole('group', { name: 'Instrumentos:' })).toBeNull()
    expect(screen.queryByText('Instrumentos do dia')).toBeNull()

    // 5. O resto do mês continua utilizável (degrada como a dos técnicos).
    expect(screen.getByRole('group', { name: 'Técnicos:' })).toBeInTheDocument()
    expect(screen.getByText('OS26-02')).toBeInTheDocument()
  })

  it('catálogo de instrumentos ainda em voo: segura o LoadingState em vez de mostrar a grade com nomes que vão pular', async () => {
    estadoInstrumentos = 'pending'
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', instrument_ids: [101] })],
    }
    montar()
    irParaMes()

    // As duas buscas saem em paralelo na primeira abertura; se a do catálogo
    // resolve depois, a grade aparecia com `Instrumento #101` e os nomes
    // trocavam sozinhos em seguida.
    expect(screen.getByText('Carregando sua agenda...')).toBeInTheDocument()
    expect(screen.queryAllByRole('button', { name: /de (setembro|agosto|outubro)/ })).toHaveLength(0)
    expect(screen.queryByText(/Instrumento #/)).toBeNull()
  })

  it('instrumento usado mas ausente das opções (arquivado): grade, legenda e seção do dia concordam', async () => {
    // Só o 102 está no catálogo; o 101 foi arquivado depois de usado
    // (`pwa_instrumento_options` faz `search([])`, com `active_test` ligado),
    // então continua em `instrument_ids` e some das opções.
    instrumentoOptionsAtual = [{ id: 102, name: 'Q002', validade: '2027-01-01' }]
    payloadAtual = {
      ...payload,
      visitas: [visita({
        id: 7, date: '2026-09-17', instrument_ids: [101, 102],
        time_start: 8, time_stop: 12, os_name: 'OS26-02', tecnico_name: 'Afonso',
      })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Legenda (metade 1) — deriva da união do que é usado.
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    expect(within(grupoInstrumentos).getByText('Q002')).toBeInTheDocument()
    expect(within(grupoInstrumentos).getByText('Instrumento #101')).toBeInTheDocument()

    // Célula (a mesma fonte da legenda).
    expect(
      screen.getByRole('button', { name: /^17 de setembro,.*Instrumento #101/ }),
    ).toBeInTheDocument()

    // Seção "Instrumentos do dia" (metade 2) — antes da correção ela mapeava
    // sobre o catálogo (a INTERSEÇÃO) e o 101 sumia: a grade afirmava que o
    // dia tem o instrumento e a lista negava.
    const secao = screen.getByText('Instrumentos do dia').closest('div') as HTMLElement
    expect(within(secao).getByText('Q002')).toBeInTheDocument()
    expect(within(secao).getByText('Instrumento #101')).toBeInTheDocument()
    expect(within(secao).getAllByText(/08:00–12:00/)).toHaveLength(2)
  })

  it('legenda e célula listam os instrumentos na MESMA ordem, com colação numérica (TAG-2 antes de TAG-10)', async () => {
    instrumentoOptionsAtual = [
      { id: 1, name: 'TAG-10', validade: '2027-01-01' },
      { id: 2, name: 'TAG-2', validade: '2027-01-01' },
      { id: 3, name: 'TAG-3', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', instrument_ids: [1, 2, 3] })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    const nomesLegenda = within(grupoInstrumentos)
      .getAllByText(/^TAG-\d+$/)
      .map((el) => el.textContent)
    expect(nomesLegenda).toEqual(['TAG-2', 'TAG-3', 'TAG-10'])

    // A célula (via `aria-label`, a fonte de verdade do que ela desenha) tem
    // de listar na MESMA sequência — a ordem também decide quais triângulos
    // sobrevivem quando a célula corta por lotação.
    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(celula.getAttribute('aria-label')).toContain('instrumentos: TAG-2, TAG-3, TAG-10')
  })
  it('refetch do catálogo falha mas o catálogo anterior continua em cache: nada é blanqueado e nenhuma tarja aparece', async () => {
    estadoInstrumentos = 'erro-com-cache'
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', instrument_ids: [101] })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // O catálogo bom está na mão: não há nome fabricado pra suprimir, e tirar
    // os triângulos/legenda/lista por causa de uma falha de fundo passageira
    // seria remover informação correta da tela.
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    expect(within(grupoInstrumentos).getByText('Q001')).toBeInTheDocument()
    const secao = screen.getByText('Instrumentos do dia').closest('div') as HTMLElement
    expect(within(secao).getByText('Q001')).toBeInTheDocument()

    // E a tarja seria ruído: nada está faltando pro usuário.
    expect(screen.queryByText(/Erro ao carregar os instrumentos/)).toBeNull()
  })

  it('agenda e catálogo falhando juntos (sessão expirada): só a tarja da agenda, sem a segunda falando de uma grade que não existe', async () => {
    erroAtual = new Error('Failed to fetch')
    estadoInstrumentos = 'error'
    montar()
    irParaMes()

    await waitFor(() =>
      expect(screen.getByText(/Erro ao carregar a agenda/)).toBeInTheDocument(),
    )
    // A `VistaMes` nem é renderizada quando a agenda falha — uma tarja falando
    // de triângulos e lista do dia de uma grade ausente é ruído puro.
    expect(screen.queryByText(/Erro ao carregar os instrumentos/)).toBeNull()
  })

  // --- Task 2: badges de filtro nas duas faixas de legenda ---

  it('desligar um técnico tira a bolinha dele das células e o aria-label deixa de citá-lo', async () => {
    payloadAtual = {
      ...payload,
      visitas: [
        visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso' }),
        visita({ id: 8, date: '2026-09-17', tecnico_id: 9, tecnico_name: 'Bruno' }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Os dois nomes começam citados no mesmo dia (dois técnicos, mesma data).
    expect(
      screen.getByRole('button', { name: /^17 de setembro,.*Afonso.*Bruno/ }),
    ).toBeInTheDocument()

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    fireEvent.click(within(grupoTecnicos).getByRole('button', { name: 'Afonso' }))

    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(celula.getAttribute('aria-label')).not.toContain('Afonso')
    expect(celula.getAttribute('aria-label')).toContain('Bruno')
  })

  it('desligar um técnico não tira o VisitaCard dele do dia selecionado nem a seção "Instrumentos do dia"', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    payloadAtual = {
      ...payload,
      visitas: [visita({
        id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
      })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    fireEvent.click(within(grupoTecnicos).getByRole('button', { name: 'Afonso' }))

    // A bolinha some da célula...
    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(celula.getAttribute('aria-label')).not.toContain('Afonso')
    // ...mas o card e a seção "Instrumentos do dia" continuam mostrando a
    // visita (o filtro altera SÓ as marcas da grade — brief).
    expect(screen.getByText('OS26-02')).toBeInTheDocument()
    const secao = screen.getByText('Instrumentos do dia').closest('div') as HTMLElement
    expect(within(secao).getByText('Q001')).toBeInTheDocument()
  })

  it('interseção: com um instrumento selecionado, a visita de outro técnico que não usa aquele instrumento perde as marcas', async () => {
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        visita({
          id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
        }),
        visita({
          id: 8, date: '2026-09-17', tecnico_id: 9, tecnico_name: 'Bruno', instrument_ids: [102],
        }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Desliga Q002: a faixa de instrumentos fica restrita a Q001.
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    fireEvent.click(within(grupoInstrumentos).getByRole('button', { name: /Q002/ }))

    // Nenhum técnico foi tocado — mas Bruno (só usa Q002) some das marcas do
    // dia, porque sua visita não intersecta a faixa de instrumentos restrita.
    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(celula.getAttribute('aria-label')).toContain('Afonso')
    expect(celula.getAttribute('aria-label')).not.toContain('Bruno')
    // O TRIÂNGULO também é filtrado, não só a bolinha: `pontosInstrumentoGrade`
    // é código novo sem cobertura própria — sem esta asserção, Q002
    // continuando no trecho "; instrumentos: ..." passaria batido.
    expect(celula.getAttribute('aria-label')).toContain('Q001')
    expect(celula.getAttribute('aria-label')).not.toContain('Q002')
  })

  it('camada 2: UMA visita com dois instrumentos, um deles desligado, desenha só o triângulo do ligado', async () => {
    // Bug relatado pelo user: diferente do teste de interseção acima (cada
    // visita usa UM instrumento só, e a camada 1 já basta pra sumir com
    // ela inteira), aqui a MESMA visita usa os dois — sobrevive à camada 1
    // (tem ao menos um instrumento ligado), mas `pontosInstrumentoGrade`
    // não filtrava os instrumentos dela própria, e o desligado continuava
    // virando triângulo e citado no aria-label.
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        visita({
          id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso',
          instrument_ids: [101, 102],
        }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Desliga Q001 — a visita continua valendo pela camada 1 (ainda usa
    // Q002, que está ligado).
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    fireEvent.click(within(grupoInstrumentos).getByRole('button', { name: /Q001/ }))

    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    const label = celula.getAttribute('aria-label') ?? ''
    // A visita (Afonso) continua — camada 1 não mexe nisso.
    expect(label).toContain('Afonso')
    // Mas o Q001 desligado não pode aparecer mais — nem o triângulo (via
    // `data-testid="triangulo"`), nem o aria-label.
    expect(label).toContain('Q002')
    expect(label).not.toContain('Q001')
    expect(within(celula).queryAllByTestId('triangulo')).toHaveLength(1)
  })

  it('a legenda e a seção "Instrumentos do dia" continuam listando os dois instrumentos mesmo com um desligado na grade', async () => {
    // NÃO pode regredir: a legenda (pra dar pra religar) e a seção do dia
    // (que é sempre não-filtrada, por brief) usam `pontosInstrumentoJanela`,
    // que este fix não pode tocar.
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        visita({
          id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso',
          instrument_ids: [101, 102],
        }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    fireEvent.click(within(grupoInstrumentos).getByRole('button', { name: /Q001/ }))

    // Legenda continua com os dois chips (Q001 desligado, mas presente).
    expect(within(grupoInstrumentos).getByText('Q001')).toBeInTheDocument()
    expect(within(grupoInstrumentos).getByText('Q002')).toBeInTheDocument()

    // Seção "Instrumentos do dia" do dia selecionado (17, default via
    // server_today) — não filtrada, lista os dois.
    const titulo = screen.getByText('Instrumentos do dia')
    const secao = titulo.closest('div') as HTMLElement
    expect(within(secao).getByText('Q001')).toBeInTheDocument()
    expect(within(secao).getByText('Q002')).toBeInTheDocument()
  })

  it('não-regressão: sem nenhuma restrição de instrumento ativa, uma visita com dois instrumentos continua desenhando os dois', async () => {
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        visita({
          id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso',
          instrument_ids: [101, 102],
        }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    const label = celula.getAttribute('aria-label') ?? ''
    expect(label).toContain('Q001')
    expect(label).toContain('Q002')
    expect(within(celula).queryAllByTestId('triangulo')).toHaveLength(2)
  })

  it('consequência aceita: com a faixa de instrumentos restrita, a visita sem instrumento nenhum perde a bolinha do técnico', async () => {
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        // Sem instrumento nenhum — o alvo desta consequência.
        visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [] }),
        // Mesmo dia, usa Q001 — permanece dentro da faixa restrita.
        visita({ id: 8, date: '2026-09-17', tecnico_id: 9, tecnico_name: 'Bruno', instrument_ids: [101] }),
        // Em outro dia, só pra Q002 entrar na legenda da janela.
        visita({ id: 9, date: '2026-09-20', tecnico_id: 9, tecnico_name: 'Bruno', instrument_ids: [102] }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Restringe a faixa de instrumentos a Q001 (desliga Q002).
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    fireEvent.click(within(grupoInstrumentos).getByRole('button', { name: /Q002/ }))

    // O técnico da visita sem instrumento (Afonso) nunca foi tocado — mesmo
    // assim some da célula, porque a visita não tem instrumento nenhum para
    // intersectar a faixa restrita. Bruno (usa Q001) continua.
    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(celula.getAttribute('aria-label')).not.toContain('Afonso')
    expect(celula.getAttribute('aria-label')).toContain('Bruno')
  })

  it('catálogo de instrumentos cai em falha com uma restrição de instrumento já armada: a faixa some, e a restrição para de suprimir as bolinhas de técnico', async () => {
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        visita({
          id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
        }),
        visita({
          id: 8, date: '2026-09-17', tecnico_id: 9, tecnico_name: 'Bruno', instrument_ids: [102],
        }),
      ],
    }
    const { rerender, qc } = montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Restringe a instrumentos a Q001 — Bruno (só usa Q002) some das marcas
    // (mesmo mecanismo do teste de interseção acima).
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    fireEvent.click(within(grupoInstrumentos).getByRole('button', { name: /Q002/ }))
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).not.toContain('Bruno')

    // O catálogo cai em falha SEM cache (achado da review desta task): a
    // faixa "Instrumentos:" inteira some — "Todos" incluído — e não haveria
    // mais controle pra limpar a restrição que já estava armada.
    estadoInstrumentos = 'error'
    rerender(<QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>)

    expect(screen.getByText(/Erro ao carregar os instrumentos/)).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Instrumentos:' })).toBeNull()
    // A restrição parou de suprimir: as duas bolinhas voltam a aparecer —
    // sem isto, Bruno ficaria escondido sem nenhum jeito de religá-lo.
    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(celula.getAttribute('aria-label')).toContain('Afonso')
    expect(celula.getAttribute('aria-label')).toContain('Bruno')
  })

  it('restringir instrumentos e navegar para um mês sem NENHUMA visita instrumentada: a faixa continua com "Todos" visível, e a restrição do mês anterior não suprime as marcas de lá (achado 1, fix round 1)', async () => {
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        visita({
          id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
        }),
        visita({
          id: 8, date: '2026-09-17', tecnico_id: 9, tecnico_name: 'Bruno', instrument_ids: [102],
        }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Restringe a Q001 — antes de navegar, mesma mecânica dos testes acima.
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    fireEvent.click(within(grupoInstrumentos).getByRole('button', { name: /Q002/ }))
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).not.toContain('Bruno')

    // Outubro: uma visita, NENHUM instrumento usado em lugar nenhum da
    // janela — sem catálogo em falha, só um mês onde a faixa não tem nada
    // pra mostrar (`legendaInstrumentos` fica `[]` igual à falha, mas por
    // outro motivo).
    payloadAtual = {
      ...payload,
      visitas: [visita({
        id: 9, date: '2026-10-05', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [],
      })],
    }
    fireEvent.click(screen.getByRole('button', { name: 'Próximo período' }))
    await waitFor(() => expect(screen.getByText('outubro de 2026')).toBeInTheDocument())

    // A faixa "Instrumentos:" continua na tela com "Todos" — mesmo sem
    // nenhum chip de item pra mostrar — porque `instrumentosSel` ainda não
    // é `null` (o Gestor nunca tocou "Todos"); sem isto a restrição de
    // setembro ficaria escondida e sem controle nenhum pra limpar.
    const grupoInstrumentosOutubro = screen.getByRole('group', { name: 'Instrumentos:' })
    const badgeTodosOutubro = within(grupoInstrumentosOutubro).getByRole('button', { name: 'Todos os instrumentos' })
    expect(badgeTodosOutubro).toHaveAttribute('aria-pressed', 'false')

    // E a restrição de Q001/Q002 — que não tem contra o que ser aplicada
    // num mês sem nenhum instrumento usado — não suprime a bolinha de
    // Afonso em outubro.
    expect(
      screen.getByRole('button', { name: /^5 de outubro,/ }).getAttribute('aria-label'),
    ).toContain('Afonso')
  })

  it('as duas faixas restritas ao mesmo tempo combinam por interseção (E), não união', async () => {
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    payloadAtual = {
      ...payload,
      visitas: [
        // Afonso + Q001: bate as duas faixas restritas — deve sobreviver.
        visita({
          id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
        }),
        // Afonso + Q002: técnico bate, instrumento não — some.
        visita({
          id: 8, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [102],
        }),
        // Bruno + Q001: instrumento bate, técnico não — some.
        visita({
          id: 9, date: '2026-09-17', tecnico_id: 9, tecnico_name: 'Bruno', instrument_ids: [101],
        }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Restringe técnico a Afonso (desliga Bruno)...
    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    fireEvent.click(within(grupoTecnicos).getByRole('button', { name: 'Bruno' }))
    // ...e instrumento a Q001 (desliga Q002).
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    fireEvent.click(within(grupoInstrumentos).getByRole('button', { name: /Q002/ }))

    // União deixaria as três visitas (qualquer uma bate uma das duas
    // faixas); interseção só deixa a 7 (Afonso E Q001).
    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    const label = celula.getAttribute('aria-label') ?? ''
    expect(label).toContain('1 visita')
    expect(label).toContain('Afonso')
    expect(label).not.toContain('Bruno')
    expect(label).toContain('Q001')
    expect(label).not.toContain('Q002')
  })

  it('os dois badges "Todos" têm nomes acessíveis distintos, um por faixa', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    payloadAtual = {
      ...payload,
      visitas: [visita({
        id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
      })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Busca no escopo da TELA, não dentro do grupo: `getByRole` falha se
    // houver mais de um botão com o mesmo nome — é essa ambiguidade que o
    // teste guarda. O `role="group"` + `aria-labelledby` já separava as duas
    // faixas na leitura em FLUXO, mas a navegação por LISTA de botões (o
    // rotor do leitor de tela) anuncia só o nome, e eram dois "Todos"
    // indistinguíveis na mesma tela.
    const todosTecnicos = screen.getByRole('button', { name: 'Todos os técnicos' })
    const todosInstrumentos = screen.getByRole('button', { name: 'Todos os instrumentos' })
    expect(
      within(screen.getByRole('group', { name: 'Técnicos:' }))
        .getByRole('button', { name: 'Todos os técnicos' }),
    ).toBe(todosTecnicos)
    expect(
      within(screen.getByRole('group', { name: 'Instrumentos:' }))
        .getByRole('button', { name: 'Todos os instrumentos' }),
    ).toBe(todosInstrumentos)

    // O texto VISÍVEL continua o "Todos" curto: a faixa é estreita e o
    // rótulo do grupo está do lado. O nome longo é só para quem lê o botão
    // fora do contexto dele.
    expect(todosTecnicos).toHaveTextContent('Todos')
    expect(todosInstrumentos).toHaveTextContent('Todos')
  })

  it('desligar todos os chips de uma faixa sem usar "Todos" deixa um Set vazio (não null): nada passa naquela camada, mas "Todos" continua visível como saída', async () => {
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso' })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Único técnico da janela é Afonso — desligá-lo (sem tocar "Todos")
    // deixa `tecnicosSel` num `Set` vazio, não `null`.
    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    fireEvent.click(within(grupoTecnicos).getByRole('button', { name: 'Afonso' }))

    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).not.toContain('Afonso')
    // A saída continua lá, ligável a qualquer momento.
    const badgeTodos = within(grupoTecnicos).getByRole('button', { name: 'Todos os técnicos' })
    expect(badgeTodos).toBeInTheDocument()
    expect(badgeTodos).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(badgeTodos)
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).toContain('Afonso')
  })

  it('"Todos" restaura a faixa e o próprio badge reflete aria-pressed corretamente', async () => {
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso' })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    const badgeTodos = within(grupoTecnicos).getByRole('button', { name: 'Todos os técnicos' })
    expect(badgeTodos).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(within(grupoTecnicos).getByRole('button', { name: 'Afonso' }))
    expect(badgeTodos).toHaveAttribute('aria-pressed', 'false')
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).not.toContain('Afonso')

    fireEvent.click(badgeTodos)
    expect(badgeTodos).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).toContain('Afonso')
  })

  it('badge desligado continua na faixa — dá para religar', async () => {
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso' })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupoTecnicos).getByRole('button', { name: 'Afonso' })
    fireEvent.click(chipAfonso)
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'false')
    // O botão continua na faixa (legível sem cor, via aria-pressed) — não
    // some da tela só porque foi desligado.
    expect(within(grupoTecnicos).getByRole('button', { name: 'Afonso' })).toBeInTheDocument()

    fireEvent.click(chipAfonso)
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).toContain('Afonso')
  })

  it('com as duas faixas em "Todos", a agregação de instrumentos roda UMA vez por conjunto de visitas', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    payloadAtual = {
      ...payload,
      visitas: [visita({
        id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
      })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Sem restrição nenhuma, `visitasVisiveis` É `visitas` (mesma
    // referência), então a agregação "da grade" produziria byte a byte a
    // mesma coisa que a "da janela" — Map sobre o catálogo, laço de 42 dias
    // e um sort por dia, pagos duas vezes a cada troca de payload.
    //
    // O número: entrar no Mês passa por DUAS rodadas de derivação (antes e
    // depois de a âncora do mês existir, que é o que monta a grade de 42
    // dias). O que este teste guarda é o CUSTO POR RODADA — uma agregação,
    // não duas: eram 4 chamadas, agora são 2. Se a contagem cair para 1, a
    // rodada extra sumiu e o teste deve ser relido, não afrouxado.
    expect(espiaInstrumentosPorDia).toHaveBeenCalledTimes(2)
    // E a grade continua mostrando o que a agregação diz.
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).toContain('Q001')

    // Com uma restrição ativa as duas listas DIVERGEM, e aí a segunda
    // agregação é obrigatória — o atalho não pode engolir este caso.
    fireEvent.click(
      within(screen.getByRole('group', { name: 'Técnicos:' })).getByRole('button', { name: 'Afonso' }),
    )
    expect(espiaInstrumentosPorDia).toHaveBeenCalledTimes(3)
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).not.toContain('Q001')
  })

  it('a marca do chip desligado também perde o preenchimento — vira contorno (achado 2 da review final)', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    payloadAtual = {
      ...payload,
      visitas: [visita({
        id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
      })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const chipAfonso = within(screen.getByRole('group', { name: 'Técnicos:' }))
      .getByRole('button', { name: 'Afonso' })
    const chipQ001 = within(screen.getByRole('group', { name: 'Instrumentos:' }))
      .getByRole('button', { name: /Q001/ })
    // As marcas são `aria-hidden` (decoração — o nome do recurso está em
    // texto puro ao lado), então não têm papel pra consultar: a busca é
    // estrutural, mesmo precedente do teste de peso acima.
    const bolinha = () => chipAfonso.querySelector('span[aria-hidden]') as HTMLElement
    const triangulo = () => chipQ001.querySelector('polygon') as SVGPolygonElement

    // Ligado: marca CHEIA, na cor do recurso.
    expect(bolinha().style.backgroundColor).not.toBe('')
    expect(bolinha().style.backgroundColor).not.toBe('transparent')
    expect(triangulo().getAttribute('fill')).not.toBe('none')

    fireEvent.click(chipAfonso)
    fireEvent.click(chipQ001)

    // Desligado: só contorno. A marca é o elemento visual DOMINANTE do chip
    // — mantê-la saturada enquanto o resto do chip apaga fazia o chip
    // desligado continuar lendo como ligado, que é o mesmo defeito que o
    // fix round 1 corrigiu no fundo e na borda e deixou passar na marca.
    expect(bolinha().style.backgroundColor).toBe('transparent')
    expect(bolinha().style.borderColor).not.toBe('')
    expect(triangulo().getAttribute('fill')).toBe('none')
    expect(Number(triangulo().getAttribute('stroke-width'))).toBeGreaterThan(0)
  })

  it('chip ligado é o preenchido (tem o peso); desligado fica apagado — nunca o contrário (achado 2, fix round 1)', async () => {
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso' })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupoTecnicos).getByRole('button', { name: 'Afonso' })
    const badgeTodos = within(grupoTecnicos).getByRole('button', { name: 'Todos os técnicos' })

    // Estado inicial ("Todos" ativo, Afonso ligado por herança): os dois
    // usam o MESMO vocabulário de peso — preenchido, sem contorno
    // tracejado.
    expect(badgeTodos.className).toMatch(/bg-accent/)
    expect(chipAfonso.className).toMatch(/bg-accent/)
    expect(chipAfonso.className).not.toMatch(/border-dashed/)

    fireEvent.click(chipAfonso)

    // Desligado: sem preenchimento, com contorno tracejado — a validação em
    // navegador achou o oposto (desligado com MAIS peso visual que ligado,
    // o olho lia o destacado como "selecionado"). Desligar um chip
    // específico sai do estado "Todos" (vira um `Set` restrito), então o
    // próprio badge "Todos" segue o MESMO vocabulário: também perde o
    // preenchimento.
    expect(chipAfonso.className).not.toMatch(/bg-accent/)
    expect(chipAfonso.className).toMatch(/border-dashed/)
    expect(badgeTodos.className).not.toMatch(/bg-accent/)
    expect(badgeTodos.className).toMatch(/border-dashed/)
  })

  it('trocar de modo e voltar ao Mês zera o filtro', async () => {
    payloadAtual = {
      ...payload,
      visitas: [visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso' })],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    fireEvent.click(within(grupoTecnicos).getByRole('button', { name: 'Afonso' }))
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).not.toContain('Afonso')

    fireEvent.click(screen.getByRole('button', { name: /^Semana$/ }))
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    // Voltar ao Mês: o badge "Todos" está de novo ativo e a bolinha voltou.
    const grupoTecnicosDepois = screen.getByRole('group', { name: 'Técnicos:' })
    expect(within(grupoTecnicosDepois).getByRole('button', { name: 'Todos os técnicos' }))
      .toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('button', { name: /^17 de setembro,/ }).getAttribute('aria-label'),
    ).toContain('Afonso')
  })

  // --- achados da review da Task 1: gate de `alvoVisivel` no diálogo pendente ---

  it('refetch em segundo plano move a visita em ajuste para fora da janela visível: fecha o diálogo pendente de confirmação de data', async () => {
    const { rerender, qc } = montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^19 de setembro,/ }))
    expect(screen.getByRole('dialog', { name: 'Mudar data da visita' })).toBeInTheDocument()

    // Refetch em BACKGROUND — não uma navegação do Gestor — traz a MESMA
    // visita (mesmo id, ainda `editable`) com uma data fora da grade de
    // setembro/2026 visível. `alvoVisivel` cai para `false` sem que
    // ninguém tenha tocado em nada.
    payloadAtual = { ...payload, visitas: [visita({ date: '2026-11-15' })] }
    rerender(<QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>)

    // O diálogo fecha sozinho — não fica pendurado esperando um "Confirmar"
    // que gravaria fora da janela visível.
    expect(screen.queryByRole('dialog')).toBeNull()
    // A tarja de ajuste continua (a visita não sumiu nem travou), agora
    // avisando que está fora do período visível.
    expect(screen.getByText(/Fora do período visível/)).toBeInTheDocument()
    expect(mutateUpdate).not.toHaveBeenCalled()
  })

  it('visita armada perde editable (travada em outro lugar) fecha o diálogo pendente de confirmação de data', async () => {
    const { rerender, qc } = montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^19 de setembro,/ }))
    expect(screen.getByRole('dialog', { name: 'Mudar data da visita' })).toBeInTheDocument()

    // Mesma visita, mesma data — só perde `editable` (ex.: a OS saiu de
    // `scheduled` em outro lugar). Gatilho DIFERENTE do teste "some do
    // payload" acima: sem este teste, o ramo `!atual.editable` da rede de
    // segurança nunca era exercido.
    payloadAtual = { ...payload, visitas: [visita({ editable: false })] }
    rerender(<QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>)

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByText(/Movendo a visita/)).toBeNull()
    expect(mutateUpdate).not.toHaveBeenCalled()
  })

  // --- Task 1 (plano "agenda-barra-estado-dia"): a barra e o aria-label
  // sobrevivem ao filtro das duas faixas de legenda, porque as duas leem a
  // fonte NÃO FILTRADA (`conflitosPorDia(visitas, ...)`, montada em `page.tsx`
  // a partir de `visitas`, nunca `visitasVisiveis`) ---

  describe('barra de estado do dia sobrevive ao filtro (fonte não filtrada)', () => {
    it('filtro que esconde as visitas de um dia em conflito: o dia fica sem pontinhos, com barra vermelha, e o aria-label continua dizendo ", com conflito"', async () => {
      // 20/09, NÃO 17/09 (`server_today`): o dia selecionado por default
      // ganha fundo `--primary` e suprime a barra (achado de contraste desta
      // task, ver `mes.test.ts`) — este teste teria que checar uma barra que
      // não deveria estar lá por um motivo ALHEIO ao que ele prova.
      payloadAtual = {
        ...payload,
        visitas: [
          visita({
            id: 7, date: '2026-09-20', tecnico_id: 441, tecnico_name: 'Afonso', conflict: true,
          }),
        ],
      }
      montar()
      irParaMes()
      await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

      const celulaAntes = screen.getByRole('button', { name: /^20 de setembro,/ })
      expect(celulaAntes.getAttribute('aria-label')).toContain(', com conflito')
      expect(within(celulaAntes).getByTestId('barra-estado').className).toContain('bg-danger')

      // Desliga o único técnico da faixa — a camada 1 do filtro (`page.tsx`)
      // esconde a visita inteira das marcas, mas `conflitosGrade` não muda:
      // ela nunca leu `visitasVisiveis`.
      const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
      fireEvent.click(within(grupoTecnicos).getByRole('button', { name: 'Afonso' }))

      const celula = screen.getByRole('button', { name: /^20 de setembro,/ })
      expect(within(celula).queryAllByTestId('ponto')).toHaveLength(0)
      // O sufixo continua — a data segue no `Set` não filtrado.
      expect(celula.getAttribute('aria-label')).toContain(', com conflito')
      // E a barra continua vermelha — nunca vira `--ok` nem some, mesmo sem
      // nenhum pontinho visível (consequência aceita no brief).
      expect(within(celula).getByTestId('barra-estado').className).toContain('bg-danger')
    })

    it('filtro que esconde as visitas de um dia SEM conflito: o dia perde a barra verde junto com os pontinhos', async () => {
      // Mesmo raciocínio acima: 20/09, não o dia selecionado por default.
      payloadAtual = {
        ...payload,
        visitas: [
          visita({
            id: 7, date: '2026-09-20', tecnico_id: 441, tecnico_name: 'Afonso', conflict: false,
          }),
        ],
      }
      montar()
      irParaMes()
      await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

      const celulaAntes = screen.getByRole('button', { name: /^20 de setembro,/ })
      expect(within(celulaAntes).getByTestId('barra-estado').className).toContain('bg-ok')

      const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
      fireEvent.click(within(grupoTecnicos).getByRole('button', { name: 'Afonso' }))

      const celula = screen.getByRole('button', { name: /^20 de setembro,/ })
      expect(within(celula).queryAllByTestId('ponto')).toHaveLength(0)
      // Sem conflito na janela e sem visita FILTRADA sobrando: a barra some
      // por inteiro — não vira `--danger` (não há conflito) nem continua
      // `--ok` (a camada 1 do filtro esvaziou o dia filtrado).
      expect(within(celula).queryByTestId('barra-estado')).not.toBeInTheDocument()
    })
  })
})

// --- Task 1 (isolar recurso): toque longo num chip da faixa ---
//
// Fake timers só entram DEPOIS do `await waitFor` do mount — o `waitFor` do
// Testing Library faz polling em timer real, e ligar `vi.useFakeTimers()`
// antes travaria o próprio mount. `afterEach` sempre volta pra timer real,
// mesmo se um teste falhar no meio — senão o fake timer vaza pro próximo
// teste do arquivo (que não espera por isso) e trava ele num `waitFor` que
// nunca avança.
describe('Modo Mês — isolar recurso (toque longo na faixa)', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  async function montarNoMes() {
    payloadAtual = {
      ...payload,
      visitas: [
        visita({
          id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso', instrument_ids: [101],
        }),
        visita({
          id: 8, date: '2026-09-17', tecnico_id: 9, tecnico_name: 'Bruno', instrument_ids: [102],
        }),
      ],
    }
    instrumentoOptionsAtual = [
      { id: 101, name: 'Q001', validade: '2027-01-01' },
      { id: 102, name: 'Q002', validade: '2027-01-01' },
    ]
    // Retorna os utils do `render` (fix round 1, achado 3): o teste de
    // desmontagem com o timer armado precisa do `unmount` desta MESMA
    // instância — um `montar()` novo criaria uma árvore sem relação com o
    // toque já em andamento na primeira.
    const utils = montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())
    return utils
  }

  /** Simula o gesto completo até o limiar de 500ms, SEM soltar o ponteiro
   *  ainda — o timer de isolar dispara com o dedo/botão ainda pressionado,
   *  igual ao toque longo real. */
  function seguraAte500ms(chip: HTMLElement) {
    fireEvent.pointerDown(chip, { pointerId: 1, clientX: 0, clientY: 0 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
  }

  /**
   * Estica as bounds do chip pra um retângulo real e previsível — o
   * happy-dom não calcula layout, então `getBoundingClientRect()` sem este
   * stub devolve `{ left: 0, top: 0, right: 0, bottom: 0 }` pra QUALQUER
   * elemento. Isso é uma armadilha, não um placeholder inofensivo: com o
   * retângulo zerado, um `pointerUp` disparado sem `clientX`/`clientY`
   * explícitos (que também vêm a 0) SEMPRE cai "dentro" das bounds — o teste
   * passaria mesmo se a checagem de posição em `soltarToqueLongo` estivesse
   * quebrada ou ausente, só por acidente do stub. Os testes que exercitam a
   * checagem de posição (dentro vs. fora) por isso `stubBounds` o chip ANTES
   * do gesto e usam `clientX`/`clientY` explícitos e coerentes com o
   * retângulo escolhido — nunca dependem do zero implícito.
   */
  function stubBounds(
    chip: HTMLElement,
    rect: { left: number; top: number; right: number; bottom: number },
  ) {
    vi.spyOn(chip, 'getBoundingClientRect').mockReturnValue({
      ...rect,
      width: rect.right - rect.left,
      height: rect.bottom - rect.top,
      x: rect.left,
      y: rect.top,
      toJSON: () => rect,
    } as DOMRect)
  }

  it('toque longo isola: só aquele chip fica ligado, os demais desligam (aria-pressed e marcas da grade)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    seguraAte500ms(chipAfonso)
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })

    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'false')

    vi.useRealTimers()
    const celula = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(celula.getAttribute('aria-label')).toContain('Afonso')
    expect(celula.getAttribute('aria-label')).not.toContain('Bruno')
  })

  it('toque longo no chip já isolado volta para "Todos"', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const badgeTodos = within(grupo).getByRole('button', { name: 'Todos os técnicos' })

    seguraAte500ms(chipAfonso)
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })
    expect(badgeTodos).toHaveAttribute('aria-pressed', 'false')

    // Segundo toque longo no MESMO chip, já isolado: reverte pra "Todos" —
    // reversível por si mesmo, sem precisar caçar o badge "Todos".
    seguraAte500ms(chipAfonso)
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })

    expect(badgeTodos).toHaveAttribute('aria-pressed', 'true')
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
  })

  it('toque simples continua alternando só aquele chip, sem isolar', async () => {
    await montarNoMes()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    fireEvent.click(chipAfonso)

    expect(chipAfonso).toHaveAttribute('aria-pressed', 'false')
    // Bruno não foi tocado — continua ligado (toque simples só alterna o
    // chip clicado, não isola os demais).
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
  })

  it('toque longo não dispara também o alternar: o chip isolado termina ligado, não desligado', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })

    // Bounds explícitas e o `pointerUp` DENTRO delas — de propósito, não por
    // acidente do retângulo zerado do happy-dom (que também leria "dentro"
    // sem stub nenhum, já que um `pointerUp` sem `clientX`/`clientY`
    // explícitos vem a 0,0). Este teste protege o invariante "só ARMA a
    // flag, nunca desarma" de `soltarToqueLongo`: soltar DENTRO do chip — o
    // caminho normal de um toque longo bem-sucedido — não pode limpar a
    // supressão que o `setTimeout` de `iniciarToqueLongo` já armou. Com
    // bounds explícitas, uma regressão que trocasse esse `if` por um
    // `if/else` (limpando a flag quando "dentro") quebraria este teste de
    // verdade, não só por coincidência de zeros.
    stubBounds(chipAfonso, { left: 0, top: 0, right: 100, bottom: 44 })
    seguraAte500ms(chipAfonso)
    fireEvent.pointerUp(chipAfonso, { pointerId: 1, clientX: 50, clientY: 20 })
    // O `click` que o navegador dispara em seguida a um toque real (pointerup
    // -> click) não pode "desfazer" o isolar reaplicando o alternar.
    // `detail: 1` é o que marca este `click` como vindo de um PONTEIRO real
    // (mouse/toque) — sem isto, o padrão de `MouseEvent` sintético é
    // `detail: 0`, o mesmo valor de um `click` ativado por teclado, e o
    // teste não provaria nada sobre o caminho que a correção do achado 1
    // precisa distinguir.
    fireEvent.click(chipAfonso, { detail: 1 })

    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
  })

  it('clique curto com tremida pequena (13px) DENTRO do chip alterna normalmente (fix: "às vezes o clique funciona, às vezes não")', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // Chip de 100x44 — 13px de tremida no meio do caminho (> LIMIAR_ARRASTO_PX
    // de 10) continua bem DENTRO do retângulo.
    stubBounds(chipAfonso, { left: 0, top: 0, right: 100, bottom: 44 })

    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 10, clientY: 20 })
    fireEvent.pointerMove(chipAfonso, { pointerId: 1, clientX: 23, clientY: 20 })
    // Solto BEM antes dos 500ms — não é toque longo, é um toque curto comum
    // com a mão tremendo no caminho. Reprodução do bug relatado: pointerdown,
    // mover 13px, pointerup, sem nenhum arrasto de verdade.
    fireEvent.pointerUp(chipAfonso, { pointerId: 1, clientX: 23, clientY: 20 })
    fireEvent.click(chipAfonso, { detail: 1 })

    // O clique PRECISA valer — antes do fix, `moverToqueLongo` suprimia
    // qualquer click depois de >10px de trajeto, sem olhar pra onde o dedo
    // soltou, e este era exatamente o clique intermitentemente perdido.
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'false')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
  })

  it('pressionar o chip, mover para FORA das bounds e soltar lá NÃO alterna (comportamento de botão nativo)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    stubBounds(chipAfonso, { left: 0, top: 0, right: 100, bottom: 44 })

    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 50, clientY: 20 })
    // Move pra fora do retângulo (right: 100) — bem além do limiar de
    // arrasto, então o isolar pendente também é cancelado (não chega a
    // 500ms aqui, mas não haveria isolar de qualquer forma).
    fireEvent.pointerMove(chipAfonso, { pointerId: 1, clientX: 150, clientY: 20 })
    // Solta FORA — `evento.currentTarget` continua sendo o botão graças à
    // captura de ponteiro (`setPointerCapture`), então é a posição real
    // (150, 20) que é comparada contra as bounds (0..100, 0..44).
    fireEvent.pointerUp(chipAfonso, { pointerId: 1, clientX: 150, clientY: 20 })
    fireEvent.click(chipAfonso, { detail: 1 })

    // Nenhum botão nativo alterna quando você aperta, arrasta pra fora e
    // solta lá — o click é suprimido, Afonso continua ligado.
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
  })

  it('arrastar além do limiar continua cancelando o isolar (o toque longo não dispara), mesmo soltando dentro do chip', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    stubBounds(chipAfonso, { left: 0, top: 0, right: 200, bottom: 44 })

    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 10, clientY: 20 })
    // 70px — bem acima do limiar de 10px — mas ainda DENTRO do retângulo
    // largo (0..200): isola o efeito do limiar (cancela o timer) do efeito
    // da posição de soltura (que aqui não suprime, por estar dentro).
    fireEvent.pointerMove(chipAfonso, { pointerId: 1, clientX: 80, clientY: 20 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerUp(chipAfonso, { pointerId: 1, clientX: 80, clientY: 20 })
    fireEvent.click(chipAfonso, { detail: 1 })

    // O sinal de isolar bem-sucedido é Bruno DESLIGAR (isolar apaga todos os
    // outros) — não o badge "Todos", que também apaga num alternar comum a
    // partir de "Todos" (o toggle vira um `Set` com todos MENOS o tocado,
    // deixando de ser `null`; não é exclusivo de isolar). Bruno continua
    // ligado: se o timer não tivesse sido cancelado pelo arrasto, `onIsolar`
    // o teria desligado aos 500ms, com o dedo ainda no ar.
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
    // E o clique, por ter sido solto DENTRO do chip, ainda vale como toque
    // simples comum — o arrasto cancelou o isolar, não o clique: Afonso
    // alterna (desliga), sem isolar ninguém.
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'false')
  })

  it('Alt+Enter isola pelo teclado', async () => {
    await montarNoMes()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    fireEvent.keyDown(chipAfonso, { key: 'Enter', altKey: true })

    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'false')
  })

  it('Alt+clique isola pelo mouse', async () => {
    await montarNoMes()

    const grupo = screen.getByRole('group', { name: 'Instrumentos:' })
    const chipQ001 = within(grupo).getByRole('button', { name: /Q001/ })
    const chipQ002 = within(grupo).getByRole('button', { name: /Q002/ })

    fireEvent.click(chipQ001, { altKey: true })

    expect(chipQ001).toHaveAttribute('aria-pressed', 'true')
    expect(chipQ002).toHaveAttribute('aria-pressed', 'false')
  })

  it('a dica "Segure um para ver só ele" aparece nas duas faixas', async () => {
    await montarNoMes()

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    expect(within(grupoTecnicos).getByText('Segure um para ver só ele')).toBeInTheDocument()
    expect(within(grupoInstrumentos).getByText('Segure um para ver só ele')).toBeInTheDocument()
  })

  it('isolar na faixa de instrumentos não mexe na de técnicos', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupoInstrumentos = screen.getByRole('group', { name: 'Instrumentos:' })
    const chipQ001 = within(grupoInstrumentos).getByRole('button', { name: /Q001/ })

    seguraAte500ms(chipQ001)
    fireEvent.pointerUp(chipQ001, { pointerId: 1 })

    expect(chipQ001).toHaveAttribute('aria-pressed', 'true')

    vi.useRealTimers()
    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    const badgeTodosTecnicos = within(grupoTecnicos).getByRole('button', { name: 'Todos os técnicos' })
    expect(badgeTodosTecnicos).toHaveAttribute('aria-pressed', 'true')
    expect(within(grupoTecnicos).getByRole('button', { name: 'Afonso' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(grupoTecnicos).getByRole('button', { name: 'Bruno' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('Alt+Espaço isola pelo teclado', async () => {
    await montarNoMes()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    fireEvent.keyDown(chipAfonso, { key: ' ', altKey: true })

    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'false')
  })

  // --- Fix round 1 (review) ---

  it('flag de supressão armada e ainda por consumir não engole um Enter legítimo de teclado noutro chip (achado 1 importante — quem protege aqui é o gate de detail, não um pointercancel)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // Toque longo em Afonso isola e solta NORMALMENTE — `pointerup`, não
    // `pointercancel`. Isto importa: desde o fix round 4/5,
    // `cancelarToqueLongo` (só `pointercancel`) É quem libera a flag, e só
    // quando o `pointerId` que cancela é o mesmo que a armou — um
    // `pointerup` normal nunca passa por ali. Armar a flag por ESTE
    // caminho é o que garante que ela continua ARMADA na hora do clique de
    // teclado abaixo: se a flag já tivesse sido liberada por outro motivo,
    // o teste passaria mesmo com o gate de `detail` apagado, sem provar
    // nada (foi exatamente o que aconteceu com a versão anterior deste
    // teste, que usava `pointercancel` — achado da re-review, fix round 5).
    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'false')

    // Interação seguinte na faixa é só por TECLADO, num chip diferente, sem
    // nenhum `pointerdown` antes (Tab até lá + Enter) — o `click`
    // sintetizado por essa ativação tem `detail: 0`. A flag de Afonso
    // continua armada (o click REAL dele ainda está "em voo", nunca
    // disparado neste teste) — é o gate `evento.detail === 0`, e só ele,
    // quem impede este clique legítimo de ser engolido.
    fireEvent.click(chipBruno, { detail: 0 })

    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
  })

  it('pointerup de um dedo não cancela o toque longo em andamento de outro chip da mesma faixa (achado 2)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // Dedo 1 (pointerId 1) toca Afonso e solta rápido, sem isolar.
    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    // Dedo 2 (pointerId 2) toca Bruno e continua pressionado — o
    // `pointerdown` dele já assume o `toqueRef` da faixa (só um toque longo
    // em andamento por vez é o comportamento aceito, ver comentário do
    // componente).
    fireEvent.pointerDown(chipBruno, { pointerId: 2, clientX: 0, clientY: 0 })
    // O `pointerup` do dedo 1 chega DEPOIS do `pointerdown` do dedo 2 — sem
    // conferir o `pointerId`, isto cancelaria por engano o timer que já
    // pertence ao dedo 2.
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })

    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerUp(chipBruno, { pointerId: 2 })

    // O toque longo do dedo 2 (Bruno) precisa ter completado normalmente —
    // Afonso desligado é o único sinal visível de que Bruno isolou de
    // verdade (sem isolar nenhum, os dois continuariam com "Todos", os dois
    // ligados).
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'false')
  })

  it('desmontar com o toque longo armado limpa o timer (cleanup) — nada sobra pra chamar onIsolar depois (achado 3)', async () => {
    const { unmount } = await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })

    // Contagem de timers pendentes ANTES do gesto — não pode ser 0 fixo
    // como baseline: o React Query e outros hooks da página já podem ter
    // timers próprios em voo, e um `toBe(0)` cravado seria frágil. O que
    // prova o cleanup é a DELTA: +1 no pointerdown, de volta ao mesmo
    // número na desmontagem.
    const timersAntes = vi.getTimerCount()

    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    expect(vi.getTimerCount()).toBe(timersAntes + 1)

    // Desmonta a árvore inteira (troca de mês/modo real desmontaria só a
    // `VistaMes`, mas também reseta o filtro — mascararia exatamente o que
    // este teste quer provar) ANTES dos 500ms, com o timer do toque longo
    // ainda armado.
    unmount()

    // Sem o `useEffect` de limpeza, este timer sobreviveria à desmontagem e
    // dispararia `onIsolar` (que chama `setTecnicosSel`) num componente que
    // não existe mais — a armadilha do timer solto que o brief pede pra
    // fechar. O `toqueRef` (e o próprio componente) não existem mais pra
    // consultar `onIsolar` diretamente, então a prova aqui é que o TIMER em
    // si não sobra na fila: nada existe mais que possa chamá-lo.
    expect(vi.getTimerCount()).toBe(timersAntes)

    // Avançar o relógio depois da desmontagem não pode lançar nem deixar
    // nada pendurado.
    expect(() => {
      act(() => {
        vi.advanceTimersByTime(1000)
      })
    }).not.toThrow()
  })

  // --- Fix round 2 (re-review): corrida de dois dedos ---

  it('clique-fantasma do dedo 1 não desliga o item isolado quando o dedo 2 já tocou outro chip antes do click chegar', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // Dedo 1 (pointerId 1): toque longo em Afonso, isola, solta normalmente
    // (pointerup, não pointercancel — o `click` real ainda vai vir).
    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'false')

    // Dedo 2 (pointerId 2) toca Bruno ANTES do `click` do dedo 1 chegar —
    // a janela assíncrona real entre o `pointerup` e o `click` que o
    // navegador dispara depois. Sem a correção, o `pointerdown` do dedo 2
    // sobrescreve `toqueRef.current` inteiro, levando junto a supressão que
    // o `click` do dedo 1 ainda precisa consumir.
    fireEvent.pointerDown(chipBruno, { pointerId: 2, clientX: 0, clientY: 0 })

    // Só AGORA chega o `click` do dedo 1 (detail: 1 — click de ponteiro
    // real). Precisa continuar suprimido: sem isto, cairia no `onAlternar`
    // e desligaria Afonso, que acabou de ser isolado com sucesso.
    fireEvent.click(chipAfonso, { detail: 1 })
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')

    // (b) o segundo gesto continua funcionando normalmente: completa o
    // toque longo em Bruno (isola, derrubando Afonso) e o próprio `click`
    // fantasma DELE também é suprimido corretamente — a correção não pode
    // ter comprometido o ciclo de supressão do gesto que a sucedeu.
    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerUp(chipBruno, { pointerId: 2 })
    fireEvent.click(chipBruno, { detail: 1 })

    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'false')
  })

  // --- Review final da branch ---

  it('pede a captura do ponteiro ao iniciar o toque longo — soltar o mouse fora do chip não isola sozinho (achado importante 1)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // happy-dom rastreia `hasPointerCapture` mas não redireciona o
    // DESPACHO do evento pro elemento capturador quando o evento é
    // disparado noutro nó — o comportamento central que faz a captura
    // valer a pena no navegador real (custo antecipado pela review). O
    // stub simula esse redirecionamento: registra quem capturou cada
    // `pointerId` e resolve o alvo real de `pointermove`/`pointerup`
    // disparados "fora" do chip, do mesmo jeito que o navegador faria.
    const capturas = new Map<number, HTMLElement>()
    const capturarSpy = vi.spyOn(HTMLElement.prototype, 'setPointerCapture')
      .mockImplementation(function (this: HTMLElement, pointerId: number) {
        capturas.set(pointerId, this)
      })

    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    // Prova o MECANISMO do fix: o botão pediu a captura do ponteiro que
    // acabou de pressioná-lo.
    expect(capturarSpy).toHaveBeenCalledWith(1)

    // Arrasta pra fora do chip — em cima do FUNDO da faixa, não mais do
    // botão — e solta lá aos ~300ms, antes dos 500ms do toque longo. Com a
    // captura redirecionando (o stub simula isso), os eventos chegam ao
    // BOTÃO mesmo fisicamente fora dele — os handlers já guardados por
    // `pointerId` (rounds anteriores) fecham o ciclo.
    const alvoReal = capturas.get(1) ?? grupo
    fireEvent.pointerMove(alvoReal, { pointerId: 1, clientX: 999, clientY: 999 })
    act(() => {
      vi.advanceTimersByTime(300)
    })
    fireEvent.pointerUp(alvoReal, { pointerId: 1 })
    act(() => {
      vi.advanceTimersByTime(300)
    })

    // Sem a captura, nenhum handler do botão teria rodado depois do
    // arrasto: o timer sobreviveria e isolaria Afonso ~200ms depois de o
    // usuário já ter soltado o mouse. Com ela, o arrasto (>10px) já tinha
    // cancelado o timer antes mesmo do pointerup.
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')

    capturarSpy.mockRestore()
  })

  it('a região viva da faixa anuncia isolar, reverter e o alternar simples (achado importante 2)', async () => {
    await montarNoMes()

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    const status = within(grupoTecnicos).getByRole('status')
    const chipAfonso = within(grupoTecnicos).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupoTecnicos).getByRole('button', { name: 'Bruno' })

    expect(status).toHaveTextContent('Mostrando todos os técnicos')

    // Isolar por teclado (Alt+Enter) — o único caminho que quem usa leitor
    // de tela tem pro gesto.
    fireEvent.keyDown(chipAfonso, { key: 'Enter', altKey: true })
    expect(status).toHaveTextContent('Mostrando só Afonso')

    // Reverter (segundo Alt+Enter no mesmo chip).
    fireEvent.keyDown(chipAfonso, { key: 'Enter', altKey: true })
    expect(status).toHaveTextContent('Mostrando todos os técnicos')

    // Toque simples (alternar) também precisa atualizar a região viva —
    // não só isolar/reverter.
    fireEvent.click(chipBruno)
    expect(status).toHaveTextContent('Mostrando só Afonso')
  })

  it('a região viva mostra "N de M" quando a restrição não é nem "Todos" nem um item só (achado importante 2)', async () => {
    payloadAtual = {
      ...payload,
      visitas: [
        visita({ id: 7, date: '2026-09-17', tecnico_id: 441, tecnico_name: 'Afonso' }),
        visita({ id: 8, date: '2026-09-17', tecnico_id: 9, tecnico_name: 'Bruno' }),
        visita({ id: 9, date: '2026-09-17', tecnico_id: 55, tecnico_name: 'Carla' }),
      ],
    }
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    const grupoTecnicos = screen.getByRole('group', { name: 'Técnicos:' })
    const status = within(grupoTecnicos).getByRole('status')
    const chipCarla = within(grupoTecnicos).getByRole('button', { name: 'Carla' })

    // Desliga só Carla — de "Todos" (3) restam 2 de 3, nem "Todos" nem "só
    // um", o caso geral que `textoStatus` cobre com a contagem.
    fireEvent.click(chipCarla)

    expect(status).toHaveTextContent('Mostrando 2 de 3 técnicos')
  })

  it('pointercancel libera suprimirCliqueRef: um clique de PONTEIRO legítimo noutro chip da faixa volta a alternar normalmente (achado da review final, fix round 4)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // Toque longo em Afonso isola — mas o SISTEMA interrompe o toque com
    // `pointercancel` em vez do `pointerup` normal (rolagem detectada
    // tarde, notificação, etc.): por spec, nenhum `click` vem depois pra
    // ESTE gesto.
    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerCancel(chipAfonso, { pointerId: 1 })
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'false')

    // Interação seguinte é um toque simples REAL (ponteiro, não teclado)
    // num chip DIFERENTE, sem nenhuma relação com o gesto de Afonso.
    fireEvent.pointerDown(chipBruno, { pointerId: 2, clientX: 0, clientY: 0 })
    fireEvent.pointerUp(chipBruno, { pointerId: 2 })
    fireEvent.click(chipBruno, { detail: 1 })

    // Bruno precisa ligar (alternar normal). Antes do fix, a flag de
    // supressão ficava presa do `pointercancel` de Afonso — o gate
    // `detail === 0` do round 1 protege só cliques de TECLADO, nunca este
    // (um clique de ponteiro real tem `detail: 1`) — e este clique era
    // engolido em silêncio, mesmo sem nenhuma relação com o gesto abortado.
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
  })

  // --- Fix round 5 (re-review): a flag precisa saber QUEM a armou ---

  it('pointercancel do dedo que armou a flag ainda a libera mesmo depois de outro dedo tomar o toqueRef (janela i, fix round 5)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // Dedo 1 isola Afonso (a flag guarda o `pointerId` 1).
    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')

    // Dedo 2 toca Bruno ANTES do `pointercancel` do dedo 1 chegar — toma o
    // `toqueRef` por inteiro (só um gesto de posição/timer em andamento por
    // vez, ver comentário do componente).
    fireEvent.pointerDown(chipBruno, { pointerId: 2, clientX: 0, clientY: 0 })

    // SÓ ENTÃO o sistema interrompe o dedo 1 com `pointercancel` — o
    // `toqueRef` já não é mais dele, mas a flag de supressão continua
    // sendo (ela guarda o `pointerId` que a armou, não quem é dono do
    // `toqueRef` agora).
    fireEvent.pointerCancel(chipAfonso, { pointerId: 1 })

    // Dedo 2 solta rápido — toque simples em Bruno, sem isolar — e o click
    // real dele chega.
    fireEvent.pointerUp(chipBruno, { pointerId: 2 })
    fireEvent.click(chipBruno, { detail: 1 })

    // Bruno precisa alternar normalmente (liga, já que estava desligado
    // pela restrição a Afonso). Sem esta correção, o `pointercancel` do
    // dedo 1 não conseguia liberar a flag (comparava contra o DONO ATUAL
    // do `toqueRef`, que já era o dedo 2) — ela ficava presa e engolia
    // este clique sem nenhuma relação com o gesto de Afonso.
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
  })

  it('pointercancel de um dedo NÃO libera a flag armada por OUTRO dedo — o click atrasado do primeiro continua suprimido (janela ii, fix round 5)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // Dedo 1 isola Afonso e solta NORMALMENTE (`pointerup`) — o click real
    // dele ainda está "em voo" (a flag guarda o `pointerId` 1).
    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')

    // Dedo 2 toca Bruno (toma o `toqueRef`) e é interrompido por
    // `pointercancel` — um gesto totalmente diferente do de Afonso.
    fireEvent.pointerDown(chipBruno, { pointerId: 2, clientX: 0, clientY: 0 })
    fireEvent.pointerCancel(chipBruno, { pointerId: 2 })

    // SÓ ENTÃO chega o click atrasado do dedo 1, no PRÓPRIO chip que ele
    // isolou.
    fireEvent.click(chipAfonso, { detail: 1 })

    // Afonso precisa continuar isolado — o `pointercancel` do dedo 2 (id 2)
    // não pode liberar uma flag que foi armada pelo dedo 1 (id 1). Sem
    // esta correção (round 4 zerava a flag sempre que o `pointerId` do
    // `pointercancel` batia com o dono ATUAL do `toqueRef`, sem checar de
    // quem era a flag), o click atrasado do dedo 1 chegava sem supressão e
    // desfazia o isolamento que ele mesmo tinha acabado de fazer.
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
  })
})
