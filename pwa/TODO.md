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
- ~~Limpeza de neon.~~ **Feita em 2026-09-03.** Saíram do código e do
  `tailwind.config.ts`: paleta `neon`, `bg-gradient-cyber`, `mesh-gradient`,
  sombras `glow-*`/`glass*`, animações `float`/`pulse-glow`/`gradient-shift`,
  a utilidade `.glass` e o texto com gradiente do login (`bg-clip-text`, que o
  DESIGN.md proíbe explicitamente). `NeonBadge` virou `StatusBadge` com tons
  semânticos; `GlassCard` perdeu o vidro e o hover com zoom e virou superfície
  tonal. O `globals.css` também perdeu ~370 linhas de utilitários herdados do
  app de Equipamentos (`*-glow`, `phase-*`, `ib-*`, `dashboard-mode`) — nenhum
  tinha uso aqui, e vários rodavam animação em loop.
- ~~`KindPill`: etiqueta mentia e usava cor como categoria.~~ **Resolvido em 2026-09-04
  (corrigir e neutralizar).** Eram dois defeitos: (a) o chamador passava
  `qualifType="installation"` fixo, então toda etiqueta saía azul escrita "QI" —
  inclusive em coleta de QO, onde exibia "QI·QO"; só o sufixo vinha do dado
  (`docx_section`). (b) As cinco cores codificavam *categoria*, única exceção à
  Regra do Estado depois da limpeza do neon (verde ali significava QD, não
  "coletado").
  Agora `getOsDetail` traz `qualifs` (o `qualification_type` do registro-pai) e a
  etiqueta exibe o tipo verdadeiro, em cinza neutro com `title`/`sr-only` por
  extenso ("Qualificação de desempenho"). O gatilho também mudou: era
  `docx_section` preenchido — campo do template Word, que quase nenhum item tem —
  e passou a ser "a OS mistura mais de um tipo"; numa OS de tipo único a etiqueta
  repetiria a mesma sigla em toda linha. Verificado na OS26-06-0002, que mistura
  QD, Cal e QO. Print antes/depois em
  https://claude.ai/code/artifact/aca3898d-5a98-4c0e-b93a-5b5446f0cde5
- ~~Entradas animadas escondiam o conteúdo.~~ **Corrigido**: os `initial` de
  `framer-motion` partiam de `opacity: 0` (e `scale: 0`) no login e no
  visualizador de PDF. Se a animação não roda — aba em segundo plano, PWA
  retomado do standby, renderizador headless — a tela ficava **em branco**,
  com o conteúdo no DOM e invisível. Foi assim que o print do login saiu preto.
  Agora a entrada é só deslocamento; o conteúdo nasce legível.
- Auditoria de contraste tela a tela ainda não foi feita (só os tokens base).

### Técnico Qualificação
- 👉 **PRÓXIMO PASSO (decidido em 2026-09-04).** **Layout preso em 480px: ruim no notebook.** A casca do app
  (`pwa/app/tecnico/qualificacao/layout.tsx`) tem `max-w-[480px]`, então em
  desktop tudo fica espremido numa coluna estreita no meio da tela, com o
  resto vazio. Relatado pelo dono do produto em 2026-09-04: o técnico nem
  sempre está em campo — às vezes revisa a OS pelo notebook.
  A decidir antes de mexer:
  - até onde a coluna cresce (ex.: `max-w-[480px]` no celular, ~720px em
    tablet, e layout de duas colunas — lista + detalhe da coleta — a partir
    de ~1024px, aproveitando que o detalhe hoje é uma rota separada);
  - se a navegação inferior vira barra lateral em desktop (`sticky bottom-0`
    é padrão de polegar, não de mouse);
  - assinatura no `SignaturePad` desenhada com mouse/trackpad — hoje só foi
    testada com toque;
  - alvos de toque continuam ≥44px (notebook com tela sensível existe), então
    o ganho de espaço vai para densidade de informação, não para encolher
    controle.
  Isto contradiz o que está escrito hoje: `PRODUCT.md` princípio 6 ("Uma mão,
  retrato, luva") e `DESIGN.md` ("Coluna única, sempre; retrato de celular é o
  caso de projeto"). Os dois textos precisam ser reescritos na mesma passada,
  senão a regra volta a proibir o que se quer fazer.
  Verificação: as telas conferidas até hoje foram todas em 390×844/390×900 —
  refazer a passada em 1280×800 e 1920×1080.
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
- ~~Erro de rede aparecia cru pro técnico~~ (`Erro: Request failed with status code 502`).
  **Corrigido**: a tradução vive no interceptor do `odooClient`, então toda tela herda. Distingue
  sem-conexão, 403, 404 e 5xx, e sempre diz que o que ele preencheu continua ali. Conferido
  derrubando o container do Odoo: "O servidor não respondeu (erro 502). O que você preencheu
  continua aqui — tente de novo em instantes.".
- ~~Leitura de OS não é restrita por técnico.~~ **Decidido em 2026-09-04: fica global mesmo.**
  As `ir.rule` do grupo Técnico têm `perm_read = False`
  (`afr_qualificacao/security/qualificacao_groups.xml:59`) — o escopo é só de escrita, e assim
  permanece: um técnico enxerga as OSs dos colegas quando desliga "Só minhas". O que muda é a
  expectativa registrada: o texto de F.1/F.2 do checklist, que prometia isolamento de leitura,
  precisa ser reescrito para descrever o filtro do cliente, não uma record rule.
- ~~Item `kind='outro'` sem anexo estourava ValidationError.~~ **Resolvido em 2026-09-03.**
  O backend `_check_required_has_file` sempre exigiu `file` para qualquer item em
  `state='collected'`, mas o front tratava `outro` como anexo opcional — salvar um item "Outro"
  sem foto estourava na cara do técnico, em campo, depois de ele já ter escrito a observação.
  Decisão: alinhar pelo backend (item coletado é item com evidência anexada). `outro` entrou em
  `FILE_REQUIRED_KINDS`. **Verificado na tela em 2026-09-04** com um item `outro` semeado na OS 4:
  o campo aparece como "Arquivo *", salvar sem anexo mostra `Anexe arquivo antes de salvar` e não
  dispara RPC nenhum (contador do proxy: 105 → 105); com anexo, grava `state=collected` com
  `filename` e `relatorio_id`. Item de teste apagado depois.
- ~~"Só minhas" off esconde os rascunhos.~~ **Decidido em 2026-09-04: é regra mesmo.** Rascunho
  alheio não entra na lista do técnico — desligar o filtro serve para ver as OSs *em andamento e
  agendadas* dos colegas, não o rascunho de todo mundo. Pendente só a formalização: comentar a
  intenção em `pwa/app/tecnico/qualificacao/page.tsx:23` (`filterMine ? drafts : []`) e ajustar o
  texto de H3/A.3 do checklist, que hoje descreve como se desligar o filtro sempre mostrasse
  *mais* cards.
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

### Backend `afr_qualificacao` — autorização

**Os cinco achados foram fechados em 2026-09-03 (v16.0.7.4.0)**, depois que as
contas puramente técnicas passaram a existir (Bloco F) e os tornaram
alcançáveis de verdade:

- `cycle` e `malha` ganharam o par de `ir.rule` (restritiva no Técnico via
  `qualificacao_id.os_id.tecnico_default_user_id` + permissiva no grupo
  Usuário). Era o achado grave: técnico alheio editava ciclo de qualificação
  aprovada e o certificado do cliente virava `tampered`.
- `collect.item` ganhou o mesmo par (write + create) e **perdeu `unlink` na
  ACL do Técnico** — apagar evidência não é ação de campo.
- `approver_id` passou a exigir Gestor (`_check_approver_write` no mixin de
  segurança, chamado do `write()` de `afr.qualificacao` e `.os`). O campo
  entra no `_snapshot_for_hash`, então dava pra assinar um certificado
  nomeando um gestor que nunca aprovou nada.
- Report do certificado ganhou `groups_id` = grupo Usuário (Gestor herda):
  `/report/pdf/...` e o menu Imprimir contornavam o gate de `state ==
  'approved'`. Decisão de produto: emitir certificado é ato de escritório.
- Botões Aprovar/Reprovar/Cancelar da view ganharam `groups=` — já levantavam
  `UserError` para não-Gestor, mas continuavam visíveis.

Cobertura: `tests/test_authorization_scope.py`, 14 testes.

### Contexto original (auditoria de 2026-07-27) — histórico

⚠️ **Nada aqui é pendência.** Os cinco achados desta auditoria adversarial
foram todos fechados em 2026-09-03 (ver a seção acima); o texto fica só como
registro do que existia e de por que demorou.

Na época **nenhum era explorável**: os 5 usuários do banco tinham os três
grupos (Técnico/Usuário/Gestor) por implicação, então não existia conta
puramente técnica — e com o grupo Usuário a `ir.rule` permissiva anula o
lockdown inteiro. Os achados só viraram alcançáveis quando o Bloco F do
checklist criou as contas só-Técnico, e foi aí que foram corrigidos.

Os cinco: `cycle`/`malha` com write sem `ir.rule` (o grave — técnico alheio
adulterava ciclo de qualificação já certificada e o certificado do cliente
virava `tampered`); `collect.item` com CRUD irrestrito, unlink incluído;
report de certificado sem `groups_id`, deixando `/report/pdf/...` e o menu
Imprimir contornarem o gate de `state == 'approved'`; `approver_id` gravável
por técnico, permitindo certificado que nomeia gestor que nunca aprovou; e os
botões Aprovar/Reprovar/Cancelar visíveis para quem só receberia `UserError`.

### Migração para o addon (Tasks 2 e 4)
- **Débito de lint herdado da origem.** O `next build` da origem nunca rodou de fato (no worktree
  de origem o `next lint` aborta por conflito de plugin com o `.eslintrc.json` do repo pai). Aqui
  ele roda e acusava 41 erros; os 5 defeitos reais (imports/bindings mortos) foram removidos, e
  `@typescript-eslint/no-explicit-any` virou `"warn"` em `pwa/.eslintrc.json` — o débito fica
  **visível** em toda build, não escondido. Restam ~30 `any` explícitos como warning; tipá-los é
  trabalho futuro, e a regra volta a `"error"` quando isso for feito.
- ~~`/manifest.json` respondia 307 sem sessão.~~ **Resolvido em 2026-09-03**: o bypass de
  estáticos do `pwa/middleware.ts` não cobria `.json`/`.webmanifest`, então o manifesto só era
  servido depois do login e o prompt de instalação nunca aparecia. Era comportamento idêntico ao
  da origem, não regressão da migração. Agora responde 200 sem sessão e as rotas do app continuam
  protegidas (307). Confirmado em Chrome de verdade em 2026-09-04 (E.1 do checklist).
- ~~`POST /api/odoo/.../session/destroy` devolve 502 na tela de login.~~ **Benigno, diagnosticado
  e encerrado.** `AuthGuard.forceLogout()`
  (`pwa/components/providers/AuthGuard.tsx:12-29`) dispara esse POST quando `serverUrl` está vazio
  no `authStore`; sem cookie `odoo-target`, `normalizeTarget(undefined)`
  (`pwa/app/api/odoo/[...path]/route.ts:5-10`) cai no `DEFAULT_ODOO_URL = 'http://localhost:8069'`,
  onde nada escuta nesse ambiente — o `fetch` falha e o `catch` devolve o 502 deliberado
  (`route.ts:48-61`). Não indica problema no proxy; não precisa de ação.
- ~~Proxy de encaminhamento aberto em `/api/odoo/[...path]`.~~ **Resolvido em 2026-09-04.**
  O middleware isenta todo `/api` do gate de sessão e a rota honrava um header `x-odoo-target`
  vindo do próprio chamador, sem validação: quem alcançasse a porta 3010 fazia o servidor Next
  buscar qualquer URL — inclusive host interno que só ele enxerga — e lia a resposta (SSRF/open
  proxy). Herdado verbatim da origem `frontend_odoo`, não introduzido pela migração.
  Fechado com allowlist de origens (`lib/server/odooTarget.ts`, 17 testes): fixar um host não
  servia, porque o técnico digita o servidor no login e o mesmo build atende instâncias
  diferentes. Agora `ODOO_ALLOWED_ORIGINS` declara as origens válidas; `ODOO_URL` sozinho vale
  como lista de um item; em `NODE_ENV=development` loopback e rede privada entram sem
  configuração; fora isso **falha fechado** (403 com mensagem dizendo o que configurar).
  Também fechados no mesmo passo: URL com credenciais embutidas (`http://permitido@evil.tld`),
  esquema não-http, e redirecionamento que saía da allowlist depois do primeiro salto (a origem
  final da resposta é reconferida). O cookie `odoo-target` virou `HttpOnly` — só o servidor o lê,
  então script na página não reescreve mais o destino do proxy.
  Verificado com o app rodando: `x-odoo-target: http://example.com` → 403,
  `http://169.254.169.254` (metadata de nuvem) → 403, e o fluxo normal (listar bancos, login,
  navegação, imagens das coletas) intacto.
