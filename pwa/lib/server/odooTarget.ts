/**
 * Allowlist do proxy `/api/odoo/[...path]` — fecho do SSRF herdado da origem.
 *
 * O proxy encaminha para a URL que o chamador manda em `x-odoo-target` (e,
 * depois do login, no cookie `odoo-target`). Sem validação, qualquer um que
 * alcance a porta do Next faz o servidor buscar endereço arbitrário — inclusive
 * host interno que só o servidor enxerga — e lê a resposta.
 *
 * Fixar um host não serve: o técnico digita o servidor Odoo na tela de login,
 * e o mesmo build atende instâncias diferentes. O controle é declarar por
 * ambiente quais origens valem:
 *
 *   ODOO_ALLOWED_ORIGINS=https://labquali.afrsistemas.com.br,http://localhost:8069
 *
 * Regras de fallback, todas conservadoras:
 *   - `ODOO_URL` sozinho autoriza aquele host (instância única);
 *   - em `NODE_ENV=development`, loopback e rede privada entram sem
 *     configuração, porque é onde o dev roda o Odoo em container;
 *   - fora isso, **sem lista não passa nada** — falha fechado, com mensagem
 *     dizendo o que configurar.
 */

export interface EnvAlvo {
  ODOO_ALLOWED_ORIGINS?: string
  ODOO_URL?: string
  NODE_ENV?: string
}

export type ResultadoAlvo =
  | { ok: true; base: string; veioDoHeader: boolean }
  | { ok: false; motivo: string }

/** Normaliza para `esquema://host[:porta]`, sem barra final nem caminho. */
function origemDe(raw: string): URL | null {
  const bruto = raw.trim()
  if (!bruto) return null
  // Sem esquema explícito não dá pra decidir nada com segurança: `//evil.tld`
  // e `localhost:8069` são ambíguos.
  if (!/^https?:\/\//i.test(bruto)) return null
  let u: URL
  try {
    u = new URL(bruto)
  } catch {
    return null
  }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
  // Credenciais embutidas confundem parser e leitor humano: `http://ok@evil.tld`
  // parece apontar pro host permitido e não aponta.
  if (u.username || u.password) return null
  return u
}

/** `esquema://host:porta` canônico — a chave de comparação da allowlist. */
export function origemCanonica(raw: string): string | null {
  const u = origemDe(raw)
  if (!u) return null
  return `${u.protocol}//${u.host}`.toLowerCase()
}

export function alvoPermitido(alvo: string, permitidas: string[]): boolean {
  const origem = origemCanonica(alvo)
  if (!origem) return false
  return permitidas.some((p) => origemCanonica(p) === origem)
}

/** Loopback e faixas privadas — só valem em desenvolvimento. */
function ehRedeLocal(host: string): boolean {
  const nome = host.toLowerCase()
  if (nome === 'localhost' || nome.endsWith('.localhost')) return true
  if (nome === '::1' || nome === '[::1]') return true
  const ipv4 = nome.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/)
  if (!ipv4) return false
  const [a, b] = [Number(ipv4[1]), Number(ipv4[2])]
  if (a === 127) return true
  if (a === 10) return true
  if (a === 192 && b === 168) return true
  if (a === 172 && b >= 16 && b <= 31) return true
  return false
}

function listaConfigurada(env: EnvAlvo): string[] {
  const declaradas = (env.ODOO_ALLOWED_ORIGINS ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  if (declaradas.length > 0) return declaradas
  return env.ODOO_URL ? [env.ODOO_URL] : []
}

export function resolverAlvoOdoo({
  header,
  cookie,
  env,
}: {
  header: string | null | undefined
  cookie: string | null | undefined
  env: EnvAlvo
}): ResultadoAlvo {
  // O header é o vetor: quando presente, ele é o candidato — nunca se cai no
  // cookie pra "consertar" um header recusado. Sem nenhum dos dois, vale o
  // padrão do próprio operador (`ODOO_URL`), que é o modo instância única.
  const candidato = header ?? cookie ?? env.ODOO_URL
  const deHeader = Boolean(header)

  if (!candidato) {
    return {
      ok: false,
      motivo:
        'Nenhum servidor Odoo informado. Faça login novamente escolhendo o servidor.',
    }
  }

  const origem = origemCanonica(candidato)
  if (!origem) {
    return { ok: false, motivo: 'Endereço de servidor inválido.' }
  }

  const permitidas = listaConfigurada(env)
  if (permitidas.length > 0) {
    if (!alvoPermitido(candidato, permitidas)) {
      return {
        ok: false,
        motivo: `Servidor não autorizado: ${origem}. Origens permitidas são declaradas em ODOO_ALLOWED_ORIGINS.`,
      }
    }
    return { ok: true, base: origem, veioDoHeader: deHeader }
  }

  const host = new URL(origem).hostname
  if (env.NODE_ENV === 'development') {
    if (ehRedeLocal(host)) {
      return { ok: true, base: origem, veioDoHeader: deHeader }
    }
    return {
      ok: false,
      motivo: `Servidor não autorizado: ${origem}. Em desenvolvimento o proxy só alcança loopback e rede privada; para outros destinos declare ODOO_ALLOWED_ORIGINS.`,
    }
  }

  return {
    ok: false,
    motivo:
      'Proxy sem allowlist configurada. Defina ODOO_ALLOWED_ORIGINS (ou ODOO_URL) com as origens Odoo autorizadas.',
  }
}
