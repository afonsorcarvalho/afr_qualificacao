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
import { destinoSeguro } from '@/lib/navegacao'
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

    // `list_db = False` é a configuração normal de um Odoo de produção: ele
    // recusa listar bancos. Recusa de listagem não é servidor fora do ar, e
    // tratá-la como tal foi o que impediu a publicação no labquali em
    // 2026-09-06. Quando a lista não vem, perguntamos de outro jeito se o
    // servidor responde e deixamos o técnico digitar o banco — que é como o
    // próprio Odoo se comporta nesse modo.
    let dbs: string[] = []
    try {
      dbs = await odooClient.getDatabases(normalized)
    } catch {
      dbs = []
    }

    if (dbs.length === 0) {
      const responde = await odooClient.pingServer(normalized)
      if (!responde) {
        setServerStatus({
          state: 'error',
          message: 'Não foi possível conectar. Verifique a URL e se o servidor está acessível.',
        })
        return false
      }
      setServerStatus({ state: 'ok', databases: [] })
      // Sem lista, o `?db=` da URL é a única dica automática do nome — e o
      // caminho manual (clicar em "Conectar") não recebe `preselectDb`, então
      // ele é lido aqui também. É o que faz o link de suporte
      // `/login?server=...&db=...` valer alguma coisa nesse modo.
      const dbDaUrl = parseLoginParams(searchParams).db
      setSelectedDb(preselectDb || dbDaUrl || savedDb || '')
      setCompanyLogoFailed(false)
      setCompanyLogoUrl(null)
      if (savedUrl && savedUrl !== normalized) resetSessionCache(queryClient)
      setServerUrl(normalized)
      addServerUrlToHistory(normalized)
      odooClient.reset()
      setTimeout(() => setStep('credentials'), 400)
      return true
    }

    try {
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

      // `replace`: entrar não deixa o formulário de login no histórico.
      // Com `push`, o botão voltar levava o técnico já autenticado de volta
      // à tela de credenciais. Mesmo defeito do fechamento de relatório.
      // `destinoSeguro` devolve o técnico ao deep link que o trouxe ao login
      // (?next=...), recusando qualquer destino que não seja caminho interno.
      router.replace(destinoSeguro(searchParams.get('next')))
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
            <div className="flex-1 h-px mx-2 bg-muted relative overflow-hidden">
              <motion.div
                className="absolute inset-y-0 left-0 bg-ok"
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
          className="text-center text-xs text-muted-foreground mt-6"
          initial={false}
          // Era branco absoluto a 20% de opacidade e passou por um estágio
          // intermediário de `animate={{ opacity: 0.6 }}` — reduzir a tinta
          // pelo Framer em vez de pela classe, para escapar da catraca sem
          // mudar o brilho no escuro. A revisão final derrubou a saída
          // inteira: a tinta secundária a 60% de opacidade compõe IDÊNTICO
          // à mesma tinta com a opacidade embutida na cor (2,80:1 no claro,
          // 3,74:1 no escuro), então trocar o mecanismo só escondia o
          // defeito da guarda. Para TEXTO não existe terceiro nível de
          // tinta (DESIGN.md, "Tinta Apagada" proibida em texto legível):
          // fica `text-muted-foreground` cheio. O `animate` continua aqui só
          // porque estilo inline vence classe — com `initial={false}` logo
          // acima NÃO há animação de entrada nenhuma (o Framer parte do
          // estado final), então isto é um valor fixo de opacidade 1, não um
          // fade. Apagar as duas linhas daria o mesmo resultado visual;
          // ficam para deixar explícito que a opacidade deste elemento é
          // deliberadamente cheia, e que reduzi-la aqui volta a burlar a
          // catraca (que só lê `className`).
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
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
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
        <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
          <Server size={11} className="text-muted-foreground" />
          URL do servidor
        </label>

        <div className="relative">
          <div className={clsx(
            'absolute -inset-0.5 rounded-xl blur transition-all duration-500',
            status.state === 'ok'
              ? 'bg-ok-surface'
              : status.state === 'error'
              ? 'bg-danger-surface'
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
                'bg-surface-raised border text-foreground placeholder:text-muted-foreground',
                'focus:outline-none focus:ring-2 focus:ring-ring transition-all duration-200',
                status.state === 'ok'
                  ? 'border-ok/40'
                  : status.state === 'error'
                  ? 'border-danger/40'
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
                    <CheckCircle2 size={14} className="text-ok" />
                  </motion.div>
                )}
                {status.state === 'error' && (
                  <motion.div key="err" initial={{ scale: 0.6 }} animate={{ scale: 1 }} exit={{ scale: 0.6 }}>
                    <WifiOff size={14} className="text-danger" />
                  </motion.div>
                )}
                {status.state === 'idle' && (
                  <motion.div key="idle" initial={false} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <Wifi size={14} className="text-muted-foreground" />
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
                <>
                  <Loader2 size={12} className="animate-spin" aria-hidden />
                  Conectando...
                </>
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
                status.state === 'error' ? 'text-danger' : 'text-ok'
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
          <p className="text-xs text-muted-foreground font-medium">Histórico:</p>
          {history.map((h) => (
            <div key={h} className="flex items-center gap-1 group/item">
              <button
                onClick={() => setUrl(h)}
                className="flex-1 text-left text-xs text-muted-foreground hover:text-foreground transition-colors py-0.5 font-mono truncate"
              >
                {h}
              </button>
              <button
                onClick={() => onRemoveHistory(h)}
                // `hover:text-foreground`, não `hover:text-muted-foreground`:
                // um fix round anterior igualou repouso e hover para matar um
                // "hover mais claro que o baseline" no escuro, e o preço foi a
                // affordance inteira (o botão não responde ao ponteiro). Hover
                // marginalmente mais claro que o baseline escuro não é
                // regressão que valha trocar por affordance perdida.
                className="opacity-0 group-hover/item:opacity-100 p-0.5 text-muted-foreground hover:text-foreground transition-all flex-shrink-0"
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
        className="flex items-center gap-2 px-3 py-2 rounded-xl bg-ok-surface border border-ok/30"
      >
        <CheckCircle2 size={13} className="text-ok flex-shrink-0" />
        <span className="text-xs text-ok truncate font-mono">{url}</span>
        <button
          type="button"
          onClick={onBack}
          className="ml-auto text-xs text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
        >
          Trocar
        </button>
      </motion.div>

      {/* Banco de dados */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
          <Database size={11} className="text-muted-foreground" />
          Banco de dados
          {/* Era branco a 25% de opacidade, e por um tempo tinta secundária
              reduzida a 60% pelo elemento — que compõe idêntico à mesma
              tinta com a opacidade embutida na cor (2,80:1 no claro), o
              padrão que a catraca proíbe. Texto não ganha terceiro nível: a
              distinção de peso contra o rótulo fica por conta de
              `font-normal` (o rótulo é `font-medium`), não da opacidade. */}
          <span className="ml-auto text-muted-foreground font-normal">
            {databases.length > 0
              ? `${databases.length} disponíve${databases.length !== 1 ? 'is' : 'l'}`
              : 'digite o nome'}
          </span>
        </label>

        {/* Servidor com `list_db = False` (o normal em produção) não entrega a
            lista: o Odoo recusa `/web/database/list`. Aí o banco vira campo
            digitável, como no próprio Odoo nesse modo — em vez de a tela
            declarar o servidor inacessível, que foi o que travou a publicação
            no labquali em 2026-09-06. */}
        {databases.length === 0 ? (
          <div className="relative">
            <Database size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <input
              type="text"
              name="db"
              value={selectedDb}
              onChange={(e) => setSelectedDb(e.target.value)}
              placeholder="nome do banco"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              className={clsx(
                'w-full pl-9 pr-4 py-3 rounded-xl text-sm',
                'bg-surface-raised border border-border text-foreground placeholder:text-muted-foreground',
                'focus:outline-none focus:border-ring',
                'transition-all duration-200'
              )}
            />
          </div>
        ) : (
        <div className="relative">
          <Database size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <select
            value={selectedDb}
            onChange={(e) => setSelectedDb(e.target.value)}
            className={clsx(
              'w-full pl-9 pr-4 py-3 rounded-xl text-sm appearance-none cursor-pointer',
              'bg-surface-raised border border-border text-foreground',
              'focus:outline-none focus:border-ring',
              'transition-all duration-200'
            )}
          >
            {databases.map((db) => (
              <option key={db} value={db}>
                {db}
              </option>
            ))}
          </select>
          {/* Custom chevron */}
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
        )}
      </div>

      {/* Login */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
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
              'bg-surface-raised border border-border text-foreground placeholder:text-muted-foreground',
              'focus:outline-none focus:border-ring',
              'transition-all duration-200'
            )}
          />
        </div>
      </div>

      {/* Senha */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
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
              'bg-surface-raised border text-foreground placeholder:text-muted-foreground',
              'focus:outline-none transition-all duration-200',
              error
                ? 'border-danger/40 focus:border-danger/60'
                : 'border-input focus:border-ring'
            )}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            // Mesmo raciocínio do botão de remover histórico acima: repouso e
            // hover na mesma cor é affordance morta no botão de mostrar senha.
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
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
            className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-danger-surface border border-danger/30"
          >
            <AlertCircle size={13} className="text-danger flex-shrink-0" />
            <span className="text-xs text-danger">{error}</span>
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
      {/* Era `animate={{ backgroundColor, borderColor }}` com branco
          translúcido em RGB literal fixo (valor exato documentado em
          temaTokens.test.ts): branco quase-transparente sobre cartão navy
          funcionava no escuro, mas sobre cartão branco no claro é o mesmo
          círculo somando branco com branco — o badge do passo ativo
          desaparecia por completo. Framer Motion não resolve
          `hsl(var(--x))` para interpolar cor (perderia a animação), então a
          troca é por classe: `text-foreground` é a tinta escura no claro e
          branca no escuro — aplicada como fundo/borda em baixa opacidade,
          ela clareia sobre navy e escurece sobre branco, nos dois casos
          ficando visível. */}
      <motion.div
        className={clsx(
          'w-6 h-6 rounded-full border flex items-center justify-center transition-colors duration-300',
          done
            ? 'bg-ok-surface border-ok/50'
            : active
            ? 'bg-foreground/10 border-foreground/30'
            : 'bg-foreground/5 border-foreground/10'
        )}
      >
        {done ? (
          <motion.div initial={{ scale: 0.6 }} animate={{ scale: 1 }}>
            <CheckCircle2 size={12} className="text-ok" />
          </motion.div>
        ) : (
          <span className={clsx(active ? 'text-foreground' : 'text-muted-foreground')}>{icon}</span>
        )}
      </motion.div>
      {/* Esta é a tela do bug original (o modo claro perdia o texto do
          login). Era branco a 70% (ativo) / 25% (futuro) de opacidade; a
          tradução mecânica mandou os dois para a tinta secundária e a
          distinção ativo/futuro foi reaberta reduzindo o futuro a 60% de
          opacidade — que compõe idêntico à mesma tinta com a opacidade
          embutida na cor (2,80:1 no claro), exatamente o que a catraca
          proíbe. A distinção volta por PESO de
          fonte (`font-medium` no ativo/concluído, `font-normal` no futuro),
          não por tinta: o rótulo do passo futuro é informação que o técnico
          precisa ler para saber o que vem depois. */}
      <span className={clsx('text-xs', active ? 'font-medium text-muted-foreground' : done ? 'font-medium text-ok' : 'font-normal text-muted-foreground')}>
        {label}
      </span>
    </div>
  )
}

// ─── Partículas decorativas ──────────────────────────────────────────────────
