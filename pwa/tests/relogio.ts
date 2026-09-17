/**
 * Sabotagem do relógio do aparelho para os testes-âncora de cálculo de data.
 *
 * Sabotar só `Date.now` não fecha o buraco: `new Date()` sem argumento lê a
 * hora do sistema por um caminho interno que não passa pela propriedade
 * `Date.now` — um `new Date()` cru escondido dentro de uma função de data
 * passaria batido por uma âncora que só sobrescreve `Date.now`. Este helper
 * sabota os dois: `Date.now()` e `new Date()` sem argumento estouram; `new
 * Date(x)` com argumento (o caso normal de cálculo a partir de uma data
 * conhecida) continua delegando pro `Date` real. Restaura sempre, mesmo se
 * a asserção do chamador estourar — não é código de produção, por isso mora
 * em `tests/`, fora de `app`/`components`/`lib`.
 */
export function semRelogioDoAparelho<T>(fn: () => T): T {
  const RealDate = Date

  class DataSabotada extends RealDate {
    constructor(...args: any[]) {
      if (args.length === 0) {
        throw new Error('relógio do aparelho usado')
      }
      // @ts-expect-error — `args` não está vazio aqui, mas o construtor do
      // `Date` real é sobrecarregado por aridade fixa, não por rest
      // parameter; repassamos os argumentos originais de qualquer forma.
      super(...args)
    }

    static now(): number {
      throw new Error('relógio do aparelho usado')
    }
  }

  globalThis.Date = DataSabotada as unknown as DateConstructor
  try {
    return fn()
  } finally {
    globalThis.Date = RealDate
  }
}
