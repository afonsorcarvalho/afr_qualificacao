// @vitest-environment happy-dom
//
// Suíte separada de `ChatAgenda.test.tsx` de propósito, mesmo raciocínio de
// `ChatAgenda.cardOcupado.test.tsx`: aquele arquivo já mantém o fluxo de
// ditado de PONTA A PONTA (getUserMedia + MediaRecorder falsos, timers
// reais) contra o `useDitado` de verdade — ótimo pra provar que gravar e
// transcrever funcionam juntos, péssimo pra testar a FORMA da barra em
// cada combinação de `gravando`/`transcrevendo`/`nivelAudio`, porque
// chegar em cada combinação exigiria coreografar o hook real. Aqui
// mockamos `useDitado` (e `useChatAgenda`) por inteiro e controlamos os
// três campos direto — Task 3 de docs/superpowers/plans/2026-09-22-ditado-em
// -rajadas.md.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

const { useChatAgendaMock } = vi.hoisted(() => ({ useChatAgendaMock: vi.fn() }))
vi.mock('@/lib/hooks/useChatAgenda', () => ({ useChatAgenda: useChatAgendaMock }))

// `enabled: true` fixo: sem isto o botão de ditar (e a barra de gravação)
// nunca aparecem, e este arquivo existe pra testar exatamente o que
// acontece quando aparecem.
const { useGroqStatusMock } = vi.hoisted(() => ({
  useGroqStatusMock: vi.fn(() => ({ enabled: true, isLoading: false })),
}))
vi.mock('@/lib/hooks/useGroqStatus', () => ({ useGroqStatus: useGroqStatusMock }))

const { useDitadoMock, alternarMock, pararEDescartarMock } = vi.hoisted(() => ({
  useDitadoMock: vi.fn(),
  alternarMock: vi.fn(),
  pararEDescartarMock: vi.fn(),
}))
vi.mock('@/lib/hooks/useDitado', () => ({ useDitado: useDitadoMock }))

import { ChatAgenda } from '../agenda/_ChatAgenda'

const payload = {
  server_today: '2026-10-14', date_from: '2026-10-01', date_to: '2026-10-31',
  my_employee_id: 441 as number | false, can_manage: true,
  visitas: [{
    id: 87, date: '2026-10-15', time_start: 8, time_stop: 17, planned_hours: 9,
    os_id: 4, os_name: 'OS26-06-0002', os_state: 'draft',
    partner_name: 'Hospital Central', city: 'São Luís', equipment_list: [],
    instrument_ids: [], instrument_list: [], tecnico_id: 3,
    tecnico_name: 'João Silva', is_mine: false, state: 'draft', overflow: false,
    editable: true, lock_reason: false as const, conflict: false,
    conflict_msg: '', note: '',
  }],
}

/** Estado padrão parado — cada teste sobrescreve só o que precisa. */
function ditado(overrides: Partial<{ gravando: boolean; transcrevendo: boolean; nivelAudio: number }> = {}) {
  return {
    gravando: false,
    transcrevendo: false,
    alternar: alternarMock,
    pararEDescartar: pararEDescartarMock,
    nivelAudio: 0,
    ...overrides,
  }
}

function montar() {
  useChatAgendaMock.mockReturnValue({
    bolhas: [],
    proposta: null,
    ocupado: false,
    enviar: vi.fn(),
    confirmar: vi.fn(),
    cancelar: vi.fn(),
    totais: { chamadas: 0, entrada: 0, saida: 0, custo: 0, temCusto: false },
  })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ChatAgenda open onClose={() => {}} payload={payload as never} />
    </QueryClientProvider>,
  )
}

describe('ChatAgenda — barra de gravação (Task 3)', () => {
  // Os três dublês são módulo-level (`vi.hoisted`) — sem limpar as
  // chamadas entre testes, `alternarMock`/`pararEDescartarMock` carregam
  // clique do teste anterior e um `expect(...).not.toHaveBeenCalled()`
  // vira falso negativo (viu chamada de OUTRO teste, não deste).
  beforeEach(() => {
    vi.clearAllMocks()
    useGroqStatusMock.mockReturnValue({ enabled: true, isLoading: false })
  })

  it('gravando: mostra ✕ e ✓, esconde mic e enviar', () => {
    useDitadoMock.mockReturnValue(ditado({ gravando: true, nivelAudio: 0.2 }))
    montar()
    expect(screen.getByRole('button', { name: /descartar gravação/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /parar gravação/i })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /^ditar$/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /enviar/i })).toBeNull()
  })

  it('✕ descarta sem transcrever: chama pararEDescartar, não chama alternar (parar)', async () => {
    useDitadoMock.mockReturnValue(ditado({ gravando: true }))
    montar()
    await userEvent.click(screen.getByRole('button', { name: /descartar gravação/i }))
    expect(pararEDescartarMock).toHaveBeenCalledTimes(1)
    expect(alternarMock).not.toHaveBeenCalled()
  })

  it('✓ transcreve: chama alternar (que hoje já é o parar() do segundo clique do mic)', async () => {
    useDitadoMock.mockReturnValue(ditado({ gravando: true }))
    montar()
    await userEvent.click(screen.getByRole('button', { name: /parar gravação/i }))
    expect(alternarMock).toHaveBeenCalledTimes(1)
    expect(pararEDescartarMock).not.toHaveBeenCalled()
  })

  it('o medidor reflete o nível exposto pelo hook, em níveis REALISTAS de fala', () => {
    // 0.05/0.09 (não 0.3/0.9): `nivelAudio` é RMS cru do AnalyserNode, e
    // fala captada por microfone de celular fica na casa de 0.01-0.15
    // (ver `NIVEL_REFERENCIA_CHEIA` em `_ChatAgenda.tsx`), bem abaixo do
    // topo teórico da escala (1.0). Testar só com valores altos (0.3/0.9)
    // passaria mesmo se a barra ficasse colada no piso visual durante uma
    // fala inteira — o defeito que motivou reescrever a fórmula.
    useDitadoMock.mockReturnValue(ditado({ gravando: true, nivelAudio: 0.05 }))
    const { rerender, container } = montar()
    const medidor = screen.getByTestId('medidor-nivel')
    expect(medidor).toHaveAttribute('aria-hidden', 'true')
    const barraBaixa = container.querySelector('[data-testid="medidor-barra-referencia"]') as HTMLElement
    // Bem acima do piso visual (15%): prova que a fala normal MOVE o
    // medidor, não só o silêncio total ou o grito.
    expect(barraBaixa.style.height).toBe('50%')

    useDitadoMock.mockReturnValue(ditado({ gravando: true, nivelAudio: 0.09 }))
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    rerender(
      <QueryClientProvider client={qc}>
        <ChatAgenda open onClose={() => {}} payload={payload as never} />
      </QueryClientProvider>,
    )
    const barraAlta = container.querySelector('[data-testid="medidor-barra-referencia"]') as HTMLElement
    expect(barraAlta.style.height).toBe('90%')
  })

  it('parada, a barra volta ao normal: mic e enviar de volta, ✕/✓ e medidor somem', () => {
    useDitadoMock.mockReturnValue(ditado({ gravando: false }))
    montar()
    expect(screen.getByRole('button', { name: /^ditar$/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /enviar/i })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /descartar gravação/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /parar gravação/i })).toBeNull()
    expect(screen.queryByTestId('medidor-nivel')).toBeNull()
  })

  it('placeholder "Ouvindo…" enquanto grava e o campo está vazio', () => {
    useDitadoMock.mockReturnValue(ditado({ gravando: true }))
    montar()
    expect(screen.getByPlaceholderText('Ouvindo…')).toBeTruthy()
  })

  it('parado, o placeholder volta ao normal', () => {
    useDitadoMock.mockReturnValue(ditado({ gravando: false }))
    montar()
    expect(screen.getByPlaceholderText('Escreva o que precisa')).toBeTruthy()
  })

  it('role="status" anuncia "Gravando" pra quem usa leitor de tela (as barras são aria-hidden e não bastam sozinhas)', () => {
    useDitadoMock.mockReturnValue(ditado({ gravando: true }))
    montar()
    expect(screen.getByRole('status')).toHaveTextContent('Gravando')
  })

  it('parou de gravar e está transcrevendo: role="status" muda pra "Transcrevendo", e a barra some (mic volta, desabilitado; ✕/✓ somem)', () => {
    useDitadoMock.mockReturnValue(ditado({ gravando: false, transcrevendo: true }))
    montar()
    expect(screen.getByRole('status')).toHaveTextContent('Transcrevendo')
    // Mesma forma de "parado" (gravando=false): mic reaparece, mas
    // desabilitado — não dá pra começar uma gravação nova em cima da
    // transcrição ainda em voo. Enviar também volta (`!ditado.gravando`).
    // Nenhum estado novo: é o `disabled={ocupado || ditado.transcrevendo}`
    // que já existia antes desta task.
    const mic = screen.getByRole('button', { name: /^ditar$/i })
    expect(mic).toBeDisabled()
    expect(screen.getByRole('button', { name: /enviar/i })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /descartar gravação/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /parar gravação/i })).toBeNull()
    expect(screen.queryByTestId('medidor-nivel')).toBeNull()
  })

  it('parado de verdade (nem gravando, nem transcrevendo): role="status" fica vazio', () => {
    useDitadoMock.mockReturnValue(ditado())
    montar()
    expect(screen.getByRole('status')).toHaveTextContent('')
  })
})
