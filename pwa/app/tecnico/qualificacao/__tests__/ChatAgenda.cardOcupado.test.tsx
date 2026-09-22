// @vitest-environment happy-dom
//
// Suíte separada de `ChatAgenda.test.tsx` de propósito: aquela testa o
// card de proposta através de interações reais (clique dispara `confirmar`
// real do hook `useChatAgenda`, que já zera `proposta` no mesmo commit em
// que liga `ocupado` — ver "Some com o card antes de executar" no próprio
// hook). Isso significa que, na aplicação real, nunca existe um render em
// que o card apareça com `ocupado === true`: as duas mudanças de estado são
// batched juntas, e o card desmonta antes de qualquer clique seguinte
// conseguir alcançar o botão Cancelar (confirmado empiricamente com
// `fireEvent.click` síncrono: o nó já não está mais no DOM na linha
// seguinte).
//
// Ainda assim, `disabled={ocupado}` no Cancelar é a mudança pedida pelo
// review (mesma trava visual que o Confirmar já tem) — é sobre a
// DECLARAÇÃO do JSX, não sobre uma sequência de eventos possível hoje.
// Testamos isso diretamente: mockamos `useChatAgenda` para devolver
// `ocupado: true` com uma proposta setada (um estado que o hook real nunca
// produz sozinho, mas que o componente precisa honrar se algum caller —
// hoje ou amanhã — o produzir) e conferimos que o JSX desabilita os dois
// botões, não só o Confirmar.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

// `vi.hoisted`: a fábrica de `vi.mock` abaixo é hoisted para o topo do
// arquivo — sem isso, `useChatAgendaMock` seria referenciado antes de
// inicializar (mesmo motivo do `vi.hoisted` em `ChatAgenda.test.tsx`).
const { useChatAgendaMock } = vi.hoisted(() => ({ useChatAgendaMock: vi.fn() }))
vi.mock('@/lib/hooks/useChatAgenda', () => ({ useChatAgenda: useChatAgendaMock }))
vi.mock('@/lib/hooks/useDitado', () => ({
  useDitado: () => ({ gravando: false, transcrevendo: false, alternar: vi.fn(), pararEDescartar: vi.fn() }),
}))

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

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ChatAgenda open onClose={() => {}} payload={payload as never} />
    </QueryClientProvider>,
  )
}

describe('ChatAgenda — card de proposta com ocupado=true', () => {
  it('Cancelar fica desabilitado junto com o Confirmar (mesmo estado visual)', () => {
    useChatAgendaMock.mockReturnValue({
      bolhas: [],
      proposta: { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'reagenda p/ sexta' },
      ocupado: true,
      enviar: vi.fn(),
      confirmar: vi.fn(),
      cancelar: vi.fn(),
      totais: { chamadas: 0, entrada: 0, saida: 0, custo: 0, temCusto: false },
    })
    montar()
    const confirmarBtn = screen.getByRole('button', { name: /confirmar/i })
    const cancelarBtn = screen.getByRole('button', { name: /cancelar/i })
    expect(confirmarBtn).toBeDisabled()
    expect(cancelarBtn).toBeDisabled()
  })
})
