'use client'
import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

/**
 * O que o navegador considera focável dentro do diálogo. Lista deliberadamente
 * curta: é a mesma que o trap usa para achar o primeiro e o último parada do
 * Tab, e conteúdo focável exótico (`contenteditable`, `<audio controls>`) não
 * existe em nenhuma das duas folhas do app.
 */
const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Folha vinda de baixo. O projeto não tem Modal genérico (só o
 * `PdfViewerModal`, que é específico); esta é a primeira.
 *
 * FOCO (review final, achado 1). O `aria-modal="true"` abaixo é uma PROMESSA
 * ao leitor de tela: "o resto da página não existe enquanto isto está
 * aberto". Sem gestão de foco a promessa era falsa nos dois sentidos — o
 * leitor escondia o fundo enquanto o foco continuava lá (o usuário não ouvia
 * nem o diálogo nem a célula que o disparou), e o Tab passeava pelas ~40
 * células da grade, badges, setas e o FAB, todos ativáveis por teclado por
 * baixo do overlay, que só bloqueia o PONTEIRO. Então, enquanto aberto:
 *
 *   1. o foco entra no container (`tabIndex={-1}` + `role="dialog"` +
 *      `aria-label`) — é o container, e não o botão de confirmação, para que
 *      o leitor anuncie o TÍTULO antes da primeira ação;
 *   2. o Tab circula só dentro do diálogo (e puxa de volta o foco que
 *      escapou por outro caminho);
 *   3. ao fechar, o foco volta ao elemento que abriu a folha.
 *
 * Vale para as DUAS folhas (`VisitaSheet` e `ConfirmarMudancaData`): o
 * componente é compartilhado e nada aqui é específico de uma delas.
 */
export function BottomSheet({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  const dialogoRef = useRef<HTMLDivElement>(null)

  // Escape (comportamento antigo, intocado) + trap do Tab. Continua com
  // `onClose` nas dependências — reanexar um listener a cada render é
  // inofensivo. O ramo do Escape vem ANTES de qualquer guarda de `ref`: no
  // render em que a ref ainda não apontou, fechar tem de continuar valendo.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const container = dialogoRef.current
      if (!container) return
      const focaveis = Array.from(container.querySelectorAll<HTMLElement>(FOCAVEIS))
      if (focaveis.length === 0) {
        // Diálogo sem nenhum controle: o foco fica no próprio container em
        // vez de sair andando pelo fundo.
        e.preventDefault()
        container.focus()
        return
      }
      const primeiro = focaveis[0]
      const ultimo = focaveis[focaveis.length - 1]
      const ativo = document.activeElement
      // "Dentro" exclui o próprio container: com o foco nele, o Tab tem de
      // ENTRAR na lista (e o Shift+Tab, ir para o fim dela), não ser tratado
      // como "já está no meio do ciclo".
      const dentro = ativo instanceof HTMLElement && ativo !== container && container.contains(ativo)
      if (e.shiftKey) {
        if (!dentro || ativo === primeiro) {
          e.preventDefault()
          ultimo.focus()
        }
      } else if (!dentro || ativo === ultimo) {
        e.preventDefault()
        primeiro.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Efeito SEPARADO, e com `[open]` sozinho nas dependências de propósito:
  // `onClose` costuma chegar como arrow inline (é o caso da `page.tsx` da
  // agenda), ou seja, referência nova a cada render. Num efeito só, a
  // limpeza rodaria a cada re-render — devolvendo o foco e logo em seguida
  // recapturando `document.activeElement`, que a essa altura é o PRÓPRIO
  // container. Fechar depois disso restauraria o foco para um nó que está
  // saindo da árvore: exatamente o defeito que este efeito corrige, só que
  // intermitente.
  useEffect(() => {
    if (!open) return
    const anterior = document.activeElement
    dialogoRef.current?.focus()
    return () => {
      // `isConnected`: o disparador pode ter saído da árvore enquanto a
      // folha estava aberta (o `VisitaCard` some do payload depois de
      // gravar/apagar). Focar um nó desconectado não devolve nada a
      // ninguém — o navegador cai no `<body>` de qualquer forma.
      if (anterior instanceof HTMLElement && anterior.isConnected) anterior.focus()
    }
  }, [open])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div
        className="absolute inset-0 bg-black/60"
        aria-hidden
        onClick={onClose}
      />
      <div
        ref={dialogoRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        // Focável só por programa: entra no ciclo do Tab pelo trap acima, não
        // pela ordem natural do documento. `outline-none` porque o anel de
        // foco em volta da folha INTEIRA não informa nada — o que o usuário
        // precisa ver é o anel do primeiro controle, um Tab depois.
        tabIndex={-1}
        className="relative w-full max-w-[560px] rounded-t-2xl border-t border-border bg-card p-4 shadow-[0_-8px_24px_rgba(0,0,0,0.45)] outline-none"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">{title}</h2>
          <button
            type="button"
            aria-label="Fechar"
            onClick={onClose}
            className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          >
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
