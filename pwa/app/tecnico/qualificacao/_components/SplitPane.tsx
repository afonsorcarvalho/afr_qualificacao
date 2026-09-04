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
 *
 * Rolagem independente (fix 2026-09-04): a primeira versão usava
 * `lg:sticky lg:top-0 lg:max-h-full lg:overflow-y-auto` na coluna da lista,
 * apostando que `max-height:100%` resolveria contra a altura do item do
 * grid. Não resolve — o item do grid não tem altura definida (a track é
 * `auto`, do tamanho do conteúdo), então `max-height:100%` vira `none` por
 * spec, `overflow-y-auto` nunca ativa, e quem rola é o `<main>` inteiro lá
 * de cima do layout — arrastando as duas colunas juntas. Confirmado rolando
 * o `<main>` de verdade num browser: o formulário à direita sai da tela
 * junto com a lista. Fix: `lg:grid-rows-1` no container (equivale a
 * `grid-template-rows: repeat(1, minmax(0,1fr))` no Tailwind, a track
 * "blowout fix" padrão) + `lg:h-full` pra dar altura definida à track, e
 * `lg:min-h-0 lg:overflow-y-auto` nas DUAS colunas — cada uma vira seu
 * próprio container de rolagem, limitado à altura da linha do grid.
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
    <div className="mx-auto w-full lg:grid lg:h-full lg:max-w-[1440px] lg:grid-cols-[minmax(320px,380px)_1fr] lg:grid-rows-1 lg:items-stretch lg:gap-6">
      {/* Sem isto, tab a partir do topo passa por ~24 links da lista antes
          de chegar no formulário — só aparece no foco (sr-only), então não
          ocupa espaço nem aparece pra quem usa mouse/toque. */}
      <a
        href="#detalhe"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        Ir para o formulário
      </a>
      <div
        data-pane="list"
        className={clsx(
          'lg:block lg:min-h-0 lg:overflow-y-auto lg:pr-1',
          narrow === 'detail' && 'hidden',
        )}
      >
        {list}
      </div>
      <div
        id="detalhe"
        data-pane="detail"
        className={clsx(
          'min-w-0 lg:block lg:min-h-0 lg:overflow-y-auto',
          narrow === 'list' && 'hidden',
        )}
      >
        {children}
      </div>
    </div>
  )
}
