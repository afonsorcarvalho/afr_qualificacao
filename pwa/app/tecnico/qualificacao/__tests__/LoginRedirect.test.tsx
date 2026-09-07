// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { NextRequest } from 'next/server'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import LoginPage from '../../../login/page'
import { destinoSeguro } from '@/lib/navegacao'
import { middleware } from '@/middleware'

const push = vi.fn()
const replace = vi.fn()

// `vi.hoisted`: a fábrica de `vi.mock` abaixo é hoisted acima destas
// declarações, então o estado mutável de `?next=` que ela lê precisa nascer
// dentro do próprio hoist para não virar `undefined` na primeira leitura.
const { getSearchParams, setNext, clearNext } = vi.hoisted(() => {
  let params = new URLSearchParams('')
  return {
    getSearchParams: () => params,
    setNext: (next: string) => {
      params = new URLSearchParams()
      params.set('next', next)
    },
    clearNext: () => {
      params = new URLSearchParams('')
    },
  }
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace, back: vi.fn() }),
  useSearchParams: () => getSearchParams(),
  usePathname: () => '/login',
}))

vi.mock('@/lib/odoo/client', () => {
  const falso = {
    getDatabases: vi.fn().mockResolvedValue(['qualificacao-dev']),
    authenticate: vi.fn().mockResolvedValue({ uid: 7, name: 'Técnico A', company_id: 1 }),
    reset: vi.fn(),
    read: vi.fn().mockResolvedValue([]),
    searchRead: vi.fn().mockResolvedValue([]),
    callKw: vi.fn().mockResolvedValue(null),
  }
  return { odooClient: falso, default: falso }
})

vi.mock('@/lib/odoo/schema', () => ({
  preloadSchemas: vi.fn().mockResolvedValue({ ok: 0, failed: 0 }),
}))

// Retorno SÍNCRONO: a página usa o valor direto em `setCompanyLogoUrl`.
vi.mock('@/lib/odoo/publicCompany', () => ({
  getCompanyLogoUrl: vi.fn(() => null),
}))

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

/** Vai do passo "Servidor" até o formulário de credenciais.
 *  O marco é o campo de senha aparecer — o botão "Entrar" nasce desabilitado
 *  até haver usuário e senha, então esperar por ele habilitado travaria. */
async function conecta() {
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'http://localhost:8084' },
  })
  fireEvent.click(screen.getByRole('button', { name: /Conectar/i }))
  // 3s, não o 1s padrão: a troca de passo é agendada com `setTimeout(400)` e
  // ainda espera a animação de saída do framer-motion.
  await waitFor(
    () => expect(document.querySelector('input[type="password"]')).not.toBeNull(),
    { timeout: 3000 },
  )
}

beforeEach(() => {
  push.mockClear()
  replace.mockClear()
  clearNext()
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ json: () => Promise.resolve({}), ok: true })),
  )
})

describe('entrar', () => {
  it('SUBSTITUI a entrada no histórico ao entrar, em vez de empilhar', async () => {
    // Com `push`, o botão voltar levava o técnico já autenticado de volta à
    // tela de credenciais. Mesmo defeito do fechamento de relatório e do
    // logout, achado na mesma varredura em 2026-09-05.
    wrap(<LoginPage />)
    await conecta()

    const campos = screen.getAllByRole('textbox')
    fireEvent.change(campos[campos.length - 1], { target: { value: 'tecnico.a@teste.local' } })
    fireEvent.change(document.querySelector('input[type="password"]')!, {
      target: { value: 'Teste@2026' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/tecnico/qualificacao'))
    expect(push).not.toHaveBeenCalled()
  })

  it('depois de autenticar vai para o destino guardado (?next=), sem deixar o login no histórico', async () => {
    // Deep link real: /tecnico/qualificacao/4/coleta/213. `replace`, não
    // `push` — o formulário de credenciais não pode sobreviver no histórico
    // (regra travada por navegacaoHistorico.test.ts).
    setNext('/tecnico/qualificacao/4/coleta/213')
    wrap(<LoginPage />)
    await conecta()

    const campos = screen.getAllByRole('textbox')
    fireEvent.change(campos[campos.length - 1], { target: { value: 'tecnico.a@teste.local' } })
    fireEvent.change(document.querySelector('input[type="password"]')!, {
      target: { value: 'Teste@2026' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith('/tecnico/qualificacao/4/coleta/213'),
    )
    expect(push).not.toHaveBeenCalled()
  })

  it('ignora ?next= externo e cai na lista padrão (open redirect)', async () => {
    setNext('https://evil.example')
    wrap(<LoginPage />)
    await conecta()

    const campos = screen.getAllByRole('textbox')
    fireEvent.change(campos[campos.length - 1], { target: { value: 'tecnico.a@teste.local' } })
    fireEvent.change(document.querySelector('input[type="password"]')!, {
      target: { value: 'Teste@2026' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/tecnico/qualificacao'))
    expect(push).not.toHaveBeenCalled()
  })
})

describe('middleware: expulsão guarda o destino original', () => {
  it('guarda o destino original ao expulsar para o login', () => {
    const req = new NextRequest('http://localhost:3010/tecnico/qualificacao/4/coleta/213')
    const res = middleware(req)
    const destino = new URL(res.headers.get('location')!)
    expect(destino.pathname).toBe('/login')
    expect(destino.searchParams.get('next')).toBe('/tecnico/qualificacao/4/coleta/213')
  })

  it('preserva a query string do destino original em next', () => {
    const req = new NextRequest('http://localhost:3010/tecnico/qualificacao?filtro=pendentes')
    const res = middleware(req)
    const destino = new URL(res.headers.get('location')!)
    expect(destino.searchParams.get('next')).toBe('/tecnico/qualificacao?filtro=pendentes')
  })

  it('não expulsa /login, mesmo sem sessão', () => {
    const req = new NextRequest('http://localhost:3010/login')
    const res = middleware(req)
    expect(res.headers.get('location')).toBeNull()
  })
})

describe('destinoSeguro: só caminho interno vale', () => {
  const PADRAO = '/tecnico/qualificacao'

  it('usa destino padrão quando não há next', () => {
    expect(destinoSeguro(null)).toBe(PADRAO)
  })

  it('aceita caminho interno', () => {
    expect(destinoSeguro('/tecnico/qualificacao/4/coleta/213')).toBe(
      '/tecnico/qualificacao/4/coleta/213',
    )
  })

  it('preserva query string e fragmento do destino — o recurso que a task existe para entregar', () => {
    // Se a correção do bypass quebrar isto, ela quebrou o próprio objetivo
    // da task: devolver o técnico ao link exato que ele abriu.
    expect(destinoSeguro('/tecnico/qualificacao/4/coleta/213?x=1#top')).toBe(
      '/tecnico/qualificacao/4/coleta/213?x=1#top',
    )
  })

  it('recusa destino externo (open redirect)', () => {
    // `?next=https://evil.example` faria o login mandar o técnico para
    // fora. Só caminho absoluto interno vale.
    const req = new NextRequest('http://localhost:3010/login?next=https://evil.example')
    expect(destinoSeguro(req.nextUrl.searchParams.get('next'))).toBe(PADRAO)
  })

  it('recusa protocolo relativo (barra dupla) — URL absoluta para o navegador', () => {
    expect(destinoSeguro('//evil.example')).toBe(PADRAO)
  })

  it('recusa barra tripla e variantes barra/contrabarra que colapsam para host externo', () => {
    expect(destinoSeguro('///evil.example')).toBe(PADRAO)
    expect(destinoSeguro('/\\evil.example')).toBe(PADRAO)
    expect(destinoSeguro('\\/evil.example')).toBe(PADRAO)
  })

  it('recusa esquema absoluto, com ou sem barra dupla (https:/evil, http://evil)', () => {
    expect(destinoSeguro('https:/evil')).toBe(PADRAO)
    expect(destinoSeguro('http://evil')).toBe(PADRAO)
  })

  it('recusa esquema não-http (javascript:, data:) — origin opaco não bate com o interno', () => {
    expect(destinoSeguro('javascript:alert(1)')).toBe(PADRAO)
    expect(destinoSeguro('data:text/html,x')).toBe(PADRAO)
  })

  // Achado da revisão adversarial (fix round 1): a primeira versão desta
  // função checava a string CRUA (`startsWith`, `includes('\\')`), mas quem
  // consome o retorno (`router.replace` do Next) resolve com `new URL`, cujo
  // parser remove todo tab/LF/CR da string ANTES de resolver — colapsando
  // `/\t/evil.example` em `//evil.example` por baixo do bloqueio de `\`.
  // Exploração real: autentica com `?next=%2F%09%2Fevil.example` e o técnico
  // sai do host. Cobre literal e percent-encoded — o encoded não deve
  // decodificar para o caractere de controle nesta camada (permanece
  // caminho interno literal, inofensivo).
  it('recusa tab/LF/CR (literal) que o parser da URL colapsa para host externo', () => {
    expect(destinoSeguro('/\t/evil.example')).toBe(PADRAO)
    expect(destinoSeguro('/\n/evil.example')).toBe(PADRAO)
    expect(destinoSeguro('/\r/evil.example')).toBe(PADRAO)
  })

  it('percent-encoded (%09/%0A/%0D) não decodifica para controle nesta camada — path interno literal', () => {
    expect(destinoSeguro('/%09/evil.example')).toBe('/%09/evil.example')
    expect(destinoSeguro('/%0A/evil.example')).toBe('/%0A/evil.example')
    expect(destinoSeguro('/%0D/evil.example')).toBe('/%0D/evil.example')
  })

  it('normaliza travessia de diretório (..) em vez de devolver literal', () => {
    // Bônus da correção por `new URL`: o parser resolve `..` antes de
    // comparar origin, então não sobra `..` no destino final.
    expect(destinoSeguro('/tecnico/../../evil')).toBe('/evil')
  })

  it('destino malformado (URL lança) cai no padrão', () => {
    expect(destinoSeguro('http://')).toBe(PADRAO)
  })

  // Achado da revisão final: as duas revisões anteriores atacaram só com
  // HOST ESTRANGEIRO (`evil.example` como autoridade), e a função passava.
  // Ninguém tentou nomear a PRÓPRIA SENTINELA — que é constante pública no
  // código-fonte, portanto legível pelo atacante. Nomeada, ela é consumida
  // como autoridade no primeiro parse (origin bate, checagem de entrada
  // passa) e o que sobra de caminho começa com `//`, que no SEGUNDO parse
  // (o `router.replace`, contra a `location.href` real) volta a ser
  // autoridade — agora a do atacante. Link real: `/login?next=//interno
  // .invalid//evil.example`.
  it('recusa next que nomeia a própria sentinela para vazar host no re-parse', () => {
    expect(destinoSeguro('//interno.invalid//evil.example')).toBe(PADRAO)
    expect(destinoSeguro('http://interno.invalid//evil.example/x')).toBe(PADRAO)
    expect(destinoSeguro('http://interno.invalid/\\evil.example')).toBe(PADRAO)
  })

  it('recusa outras formas de nomear a sentinela (barra tripla, contrabarra, tab, esquema, ponto inicial)', () => {
    expect(destinoSeguro('///interno.invalid//evil.example')).toBe(PADRAO)
    expect(destinoSeguro('//interno.invalid/\\evil.example')).toBe(PADRAO)
    expect(destinoSeguro('//interno.invalid/\t//evil.example')).toBe(PADRAO)
    expect(destinoSeguro('https://interno.invalid//evil.example')).toBe(PADRAO)
    expect(destinoSeguro('//interno.invalid//evil.example/x?y=1#z')).toBe(PADRAO)
    // TERCEIRA rodada da mesma família: `.` inicial faz o WHATWG tratar a
    // string como caminho relativo, o origin do primeiro parse bate, e o
    // pathname resolvido sai `//interno.invalid` — protocol-relative de novo.
    // Link de ataque, sem encoding nenhum: `/login?next=.//interno.invalid`.
    expect(destinoSeguro('.//interno.invalid')).toBe(PADRAO)
    expect(destinoSeguro('..//interno.invalid')).toBe(PADRAO)
    expect(destinoSeguro('/.//interno.invalid')).toBe(PADRAO)
    expect(destinoSeguro('.//interno.invalid/x?u=1#f')).toBe(PADRAO)
    expect(destinoSeguro('.//outra.invalid')).toBe(PADRAO)
  })

  /**
   * A asserção que faltou nas TRÊS rodadas, e é por isso que nenhuma delas
   * podia ter pego o buraco: todo teste acima compara a saída com
   * `DESTINO_PADRAO`. Isso só verifica que a função recusou o que ELA já
   * sabia recusar. O que o atacante explora é o que o CONSUMIDOR faz com a
   * saída — `router.replace` resolve contra a `location.href` REAL do app,
   * que não é nenhuma das sentinelas.
   *
   * Então a propriedade certa não é "devolveu o padrão", é: **resolvida
   * contra a origem real do app, a saída continua naquela origem** — para
   * QUALQUER entrada, aceita ou recusada.
   */
  describe('a saída nunca sai da origem real do app (a propriedade que importa)', () => {
    const BASES_REAIS = [
      'https://pwa.real.app/login',
      'http://localhost:3010/login',
      'https://qualif.empresa.com.br/a/b?q=1',
    ]

    const PAYLOADS = [
      // nomeiam a sentinela (rodadas 2 e 3)
      '//interno.invalid//evil.example',
      'http://interno.invalid//evil.example/x',
      'http://interno.invalid/\\evil.example',
      './/interno.invalid',
      '..//interno.invalid',
      '/.//interno.invalid',
      './/interno.invalid/x?u=1#f',
      './/outra.invalid',
      // ESQUEMA, não host (rodada 4): a origem de `blob:` deriva da URL
      // interna, então o gate de entrada passa; e `url.pathname` de um
      // `blob:` é a URL interna INTEIRA, então a saída seria
      // `http://interno.invalid/x` — URL absoluta cuja origem é
      // exatamente ORIGEM_INTERNA, logo a checagem contra a base interna
      // também passa. Na v2 isso teria virado alvo de redirect. É a única
      // entrada alcançável conhecida que vence o gate 0 E a base interna,
      // e é uma forma de escape que nenhum raciocínio sobre a família `//`
      // teria previsto.
      'blob:http://interno.invalid/x',
      'blob:http://interno.invalid',
      // host estrangeiro (rodada 1)
      'https://evil.example',
      '//evil.example',
      '///evil.example',
      '/\\evil.example',
      '/\t/evil.example',
      'javascript:alert(1)',
      // e as entradas LEGÍTIMAS, que também têm que satisfazer a propriedade
      '/tecnico/qualificacao/4/coleta/213?x=1#top',
      '//interno.invalid/ok',
      '/tecnico/../../evil',
    ]

    it.each(PAYLOADS)('next=%j não escapa da origem do app', (payload) => {
      const saida = destinoSeguro(payload)
      for (const base of BASES_REAIS) {
        expect(new URL(saida, base).origin, `saída ${JSON.stringify(saida)} sobre ${base}`).toBe(
          new URL(base).origin,
        )
      }
    })

    /**
     * As três checagens se sobrepõem, mas NÃO são intercambiáveis — e a
     * medição por porta desmente a glosa fácil de que "cada uma basta
     * sozinha" (que esta função chegou a carregar escrita, e é o mesmo
     * defeito das rodadas anteriores: invariante mais forte que a verdade):
     *
     *   só a invariante de FORMA .... 0 vazamentos  (esta sim basta sozinha)
     *   só a base TESTEMUNHA ........ 499           (`.//outra.invalid`)
     *   só a base INTERNA (= v2) .... 767           (`.//interno.invalid`, `blob:`)
     *   interna + testemunha ........ 0             (é o PAR que fecha)
     *
     * Como qualquer PAR já dá zero, nenhum teste de comportamento consegue
     * notar a remoção de UMA das três. Daí esta guarda de fonte, no espírito
     * do `temaTokens.test.ts`: ela é a única coisa que impede alguém de
     * "simplificar" a função para uma base só — que é exatamente o estado
     * explorável da versão 2.
     */
    it('as três checagens continuam no código (a mutação de uma só é invisível para os testes)', () => {
      const fonte = readFileSync(join(__dirname, '..', '..', '..', '..', 'lib/navegacao.ts'), 'utf8')
      // As DUAS bases são pinadas, não só a testemunha. Medido: só a interna
      // deixa vazar 767 payloads (é a v2), só a testemunha deixa vazar 499
      // (`.//outra.invalid` -> `//outra.invalid`). Quem basta sozinha é a
      // FORMA. Uma versão anterior desta guarda pinava só a testemunha,
      // apoiada na glosa errada de que "cada defesa basta sozinha" — alguém
      // podia apagar a base interna achando que a testemunha era a rede.
      expect(fonte, 'a base interna sumiu — reabre ?next=.//outra.invalid').toMatch(
        /new URL\(destino, ORIGEM_INTERNA\)\.origin !== ORIGEM_INTERNA/,
      )
      expect(fonte, 'a base testemunha sumiu — reabre ?next=.//interno.invalid').toMatch(
        /ORIGEM_TESTEMUNHA\).origin !== ORIGEM_TESTEMUNHA/,
      )
      // Casa o ESTATUTO executável, não a regex citada no comentário logo
      // acima dela — a primeira versão desta asserção passava verde com a
      // linha de código apagada, porque o JSDoc ainda mencionava o padrão.
      expect(fonte, 'a invariante de forma sumiu').toMatch(
        /if \(!\/\^\\\/\(\?!\\\/\)\/\.test\(destino\)\) return DESTINO_PADRAO/,
      )
      // Âncoras de parse, nunca destinos: TLD inexistente (RFC 2606) e hosts
      // distintos entre si. Trocar por `localhost` ou pela origem real do app
      // converteria isto num open redirect, com os testes verdes.
      //
      // O ESQUEMA é pinado junto, e não é detalhe: a invariante de forma
      // `/^\/(?!\/)/` ADMITE `/\` (o lookahead só exclui a segunda barra), e
      // `\` no índice 1 é o único caractere que ainda escalaria para
      // autoridade — `new URL('/\\evil.example', 'https://app.real/')` dá
      // `https://evil.example/`. O que torna isso inalcançável é que, para
      // esquema ESPECIAL (http/https/ws/ftp), o path state do WHATWG
      // normaliza contrabarra crua para `/`, então `url.pathname` nunca
      // contém `\` cru. Com um esquema NÃO-especial a normalização some e o
      // `/\` admitido pela regex vira alcançável — daí pinar `http://` e
      // `https://`, não só o `.invalid`.
      expect(fonte).toMatch(/ORIGEM_INTERNA = 'http:\/\/[a-z-]+\.invalid'/)
      expect(fonte).toMatch(/ORIGEM_TESTEMUNHA = 'https:\/\/[a-z-]+\.invalid'/)
    })

    it('a saída sempre tem exatamente uma barra inicial (invariante de forma)', () => {
      // Mesma propriedade, conferível de olho: é a defesa que continua
      // valendo se o comportamento do parser mudar debaixo dos pés.
      for (const payload of [...PAYLOADS, null, '', 'http://']) {
        expect(destinoSeguro(payload), `payload ${JSON.stringify(payload)}`).toMatch(/^\/(?!\/)/)
      }
    })
  })

  // A prova de que a correção NÃO é uma recusa geral: nomear a sentinela
  // sem o `//` extra continua sendo um caminho interno legítimo, e query e
  // fragmento chegam intactos. Sem estes dois casos, quem ler depois não
  // distingue a invariante de um `return PADRAO` cego.
  it('aceita a sentinela quando o resto é caminho interno de verdade, com query e fragmento', () => {
    expect(destinoSeguro('//interno.invalid/ok')).toBe('/ok')
    expect(destinoSeguro('http://interno.invalid/tecnico/qualificacao/4?x=1#top')).toBe(
      '/tecnico/qualificacao/4?x=1#top',
    )
  })
})
