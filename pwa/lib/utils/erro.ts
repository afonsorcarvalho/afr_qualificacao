/**
 * Leitura segura de erro capturado.
 *
 * `catch (e)` entrega `unknown`, e era isso que o código contornava com
 * `catch (e: any)` — em oito lugares, todos terminando num `toast.error`.
 * O `any` calava o compilador mas não o problema: `e.message` em algo que
 * não é Error dá `undefined` no toast, e `e.name` num erro que atravessou
 * realm nem sempre existe.
 *
 * Nem todo erro é `instanceof Error`: o que vem de worker, iframe, `fetch`
 * de API ou biblioteca antiga chega como objeto simples com `message`.
 */

function comoRegistro(e: unknown): Record<string, unknown> | null {
  return typeof e === 'object' && e !== null ? (e as Record<string, unknown>) : null
}

function textoUtil(v: unknown): string | undefined {
  return typeof v === 'string' && v.trim() ? v : undefined
}

/**
 * Frase para mostrar ao usuário. Nunca devolve string vazia — toast em
 * branco é pior que texto genérico.
 */
export function mensagemDoErro(e: unknown, padrao = 'Erro inesperado'): string {
  if (e instanceof Error) return textoUtil(e.message) ?? padrao
  const direto = textoUtil(e)
  if (direto) return direto
  const reg = comoRegistro(e)
  return (reg && textoUtil(reg.message)) ?? padrao
}

/**
 * Nome do erro, quando existe. É o que distingue `NotAllowedError`
 * (usuário negou o microfone) de uma falha qualquer — a mensagem varia por
 * navegador, o nome não.
 */
export function nomeDoErro(e: unknown): string | undefined {
  if (e instanceof Error) return textoUtil(e.name)
  const reg = comoRegistro(e)
  return reg ? textoUtil(reg.name) : undefined
}
