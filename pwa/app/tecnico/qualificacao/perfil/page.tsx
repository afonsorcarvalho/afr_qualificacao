'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft, User as UserIcon, Building2, Mail, LogOut, Sun, Moon, ChevronDown, Server, Database,
} from 'lucide-react'
import { useTheme } from 'next-themes'
import { useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/lib/store/authStore'
import { odooClient } from '@/lib/odoo/client'
import { resetSessionCache } from '@/lib/store/resetSessionCache'
import { fetchAvailableCompanies } from '@/lib/odoo/companies'
import { buildPostLogoutLoginPath } from '@/lib/utils/loginUrlParams'
import toast from 'react-hot-toast'

export default function PerfilPage() {
  const router = useRouter()
  const qc = useQueryClient()
  const { theme, setTheme } = useTheme()
  const {
    userName, userId, companyName, companyLogo, serverUrl, dbName,
    availableCompanies, selectedCompanyId,
    setAvailableCompanies, setSelectedCompany, logout,
  } = useAuthStore()

  const [email, setEmail] = useState<string | null>(null)
  const [companyOpen, setCompanyOpen] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch('/api/odoo/session-info')
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return
        if (typeof d?.username === 'string' && d.username) setEmail(d.username)
      })
      .catch(() => { /* ignora */ })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!userId || email) return
    odooClient
      .searchRead<{ email: string | false }>(
        'res.partner', [['user_ids', 'in', [userId]]], ['email'],
      )
      .then((rows) => {
        const e = rows?.[0]?.email
        if (typeof e === 'string' && e) setEmail(e)
      })
      .catch(() => { /* sem acesso → ignora */ })
  }, [userId, email])

  useEffect(() => {
    fetchAvailableCompanies()
      .then(setAvailableCompanies)
      .catch(() => { /* sem acesso → ignora */ })
  }, [setAvailableCompanies])

  const isDark = theme === 'dark'
  const selectedCompanyName = selectedCompanyId
    ? availableCompanies.find((c) => c.id === selectedCompanyId)?.name ?? companyName
    : null

  const handleLogout = async () => {
    setLoggingOut(true)
    try { await odooClient.logout() } catch { /* ignora */ }
    logout()
    odooClient.reset()
    resetSessionCache(qc)
    router.push(buildPostLogoutLoginPath(serverUrl, dbName))
  }

  const initials = userName
    ? userName.split(/\s+/).slice(0, 2).map((s) => s[0]?.toUpperCase() ?? '').join('') || '?'
    : '?'

  return (
    <div className="mx-auto w-full max-w-[880px] space-y-4">
      <Button variant="ghost" size="sm" onClick={() => router.back()}>
        <ArrowLeft className="mr-1 h-4 w-4" /> Voltar
        <kbd className="ml-2 hidden rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/90 sm:inline">Esc</kbd>
      </Button>

      <section className="rounded-2xl border border-border/70 bg-gradient-to-br from-violet-500/15 via-cyan-500/10 to-transparent p-5">
        <div className="flex items-center gap-3">
          {companyLogo ? (
            <img
              src={`data:image/png;base64,${companyLogo}`}
              alt={companyName ?? ''}
              className="h-14 w-14 shrink-0 rounded-2xl border border-border bg-white object-contain p-1"
            />
          ) : (
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-border bg-gradient-to-br from-violet-500 to-cyan-500 text-lg font-bold text-foreground">
              {initials}
            </div>
          )}
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-300/80">Técnico</p>
            <h1 className="truncate text-lg font-semibold text-foreground">{userName || 'Sem nome'}</h1>
            <p className="truncate text-xs text-muted-foreground">{companyName || 'Sem empresa'}</p>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border/70 bg-muted/20 p-3">
        <h2 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/90">Identidade</h2>
        <ul className="divide-y divide-border/40">
          <Row icon={<UserIcon className="h-4 w-4 text-violet-300" />} label="Nome" value={userName || '—'} />
          <Row icon={<Mail className="h-4 w-4 text-cyan-300" />} label="Email" value={email ?? '—'} />
          <Row icon={<Building2 className="h-4 w-4 text-emerald-300" />} label="Empresa" value={companyName || '—'} />
          <Row icon={<Server className="h-4 w-4 text-amber-300" />} label="Servidor" value={serverUrl || '—'} mono />
          <Row icon={<Database className="h-4 w-4 text-amber-300" />} label="Database" value={dbName || '—'} mono />
        </ul>
      </section>

      {availableCompanies.length > 1 && (
        <section className="rounded-xl border border-border/70 bg-muted/20 p-3">
          <h2 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/90">Empresa ativa</h2>
          <div className="relative">
            <button
              onClick={() => setCompanyOpen((v) => !v)}
              className="flex w-full items-center justify-between gap-2 rounded-lg border border-border/70 bg-muted/40 px-3 py-2 text-sm text-foreground/90 transition hover:border-border/60 hover:text-foreground"
            >
              <span className="truncate">{selectedCompanyName ?? 'Todas as empresas'}</span>
              <ChevronDown className={`h-4 w-4 shrink-0 transition-transform ${companyOpen ? 'rotate-180' : ''}`} />
            </button>
            {companyOpen && (
              <div className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-lg border border-border/70 bg-background shadow-2xl">
                <button
                  onClick={() => { setSelectedCompany(null); setCompanyOpen(false); toast.success('Empresa: todas') }}
                  className={`block w-full px-3 py-2 text-left text-sm ${selectedCompanyId === null ? 'bg-cyan-500/15 text-cyan-300' : 'text-foreground/80 hover:bg-muted/40'}`}
                >
                  Todas as empresas
                </button>
                {availableCompanies.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => { setSelectedCompany(c.id); setCompanyOpen(false); toast.success(`Empresa: ${c.name}`) }}
                    className={`block w-full px-3 py-2 text-left text-sm ${selectedCompanyId === c.id ? 'bg-cyan-500/15 text-cyan-300' : 'text-foreground/80 hover:bg-muted/40'}`}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      <section className="rounded-xl border border-border/70 bg-muted/20 p-3">
        <h2 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/90">Aparência</h2>
        <button
          onClick={() => setTheme(isDark ? 'light' : 'dark')}
          className="flex w-full items-center justify-between gap-3 rounded-lg border border-border/70 bg-muted/40 px-3 py-2 text-sm text-foreground/90 transition hover:border-border/60 hover:text-foreground"
        >
          <span className="inline-flex items-center gap-2">
            {isDark ? <Moon className="h-4 w-4 text-cyan-300" /> : <Sun className="h-4 w-4 text-amber-300" />}
            Tema {isDark ? 'escuro' : 'claro'}
          </span>
          <span className="text-[11px] text-muted-foreground/80">Trocar</span>
        </button>
      </section>

      <Button
        variant="outline"
        className="min-h-[48px] w-full border-red-500/40 text-red-600 hover:bg-red-500/10 dark:text-red-400"
        onClick={handleLogout}
        loading={loggingOut}
        loadingText="Saindo..."
      >
        <LogOut className="mr-2 h-4 w-4" aria-hidden />
        Sair
      </Button>
    </div>
  )
}

function Row({
  icon, label, value, mono,
}: {
  icon: React.ReactNode
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <li className="flex items-center gap-3 py-2">
      <div className="shrink-0">{icon}</div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground/80">{label}</p>
        <p className={`truncate text-sm text-foreground ${mono ? 'font-mono text-xs' : ''}`}>{value}</p>
      </div>
    </li>
  )
}
