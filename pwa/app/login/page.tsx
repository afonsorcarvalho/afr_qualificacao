'use client'

import { useState, useRef, useEffect, Suspense } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Server, Database, User, Lock, Eye, EyeOff,
  ChevronRight, AlertCircle, CheckCircle2, Loader2,
  Wifi, WifiOff,
} from 'lucide-react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { odooClient } from '@/lib/odoo/client'
import { preloadSchemas } from '@/lib/odoo/schema'
import { useAuthStore } from '@/lib/store/authStore'
import { useSchemaStore } from '@/lib/store/schemaStore'
import { resetSessionCache } from '@/lib/store/resetSessionCache'
import { parseLoginParams, normalizeServerUrl } from '@/lib/utils/loginUrlParams'
import { getCompanyLogoUrl } from '@/lib/odoo/publicCompany'
import { clsx } from 'clsx'

type Step = 'server' | 'credentials'

interface ServerStatus {
  state: 'idle' | 'checking' | 'ok' | 'error'
  message?: string
  databases?: string[]
}

function LoginPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()
  const { setServerUrl, setDbName, setUser, setCompany, serverUrl: savedUrl, dbName: savedDb, addServerUrlToHistory, serverUrlHistory } = useAuthStore()

  const [step, setStep] = useState<Step>('server')
  const [url, setUrl] = useState(savedUrl || '')
  const [serverStatus, setServerStatus] = useState<ServerStatus>({ state: 'idle' })
  const [selectedDb, setSelectedDb] = useState(savedDb || '')
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [companyLogoUrl, setCompanyLogoUrl] = useState<string | null>(null)
  const [companyLogoFailed, setCompanyLogoFailed] = useState(false)

  const urlInputRef = useRef<HTMLInputElement>(null) as React.MutableRefObject<HTMLInputElement>
  const loginInputRef = useRef<HTMLInputElement>(null) as React.MutableRefObject<HTMLInputElement>

  useEffect(() => {
    urlInputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (step === 'credentials') {
      setTimeout(() => loginInputRef.current?.focus(), 300)
    }
  }, [step])

  function normalizeUrl(raw: string): string {
    return normalizeServerUrl(raw)
  }

  async function checkServer(rawUrl: string, preselectDb?: string | null): Promise<boolean> {
    const normalized = normalizeUrl(rawUrl)
    if (!normalized) return false

    setUrl(normalized)
    setServerStatus({ state: 'checking' })

    try {
      const dbs = await odooClient.getDatabases(normalized)
      if (dbs.length === 0) {
        setServerStatus({ state: 'error', message: 'Nenhum banco de dados encontrado neste servidor.' })
        return false
      }
      setServerStatus({ state: 'ok', databases: dbs })
      const targetDb = preselectDb && dbs.includes(preselectDb)
        ? preselectDb
        : (savedDb && dbs.includes(savedDb) ? savedDb : dbs[0])
      setSelectedDb(targetDb)
      setCompanyLogoFailed(false)
      setCompanyLogoUrl(getCompanyLogoUrl(normalized, targetDb))

      // Mudou de server? Limpa cache de empresa/ciclos/filtros/schema ANTES de persistir
      if (savedUrl && savedUrl !== normalized) {
        resetSessionCache(queryClient)
      }
      setServerUrl(normalized)
      addServerUrlToHistory(normalized)
      odooClient.reset()

      setTimeout(() => setStep('credentials'), 400)
      return true
    } catch {
      setServerStatus({
        state: 'error',
        message: 'Não foi possível conectar. Verifique a URL e se o servidor está acessível.',
      })
      return false
    }
  }

  async function handleCheckServer() {
    await checkServer(url)
  }

  // Recalcula logo quando url ou selectedDb mudam (ex.: troca de DB no dropdown)
  useEffect(() => {
    if (!url || !selectedDb) return
    setCompanyLogoFailed(false)
    setCompanyLogoUrl(getCompanyLogoUrl(url, selectedDb))
  }, [url, selectedDb])

  // Pré-preenchimento via URL: /login?server=...&db=... avança direto ao
  // passo de credenciais. Executa uma única vez no mount. Não limpa a URL
  // (mantém bookmark/reload e permite que o logout redirecione de volta).
  const prefillRan = useRef(false)
  useEffect(() => {
    if (prefillRan.current) return
    prefillRan.current = true
    const { server, db } = parseLoginParams(searchParams)
    if (!server) return
    checkServer(server, db)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!login || !password || !selectedDb) return

    setAuthError('')
    setAuthLoading(true)

    try {
      const { uid, name, company_id } = await odooClient.authenticate(
        normalizeUrl(url),
        selectedDb,
        login,
        password
      )

      // Trocou de DB dentro do mesmo servidor? Também é troca de "tenant" — limpa cache
      if (savedDb && savedDb !== selectedDb) {
        resetSessionCache(queryClient)
      }

      setDbName(selectedDb)
      setUser(uid, name)
      odooClient.reset()

      // Limpa schema de sessão anterior e recarrega para este usuário
      useSchemaStore.getState().clear()
      try {
        const { ok, failed } = await preloadSchemas()
        if (failed > 0) console.warn(`[schema] ${failed} models falharam ao carregar (${ok} ok)`)
      } catch (e) {
        console.warn('[schema] preloadSchemas falhou:', e)
      }

      // Busca logo + nome da empresa (não-bloqueante)
      if (company_id && typeof company_id === 'number') {
        odooClient
          .read<{ id: number; name: string; logo: string | false }>(
            'res.company', [company_id], ['id', 'name', 'logo']
          )
          .then((records) => {
            const c = records[0]
            if (c) {
              setCompany(c.id, c.name, c.logo ? String(c.logo) : null)
            }
          })
          .catch((e) => console.warn('[company] falha ao carregar:', e))
      }

      router.push('/tecnico/qualificacao')
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Erro ao autenticar')
    } finally {
      setAuthLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* Saíram daqui: 20 partículas animadas e três orbs neon desfocados.
          Custavam composição de camada em celular e não diziam nada sobre o
          servidor ao qual o técnico está se conectando. */}

      <motion.div
        initial={{ y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 240, damping: 24 }}
        className="w-full max-w-md relative z-10"
      >
        {/* Logo / título */}
        <motion.div
          className="text-center mb-8"
          initial={{ y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <motion.div
            className="inline-flex items-center justify-center w-20 h-20 rounded-lg border border-border bg-card mb-4 overflow-hidden p-2"
          >
            {companyLogoUrl && !companyLogoFailed ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={companyLogoUrl}
                alt="Logo da empresa"
                className="max-w-full max-h-full object-contain"
                onError={() => setCompanyLogoFailed(true)}
              />
            ) : (
              <Server size={28} className="text-muted-foreground" />
            )}
          </motion.div>

          <h1 className="text-2xl font-bold text-foreground">
            Labquali Connect
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            {step === 'server' ? 'Conecte ao seu servidor Odoo' : 'Entre com suas credenciais'}
          </p>
        </motion.div>

        {/* Card principal */}
        <div className="relative rounded-lg border border-border bg-card overflow-hidden">

          {/* Progress indicator */}
          <div className="flex items-center gap-0 px-6 pt-5 pb-0">
            <StepIndicator active={step === 'server'} done={step === 'credentials'} label="Servidor" icon={<Server size={12} />} />
            <div className="flex-1 h-px mx-2 bg-white/10 relative overflow-hidden">
              <motion.div
                className="absolute inset-y-0 left-0 bg-foreground/30"
                animate={{ width: step === 'credentials' ? '100%' : '0%' }}
                transition={{ duration: 0.5, ease: 'easeInOut' }}
              />
            </div>
            <StepIndicator active={step === 'credentials'} done={false} label="Login" icon={<User size={12} />} />
          </div>

          <div className="p-6">
            <AnimatePresence mode="wait">
              {step === 'server' ? (
                <motion.div
                  key="server"
                  initial={{ x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ type: 'spring', stiffness: 280, damping: 26 }}
                >
                  <ServerStep
                    url={url}
                    setUrl={setUrl}
                    status={serverStatus}
                    onCheck={handleCheckServer}
                    inputRef={urlInputRef}
                    history={serverUrlHistory}
                    onRemoveHistory={useAuthStore.getState().removeServerUrlFromHistory}
                  />
                </motion.div>
              ) : (
                <motion.div
                  key="credentials"
                  initial={{ x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ type: 'spring', stiffness: 280, damping: 26 }}
                >
                  <CredentialsStep
                    url={url}
                    databases={serverStatus.databases ?? []}
                    selectedDb={selectedDb}
                    setSelectedDb={setSelectedDb}
                    login={login}
                    setLogin={setLogin}
                    password={password}
                    setPassword={setPassword}
                    showPassword={showPassword}
                    setShowPassword={setShowPassword}
                    error={authError}
                    loading={authLoading}
                    onSubmit={handleLogin}
                    onBack={() => setStep('server')}
                    loginInputRef={loginInputRef}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <motion.p
          className="text-center text-xs text-white/20 mt-6"
          initial={false}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          Labquali · Comunicação via JSON-RPC
        </motion.p>
      </motion.div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-white/60" />
      </div>
    }>
      <LoginPageInner />
    </Suspense>
  )
}

// ─── Passo 1: Servidor ───────────────────────────────────────────────────────

function ServerStep({
  url, setUrl, status, onCheck, inputRef, history, onRemoveHistory,
}: {
  url: string
  setUrl: (v: string) => void
  status: ServerStatus
  onCheck: () => void
  inputRef: React.RefObject<HTMLInputElement>
  history: string[]
  onRemoveHistory: (url: string) => void
}) {
  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') onCheck()
  }

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-white/60 flex items-center gap-1.5">
          <Server size={11} className="text-muted-foreground" />
          URL do servidor
        </label>

        <div className="relative">
          <div className={clsx(
            'absolute -inset-0.5 rounded-xl blur transition-all duration-500',
            status.state === 'ok'
              ? 'bg-emerald-500/20'
              : status.state === 'error'
              ? 'bg-red-500/20'
              : 'bg-transparent group-focus-within:bg-foreground/10'
          )} />

          <div className="relative flex items-center">
            <input
              ref={inputRef}
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={handleKey}
              placeholder="https://mb.fitadigital.com.br"
              className={clsx(
                'w-full pl-4 pr-28 py-3 rounded-xl text-sm',
                'bg-white/[0.05] border text-white placeholder-white/25',
                'focus:outline-none focus:bg-white/[0.08] transition-all duration-200',
                status.state === 'ok'
                  ? 'border-emerald-500/40'
                  : status.state === 'error'
                  ? 'border-red-500/40'
                  : 'border-input focus:border-ring'
              )}
            />

            {/* Status icon */}
            <div className="absolute right-[82px]">
              <AnimatePresence mode="wait">
                {status.state === 'checking' && (
                  <motion.div key="check" initial={false} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <Loader2 size={14} className="text-foreground animate-spin" />
                  </motion.div>
                )}
                {status.state === 'ok' && (
                  <motion.div key="ok" initial={{ scale: 0.6 }} animate={{ scale: 1 }} exit={{ scale: 0.6 }}>
                    <CheckCircle2 size={14} className="text-emerald-400" />
                  </motion.div>
                )}
                {status.state === 'error' && (
                  <motion.div key="err" initial={{ scale: 0.6 }} animate={{ scale: 1 }} exit={{ scale: 0.6 }}>
                    <WifiOff size={14} className="text-red-400" />
                  </motion.div>
                )}
                {status.state === 'idle' && (
                  <motion.div key="idle" initial={false} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <Wifi size={14} className="text-white/20" />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <motion.button
              onClick={onCheck}
              disabled={!url || status.state === 'checking'}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
              className={clsx(
                'absolute right-2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg',
                'text-xs font-medium transition-all duration-200',
                'disabled:opacity-40 disabled:cursor-not-allowed',
                status.state === 'checking'
                  ? 'bg-muted text-muted-foreground'
                  : 'bg-primary text-primary-foreground hover:bg-primary/90'
              )}
            >
              {status.state === 'checking' ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <>Conectar <ChevronRight size={12} /></>
              )}
            </motion.button>
          </div>
        </div>

        <AnimatePresence>
          {status.message && (
            <motion.p
              initial={{ y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={clsx(
                'text-xs flex items-center gap-1.5',
                status.state === 'error' ? 'text-red-400' : 'text-emerald-400'
              )}
            >
              <AlertCircle size={11} />
              {status.message}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {history.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-white/30 font-medium">Histórico:</p>
          {history.map((h) => (
            <div key={h} className="flex items-center gap-1 group/item">
              <button
                onClick={() => setUrl(h)}
                className="flex-1 text-left text-xs text-white/40 hover:text-foreground transition-colors py-0.5 font-mono truncate"
              >
                {h}
              </button>
              <button
                onClick={() => onRemoveHistory(h)}
                className="opacity-0 group-hover/item:opacity-100 p-0.5 text-white/20 hover:text-white/60 transition-all flex-shrink-0"
                title="Remover"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Passo 2: Credenciais ────────────────────────────────────────────────────

function CredentialsStep({
  url, databases, selectedDb, setSelectedDb,
  login, setLogin, password, setPassword,
  showPassword, setShowPassword,
  error, loading, onSubmit, onBack,
  loginInputRef,
}: {
  url: string
  databases: string[]
  selectedDb: string
  setSelectedDb: (v: string) => void
  login: string
  setLogin: (v: string) => void
  password: string
  setPassword: (v: string) => void
  showPassword: boolean
  setShowPassword: (v: boolean) => void
  error: string
  loading: boolean
  onSubmit: (e: React.FormEvent) => void
  onBack: () => void
  loginInputRef: React.RefObject<HTMLInputElement>
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {/* Servidor conectado */}
      <motion.div
        initial={false}
        animate={{ opacity: 1 }}
        className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30"
      >
        <CheckCircle2 size={13} className="text-emerald-400 flex-shrink-0" />
        <span className="text-xs text-emerald-400 truncate font-mono">{url}</span>
        <button
          type="button"
          onClick={onBack}
          className="ml-auto text-xs text-white/30 hover:text-white transition-colors flex-shrink-0"
        >
          Trocar
        </button>
      </motion.div>

      {/* Banco de dados */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-white/60 flex items-center gap-1.5">
          <Database size={11} className="text-muted-foreground" />
          Banco de dados
          <span className="ml-auto text-white/25 font-normal">{databases.length} disponível{databases.length !== 1 ? 'is' : ''}</span>
        </label>

        <div className="relative">
          <Database size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <select
            value={selectedDb}
            onChange={(e) => setSelectedDb(e.target.value)}
            className={clsx(
              'w-full pl-9 pr-4 py-3 rounded-xl text-sm appearance-none cursor-pointer',
              'bg-white/[0.05] border border-white/10 text-white',
              'focus:outline-none focus:border-ring focus:bg-white/[0.08]',
              'transition-all duration-200'
            )}
          >
            {databases.map((db) => (
              <option key={db} value={db} className="bg-dark-800 text-white">
                {db}
              </option>
            ))}
          </select>
          {/* Custom chevron */}
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-white/30">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
      </div>

      {/* Login */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-white/60 flex items-center gap-1.5">
          <User size={11} className="text-muted-foreground" />
          Usuário
        </label>
        <div className="relative">
          <User size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            ref={loginInputRef}
            type="text"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            placeholder="admin"
            autoComplete="username"
            className={clsx(
              'w-full pl-9 pr-4 py-3 rounded-xl text-sm',
              'bg-white/[0.05] border border-white/10 text-white placeholder-white/25',
              'focus:outline-none focus:border-ring focus:bg-white/[0.08]',
              'transition-all duration-200'
            )}
          />
        </div>
      </div>

      {/* Senha */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-white/60 flex items-center gap-1.5">
          <Lock size={11} className="text-muted-foreground" />
          Senha
        </label>
        <div className="relative">
          <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            className={clsx(
              'w-full pl-9 pr-11 py-3 rounded-xl text-sm',
              'bg-white/[0.05] border text-white placeholder-white/25',
              'focus:outline-none focus:bg-white/[0.08] transition-all duration-200',
              error
                ? 'border-red-500/40 focus:border-red-500/60'
                : 'border-input focus:border-ring'
            )}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
          >
            {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>
      </div>

      {/* Erro de auth */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={false}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -6, height: 0 }}
            className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-red-500/10 border border-red-500/30"
          >
            <AlertCircle size={13} className="text-red-400 flex-shrink-0" />
            <span className="text-xs text-red-400">{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Botão entrar */}
      <motion.button
        type="submit"
        disabled={!login || !password || !selectedDb || loading}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.98 }}
        className={clsx(
          'w-full flex items-center justify-center gap-2 py-3 rounded-xl',
          'text-sm font-semibold transition-all duration-200',
          'disabled:opacity-40 disabled:cursor-not-allowed',
          'min-h-[48px] bg-primary text-primary-foreground',
          'hover:bg-primary/90',
        )}
      >
        {loading ? (
          <>
            <Loader2 size={15} className="animate-spin" />
            Autenticando...
          </>
        ) : (
          <>
            Entrar
            <ChevronRight size={15} />
          </>
        )}
      </motion.button>
    </form>
  )
}

// ─── Step Indicator ──────────────────────────────────────────────────────────

function StepIndicator({ active, done, label, icon }: {
  active: boolean; done: boolean; label: string; icon: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-1.5">
      <motion.div
        animate={{
          backgroundColor: done
            ? 'rgba(16,185,129,0.2)'
            : active
            ? 'rgba(248,250,252,0.15)'
            : 'rgba(255,255,255,0.04)',
          borderColor: done
            ? 'rgba(16,185,129,0.5)'
            : active
            ? 'rgba(248,250,252,0.4)'
            : 'rgba(255,255,255,0.1)',
        }}
        transition={{ duration: 0.3 }}
        className="w-6 h-6 rounded-full border flex items-center justify-center"
      >
        {done ? (
          <motion.div initial={{ scale: 0.6 }} animate={{ scale: 1 }}>
            <CheckCircle2 size={12} className="text-emerald-400" />
          </motion.div>
        ) : (
          <span className={clsx(active ? 'text-foreground' : 'text-white/30')}>{icon}</span>
        )}
      </motion.div>
      <span className={clsx('text-xs font-medium', active ? 'text-white/70' : done ? 'text-emerald-400' : 'text-white/25')}>
        {label}
      </span>
    </div>
  )
}

// ─── Partículas decorativas ──────────────────────────────────────────────────
