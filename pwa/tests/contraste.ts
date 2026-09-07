/**
 * Matemática de contraste WCAG compartilhada pelos testes de tema.
 *
 * Mora aqui, e não dentro de um `describe`, porque a duplicação já custou:
 * `StatusBadge.test.tsx` afirmava que o render do chip "não pode mudar em
 * tema nenhum" apoiado em `text-emerald-700` bater com `--ok` do tema claro
 * — verdade quando escrito, falso depois que a Task 13 escureceu `--ok` para
 * o equivalente a emerald-800. Duas cópias da mesma medição divergem em
 * silêncio; uma cópia só, importada pelos dois arquivos, não.
 *
 * Não é código de produção: fica em `tests/` (fora de `app`/`components`/
 * `lib`), e o nome sem `.test.` mantém o vitest de coletá-lo como suíte.
 */

/** HSL (graus, %, %) -> RGB (0-255), conversão padrão sem lib de cor. */
export function hsl2rgb(triple: string): number[] {
  const [hStr, sStr, lStr] = triple.trim().split(/\s+/)
  const h = parseFloat(hStr)
  const s = parseFloat(sStr) / 100
  const l = parseFloat(lStr) / 100
  const c = (1 - Math.abs(2 * l - 1)) * s
  const hp = h / 60
  const x = c * (1 - Math.abs((hp % 2) - 1))
  let r1 = 0
  let g1 = 0
  let b1 = 0
  if (hp >= 0 && hp < 1) [r1, g1, b1] = [c, x, 0]
  else if (hp < 2) [r1, g1, b1] = [x, c, 0]
  else if (hp < 3) [r1, g1, b1] = [0, c, x]
  else if (hp < 4) [r1, g1, b1] = [0, x, c]
  else if (hp < 5) [r1, g1, b1] = [x, 0, c]
  else [r1, g1, b1] = [c, 0, x]
  const m = l - c / 2
  return [r1, g1, b1].map((v) => Math.round((v + m) * 255))
}

/** Luminância relativa WCAG (fórmula 1.4.3). */
export function luminancia([r, g, b]: number[]): number {
  const canal = (v: number) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)
}

/** Razão de contraste entre duas cores opacas. */
export function contraste(a: number[], b: number[]): number {
  const la = luminancia(a) + 0.05
  const lb = luminancia(b) + 0.05
  return la > lb ? la / lb : lb / la
}

/** Composição alpha: `fg` a `alpha` de opacidade sobre `bg` opaco. */
export function sobre(fg: number[], alpha: number, bg: number[]): number[] {
  return fg.map((c, i) => Math.round(c * alpha + bg[i] * (1 - alpha)))
}

/**
 * Lê a tripla HSL de um token dentro de um bloco de seletor do `globals.css`
 * (`:root` = tema claro, `:root.dark` = escuro). Devolve `null` quando o
 * token não existe — quem chama decide se isso é falha ou "não aplicável".
 */
export function tokenDe(css: string, seletor: string, papel: string): string | null {
  const i = css.indexOf(`${seletor} {`)
  if (i < 0) return null
  const bloco = css.slice(i, css.indexOf('\n}', i))
  const m = bloco.match(new RegExp(String.raw`--${papel}:\s*([^;]+);`))
  return m ? m[1].trim() : null
}
