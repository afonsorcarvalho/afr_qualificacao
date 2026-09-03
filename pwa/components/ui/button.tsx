'use client'
import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-11 rounded-md px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  /**
   * Ação em andamento: mostra spinner, bloqueia repetição e anuncia
   * `aria-busy` pro leitor de tela.
   *
   * Regra da casa (PRODUCT.md): nenhum toque fica sem resposta. Se o clique
   * dispara qualquer coisa que possa demorar — RPC, upload, navegação com
   * busca — ele precisa mudar de aparência imediatamente, senão o técnico
   * acha que o app travou e toca de novo.
   */
  loading?: boolean
  /** Texto exibido enquanto `loading` (default: mantém o label original). */
  loadingText?: string
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant, size, asChild = false, loading = false, loadingText, children, disabled, ...props },
    ref,
  ) => {
    const Comp = asChild ? Slot : 'button'
    // Com `asChild` o filho é um elemento arbitrário (ex.: <Link>); injetar
    // spinner ali quebraria o Slot, que exige um único filho.
    if (asChild) {
      return (
        <Comp
          className={cn(buttonVariants({ variant, size, className }))}
          ref={ref}
          {...props}
        >
          {children}
        </Comp>
      )
    }
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading && <Loader2 className="mr-2 h-4 w-4 shrink-0 animate-spin" aria-hidden />}
        {loading && loadingText ? loadingText : children}
      </Comp>
    )
  },
)
Button.displayName = 'Button'

export { buttonVariants }
