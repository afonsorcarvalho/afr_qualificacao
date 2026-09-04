import { describe, it, expect } from 'vitest'
import { resolverAlvoOdoo, alvoPermitido } from '@/lib/server/odooTarget'

/**
 * O proxy `/api/odoo/[...path]` encaminha para a URL que o próprio chamador
 * manda no header `x-odoo-target`. Sem validação, quem alcança a porta 3010
 * faz o servidor Next buscar qualquer endereço — inclusive host interno da
 * rede — e lê a resposta: SSRF clássico.
 *
 * A lista de origens permitidas é o controle. Ela não pode ser fixa porque o
 * técnico digita o servidor no login (o app é multi-instância), mas pode ser
 * declarada por ambiente.
 */
describe('alvoPermitido', () => {
  const lista = ['http://localhost:8069', 'https://labquali.afrsistemas.com.br']

  it('aceita origem exatamente listada', () => {
    expect(alvoPermitido('http://localhost:8069', lista)).toBe(true)
    expect(alvoPermitido('https://labquali.afrsistemas.com.br', lista)).toBe(true)
  })

  it('ignora barra final e diferença de caixa no host', () => {
    expect(alvoPermitido('http://LOCALHOST:8069/', lista)).toBe(true)
  })

  it('recusa host não listado', () => {
    expect(alvoPermitido('http://169.254.169.254', lista)).toBe(false)
    expect(alvoPermitido('http://metadata.internal', lista)).toBe(false)
  })

  it('recusa porta diferente no mesmo host', () => {
    expect(alvoPermitido('http://localhost:9999', lista)).toBe(false)
  })

  it('recusa esquema diferente no mesmo host', () => {
    expect(alvoPermitido('https://localhost:8069', lista)).toBe(false)
  })

  it('recusa subdomínio que apenas termina igual', () => {
    expect(alvoPermitido('https://evil-labquali.afrsistemas.com.br', lista)).toBe(false)
    expect(alvoPermitido('https://labquali.afrsistemas.com.br.evil.tld', lista)).toBe(false)
  })

  it('recusa protocolo que não é http(s)', () => {
    expect(alvoPermitido('file:///etc/passwd', lista)).toBe(false)
    expect(alvoPermitido('gopher://localhost:8069', lista)).toBe(false)
  })

  it('recusa URL com credenciais embutidas', () => {
    // `http://localhost:8069@evil.tld` é lido como host `evil.tld` por alguns
    // parsers e como `localhost` por outros — não passa em nenhum caso.
    expect(alvoPermitido('http://localhost:8069@evil.tld', lista)).toBe(false)
    expect(alvoPermitido('http://user:senha@localhost:8069', lista)).toBe(false)
  })

  it('lista vazia recusa tudo — falha fechado', () => {
    expect(alvoPermitido('http://localhost:8069', [])).toBe(false)
  })
})

describe('resolverAlvoOdoo', () => {
  const env = { ODOO_ALLOWED_ORIGINS: 'http://localhost:8069' }

  it('usa o header quando ele é permitido', () => {
    const r = resolverAlvoOdoo({ header: 'http://localhost:8069', cookie: null, env })
    expect(r).toEqual({ ok: true, base: 'http://localhost:8069', veioDoHeader: true })
  })

  it('cai no cookie quando não há header', () => {
    const r = resolverAlvoOdoo({ header: null, cookie: 'http://localhost:8069', env })
    expect(r).toEqual({ ok: true, base: 'http://localhost:8069', veioDoHeader: false })
  })

  it('recusa header fora da lista mesmo com cookie válido', () => {
    // O header é o vetor de ataque: não pode ser "melhorado" pelo fallback.
    const r = resolverAlvoOdoo({
      header: 'http://169.254.169.254',
      cookie: 'http://localhost:8069',
      env,
    })
    expect(r.ok).toBe(false)
  })

  it('recusa cookie adulterado', () => {
    const r = resolverAlvoOdoo({ header: null, cookie: 'http://evil.tld', env })
    expect(r.ok).toBe(false)
  })

  it('sem lista configurada e sem ODOO_URL, recusa tudo', () => {
    const r = resolverAlvoOdoo({ header: 'http://localhost:8069', cookie: null, env: {} })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.motivo).toMatch(/ODOO_ALLOWED_ORIGINS/)
  })

  it('ODOO_URL sozinho já autoriza aquele host (modo instância única)', () => {
    const r = resolverAlvoOdoo({
      header: null,
      cookie: null,
      env: { ODOO_URL: 'http://localhost:8069' },
    })
    expect(r).toEqual({ ok: true, base: 'http://localhost:8069', veioDoHeader: false })
  })

  it('em desenvolvimento libera loopback e rede privada sem configuração', () => {
    const dev = { NODE_ENV: 'development' }
    expect(resolverAlvoOdoo({ header: 'http://localhost:8084', cookie: null, env: dev }).ok).toBe(true)
    expect(resolverAlvoOdoo({ header: 'http://172.24.97.65:8084', cookie: null, env: dev }).ok).toBe(true)
    // Mesmo em dev, host público não entra por acidente.
    expect(resolverAlvoOdoo({ header: 'http://exemplo.com', cookie: null, env: dev }).ok).toBe(false)
  })

  it('produção não herda a liberação de desenvolvimento', () => {
    const prod = { NODE_ENV: 'production' }
    expect(resolverAlvoOdoo({ header: 'http://172.24.97.65:8084', cookie: null, env: prod }).ok).toBe(false)
  })
})
