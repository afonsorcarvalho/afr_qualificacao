// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { DetalhesTraco } from '../agenda/_DetalhesTraco'
import type { TracoVolta } from '@/lib/chat/machine'

describe('DetalhesTraco', () => {
  it('não renderiza nada quando não há tracos', () => {
    const { container } = render(<DetalhesTraco tracos={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('o dobrável fica fechado por padrão (sem atributo open)', () => {
    const tracos: TracoVolta[] = [
      { duracaoMs: 100, chamadas: [{ nome: 'texto' }] },
    ]
    const { container } = render(<DetalhesTraco tracos={tracos} />)
    const details = container.querySelector('details')
    expect(details).toBeTruthy()
    expect(details?.hasAttribute('open')).toBe(false)
  })

  it('numera cada volta e mostra o nome da ferramenta, os argumentos crus e o resumo do resultado', () => {
    const tracos: TracoVolta[] = [
      {
        modelo: 'gemma-4-31b-it', duracaoMs: 2000,
        usage: { prompt_tokens: 4000, completion_tokens: 150, total_tokens: 4150 },
        chamadas: [{
          nome: 'buscar_agenda',
          argumentos: '{"date_from":"2026-09-23","date_to":"2026-09-30"}',
          resultado: '7 visitas (2126, 2128, 2130…)',
        }],
      },
      {
        modelo: 'gemma-4-31b-it', duracaoMs: 1400,
        usage: { prompt_tokens: 812, completion_tokens: 37, total_tokens: 849 },
        chamadas: [{ nome: 'texto' }],
      },
    ]
    const { container, getByText } = render(<DetalhesTraco tracos={tracos} />)
    expect(getByText(/1 · buscar_agenda/)).toBeTruthy()
    expect(getByText('{"date_from":"2026-09-23","date_to":"2026-09-30"}')).toBeTruthy()
    expect(getByText(/7 visitas \(2126, 2128, 2130…\)/)).toBeTruthy()
    expect(getByText(/2 · texto/)).toBeTruthy()
    // O item "texto" não tem bloco de argumentos nem seta de resultado —
    // só existe um <pre> no documento inteiro (o da volta 1).
    expect(container.querySelectorAll('pre')).toHaveLength(1)
  })

  it('rodapé soma tokens e tempo de TODAS as voltas, com o modelo e a contagem de chamadas', () => {
    const tracos: TracoVolta[] = [
      {
        modelo: 'gemma-4-31b-it', duracaoMs: 2000,
        usage: { prompt_tokens: 4000, completion_tokens: 150, total_tokens: 4150 },
        chamadas: [{ nome: 'buscar_agenda', argumentos: '{}', resultado: 'ok' }],
      },
      {
        modelo: 'gemma-4-31b-it', duracaoMs: 1400,
        usage: { prompt_tokens: 812, completion_tokens: 37, total_tokens: 849 },
        chamadas: [{ nome: 'texto' }],
      },
    ]
    const { getByText } = render(<DetalhesTraco tracos={tracos} />)
    expect(getByText(/gemma-4-31b-it/)).toBeTruthy()
    expect(getByText(/2 chamadas/)).toBeTruthy()
    // 4000+812 = 4812 entrada; 150+37 = 187 saída; pt-BR usa ponto de milhar.
    expect(getByText(/4\.812 entrada/)).toBeTruthy()
    expect(getByText(/187 saída/)).toBeTruthy()
    // 2000+1400 = 3400ms = 3,4s (vírgula, não ponto).
    expect(getByText(/3,4s/)).toBeTruthy()
  })

  it('uma única chamada usa o singular ("1 chamada")', () => {
    const tracos: TracoVolta[] = [
      { modelo: 'gemma-4-31b-it', duracaoMs: 500, chamadas: [{ nome: 'texto' }] },
    ]
    const { getByText, queryByText } = render(<DetalhesTraco tracos={tracos} />)
    expect(getByText(/1 chamada\b/)).toBeTruthy()
    expect(queryByText(/1 chamadas/)).toBeNull()
  })

  it('usage ausente numa volta não quebra a soma (trata como zero)', () => {
    const tracos: TracoVolta[] = [
      { modelo: 'gemma-4-31b-it', duracaoMs: 500, chamadas: [{ nome: 'texto' }] },
    ]
    const { getByText } = render(<DetalhesTraco tracos={tracos} />)
    expect(getByText(/0 entrada \/ 0 saída/)).toBeTruthy()
  })
})
