// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { EquipmentHeader } from '../_components/EquipmentHeader'

/**
 * Trava a distinção de papel entre título e metadado.
 *
 * Fix round 1 da Task 3: a primeira migração apontou `text` (título do
 * equipamento) e `muted` (contador "N de M", apelido, marca/modelo/serial)
 * pro mesmo token (`text-info`/`text-ok`), fundindo os dois pesos visuais.
 * Nem a catraca nem o pixel-diff pegam isso — nenhuma classe proibida
 * sobra, a diferença é de papel, não de piso. Este teste existe pra não
 * deixar a próxima migração colapsar os dois de novo.
 */
describe('EquipmentHeader: título e metadado não podem ter a mesma cor', () => {
  function classesDoTitulo(tone: 'cyan' | 'emerald') {
    const { container } = render(
      <EquipmentHeader
        label="Autoclave a Gás"
        feitas={3}
        total={8}
        tone={tone}
        aberto={false}
        onToggle={() => {}}
        controlsId="grupo-1"
      />,
    )
    const titulo = container.querySelector('strong')!
    const contador = container.querySelector('span.tabular-nums')!
    return { titulo: titulo.className, contador: contador.className }
  }

  it('tom cyan (pendentes): título usa --info, contador usa --muted-foreground', () => {
    const { titulo, contador } = classesDoTitulo('cyan')
    expect(titulo).toContain('text-info')
    expect(contador).toContain('text-muted-foreground')
    expect(contador).not.toEqual(titulo)
  })

  it('tom emerald (feitas): título usa --ok, contador usa --muted-foreground', () => {
    const { titulo, contador } = classesDoTitulo('emerald')
    expect(titulo).toContain('text-ok')
    expect(contador).toContain('text-muted-foreground')
    expect(contador).not.toEqual(titulo)
  })
})
