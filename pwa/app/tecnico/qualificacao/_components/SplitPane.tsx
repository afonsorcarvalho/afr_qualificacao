import { clsx } from 'clsx'

/**
 * Casca de duas colunas de dentro da OS: lista de coletas à esquerda, detalhe
 * à direita, a partir de 1024px.
 *
 * As duas rotas (`/[osId]` e `/[osId]/coleta/[itemId]`) renderizam este mesmo
 * componente — é por isso que clicar numa coleta continua sendo navegação de
 * rota real, com URL, deep link, botão voltar, Esc, `PendingLink` e
 * `NavProgressBar` funcionando sem nenhum caso especial.
 *
 * Abaixo de 1024px só um lado aparece, escolhido por `narrow`, e o resultado é
 * idêntico ao layout de coluna única de antes. A escolha é CSS: os dois lados
 * estão sempre no DOM. Decidir isso em JS (matchMedia) daria HTML diferente no
 * servidor e no cliente — hidratação quebrada, que já custou caro aqui antes.
 *
 * Custo aceito: em celular, a rota da coleta monta a lista escondida. Não há
 * requisição extra — as duas rotas já usam `useOsDetail`, então vem do cache
 * do React Query.
 */
export function SplitPane({
  list,
  narrow,
  children,
}: {
  list: React.ReactNode
  narrow: 'list' | 'detail'
  children: React.ReactNode
}) {
  return (
    <div className="mx-auto w-full lg:grid lg:max-w-[1440px] lg:grid-cols-[minmax(320px,380px)_1fr] lg:items-start lg:gap-6">
      <div
        data-pane="list"
        className={clsx(
          'lg:sticky lg:top-0 lg:block lg:max-h-full lg:overflow-y-auto lg:pr-1',
          narrow === 'detail' && 'hidden',
        )}
      >
        {list}
      </div>
      <div
        data-pane="detail"
        className={clsx('min-w-0 lg:block', narrow === 'list' && 'hidden')}
      >
        {children}
      </div>
    </div>
  )
}
