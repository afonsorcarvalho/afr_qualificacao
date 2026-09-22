// lib/chat/semana.ts
// Helpers puros de "semana" para o prompt do chat de agendamento.
//
// O defeito que isto resolve: pedido "como tá a agenda da semana que vem?",
// o modelo fazia a própria aritmética de calendário a partir da data de hoje
// e sorteava um intervalo de sete dias diferente a cada chamada — três
// janelas distintas em três execuções idênticas (ver plano
// docs/superpowers/plans/2026-09-21-semana-no-prompt.md). A correção é
// nunca deixar o modelo calcular: ele recebe os intervalos já prontos.
//
// Toda aritmética usa Date.UTC, nunca o relógio local — o fuso do aparelho
// não pode decidir que dia é hoje nem em que dia a semana começa (mesma
// razão registrada em app/tecnico/qualificacao/agenda/janela.ts).

export interface IntervaloSemana {
  from: string
  to: string
}

/**
 * Dia em que a semana do produto começa, no mesmo esquema de
 * `Date#getUTCDay` (0 = domingo … 6 = sábado). `1` = segunda-feira.
 *
 * Isto é decisão de produto, não detalhe técnico: o parceiro humano decidiu
 * em 2026-09-21 que a semana vai de segunda a domingo (costume brasileiro e
 * ISO-8601). Único lugar do código que conhece esse número — nenhum outro
 * arquivo repete `1` ou `7` para isto.
 */
export const DIA_INICIO_SEMANA = 1

function paraData(iso: string): Date {
  const [ano, mes, dia] = iso.split('-').map(Number)
  return new Date(Date.UTC(ano, mes - 1, dia))
}

function paraIso(data: Date): string {
  return data.toISOString().slice(0, 10)
}

function somarDias(iso: string, dias: number): string {
  const data = paraData(iso)
  data.setUTCDate(data.getUTCDate() + dias)
  return paraIso(data)
}

/**
 * A semana (segunda a domingo) que contém `iso`.
 *
 * O caso que uma implementação ingênua erra é o domingo: `getUTCDay()`
 * devolve `0`, que fica numericamente "antes" de `DIA_INICIO_SEMANA` (`1`)
 * na escala 0-6. `diaSemana - DIA_INICIO_SEMANA` dá `-1`, e o operador `%`
 * de JS preserva o sinal do operando esquerdo (`-1 % 7 === -1`, não `6`) —
 * sem o `+ 7` antes do `% 7`, o domingo "andaria" um dia para a frente em
 * vez de voltar seis dias até a segunda anterior.
 */
export function semanaDe(iso: string): IntervaloSemana {
  const diaSemana = paraData(iso).getUTCDay()
  const deslocamento = (diaSemana - DIA_INICIO_SEMANA + 7) % 7
  const from = somarDias(iso, -deslocamento)
  const to = somarDias(from, 6)
  return { from, to }
}

/**
 * A semana de `iso` deslocada `n` semanas inteiras (positivo = futuro,
 * negativo = passado). Desloca em blocos de 7 dias e só então realinha com
 * `semanaDe`, para que "onde a semana começa" exista num único lugar.
 */
export function deslocarSemanas(iso: string, n: number): IntervaloSemana {
  return semanaDe(somarDias(iso, n * 7))
}
