import type { ReactNode } from 'react'

/**
 * Célula de contador do resumo "Hoje" (Histórico).
 *
 * Extraída de `historico/page.tsx` pra poder ser renderizada isolada em
 * teste (`HistoricoPerfil.test.tsx`) — um `page.tsx` de App Router só pode
 * exportar os nomes que o Next reconhece (`default`, `metadata`,
 * `generateStaticParams`, ...); exportar um componente auxiliar por lá
 * quebra a tipagem gerada da rota.
 */
export function SummaryCell({
  icon, value, label, tone,
}: {
  icon: ReactNode
  value: number
  label: string
  tone: 'info' | 'ok'
}) {
  // O número é dado neutro (não estado) — vira `text-foreground`. O ícone
  // acompanha o token do seu escopo: `info` pras duas contagens sem estado
  // próprio (fotos/OSs de hoje), `ok` pra "rel. fechados" — mesmo token de
  // "concluído" usado no card de relatório logo abaixo. O rótulo abaixo do
  // número já diz o que é ("coletas", "OSs", "rel. fechados") — é texto
  // secundário, não repete o token do ícone (mesma lição do metadado do
  // `EquipmentHeader`: secundário vira `text-muted-foreground`, não o peso
  // do primário).
  const color = tone === 'info' ? 'text-info' : 'text-ok'
  return (
    <div className="rounded-lg bg-muted/30 p-2 text-center">
      <div className={`mx-auto mb-1 flex h-6 w-6 items-center justify-center ${color}`}>{icon}</div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
    </div>
  )
}
