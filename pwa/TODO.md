# TODO — PWA Técnico

## Pendente

### Design system (novo em 2026-09-03)

`PRODUCT.md` e `DESIGN.md` agora existem na raiz do PWA, com o sidecar
`.impeccable/design.json` e a config do live mode. North star: **"A Prancheta"**
— checklist de campo, coluna única, cor só para estado. O tema "cyber/neon"
(roxo, rosa, gradiente, glow) está aposentado por decisão registrada lá.

- ~~Classes utilitárias mortas.~~ **Resolvido.** `bg-card`, `text-muted-foreground`,
  `border-border`, `bg-primary`, `bg-muted` e cia. eram usadas em ~236 lugares sem
  nunca terem sido definidas — geravam zero CSS (botão primário sem fundo, texto
  secundário sem cor própria). Tokens definidos em `app/globals.css` + mapeamento
  em `tailwind.config.ts`, no formato HSL que o modificador de opacidade exige.
- ~~`--text-muted` do tema escuro reprovava em contraste~~ (`rgba(255,255,255,0.4)`
  ≈ 3.4:1). Agora `#a3adc2`, acima do piso AA de 4.5:1.
- **Limpeza de neon pendente.** Ainda existem `shadow-glow-*`, `bg-gradient-cyber`,
  `animate-pulse-glow`, `glass` e as cores `neon-purple`/`neon-pink` no
  `tailwind.config.ts` e em componentes (`GlassCard`, `NeonBadge`, fundo do
  `app/layout.tsx`). O DESIGN.md os proíbe; remover numa passada dedicada.
- **`KindPill` usa violeta/azul/roxo por tipo de qualificação** — cor como
  categoria, não estado. Revisar contra a Regra do Estado.
- Auditoria de contraste tela a tela ainda não foi feita (só os tokens base).

### Técnico Qualificação
- CollectedCard: mostrar campo `description` (observação) nos itens já coletados (OsDetail + RelatorioDetail)
- ~~"Coletas realizadas" na tela de fechar turno contava a OS inteira.~~ **Resolvido
  em 2026-09-03**: o bloco agora mostra os três escopos — quantas coletas *neste
  turno* (número protagonista), o progresso da OS (`7 de 25`) e quantas faltam. Os
  itens passaram a trazer `relatorio_id` no `getOsDetail` pra isso ser possível.
- ~~Cartões com faixa lateral colorida e cartão aninhado.~~ **Resolvido**: o resumo
  do turno virou um bloco único com barra de progresso, e o box "Qualificador /
  padrão cadastrado" dentro da linha de coleta virou uma linha de texto (some
  quando não há nada a dizer).
- ~~Emoji como ícone de navegação~~ (📋 📊 👤) → ícones SVG do lucide, com alvo de
  44px e `aria-current`.
- ~~Duas coletas do mesmo ciclo (foto e planilha) eram indistinguíveis na lista~~ —
  só o ícone diferenciava. Agora o tipo aparece por extenso ("Foto", "Planilha").
- ~~Hidratação quebrada em toda navegação~~: o `ReactQueryDevtools` injetava um
  `<div>` que o servidor não renderizava, o React descartava o HTML do servidor e
  o overlay do Next mostrava "1 error" permanente (que mascarou erros reais
  durante os testes). Agora só monta no cliente.
- **Service worker: confirmar em Chrome de verdade.** O `next-pwa` 5.6 só injeta o script de
  registro pelo Pages Router; com App Router o `sw.js` era gerado e nunca registrado. Foi
  adicionado `components/providers/ServiceWorkerRegister.tsx` (registra `/sw.js` no `load`, só em
  produção), mas o Chrome headless do `agent-browser` ignora service workers — nem o registro
  manual instala. Validar em navegador normal/device: SW ativo, prompt de instalação e navegação
  offline (E.2/E.3/E.4 do checklist).
- **Erro de rede aparece cru pro técnico:** ao salvar coleta sem backend, o toast é
  `Erro: Request failed with status code 502` (texto do axios). Trocar por mensagem em pt-BR que
  diga o que fazer — o trabalho não se perde, a foto continua anexada, mas o técnico não sabe disso.
- **"Coletas realizadas" na tela de fechar o turno conta a OS inteira**, não o relatório
  (`app/tecnico/qualificacao/[osId]/relatorio/[relId]/finalizar/page.tsx:57-58` derivam de
  `getOsDetail`). Um turno com 1 coleta exibiu "6". Decidir: filtrar por `relatorio_id` ou trocar
  o rótulo pra deixar claro que é o total da OS.
- **Leitura de OS não é restrita por técnico.** As `ir.rule` do grupo Técnico têm
  `perm_read = False` (`afr_qualificacao/security/qualificacao_groups.xml:59`) — escopo só de
  escrita. Um técnico com o toggle "Só minhas" desligado lista as OSs de todos os colegas
  (verificado com conta só-Técnico em 2026-09-03). Foi deliberado no backend, mas o Bloco F do
  checklist prometia isolamento de leitura. Decidir se restringe leitura ou se ajusta a
  expectativa (e o texto do F.1/F.2).
- **Item `kind='outro'` sem anexo estoura ValidationError.** O backend `_check_required_has_file`
  (`afr_qualificacao/models/qualificacao_collect_item.py:269-276`) exige `file` para **qualquer**
  item com `state='collected'`, mas o front trata `outro` como anexo-opcional
  (`pwa/app/tecnico/qualificacao/[osId]/coleta/[itemId]/page.tsx:17,71`). Salvar um item "Outro" sem
  foto quebra. Decidir de que lado corrigir: relaxar a constraint para `kind='outro'` no backend,
  ou exigir anexo no front. Achado no final review de 2026-07-27. (Não bloqueou o bloco H —
  nenhum item H1–H12 salva `kind='outro'`; a OS 4 semeada só tem `foto`/`excel`.)
- **"Só minhas" off esconde os rascunhos** (`pwa/app/tecnico/qualificacao/page.tsx:23`:
  `filterMine ? drafts : []`). Desligar o filtro mostra *menos* cards quando as OSs alheias
  estão em `draft` — foi o que travou o H3 até semear uma OS alheia em `scheduled`. Parece
  deliberado (evitar inundar com rascunho dos outros), mas não está documentado nem comentado.
  Confirmar a intenção e, se for regra mesmo, comentar no código e ajustar o texto do H3/A.3.
- ~~Relógio do dispositivo vs. do servidor no fechamento do relatório.~~ **Resolvido em
  2026-09-03.** Abertura e fechamento do relatório do dia agora são carimbados inteiramente pelo
  servidor: `action_start_daily_relatorio`/`action_get_daily_relatorio` decidem a janela do dia
  (sem `day_start`/`day_end` vindos do front), e `action_finish_daily_relatorio`
  (`afr.qualificacao.os.relatorio`) grava `data_fim = fields.Datetime.now()` no fechamento — o front
  (`finalizeRelatorio`, `pwa/lib/odoo/tecnico.ts`) manda só `descricao`/`signature_b64`, sem
  `data_fim` nem `signature_technician_date`. O relógio do celular não entra mais em nenhum dos
  dois lados do ciclo diário.
- ~~`getHistoricoSummary`/`todayRangeOdoo` calculam "hoje" pelo relógio do dispositivo.~~
  **Resolvido em 2026-09-03 (v16.0.7.3.0).** Era o último resquício do relógio do aparelho: a
  janela do dia saía de `todayRangeOdoo` e era comparada contra `captured_at`/
  `signature_technician_date`, carimbados pelo servidor — celular torto, contador errado. Agora
  `getHistoricoSummary` só chama `action_historico_hoje` (`afr.qualificacao.os.relatorio`,
  `@api.model`), que devolve os três contadores prontos com a janela decidida no servidor, no fuso
  do usuário Odoo. O critério de "hoje" ficou num lugar só: `_janela_do_dia_do_usuario`
  (`afr.qualificacao.os`), que o fallback de `_janela_do_dia` também passou a usar.
  `todayRangeOdoo`/`toOdooDatetime` foram removidos do front. 10 testes backend
  (`tests/test_pwa_historico_hoje.py`, incluindo o par de fronteira ±1h da meia-noite local) + 2
  no front; conferido na tela: RPC e Histórico mostram os mesmos 8/2/4.
  Ressalva: os **rótulos** de agrupamento da lista ("Hoje"/"Ontem"/data) continuam saindo do
  relógio do aparelho — são de exibição, não contadores. Junto com este fix eles deixaram de
  agrupar por dia **UTC** (`toISOString().slice(0,10)`), que jogava um relatório fechado às 22h
  local no grupo do dia seguinte, e o rótulo de datas antigas deixou de nascer um dia atrás por
  `new Date('YYYY-MM-DD')` ser lido como meia-noite UTC.
- ~~Bloco H do `pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md` (H1-H12).~~ **Executado em
  2026-09-03: 12/12 verdes** no db `qualificacao-dev` (uid 2), evidência por item no próprio
  checklist. O gate de aceitação end-to-end da adequação PWA↔backend está fechado. Blocos A–G
  (funcionalidade geral, PWA, IA, record rules) continuam sem execução manual — o Bloco F em
  particular precisa de uma conta **só** com o grupo Técnico, que ainda não existe no db.
- ~~Blocos A–D e F do checklist.~~ **Executados em 2026-09-03**: A 6/6, B 6/6, C 8/9 (C.3 precisa de
  tablet/celular), D 8/8, F 3/3 com a ressalva de leitura acima. Contas de teste criadas no
  `qualificacao-dev`: `tecnico.a@teste.local`, `tecnico.b@teste.local`, `gestor@teste.local`
  (senha `Teste@2026`). **Falta**: Bloco E (E.2/E.3/E.4 dependem de Chrome real) e Bloco G
  (precisa de `GROQ_API_KEY` reposta + microfone).
- **Bloco G (IA/Groq, G1–G9) — adiado por decisão de 2026-09-03.** Dois bloqueios: (1) não existe
  `pwa/.env.local` e a `GROQ_API_KEY` antiga vazou numa sessão, precisa ser rotacionada antes de
  qualquer teste; (2) G4, G5, G6 e G9 dependem de microfone real — browser headless não tem, então
  isso só roda em máquina com mic. Retomar quando a chave for reposta.
- ~~`/manifest.json` respondia 307 sem sessão.~~ **Corrigido em 2026-09-03**: o bypass de estáticos
  do `middleware.ts` não cobria `.json`/`.webmanifest`. Rotas do app seguem protegidas.

### Backend `afr_qualificacao` — autorização (deferido em 2026-07-27)

Achados de uma auditoria adversarial que rodou junto da adequação PWA↔backend. **Nenhum é
explorável hoje**: os 5 usuários do db têm os três grupos (Técnico/Usuário/Gestor) por implicação,
então não existe conta puramente técnica. Passam a valer quando as contas do PWA forem criadas —
e por isso essas contas devem receber **só** o grupo Técnico: com o grupo Usuário elas herdam a
`ir.rule` permissiva e o lockdown inteiro vira enfeite.

- **`afr.qualificacao.cycle` / `.malha` sem `ir.rule`.** O grupo Técnico tem write nos dois
  (`security/ir.model.access.csv:22,25`) sem escopo nenhum. Provado por sonda: um técnico que
  **não** é o dono da OS editou o cycle de uma qualificação alheia já aprovada e certificada, e o
  certificado do cliente passou de `valid` para `tampered`. Fix: espelhar o par de rules
  (restritiva + permissiva no `group_afr_qualificacao_user`) usando
  `qualificacao_id.os_id.tecnico_default_user_id`.
- **`afr.qualificacao.collect.item`: CRUD completo, incluindo unlink, sem `ir.rule`.** Alcance
  irrestrito em registros-filho de qualquer OS do banco.
- **Report de certificado sem `groups_id`** (`reports/qualificacao_certificate_report.xml:3`). O
  gate de `state == 'approved'` que foi adicionado em `action_print_certificate` **não** cobre
  `/report/pdf/...` nem o menu Imprimir da UI — esses contornam o método. O único controle nesses
  caminhos é a marca d'água `SEM VALIDADE` do template.
- **`approver_id` é escrevível pelo técnico** (`models/qualificacao_os.py:96`,
  `models/qualificacao.py:122`) e entra no `_snapshot_for_hash` como `"approver"` — um certificado
  pode nomear um gestor que nunca aprovou nada.
- **Botões do form da qualificação sem `groups=`** (`views/qualificacao_views.xml:43,50,57`):
  `action_mark_approved`/`_rejected`/`action_cancel` agora sempre levantam `UserError` para
  não-gestor, mas continuam visíveis. Além disso, o grupo Usuário perdeu a capacidade de aprovar
  por esse form — mudança de comportamento não documentada, introduzida pelos guards.

### Migração para o addon (Tasks 2 e 4)
- **Débito de lint herdado da origem.** O `next build` da origem nunca rodou de fato (no worktree
  de origem o `next lint` aborta por conflito de plugin com o `.eslintrc.json` do repo pai). Aqui
  ele roda e acusava 41 erros; os 5 defeitos reais (imports/bindings mortos) foram removidos, e
  `@typescript-eslint/no-explicit-any` virou `"warn"` em `pwa/.eslintrc.json` — o débito fica
  **visível** em toda build, não escondido. Restam ~30 `any` explícitos como warning; tipá-los é
  trabalho futuro, e a regra volta a `"error"` quando isso for feito.
- **`/manifest.json` responde 307 sem sessão.** `pwa/middleware.ts` não isenta `.json` do gate de
  autenticação, então o manifest só é servido depois do login. Comportamento **idêntico à origem**
  (não é regressão da migração), mas afeta os itens E.1/E.2 do bloco E — PWA — de
  `pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md` (manifest e "Add to Home Screen"). A
  decidir: isentar `.json` no matcher do middleware, ou aceitar que o A2HS só funcione pós-login.
- **`POST /api/odoo/.../session/destroy` devolve 502** no carregamento da tela de login (observado
  na Task 4). **Diagnosticado no final review: benigno.** `AuthGuard.forceLogout()`
  (`pwa/components/providers/AuthGuard.tsx:12-29`) dispara esse POST quando `serverUrl` está vazio
  no `authStore`; sem cookie `odoo-target`, `normalizeTarget(undefined)`
  (`pwa/app/api/odoo/[...path]/route.ts:5-10`) cai no `DEFAULT_ODOO_URL = 'http://localhost:8069'`,
  onde nada escuta nesse ambiente — o `fetch` falha e o `catch` devolve o 502 deliberado
  (`route.ts:48-61`). Não indica problema no proxy; não precisa de ação.
- **Proxy de encaminhamento aberto em `/api/odoo/[...path]`.** `pwa/middleware.ts:11` isenta todo
  `/api` do gate de sessão, e `pwa/app/api/odoo/[...path]/route.ts:19-23` honra um header
  `x-odoo-target` fornecido pelo próprio chamador sem validar contra allowlist. Quem alcançar a
  porta 3010 pode fazer o servidor Next buscar qualquer URL arbitrária (inclusive hosts internos da
  rede) e ler a resposta — um SSRF/open proxy clássico. Herdado verbatim da origem
  (`frontend_odoo`), não introduzido pela migração. **Não corrigido nesta wave** — só registrado
  aqui porque não estava documentado em lugar nenhum e o README fala em prontidão para produção.
  A decidir: allowlist de hosts, ou exigir que `x-odoo-target` bata com um valor já gravado em
  cookie assinado no login.
