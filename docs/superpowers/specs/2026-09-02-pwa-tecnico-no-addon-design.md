# Design — PWA Técnico de campo dentro do addon `afr_qualificacao`

Data: 2026-09-02
Status: aprovado pelo usuário (2026-09-02), pronto para plano de implementação

## Problema

O PWA Técnico de campo (coleta de dados de qualificação em tablet/celular) vive
hoje no repositório `frontend_odoo`, no branch `tecnico-qualif-pwa` — 42 commits,
último em 2026-07-27, nunca mergeado em `main`. O código não existe em `main`:
`app/tecnico/**` só aparece no branch.

O PWA e o backend `afr_qualificacao` formam um contrato acoplado
(`action_start_daily_relatorio`, `action_done`, `collect.item`, as `ir.rule` do
grupo Técnico). Estando em repositórios diferentes, nada garante que as duas
pontas avancem juntas: uma mudança de assinatura no backend pode ser pushada sem
a mudança correspondente no front, e o único aviso é o bloco H falhando semanas
depois.

## Decisão

Mover o PWA para dentro do repositório do addon, em
`addons/afr_qualificacao/pwa/`. Um único commit passa a poder alterar backend e
front juntos, e o pointer do submodule no monorepo amarra o par.

Três decisões tomadas na fase de brainstorm (2026-09-02):

1. **Local:** dentro do repo `afr_qualificacao`, não repo irmão nem submodule
   aninhado.
2. **Escopo:** só o técnico + o shell mínimo que ele importa. Não é cópia
   integral do `frontend_odoo` para podar depois, nem extração do shell para um
   pacote npm compartilhado.
3. **Histórico:** import limpo — um commit citando a origem
   (`frontend_odoo@4cd26dd`). Os 42 commits continuam acessíveis em
   `origin/tecnico-qualif-pwa`, que passa a ser arquivo.

## Estrutura de diretórios

```
addons/afr_qualificacao/            [submodule → afr_qualificacao.git, branch main]
├── models/  views/  tests/  security/  migrations/   ← backend Odoo, inalterado
├── __manifest__.py
└── pwa/                                              ← NOVO
    ├── app/
    │   ├── tecnico/qualificacao/**                   ← 29 arquivos movidos
    │   ├── login/
    │   ├── api/odoo/**   api/groq/**
    │   ├── layout.tsx  globals.css  favicon.ico  fonts/
    ├── lib/          components/       public/
    ├── tests/        middleware.ts     next.config.mjs
    ├── package.json  tsconfig.json     tailwind.config.ts  postcss.config.mjs
    ├── Dockerfile    docker-compose.yml  .dockerignore  .gitignore
    └── F7_0_TEST_CHECKLIST.md
```

`pwa/` não contém `__manifest__.py` nem `__init__.py`, logo o Odoo não a
descobre como módulo.

## Inventário da migração

### Como determinar o conjunto completo

O grep de imports de primeiro nível encontra 18 dependências externas de
`app/tecnico`, mas cada arquivo do shell tem as suas próprias — `app/login/page.tsx`,
por exemplo, puxa `publicCompany`, `schema`, `schemaStore` e `loginUrlParams`, e
nenhum aparece no grep do técnico.

O fecho transitivo sai do compilador, não do grep:

1. Copiar a semente (lista abaixo).
2. `npx tsc --noEmit` — cada import não resolvido é uma peça faltando.
3. Copiar exatamente o que o erro nomeia. Repetir até `tsc` limpo.
4. `npm run build` — pega o que o `tsc` não enxerga (assets, fontes, config do
   `next-pwa`, worker do pdfjs).

O repositório de origem estava `tsc`-limpo, então toda lacuna aparece como erro.

### Semente

- `app/tecnico/**` — 29 arquivos (páginas, `_components/`, `__tests__/`,
  `layout.tsx`, checklist)
- `app/login/**`
- `app/api/odoo/[...path]/route.ts`, `app/api/odoo/session-info/route.ts`
- `app/api/groq/{summary,review,status,transcribe}/route.ts`
- `app/layout.tsx`, `middleware.ts`
- `components/providers/` — `QueryProvider`, `ThemeProvider`, `AuthGuard`,
  `ErrorReporter`, `PageTitle`
- `components/ui/` — `GlassCard`, `NeonBadge`, `button`, `PdfViewerModal`
- `lib/odoo/` — `client`, `tecnico`, `companies`, `publicCompany`, `schema`
- `lib/groq/` — `client`, `prompts`, `client.test.ts`
- `lib/hooks/` — `useTecnicoQualif`, `useGroqStatus`, `useReviewCache`,
  `useReviewDismissed`
- `lib/store/` — `authStore`, `tecnicoSettings`, `resetSessionCache`,
  `schemaStore`
- `lib/tecnico/buildSummaryContext.ts`, `lib/utils/loginUrlParams.ts`,
  `lib/utils/index.ts`

### Assets fora de qualquer grafo de imports

Não aparecem em `tsc`; quebram o build ou — pior — quebram o PWA em silêncio com
build verde:

- `app/fonts/GeistVF.woff`, `app/fonts/GeistMonoVF.woff` — o root layout usa
  `localFont({ src: './fonts/...' })`
- `app/globals.css`, `tailwind.config.ts`, `postcss.config.mjs`
- `public/manifest.json` e `public/icons/` — o root layout declara
  `manifest: '/manifest.json'`; ausência derruba os itens E.1/E.2 do bloco E sem
  nenhum erro de build
- `public/pdf.worker.min.mjs` **e** o script `postinstall` do `package.json` que
  o copia de `node_modules` (o `PdfViewerModal` depende dele)
- `app/favicon.ico`
- `next.config.mjs` — wrapper `next-pwa` (`dest: 'public'`, `runtimeCaching`) e
  `output: 'standalone'`
- `vitest.config.ts`, `tsconfig.json`, `.dockerignore`, `Dockerfile`,
  `docker-compose.yml`, `.gitignore`

### Adaptações no que migra

**Login — copiado e podado, não reescrito.** São 746 LOC load-bearing: cookie da
URL do Odoo, prefill por query string, logo público da empresa, reset de cache de
sessão. Reescrever é onde bugs de autenticação nascem. A poda se limita aos
branches de redirect para `/ciclos` e `/os`; o destino `/tecnico/qualificacao` já
existe (`app/login/page.tsx:176`).

**Root layout enxuto.** Saem `AppShell` e `AppSidebar` — o layout técnico já traz
header próprio e bottom nav (OSs / Histórico / Perfil). Permanecem
`ThemeProvider` (os fixes de contraste no modo claro, commits `350cfdb` e
`f46df2f`, dependem dele), `QueryProvider`, `AuthGuard`, `ErrorReporter` e o
`Toaster`.

**`docker-compose.yml`.** Porta do serviço muda de 3000 para 3010, alinhada ao
`npm run dev` já usado pelo checklist, e o `container_name` passa a
`afr_qualificacao_pwa`.

**`F7_0_TEST_CHECKLIST.md`.** A seção "Ambiente" cita caminhos do worktree
antigo; passa a apontar `addons/afr_qualificacao/pwa/`.

## O que fica no `frontend_odoo`

Módulos `ciclos`, `os`, `equipamentos`, `wall`, `contacts`, os 16 componentes
restantes de `components/ui/`, `components/layout/`, e as suítes de teste desses
módulos.

`TODO.md` é **dividido, não movido**: a seção "Técnico Qualificação" viaja para
`pwa/TODO.md`; as seções "Ciclos" e "Infra" permanecem no `frontend_odoo`.

Há duplicação deliberada de shell entre os dois repositórios — `lib/odoo/client.ts`
(392 LOC), o proxy `/api/odoo`, `authStore` e a página de login passam a existir
nos dois lados. É o preço aceito por não criar um terceiro repositório de pacote
compartilhado. Divergência futura entre as duas cópias é esperada e aceitável: os
dois apps têm ciclos de vida diferentes.

## Política de versão

O PWA **não** bumpa `__manifest__.py`. A versão do front vive no `package.json`
do `pwa/`. O manifesto Odoo é bumpado apenas em mudança de Python/XML/segurança —
caso contrário todo ajuste de front dispararia um `-u afr_qualificacao`
desnecessário no deploy.

Quando um commit toca os dois lados (mudança de contrato), o bump do manifesto
acontece por causa da parte backend, como já acontece hoje.

## Convivência com o watcher do Odoo

`addons/` é bind-montado em `/mnt/extra-addons` e o container de dev roda
`--dev=all` (`docker-compose.qualificacao.yml:22`), com `watchdog` instalado. A
árvore observada passa a incluir `pwa/node_modules`.

Verificado: `fs.inotify.max_user_watches = 524288` no host e no container, folga
suficiente para os ~500 diretórios de `node_modules`. `pwa/` não é módulo Odoo,
então o carregamento de módulos não é afetado.

Plano: medir o tempo de boot do container depois da mudança. Se degradar, o
`node_modules` migra para um volume nomeado num serviço compose do próprio PWA,
deixando a árvore do host limpa. `.gitignore` não resolve esse ponto — o bind
mount enxerga os arquivos independentemente do git.

## Gate de aceitação

Baseline nova, medida no destino. Das 20 suítes do `frontend_odoo`, só ~8 viajam:
as 7 de `app/tecnico/qualificacao/__tests__/` e `lib/groq/client.test.ts`.
`tests/reports.test.ts` é de Ciclos (`afr.supervisorio.ciclos`) e permanece na
origem. Carregar o número antigo (92 pass / 3 fail) para o destino mascararia uma
lacuna real como se fosse a falha de rede já conhecida.

Verde significa, em `addons/afr_qualificacao/pwa/`:

1. `npx tsc --noEmit` limpo
2. `npm run build` bem-sucedido
3. as ~8 suítes migradas passando, com a contagem registrada como baseline nova
4. `npm run dev` servindo `/tecnico/qualificacao` e autenticando contra o Odoo em
   `localhost:8084`

O worktree `tecnico-qualif-pwa` e o branch `origin/tecnico-qualif-pwa` ficam
intactos até os quatro itens passarem. São a rede de segurança e a prova de que o
fecho transitivo da migração ficou completo.

## Execução e commits

Um commit em `afr_qualificacao/main`, mensagem citando a origem
(`frontend_odoo@4cd26dd`). Conforme o `CLAUDE.md` do monorepo: commit e
`git push origin main` **de dentro** de `addons/afr_qualificacao/`, via o agente
de commit, e só então o bump do pointer no monorepo.

## Fora de escopo

- Executar o bloco H (H1–H12) do checklist. Continua pendente; a migração não o
  desbloqueia nem o bloqueia.
- Corrigir os bugs já registrados no TODO (`kind='outro'` sem anexo, relógio do
  dispositivo vs. servidor, `description` no CollectedCard).
- Mergear qualquer coisa em `main` do `frontend_odoo`.
- Os achados de autorização deferidos em 2026-07-27 (`ir.rule` em `cycle`/`malha`
  e `collect.item`, report sem `groups_id`, `approver_id` escrevível).

## Risco operacional registrado

A `GROQ_API_KEY` de `.env.local` foi exposta em texto claro durante a sessão de
2026-09-02. O arquivo está corretamente coberto por `.gitignore` (`.env*.local`) e
continua untracked no destino, mas a chave deve ser rotacionada no console da
Groq.
