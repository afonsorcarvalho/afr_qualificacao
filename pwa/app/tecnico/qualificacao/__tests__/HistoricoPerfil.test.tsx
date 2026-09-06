// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { SummaryCell } from '@/app/tecnico/qualificacao/_components/SummaryCell'

const RAIZ = join(__dirname, '..', '..', '..', '..')
const ler = (p: string) => readFileSync(join(RAIZ, p), 'utf8')

describe('Histórico e Perfil: sem enfeite, com token', () => {
  const telas = [
    'app/tecnico/qualificacao/historico/page.tsx',
    'app/tecnico/qualificacao/perfil/page.tsx',
  ]

  it.each(telas)('%s não usa gradiente decorativo (DESIGN.md §6 Don\'t)', (p) => {
    expect(ler(p)).not.toMatch(/bg-gradient-to-/)
  })

  it.each(telas)('%s não usa sombra colorida', (p) => {
    // `shadow-cyan-500/10` é o mesmo vocabulário do glow aposentado.
    expect(ler(p)).not.toMatch(/shadow-(?:cyan|violet|emerald|blue)-/)
  })
})

describe('SummaryCell: número é protagonista, rótulo é secundário', () => {
  // Round 2 da Task 4 corrigiu um colapso de hierarquia (rótulo ganhou o
  // mesmo token colorido do ícone, empatando peso visual com o número) que
  // o teste baseado em regex anterior não pegava — ele varria o arquivo
  // inteiro e passava só com o `text-foreground` do `<h1>`, indiferente ao
  // que `SummaryCell` de fato renderizava. Este teste renderiza o
  // componente e trava a hierarquia real, no formato de
  // `StatusBadge.test.tsx` (Task 3).
  it('o valor usa text-foreground; o rótulo usa text-muted-foreground — nunca a mesma cor', () => {
    const { container } = render(
      <SummaryCell icon={<svg />} value={3} label="coletas" tone="info" />,
    )
    // Ordem fixa no JSX de `SummaryCell`: ícone, depois o valor, depois o
    // rótulo — mais robusto que casar por classe (que tem colchete literal
    // no arbitrary value `text-[10px]`, chato de escapar em CSS selector).
    const paragrafos = container.querySelectorAll('p')
    const valor = paragrafos[0]
    const rotulo = paragrafos[1]
    expect(valor.className).toContain('text-foreground')
    expect(rotulo.className).toContain('text-muted-foreground')
    expect(rotulo.className).not.toContain('text-foreground')
    expect(valor.className).not.toBe(rotulo.className)
  })

  it('o ícone acompanha o token do escopo (info/ok), nunca shade crua', () => {
    const info = render(<SummaryCell icon={<svg />} value={0} label="OSs" tone="info" />)
    const iconeInfo = info.container.firstElementChild!.firstElementChild!
    expect(iconeInfo.className).toContain('text-info')

    const ok = render(<SummaryCell icon={<svg />} value={0} label="rel. fechados" tone="ok" />)
    const iconeOk = ok.container.firstElementChild!.firstElementChild!
    expect(iconeOk.className).toContain('text-ok')
    expect(iconeOk.className).not.toMatch(/emerald-\d/)
  })
})
