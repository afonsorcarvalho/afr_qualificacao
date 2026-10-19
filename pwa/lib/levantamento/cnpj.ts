export const onlyDigits = (s: string): string => (s ?? '').replace(/\D/g, '')

function digit(base: string, weights: number[]): number {
  const sum = weights.reduce((acc, w, i) => acc + w * Number(base[i]), 0)
  const r = sum % 11
  return r < 2 ? 0 : 11 - r
}

/** Valida os dois dígitos verificadores; rejeita sequências repetidas. */
export function isValidCnpj(s: string): boolean {
  const d = onlyDigits(s)
  if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false
  const d1 = digit(d, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
  const d2 = digit(d, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
  return d1 === Number(d[12]) && d2 === Number(d[13])
}

/** Máscara progressiva `12.345.678/0001-95` (aceita entrada parcial). */
export function maskCnpj(s: string): string {
  const d = onlyDigits(s).slice(0, 14)
  let out = d.slice(0, 2)
  if (d.length > 2) out += '.' + d.slice(2, 5)
  if (d.length > 5) out += '.' + d.slice(5, 8)
  if (d.length > 8) out += '/' + d.slice(8, 12)
  if (d.length > 12) out += '-' + d.slice(12, 14)
  return out
}
