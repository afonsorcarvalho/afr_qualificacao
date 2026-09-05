'use client'
import { ReactNode, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Wrench } from 'lucide-react'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import {
  NavProgressBar,
  NavProgressProvider,
} from '@/components/providers/NavProgress'
import { TecnicoNav } from './_components/TecnicoNav'

const ROOT_PATH = '/tecnico/qualificacao'

export default function TecnicoLayout({ children }: { children: ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const setLastUserId = useTecnicoSettings((s) => s.setLastUserId)

  // Refresca `lastUserId` uma vez por montagem do layout (todo entra em
  // /tecnico/qualificacao/*, este layout persiste por baixo). Sem isso, só a
  // home e o histórico buscavam session-info — abrir direto uma rota como
  // /[osId] (deep link, PWA reaberto) via localStorage estale ou vazio deixava
  // `lastUserId` desatualizado/null, e `useOsDetail` (que agora escopa por
  // `create_uid`) ou nunca disparava, ou pior, escopava pelo usuário ERRADO
  // se outro técnico tivesse usado o mesmo aparelho antes.
  useEffect(() => {
    fetch('/api/odoo/session-info')
      .then((r) => r.json())
      .then((d) => d?.uid && setLastUserId(d.uid))
      .catch(() => {})
  }, [setLastUserId])

  useEffect(() => {
    if (pathname === ROOT_PATH) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || target?.isContentEditable) return
      e.preventDefault()
      router.back()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pathname, router])

  return (
    <NavProgressProvider>
      {/* Altura definida em TODA largura, não só a partir de 1024px: com
          `min-h-screen` o invólucro crescia com o conteúdo em tela estreita, o
          `<main overflow-auto>` crescia junto, quem rolava era a janela e o
          scrollport do `main` nunca rolava — todo `sticky` lá dentro ficava
          inerte (medido a 375px: o filtro de coletas saía da tela junto com a
          lista). `dvh` porque a barra de endereço do celular muda a altura
          visível. Efeito colateral aceito: a barra de navegação inferior
          deixa de rolar junto e fica sempre à vista. */}
      <div className="mx-auto flex h-dvh min-h-0 w-full max-w-[480px] flex-col overflow-hidden bg-background sm:max-w-[720px] lg:max-w-none lg:flex-row">
        <TecnicoNav variant="side" />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-10 border-b border-border bg-card shadow-md lg:static lg:shadow-none">
            <div className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-2">
                <Wrench className="h-5 w-5 text-foreground" />
                <span className="font-semibold">Qualificação · Técnico</span>
              </div>
            </div>
            {/* Toda navegação acende esta barra até a rota nova aparecer. */}
            <NavProgressBar />
          </header>
          {/* O respiro fica no wrapper, não no `main`: com `p-3` no próprio
              scrollport, o conteúdo rolava por dentro da faixa de 12px acima
              do primeiro elemento grudado (sticky ancora na borda do padding,
              não na do main), e cartão passando por trás do filtro é
              exatamente o que ele existe pra impedir. */}
          <main className="min-h-0 flex-1 overflow-auto">
            {/* `h-full` porque o `SplitPane` usa `lg:h-full` pra dar altura à
                linha do grid e ligar a rolagem independente das duas colunas:
                sem altura definida aqui aquilo vira `auto` e quem rola volta a
                ser o `main` inteiro, arrastando as duas colunas juntas. */}
            <div className="h-full p-3">{children}</div>
          </main>
          <TecnicoNav variant="bottom" />
        </div>
      </div>
    </NavProgressProvider>
  )
}
