// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

// Achado 4 (revisão final do refactor "painel persistente", 2026-09-04):
// nada travava estruturalmente a premissa do refactor — que `SplitPane` e
// `ColetaList` são donas do `(painel)/layout.tsx`, não das páginas dentro do
// grupo. Sem este teste, uma edição futura poderia mover `SplitPane` de
// volta pra `(painel)/page.tsx` (ou pra `coleta/[itemId]/page.tsx`) e
// reintroduzir em silêncio o bug original: cada navegação remontando a
// coluna esquerda e a lista de coletas voltando pro topo.
const painelDir = path.resolve(__dirname, '..', '[osId]', '(painel)')

// Checa só `import ... from '...ComponentName'`, não qualquer menção (um
// comentário citando "SplitPane" de passagem — como há na página de coleta,
// explicando por que ela não precisa montar a lista — não deve derrubar o
// teste; só um import de verdade deve).
function importa(src: string, componentName: string): boolean {
  const re = new RegExp(`import\\s*{[^}]*\\b${componentName}\\b[^}]*}\\s*from`, 'm')
  return re.test(src)
}

describe('estrutura do grupo (painel)', () => {
  it('layout.tsx existe e é quem monta SplitPane/ColetaList', () => {
    const layoutPath = path.join(painelDir, 'layout.tsx')
    expect(fs.existsSync(layoutPath)).toBe(true)
    const layoutSrc = fs.readFileSync(layoutPath, 'utf-8')
    expect(importa(layoutSrc, 'SplitPane')).toBe(true)
    expect(importa(layoutSrc, 'ColetaList')).toBe(true)
  })

  it('page.tsx do grupo NÃO importa SplitPane nem ColetaList', () => {
    const pagePath = path.join(painelDir, 'page.tsx')
    expect(fs.existsSync(pagePath)).toBe(true)
    const pageSrc = fs.readFileSync(pagePath, 'utf-8')
    expect(importa(pageSrc, 'SplitPane')).toBe(false)
    expect(importa(pageSrc, 'ColetaList')).toBe(false)
  })

  it('page.tsx da coleta também NÃO importa SplitPane nem ColetaList', () => {
    const coletaPagePath = path.join(painelDir, 'coleta', '[itemId]', 'page.tsx')
    expect(fs.existsSync(coletaPagePath)).toBe(true)
    const coletaPageSrc = fs.readFileSync(coletaPagePath, 'utf-8')
    expect(importa(coletaPageSrc, 'SplitPane')).toBe(false)
    expect(importa(coletaPageSrc, 'ColetaList')).toBe(false)
  })
})
