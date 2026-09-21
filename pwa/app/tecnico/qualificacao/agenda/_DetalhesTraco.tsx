'use client'
import type { TracoVolta } from '@/lib/chat/machine'

/** 3400 → "3,4" — segundos com vírgula (pt-BR), não ponto. */
function formatarSegundos(ms: number): string {
  return (ms / 1000).toFixed(1).replace('.', ',')
}

/** 4812 → "4.812" — pt-BR usa ponto de milhar, não vírgula. Exportado: o
 * rodapé de sessão em `_ChatAgenda.tsx` usa o mesmo formato. */
export function formatarNumero(n: number): string {
  return n.toLocaleString('pt-BR')
}

/**
 * Painel de debug de UMA resposta do chat: o que a IA de fato chamou (nome,
 * argumentos CRUS — é o ponto central, para o gestor pegar uma data errada
 * que o modelo mandou — e um resumo do resultado, nunca o payload cru), o
 * modelo que respondeu, e tokens/tempo da resposta inteira.
 *
 * Dobrável, fechado por padrão (`<details>` nativo, sem `open`): não pode
 * atrapalhar o uso normal do chat.
 */
export function DetalhesTraco({ tracos }: { tracos: TracoVolta[] }) {
  if (!tracos.length) return null

  const modelo = tracos.find((t) => t.modelo)?.modelo
  const entrada = tracos.reduce((soma, t) => soma + (t.usage?.prompt_tokens ?? 0), 0)
  const saida = tracos.reduce((soma, t) => soma + (t.usage?.completion_tokens ?? 0), 0)
  const duracaoMs = tracos.reduce((soma, t) => soma + t.duracaoMs, 0)

  return (
    <details className="mt-1 text-xs text-muted-foreground">
      <summary className="cursor-pointer select-none">detalhes</summary>
      <div className="mt-1 space-y-1.5 rounded-md border border-border bg-background/60 p-2">
        {tracos.map((volta, i) => (
          <div key={i}>
            {volta.chamadas.map((c, j) => (
              <div key={j}>
                <p className="font-mono">{i + 1} · {c.nome}</p>
                {c.argumentos !== undefined && (
                  <pre className="whitespace-pre-wrap break-all font-mono">{c.argumentos}</pre>
                )}
                {c.resultado !== undefined && <p>→ {c.resultado}</p>}
              </div>
            ))}
          </div>
        ))}
        <p className="border-t border-border pt-1.5">
          {modelo ? `${modelo} · ` : ''}
          {tracos.length} {tracos.length === 1 ? 'chamada' : 'chamadas'}
        </p>
        <p>
          {formatarNumero(entrada)} entrada / {formatarNumero(saida)} saída · {formatarSegundos(duracaoMs)}s
        </p>
      </div>
    </details>
  )
}
