// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'
import odooClient from '../client'

vi.mock('axios', async () => {
  const real = await vi.importActual<typeof import('axios')>('axios')
  return {
    ...real,
    default: { ...real.default, post: vi.fn(), create: real.default.create },
  }
})

/**
 * `getDatabases` e `authenticate` acontecem ANTES de haver sessão, então usam
 * `axios.post` direto com o alvo no header, em vez da instância do cliente —
 * e por isso escapavam do interceptor que traduz falha de transporte.
 *
 * O resultado apareceu na tela de login em 2026-09-05: "timeout of 15000ms
 * exceeded", em inglês, sobre milissegundos, na primeira tela do app.
 */

const demora = () =>
  Object.assign(new Error('timeout of 15000ms exceeded'), { code: 'ECONNABORTED' })

beforeEach(() => {
  vi.mocked(axios.post).mockReset()
})

describe('authenticate', () => {
  it('traduz falha de transporte em vez de vazar o texto do axios', async () => {
    vi.mocked(axios.post).mockRejectedValueOnce(demora())
    await expect(
      odooClient.authenticate('http://localhost:8084', 'db', 'u', 'p'),
    ).rejects.toThrow(/demorou/i)
    await expect(
      odooClient.authenticate('http://localhost:8084', 'db', 'u', 'p'),
    ).rejects.not.toThrow(/timeout|exceeded/)
  })

  it('502 do proxy também vira frase em pt-BR', async () => {
    vi.mocked(axios.post).mockRejectedValue({ response: { status: 502 } })
    await expect(
      odooClient.authenticate('http://localhost:8084', 'db', 'u', 'p'),
    ).rejects.toThrow(/erro 502/)
  })

  it('credencial errada continua sendo credencial errada, não falha de rede', async () => {
    // O Odoo responde 200 com `result` vazio; não é erro de transporte e não
    // pode virar "o servidor demorou".
    vi.mocked(axios.post).mockResolvedValue({ data: { result: null } })
    await expect(
      odooClient.authenticate('http://localhost:8084', 'db', 'u', 'p'),
    ).rejects.toThrow(/Login ou senha incorretos/)
  })
})

describe('getDatabases', () => {
  it('traduz falha de transporte', async () => {
    vi.mocked(axios.post).mockRejectedValue(demora())
    await expect(odooClient.getDatabases('http://localhost:8084')).rejects.toThrow(
      /demorou/i,
    )
  })

  it('lista normalmente quando dá certo', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: { result: ['a', 'b'] } })
    await expect(odooClient.getDatabases('http://localhost:8084')).resolves.toEqual([
      'a',
      'b',
    ])
  })
})
