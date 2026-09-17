// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FaixaDias } from '../agenda/_FaixaDias'
import { PainelRecursos } from '../agenda/_PainelRecursos'

const dias = [
  { date: '2026-09-14', horas: 4, conflito: false },
  { date: '2026-09-15', horas: 0, conflito: false },
  { date: '2026-09-16', horas: 12, conflito: true },
]

describe('FaixaDias', () => {
  it('mostra um alvo por dia, com as horas, e marca o selecionado', () => {
    render(<FaixaDias dias={dias} selecionado="2026-09-15" onSelecionar={vi.fn()} />)
    const alvos = screen.getAllByRole('button')
    expect(alvos).toHaveLength(3)
    expect(alvos[1]).toHaveAttribute('aria-pressed', 'true')
    expect(alvos[0]).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('4h')).toBeInTheDocument()
    expect(screen.getByText('12h')).toBeInTheDocument()
  })

  it('dia vazio não mostra "0h"', () => {
    render(<FaixaDias dias={dias} selecionado="2026-09-14" onSelecionar={vi.fn()} />)
    expect(screen.queryByText('0h')).toBeNull()
  })

  it('dia vazio não anuncia "0h" no aria-label (só no texto visível havia guarda)', () => {
    render(<FaixaDias dias={dias} selecionado="2026-09-14" onSelecionar={vi.fn()} />)
    const vazio = screen.getAllByRole('button')[1]
    expect(vazio.getAttribute('aria-label')).not.toMatch(/0h/)
  })

  it('dia com conflito recebe rótulo acessível', () => {
    render(<FaixaDias dias={dias} selecionado="2026-09-14" onSelecionar={vi.fn()} />)
    expect(screen.getAllByRole('button')[2].getAttribute('aria-label')).toMatch(/conflito/i)
  })

  it('tocar num dia avisa qual', () => {
    const onSelecionar = vi.fn()
    render(<FaixaDias dias={dias} selecionado="2026-09-14" onSelecionar={onSelecionar} />)
    fireEvent.click(screen.getAllByRole('button')[2])
    expect(onSelecionar).toHaveBeenCalledWith('2026-09-16')
  })

  it('todo alvo tem 44px', () => {
    render(<FaixaDias dias={dias} selecionado="2026-09-14" onSelecionar={vi.fn()} />)
    for (const b of screen.getAllByRole('button')) {
      expect(b.className).toContain('min-h-[44px]')
    }
  })
})

const tecnicos = [
  { id: 441, name: 'Afonso', horas: 8 },
  { id: 9, name: 'Bruno', horas: 0 },
]
const instrumentos = [
  { id: 1, name: 'Q001', vencido: false,
    usos: [{ visitaId: 7, osName: 'OS26-02', tecnicoName: 'Afonso', faixa: '08:00–12:00' }] },
  { id: 2, name: 'Q002', vencido: false, usos: [] },
  { id: 3, name: 'Q003', vencido: true, usos: [] },
]

function painel(over = {}) {
  return (
    <PainelRecursos
      dimensao="tecnico"
      onTrocarDimensao={vi.fn()}
      tecnicos={tecnicos}
      pico={Math.max(1, ...tecnicos.map((t) => t.horas))}
      instrumentos={instrumentos}
      instrumentoIdsDaVisita={[]}
      alvoAtivo={false}
      onTocarTecnico={vi.fn()}
      onTocarInstrumento={vi.fn()}
      {...over}
    />
  )
}

describe('PainelRecursos — técnico', () => {
  it('técnico sem hora aparece como livre, não como "0h"', () => {
    render(painel())
    expect(screen.getByText(/livre/i)).toBeInTheDocument()
    expect(screen.queryByText('0h')).toBeNull()
  })

  it('sem alvo ativo, as linhas não são botão', () => {
    render(painel())
    expect(screen.queryByRole('button', { name: /Afonso/ })).toBeNull()
  })

  it('com alvo ativo, tocar num técnico avisa qual', () => {
    const onTocarTecnico = vi.fn()
    render(painel({ alvoAtivo: true, onTocarTecnico }))
    fireEvent.click(screen.getByRole('button', { name: /Bruno/ }))
    expect(onTocarTecnico).toHaveBeenCalledWith(9)
  })

  it('marca o técnico dono da visita em ajuste', () => {
    render(painel({ alvoAtivo: true, tecnicoIdDaVisita: 441 }))
    expect(screen.getByRole('button', { name: /Afonso/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Bruno/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('a barra usa o pico da SEMANA (prop do chamador), não o do dia', () => {
    // Um técnico com 4h num dia onde ele é o mais cheio (pico do dia = 4h)
    // encheria a barra (100%) se a escala fosse local. Passar o pico real da
    // semana (16h, de outro dia) prova que a escala não é recalculada aqui.
    const { container } = render(painel({
      tecnicos: [{ id: 441, name: 'Afonso', horas: 4 }],
      pico: 16,
    }))
    const barra = container.querySelector('.bg-primary') as HTMLElement
    expect(barra.style.width).toBe('25%')
  })
})

describe('PainelRecursos — instrumento', () => {
  it('mostra onde o instrumento está, com a faixa de horário', () => {
    render(painel({ dimensao: 'instrumento' }))
    expect(screen.getByText(/08:00–12:00/)).toBeInTheDocument()
    expect(screen.getByText(/OS26-02/)).toBeInTheDocument()
  })

  it('instrumento sem uso aparece como livre', () => {
    render(painel({ dimensao: 'instrumento' }))
    expect(screen.getAllByText(/livre/i).length).toBeGreaterThan(0)
  })

  it('calibração vencida é dita em texto, não só em cor', () => {
    render(painel({ dimensao: 'instrumento' }))
    expect(screen.getByText(/calibra[çc][ãa]o vencida/i)).toBeInTheDocument()
  })

  it('marca o que a visita selecionada já usa', () => {
    render(painel({ dimensao: 'instrumento', alvoAtivo: true, instrumentoIdsDaVisita: [1] }))
    expect(screen.getByRole('button', { name: /Q001/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Q002/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('com alvo ativo, tocar num instrumento avisa qual', () => {
    const onTocarInstrumento = vi.fn()
    render(painel({ dimensao: 'instrumento', alvoAtivo: true, onTocarInstrumento }))
    fireEvent.click(screen.getByRole('button', { name: /Q002/ }))
    expect(onTocarInstrumento).toHaveBeenCalledWith(2)
  })

  it('o botão de dimensão troca', () => {
    const onTrocarDimensao = vi.fn()
    render(painel({ onTrocarDimensao }))
    fireEvent.click(screen.getByRole('button', { name: /Instrumento/ }))
    expect(onTrocarDimensao).toHaveBeenCalledWith('instrumento')
  })

  it('dois usos no mesmo dia: cada faixa vive em seu próprio nó, não numa string concatenada', () => {
    // Fix round 2: a versão anterior deste teste (`getByText(/08:00–12:00/)`)
    // passava mesmo contra o `join(' | ')` de antes do fix round 1, porque
    // happy-dom/jsdom não aplica layout nem `text-overflow: ellipsis` — o
    // texto truncado nunca some do DOM, só do olho. A asserção "está no
    // documento" era verdadeira nos dois casos; não discriminava o defeito.
    // Este teste afirma ESTRUTURA, não presença de texto.
    const doisUsos = [
      { id: 1, name: 'Q001', vencido: false, usos: [
        { visitaId: 7, osName: 'OS26-02', tecnicoName: 'Afonso', faixa: '08:00–12:00' },
        { visitaId: 8, osName: 'OS26-05', tecnicoName: 'Bruno', faixa: '13:00–17:00' },
      ] },
    ]
    const { container } = render(painel({ dimensao: 'instrumento', instrumentos: doisUsos }))

    // Match EXATO (sem regex): só existe um elemento cujo texto INTEIRO é
    // "08:00–12:00" quando cada uso tem seu próprio nó-folha. Se as duas
    // faixas estivessem concatenadas num span só (`join(' | ')`), nenhum
    // elemento teria texto exatamente igual a uma faixa isolada — o texto
    // do único nó seria a string inteira concatenada — e `getByText` com
    // match exato lançaria "elemento não encontrado".
    const faixa1 = screen.getByText('08:00–12:00')
    const faixa2 = screen.getByText('13:00–17:00')
    expect(faixa1).not.toBe(faixa2)

    // Segunda rede, mais direta: nenhum nó-folha (sem filhos elemento) do
    // DOM contém as duas faixas ao mesmo tempo — é exatamente a assinatura
    // do `join(' | ')` que o fix round 1 removeu.
    const algumNoFolhaTemAsDuas = Array.from(container.querySelectorAll('*')).some(
      (el) =>
        el.children.length === 0 &&
        (el.textContent ?? '').includes('08:00–12:00') &&
        (el.textContent ?? '').includes('13:00–17:00'),
    )
    expect(algumNoFolhaTemAsDuas).toBe(false)
  })
})
