// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BottomSheet } from '../BottomSheet'

/**
 * Foco do `BottomSheet` (review final, achado 1).
 *
 * O componente declara `aria-modal="true"` — a promessa é que o resto da
 * página não existe enquanto a folha está aberta. Sem gestão de foco essa
 * promessa é falsa nos dois sentidos: o leitor de tela ESCONDE o fundo
 * enquanto o foco continua lá (o usuário não ouve nem o diálogo nem a célula
 * que o disparou), e o Tab passeia pelas ~40 células, badges e o FAB, todos
 * ativáveis por teclado por baixo do overlay — que só bloqueia o ponteiro.
 *
 * Os testes abaixo não usam `userEvent.tab()` de propósito: ele depende da
 * emulação de ordem de tabulação da própria biblioteca e de ela honrar o
 * `preventDefault`. O que interessa aqui é o handler, então o Tab é
 * disparado direto (`fireEvent.keyDown(document, …)`), que é o mesmo evento
 * que o navegador entrega.
 */
function Folha({ open, onClose = vi.fn() }: { open: boolean; onClose?: () => void }) {
  return (
    <BottomSheet open={open} title="Folha de teste" onClose={onClose}>
      <button type="button">Cancelar</button>
      <button type="button">Confirmar</button>
    </BottomSheet>
  )
}

describe('BottomSheet: foco', () => {
  it('ao abrir, o foco vai para o diálogo — não fica no fundo escondido pelo aria-modal', () => {
    const { rerender } = render(<Folha open={false} />)
    rerender(<Folha open />)

    expect(document.activeElement).toBe(screen.getByRole('dialog', { name: 'Folha de teste' }))
  })

  it('ao fechar, devolve o foco ao elemento que abriu a folha', () => {
    function Cena({ open }: { open: boolean }) {
      return (
        <>
          <button type="button">Disparador</button>
          <Folha open={open} />
        </>
      )
    }
    const { rerender } = render(<Cena open={false} />)
    const disparador = screen.getByRole('button', { name: 'Disparador' })
    disparador.focus()

    rerender(<Cena open />)
    expect(document.activeElement).not.toBe(disparador)

    rerender(<Cena open={false} />)
    expect(document.activeElement).toBe(disparador)
  })

  it('o disparador que sumiu da tela não leva o foco junto — sem exceção ao fechar', () => {
    function Cena({ open, comDisparador }: { open: boolean; comDisparador: boolean }) {
      return (
        <>
          {comDisparador && <button type="button">Disparador</button>}
          <Folha open={open} />
        </>
      )
    }
    const { rerender } = render(<Cena open={false} comDisparador />)
    screen.getByRole('button', { name: 'Disparador' }).focus()

    rerender(<Cena open comDisparador />)
    // Gravou e o card sumiu do payload enquanto a folha estava aberta.
    rerender(<Cena open comDisparador={false} />)
    expect(() => rerender(<Cena open={false} comDisparador={false} />)).not.toThrow()
  })

  it('Tab no último foco do diálogo volta para o primeiro (não escapa para o fundo)', () => {
    render(<Folha open />)
    const fechar = screen.getByRole('button', { name: 'Fechar' })
    const confirmar = screen.getByRole('button', { name: 'Confirmar' })

    confirmar.focus()
    fireEvent.keyDown(document, { key: 'Tab' })

    expect(document.activeElement).toBe(fechar)
  })

  it('Shift+Tab no primeiro foco do diálogo volta para o último', () => {
    render(<Folha open />)
    const fechar = screen.getByRole('button', { name: 'Fechar' })
    const confirmar = screen.getByRole('button', { name: 'Confirmar' })

    fechar.focus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })

    expect(document.activeElement).toBe(confirmar)
  })

  it('Tab com o foco no container leva ao primeiro controle, e do fundo puxa de volta para dentro', () => {
    render(
      <>
        <button type="button">Fora</button>
        <Folha open />
      </>,
    )
    const dialogo = screen.getByRole('dialog', { name: 'Folha de teste' })
    const fechar = screen.getByRole('button', { name: 'Fechar' })

    expect(document.activeElement).toBe(dialogo)
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(fechar)

    // Foco que escapou por outro caminho (ex.: chrome do navegador) é
    // trazido de volta no próximo Tab, em vez de seguir pelo fundo.
    screen.getByRole('button', { name: 'Fora' }).focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(fechar)
  })

  it('Escape continua fechando', () => {
    const onClose = vi.fn()
    render(<Folha open onClose={onClose} />)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Escape fecha a folha e NÃO acorda o atalho global do layout por baixo dela', () => {
    // Achado da validação em navegador: o layout de `/tecnico/qualificacao`
    // tem um atalho global "Escape = voltar" (`router.back()`) numa escuta de
    // `window`. Com a folha aberta, o mesmo Escape fazia as duas coisas — a
    // folha fechava E o app navegava de página. É a mesma classe do achado 1
    // (controle do FUNDO ativável por teclado enquanto o `aria-modal` diz que
    // o fundo não existe), só que pelo atalho em vez do Tab. Como a escuta da
    // folha é em `document` e o `window` é o próximo do caminho de
    // borbulhamento, parar a propagação aqui resolve sem tocar em quem
    // fecha o quê.
    const onClose = vi.fn()
    const atalhoDoFundo = vi.fn()
    window.addEventListener('keydown', atalhoDoFundo)
    const { rerender } = render(<Folha open onClose={onClose} />)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(atalhoDoFundo).not.toHaveBeenCalled()

    // Fechada, o atalho do layout volta a valer — nada foi desligado de vez.
    rerender(<Folha open={false} onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(atalhoDoFundo).toHaveBeenCalledTimes(1)

    window.removeEventListener('keydown', atalhoDoFundo)
  })
})
