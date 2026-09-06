// @vitest-environment happy-dom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { mensagemDeFalha } from '../client'

/**
 * Estas frases são o que o técnico lê quando a rede ou o servidor falham —
 * antes delas a tela mostrava `Request failed with status code 502`, texto do
 * axios, em inglês, sobre uma camada que ele não conhece. O DESIGN.md pede
 * erro como instrução em pt-BR dizendo se o trabalho foi perdido, e não havia
 * teste nenhum segurando isso.
 */

afterEach(() => {
  vi.unstubAllGlobals()
})

const semRede = () =>
  vi.stubGlobal('navigator', { ...globalThis.navigator, onLine: false })

describe('mensagemDeFalha', () => {
  it('sem status e sem rede: diz que é falta de sinal e que nada se perdeu', () => {
    semRede()
    const m = mensagemDeFalha(new Error('Network Error'))
    expect(m).toMatch(/Sem conexão/)
    expect(m).toMatch(/continua aqui/)
  })

  it('sem status mas com rede: culpa o servidor, não o sinal', () => {
    const m = mensagemDeFalha(new Error('Network Error'))
    expect(m).toMatch(/Não deu para falar com o servidor/)
    expect(m).toMatch(/continua aqui/)
  })

  it('403 fala de permissão e aponta o que fazer', () => {
    const m = mensagemDeFalha({ response: { status: 403 } })
    expect(m).toMatch(/não tem permissão/i)
    expect(m).toMatch(/responsável/)
  })

  it('404 manda atualizar a tela', () => {
    expect(mensagemDeFalha({ response: { status: 404 } })).toMatch(/Atualize a tela/)
  })

  it('5xx nomeia o código e garante que nada se perdeu', () => {
    const m = mensagemDeFalha({ response: { status: 502 } })
    expect(m).toMatch(/erro 502/)
    expect(m).toMatch(/continua aqui/)
  })

  it('outros status caem numa frase genérica, ainda em pt-BR e com o código', () => {
    const m = mensagemDeFalha({ response: { status: 418 } })
    expect(m).toMatch(/erro 418/)
    expect(m).not.toMatch(/status code/)
  })

  it('nunca vaza o texto do axios', () => {
    for (const e of [
      new Error('Request failed with status code 502'),
      { response: { status: 500 } },
      null,
      'qualquer coisa',
    ]) {
      expect(mensagemDeFalha(e)).not.toMatch(/Request failed|status code/)
    }
  })

  it('formato inesperado de erro não quebra nem vira status', () => {
    // `response` que não é objeto, `status` que não é número: antes a leitura
    // era `error?.response?.status` sobre `any` e um `status: "500"` viraria
    // comparação de string com número, sem o compilador reclamar.
    expect(mensagemDeFalha({ response: 'nada disso' })).toMatch(/servidor/)
    expect(mensagemDeFalha({ response: { status: '500' } })).toMatch(/servidor/)
    expect(mensagemDeFalha(undefined)).toMatch(/servidor/)
  })
})

describe('mensagemDeFalha: espera longa', () => {
  it('timeout do axios vira frase sobre o servidor demorar, não sobre milissegundos', () => {
    // O que apareceu na tela de login em 2026-09-05 foi
    // "timeout of 15000ms exceeded" — texto do axios, em inglês, sobre uma
    // unidade que não diz nada pra quem está em campo. E o caso real é
    // banal: Odoo recém-reiniciado carregando o registry na primeira
    // requisição que toca o banco.
    const e = Object.assign(new Error('timeout of 15000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    const m = mensagemDeFalha(e)
    expect(m).toMatch(/demorou/i)
    expect(m).toMatch(/tente de novo/i)
    expect(m).not.toMatch(/timeout|exceeded|ms\b/)
  })

  it('o timeout do fetch nativo (AbortError) cai na mesma frase', () => {
    const e = Object.assign(new Error('The operation was aborted'), {
      name: 'AbortError',
    })
    expect(mensagemDeFalha(e)).toMatch(/demorou/i)
  })

  it('sem rede continua sendo falta de sinal, não demora', () => {
    semRede()
    expect(mensagemDeFalha(new Error('Network Error'))).toMatch(/Sem conexão/)
  })
})
