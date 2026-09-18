// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { GradeMes } from '../agenda/_GradeMes'
import { gradeDoMes } from '../agenda/mes'
import type { PontosDia, PontoTecnico, PontosInstrumentoDia, PontoInstrumento } from '../agenda/mes'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { contraste, hsl2rgb, tokenDe } from '@/tests/contraste'

const ANCORA = '2026-09-01'
const GRADE = gradeDoMes(ANCORA) // 42 dias: 2026-08-30 .. 2026-10-10

function ponto(over: Partial<PontoTecnico> = {}): PontoTecnico {
  return { id: 1, name: 'Ana Silva', cor: '#0ea5e9', visitas: 1, ...over }
}

function pontosDiaVazio(date: string): PontosDia {
  return { date, pontos: [], total: 0, conflito: false }
}

/** Grade de 42 `PontosDia` vazios, com overrides por data ISO. */
function montarDias(overrides: Record<string, Partial<PontosDia>> = {}): PontosDia[] {
  return GRADE.map((date) => ({ ...pontosDiaVazio(date), ...(overrides[date] ?? {}) }))
}

function instrumento(over: Partial<PontoInstrumento> = {}): PontoInstrumento {
  return { id: 101, name: 'Q001', cor: '#059669', visitas: 1, ...over }
}

/** Grade de 42 `PontosInstrumentoDia` vazios, com overrides por data ISO. */
function montarInstrumentos(
  overrides: Record<string, PontoInstrumento[]> = {},
): PontosInstrumentoDia[] {
  return GRADE.map((date) => ({ date, instrumentos: overrides[date] ?? [] }))
}

/**
 * `Set` de datas (ISO) em conflito — a prop `conflitos`, fonte NÃO FILTRADA
 * (Task 1 da barra de estado). Prop OBRIGATÓRIA em `GradeMes`, de propósito:
 * sem default aqui, todo `render` deste arquivo precisa decidir e declarar
 * o estado de conflito, em vez de um valor implícito que esconderia o dia
 * `page.tsx` esquecer de passar a prop de verdade.
 */
function montarConflitos(...datas: string[]): Set<string> {
  return new Set(datas)
}

describe('GradeMes', () => {
  it('renderiza 42 células, uma por dia da grade', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(screen.getAllByRole('button')).toHaveLength(42)
  })

  it('célula fora do mês leva o prefixo no aria-label e continua clicável', () => {
    const onSelecionar = vi.fn()
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={onSelecionar}
      />,
    )
    // 2026-08-30 é o primeiro dia da grade, fora do mês de setembro.
    const cel = screen.getByRole('button', { name: /^fora do mês, 30 de agosto, sem visitas$/ })
    fireEvent.click(cel)
    expect(onSelecionar).toHaveBeenCalledWith('2026-08-30')
  })

  it('aria-pressed é true só na célula selecionada', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-05"
        onSelecionar={vi.fn()}
      />,
    )
    const pressionados = screen.getAllByRole('button', { pressed: true })
    expect(pressionados).toHaveLength(1)
    expect(pressionados[0]).toHaveAccessibleName(/5 de setembro/)
  })

  it('dia com 6 técnicos distintos mostra 3 pontos e o rótulo +3', () => {
    const dias = montarDias({
      '2026-09-17': {
        total: 6,
        pontos: [
          ponto({ id: 1, name: 'Ana Silva' }),
          ponto({ id: 2, name: 'Bruno' }),
          ponto({ id: 3, name: 'Carla' }),
          ponto({ id: 4, name: 'Dario' }),
          ponto({ id: 5, name: 'Elis' }),
          ponto({ id: 6, name: 'Fabio' }),
        ],
      },
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(within(cel).getAllByTestId('ponto')).toHaveLength(3)
    expect(within(cel).getByTestId('mais')).toHaveTextContent('+3')
  })

  it('dia vazio tem aria-label "sem visitas"', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: '1 de setembro, sem visitas' }),
    ).toBeInTheDocument()
  })

  it('dia com conflito tem o sufixo ", com conflito" no aria-label', () => {
    // `PontosDia.conflito` (filtrado) fica `false` de propósito — desde a
    // Task 1 o sufixo lê `conflitos` (não filtrado), nunca mais este campo.
    // Ver o par de testes dedicado a essa troca de fonte, no describe
    // "barra de estado do dia" abaixo.
    const dias = montarDias({
      '2026-09-10': {
        total: 1,
        pontos: [ponto({ id: 1, name: 'Ana Silva' })],
      },
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos('2026-09-10')}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', {
        name: '10 de setembro, 1 visita: Ana Silva, com conflito',
      }),
    ).toBeInTheDocument()
  })

  it('visita sem técnico aparece como "Sem técnico" no aria-label', () => {
    const dias = montarDias({
      '2026-09-12': {
        total: 1,
        pontos: [ponto({ id: false, name: 'Sem técnico', cor: '#6b7280' })],
      },
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: '12 de setembro, 1 visita: Sem técnico' }),
    ).toBeInTheDocument()
  })

  it('hoje === null não marca nenhuma célula como hoje', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const todas = screen.getAllByRole('button')
    expect(todas.every((b) => !b.className.includes('ring-primary'))).toBe(true)
  })

  it('hoje marca só a célula correspondente, distinta da seleção', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje="2026-09-20"
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const marcadas = screen
      .getAllByRole('button')
      .filter((b) => b.className.includes('ring-primary'))
    expect(marcadas).toHaveLength(1)
    expect(marcadas[0]).toHaveAccessibleName(/20 de setembro/)
  })

  // --- fix round 2, achado 3: "hoje" era marcado SÓ visualmente ---

  it('a célula de hoje diz "hoje" no aria-label, não só pelo anel', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje="2026-09-20"
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    // Cor/anel sozinhos violam a Global Constraint #4: quem usa leitor de
    // tela não ouvia nada sobre hoje, ainda que o label já carregasse dia,
    // total, nomes, conflito e "fora do mês".
    expect(
      screen.getByRole('button', { name: '20 de setembro, hoje, sem visitas' }),
    ).toBeInTheDocument()
    // Uma célula só — o sufixo não pode vazar para as vizinhas.
    expect(screen.getAllByRole('button', { name: /hoje/ })).toHaveLength(1)
  })

  it('com hoje === null nenhum aria-label menciona hoje', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(screen.queryAllByRole('button', { name: /hoje/ })).toHaveLength(0)
  })

  // --- fix round 2, achado 6: nomes de menos quando um técnico repete no dia ---

  it('técnico com duas visitas no mesmo dia leva a contagem no aria-label', () => {
    const dias = montarDias({
      '2026-09-15': {
        total: 3,
        pontos: [
          ponto({ id: 1, name: 'Ana Silva', visitas: 2 }),
          ponto({ id: 2, name: 'João Lima', visitas: 1 }),
        ],
      },
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    // Antes: "3 visitas: Ana Silva, João Lima" — dois nomes para três
    // visitas, e nada dizendo de quem era a terceira.
    expect(
      screen.getByRole('button', {
        name: '15 de setembro, 3 visitas: Ana Silva (2), João Lima',
      }),
    ).toBeInTheDocument()
  })

  it('técnico com uma visita só continua sem contagem pendurada', () => {
    const dias = montarDias({
      '2026-09-16': { total: 1, pontos: [ponto({ id: 1, name: 'Ana Silva', visitas: 1 })] },
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: '16 de setembro, 1 visita: Ana Silva' }),
    ).toBeInTheDocument()
  })

  // --- fix round 2, achado 4: seleção e fora-do-mês quase invisíveis ---

  it('o dia selecionado recebe tinta de fundo sólida, não o bg-accent de ~1.08:1', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-05"
        onSelecionar={vi.fn()}
      />,
    )
    const sel = screen.getAllByRole('button', { pressed: true })[0]
    expect(sel.className).toContain('bg-primary')
    expect(sel.className).toContain('text-primary-foreground')
    // `bg-accent` funcionava na FaixaDias porque lá o parceiro de contraste
    // era o texto (muted vs foreground); na grade todos os dias do mês já
    // são `text-foreground`, e sobrava um `font-semibold` num número de 12px.
    expect(sel.className).not.toContain('bg-accent')
  })

  it('--primary sobre --card passa os 3:1 da WCAG 1.4.11 nos dois temas', () => {
    // O indicador de estado tem piso próprio (1.4.11), e é a medição — não o
    // olho — que decide se a tinta escolhida serve. `--accent` sobre
    // `--card` dava 1.08:1 no claro e 1.05:1 no escuro.
    const css = readFileSync(join(__dirname, '..', '..', '..', '..', 'app/globals.css'), 'utf8')
    for (const tema of [':root', ':root.dark']) {
      const primary = tokenDe(css, tema, 'primary')
      const card = tokenDe(css, tema, 'card')
      expect(primary, `--primary ausente em ${tema}`).not.toBeNull()
      expect(card, `--card ausente em ${tema}`).not.toBeNull()
      expect(
        contraste(hsl2rgb(primary!), hsl2rgb(card!)),
        `--primary sobre --card em ${tema}`,
      ).toBeGreaterThanOrEqual(3)
    }
  })

  it('a marca de hoje continua distinta da seleção quando os dois caem na mesma célula', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje="2026-09-05"
        selecionado="2026-09-05"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getAllByRole('button', { pressed: true })[0]
    // Sobre o fundo sólido da seleção, um anel `ring-primary` sumiria (é a
    // mesma cor do fundo) — o anel inverte junto.
    expect(cel.className).toContain('ring-primary-foreground')
  })

  it('célula fora do mês difere da de dentro por mais que a troca de token de texto', () => {
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-10"
        onSelecionar={vi.fn()}
      />,
    )
    const fora = screen.getByRole('button', { name: /^fora do mês, 30 de agosto,/ })
    const dentro = screen.getByRole('button', { name: /^1 de setembro,/ })
    // O stripper é defensivo: hoje os tokens de cor moram no botão, não no
    // número — se algum dia descerem para cá, a asserção continua exigindo
    // uma diferença ALÉM deles, que é o que a review pediu.
    const semTokenDeTexto = (c: string) =>
      c.replace(/text-(?:muted-foreground|foreground|primary-foreground)/g, '').trim()
    const numFora = within(fora).getByTestId('numero').className
    const numDentro = within(dentro).getByTestId('numero').className
    // Trocar só o token de texto é o que a validação manual achou fraco nos
    // DOIS temas; a diferença tem que sobreviver a apagar os tokens de cor.
    expect(semTokenDeTexto(numFora)).not.toBe(semTokenDeTexto(numDentro))
  })

  // --- Task 2: triângulos de instrumento e regra de lotação da célula ---

  it('dia com 2 técnicos e 1 instrumento mostra 3 marcas, sem +N', () => {
    const dias = montarDias({
      '2026-09-17': {
        total: 2,
        pontos: [ponto({ id: 1, name: 'Ana Silva' }), ponto({ id: 2, name: 'João Lima' })],
      },
    })
    const instrumentos = montarInstrumentos({
      '2026-09-17': [instrumento({ id: 101, name: 'Q001' })],
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={instrumentos}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(within(cel).getAllByTestId('ponto')).toHaveLength(2)
    expect(within(cel).getAllByTestId('triangulo')).toHaveLength(1)
    expect(within(cel).queryByTestId('mais')).not.toBeInTheDocument()
  })

  it('dia com 3 técnicos e 5 instrumentos mostra +5 sem apagar nenhum dos dois grupos', () => {
    const dias = montarDias({
      '2026-09-17': {
        total: 3,
        pontos: [
          ponto({ id: 1, name: 'Ana Silva' }),
          ponto({ id: 2, name: 'Bruno' }),
          ponto({ id: 3, name: 'Carla' }),
        ],
      },
    })
    const instrumentos = montarInstrumentos({
      '2026-09-17': [
        instrumento({ id: 101, name: 'Q001' }),
        instrumento({ id: 102, name: 'Q002' }),
        instrumento({ id: 103, name: 'Q003' }),
        instrumento({ id: 104, name: 'Q004' }),
        instrumento({ id: 105, name: 'Q005' }),
      ],
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={instrumentos}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
    // A repartição de slots garante 1 pra cada grupo antes de dar o slot
    // extra pro maior — sem essa garantia, os 3 técnicos engoliriam as 3
    // marcas e os 5 instrumentos sumiriam por inteiro atrás do "+N".
    expect(within(cel).getAllByTestId('ponto').length).toBeGreaterThanOrEqual(1)
    expect(within(cel).getAllByTestId('triangulo').length).toBeGreaterThanOrEqual(1)
    expect(
      within(cel).getAllByTestId('ponto').length + within(cel).getAllByTestId('triangulo').length,
    ).toBe(3)
    expect(within(cel).getByTestId('mais')).toHaveTextContent('+5')
  })

  // --- Task 3 (review da Task 2): bordas de `repartirMarcas` ---

  it('total === 4 marcas (2 técnicos + 2 instrumentos) mostra as 4, sem +N', () => {
    const dias = montarDias({
      '2026-09-17': {
        total: 2,
        pontos: [ponto({ id: 1, name: 'Ana Silva' }), ponto({ id: 2, name: 'João Lima' })],
      },
    })
    const instrumentos = montarInstrumentos({
      '2026-09-17': [
        instrumento({ id: 101, name: 'Q001' }),
        instrumento({ id: 102, name: 'Q002' }),
      ],
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={instrumentos}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(within(cel).getAllByTestId('ponto')).toHaveLength(2)
    expect(within(cel).getAllByTestId('triangulo')).toHaveLength(2)
    expect(within(cel).queryByTestId('mais')).not.toBeInTheDocument()
  })

  it('empate com estouro (3 técnicos + 3 instrumentos): o slot extra vai para os técnicos', () => {
    const dias = montarDias({
      '2026-09-17': {
        total: 3,
        pontos: [
          ponto({ id: 1, name: 'Ana Silva' }),
          ponto({ id: 2, name: 'Bruno' }),
          ponto({ id: 3, name: 'Carla' }),
        ],
      },
    })
    const instrumentos = montarInstrumentos({
      '2026-09-17': [
        instrumento({ id: 101, name: 'Q001' }),
        instrumento({ id: 102, name: 'Q002' }),
        instrumento({ id: 103, name: 'Q003' }),
      ],
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={instrumentos}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
    // 6 marcas ao todo, só 3 cabem soltas: 1 slot garantido pra cada grupo
    // + o 3º (o do empate) vai para os técnicos, não para os instrumentos.
    expect(within(cel).getAllByTestId('ponto')).toHaveLength(2)
    expect(within(cel).getAllByTestId('triangulo')).toHaveLength(1)
    expect(within(cel).getByTestId('mais')).toHaveTextContent('+3')
  })

  it('dia com 5 instrumentos e nenhum técnico mostra 3 triângulos e +2', () => {
    const instrumentos = montarInstrumentos({
      '2026-09-17': [
        instrumento({ id: 101, name: 'Q001' }),
        instrumento({ id: 102, name: 'Q002' }),
        instrumento({ id: 103, name: 'Q003' }),
        instrumento({ id: 104, name: 'Q004' }),
        instrumento({ id: 105, name: 'Q005' }),
      ],
    })
    render(
      <GradeMes
        dias={montarDias()}
        conflitos={montarConflitos()}
        instrumentos={instrumentos}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(within(cel).getAllByTestId('triangulo')).toHaveLength(3)
    expect(within(cel).queryAllByTestId('ponto')).toHaveLength(0)
    expect(within(cel).getByTestId('mais')).toHaveTextContent('+2')
  })

  it('aria-label lista os instrumentos do dia depois das visitas', () => {
    const dias = montarDias({
      '2026-09-17': {
        total: 3,
        pontos: [ponto({ id: 1, name: 'Ana Silva', visitas: 2 }), ponto({ id: 2, name: 'João Lima' })],
      },
    })
    const instrumentos = montarInstrumentos({
      '2026-09-17': [
        instrumento({ id: 101, name: 'Q001' }),
        instrumento({ id: 102, name: 'Q002' }),
      ],
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={instrumentos}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', {
        name: '17 de setembro, 3 visitas: Ana Silva (2), João Lima; instrumentos: Q001, Q002',
      }),
    ).toBeInTheDocument()
  })

  it('conflito e instrumentos juntos: o sufixo de conflito fica colado nas visitas, antes de "instrumentos:"', () => {
    // `PontosDia.conflito` fica `false` — o sufixo lê `conflitos` (não
    // filtrado), ver o describe "barra de estado do dia".
    const dias = montarDias({
      '2026-09-19': {
        total: 1,
        pontos: [ponto({ id: 1, name: 'Ana Silva' })],
      },
    })
    const instrumentos = montarInstrumentos({
      '2026-09-19': [instrumento({ id: 101, name: 'Q001' })],
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos('2026-09-19')}
        instrumentos={instrumentos}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    // ", com conflito" qualifica as visitas — precisa ficar colado nelas,
    // não depois da lista de instrumentos (que leria como se o conflito
    // fosse dos instrumentos).
    expect(
      screen.getByRole('button', {
        name: '19 de setembro, 1 visita: Ana Silva, com conflito; instrumentos: Q001',
      }),
    ).toBeInTheDocument()
  })

  it('dia sem instrumento não escreve a parte de instrumentos no aria-label', () => {
    const dias = montarDias({
      '2026-09-18': { total: 1, pontos: [ponto({ id: 1, name: 'Ana Silva' })] },
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={montarInstrumentos()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: '18 de setembro, 1 visita: Ana Silva' }),
    ).toBeInTheDocument()
  })

  it('bolinhas e triângulos continuam fora da árvore de acessibilidade', () => {
    const instrumentos = montarInstrumentos({
      '2026-09-17': [instrumento({ id: 101, name: 'Q001' })],
    })
    const dias = montarDias({
      '2026-09-17': { total: 1, pontos: [ponto({ id: 1, name: 'Ana Silva' })] },
    })
    render(
      <GradeMes
        dias={dias}
        conflitos={montarConflitos()}
        instrumentos={instrumentos}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
    const ponto1 = within(cel).getByTestId('ponto')
    const triangulo1 = within(cel).getByTestId('triangulo')
    expect(ponto1.closest('[aria-hidden]')).not.toBeNull()
    expect(triangulo1).toHaveAttribute('aria-hidden')
  })

  // --- Task 1 (plano "agenda-barra-estado-dia"): barra de estado por dia ---

  describe('barra de estado do dia', () => {
    it('dia com visita e sem conflito mostra a barra --ok', () => {
      const dias = montarDias({
        '2026-09-17': { total: 1, pontos: [ponto({ id: 1, name: 'Ana Silva' })] },
      })
      render(
        <GradeMes
          dias={dias}
          conflitos={montarConflitos()}
          instrumentos={montarInstrumentos()}
          ancora={ANCORA}
          hoje={null}
          selecionado="2026-09-01"
          onSelecionar={vi.fn()}
        />,
      )
      const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
      const barra = within(cel).getByTestId('barra-estado')
      expect(barra.className).toContain('bg-ok')
      expect(barra.className).not.toContain('bg-danger')
    })

    it('dia com conflito mostra a barra --danger, mesmo havendo visita (conflito manda sobre visita)', () => {
      const dias = montarDias({
        '2026-09-17': { total: 1, pontos: [ponto({ id: 1, name: 'Ana Silva' })] },
      })
      render(
        <GradeMes
          dias={dias}
          conflitos={montarConflitos('2026-09-17')}
          instrumentos={montarInstrumentos()}
          ancora={ANCORA}
          hoje={null}
          selecionado="2026-09-01"
          onSelecionar={vi.fn()}
        />,
      )
      const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
      const barra = within(cel).getByTestId('barra-estado')
      expect(barra.className).toContain('bg-danger')
      expect(barra.className).not.toContain('bg-ok')
    })

    it('dia vazio (sem visita, sem conflito) não mostra barra nenhuma', () => {
      render(
        <GradeMes
          dias={montarDias()}
          conflitos={montarConflitos()}
          instrumentos={montarInstrumentos()}
          ancora={ANCORA}
          hoje={null}
          selecionado="2026-09-05"
          onSelecionar={vi.fn()}
        />,
      )
      const cel = screen.getByRole('button', { name: '17 de setembro, sem visitas' })
      expect(within(cel).queryByTestId('barra-estado')).not.toBeInTheDocument()
    })

    it('conflito sem NENHUMA visita visível (filtro escondeu todas) ainda mostra a barra --danger — consequência aceita do brief', () => {
      // `dia.total === 0` (filtrado) mas a data está em `conflitos` (não
      // filtrado): o dia pode ficar sem nenhum pontinho e com barra vermelha
      // mesmo assim — é a consequência que o brief pede para assumir.
      render(
        <GradeMes
          dias={montarDias()}
          conflitos={montarConflitos('2026-09-17')}
          instrumentos={montarInstrumentos()}
          ancora={ANCORA}
          hoje={null}
          selecionado="2026-09-01"
          onSelecionar={vi.fn()}
        />,
      )
      const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
      expect(within(cel).queryAllByTestId('ponto')).toHaveLength(0)
      const barra = within(cel).getByTestId('barra-estado')
      expect(barra.className).toContain('bg-danger')
    })

    it('dia SELECIONADO não mostra a barra — --ok/--danger medem 1.77–2.63:1 sobre --primary, abaixo do piso de 3:1 (ver guarda em mes.test.ts); o aria-label continua carregando a mesma informação', () => {
      const dias = montarDias({
        '2026-09-05': { total: 1, pontos: [ponto({ id: 1, name: 'Ana Silva' })] },
      })
      render(
        <GradeMes
          dias={dias}
          conflitos={montarConflitos('2026-09-05')}
          instrumentos={montarInstrumentos()}
          ancora={ANCORA}
          hoje={null}
          selecionado="2026-09-05"
          onSelecionar={vi.fn()}
        />,
      )
      const cel = screen.getAllByRole('button', { pressed: true })[0]
      expect(within(cel).queryByTestId('barra-estado')).not.toBeInTheDocument()
      // A informação não se perde — só o portador visual é suprimido aqui.
      expect(cel).toHaveAccessibleName(/5 de setembro, 1 visita: Ana Silva, com conflito/)
    })

    it('a barra é aria-hidden e não entra na árvore de acessibilidade', () => {
      const dias = montarDias({
        '2026-09-17': { total: 1, pontos: [ponto({ id: 1, name: 'Ana Silva' })] },
      })
      render(
        <GradeMes
          dias={dias}
          conflitos={montarConflitos()}
          instrumentos={montarInstrumentos()}
          ancora={ANCORA}
          hoje={null}
          selecionado="2026-09-01"
          onSelecionar={vi.fn()}
        />,
      )
      const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
      const barra = within(cel).getByTestId('barra-estado')
      expect(barra).toHaveAttribute('aria-hidden')
    })
  })

  // --- Task 1, item 1c: a fonte do sufixo ", com conflito" mudou de
  // `PontosDia.conflito` (filtrado) para `conflitos` (não filtrado). O par
  // abaixo prova a troca de fonte especificamente — sem ele, reverter 1c
  // (voltar a ler `dia.conflito`) deixaria a suíte inteira verde, porque os
  // outros testes deste arquivo sempre mantêm as duas fontes consistentes. ---

  describe('1c: fonte do sufixo ", com conflito" é `conflitos`, não `PontosDia.conflito`', () => {
    it('PontosDia.conflito=true com `conflitos` vazio NÃO produz o sufixo', () => {
      const dias = montarDias({
        '2026-09-17': {
          total: 1,
          conflito: true,
          pontos: [ponto({ id: 1, name: 'Ana Silva' })],
        },
      })
      render(
        <GradeMes
          dias={dias}
          conflitos={montarConflitos()}
          instrumentos={montarInstrumentos()}
          ancora={ANCORA}
          hoje={null}
          selecionado="2026-09-01"
          onSelecionar={vi.fn()}
        />,
      )
      expect(
        screen.getByRole('button', { name: '17 de setembro, 1 visita: Ana Silva' }),
      ).toBeInTheDocument()
    })

    it('PontosDia.conflito=false com a data em `conflitos` PRODUZ o sufixo', () => {
      const dias = montarDias({
        '2026-09-17': {
          total: 1,
          conflito: false,
          pontos: [ponto({ id: 1, name: 'Ana Silva' })],
        },
      })
      render(
        <GradeMes
          dias={dias}
          conflitos={montarConflitos('2026-09-17')}
          instrumentos={montarInstrumentos()}
          ancora={ANCORA}
          hoje={null}
          selecionado="2026-09-01"
          onSelecionar={vi.fn()}
        />,
      )
      expect(
        screen.getByRole('button', {
          name: '17 de setembro, 1 visita: Ana Silva, com conflito',
        }),
      ).toBeInTheDocument()
    })
  })
})
