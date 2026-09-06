import { describe, it, expect } from 'vitest'
import { mensagemDoErro, nomeDoErro } from '../erro'

describe('mensagemDoErro', () => {
  it('lê a mensagem de um Error', () => {
    expect(mensagemDoErro(new Error('deu ruim'))).toBe('deu ruim')
  })

  it('cai no padrão quando o Error não tem mensagem', () => {
    // `new Error()` tem `message: ''`, e string vazia na tela é pior que
    // texto genérico: o técnico vê um toast em branco.
    expect(mensagemDoErro(new Error(''))).toBe('Erro inesperado')
  })

  it('aceita string solta', () => {
    expect(mensagemDoErro('sem sinal')).toBe('sem sinal')
    expect(mensagemDoErro('   ')).toBe('Erro inesperado')
  })

  it('aceita objeto com message de outra origem', () => {
    // Erro que atravessa realm (worker, iframe, JSON de API) não passa no
    // `instanceof Error`, mas continua tendo `message`.
    expect(mensagemDoErro({ message: 'vindo do worker' })).toBe('vindo do worker')
  })

  it('ignora message que não é string', () => {
    expect(mensagemDoErro({ message: 42 })).toBe('Erro inesperado')
    expect(mensagemDoErro({ message: null })).toBe('Erro inesperado')
  })

  it('sobrevive a null, undefined e tipos exóticos', () => {
    expect(mensagemDoErro(null)).toBe('Erro inesperado')
    expect(mensagemDoErro(undefined)).toBe('Erro inesperado')
    expect(mensagemDoErro(0)).toBe('Erro inesperado')
    expect(mensagemDoErro([])).toBe('Erro inesperado')
  })

  it('aceita um padrão próprio', () => {
    expect(mensagemDoErro(null, 'indisponível')).toBe('indisponível')
    expect(mensagemDoErro(new Error('real'), 'indisponível')).toBe('real')
  })
})

describe('nomeDoErro', () => {
  it('lê o name de um Error', () => {
    const e = new Error('x')
    e.name = 'NotAllowedError'
    expect(nomeDoErro(e)).toBe('NotAllowedError')
  })

  it('lê o name de objeto de outra origem', () => {
    // É assim que o erro do getUserMedia chega: o que distingue "usuário
    // negou o microfone" de "falhou" é o `name`, não a mensagem.
    expect(nomeDoErro({ name: 'SecurityError' })).toBe('SecurityError')
  })

  it('devolve undefined quando não há name utilizável', () => {
    expect(nomeDoErro(null)).toBeUndefined()
    expect(nomeDoErro('texto')).toBeUndefined()
    expect(nomeDoErro({ name: 7 })).toBeUndefined()
  })
})
