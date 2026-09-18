'use client'
import { BottomSheet } from '@/components/ui/BottomSheet'

/**
 * "2026-09-18" → "18/09/2026", em UTC — nunca `toLocaleDateString()` sem
 * fuso (leria o relógio do aparelho, não o calendário do servidor).
 */
function formatarData(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number)
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC',
  }).format(new Date(Date.UTC(a, m - 1, d)))
}

/**
 * Confirmação antes de gravar a mudança de DATA de uma visita (gesto de
 * mover, Semana e Mês). Sem estado próprio além do necessário para
 * renderizar — quem decide abrir, confirmar ou cancelar é a `page.tsx`
 * (ruling do controlador, mesmo padrão dos outros componentes da agenda).
 */
export function ConfirmarMudancaData({
  open,
  osName,
  dataAtual,
  dataNova,
  onConfirmar,
  onCancelar,
}: {
  open: boolean
  osName: string
  /** ISO (`YYYY-MM-DD`) da data atual da visita. */
  dataAtual: string
  /** ISO (`YYYY-MM-DD`) do destino tocado na grade/faixa. */
  dataNova: string
  onConfirmar: () => void
  onCancelar: () => void
}) {
  // `page.tsx` sempre monta este componente (não condiciona no JSX) e passa
  // `''` para `dataAtual`/`dataNova` quando não há diálogo pendente — sem
  // este retorno cedo, `formatarData('')` rodaria a cada render do resto da
  // agenda e quebraria com `RangeError: Invalid time value`, escondido atrás
  // do `open={false}` que o `BottomSheet` só checa depois de já ter
  // avaliado estes `children`.
  if (!open) return null
  return (
    <BottomSheet open={open} title="Mudar data da visita" onClose={onCancelar}>
      <p className="text-sm">
        Tem certeza que deseja mudar a data da visita {osName} de{' '}
        {formatarData(dataAtual)} para {formatarData(dataNova)}?
      </p>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={onCancelar}
          className="min-h-[44px] flex-1 rounded-md border border-border px-3 text-sm font-medium"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={onConfirmar}
          className="min-h-[44px] flex-1 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground"
        >
          Confirmar
        </button>
      </div>
    </BottomSheet>
  )
}
