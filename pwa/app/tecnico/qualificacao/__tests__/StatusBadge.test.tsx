// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { StatusBadge, StatusTone } from '@/components/ui/StatusBadge'
import { hsl2rgb, contraste, tokenDe } from '@/tests/contraste'

/**
 * O que este arquivo trava, e por que mudou.
 *
 * A versão anterior afirmava que "o render do StatusBadge não pode mudar em
 * tema nenhum", e provava isso conferindo que a classe contém `text-ok` e
 * não contém `emerald-\d`. Duas coisas erradas nisso:
 *
 * 1. A PREMISSA caducou. Ela valia porque `text-emerald-700` batia com
 *    `--ok` do tema claro — verdade quando escrita, falsa depois que a
 *    Task 13 escureceu `--ok` para o equivalente a emerald-800. O render
 *    mudou nos DOIS temas (claro: emerald-700 -> 800; escuro: a superfície
 *    saiu de emerald a 10% para `--ok-surface`, calibrada a 15% — texto
 *    sobre fundo caiu de 8,72:1 para 7,99:1). A mudança é benigna, mas o
 *    teste que a proibia continuou verde: ele nunca a mediu.
 * 2. A ASSERÇÃO era vazia. `expect(cls).toContain('text-ok')` passa com o
 *    token apontando para qualquer cor — inclusive para cinza sobre cinza.
 *    Presença de string não é contraste.
 *
 * Então o que se trava aqui é a GRANDEZA, não a identidade: para cada tom,
 * os tokens que o render de fato emitiu (lidos da className, não escritos à
 * mão) são resolvidos contra `app/globals.css` nos dois temas e medidos.
 * Um token pode ser recalibrado à vontade; o que não pode é o chip ficar
 * ilegível — e é isso que quebra o teste.
 */

const css = readFileSync(join(__dirname, '..', '..', '..', '..', 'app/globals.css'), 'utf8')

/** Resolve um token de `globals.css` para RGB, falhando alto se sumir. */
function rgbDoToken(tema: string, papel: string): number[] {
  const triple = tokenDe(css, tema, papel)
  expect(triple, `--${papel} ausente em ${tema} (globals.css)`).not.toBeNull()
  // Tripla HSL crua é o que faz `bg-ok/15` gerar CSS; hex ou `hsl()` gera zero.
  expect(triple!).toMatch(/^\d{1,3} \d{1,3}% \d{1,3}%$/)
  return hsl2rgb(triple!)
}

/**
 * Extrai do render os tokens de tinta e de fundo que o componente escolheu.
 *
 * "É token" não é uma lista escrita aqui — é resolver em `globals.css`. Isso
 * separa `text-ok` de `text-xs` sem manter um catálogo paralelo que
 * envelhece (o catálogo desatualizado foi o defeito da versão anterior deste
 * arquivo) e faz o teste falhar alto, em vez de em silêncio, se algum dia o
 * chip trocar o token por uma shade crua: aí nenhuma classe resolve e a
 * asserção de "achou token" quebra.
 */
function tokensDoChip(tone: StatusTone): { texto: string; fundo: string } {
  const { container } = render(<StatusBadge tone={tone}>Rótulo</StatusBadge>)
  const cls = container.firstElementChild!.className
  const achaToken = (prefixo: string) =>
    cls
      .split(/\s+/)
      .filter((c) => c.startsWith(`${prefixo}-`))
      .map((c) => c.slice(prefixo.length + 1))
      .find((papel) => tokenDe(css, ':root', papel) !== null)
  const texto = achaToken('text')
  const fundo = achaToken('bg')
  expect(texto, `nenhum token de texto no render do tom "${tone}": ${cls}`).toBeTruthy()
  expect(fundo, `nenhum token de fundo no render do tom "${tone}": ${cls}`).toBeTruthy()
  return { texto: texto!, fundo: fundo! }
}

describe('StatusBadge: contraste real do chip, nos dois temas', () => {
  const TONS: StatusTone[] = ['done', 'progress', 'waiting', 'error', 'neutral']

  it.each(TONS)('tom "%s" passa 4.5:1 no claro e no escuro', (tone) => {
    const { texto, fundo } = tokensDoChip(tone)
    for (const tema of [':root', ':root.dark']) {
      const razao = contraste(rgbDoToken(tema, texto), rgbDoToken(tema, fundo))
      expect(
        razao,
        `chip "${tone}" em ${tema}: text-${texto} sobre bg-${fundo} = ${razao.toFixed(2)}:1`,
      ).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('a cor vem de token semântico, não de shade crua nem de par dark:', () => {
    // Continua valendo como regra de VOCABULÁRIO (a Regra do Token do
    // DESIGN.md) — só não é mais confundida com uma garantia de contraste.
    const { container } = render(<StatusBadge tone="done">Coletada</StatusBadge>)
    const cls = container.firstElementChild!.className
    expect(cls).not.toMatch(/(?:emerald|amber|red|rose|cyan|sky|blue|green|yellow)-\d/)
    expect(cls).not.toContain('dark:')
  })

  it('a informação sobrevive sem a cor (Regra do Par, DESIGN.md §2)', () => {
    const { container } = render(<StatusBadge tone="waiting">Pendente</StatusBadge>)
    expect(container.textContent).toBe('Pendente')
  })
})
