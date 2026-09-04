import { MousePointerClick } from 'lucide-react'

/**
 * Lado direito de `/[osId]` quando nenhuma coleta está aberta. Só existe em
 * desktop — em celular o `SplitPane` esconde este lado e a tela é a lista.
 */
export function EmptyDetail() {
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center rounded-lg border border-dashed border-border p-6 text-center">
      <MousePointerClick className="h-6 w-6 text-muted-foreground" aria-hidden />
      <p className="mt-3 text-sm font-semibold text-foreground">Escolha uma coleta</p>
      <p className="mt-1 text-xs text-muted-foreground">
        O formulário abre aqui, ao lado da lista.
      </p>
    </div>
  )
}
