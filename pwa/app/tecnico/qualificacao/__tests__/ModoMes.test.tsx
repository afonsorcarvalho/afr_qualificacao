// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AgendaPage from '../agenda/page'
import { gradeDoMes } from '../agenda/mes'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import type { AgendaPayload, InstrumentoOpcao, VisitaAgenda } from '@/lib/odoo/agenda'

const mutateUpdate = vi.fn()

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
const mockUseInstrumentoOptions = vi.fn((_enabled: boolean) => ({ data: instrumentoOptionsAtual }))

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
    mutateUpdate.mockReset().mockResolvedValue(visita())
    mockUseAgenda.mockClear()
    mockUseInstrumentoOptions.mockClear()
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

  it('Gestor: selecionar visita para ajuste + tocar outro dia chama pwa_visita_update com o date do destino', async () => {
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^17 de setembro,/ }))
    fireEvent.click(screen.getByRole('button', { name: /Ajustar/ }))
    fireEvent.click(screen.getByRole('button', { name: /^19 de setembro,/ }))

    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { date: '2026-09-19' } }),
    )
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

    await waitFor(() =>
      expect(mutateUpdate).toHaveBeenCalledWith({ id: 7, vals: { date: '2026-10-03' } }),
    )
    // A âncora segue o destino mesmo sem esperar o refetch: é o `ajustar`
    // da página que avança `ancoraMes` logo após a gravação (ruling do
    // brief 3d) — sem isto, o card sairia da grade (mudou de mês) e a
    // seleção ficaria presa olhando pro mês errado.
    await waitFor(() => expect(screen.getByText('outubro de 2026')).toBeInTheDocument())

    // Simula o refetch (real, depois do `onSuccess`) trazendo a visita já
    // com a data nova — a vista continua mostrando o card, ainda em ajuste
    // ("Concluir", não "Ajustar").
    payloadAtual = { ...payload, visitas: [visita({ date: '2026-10-03' })] }
    rerender(
      <QueryClientProvider client={qc}><AgendaPage /></QueryClientProvider>,
    )
    // A âncora já avançou pra outubro (checado acima) — "3 de outubro"
    // agora é uma célula DENTRO do mês visível, sem o prefixo "fora do mês".
    expect(screen.getByRole('button', { name: /^3 de outubro,/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Concluir/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Ajustar$/ })).toBeNull()
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
    // corpo do card, nunca a palavra "Sem técnico".
    expect(screen.getByText('Afonso')).toBeInTheDocument()
    expect(screen.getByText('Sem técnico')).toBeInTheDocument()
    // "Bruno" está no roster (mock de useTecnicoOptions) mas não tem
    // nenhuma visita na janela — não pode virar chip (brief 3d: "não o
    // roster inteiro, 20 chips de gente sem visita é ruído").
    expect(screen.queryByText('Bruno')).toBeNull()
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

    expect(screen.getByText('Q001')).toBeInTheDocument()
    expect(screen.queryByText('Q002')).toBeNull()
    // A faixa carrega um rótulo textual próprio, não só a forma do
    // triângulo — cor e forma nunca são o único portador (Global
    // Constraint de a11y); sem isto, um leitor de tela ouviria "Afonso,
    // Q001" como um único grupo indistinto.
    expect(screen.getByText('Instrumentos:')).toBeInTheDocument()
  })

  it('sem instrumento usado na janela, a faixa de instrumentos não é renderizada', async () => {
    instrumentoOptionsAtual = [{ id: 101, name: 'Q001', validade: '2027-01-01' }]
    // Payload default: a única visita não usa nenhum instrumento
    // (`instrument_ids: []`).
    montar()
    irParaMes()
    await waitFor(() => expect(screen.getByText('setembro de 2026')).toBeInTheDocument())

    expect(screen.queryByText('Q001')).toBeNull()
    expect(screen.queryByText('Instrumentos:')).toBeNull()
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
})
