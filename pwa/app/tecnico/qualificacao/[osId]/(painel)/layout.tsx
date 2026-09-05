'use client'
import { useState, useTransition } from 'react'
import { useParams, usePathname, useRouter } from 'next/navigation'
import { CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { LoadingState } from '@/components/ui/LoadingState'
import { useNavProgress } from '@/components/providers/NavProgress'
import { ColetaList } from '../../_components/ColetaList'
import { SplitPane } from '../../_components/SplitPane'
import { RelatorioHeader } from '../../_components/RelatorioHeader'
import { ReviewPanel } from '../../_components/ReviewPanel'
import {
  useOsDetail,
  useStartDailyRelatorio,
} from '@/lib/hooks/useTecnicoQualif'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import { buildSummaryContext } from '@/lib/tecnico/buildSummaryContext'
import toast from 'react-hot-toast'

/**
 * Dono da coluna esquerda de `/[osId]` e `/[osId]/coleta/[itemId]`: as duas
 * rotas vivem sob este grupo `(painel)` e renderizam este mesmo layout, que
 * não desmonta entre elas (Task 1 provou isso). É por isso que a lista de
 * coletas sobrevive à navegação em vez de remontar a cada clique — o bug que
 * esta task existe pra resolver.
 */
export default function PainelLayout({ children }: { children: React.ReactNode }) {
  const { osId } = useParams<{ osId: string }>()
  const id = parseInt(osId, 10)
  const router = useRouter()
  const pathname = usePathname()
  const { lastUserId } = useTecnicoSettings()
  const userId = lastUserId ?? 0
  const { data, isLoading, error, refetch } = useOsDetail(id, userId)
  const startMutation = useStartDailyRelatorio()
  const { begin } = useNavProgress()
  // A ida pra tela de fechar turno também busca dados: sem `useTransition` o
  // botão ficava mudo entre o toque e a troca de tela.
  const [finalizando, startFinalize] = useTransition()
  // Só o clique em "Atualizar" liga isto — nunca o refetch automático de
  // fundo que o segundo observador de `useOsDetail` (a página de coleta,
  // mesma query key) pode disparar ao montar sobre dado stale. Sem esta
  // separação, `isFetching` piscava o botão "Atualizando..." a cada clique
  // numa coleta, mesmo sem o técnico ter pedido nada.
  const [atualizandoManual, setAtualizandoManual] = useState(false)

  // `enabled: userId > 0` (useTecnicoQualif.ts) faz uma query desabilitada
  // reportar `isLoading === false` — sem isto, a janela em que `lastUserId`
  // ainda não chegou do zustand `persist` (primeira abertura, storage limpo,
  // sessão lenta/offline) caía direto no branch de erro.
  const carregandoOs = isLoading || userId <= 0

  // `narrow` deixa de ser fixo: segue a rota, não a página.
  const emColeta = pathname.includes('/coleta/')

  // `selectedId` sai do pathname, não do `useParams()`: dentro deste layout o
  // segmento `itemId` está abaixo dele na árvore, então `useParams()` devolve
  // só `{ osId }` — ler `itemId` dali daria `undefined` em silêncio, apagando
  // o marcador `aria-current` da linha aberta.
  const m = pathname.match(/\/coleta\/(\d+)/)
  const selectedId = m ? parseInt(m[1], 10) : undefined

  const handleStart = () => {
    startMutation.mutate(id, {
      onError: (e: any) => toast.error(e.message),
    })
  }
  const handleContinue = () => {
    setAtualizandoManual(true)
    refetch().finally(() => setAtualizandoManual(false))
  }
  const handleFinalize = () => {
    if (!data?.open_relatorio_id || finalizando) return
    begin()
    startFinalize(() =>
      router.push(`/tecnico/qualificacao/${id}/relatorio/${data.open_relatorio_id}/finalizar`),
    )
  }

  // O "← Voltar" fica FORA do ternário abaixo, de propósito: é o único
  // controle de volta em ≥1024px (o da própria página de coleta virou
  // `lg:hidden`), então precisa renderizar nos três estados — carregando,
  // erro e sucesso — não só no de sucesso.
  const botaoVoltar = (
    <Button variant="ghost" size="sm" className="min-h-[44px]" onClick={() => router.back()}>
      ← Voltar
      <kbd className="ml-2 hidden rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/90 sm:inline">Esc</kbd>
    </Button>
  )

  // Carregando e erro NÃO fazem early-return: ocupam só o painel da lista,
  // com `{children}` sempre montado no painel direito. Um early-return aqui
  // apagaria o painel direito junto — foram os achados 2 e 7 da revisão do
  // layout desktop, verificados corrigidos há poucas horas.
  const conteudo = carregandoOs ? (
    <LoadingState label="Carregando OS..." />
  ) : error || !data ? (
    <p className="text-center text-red-400">Erro ao carregar OS</p>
  ) : (
    (() => {
      const { os, collect_items, open_relatorio_id } = data
      const pending_items = collect_items.filter((i) => i.state === 'pending')
      const done_items = collect_items.filter(
        (i) => i.state === 'collected' || i.state === 'skipped',
      )
      return (
        <>
          <div className="rounded-lg bg-muted/30 p-3 shadow-sm border border-border/70">
            <h1 className="text-lg font-semibold text-foreground">{os.name}</h1>
            <p className="text-sm text-muted-foreground/90">{os.partner_id?.[1]}</p>
          </div>

          <RelatorioHeader
            openRelId={open_relatorio_id}
            onStart={handleStart}
            onContinue={handleContinue}
            starting={startMutation.isPending}
            refreshing={atualizandoManual}
            allDone={pending_items.length === 0 && done_items.length > 0}
          />

          {open_relatorio_id && done_items.length > 0 && (
            <ReviewPanel
              buildContext={() => buildSummaryContext(data)}
              osId={id}
              relId={open_relatorio_id}
              collapsedByDefault
            />
          )}

          {pending_items.length === 0 && done_items.length > 0 && (
            // Confirmação, não comemoração: o PRODUCT.md diz que a tela
            // informa e o DESIGN.md proíbe gradiente decorativo, emoji como
            // ícone e animação em loop — o bloco anterior tinha os três.
            <div className="rounded-lg border border-emerald-600/40 bg-emerald-500/10 p-3 dark:border-emerald-500/30">
              <div className="flex items-start gap-2">
                <CheckCircle2
                  className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700 dark:text-emerald-400"
                  aria-hidden
                />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">
                    Todas as coletas concluídas
                  </p>
                  <p className="mt-0.5 text-xs tabular-nums text-muted-foreground">
                    {done_items.length} de {done_items.length}{' '}
                    {done_items.length > 1 ? 'itens coletados' : 'item coletado'} nesta OS.
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {open_relatorio_id
                      ? 'Pronto pra finalizar o relatório do dia.'
                      : 'Ordem de Serviço concluída.'}
                  </p>
                </div>
              </div>
            </div>
          )}

          <ColetaList data={data} osId={id} selectedId={selectedId} />

          {open_relatorio_id && (
            <Button
              onClick={handleFinalize}
              className="h-12 w-full"
              loading={finalizando}
              loadingText="Abrindo fechamento..."
            >
              Finalizar relatório do dia
            </Button>
          )}
        </>
      )
    })()
  )

  const listaEsquerda = (
    <div className="space-y-4">
      {botaoVoltar}
      {conteudo}
    </div>
  )

  // Em desktop, clicar numa coleta troca só o painel direito e o foco não
  // se move — sem isto, quem usa leitor de tela não recebe aviso nenhum de
  // que a tela mudou. Fica FORA do `SplitPane` de propósito: a coluna da
  // lista ganha `hidden` em tela estreita, e conteúdo em `display:none` não
  // é anunciado. O nó existe sempre e só o texto muda; inserir região e
  // texto juntos não dispara anúncio na maioria dos leitores.
  const itemAberto = data?.collect_items.find((i) => i.id === selectedId)
  const anuncio = itemAberto ? `Coleta aberta: ${itemAberto.name}` : ''

  return (
    <>
      <p
        data-testid="painel-anuncio"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {anuncio}
      </p>
      <SplitPane narrow={emColeta ? 'detail' : 'list'} list={listaEsquerda}>
        {children}
      </SplitPane>
    </>
  )
}
