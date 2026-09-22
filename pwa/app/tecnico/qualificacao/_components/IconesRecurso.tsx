import type { SVGProps } from 'react'

/**
 * Silhueta preenchida de pessoa — substitui `User` do lucide (outline) nos
 * tamanhos 14-16px do Painel/Card, onde o traço fino do lucide perde
 * definição. `fill="currentColor"` lê a cor do `style.color` do call site,
 * mesmo mecanismo do `stroke="currentColor"` que ele substitui.
 */
export function IconeTecnico(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M12 12q-1.65 0-2.825-1.175Q8 9.65 8 8t1.175-2.825Q10.35 4 12 4t2.825 1.175Q16 6.35 16 8t-1.175 2.825Q13.65 12 12 12Zm-8 8v-2.8q0-.85.438-1.563.437-.712 1.162-1.087 1.55-.775 3.15-1.163Q10.35 13 12 13t3.25.387q1.6.388 3.15 1.163.725.375 1.163 1.087Q20 16.35 20 17.2V20Z" />
    </svg>
  )
}

/** Silhueta preenchida de chave de boca — substitui `Wrench` do lucide, mesmo raciocínio de `IconeTecnico`. */
export function IconeInstrumento(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z" />
    </svg>
  )
}
