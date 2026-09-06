import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

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

  it('os contadores do Histórico usam os tokens de estado', () => {
    const src = ler('app/tecnico/qualificacao/historico/page.tsx')
    expect(src).toMatch(/text-(?:info|ok|warn|foreground)\b/)
    expect(src).not.toMatch(/text-(?:cyan|violet|emerald)-\d/)
  })
})
