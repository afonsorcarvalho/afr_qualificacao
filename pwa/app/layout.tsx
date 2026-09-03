import type { Metadata } from 'next'
import localFont from 'next/font/local'
import { Toaster } from 'react-hot-toast'
import { QueryProvider } from '@/components/providers/QueryProvider'
import { ThemeProvider } from '@/components/providers/ThemeProvider'
import { ErrorReporter } from '@/components/providers/ErrorReporter'
import { AuthGuard } from '@/components/providers/AuthGuard'
import { PageTitle } from '@/components/providers/PageTitle'
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
            <div className="fixed inset-0 bg-[var(--bg-base)] bg-mesh-gradient -z-10" />
            <div
              className="fixed top-0 left-1/4 w-96 h-96 bg-neon-blue/5 rounded-full blur-3xl pointer-events-none -z-10 animate-float"
              aria-hidden
            />
            <div
              className="fixed bottom-1/4 right-1/4 w-80 h-80 bg-neon-purple/5 rounded-full blur-3xl pointer-events-none -z-10 animate-float"
              style={{ animationDelay: '-3s' }}
              aria-hidden
            />

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
