import axios, { AxiosInstance } from 'axios'

interface JsonRpcResponse<T = unknown> {
  jsonrpc: '2.0'
  id: number
  result?: T
  error?: {
    code: number
    message: string
    data: {
      name: string
      debug: string
      message: string
      arguments: unknown[]
      exception_type: string
    }
  }
}

export class OdooError extends Error {
  constructor(
    message: string,
    public readonly code: number,
    public readonly odooDebug?: string
  ) {
    super(message)
    this.name = 'OdooError'
  }
}

export class OdooSessionError extends OdooError {
  constructor() {
    super('Sessão expirada ou não autenticado', 401)
    this.name = 'OdooSessionError'
  }
}

let requestIdCounter = 1

function nextId() {
  return requestIdCounter++
}

function rpcPayload(params: Record<string, unknown>) {
  return { jsonrpc: '2.0', method: 'call', id: nextId(), params }
}

const PROXY_BASE = '/api/odoo'

function normalizeTarget(raw: string): string {
  let u = raw.trim().replace(/\/+$/, '')
  if (u && !/^https?:\/\//i.test(u)) u = 'https://' + u
  return u
}

class OdooClient {
  private _axios: AxiosInstance | null = null
  private _target = ''

  private get http(): AxiosInstance {
    // Lê a URL do store em runtime para suportar URL dinâmica
    const target = this.resolveTarget()
    if (!this._axios || target !== this._target) {
      this._target = target
      this._axios = axios.create({
        baseURL: PROXY_BASE,
        withCredentials: true,
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-Odoo-Target': target,
        },
      })

      this._axios.interceptors.response.use(
        (r) => r,
        (error) => {
          if (error.response?.status === 401) {
            if (typeof window !== 'undefined') window.location.href = '/login'
            throw new OdooSessionError()
          }
          return Promise.reject(error)
        }
      )
    }
    return this._axios
  }

  private resolveTarget(): string {
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem('auth-store')
        if (raw) {
          const parsed = JSON.parse(raw)
          const url = parsed?.state?.serverUrl
          if (url) return normalizeTarget(url)
        }
      } catch {
        // ignora erros de parse
      }
    }
    return normalizeTarget('http://localhost:8069')
  }

  // Força recriação do cliente (usado após troca de servidor)
  reset() {
    this._axios = null
    this._target = ''
  }

  // Lista bancos de dados disponíveis no servidor (via proxy)
  async getDatabases(serverUrl: string): Promise<string[]> {
    const target = normalizeTarget(serverUrl)
    const response = await axios.post<JsonRpcResponse<string[]>>(
      `${PROXY_BASE}/web/database/list`,
      rpcPayload({}),
      {
        timeout: 15000,
        withCredentials: true,
        headers: { 'Content-Type': 'application/json', 'X-Odoo-Target': target },
      }
    )
    if (response.data.error) {
      throw new OdooError(
        response.data.error.data?.message || response.data.error.message || 'Não foi possível listar os bancos',
        500
      )
    }
    return response.data.result ?? []
  }

  async authenticate(
    serverUrl: string,
    db: string,
    login: string,
    password: string
  ): Promise<{ uid: number; name: string; company_id: number | false }> {
    const target = normalizeTarget(serverUrl)
    const response = await axios.post<JsonRpcResponse<{
      uid: number
      name: string
      session_id: string
      company_id: number | false
    }>>(
      `${PROXY_BASE}/web/session/authenticate`,
      rpcPayload({ db, login, password }),
      {
        withCredentials: true,
        timeout: 15000,
        headers: { 'Content-Type': 'application/json', 'X-Odoo-Target': target },
      }
    )

    const data = response.data
    if (data.error || !data.result?.uid) {
      throw new OdooError('Login ou senha incorretos', 403)
    }
    return data.result
  }

  async logout(): Promise<void> {
    await this.http.post('/web/session/destroy', rpcPayload({}))
  }

  async getSession(): Promise<{ uid: number | false; name: string }> {
    const r = await this.http.post<JsonRpcResponse<{ uid: number | false; name: string }>>(
      '/web/session/get_session_info',
      rpcPayload({})
    )
    return r.data.result as { uid: number | false; name: string }
  }

  async callKw<T = unknown>(
    model: string,
    method: string,
    args: unknown[],
    kwargs: Record<string, unknown> = {}
  ): Promise<T> {
    const payload = rpcPayload({
      model,
      method,
      args,
      kwargs: { context: { lang: 'pt_BR' }, ...kwargs },
    })

    const response = await this.http.post<JsonRpcResponse<T>>(
      '/web/dataset/call_kw',
      payload
    )

    if (response.data.error) {
      const errData = response.data.error.data
      if (
        errData?.exception_type === 'access_denied' ||
        errData?.name === 'odoo.exceptions.AccessDenied'
      ) {
        throw new OdooSessionError()
      }
      throw new OdooError(
        errData?.message || response.data.error.message,
        response.data.error.code,
        errData?.debug
      )
    }

    return response.data.result as T
  }

  async searchRead<T>(
    model: string,
    domain: unknown[],
    fields: string[],
    options: { limit?: number; offset?: number; order?: string; context?: Record<string, unknown> } = {}
  ): Promise<T[]> {
    return this.callKw<T[]>(model, 'search_read', [domain], {
      fields,
      limit: options.limit ?? 80,
      offset: options.offset ?? 0,
      order: options.order ?? 'name asc',
      context: options.context,
    })
  }

  async searchCount(model: string, domain: unknown[]): Promise<number> {
    return this.callKw<number>(model, 'search_count', [domain])
  }

  async read<T>(model: string, ids: number[], fields: string[]): Promise<T[]> {
    return this.callKw<T[]>(model, 'read', [ids], { fields })
  }

  async create(model: string, values: Record<string, unknown>): Promise<number> {
    return this.callKw<number>(model, 'create', [values])
  }

  async write(model: string, ids: number[], values: Record<string, unknown>): Promise<boolean> {
    return this.callKw<boolean>(model, 'write', [ids, values])
  }

  async unlink(model: string, ids: number[]): Promise<boolean> {
    return this.callKw<boolean>(model, 'unlink', [ids])
  }

  /**
   * Baixa um report QWeb-PDF do Odoo.
   * Endpoint: GET /report/pdf/<report_name>/<doc_ids>
   */
  async downloadReport(reportName: string, ids: number[], filename: string): Promise<void> {
    const idList = ids.join(',')
    await this.downloadBinary(`/report/pdf/${encodeURIComponent(reportName)}/${idList}`, filename)
  }

  /**
   * Retorna o PDF de um report como Blob (para visualização inline no PdfViewerModal).
   */
  async fetchReportPdf(reportName: string, ids: number[]): Promise<{ blob: Blob; filename?: string }> {
    const idList = ids.join(',')
    return this.fetchBinary(`/report/pdf/${encodeURIComponent(reportName)}/${idList}`)
  }

  /**
   * Renderiza o Laudo de Liberação restrito aos materiais selecionados.
   *
   * Usa o método `get_laudo_public_url` no backend (já existente) para obter uma
   * URL assinada (HMAC) e depois baixa o PDF via rota pública existente
   * `/laudo/liberacao/public/<ciclo_id>?token=...&materials=...`.
   * Não requer novo controller no Odoo.
   */
  async fetchLaudoPdf(cycleId: number, materialLineIds: number[]): Promise<{ blob: Blob; filename?: string }> {
    const url = await this.callKw<string>(
      'afr.supervisorio.ciclos',
      'get_laudo_public_url',
      [[cycleId]],
      { material_line_ids: materialLineIds }
    )
    // Extrai apenas o path + query (descarta scheme/host — fetch passa pelo proxy interno).
    let path: string
    try {
      const u = new URL(url)
      path = `${u.pathname}${u.search}`
    } catch {
      path = url.startsWith('/') ? url : `/${url}`
    }
    return this.fetchBinary(path)
  }

  /**
   * Busca qualquer endpoint binário via proxy como Blob (para visualização inline).
   * Não dispara download.
   */
  async fetchBinary(
    path: string,
    options?: { method?: 'GET' | 'POST'; body?: BodyInit; contentType?: string }
  ): Promise<{ blob: Blob; filename?: string }> {
    if (typeof window === 'undefined') throw new Error('fetchBinary só funciona no navegador')
    const target = this.resolveTarget()
    const url = `${PROXY_BASE}${path.startsWith('/') ? path : '/' + path}`
    const headers: Record<string, string> = { 'X-Odoo-Target': target }
    if (options?.contentType) headers['Content-Type'] = options.contentType
    const res = await fetch(url, {
      method: options?.method ?? 'GET',
      credentials: 'include',
      headers,
      body: options?.body,
    })
    if (!res.ok) {
      // tenta extrair mensagem útil do servidor
      let detail = ''
      try {
        const ct = res.headers.get('content-type') || ''
        const text = await res.text()
        if (ct.includes('application/json')) {
          const parsed = JSON.parse(text) as { error?: { data?: { message?: string; arguments?: string[] }; message?: string } }
          detail =
            parsed?.error?.data?.message ||
            parsed?.error?.data?.arguments?.[0] ||
            parsed?.error?.message ||
            ''
        } else if (text) {
          // Odoo retorna às vezes HTML — extrai <h1> ou primeira linha não vazia
          const h1 = /<h1[^>]*>([^<]+)<\/h1>/i.exec(text)?.[1]
          const pre = /<pre[^>]*>([\s\S]{0,400}?)<\/pre>/i.exec(text)?.[1]
          detail = (h1 || pre || text.split('\n').find((l) => l.trim()) || '').trim().slice(0, 300)
        }
      } catch { /* ignore */ }
      const msg = detail
        ? `Falha ao gerar (HTTP ${res.status}): ${detail}`
        : `Falha ao buscar binário (HTTP ${res.status})`
      throw new OdooError(msg, res.status)
    }
    const suggested = /filename\*?=(?:UTF-8'')?"?([^";\n]+)"?/i.exec(res.headers.get('content-disposition') ?? '')?.[1]
    const filename = suggested ? decodeURIComponent(suggested) : undefined
    const blob = await res.blob()
    return { blob, filename }
  }

  /**
   * Busca o conteúdo de um endpoint de texto via proxy (TXT/CSV/etc.)
   * Não dispara download — retorna o conteúdo como string.
   */
  async fetchText(path: string): Promise<{ content: string; filename?: string }> {
    if (typeof window === 'undefined') throw new Error('fetchText só funciona no navegador')
    const target = this.resolveTarget()
    const url = `${PROXY_BASE}${path.startsWith('/') ? path : '/' + path}`
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: { 'X-Odoo-Target': target },
    })
    if (!res.ok) throw new OdooError(`Falha ao buscar texto (HTTP ${res.status})`, res.status)

    const suggested = /filename\*?=(?:UTF-8'')?"?([^";\n]+)"?/i.exec(res.headers.get('content-disposition') ?? '')?.[1]
    const filename = suggested ? decodeURIComponent(suggested) : undefined
    const content = await res.text()
    return { content, filename }
  }

  /**
   * Baixa qualquer endpoint binário do Odoo pelo proxy.
   * @param path  caminho iniciando com "/" (ex: "/web/content/...")
   * @param filename nome sugerido (fallback se o servidor não enviar Content-Disposition)
   */
  async downloadBinary(path: string, filename: string): Promise<void> {
    if (typeof window === 'undefined') throw new Error('downloadBinary só funciona no navegador')
    const target = this.resolveTarget()
    const url = `${PROXY_BASE}${path.startsWith('/') ? path : '/' + path}`

    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: { 'X-Odoo-Target': target },
    })
    if (!res.ok) throw new OdooError(`Falha no download (HTTP ${res.status})`, res.status)

    const blob = await res.blob()
    const suggested = /filename\*?=(?:UTF-8'')?"?([^";\n]+)"?/i.exec(res.headers.get('content-disposition') ?? '')?.[1]
    const finalName = suggested ? decodeURIComponent(suggested) : filename

    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = finalName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(objectUrl)
  }
}

export const odooClient = new OdooClient()
export default odooClient
