import { describe, it, expect } from 'vitest'
import {
  primeiroDiaDoMes, deslocarMes, gradeDoMes, noMes, rotuloMes,
  corDoTecnico, tecnicosPorDia, PALETA, COR_SEM_TECNICO,
} from '../agenda/mes'
import type { VisitaAgenda, Opcao } from '@/lib/odoo/agenda'
import { semRelogioDoAparelho } from '@/tests/relogio'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { contraste, hex2rgb, hsl2rgb, tokenDe } from '@/tests/contraste'

function v(over: Partial<VisitaAgenda> = {}): VisitaAgenda {
  return {
    id: 1, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 4,
    os_id: 4, os_name: 'OS26-02', os_state: 'scheduled',
    partner_name: 'Hospital', city: 'São Luís',
    equipment_list: [], instrument_list: [], instrument_ids: [],
    tecnico_id: 441, tecnico_name: 'Afonso', is_mine: true,
    state: 'planned', overflow: false, editable: true, lock_reason: false,
    conflict: false, conflict_msg: '', note: '',
    ...over,
  }
}

describe('primeiroDiaDoMes', () => {
  it('normaliza qualquer dia do mês para o dia 1', () => {
    semRelogioDoAparelho(() => {
      expect(primeiroDiaDoMes('2026-09-17')).toBe('2026-09-01')
    })
  })

  it('já no dia 1 permanece', () => {
    expect(primeiroDiaDoMes('2026-01-01')).toBe('2026-01-01')
  })
})

describe('deslocarMes', () => {
  it('não estoura para o mês seguinte ao somar mês em cima de dia 31, sem ler o relógio do aparelho', () => {
    semRelogioDoAparelho(() => {
      expect(deslocarMes('2026-01-31', 1)).toBe('2026-02-01')
    })
  })

  it('virada de ano para trás', () => {
    expect(deslocarMes('2026-01-15', -1)).toBe('2025-12-01')
  })

  it('virada de ano para frente', () => {
    expect(deslocarMes('2026-12-10', 1)).toBe('2027-01-01')
  })

  it('n = 0 devolve o dia 1 do próprio mês da âncora', () => {
    expect(deslocarMes('2026-09-17', 0)).toBe('2026-09-01')
  })
})

describe('gradeDoMes', () => {
  it('tem 42 dias, começa no domingo anterior e cobre o mês inteiro, sem ler o relógio do aparelho', () => {
    semRelogioDoAparelho(() => {
      const g = gradeDoMes('2026-09-17')
      expect(g).toHaveLength(42)
      expect(g[0]).toBe('2026-08-30')
      expect(g[41]).toBe('2026-10-10')
      expect(g).toContain('2026-09-01')
      expect(g).toContain('2026-09-30')
    })
  })

  it('quando o dia 1 cai num domingo, a grade começa nele mesmo', () => {
    const g = gradeDoMes('2026-11-01')
    expect(g[0]).toBe('2026-11-01')
  })

  it('mês que precisa das 6 semanas inclui o dia 31', () => {
    const g = gradeDoMes('2026-05-01')
    expect(g).toContain('2026-05-31')
    expect(g).toHaveLength(42)
  })

  it('fevereiro bissexto inclui 29/02 e não inclui 30/02', () => {
    const g = gradeDoMes('2028-02-01')
    expect(g).toContain('2028-02-29')
    expect(g).not.toContain('2028-02-30')
  })
})

describe('noMes', () => {
  it('marca fora as células acinzentadas do começo e do fim da grade', () => {
    const ancora = '2026-09-17'
    const g = gradeDoMes(ancora)
    expect(noMes(g[0], ancora)).toBe(false) // 2026-08-30
    expect(noMes(g[41], ancora)).toBe(false) // 2026-10-10
    expect(noMes('2026-09-01', ancora)).toBe(true)
    expect(noMes('2026-09-30', ancora)).toBe(true)
  })
})

describe('rotuloMes', () => {
  it('formata "mês de ano" em pt-BR, minúsculo, sem ler o relógio do aparelho', () => {
    semRelogioDoAparelho(() => {
      expect(rotuloMes('2026-09-17')).toBe('setembro de 2026')
    })
  })
})

describe('corDoTecnico', () => {
  it('é estável entre chamadas para o mesmo id', () => {
    expect(corDoTecnico(441)).toBe(corDoTecnico(441))
  })

  it('difere para dois ids que caem em índices diferentes da paleta', () => {
    expect(corDoTecnico(0)).not.toBe(corDoTecnico(1))
  })

  it('id === false devolve a cor neutra de "sem técnico"', () => {
    expect(corDoTecnico(false)).toBe(COR_SEM_TECNICO)
  })

  it('nenhuma cor da paleta coincide com a cor de "sem técnico"', () => {
    expect(PALETA).not.toContain(COR_SEM_TECNICO)
  })
})

describe('tecnicosPorDia', () => {
  const roster: Opcao[] = [
    { id: 441, name: 'Afonso' },
    { id: 9, name: 'Bruno' },
  ]
  const dias = ['2026-09-17', '2026-09-18']

  it('duas visitas do mesmo técnico no dia rendem um único ponto com visitas: 2', () => {
    const r = tecnicosPorDia(
      [v({ id: 1, date: '2026-09-17', tecnico_id: 441 }),
       v({ id: 2, date: '2026-09-17', tecnico_id: 441 })],
      dias, roster,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.pontos).toEqual([
      { id: 441, name: 'Afonso', cor: corDoTecnico(441), visitas: 2 },
    ])
    expect(dia.total).toBe(2)
  })

  it('visita sem técnico rende o ponto "Sem técnico"', () => {
    const r = tecnicosPorDia(
      [v({ id: 1, date: '2026-09-17', tecnico_id: false, tecnico_name: 'Sem técnico' })],
      dias, roster,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.pontos).toEqual([
      { id: false, name: 'Sem técnico', cor: COR_SEM_TECNICO, visitas: 1 },
    ])
  })

  it('dia sem visita nenhuma rende pontos vazios e total zero', () => {
    const r = tecnicosPorDia([], dias, roster)
    expect(r).toEqual([
      { date: '2026-09-17', pontos: [], total: 0, conflito: false },
      { date: '2026-09-18', pontos: [], total: 0, conflito: false },
    ])
  })

  it('conflito reflete v.conflict de qualquer visita do dia', () => {
    const r = tecnicosPorDia(
      [v({ id: 1, date: '2026-09-17', tecnico_id: 441, conflict: false }),
       v({ id: 2, date: '2026-09-17', tecnico_id: 9, conflict: true })],
      dias, roster,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.conflito).toBe(true)
  })

  it('técnico do roster sem visita no dia não vira ponto', () => {
    const r = tecnicosPorDia(
      [v({ id: 1, date: '2026-09-17', tecnico_id: 441 })],
      dias, roster,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.pontos.map((p) => p.id)).toEqual([441])
  })

  it('ordem dos pontos segue a ordem do roster, "sem técnico" por último', () => {
    const r = tecnicosPorDia(
      [v({ id: 1, date: '2026-09-17', tecnico_id: 9 }),
       v({ id: 2, date: '2026-09-17', tecnico_id: 441 }),
       v({ id: 3, date: '2026-09-17', tecnico_id: false, tecnico_name: 'Sem técnico' })],
      dias, roster,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.pontos.map((p) => p.id)).toEqual([441, 9, false])
  })
})

/**
 * Guarda da paleta (fix round 2, achado 5). A paleta original tinha 8 tons e
 * `corDoTecnico` indexa por `id % PALETA.length` com id de BANCO: com 9
 * técnicos a colisão era garantida, e com ids arbitrários acontecia bem
 * antes (3 e 11 caíam na mesma cor). Dois chips idênticos na legenda e dois
 * pontinhos indistinguíveis na célula é exatamente o que o modo Mês existe
 * para evitar.
 */
describe('PALETA', () => {
  it('tem pelo menos 12 tons, todos distintos', () => {
    expect(PALETA.length).toBeGreaterThanOrEqual(12)
    expect(new Set(PALETA).size).toBe(PALETA.length)
  })

  it('ids que colidiam na paleta de 8 (3 e 11) recebem cores diferentes', () => {
    expect(corDoTecnico(3)).not.toBe(corDoTecnico(11))
  })

  it('cada cor da paleta, e o cinza de "sem técnico", passa 3:1 sobre os QUATRO fundos possíveis', () => {
    // Crescer a paleta não pode ser feito pegando qualquer shade: metade do
    // catálogo do Tailwind (amarelo/âmbar claro) some sobre o `--card` quase
    // branco do tema claro, e os tons escuros somem sobre o quase preto do
    // escuro. 3:1 é o piso da WCAG 1.4.11 para elemento gráfico portador de
    // informação — que é o que o pontinho é.
    //
    // `--primary` entra na lista junto com `--card` porque a célula do dia
    // SELECIONADO passou a ter tinta sólida (achado 4) — e o dia selecionado
    // por default é hoje, ou seja, é a primeira célula que o usuário vê, e a
    // que mais costuma ter visita. Medir só sobre `--card` deixaria os
    // pontinhos sumirem exatamente ali.
    const css = readFileSync(join(__dirname, '..', '..', '..', '..', 'app/globals.css'), 'utf8')
    for (const tema of [':root', ':root.dark']) {
      for (const papel of ['card', 'primary']) {
        const fundo = tokenDe(css, tema, papel)
        expect(fundo, `--${papel} ausente em ${tema}`).not.toBeNull()
        const bg = hsl2rgb(fundo!)
        for (const cor of [...PALETA, COR_SEM_TECNICO]) {
          expect(
            contraste(hex2rgb(cor), bg),
            `${cor} sobre --${papel} de ${tema}`,
          ).toBeGreaterThanOrEqual(3)
        }
      }
    }
  })
})
