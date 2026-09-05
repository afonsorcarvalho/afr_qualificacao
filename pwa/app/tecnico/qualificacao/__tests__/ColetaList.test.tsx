// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ColetaList } from '../_components/ColetaList'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  usePathname: () => '/tecnico/qualificacao/4',
}))

const item = (over: Record<string, unknown>) => ({
  id: 1,
  name: 'Ciclo 1',
  kind: 'foto',
  required: true,
  state: 'pending',
  description: '',
  instruction: '',
  requires_instrument: false,
  docx_section: false,
  qualif_id: false,
  equipment_id: [10, 'Autoclave A'],
  ...over,
})

const data = {
  os: { id: 4, name: 'OS26-06-0002', partner_id: [2, 'Hospital X'] },
  open_relatorio_id: 99,
  equipments: {},
  instruments: {},
  qualifs: {},
  collect_items: [
    item({ id: 1, name: 'Ciclo 1' }),
    item({ id: 2, name: 'Ciclo 2' }),
    item({ id: 3, name: 'Ciclo 3', state: 'collected', equipment_id: [11, 'Autoclave B'] }),
  ],
} as any

describe('ColetaList', () => {
  it('separa pendentes de coletadas, com a contagem no título', () => {
    render(<ColetaList data={data} osId={4} />)
    expect(screen.getByText('Coletas pendentes (2)')).toBeInTheDocument()
    expect(screen.getByText('Já coletadas (1)')).toBeInTheDocument()
  })

  it('agrupa por equipamento', () => {
    render(<ColetaList data={data} osId={4} />)
    expect(screen.getByText('Autoclave A')).toBeInTheDocument()
    expect(screen.getByText('Autoclave B')).toBeInTheDocument()
  })

  it('marca a coleta selecionada com aria-current, não só com cor', () => {
    render(<ColetaList data={data} osId={4} selectedId={2} />)
    const selecionada = screen.getByRole('link', { name: /Ciclo 2/ })
    expect(selecionada).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('link', { name: /Ciclo 1/ })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('sem relatório aberto, avisa que é preciso iniciar o relatório', () => {
    render(<ColetaList data={{ ...data, open_relatorio_id: null }} osId={4} />)
    expect(screen.getByText(/Inicie o relatório do dia/)).toBeInTheDocument()
    expect(screen.getByText('Prévia das coletas (2)')).toBeInTheDocument()
  })

  it('coleta já feita aberta no painel também recebe aria-current', () => {
    // `CollectedCard` não é link (o único é "Recoletar", que some sem
    // relatório aberto), então o marcador vive no cartão.
    const { container } = render(<ColetaList data={data} osId={4} selectedId={3} />)
    const marcados = container.querySelectorAll('[aria-current="true"]')
    expect(marcados).toHaveLength(1)
    expect(marcados[0]).toHaveTextContent('Ciclo 3')
  })

  it('sem seleção, nenhuma coleta feita fica marcada', () => {
    const { container } = render(<ColetaList data={data} osId={4} />)
    expect(container.querySelectorAll('[aria-current="true"]')).toHaveLength(0)
  })
})
