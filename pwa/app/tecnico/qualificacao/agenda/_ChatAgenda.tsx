'use client'
import { memo, useEffect, useState } from 'react'
import { Send, Mic, X, Check } from 'lucide-react'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { useChatAgenda, type Bolha } from '@/lib/hooks/useChatAgenda'
import { useDitado } from '@/lib/hooks/useDitado'
import { useGroqStatus } from '@/lib/hooks/useGroqStatus'
import type { AgendaPayload } from '@/lib/odoo/agenda'
import { montarCardProposta } from '@/lib/chat/card'
import { DetalhesTraco, formatarNumero, formatarCusto } from './_DetalhesTraco'
import { MarkdownAssistente } from './_MarkdownAssistente'

/**
 * Lista de bolhas da conversa, isolada num componente `memo`.
 *
 * `ditado.nivelAudio` (Task 2) atualiza a cada ~50ms enquanto grava, e
 * `ChatAgenda` inteiro re-renderiza a cada troca de estado do hook — sem
 * isolar a lista, isso incluiria re-renderizar a conversa inteira (com
 * markdown) a ~20Hz durante a gravação, no celular do técnico em campo.
 * `bolhas` só muda quando o gestor manda mensagem ou a resposta chega
 * (`useState` em `useChatAgenda`, referência estável entre renders) — o
 * `memo` faz bail-out em todo render onde só `nivelAudio` mudou.
 */
const Bolhas = memo(function Bolhas({ bolhas }: { bolhas: Bolha[] }) {
  return (
    <>
      {bolhas.map((b, i) => (
        <div
          key={i}
          className={
            b.autor === 'user'
              ? 'self-end rounded-lg bg-primary/10 px-3 py-2 text-sm'
              : b.autor === 'erro'
                ? 'self-start rounded-lg bg-destructive/10 px-3 py-2 text-sm'
                : 'self-start rounded-lg bg-muted px-3 py-2 text-sm'
          }
        >
          {b.autor === 'assistente' ? (
            // Só a bolha do assistente passa por markdown — texto do
            // gestor e das bolhas de erro é montado pelo nosso código,
            // não pelo modelo, e fica em texto puro de propósito (ver
            // `_MarkdownAssistente.tsx`).
            <MarkdownAssistente texto={b.texto} />
          ) : (
            b.texto
          )}
          {b.tracos && <DetalhesTraco tracos={b.tracos} />}
        </div>
      ))}
    </>
  )
})

// Pesos por barra do medidor de nível — geometria da silhueta (dá cara de
// forma de onda), não canais de áudio diferentes: TODAS as barras leem a
// MESMA amostra (`ditado.nivelAudio`). O índice de peso 1 é a barra
// "cheia", usada como referência determinística no teste do medidor.
const PESOS_BARRA_MEDIDOR = [0.55, 1, 0.8, 0.45]
// Altura mínima visual (%) mesmo com nível 0 — sem isto, um instante de
// silêncio entre rajadas (comum: a máquina de silêncio corta ali de
// propósito) faria as quatro barras colapsarem pra uma linha reta, que
// lê como "travou", não como "silêncio".
const PISO_BARRA_PCT = 15
// `nivelAudio` é RMS cru de `AnalyserNode.getFloatTimeDomainData` — a
// ESCALA teórica é [0, 1] (senoide de amplitude cheia bate ~0.707, ver
// `deteccaoSilencio.test.ts`), mas fala captada por microfone de celular
// nunca chega perto disso: `limiarSilencio` (`deteccaoSilencio.ts`) marca
// o piso de ruído em 0.01, e os testes da máquina de silêncio usam 0.5
// como "voz" só pra ficar bem acima do piso, sem pretender medir uma fala
// real. Sem uma referência de "cheio" abaixo de 1, `Math.min(1, nivelAudio)`
// deixa a barra colada no piso visual (`PISO_BARRA_PCT`) durante uma frase
// inteira — exatamente a linha reta que o piso existe pra evitar, só que
// permanente. `NIVEL_REFERENCIA_CHEIA` é uma estimativa não medida (a
// medição de áudio real falhou em ambiente headless nas Tasks 1-2, ver
// `progress.md`), ~10x o piso de ruído — dá pra fala normal mover o
// medidor sem exigir grito. Ajustável sem mudar o resto da task se o uso
// real mostrar o medidor insensível ou saturado demais.
const NIVEL_REFERENCIA_CHEIA = 0.1

export function ChatAgenda({
  open,
  onClose,
  payload,
}: {
  open: boolean
  onClose: () => void
  payload: AgendaPayload | undefined
}) {
  const [texto, setTexto] = useState('')
  const { bolhas, proposta, ocupado, enviar, confirmar, cancelar, totais } =
    useChatAgenda(payload)
  const { enabled: ditadoHabilitado } = useGroqStatus()
  const ditado = useDitado((t) => setTexto((antes) => (antes ? `${antes} ${t}` : t)))

  // `ChatAgenda` nunca desmonta quando a folha fecha — é o `BottomSheet`
  // que se esconde por dentro (ver o achado da review). Sem isto, fechar
  // a folha com o mic ligado deixa a gravação correndo atrás de uma tela
  // invisível, sem nenhum controle visível pro gestor parar. `open` vira
  // `false` → descarta a gravação em andamento, nunca transcreve: o
  // gestor fechou o chat, não pediu o texto.
  useEffect(() => {
    if (!open) {
      ditado.pararEDescartar()
    }
  }, [open, ditado.pararEDescartar])

  if (!payload?.can_manage) return null

  const card = proposta ? montarCardProposta(payload, proposta) : null

  async function submeter(e: React.FormEvent) {
    e.preventDefault()
    // Só limpar o campo se o envio for mesmo acontecer: `enviar` tem seu
    // próprio guard (texto vazio, ocupado, sem payload) e retorna cedo
    // sem mandar nada — limpar `texto` ANTES desse guard perde o que o
    // gestor escreveu, sem enviar e sem devolver o texto pra tela.
    if (ocupado || !texto.trim()) return
    const t = texto
    setTexto('')
    await enviar(t)
  }

  return (
    <BottomSheet open={open} title="Agendar por conversa" onClose={onClose}>
      <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pb-2">
        {bolhas.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Peça em português: “remarca a visita do João de quinta pra sexta”,
            “quem está livre dia 20?”.
          </p>
        )}
        <Bolhas bolhas={bolhas} />

        {proposta && card && (
          <div className="rounded-lg border border-primary/40 bg-primary/5 p-3">
            <p className="text-sm font-medium">{card.titulo}</p>
            {card.subtitulo && (
              <p className="mt-1 text-xs text-muted-foreground">{card.subtitulo}</p>
            )}
            {card.aviso && (
              <p className="mt-1 text-xs text-destructive">{card.aviso}</p>
            )}
            {card.linhas.length > 0 && (
              <div className="mt-2 space-y-0.5">
                {card.linhas.map((l) => (
                  <p key={l.rotulo} className="text-sm">
                    <span className="text-muted-foreground">{l.rotulo}</span>{' '}
                    {l.de ? `${l.de} → ${l.para}` : l.para}
                  </p>
                ))}
              </div>
            )}
            {proposta.tracos && <DetalhesTraco tracos={proposta.tracos} />}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="min-h-[44px] flex-1 rounded-md bg-primary px-3 text-primary-foreground disabled:opacity-50"
                disabled={ocupado}
                onClick={confirmar}
              >
                Confirmar
              </button>
              <button
                type="button"
                className="min-h-[44px] flex-1 rounded-md border border-border px-3 disabled:opacity-50"
                disabled={ocupado}
                onClick={cancelar}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {ocupado && (
          <p className="text-xs text-muted-foreground">consultando a agenda…</p>
        )}
      </div>

      {totais.chamadas > 0 && (
        <p className="mt-2 border-t border-border pt-2 text-center text-xs text-muted-foreground">
          {totais.chamadas} {totais.chamadas === 1 ? 'chamada' : 'chamadas'} · {formatarNumero(totais.entrada + totais.saida)} tokens
          {/* `formatarCusto` usa vírgula, não ponto — mesma convenção de
              `formatarSegundos` em `_DetalhesTraco.tsx`; achado de review:
              este rodapé usava `.toFixed()` cru e destoava do resto do
              painel. */}
          {totais.temCusto ? ` · US$ ${formatarCusto(totais.custo)}` : ''}
        </p>
      )}

      <form onSubmit={submeter} className="mt-3 flex items-center gap-2">
        <input
          className="min-h-[44px] flex-1 rounded-md border border-border bg-background px-3"
          // "Ouvindo…" sai de graça: placeholder de HTML só aparece com o
          // campo vazio, então ele se apaga sozinho assim que a primeira
          // rajada trai texto — não precisa de estado próprio, só lê
          // `ditado.gravando` (que já existe).
          placeholder={ditado.gravando ? 'Ouvindo…' : 'Escreva o que precisa'}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={ocupado}
        />

        {ditadoHabilitado && (
          // As barras do medidor logo abaixo são `aria-hidden` — sozinhas
          // não dizem nada pra quem usa leitor de tela. Este `role="status"`
          // é quem cobre essa informação: anuncia a virada pra "Gravando" e
          // depois "Transcrevendo" (as duas fases que a barra visual
          // comunica) e volta a ficar vazio fora delas — sem isto a troca de
          // estado inteira fica muda pra quem não vê a tela.
          <span role="status" aria-live="polite" className="sr-only">
            {ditado.gravando ? 'Gravando' : ditado.transcrevendo ? 'Transcrevendo' : ''}
          </span>
        )}

        {ditadoHabilitado && ditado.gravando && (
          <>
            {/* Medidor de nível: todas as barras leem a MESMA amostra
                (`ditado.nivelAudio`, RMS lido do AnalyserNode a cada ~50ms
                dentro de `useDitado` — Task 2). Ele se move porque o áudio
                se move, não por keyframe — não é o vocabulário de animação
                decorativa em loop que o DESIGN.md aposentou
                (`animate-pulse-glow` e cia.), é dado, e uma limpeza de
                animação futura não pode confundir os dois. `aria-hidden`
                aqui porque o `role="status"` acima já cobre a informação
                pra leitor de tela. Sob `prefers-reduced-motion`
                (`motion-reduce:transition-none`) é a TRANSIÇÃO entre
                valores que vira corte — os valores continuam mudando com o
                áudio. */}
            <div
              aria-hidden="true"
              data-testid="medidor-nivel"
              className="flex h-[44px] w-11 shrink-0 items-end justify-center gap-0.5 rounded-md border border-border px-2 py-1.5"
            >
              {PESOS_BARRA_MEDIDOR.map((peso, i) => (
                <span
                  key={i}
                  data-testid={peso === 1 ? 'medidor-barra-referencia' : undefined}
                  className="w-1 rounded-full bg-foreground transition-[height] duration-100 ease-out motion-reduce:transition-none"
                  style={{
                    height: `${Math.max(PISO_BARRA_PCT, Math.round(Math.min(1, Math.max(0, ditado.nivelAudio) / NIVEL_REFERENCIA_CHEIA) * peso * 100))}%`,
                  }}
                />
              ))}
            </div>

            {/* ✕ descarta sem transcrever — `pararEDescartar()` existe no
                hook desde a Task 2, mas até aqui a interface nunca ofereceu
                um jeito de chamá-la: começar a gravar obrigava o gestor a
                transcrever, mesmo que tivesse mudado de ideia. Vermelho
                porque é perda de trabalho de verdade (o áudio capturado
                some) — mesmo critério do botão destructive do DESIGN.md. */}
            <button
              type="button"
              aria-label="Descartar gravação"
              onClick={ditado.pararEDescartar}
              className="min-h-[44px] min-w-[44px] rounded-md bg-destructive text-destructive-foreground"
            >
              <X className="mx-auto h-4 w-4" />
            </button>

            {/* ✓ é "parar e transcrever" — o mesmo `alternar()` que hoje já
                faz isso no segundo clique do mic (com `gravando` true,
                `alternar()` só chama `parar()`). */}
            <button
              type="button"
              aria-label="Parar gravação"
              onClick={ditado.alternar}
              className="min-h-[44px] min-w-[44px] rounded-md bg-primary text-primary-foreground"
            >
              <Check className="mx-auto h-4 w-4" />
            </button>
          </>
        )}

        {/* Esconde, não desabilita: um botão desabilitado sem explicação é
            tão mudo quanto o defeito relatado ("cliquei no mic e não
            aconteceu nada") — mesmo critério do `MicButton.tsx` (coleta),
            que faz `return null` quando a IA está desligada. */}
        {ditadoHabilitado && !ditado.gravando && (
          <button
            type="button"
            aria-label="Ditar"
            onClick={ditado.alternar}
            disabled={ocupado || ditado.transcrevendo}
            className="min-h-[44px] min-w-[44px] rounded-md border border-border"
          >
            <Mic className="mx-auto h-4 w-4" />
          </button>
        )}

        {/* Some junto com o mic durante a gravação — dá lugar ao medidor e
            aos botões ✕/✓ (ver acima). */}
        {!ditado.gravando && (
          <button
            type="submit"
            aria-label="Enviar"
            className="min-h-[44px] min-w-[44px] rounded-md bg-primary text-primary-foreground disabled:opacity-50"
            disabled={ocupado || !texto.trim()}
          >
            <Send className="mx-auto h-4 w-4" />
          </button>
        )}
      </form>
    </BottomSheet>
  )
}
