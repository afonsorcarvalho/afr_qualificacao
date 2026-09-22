import { describe, it, expect } from 'vitest'
import { semanaDe, deslocarSemanas, DIA_INICIO_SEMANA } from './semana'

describe('DIA_INICIO_SEMANA', () => {
  it('é segunda-feira (1, no esquema de Date#getUTCDay), a convenção de produto', () => {
    expect(DIA_INICIO_SEMANA).toBe(1)
  })
})

describe('semanaDe', () => {
  it('numa segunda-feira, from é a própria data (já é o início da semana)', () => {
    expect(semanaDe('2026-09-21')).toEqual({ from: '2026-09-21', to: '2026-09-27' })
  })

  it('num domingo, from é a segunda anterior, seis dias antes — o caso que implementação ingênua erra (getUTCDay()=0 fica "antes" de 1 na escala 0-6)', () => {
    expect(semanaDe('2026-09-27')).toEqual({ from: '2026-09-21', to: '2026-09-27' })
  })

  it('no meio da semana, ancora na segunda e no domingo da mesma semana', () => {
    expect(semanaDe('2026-09-23')).toEqual({ from: '2026-09-21', to: '2026-09-27' })
  })

  it('atravessa virada de mês sem perder a semana (segunda em setembro, domingo em outubro)', () => {
    expect(semanaDe('2026-09-30')).toEqual({ from: '2026-09-28', to: '2026-10-04' })
  })

  it('atravessa virada de ano (segunda em dezembro/2026, domingo em janeiro/2027)', () => {
    expect(semanaDe('2026-12-31')).toEqual({ from: '2026-12-28', to: '2027-01-03' })
  })

  it('29 de fevereiro de ano bissexto não quebra a aritmética de dias', () => {
    expect(semanaDe('2028-02-29')).toEqual({ from: '2028-02-28', to: '2028-03-05' })
  })
})

describe('deslocarSemanas', () => {
  it('n=1 a partir de 2026-09-21 dá exatamente a janela do defeito medido (2026-09-28 a 2026-10-04)', () => {
    expect(deslocarSemanas('2026-09-21', 1)).toEqual({ from: '2026-09-28', to: '2026-10-04' })
  })

  it('n=-1 volta para a semana anterior (segunda a domingo), não sete dias corridos para trás', () => {
    expect(deslocarSemanas('2026-09-21', -1)).toEqual({ from: '2026-09-14', to: '2026-09-20' })
  })
})
