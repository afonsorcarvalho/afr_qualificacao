# PWA Técnico dentro do addon — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover o PWA Técnico de campo do repositório `frontend_odoo` (branch `tecnico-qualif-pwa`) para `addons/afr_qualificacao/pwa/`, como app Next.js standalone versionado junto do backend Odoo.

**Architecture:** Cópia seletiva do app técnico mais o shell mínimo que ele importa (cliente RPC, proxy `/api/odoo`, login, providers, 4 componentes de UI). O conjunto completo de arquivos é determinado pelo compilador — copia-se a semente, roda-se `tsc --noEmit`, e cada import não resolvido nomeia a próxima peça. Nenhum histórico é replantado: é um import limpo citando o commit de origem.

**Tech Stack:** Next.js 14.2.35 (App Router, `output: 'standalone'`), React 18, TypeScript 5, TailwindCSS 3, `next-pwa` 5.6, TanStack Query 5, Zustand 4, Vitest 4 + happy-dom, axios. Backend consumido: Odoo 16 (`afr_qualificacao` 16.0.7.0.0) via JSON-RPC pelo proxy `/api/odoo`.

**Spec:** `docs/superpowers/specs/2026-09-02-pwa-tecnico-no-addon-design.md` (commit `7f6844d`)

## Global Constraints

- **Origem (SRC):** `/home/afonso/docker/frontend_odoo/.worktrees/tecnico-qualif-pwa` — worktree do branch `tecnico-qualif-pwa` @ `4cd26dd`. A fonte é o **filesystem do worktree**, não o commit: há 3 alterações não commitadas que são exatamente as adaptações "técnico-first" e precisam viajar (`app/page.tsx` redireciona p/ `/tecnico/qualificacao` em vez de renderizar o dashboard; `app/login/page.tsx:176` redireciona p/ `/tecnico/qualificacao` em vez de `/ciclos`; `package.json` usa `-p 3010`).
- **Destino (DST):** `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa`
- **Nada é apagado na origem.** O worktree e `origin/tecnico-qualif-pwa` ficam intactos até o gate da Task 5 passar. `main` do `frontend_odoo` não é tocada em nenhuma hipótese.
- **`__manifest__.py` NÃO é bumpado** por nenhuma task deste plano. Mudança só de PWA não bumpa versão do módulo Odoo; a versão do front vive no `package.json` do `pwa/`.
- **Branch de trabalho:** `feat/pwa-tecnico-no-addon`, criado a partir de `main` **dentro do submodule** `addons/afr_qualificacao/`. Merge em `main` só na Task 6.
- **Commits:** sempre com `cwd` = `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao` (submodule tem `.git` próprio), via o subagente `git-commit-push` (model haiku), nunca `git commit` direto no main loop. `git add` apenas os paths da task — o working tree do submodule tem untracked alheios (`.vscode/`, `__pycache__/`, outros `docs/superpowers/*`) que **não** podem ser staged.
- **Sem push até a Task 6.** Os commits das Tasks 1–5 ficam locais no branch.
- **Rotas preservadas:** o app continua servindo em `/tecnico/qualificacao/**`. Não renomear rotas — o `F7_0_TEST_CHECKLIST.md`, o `manifest.json` (`start_url`) e o `localStorage` dos aparelhos dependem delas.
- **`.env.local` não migra** (é gitignored e contém a `GROQ_API_KEY`). A chave está comprometida e deve ser rotacionada antes de ser reusada.
- **Medições de controle, tiradas em 2026-09-02 antes de qualquer arquivo ser copiado** (referência para as comparações das tasks): boot do container `odoo_engenapp-web-qualificacao-1` até `HTTP service (werkzeug) running` = **4 segundos**; `npx tsc --noEmit` na origem (`SRC`) = **limpo**, com as 7 suítes de `app/tecnico/qualificacao/__tests__/` presentes na árvore.

## File Structure

Arquivos criados em `addons/afr_qualificacao/pwa/`:

| Path | Responsabilidade |
|---|---|
| `app/tecnico/qualificacao/**` | O app do técnico: 4 páginas, `historico/`, `perfil/`, 13 `_components/`, 7 suítes em `__tests__/`, `layout.tsx` (header + bottom nav) |
| `app/login/page.tsx` | Autenticação: URL do Odoo, db, credenciais, logo público da empresa, preload de schema |
| `app/page.tsx` | Raiz — `redirect('/tecnico/qualificacao')` |
| `app/layout.tsx` | Root layout enxuto: providers, fontes, toaster. Sem `AppShell`/`AppSidebar` |
| `app/api/odoo/**` | Proxy JSON-RPC para o Odoo (contorna CORS, propaga `session_id`) |
| `app/api/groq/**` | Endpoints do assistente IA: resumo, revisão, status, transcrição |
| `app/api/debug-log/route.ts` | Sink de erros do `ErrorReporter` |
| `components/providers/**` | `QueryProvider`, `ThemeProvider`, `AuthGuard`, `ErrorReporter`, `PageTitle` |
| `components/ui/{GlassCard,NeonBadge,button,PdfViewerModal}.tsx` | Os 4 componentes de UI que o técnico consome |
| `lib/odoo/**` | `client` (RPC), `tecnico` (chamadas do domínio), `companies`, `publicCompany`, `schema` |
| `lib/store/**` | `authStore`, `schemaStore`, `tecnicoSettings`, `resetSessionCache` |
| `lib/hooks/**` | `useTecnicoQualif`, `useGroqStatus`, `useReviewCache`, `useReviewDismissed` |
| `lib/groq/**`, `lib/tecnico/**`, `lib/utils/**` | Cliente Groq + prompts, contexto do resumo, `cn()` e parsing de query string do login |
| `tests/setup.ts`, `tests/reset-session-cache.test.ts` | Setup do Vitest e a suíte do reset de sessão |
| Configs de raiz | `package.json`, `package-lock.json`, `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts`, `postcss.config.mjs`, `vitest.config.ts`, `.eslintrc.json`, `.gitignore`, `.dockerignore`, `.env.example`, `Dockerfile`, `docker-compose.yml`, `README.md` |

Arquivos modificados fora do `pwa/`: nenhum no addon. No `frontend_odoo` (Task 5): só `TODO.md`.

---

### Task 1: Árvore do PWA compila

Copia a semente, faz os dois ajustes que impedem o fecho de explodir (root layout e `resetSessionCache`), e itera `tsc` até limpo.

**Files:**
- Create: toda a árvore `addons/afr_qualificacao/pwa/` (ver File Structure)
- Modify (após a cópia): `pwa/app/layout.tsx`, `pwa/lib/store/resetSessionCache.ts`, `pwa/vitest.config.ts`, `pwa/docker-compose.yml`
- Test: `pwa/tests/reset-session-cache.test.ts`

**Interfaces:**
- Consumes: nada (primeira task)
- Produces: a árvore `pwa/` com `tsc --noEmit` limpo. `resetSessionCache(queryClient?: QueryClient | null): void` passa a limpar apenas `schemaStore` + `authStore` + React Query (sem `contactsStore`/`ciclosStore`). Root layout exporta `RootLayout({ children }: { children: React.ReactNode })` sem `AppShell`.

- [ ] **Step 1: Criar o branch de trabalho no submodule**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git checkout main
git status --short          # confirmar que nenhum arquivo TRACKED está modificado
git checkout -b feat/pwa-tecnico-no-addon
```

Esperado: `Switched to a new branch 'feat/pwa-tecnico-no-addon'`. Untracked (`.vscode/`, `__pycache__/`) podem existir — não interferem.

- [ ] **Step 2: Copiar a semente**

```bash
SRC=/home/afonso/docker/frontend_odoo/.worktrees/tecnico-qualif-pwa
DST=/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa

mkdir -p "$DST"/{app/api,lib/{odoo,groq,hooks,store,tecnico,utils},components/ui,public,tests}

# --- app ---
cp -a "$SRC/app/tecnico"        "$DST/app/"
cp -a "$SRC/app/login"          "$DST/app/"
cp -a "$SRC/app/fonts"          "$DST/app/"
cp -a "$SRC/app/api/odoo"       "$DST/app/api/"
cp -a "$SRC/app/api/groq"       "$DST/app/api/"
cp -a "$SRC/app/api/debug-log"  "$DST/app/api/"
cp -a "$SRC/app/layout.tsx" "$SRC/app/page.tsx" "$SRC/app/globals.css" "$SRC/app/favicon.ico" "$DST/app/"

# --- components ---
cp -a "$SRC/components/providers" "$DST/components/"
cp -a "$SRC"/components/ui/{GlassCard,NeonBadge,button,PdfViewerModal}.tsx "$DST/components/ui/"

# --- lib ---
cp -a "$SRC"/lib/odoo/{client,tecnico,companies,publicCompany,schema}.ts "$DST/lib/odoo/"
cp -a "$SRC"/lib/groq/{client,prompts}.ts "$SRC/lib/groq/client.test.ts" "$DST/lib/groq/"
cp -a "$SRC"/lib/hooks/{useTecnicoQualif,useGroqStatus,useReviewCache,useReviewDismissed}.ts "$DST/lib/hooks/"
cp -a "$SRC"/lib/store/{authStore,schemaStore,tecnicoSettings,resetSessionCache}.ts "$DST/lib/store/"
cp -a "$SRC/lib/tecnico/buildSummaryContext.ts" "$DST/lib/tecnico/"
cp -a "$SRC"/lib/utils/{index,loginUrlParams}.ts "$DST/lib/utils/"

# --- raiz, testes e assets ---
cp -a "$SRC/middleware.ts" "$DST/"
cp -a "$SRC"/{package.json,package-lock.json,tsconfig.json,tailwind.config.ts,postcss.config.mjs,next.config.mjs,vitest.config.ts,.eslintrc.json,.gitignore,.dockerignore,.env.example,Dockerfile,docker-compose.yml} "$DST/"
cp -a "$SRC/tests/setup.ts" "$SRC/tests/reset-session-cache.test.ts" "$DST/tests/"
cp -a "$SRC/public/manifest.json" "$SRC/public/icons" "$DST/public/"
```

Não copiar: `public/sw.js`, `public/workbox-*.js`, `public/pdf.worker.min.mjs` (gerados — os dois primeiros pelo `next-pwa` no build, o terceiro pelo `postinstall`), `node_modules`, `.next`, `.env.local`, `tsconfig.tsbuildinfo`.

- [ ] **Step 3: Instalar dependências**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa
npm ci
```

Esperado: instalação completa e a linha `pdfjs worker copiado de node_modules/...` vinda do `postinstall`.

**Verificação bloqueante:**

```bash
ls -la public/pdf.worker.min.mjs
```

O `postinstall` procura o worker em `node_modules/react-pdf/node_modules/pdfjs-dist/build/` e em `node_modules/pdfjs-dist/build/`, e **engole o erro** se não achar em nenhum dos dois (`catch` que só imprime). Se o arquivo não existir, o hoisting do npm colocou o `pdfjs-dist` em outro lugar: achar com `find node_modules -name pdf.worker.min.mjs`, copiar para `public/` na mão e acrescentar o caminho ao array `candidates` do `postinstall`. Sem esse arquivo, o `PdfViewerModal` quebra em runtime **com build verde** — a mesma classe de falha silenciosa que a verificação do manifest cobre na Task 2.

- [ ] **Step 4: Enxugar o root layout**

`app/layout.tsx` veio importando `AppShell` (que puxa `AppSidebar`, que puxa os módulos Ciclos/OS/Contatos). Sem esta edição, o fecho do Step 7 arrastaria o app inteiro.

Trocar as duas linhas do import e o corpo do `AuthGuard`:

```tsx
// REMOVER esta linha do topo do arquivo:
import { AppShell } from '@/components/layout/AppShell'
```

```tsx
// ANTES:
            <AuthGuard>
              <AppShell>{children}</AppShell>
            </AuthGuard>

// DEPOIS:
            <AuthGuard>{children}</AuthGuard>
```

Também atualizar o `metadata` (o título aparece na aba e no A2HS):

```tsx
export const metadata: Metadata = {
  title: 'Qualificação · Técnico',
  description: 'Coleta de dados de qualificação em campo',
  manifest: '/manifest.json',
  themeColor: '#1f6feb',
}
```

Ficam intactos: `ThemeProvider` (os fixes de contraste do modo claro dependem dele), `QueryProvider`, `ErrorReporter`, `PageTitle`, `Toaster` e as fontes Geist.

- [ ] **Step 5: Adaptar o teste do `resetSessionCache` (RED)**

`resetSessionCache` importa `./contactsStore` e `./ciclosStore`, que não viajam. O teste é adaptado primeiro para fixar o comportamento esperado da versão enxuta.

Em `tests/reset-session-cache.test.ts`:

1. Remover os imports `useContactsStore` e `useCiclosStore`.
2. Remover essas duas chamadas do `beforeEach`.
3. Apagar o caso `it('limpa filtros de contatos e ciclos', ...)` inteiro.
4. No caso `'apaga o cache do React Query (queries não sobrevivem)'`, trocar as chaves de exemplo por chaves do domínio técnico:

```ts
  it('apaga o cache do React Query (queries não sobrevivem)', () => {
    const qc = new QueryClient()
    qc.setQueryData(['os-mine', 7], [{ id: 1, name: 'OS-0001' }])
    qc.setQueryData(['os-detail', 1, 7], { id: 1 })
    qc.setQueryData(['company', 1], { id: 1, name: 'Antiga' })

    expect(qc.getQueryData(['os-mine', 7])).toBeDefined()
    expect(qc.getQueryData(['os-detail', 1, 7])).toBeDefined()

    resetSessionCache(qc)

    expect(qc.getQueryData(['os-mine', 7])).toBeUndefined()
    expect(qc.getQueryData(['os-detail', 1, 7])).toBeUndefined()
    expect(qc.getQueryData(['company', 1])).toBeUndefined()
  })
```

5. No caso `'cenário troca-de-server...'`, remover as duas asserções finais sobre `useContactsStore`/`useCiclosStore` e trocar a query semeada `['ciclos', {}]` por `['os-mine', 10]`.

- [ ] **Step 6: Rodar o teste e confirmar que falha**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa
npx vitest run tests/reset-session-cache.test.ts
```

Esperado: FAIL na resolução de import — `Failed to resolve import "./contactsStore"` (o `resetSessionCache.ts` ainda importa os stores que não vieram). Este é o RED.

- [ ] **Step 7: Enxugar o `resetSessionCache`**

Conteúdo novo de `lib/store/resetSessionCache.ts`:

```ts
/**
 * Reset completo de estado do cliente ao trocar de servidor ou usuário.
 *
 * Inclui:
 *  - React Query cache (OSs, relatórios, coletas)
 *  - schemaStore (fields_get + check_access_rights)
 *  - authStore.company (logo/nome da empresa anterior)
 *
 * Não mexe em serverUrl/dbName — essas são as próprias credenciais novas.
 */
import type { QueryClient } from '@tanstack/react-query'
import { useSchemaStore } from './schemaStore'
import { useAuthStore } from './authStore'

export function resetSessionCache(queryClient?: QueryClient | null): void {
  // React Query: invalida todas as queries e descarta cache
  if (queryClient) {
    queryClient.cancelQueries()
    queryClient.clear()
  }

  // Schema (campos + permissões)
  useSchemaStore.getState().clear()

  // Company cacheada (evita mostrar logo da empresa anterior)
  useAuthStore.getState().setCompany(null, '', null)
  useAuthStore.getState().setAvailableCompanies([])
  useAuthStore.getState().setSelectedCompany(null)
}
```

- [ ] **Step 8: Rodar o teste e confirmar que passa (GREEN)**

```bash
npx vitest run tests/reset-session-cache.test.ts
```

Esperado: 4 testes passando (eram 5; o de filtros foi removido).

- [ ] **Step 9: Ajustar `vitest.config.ts` e `docker-compose.yml`**

Em `vitest.config.ts`, remover o bloco `environmentMatchGlobs` — ele mapeava `tests/components/**`, diretório que não viaja. As suítes do técnico declaram o ambiente por docblock (`// @vitest-environment happy-dom`):

```ts
  test: {
    environment: 'node',
    globals: true,
    testTimeout: 15000,
    hookTimeout: 10000,
    reporters: ['verbose'],
    setupFiles: ['./tests/setup.ts'],
  },
```

Em `docker-compose.yml`, o serviço passa a ter identidade própria e a porta do checklist:

```yaml
services:
  pwa:
    build:
      context: .
      dockerfile: Dockerfile
    image: afr_qualificacao_pwa:latest
    container_name: afr_qualificacao_pwa
    restart: unless-stopped
    ports:
      - "3010:3000"
    environment:
      NODE_ENV: production
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:3000/"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

Em `package.json`, trocar o campo `name` de `fitadigital-frontend` para `afr-qualificacao-pwa`.

- [ ] **Step 10: Fechar a árvore com o compilador**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa
npx tsc --noEmit
```

Cada erro `Cannot find module '@/...'` nomeia um arquivo que ficou para trás. Para cada um: copiar o arquivo correspondente de `$SRC` preservando o caminho relativo, e rodar `tsc` de novo. Repetir até saída vazia.

**Erros que NÃO são de arquivo faltando:** `tsconfig.json` exclui `tests/**`, mas as 7 suítes do técnico vivem em `app/tecnico/qualificacao/__tests__/` — dentro do `include`. O `tsc` vai type-checá-las, e elas importam `vitest`, `@testing-library/react` e globais de DOM. Na origem isso compila limpo com o mesmo `tsconfig.json` (verificado em 2026-09-02, ver Global Constraints). Portanto: erro que **não** seja `Cannot find module '@/...'` significa divergência de ambiente, não peça faltando — rodar `npx tsc --noEmit` na origem (`SRC`) e comparar as saídas antes de mexer em qualquer configuração. Não relaxar `strict`, não acrescentar `skipLibCheck` extra, não excluir `__tests__` do `tsconfig` para "resolver".

**Regra de parada:** se um erro apontar para `@/components/layout/*`, `@/components/dashboard/*`, `@/lib/odoo/{ciclos,os,partners,reports,bus}`, `@/lib/hooks/use{Ciclos,Os,Contacts,Dashboard,GlobalSearch,...}` ou `@/lib/types/{ciclo,os,partner}`, **não copiar**: é sinal de que algo do shell ficou apontando para um módulo que não viaja. Achar o consumidor e cortar a dependência (como foi feito no Step 4 e no Step 7), não arrastar o módulo.

Esperado ao final: `npx tsc --noEmit` sem nenhuma saída.

- [ ] **Step 11: Commit**

Delegar ao subagente `git-commit-push` com `cwd=/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`, branch `feat/pwa-tecnico-no-addon`, staging **apenas** `pwa/`, sem push:

```
git add pwa
git commit -m "feat(pwa): import técnico field PWA from frontend_odoo@4cd26dd

Moves the field technician PWA into the addon so backend and frontend
share a commit and the RPC contract cannot desync.

Trimmed on import: root layout drops AppShell/AppSidebar, and
resetSessionCache no longer touches the ciclos/contacts stores — neither
travels with the técnico app.

Origin history stays available at frontend_odoo origin/tecnico-qualif-pwa."
```

---

### Task 2: Build de produção verde

`tsc` não enxerga fontes, CSS, manifest nem a geração do service worker. Esta task fecha o que só o build revela.

**Files:**
- Modify: `pwa/next.config.mjs` (se o build acusar), `pwa/.gitignore` (entradas do `next-pwa`)
- Test: o próprio `npm run build` + inspeção dos artefatos

**Interfaces:**
- Consumes: árvore `pwa/` com `tsc` limpo (Task 1)
- Produces: `.next/standalone/server.js` construído; `public/sw.js` e `public/workbox-*.js` gerados e gitignored

- [ ] **Step 1: Rodar o build e catalogar as falhas**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa
npm run build 2>&1 | tee /tmp/pwa-build.log
```

Falhas esperadas nesta primeira execução são de asset ausente. As mais prováveis, com a correção de cada uma:

| Erro | Causa | Correção |
|---|---|---|
| `Can't resolve './fonts/GeistVF.woff'` | `app/fonts/` não copiado | `cp -a $SRC/app/fonts $DST/app/` |
| `Module not found: Can't resolve '@/app/globals.css'` | CSS não copiado | `cp -a $SRC/app/globals.css $DST/app/` |
| Classes Tailwind ausentes no output | `tailwind.config.ts` com `content` apontando paths inexistentes | conferir o array `content` e remover globs de `app/ciclos`, `app/os` etc. |
| `next-pwa` não gera `sw.js` | `next.config.mjs` não copiado | `cp -a $SRC/next.config.mjs $DST/` |

- [ ] **Step 2: Verificar os artefatos do build**

```bash
ls -la .next/standalone/server.js .next/static public/sw.js public/manifest.json public/icons/
```

Esperado: os cinco existem. `public/sw.js` e `public/workbox-*.js` são gerados pelo `next-pwa` — confirmar que o `.gitignore` já os cobre (`grep -n "sw.js\|workbox" .gitignore`), senão acrescentar.

- [ ] **Step 3: Conferir que o manifest chegou íntegro**

```bash
cat public/manifest.json
```

Esperado, verbatim do original: `"start_url": "/tecnico/qualificacao"`, `"display": "standalone"`, `"theme_color": "#1f6feb"`, e os dois ícones `/icons/icon-192.png` e `/icons/icon-512.png`. Um manifest ausente ou com `start_url` errado derruba os itens E.1/E.2 do bloco H **com build verde** — por isso a verificação é explícita.

- [ ] **Step 4: Rodar o build de novo, limpo**

```bash
rm -rf .next && npm run build
```

Esperado: `✓ Compiled successfully` e a tabela de rotas listando `/`, `/login`, `/tecnico/qualificacao`, `/tecnico/qualificacao/[osId]`, `/tecnico/qualificacao/[osId]/coleta/[itemId]`, `/tecnico/qualificacao/[osId]/relatorio/[relId]`, `/tecnico/qualificacao/[osId]/relatorio/[relId]/finalizar`, `/tecnico/qualificacao/historico`, `/tecnico/qualificacao/perfil` e as rotas `/api/odoo/*`, `/api/groq/*`, `/api/debug-log`. Nenhuma rota de `ciclos`, `os`, `equipamentos`, `wall` ou `contacts` deve aparecer.

- [ ] **Step 5: Commit**

Via `git-commit-push`, mesmo `cwd` e branch, staging só `pwa/`:

```
git commit -m "fix(pwa): make the standalone production build green"
```

Se o Step 1 não tiver exigido nenhuma correção, pular o commit e registrar no relatório que o build passou de primeira.

---

### Task 3: Suíte migrada e baseline nova registrada

**Files:**
- Test: `pwa/app/tecnico/qualificacao/__tests__/*` (7 suítes, vieram na Task 1), `pwa/lib/groq/client.test.ts`, `pwa/tests/reset-session-cache.test.ts`
- Create: `pwa/docs/BASELINE.md`

**Interfaces:**
- Consumes: árvore compilando (Task 1) e build verde (Task 2)
- Produces: `pwa/docs/BASELINE.md` com a contagem de referência para todas as tasks futuras

- [ ] **Step 1: Rodar a suíte inteira**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa
npm test 2>&1 | tail -30
```

Esperado: 9 arquivos de teste (7 de `app/tecnico/qualificacao/__tests__/`, `lib/groq/client.test.ts`, `tests/reset-session-cache.test.ts`), **zero falhas**.

**Não** transportar a contagem antiga do `frontend_odoo` (92 pass / 3 fail). Aquelas 3 falhas eram de rede em `tests/odoo-connection.test.ts`, `tests/reports.test.ts` e `tests/pdf-viewer.test.ts` — suítes de Ciclos/OS que não viajam. Se alguma falha aparecer aqui, é lacuna real da migração, não ruído ambiental conhecido.

- [ ] **Step 2: Diagnosticar qualquer falha antes de seguir**

Falhas plausíveis e o que significam:

| Sintoma | Diagnóstico |
|---|---|
| `Cannot find module '@/lib/...'` | fecho da Task 1 incompleto — o arquivo é importado só por teste, e `tsconfig.json` exclui `tests/**` |
| `document is not defined` | falta o docblock `// @vitest-environment happy-dom` no topo da suíte, ou `setupFiles` não aponta `./tests/setup.ts` |
| `toBeInTheDocument is not a function` | `tests/setup.ts` não copiado (é ele que importa `@testing-library/jest-dom`) |

Corrigir e voltar ao Step 1 até verde.

- [ ] **Step 3: Escrever a baseline**

Criar `pwa/docs/BASELINE.md`:

```markdown
# Baseline de testes — PWA Técnico

Medida em 2026-09-02, logo após a migração de `frontend_odoo@4cd26dd`
para `addons/afr_qualificacao/pwa/`.

| Métrica | Valor |
|---|---|
| Arquivos de teste | <preencher> |
| Testes | <preencher> pass / <preencher> skip / 0 fail |
| Comando | `npm test` (vitest run) |
| `npx tsc --noEmit` | limpo |
| `npm run build` | verde |

Qualquer falha em execução futura é regressão: esta baseline não tem
falhas ambientais. As 3 falhas de rede da suíte antiga do `frontend_odoo`
(`odoo-connection`, `reports`, `pdf-viewer`) pertenciam a módulos que não
migraram.
```

Preencher os `<preencher>` com os números reais do Step 1.

- [ ] **Step 4: Commit**

```
git commit -m "test(pwa): record post-migration test baseline"
```

---

### Task 4: Smoke em dev contra o Odoo, e impacto no watcher

**Files:**
- Create: `pwa/.env.local` (não versionado)
- Modify: nenhum arquivo versionado, salvo correção que o smoke exija

**Interfaces:**
- Consumes: build verde (Task 2), suíte verde (Task 3)
- Produces: evidência de que o app autentica e lista OSs contra o Odoo real; medição do boot do container Odoo com `node_modules` na árvore de addons

- [ ] **Step 1: Medir o boot do Odoo com o `node_modules` já na árvore**

`addons/` é bind-montado em `/mnt/extra-addons` e o container roda `--dev=all` com `watchdog`. Depois da Task 1, `pwa/node_modules` (~500 diretórios) entra na árvore observada.

O controle já foi tirado antes da migração: **4 segundos** (ver Global Constraints). Medir agora, no mesmo formato:

```bash
cd /home/afonso/docker/odoo_engenapp
docker restart odoo_engenapp-web-qualificacao-1 >/dev/null && START=$(date +%s)
for i in $(seq 1 120); do
  if docker logs --since 30s odoo_engenapp-web-qualificacao-1 2>&1 | grep -q "HTTP service (werkzeug) running"; then
    echo "BOOT_SECONDS=$(( $(date +%s) - START ))"; break
  fi
done
```

Não usar `docker logs -f | grep -m1`: o `grep` fecha o pipe, o shell recebe SIGTERM (exit 143) e o `echo` do tempo nunca roda.

- [ ] **Step 2: Comparar com o controle**

`fs.inotify.max_user_watches` = 524288 no host e no container (verificado), então numericamente há folga. O que se mede aqui é o tempo de walk da árvore.

Critério: boot acima de **30 segundos** (controle de 4s + margem larga) dispara a mitigação prevista no spec — `node_modules` vai para um volume nomeado, acrescentando ao `pwa/docker-compose.yml` um serviço de dev com `- /app/node_modules` mascarando o bind, e o `npm` passa a rodar dentro desse container. Abaixo disso, registrar o número medido no relatório e seguir.

- [ ] **Step 3: Criar o `.env.local` com a chave da Groq**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa
printf 'GROQ_API_KEY=<chave NOVA, rotacionada no console da Groq>\n' > .env.local
git check-ignore -v .env.local   # deve casar com a regra .env*.local
```

A chave anterior está comprometida (apareceu em texto claro na sessão de 2026-09-02). Rotacionar antes de usar. Sem ela, as features de IA (auto-resumo, ditado, revisão pré-fechamento) ficam degradadas — o resto do app funciona.

- [ ] **Step 4: Subir o dev server**

```bash
npm run dev
```

Esperado: `Local: http://localhost:3010`. Deixar rodando em background para os steps seguintes.

- [ ] **Step 5: Smoke pela UI com `agent-browser`**

```bash
agent-browser open http://localhost:3010/
agent-browser snapshot -i
```

Verificar, na ordem:

1. `/` redireciona para `/login` (sem cookie de sessão) — item A.1 do checklist.
2. Preencher URL do Odoo `http://localhost:8084`, db, usuário e senha; submeter.
3. Após autenticar, a rota é `/tecnico/qualificacao` — item A.2.
4. A lista renderiza os grupos "Em andamento" / "Agendadas" / "Rascunhos", ou o empty state se não houver OS — itens A.3/A.6.
5. Abrir `/tecnico/qualificacao/perfil` e confirmar que nome e email do usuário aparecem.
6. DevTools não obrigatório aqui; o bloco E (service worker, A2HS) fica para a execução do checklist, fora deste plano.

Se o passo 2 falhar com erro de rede, conferir se o proxy `/api/odoo` está repassando para o host correto — `app/api/odoo/[...path]/route.ts` resolve a URL a partir do cookie gravado no login.

- [ ] **Step 6: Registrar o resultado**

Sem commit se nada versionado mudou. Registrar no relatório da task: tempo de boot do Odoo antes/depois, e o resultado dos 5 pontos do smoke. Se algum ponto falhar, corrigir e recomeçar o Step 5 — este é o gate real da migração.

---

### Task 5: Documentação e divisão do TODO

**Files:**
- Create: `pwa/README.md`, `pwa/TODO.md`
- Modify: `pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md` (seção Ambiente), `/home/afonso/docker/frontend_odoo/TODO.md` (remover a seção que migrou)

**Interfaces:**
- Consumes: app verificado em dev (Task 4)
- Produces: documentação apontando para os caminhos novos; TODO dividido sem item perdido nem duplicado

- [ ] **Step 1: Escrever o `pwa/README.md`**

```markdown
# PWA Técnico de campo — `afr_qualificacao`

App Next.js que o técnico usa em tablet/celular para executar coletas de
qualificação: inicia o relatório do dia, anexa fotos/arquivos por item,
assina e fecha o relatório.

Vive dentro do addon de propósito: backend e front compartilham commit, e o
contrato RPC (`action_start_daily_relatorio`, `action_done`,
`afr.qualificacao.collect.item`) não pode dessincronizar.

## Rodar em desenvolvimento

```bash
npm ci
cp .env.example .env.local     # preencher GROQ_API_KEY
npm run dev                    # http://localhost:3010
```

A URL do Odoo não é variável de ambiente: é digitada na tela de login e
guardada em cookie + localStorage. Em desenvolvimento, apontar para
`http://localhost:8084` (container `odoo_engenapp-web-qualificacao-1`).

## Testes

```bash
npm test            # vitest run
npx tsc --noEmit    # type check
npm run build       # build standalone de produção
```

Baseline em `docs/BASELINE.md`. Aceitação end-to-end:
`app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md`.

## Produção

```bash
docker compose up -d --build   # publica em :3010
```

## Versionamento

Este PWA **não** bumpa `__manifest__.py` do addon. A versão do front está no
`package.json`; o manifesto Odoo bumpa só em mudança de Python/XML/segurança.

## Origem

Migrado de `frontend_odoo@4cd26dd` (branch `tecnico-qualif-pwa`, 42 commits)
em 2026-09-02. O histórico anterior continua em
`origin/tecnico-qualif-pwa` naquele repositório.
```

- [ ] **Step 2: Atualizar a seção Ambiente do checklist**

Em `app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md`, trocar o bloco `## Ambiente`:

```markdown
## Ambiente
- Backend Odoo do addon rodando em http://localhost:8084
  (container `odoo_engenapp-web-qualificacao-1`)
- Frontend Next dev:
  `cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa && npm run dev`
  → http://localhost:3010
```

O resto do arquivo (blocos A–H) fica intacto.

- [ ] **Step 3: Criar o `pwa/TODO.md` com os itens que migram**

Copiar do `TODO.md` do `frontend_odoo` **apenas** a seção `### Técnico Qualificação` e a seção `### Backend afr_qualificacao — autorização (deferido em 2026-07-27)`, sob um cabeçalho novo:

```markdown
# TODO — PWA Técnico

## Pendente
```

Os quatro itens da primeira seção (`description` no CollectedCard, `kind='outro'` sem anexo, relógio dispositivo vs. servidor, bloco H não executado) e os cinco achados de autorização viajam **verbatim**, com os paths de front reescritos para `pwa/...`.

- [ ] **Step 4: Remover da origem o que migrou**

No `TODO.md` do `frontend_odoo` (worktree principal, `/home/afonso/docker/frontend_odoo/TODO.md`, arquivo já modificado e não commitado), apagar as duas seções migradas e deixar uma linha de ponteiro no lugar:

```markdown
### Técnico Qualificação
Migrado para `odoo_engenapp/addons/afr_qualificacao/pwa/TODO.md` em 2026-09-02.
```

As seções `### Ciclos`, `## Feito` e as de Infra permanecem.

**Não commitar essa mudança**: o `TODO.md` do `frontend_odoo` já estava modificado antes deste trabalho, junto de outras 9 alterações de Equipamentos. Deixar no working tree e reportar ao usuário.

- [ ] **Step 5: Commit (só do lado do addon)**

```
git add pwa
git commit -m "docs(pwa): README, checklist paths and migrated TODO items"
```

---

### Task 6: Fechamento — merge, push e pointer do monorepo

Só executar depois que Tasks 1–5 estiverem verdes e o usuário tiver confirmado o smoke da Task 4.

**Files:**
- Modify: pointer do submodule no monorepo (`addons/afr_qualificacao`)

**Interfaces:**
- Consumes: branch `feat/pwa-tecnico-no-addon` com todos os commits das Tasks 1–5
- Produces: `main` do submodule contendo o PWA; pointer do monorepo apontando para o commit novo

- [ ] **Step 1: Reconferir o gate antes de mergear**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa
npx tsc --noEmit && npm test && npm run build
```

Esperado: os três verdes, com a contagem de testes batendo com `docs/BASELINE.md`. Se algum falhar, o merge não acontece.

- [ ] **Step 2: Conferir que nada além de `pwa/` foi tocado**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git diff --stat $(git merge-base main feat/pwa-tecnico-no-addon)..feat/pwa-tecnico-no-addon -- . ':!pwa'
```

Diffar contra o merge-base, não contra `main`: o spec e o plano foram commitados em `main` **depois** do corte do branch, então um `main..branch` os mostraria como deleções do lado do branch — falso positivo.

Esperado: saída vazia. Nenhuma mudança em `models/`, `views/`, `security/`, `tests/` ou `__manifest__.py`.

- [ ] **Step 3: Merge e push do submodule**

Via `git-commit-push`, `cwd=/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`:

```bash
git checkout main
git merge --no-ff feat/pwa-tecnico-no-addon -m "feat(pwa): field technician PWA now lives in the addon"
git push origin main
```

Confirmar `local == remote` antes de seguir — o CLAUDE.md do monorepo é explícito: o push do submodule vem **antes** do bump do pointer, senão o pointer aponta para um commit ausente no remote.

- [ ] **Step 4: Bump do pointer no monorepo**

Via `git-commit-push`, `cwd=/home/afonso/docker/odoo_engenapp`, staging **apenas** o pointer:

```bash
git add addons/afr_qualificacao
git commit -m "chore: bump submodule afr_qualificacao (PWA técnico migrado para o addon)"
git push
```

O monorepo tem ~100 mudanças alheias no working tree — `git add` só do path do submodule, jamais `git add -A`.

- [ ] **Step 5: Arquivar a origem sem apagar**

```bash
cd /home/afonso/docker/frontend_odoo
git branch -m tecnico-qualif-pwa archived/tecnico-qualif-pwa-migrado-2026-09-02   # NÃO executar sem ok do usuário
```

Este step **não é executado pelo implementador**. `origin/tecnico-qualif-pwa` e o worktree ficam intactos; o comando fica registrado aqui como a ação que o usuário pode disparar quando quiser, depois de rodar o bloco H no destino. Enquanto o bloco H não passar, a origem continua sendo a rede de segurança.

---

## Notas de execução

**Desvio consciente do spec:** o spec fala em "um commit citando a origem". Este plano produz um commit de import (Task 1) mais commits menores de build, testes e docs. O compromisso preservado é o que importa — nenhum histórico é replantado, e o commit de import cita `frontend_odoo@4cd26dd`. O merge `--no-ff` da Task 6 deixa o lote identificável como uma unidade.

**Fora de escopo deste plano** (registrados no `pwa/TODO.md`): executar o bloco H, corrigir `kind='outro'` sem anexo, corrigir o risco de relógio no `finalizeRelatorio`, mostrar `description` no CollectedCard, os cinco achados de autorização deferidos, e a poda de dependências não usadas do `package.json` — esta última só faz sentido com o app rodando e a baseline estabelecida, e vale como plano próprio.
