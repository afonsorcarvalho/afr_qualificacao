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

    seguraAte500ms(chipAfonso)
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })
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

  it('arrastar além do limiar antes dos 500ms cancela o gesto: não isola nem alterna', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    fireEvent.pointerMove(chipAfonso, { pointerId: 1, clientX: 30, clientY: 0 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerUp(chipAfonso, { pointerId: 1 })
    // `detail: 1`: é um click de ponteiro real que está sendo suprimido
    // aqui (arrasto), não um click de teclado passando pelo atalho do
    // achado 1 — os dois caminhos de supressão são independentes.
    fireEvent.click(chipAfonso, { detail: 1 })

    // Nada mudou: nem isolou (Bruno continuaria ligado, único sinal visível
    // de um isolar bem-sucedido), nem alternou (Afonso continua ligado).
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'true')
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

  it('gesto abortado por pointercancel não engole um Enter legítimo de teclado noutro chip (achado 1 importante)', async () => {
    await montarNoMes()
    vi.useFakeTimers()

    const grupo = screen.getByRole('group', { name: 'Técnicos:' })
    const chipAfonso = within(grupo).getByRole('button', { name: 'Afonso' })
    const chipBruno = within(grupo).getByRole('button', { name: 'Bruno' })

    // Toque longo em Afonso isola — mas o SISTEMA interrompe o toque com
    // `pointercancel` em vez do `pointerup` normal (rolagem detectada
    // tarde, notificação, etc.): nenhum `click` vem depois pra consumir a
    // flag de supressão, que fica presa no `toqueRef`.
    fireEvent.pointerDown(chipAfonso, { pointerId: 1, clientX: 0, clientY: 0 })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    fireEvent.pointerCancel(chipAfonso, { pointerId: 1 })
    expect(chipAfonso).toHaveAttribute('aria-pressed', 'true')
    expect(chipBruno).toHaveAttribute('aria-pressed', 'false')

    // Interação seguinte na faixa é só por TECLADO, num chip diferente, sem
    // nenhum `pointerdown` antes (Tab até lá + Enter) — o `click`
    // sintetizado por essa ativação tem `detail: 0`. Sem a checagem de
    // `detail` antes de `suprimirClique`, este clique legítimo seria
    // engolido pela flag que sobrou do gesto abortado de Afonso.
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
})
