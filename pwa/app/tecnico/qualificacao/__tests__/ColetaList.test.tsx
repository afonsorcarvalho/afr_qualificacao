// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

// Dois equipamentos com pendência no mesmo segmento — é o caso que decide o
// padrão recolhido dos grupos.
const dataMultiGrupo = {
  ...data,
  collect_items: [
    item({ id: 1, name: 'Ciclo 1' }),
    item({ id: 2, name: 'Ciclo 2' }),
    item({ id: 4, name: 'Ciclo 4', equipment_id: [11, 'Autoclave B'] }),
    item({ id: 3, name: 'Ciclo 3', state: 'collected', equipment_id: [11, 'Autoclave B'] }),
  ],
} as any

describe('ColetaList', () => {
  it('abre em Pendentes e mostra a contagem dos dois segmentos', () => {
    render(<ColetaList data={data} osId={4} />)
    expect(screen.getByRole('button', { name: /Pendentes/ })).toHaveAttribute(
      'aria-pressed', 'true',
    )
    expect(screen.getByRole('button', { name: /Realizadas/ })).toHaveAttribute(
      'aria-pressed', 'false',
    )
    // A contagem do segmento inativo continua visível: é ela que diz que há
    // algo do outro lado.
    expect(screen.getByRole('button', { name: /Pendentes.*2/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Realizadas.*1/ })).toBeInTheDocument()
  })

  it('só o segmento ativo entra na lista', () => {
    render(<ColetaList data={data} osId={4} />)
    expect(screen.getByText('Autoclave A')).toBeInTheDocument()
    expect(screen.queryByText('Autoclave B')).not.toBeInTheDocument()
    expect(screen.getByText('Ciclo 1')).toBeInTheDocument()
    expect(screen.queryByText('Ciclo 3')).not.toBeInTheDocument()
  })

  it('trocar de segmento troca o conteúdo da lista', async () => {
    const user = userEvent.setup()
    render(<ColetaList data={data} osId={4} />)
    await user.click(screen.getByRole('button', { name: /Realizadas/ }))
    expect(screen.getByText('Ciclo 3')).toBeInTheDocument()
    expect(screen.queryByText('Ciclo 1')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Realizadas/ })).toHaveAttribute(
      'aria-pressed', 'true',
    )
  })

  it('agrupa por equipamento dentro do segmento', () => {
    render(<ColetaList data={data} osId={4} />)
    expect(screen.getByText('Autoclave A')).toBeInTheDocument()
  })

  it('sem pendentes, abre direto em Realizadas', () => {
    // Abrir em "Pendentes" numa OS terminada mostraria uma lista vazia justo
    // quando não há mais nada a fazer.
    const tudoFeito = {
      ...data,
      collect_items: data.collect_items.map((i: any) => ({ ...i, state: 'collected' })),
    }
    render(<ColetaList data={tudoFeito} osId={4} />)
    expect(screen.getByRole('button', { name: /Realizadas/ })).toHaveAttribute(
      'aria-pressed', 'true',
    )
    // Dois equipamentos, então os grupos nascem recolhidos: o que se vê são
    // os cabeçalhos, não as coletas.
    expect(screen.getByRole('button', { name: /Autoclave A/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Autoclave B/ })).toBeInTheDocument()
  })

  it('segmento vazio diz o que houve, não fica em branco', async () => {
    const user = userEvent.setup()
    const soPendentes = {
      ...data,
      collect_items: data.collect_items.filter((i: any) => i.state === 'pending'),
    }
    render(<ColetaList data={soPendentes} osId={4} />)
    await user.click(screen.getByRole('button', { name: /Realizadas/ }))
    expect(screen.getByText(/Nada coletado ainda/)).toBeInTheDocument()
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

  it('abrir coleta do outro segmento troca o segmento sozinho', () => {
    // Sem isto o filtro reintroduz o defeito que ele não conhece: a linha
    // marcada com `aria-current` fica no segmento escondido.
    const { rerender, container } = render(<ColetaList data={data} osId={4} />)
    expect(screen.getByRole('button', { name: /Pendentes/ })).toHaveAttribute(
      'aria-pressed', 'true',
    )
    rerender(<ColetaList data={data} osId={4} selectedId={3} />)
    expect(screen.getByRole('button', { name: /Realizadas/ })).toHaveAttribute(
      'aria-pressed', 'true',
    )
    expect(container.querySelector('[aria-current="true"]')).toHaveTextContent('Ciclo 3')
  })

  it('escolha manual do segmento sobrevive a re-render sem troca de seleção', () => {
    const { rerender } = render(<ColetaList data={data} osId={4} selectedId={2} />)
    expect(screen.getByRole('button', { name: /Pendentes/ })).toHaveAttribute(
      'aria-pressed', 'true',
    )
    rerender(<ColetaList data={data} osId={4} selectedId={2} />)
    expect(screen.getByRole('button', { name: /Pendentes/ })).toHaveAttribute(
      'aria-pressed', 'true',
    )
  })

  it('sem seleção, nenhuma coleta feita fica marcada', () => {
    const { container } = render(<ColetaList data={data} osId={4} />)
    expect(container.querySelectorAll('[aria-current="true"]')).toHaveLength(0)
  })

  it('mais de um grupo: todos nascem recolhidos', () => {
    render(<ColetaList data={dataMultiGrupo} osId={4} />)
    const cabecalhos = screen.getAllByRole('button', { name: /Autoclave/ })
    expect(cabecalhos).toHaveLength(2)
    for (const c of cabecalhos) expect(c).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Ciclo 1')).not.toBeInTheDocument()
    expect(screen.queryByText('Ciclo 4')).not.toBeInTheDocument()
  })

  it('grupo único nasce expandido', () => {
    // Recolher o único grupo esconderia a lista inteira atrás de um toque
    // sem ganho nenhum de rolagem.
    render(<ColetaList data={data} osId={4} />)
    const cabecalho = screen.getByRole('button', { name: /Autoclave A/ })
    expect(cabecalho).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Ciclo 1')).toBeInTheDocument()
  })

  it('tocar no cabeçalho abre e fecha o grupo', async () => {
    const user = userEvent.setup()
    render(<ColetaList data={dataMultiGrupo} osId={4} />)
    const cabecalho = screen.getByRole('button', { name: /Autoclave A/ })
    await user.click(cabecalho)
    expect(cabecalho).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Ciclo 1')).toBeInTheDocument()
    // O outro segue fechado: abrir um não abre todos.
    expect(screen.queryByText('Ciclo 4')).not.toBeInTheDocument()
    await user.click(cabecalho)
    expect(cabecalho).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Ciclo 1')).not.toBeInTheDocument()
  })

  it('aria-controls do cabeçalho aponta pra lista do grupo', async () => {
    const user = userEvent.setup()
    render(<ColetaList data={dataMultiGrupo} osId={4} />)
    const cabecalho = screen.getByRole('button', { name: /Autoclave A/ })
    await user.click(cabecalho)
    const alvo = document.getElementById(cabecalho.getAttribute('aria-controls')!)
    expect(alvo).not.toBeNull()
    expect(alvo).toHaveTextContent('Ciclo 1')
  })

  it('abrir uma coleta expande o grupo dela', () => {
    render(<ColetaList data={dataMultiGrupo} osId={4} selectedId={4} />)
    expect(screen.getByRole('button', { name: /Autoclave B/ })).toHaveAttribute(
      'aria-expanded', 'true',
    )
    expect(screen.getByRole('button', { name: /Autoclave A/ })).toHaveAttribute(
      'aria-expanded', 'false',
    )
    expect(screen.getByText('Ciclo 4')).toBeInTheDocument()
  })

  it('trocar de coleta por navegação expande o grupo novo', () => {
    const { rerender } = render(
      <ColetaList data={dataMultiGrupo} osId={4} selectedId={4} />,
    )
    rerender(<ColetaList data={dataMultiGrupo} osId={4} selectedId={1} />)
    expect(screen.getByRole('button', { name: /Autoclave A/ })).toHaveAttribute(
      'aria-expanded', 'true',
    )
    expect(screen.getByText('Ciclo 1')).toBeInTheDocument()
  })

  it('equipamento sem item no segmento ativo não aparece', async () => {
    const user = userEvent.setup()
    render(<ColetaList data={dataMultiGrupo} osId={4} />)
    expect(screen.getByRole('button', { name: /Autoclave B/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Realizadas/ }))
    // Só a Autoclave B tem coleta realizada.
    expect(screen.queryByRole('button', { name: /Autoclave A/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Autoclave B/ })).toBeInTheDocument()
  })

  it('cabeçalho mostra o progresso do próprio equipamento', () => {
    // Autoclave B tem 2 coletas na OS, 1 já realizada — o número é do
    // equipamento inteiro, não do segmento em exibição.
    render(<ColetaList data={dataMultiGrupo} osId={4} />)
    const cabecalho = screen.getByRole('button', { name: /Autoclave B/ })
    expect(cabecalho).toHaveTextContent('1 de 2')
    expect(cabecalho.querySelector('.tabular-nums')).not.toBeNull()
    expect(screen.getByRole('button', { name: /Autoclave A/ })).toHaveTextContent('0 de 2')
  })

  it('cabeçalho de grupo aberto é sticky; fechado não', async () => {
    const user = userEvent.setup()
    render(<ColetaList data={dataMultiGrupo} osId={4} />)
    const cabecalho = screen.getByRole('button', { name: /Autoclave A/ })
    expect(cabecalho.className).not.toContain('sticky')
    await user.click(cabecalho)
    expect(cabecalho.className).toContain('sticky')
    // Sem prefixo de breakpoint: com o invólucro de altura definida em toda
    // largura, o `main` rola também no celular e o sticky vale lá.
    expect(cabecalho.className).not.toContain('lg:top-')
    expect(cabecalho.className).toContain('top-[54px]')
  })

  it('o filtro gruda no topo do painel que rola, em toda largura', () => {
    render(<ColetaList data={data} osId={4} />)
    const filtro = screen.getByRole('group', { name: /Filtrar coletas/ })
    expect(filtro.className).toContain('sticky')
    expect(filtro.className).toContain('top-0')
    expect(filtro.className).not.toContain('top-14')
  })
})
