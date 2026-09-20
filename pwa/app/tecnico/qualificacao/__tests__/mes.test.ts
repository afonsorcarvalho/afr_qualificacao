import { describe, it, expect } from 'vitest'
import {
  primeiroDiaDoMes, deslocarMes, gradeDoMes, noMes, rotuloMes,
  corDoTecnico, tecnicosPorDia, PALETA, COR_SEM_TECNICO,
  corDoInstrumento, instrumentosPorDia, conflitosPorDia,
} from '../agenda/mes'
import type { VisitaAgenda, Opcao, InstrumentoOpcao } from '@/lib/odoo/agenda'
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

  // Cor configurada (Task 2, plano cor-por-recurso): o índice do seletor
  // nativo do Odoo vira índice direto da PALETA — 1 -> PALETA[1], 2 ->
  // PALETA[2] etc. — quando é um índice válido (1..PALETA.length - 1).
  it('índice configurado (>= 1) vence a cor automática, indexando direto a PALETA', () => {
    expect(corDoTecnico(441, 3)).toBe(PALETA[3])
  })

  it('NÃO-REGRESSÃO: sem color, o resultado é idêntico ao de hoje — `PALETA[id % PALETA.length]`, a fórmula anterior a esta task', () => {
    expect(corDoTecnico(441)).toBe(PALETA[441 % PALETA.length])
    expect(corDoTecnico(441, undefined)).toBe(PALETA[441 % PALETA.length])
  })

  it('color === 0 ("sem cor" no Odoo) mantém a cor automática — quem não configurou nada não vê diferença', () => {
    expect(corDoTecnico(441, 0)).toBe(corDoTecnico(441))
  })

  it('color fora da faixa (>= PALETA.length) não quebra e cai na cor automática', () => {
    expect(corDoTecnico(441, PALETA.length)).toBe(corDoTecnico(441))
    expect(corDoTecnico(441, 999)).toBe(corDoTecnico(441))
  })

  it('color negativo não quebra e cai na cor automática', () => {
    expect(corDoTecnico(441, -1)).toBe(corDoTecnico(441))
  })

  it('dois técnicos com o MESMO índice configurado ficam com a MESMA cor — esperado, não defeito: é o que a configuração manual permite', () => {
    // ids escolhidos de propósito para NÃO colidirem na cor automática
    // (1 % 12 = 1, 2 % 12 = 2 -> tons distintos sem configuração): se o
    // teste comparasse dois ids que já colidem sozinhos, passaria mesmo
    // ignorando `color` por completo.
    expect(corDoTecnico(1)).not.toBe(corDoTecnico(2))
    expect(corDoTecnico(1, 5)).toBe(PALETA[5])
    expect(corDoTecnico(2, 5)).toBe(PALETA[5])
    expect(corDoTecnico(1, 5)).toBe(corDoTecnico(2, 5))
  })

  it('id === false ignora color e devolve sempre a cor neutra de "sem técnico"', () => {
    expect(corDoTecnico(false, 5)).toBe(COR_SEM_TECNICO)
  })

  // Vetores REAIS da RPC não tipada (fix round 3, achado 3) — `color?:
  // number` é a assinatura TypeScript, não uma garantia de runtime. Os casos
  // acima só cobrem 0, undefined, negativo e estouro; `null`/`false`/string/
  // float são o que de fato chega de um payload sem tipagem — em especial
  // `false`, sentinela clássica do Odoo pra "sem valor" nos campos JSON-RPC.
  // Todos caem na cor automática, sem exceção.
  it('color null (RPC não tipada) cai na cor automática', () => {
    expect(corDoTecnico(441, null as any)).toBe(corDoTecnico(441))
  })

  it('color false (RPC não tipada) cai na cor automática', () => {
    expect(corDoTecnico(441, false as any)).toBe(corDoTecnico(441))
  })

  it('color string (RPC não tipada) cai na cor automática, mesmo parecendo um índice válido', () => {
    expect(corDoTecnico(441, '5' as any)).toBe(corDoTecnico(441))
  })

  it('color float/não-inteiro (RPC não tipada) cai na cor automática', () => {
    expect(corDoTecnico(441, 3.5 as any)).toBe(corDoTecnico(441))
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

  // Propagação da cor configurada (Task 2): o roster carrega `color` (via
  // `rosterTecnicos`, testado em carga.test.ts) e o ponto usa exatamente a
  // mesma regra de `corDoTecnico`.
  it('usa a cor configurada do técnico no roster quando presente', () => {
    const rosterComCor: Opcao[] = [
      { id: 441, name: 'Afonso', color: 6 },
      { id: 9, name: 'Bruno' },
    ]
    const r = tecnicosPorDia(
      [v({ id: 1, date: '2026-09-17', tecnico_id: 441 })],
      dias, rosterComCor,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.pontos[0].cor).toBe(PALETA[6])
  })

  it('técnico sem color no roster mantém a cor automática (não-regressão)', () => {
    const r = tecnicosPorDia(
      [v({ id: 1, date: '2026-09-17', tecnico_id: 441 })],
      dias, roster,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.pontos[0].cor).toBe(corDoTecnico(441))
  })
})

describe('corDoInstrumento', () => {
  it('é estável entre chamadas para o mesmo id', () => {
    expect(corDoInstrumento(7)).toBe(corDoInstrumento(7))
  })

  it('vem da mesma PALETA usada por corDoTecnico', () => {
    expect(PALETA).toContain(corDoInstrumento(3))
  })

  // Mesma regra de `corDoTecnico`: índice configurado vence, mesma indexação
  // direta na PALETA.
  it('índice configurado (>= 1) vence a cor automática, indexando direto a PALETA', () => {
    expect(corDoInstrumento(3, 7)).toBe(PALETA[7])
  })

  it('NÃO-REGRESSÃO: sem color, o resultado é idêntico ao de hoje — `PALETA[id % PALETA.length]`, a fórmula anterior a esta task', () => {
    expect(corDoInstrumento(3)).toBe(PALETA[3 % PALETA.length])
    expect(corDoInstrumento(3, undefined)).toBe(PALETA[3 % PALETA.length])
  })

  it('color === 0 mantém a cor automática', () => {
    expect(corDoInstrumento(3, 0)).toBe(corDoInstrumento(3))
  })

  it('color fora da faixa não quebra e cai na cor automática', () => {
    expect(corDoInstrumento(3, PALETA.length)).toBe(corDoInstrumento(3))
    expect(corDoInstrumento(3, -5)).toBe(corDoInstrumento(3))
  })

  it('dois instrumentos com o MESMO índice configurado ficam com a MESMA cor — esperado', () => {
    // ids escolhidos de propósito para NÃO colidirem na cor automática
    // (1 % 12 = 1, 5 % 12 = 5 -> tons distintos sem configuração).
    expect(corDoInstrumento(1)).not.toBe(corDoInstrumento(5))
    expect(corDoInstrumento(1, 4)).toBe(PALETA[4])
    expect(corDoInstrumento(5, 4)).toBe(PALETA[4])
    expect(corDoInstrumento(1, 4)).toBe(corDoInstrumento(5, 4))
  })

  // Mesmos vetores não-numéricos de `corDoTecnico` — `corConfigurada` é
  // compartilhada pelas duas funções, mas a cobertura tem que existir dos
  // dois lados independentemente.
  it('color null (RPC não tipada) cai na cor automática', () => {
    expect(corDoInstrumento(3, null as any)).toBe(corDoInstrumento(3))
  })

  it('color false (RPC não tipada) cai na cor automática', () => {
    expect(corDoInstrumento(3, false as any)).toBe(corDoInstrumento(3))
  })

  it('color string (RPC não tipada) cai na cor automática, mesmo parecendo um índice válido', () => {
    expect(corDoInstrumento(3, '5' as any)).toBe(corDoInstrumento(3))
  })

  it('color float/não-inteiro (RPC não tipada) cai na cor automática', () => {
    expect(corDoInstrumento(3, 3.5 as any)).toBe(corDoInstrumento(3))
  })
})

describe('instrumentosPorDia', () => {
  const opcoes: InstrumentoOpcao[] = [
    { id: 5, name: 'Multímetro', validade: '2027-01-01' },
    { id: 8, name: 'Termômetro', validade: false },
  ]
  const dias = ['2026-09-17', '2026-09-18']

  it('duas visitas usando o mesmo instrumento no dia rendem um único item com visitas: 2', () => {
    const r = instrumentosPorDia(
      [v({ id: 1, date: '2026-09-17', instrument_ids: [5], instrument_list: ['Multímetro'] }),
       v({ id: 2, date: '2026-09-17', instrument_ids: [5], instrument_list: ['Multímetro'] })],
      dias, opcoes,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.instrumentos).toEqual([
      { id: 5, name: 'Multímetro', cor: corDoInstrumento(5), visitas: 2 },
    ])
  })

  it('instrumento fora de `opcoes` vira "Instrumento #<id>", sem parear por índice com instrument_list', () => {
    // `instrument_list` é filtrada de nomes vazios no servidor, então pode
    // ficar mais curta que `instrument_ids` — aqui ela traz só o nome de UM
    // instrumento (o 5) enquanto `instrument_ids` também usa o 99, que não
    // está em `opcoes`. Se o código pareasse por posição, o 99 roubaria o
    // nome "Multímetro" do índice 0.
    const r = instrumentosPorDia(
      [v({ id: 1, date: '2026-09-17', instrument_ids: [99], instrument_list: ['Multímetro'] })],
      dias, opcoes,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.instrumentos).toEqual([
      { id: 99, name: 'Instrumento #99', cor: corDoInstrumento(99), visitas: 1 },
    ])
  })

  it('dia sem visita rende instrumentos: []', () => {
    const r = instrumentosPorDia([], dias, opcoes)
    expect(r).toEqual([
      { date: '2026-09-17', instrumentos: [] },
      { date: '2026-09-18', instrumentos: [] },
    ])
  })

  it('instrumento das opções não usado no dia não vira item', () => {
    const r = instrumentosPorDia(
      [v({ id: 1, date: '2026-09-17', instrument_ids: [5], instrument_list: ['Multímetro'] })],
      dias, opcoes,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.instrumentos.map((i) => i.id)).toEqual([5])
  })

  it('ordem é por nome (não pela ordem de `opcoes`), com desconhecidos no fim por id crescente', () => {
    // Fix final (M-1): a ordem deixou de ser a de `opcoes` e passou a ser a
    // de `ordenarInstrumentos` — a MESMA que a legenda aplica em `page.tsx`.
    // A ordem do servidor era uma regra que só a célula conseguia aplicar (a
    // legenda não recebe `opcoes`), então as duas metades da tela desenhavam
    // o mesmo conjunto em sequências diferentes.
    //
    // `opcoes` aqui vem em ordem DECRESCENTE de id e com os nomes fora de
    // ordem alfabética de propósito: se o código voltasse a seguir `opcoes`,
    // sairia [8, 5, ...] em vez de [5, 8, ...].
    const opcoesInvertidas: InstrumentoOpcao[] = [
      { id: 8, name: 'Termômetro', validade: false },
      { id: 5, name: 'Multímetro', validade: '2027-01-01' },
    ]
    const r = instrumentosPorDia(
      [v({ id: 1, date: '2026-09-17', instrument_ids: [8, 5, 99, 50] })],
      dias, opcoesInvertidas,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    // Conhecidos por nome (Multímetro < Termômetro), desconhecidos no fim por
    // id — identificador fabricado nunca encabeça a lista.
    expect(dia.instrumentos.map((i) => i.id)).toEqual([5, 8, 50, 99])
  })

  it('nome com número usa colação numérica: TAG-2 antes de TAG-10', () => {
    // `localeCompare` sem `{ numeric: true }` compara caractere a caractere e
    // põe "TAG-10" antes de "TAG-2" — com tags sequenciais (o caso comum do
    // cadastro), a célula e a legenda ficavam numa ordem que não é a que o
    // técnico lê na etiqueta.
    const opcoesTags: InstrumentoOpcao[] = [
      { id: 1, name: 'TAG-10', validade: false },
      { id: 2, name: 'TAG-2', validade: false },
      { id: 3, name: 'TAG-3', validade: false },
    ]
    const r = instrumentosPorDia(
      [v({ id: 1, date: '2026-09-17', instrument_ids: [1, 2, 3] })],
      dias, opcoesTags,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.instrumentos.map((i) => i.name)).toEqual(['TAG-2', 'TAG-3', 'TAG-10'])
  })

  // Propagação da cor configurada (Task 2, plano cor-por-recurso): `opcoes`
  // carrega `color` (vindo de `pwa_instrumento_options`) e o item usa
  // exatamente a mesma regra de `corDoInstrumento`.
  it('usa a cor configurada do instrumento em `opcoes` quando presente', () => {
    const opcoesComCor: InstrumentoOpcao[] = [
      { id: 5, name: 'Multímetro', validade: '2027-01-01', color: 9 },
      { id: 8, name: 'Termômetro', validade: false },
    ]
    const r = instrumentosPorDia(
      [v({ id: 1, date: '2026-09-17', instrument_ids: [5] })],
      dias, opcoesComCor,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.instrumentos[0].cor).toBe(PALETA[9])
  })

  it('instrumento sem color em `opcoes` mantém a cor automática (não-regressão)', () => {
    const r = instrumentosPorDia(
      [v({ id: 1, date: '2026-09-17', instrument_ids: [5] })],
      dias, opcoes,
    )
    const dia = r.find((d) => d.date === '2026-09-17')!
    expect(dia.instrumentos[0].cor).toBe(corDoInstrumento(5))
  })

  describe('parâmetro `ligados` (camada 2 do filtro — Task 2 bugfix)', () => {
    // A camada 1 (`visitasVisiveis` em `page.tsx`) já decide QUAIS visitas
    // sobrevivem; dentro de uma visita sobrevivente, `ligados` decide quais
    // dos SEUS instrumentos ainda viram marca. Sem isso, uma visita com dois
    // instrumentos (um ligado, um desligado) desenhava os dois — o bug
    // relatado (Q001 desligado continuava no aria-label da célula de 1/out).
    it('sem `ligados` (undefined), comportamento idêntico ao de antes — todo instrumento usado vira item', () => {
      const r = instrumentosPorDia(
        [v({ id: 1, date: '2026-09-17', instrument_ids: [5, 8] })],
        dias, opcoes,
      )
      const dia = r.find((d) => d.date === '2026-09-17')!
      expect(dia.instrumentos.map((i) => i.id)).toEqual([5, 8])
    })

    it('com `ligados` restrito, instrumento fora do conjunto não vira item nem entra na contagem', () => {
      const r = instrumentosPorDia(
        [v({ id: 1, date: '2026-09-17', instrument_ids: [5, 8] })],
        dias, opcoes, new Set([5]),
      )
      const dia = r.find((d) => d.date === '2026-09-17')!
      expect(dia.instrumentos).toEqual([
        { id: 5, name: 'Multímetro', cor: corDoInstrumento(5), visitas: 1 },
      ])
    })

    it('`ligados` vazio (Set sem nenhum id) zera os instrumentos do dia, sem quebrar a célula', () => {
      const r = instrumentosPorDia(
        [v({ id: 1, date: '2026-09-17', instrument_ids: [5, 8] })],
        dias, opcoes, new Set(),
      )
      const dia = r.find((d) => d.date === '2026-09-17')!
      expect(dia.instrumentos).toEqual([])
    })

    it('`ligados: null` (mesmo sentido de undefined — sem restrição) não filtra nada', () => {
      const r = instrumentosPorDia(
        [v({ id: 1, date: '2026-09-17', instrument_ids: [5, 8] })],
        dias, opcoes, null,
      )
      const dia = r.find((d) => d.date === '2026-09-17')!
      expect(dia.instrumentos.map((i) => i.id)).toEqual([5, 8])
    })
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

  // Trava de CONTEÚDO (fix round 3, achado 2): os testes acima e os de
  // `corDoTecnico`/`corDoInstrumento` fixam a FÓRMULA (`PALETA[id %
  // PALETA.length]`), não os valores — reordenar dois tons "pra ficar mais
  // bonito", ou trocar um tom por outro que ainda passe o contraste, segue
  // verde em todos eles, e todo recurso não configurado muda de cor em
  // silêncio. Hex literais e ORDEM aqui, de propósito: qualquer reordenação
  // ou substituição de tom tem que quebrar este teste.
  it('TRAVA DE CONTEÚDO: os 12 tons são exatamente estes, nesta ordem', () => {
    expect(PALETA).toEqual([
      '#db2777', // pink-600
      '#059669', // emerald-600
      '#8b5cf6', // violet-500
      '#ea580c', // orange-600
      '#0284c7', // sky-600
      '#f43f5e', // rose-500
      '#0d9488', // teal-600
      '#c026d3', // fuchsia-600
      '#16a34a', // green-600
      '#3b82f6', // blue-500
      '#dc2626', // red-600
      '#0891b2', // cyan-600
    ])
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

/**
 * Guarda de contraste da barra de estado do dia (Task 1). Mesmo método da
 * guarda da `PALETA` logo acima (hsl→rgb + razão WCAG), só que medindo os
 * TOKENS `--ok`/`--danger`/`--primary-foreground` em vez da paleta hex de
 * técnico.
 *
 * Duas medições, dois papéis diferentes na barra:
 *
 * 1. `--ok`/`--danger` contra `--card` (o fundo da célula NÃO selecionada,
 *    nos dois temas): 6.94–9.93:1, folgado. É essa dupla que pinta o
 *    PREENCHIMENTO da barra sempre — inclusive no dia selecionado, onde o
 *    preenchimento sozinho mede só 1.77–2.63:1 contra `--primary` (medido no
 *    fix round 1, abaixo do piso de 3:1).
 * 2. `--primary-foreground` contra `--primary` (o par que já pinta o TEXTO
 *    do dia selecionado, `text-primary-foreground`): 14.17:1 (claro) e
 *    18.23:1 (escuro) — é essa dupla que sustenta o CONTORNO de 1px que a
 *    barra ganha só no dia selecionado (`ring-1 ring-inset
 *    ring-primary-foreground` em `_GradeMes.tsx`).
 *
 * A saída (fix round 1, decidida com o coordinator desta task depois que a
 * primeira versão — suprimir a barra inteira no dia selecionado — se provou
 * errada no navegador: o dia default nasce SELECIONADO e é frequentemente o
 * que mais precisa da barra): a WCAG 1.4.11 mede o contraste do LIMITE
 * (boundary) de um elemento gráfico de estado, não do preenchimento inteiro
 * — e o limite pode usar um token diferente do preenchimento. Por isso a
 * barra continua sempre visível (preenchimento `--ok`/`--danger`, o mesmo
 * token do dia não selecionado — o MATIZ nunca muda) e ganha só um contorno
 * de 1px em `--primary-foreground` quando o dia está selecionado, cumprindo
 * 1.4.11 pelo contorno sem precisar de um token de preenchimento novo.
 *
 * Não existe tom de PREENCHIMENTO fixo que limpe 3:1 contra `--card` E
 * `--primary` ao mesmo tempo nos dois temas — os dois fundos sentam em
 * extremos opostos de luminância de propósito (claro no tema claro é
 * `--card` quase branco e `--primary` quase preto; o inverso no escuro) — daí
 * o contorno, não uma terceira cor de preenchimento inventada.
 */
describe('barra de estado do dia: --ok/--danger sobre --card, e --primary-foreground sobre --primary (contorno do dia selecionado)', () => {
  it('--ok e --danger passam 3:1 sobre --card no claro e no escuro (preenchimento da barra)', () => {
    const css = readFileSync(join(__dirname, '..', '..', '..', '..', 'app/globals.css'), 'utf8')
    for (const tema of [':root', ':root.dark']) {
      const card = tokenDe(css, tema, 'card')
      expect(card, `--card ausente em ${tema}`).not.toBeNull()
      const bg = hsl2rgb(card!)
      for (const papel of ['ok', 'danger']) {
        const token = tokenDe(css, tema, papel)
        expect(token, `--${papel} ausente em ${tema}`).not.toBeNull()
        expect(
          contraste(hsl2rgb(token!), bg),
          `--${papel} sobre --card em ${tema}`,
        ).toBeGreaterThanOrEqual(3)
      }
    }
  })

  it('--primary-foreground passa 3:1 sobre --primary no claro e no escuro (contorno da barra no dia selecionado)', () => {
    const css = readFileSync(join(__dirname, '..', '..', '..', '..', 'app/globals.css'), 'utf8')
    for (const tema of [':root', ':root.dark']) {
      const primary = tokenDe(css, tema, 'primary')
      const primaryFg = tokenDe(css, tema, 'primary-foreground')
      expect(primary, `--primary ausente em ${tema}`).not.toBeNull()
      expect(primaryFg, `--primary-foreground ausente em ${tema}`).not.toBeNull()
      expect(
        contraste(hsl2rgb(primaryFg!), hsl2rgb(primary!)),
        `--primary-foreground sobre --primary em ${tema}`,
      ).toBeGreaterThanOrEqual(3)
    }
  })
})

describe('conflitosPorDia', () => {
  const dias = ['2026-09-17', '2026-09-18']

  it('devolve só as datas com alguma visita em conflito', () => {
    const r = conflitosPorDia(
      [
        v({ id: 1, date: '2026-09-17', conflict: true }),
        v({ id: 2, date: '2026-09-18', conflict: false }),
      ],
      dias,
    )
    expect(r).toEqual(new Set(['2026-09-17']))
  })

  it('data com conflito fora da janela (`dias`) não entra', () => {
    // O filtro NÃO é sobre as visitas passadas (que continuam sendo TODAS as
    // da janela em modo Mês, não filtradas pelas duas faixas) — é sobre a
    // grade de dias recebida: uma visita de conflito fora dos 42 dias
    // pedidos (o que hoje não acontece em produção, já que `visitas` vem do
    // fetch ancorado na própria grade) não deve poder vazar para o `Set`.
    const r = conflitosPorDia(
      [v({ id: 1, date: '2026-08-01', conflict: true })],
      dias,
    )
    expect(r).toEqual(new Set())
  })

  it('dia sem visita não entra; lista vazia devolve conjunto vazio', () => {
    expect(conflitosPorDia([], dias)).toEqual(new Set())
    expect(conflitosPorDia([v({ date: '2026-09-17', conflict: false })], dias)).toEqual(new Set())
  })

  it('fonte é a lista completa, não filtrada — o filtro das duas faixas não pode esconder conflito', () => {
    // `conflitosPorDia` não sabe nada sobre técnico/instrumento — recebe
    // sempre a `visitas` que o chamador decidir passar. Este teste documenta
    // a intenção do lado de `page.tsx`: a função em si só varre o que
    // recebe, então uma visita de qualquer técnico/instrumento entra desde
    // que `conflict` seja `true` e a data esteja em `dias`.
    const r = conflitosPorDia(
      [v({ id: 1, date: '2026-09-17', tecnico_id: 9, instrument_ids: [999], conflict: true })],
      dias,
    )
    expect(r).toEqual(new Set(['2026-09-17']))
  })

  it('duas visitas em conflito no mesmo dia rendem uma única entrada no Set', () => {
    const r = conflitosPorDia(
      [
        v({ id: 1, date: '2026-09-17', conflict: true }),
        v({ id: 2, date: '2026-09-17', conflict: true }),
      ],
      dias,
    )
    expect(r.size).toBe(1)
  })
})
