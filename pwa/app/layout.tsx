import type { Metadata } from 'next'
import localFont from 'next/font/local'
import { Toaster } from 'react-hot-toast'
import { QueryProvider } from '@/components/providers/QueryProvider'
import { ThemeProvider } from '@/components/providers/ThemeProvider'
import { ErrorReporter } from '@/components/providers/ErrorReporter'
import { AuthGuard } from '@/components/providers/AuthGuard'
import { PageTitle } from '@/components/providers/PageTitle'
import { ServiceWorkerRegister } from '@/components/providers/ServiceWorkerRegister'
import './globals.css'

const geistSans = localFont({
  src: './fonts/GeistVF.woff',
  variable: '--font-geist-sans',
  weight: '100 900',
})
const geistMono = localFont({
  src: './fonts/GeistMonoVF.woff',
  variable: '--font-geist-mono',
  weight: '100 900',
})

export const metadata: Metadata = {
  title: 'Qualificação · Técnico',
  description: 'Coleta de dados de qualificação em campo',
  manifest: '/manifest.json',
  themeColor: '#1f6feb',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <body
        className="antialiased min-h-screen bg-[var(--bg-base)] text-[var(--text-base)]"
        suppressHydrationWarning
      >
        <ThemeProvider>
          <QueryProvider>
            <ErrorReporter />
            <ServiceWorkerRegister />
            {/* O fundo era um mesh gradient com dois círculos neon flutuando
                (`animate-float`, `blur-3xl`). Enfeite puro, caro de compor em
                celular e contrário ao DESIGN.md: o fundo é chapado, a
                profundidade vem da escada tonal das superfícies. */}

            <PageTitle />
            <AuthGuard>{children}</AuthGuard>

            <Toaster
              position="bottom-right"
              toastOptions={{
                style: {
                  background: 'var(--toast-bg)',
                  color: 'var(--text-base)',
                  border: '1px solid var(--border-subtle)',
                  backdropFilter: 'blur(16px)',
                  borderRadius: '12px',
                  fontSize: '14px',
                },
                success: { iconTheme: { primary: '#10b981', secondary: 'white' } },
                error: { iconTheme: { primary: '#ec4899', secondary: 'white' } },
              }}
            />
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
