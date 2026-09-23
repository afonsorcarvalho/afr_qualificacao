// scripts/validacao-chat/run.live.ts
// Harness da validação empírica do modelo do chat de agendamento.
//
// NÃO faz parte da suíte (`npm test` só pega `*.test.ts`): bate na API real
// do OpenRouter, gasta cota e exige Odoo + PWA de pé. Rodar com
//
//   COOKIE_FILE=<arquivo com os cookies do navegador logado> \
//     npx vitest run --config vitest.live.config.ts
//
// O que é real aqui: o modelo, o prompt, as travas de `machine.ts`, o
// dispatch de `tools.ts` e as RPCs do Odoo. O único substituto é o
// TRANSPORTE do `odooClient` — axios com baseURL relativa não roda fora do
// navegador —, trocado por um fetch equivalente com o cookie de sessão.
// Transporte não é o que esta validação mede.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { it, expect, vi } from 'vitest'

const PWA_BASE = process.env.PWA_BASE ?? 'http://localhost:3010'
const COOKIE_FILE = process.env.COOKIE_FILE ?? ''

function cookieHeader(): string {
  if (!COOKIE_FILE) throw new Error('COOKIE_FILE não definido')
  return readFileSync(COOKIE_FILE, 'utf8')
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .join('; ')
}

// Precisa vir antes dos imports de `lib/` (vi.mock é içado pro topo).
vi.mock('@/lib/odoo/client', () => {
  const base = process.env.PWA_BASE ?? 'http://localhost:3010'
  const cookies = readFileSync(process.env.COOKIE_FILE as string, 'utf8')
    .split('\n').map((l) => l.trim()).filter(Boolean).join('; ')

  async function rpc(payload: unknown): Promise<unknown> {
    const res = await fetch(`${base}/api/odoo/web/dataset/call_kw`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Cookie: cookies },
      body: JSON.stringify(payload),
    })
    const json = (await res.json()) as { result?: unknown; error?: { data?: { message?: string } } }
    if (json.error) {
      throw new Error(json.error.data?.message ?? 'erro Odoo')
    }
    return json.result
  }

  return {
    default: {
      callKw: (model: string, method: string, args: unknown[], kwargs: Record<string, unknown> = {}) =>
        rpc({
          jsonrpc: '2.0', method: 'call', id: Date.now(),
          params: { model, method, args, kwargs: { context: { lang: 'pt_BR' }, ...kwargs } },
        }),
      searchCount: (model: string, domain: unknown[]) =>
        rpc({
          jsonrpc: '2.0', method: 'call', id: Date.now(),
          params: { model, method: 'search_count', args: [domain], kwargs: {} },
        }),
    },
  }
})

import { runTurn, type TracoVolta } from '@/lib/chat/machine'
import { runTool } from '@/lib/chat/tools'
import { buildSystemPrompt, resumirVisitas } from '@/lib/chat/prompt'
import { fetchAgenda, listTecnicoOptions } from '@/lib/odoo/agenda'
import type { LlmMessage, LlmTurn } from '@/lib/llm/client'
import { FIXTURES, SERVER_TODAY, JANELA_NA_TELA, type Fixture } from './fixtures'

async function callModel(messages: LlmMessage[]): Promise<LlmTurn> {
  const res = await fetch(`${PWA_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Cookie: cookieHeader() },
    body: JSON.stringify({ messages }),
  })
  const json = await res.json()
  if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`)
  return json as LlmTurn
}

interface Placar {
  fixture: Fixture
  kind: string
  texto: string
  tracos: TracoVolta[]
  wallMs: number
  modelos: string[]
  /** Nome da ferramenta da primeira chamada, ou null se o turno foi só texto. */
  primeiraFerramenta: string | null
  /** Todas as datas ISO que apareceram em argumentos de ferramenta. */
  datasVistas: string[]
  /** Resultados de trava (`machine.ts` barrando) — id inventado ou data não-ISO. */
  travas: string[]
  chamadas: { nome: string; argumentos: string }[]
}

function datasDosArgumentos(args: string): string[] {
  return args.match(/\d{4}-\d{2}-\d{2}/g) ?? []
}

const RE_TRAVA_ID = /nunca (?:apareceu|foi devolvido)|não apareceu|Use data absoluta|não veio de nenhum resultado/i

async function rodarFixture(f: Fixture, system: string): Promise<Placar> {
  const messages: LlmMessage[] = [
    { role: 'system', content: system },
    { role: 'user', content: f.pedido },
  ]
  const idsVistos = new Set<number>()
  const t0 = Date.now()
  const r = await runTurn(messages, { callModel, runTool, idsVistos })
  const wallMs = Date.now() - t0

  const tracos = r.tracos ?? []
  const chamadas = tracos.flatMap((t) =>
    t.chamadas.filter((c) => c.nome !== 'texto').map((c) => ({ nome: c.nome, argumentos: c.argumentos ?? '' })),
  )
  const travas = tracos.flatMap((t) =>
    t.chamadas.filter((c) => c.resultado && RE_TRAVA_ID.test(c.resultado)).map((c) => `${c.nome}: ${c.resultado}`),
  )

  return {
    fixture: f,
    kind: r.kind,
    texto: r.kind === 'text' ? r.text : r.kind === 'proposal' ? r.proposta.resumo : (r as { erro: string }).erro,
    tracos,
    wallMs,
    modelos: Array.from(new Set(tracos.map((t) => t.modelo).filter(Boolean) as string[])),
    primeiraFerramenta: chamadas[0]?.nome ?? null,
    datasVistas: Array.from(new Set(chamadas.flatMap((c) => datasDosArgumentos(c.argumentos)))),
    travas,
    chamadas,
  }
}

function pontuar(p: Placar): { criterio: string; ok: boolean | null; nota: string }[] {
  const f = p.fixture
  const linhas: { criterio: string; ok: boolean | null; nota: string }[] = []

  linhas.push({
    criterio: 'ferramenta',
    ok: p.primeiraFerramenta === f.ferramentaEsperada,
    nota: `esperada ${f.ferramentaEsperada ?? '(nenhuma)'}, veio ${p.primeiraFerramenta ?? '(nenhuma)'}`,
  })

  if (f.datasEsperadas?.length) {
    const faltando = f.datasEsperadas.filter((d) => !p.datasVistas.includes(d))
    const deduzidas = (f.datasDeDeducao ?? []).filter((d) => p.datasVistas.includes(d))
    linhas.push({
      criterio: 'data derivada do server_today',
      ok: faltando.length === 0 && deduzidas.length === 0,
      nota: `vistas [${p.datasVistas.join(', ')}]${faltando.length ? ` | faltando [${faltando.join(', ')}]` : ''}${deduzidas.length ? ` | dedução pelo relógio real [${deduzidas.join(', ')}]` : ''}`,
    })
  }

  linhas.push({
    criterio: 'id alucinado barrado',
    ok: p.travas.length === 0 ? null : true,
    nota: p.travas.length ? `${p.travas.length} trava(s): ${p.travas.join(' / ')}` : 'nenhuma trava disparou',
  })

  if (f.esperaEncadeamento) {
    linhas.push({
      criterio: 'segunda chamada consome a primeira',
      ok: p.chamadas.length >= 2,
      nota: `${p.chamadas.length} chamada(s): ${p.chamadas.map((c) => c.nome).join(' → ')}`,
    })
  }
  if (f.esperaProposta) {
    linhas.push({ criterio: 'terminou em proposta de escrita', ok: p.kind === 'proposal', nota: `kind=${p.kind}` })
  }
  if (f.esperaPergunta) {
    linhas.push({
      criterio: 'perguntou em vez de escrever',
      ok: p.kind === 'text' && /\?/.test(p.texto),
      nota: `kind=${p.kind}`,
    })
  }
  return linhas
}

function relatorio(placares: Placar[]): string {
  const agora = new Date().toISOString()
  const l: string[] = []
  l.push('# Validação empírica do modelo — chat de agendamento')
  l.push('')
  l.push(`Gerado por \`scripts/validacao-chat/run.live.ts\` em ${agora}.`)
  l.push('')
  l.push(`\`server_today\` **injetado**: \`${SERVER_TODAY}\` (segunda-feira, deliberadamente diferente do hoje real da máquina — é assim que "derivou do servidor" se distingue de "deduziu do relógio").`)
  l.push('')
  l.push(`Janela na tela: ${JANELA_NA_TELA.from} a ${JANELA_NA_TELA.to}.`)
  l.push('')
  l.push('> **Leia junto com `TODO.md`.** Este arquivo é evidência crua, gerada: cada')
  l.push('> linha é o que aconteceu naquela execução, não a conclusão. Toda fixture de')
  l.push('> data é pontuada contra o `SERVER_TODAY` que ELA espera: as da lista padrão')
  l.push('> contra `2026-09-14`, e a `F04b` contra `2026-09-21`. Rodar uma delas na')
  l.push('> data da outra reprova por construção — é assim de propósito, para que o')
  l.push('> placar nunca dê ✅ a uma execução que ninguém conferiu. A leitura dos')
  l.push('> resultados mora no `TODO.md`.')
  l.push('')
  l.push('## Placar')
  l.push('')
  l.push('| Fixture | Grupo | Ferramenta | Data | Encadeamento | Resultado | Wall-clock | Modelo |')
  l.push('|---|---|---|---|---|---|---|---|')
  for (const p of placares) {
    const pts = pontuar(p)
    const nota = (c: string) => {
      const x = pts.find((y) => y.criterio.startsWith(c))
      if (!x) return '—'
      return x.ok === null ? '·' : x.ok ? '✅' : '❌'
    }
    l.push(
      `| ${p.fixture.id} | ${p.fixture.grupo} | ${nota('ferramenta')} | ${nota('data')} | ${nota('segunda')} | ${p.kind} | ${(p.wallMs / 1000).toFixed(1)}s | ${p.modelos.join(', ') || '—'} |`,
    )
  }
  l.push('')
  l.push('## Detalhe por fixture')
  for (const p of placares) {
    l.push('')
    l.push(`### ${p.fixture.id} — "${p.fixture.pedido}"`)
    l.push('')
    l.push(`*${p.fixture.proposito}*`)
    l.push('')
    l.push(`- grupo: \`${p.fixture.grupo}\` · desfecho: \`${p.kind}\` · ${(p.wallMs / 1000).toFixed(1)}s · ${p.tracos.length} volta(s) · modelo: ${p.modelos.join(', ') || '—'}`)
    for (const c of pontuar(p)) {
      l.push(`- ${c.ok === null ? '·' : c.ok ? '✅' : '❌'} **${c.criterio}** — ${c.nota}`)
    }
    if (p.chamadas.length) {
      l.push('')
      l.push('Argumentos crus, exatamente como o modelo mandou:')
      l.push('')
      l.push('```')
      for (const c of p.chamadas) l.push(`${c.nome} ${c.argumentos}`)
      l.push('```')
    }
    const resumoTexto = p.texto.replace(/\s+/g, ' ').slice(0, 400)
    if (resumoTexto) {
      l.push('')
      l.push(`> ${resumoTexto}`)
    }
  }
  const usoTotal = placares.flatMap((p) => p.tracos).reduce(
    (acc, t) => {
      acc.prompt += t.usage?.prompt_tokens ?? 0
      acc.completion += t.usage?.completion_tokens ?? 0
      acc.custo += t.usage?.cost ?? 0
      return acc
    },
    { prompt: 0, completion: 0, custo: 0 },
  )
  l.push('')
  l.push('## Custo e latência do run')
  l.push('')
  l.push(`- ${placares.length} fixtures, ${placares.flatMap((p) => p.tracos).length} chamadas ao modelo`)
  l.push(`- wall-clock: mediana ${(mediana(placares.map((p) => p.wallMs)) / 1000).toFixed(1)}s, pior ${(Math.max(...placares.map((p) => p.wallMs)) / 1000).toFixed(1)}s`)
  l.push(`- tokens: ${usoTotal.prompt} prompt + ${usoTotal.completion} completion`)
  l.push(`- custo reportado pelo OpenRouter: US$ ${usoTotal.custo.toFixed(4)}`)
  l.push('')
  return l.join('\n')
}

function mediana(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

it('validação empírica do chat de agendamento', async () => {
  // Aquecer a rota: em dev a primeira requisição compila, e sem isto a
  // primeira fixture mediria o compilador, não o modelo.
  await fetch(`${PWA_BASE}/api/chat/status`, { headers: { Cookie: cookieHeader() } }).catch(() => {})

  const [tecnicos, agenda] = await Promise.all([
    listTecnicoOptions(),
    fetchAgenda(JANELA_NA_TELA.from, JANELA_NA_TELA.to, false),
  ])
  expect(agenda.visitas.length, 'sem dado semeado na janela, "encadeamento" seria intestável').toBeGreaterThan(0)

  const system = buildSystemPrompt({
    serverToday: SERVER_TODAY,
    tecnicos: tecnicos.map((t) => ({ id: t.id, name: t.name })),
    visitas: resumirVisitas(agenda.visitas),
  })

  // `FIXTURE_FILTER=F04,F10` roda só as fixtures citadas — usado pra
  // reexecutar um grupo depois de mexer no prompt sem pagar as dez de novo.
  const filtro = (process.env.FIXTURE_FILTER ?? '').split(',').map((x) => x.trim()).filter(Boolean)
  const aRodar = filtro.length ? FIXTURES.filter((f) => filtro.includes(f.id)) : FIXTURES

  const placares: Placar[] = []
  for (const f of aRodar) {
    // Sequencial de propósito: a cota é compartilhada e o wall-clock por
    // mensagem é um dos critérios — paralelizar falsearia os dois.
    const p = await rodarFixture(f, system)
    placares.push(p)
    // eslint-disable-next-line no-console
    console.log(`${f.id} ${f.grupo} → ${p.kind} | ${p.primeiraFerramenta ?? 'texto'} | ${(p.wallMs / 1000).toFixed(1)}s | datas [${p.datasVistas.join(', ')}]`)
  }

  // `RELATORIO` aceita caminho absoluto — é assim que uma rodada exploratória
  // (reproduzir um defeito, repetir uma fixture) escreve fora do repo em vez
  // de deixar um `docs/_tmp.md` pra alguém commitar sem querer.
  const nome = process.env.RELATORIO ?? 'VALIDACAO-CHAT'
  const destino = nome.startsWith('/') ? nome : resolve(__dirname, `../../docs/${nome}.md`)
  mkdirSync(dirname(destino), { recursive: true })
  writeFileSync(destino, relatorio(placares), 'utf8')
  // eslint-disable-next-line no-console
  console.log(`\nRelatório: ${destino}`)
}, 900_000)
