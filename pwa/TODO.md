# TODO — PWA Técnico

## Pendente

### Publicação em produção (labquali) — levantado em 2026-09-05

> **2026-09-07: o tema claro foi para produção.** 35 commits (`a9abbc1` → `a48d216`),
> container do PWA reconstruído, backup `odoo-labquali_pre-tema-claro_20260907_1554.dump`
> antes. Verificado no ar: zero `text-white/N` no HTML servido do login (era o defeito de
> branco-sobre-branco) e o deep link preservando destino
> (`/login?next=%2Ftecnico%2Fqualificacao%2F4%2Fcoleta%2F213`).

- ~~`ODOO_ALLOWED_ORIGINS` faltava no `docker-compose.yml` e na seção "Produção" do
  README.~~ **Resolvido.** A variável é obrigatória (sem ela o proxy `/api/odoo` falha
  fechado com 403 e o app não fala com Odoo nenhum), mas nem o compose passava, nem o
  README citava: quem seguisse a documentação ao pé da letra subia um app 100% quebrado.
  Agora o compose usa `${ODOO_ALLOWED_ORIGINS:?...}` e **recusa subir** sem ela
  (verificado: `docker compose config` falha), e o README abre a seção com o `export`.
  Junto: o `ports:` virou `127.0.0.1:3010:3000` — publicar em `0.0.0.0` deixaria o app
  acessível em HTTP puro por fora, contornando o TLS.
- ~~**BLOQUEIO: o labquali roda `afr_qualificacao` 16.0.7.0.0; o PWA exige 16.0.7.4.0.**~~
  **Falso desde antes de 2026-09-07.** Conferido por RPC nessa data: o `odoo-labquali`
  está com `installed_version` = `16.0.7.4.0`, e o código em `/home/labquali` também.
  O upgrade aconteceu em algum momento entre 05/09 e 07/09 e este item ficou velho —
  **cuidado com bloqueio registrado: confira antes de acreditar.** Junto vieram as
  correções de autorização, incluindo a grave (técnico alheio editava ciclo de
  qualificação aprovada).

- ~~**BLOQUEIO: Bloco E do checklist nunca executado**~~ **Fechado em 2026-09-06**, pelo user,
  depois de o app subir em HTTPS: testado no desktop, no celular e **instalado no Android**,
  tudo funcionando. Era a parte "PWA" do PWA e o último bloqueio da entrega; até então só o
  E.1 (manifest 200) tinha sido conferido, porque Chrome headless ignora service worker.
- ~~**TLS: script pronto, sem acesso pra rodar.**~~ **Duas coisas erradas aqui, as duas
  corrigidas em 2026-09-07.**
  (a) *"A chave SSH desta máquina é recusada em `191.252.113.190`"* — o que é recusado é
  `root@191.252.113.190`. O acesso funciona pelo **alias `fitadigital`** do
  `~/.ssh/config` (user `fitadigital`, key `id_ed25519_fitadigital`), que já estava
  documentado na memória do projeto. Ninguém tinha tentado o alias.
  (b) O TLS **já está no ar**: o PWA é publicado em
  `https://labquali.afrsistemas.com.br/login` e `/tecnico` por **Apache + Let's Encrypt**
  (`/etc/apache2/sites-enabled/012-labquali-le-ssl.conf`), com `ProxyPass` de `/tecnico`,
  `/login`, `/_next` e `/api/odoo` para `127.0.0.1:3010`, declarados **antes** do
  `ProxyPass /` do Odoo. O `deploy/setup-pwa-proxy.sh` nunca precisou rodar.

  **Receita de deploy do PWA no servidor** (mapeada 2026-09-07):
  ```bash
  ssh fitadigital
  # backup antes de qualquer upgrade de módulo:
  docker exec odoo_qualif_db pg_dump -U odoo -Fc odoo-labquali > /home/labquali/data/backups/<nome>.dump
  cd /home/labquali && git merge --ff-only origin/main        # clone do afr_qualificacao
  cd /home/labquali/pwa && docker compose build && docker compose up -d
  ```
  O container é `afr_qualificacao_pwa` (compose em `/home/labquali/pwa`, serviço `pwa`,
  bind `127.0.0.1:3010`, healthcheck próprio). O `.env` de lá já tem `ODOO_ALLOWED_ORIGINS`.

- **`GROQ_API_KEY` vazada, rotação adiada por decisão de 2026-09-05.** Subir sem chave é
  degradação limpa e documentada (IA desligada, resto normal). Não subir com a chave antiga.


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
- ~~Contraste ruim no MODO CLARO — relatado pelo user em 2026-09-06, usando o app
  publicado.~~ **Resolvido em 2026-09-06.** Era exatamente a suspeita registrada
  abaixo: o tema claro nunca tinha sido medido contra o piso AA, porque todo shade
  cru do Tailwind espalhado pelos componentes (`text-emerald-300`,
  `bg-cyan-500/15`, `text-violet-300`, ...) foi escolhido olhando só o escuro.
  Migração trocou shade cru por token semântico (`--ok`/`--warn`/`--danger`/
  `--info` + `-surface`, mais os papéis `--background`/`--card`/
  `--muted-foreground`) nos dois temas, com o valor do **claro** escolhido pelo
  piso 4.5:1 (texto) / 3:1 (foco e fronteira de controle) — não só copiado do
  escuro. Medido antes/depois com o script de auditoria (ver item abaixo):
  397 → 140 ocorrências totais no claro (o 397 original não foi decomposto
  por categoria; o 140 de hoje foi — 106 são borda/anel decorativo, sem piso,
  34 são o cromo escuro fixo do `PdfViewerModal`, falso positivo por
  construção, e **0 são texto real abaixo do piso**, ver
  `docs/AUDITORIA-CONTRASTE.md`). O que trava a volta: `temaTokens.test.ts`
  recusa shade cru de cor de estado fora de
  `PERMITIDO_TEMA` (exceções nomeadas e justificadas), e `npm run
  audit:contrast` mede a razão real dos dois temas a qualquer momento — sem
  browser, em segundos.
- ~~Auditoria de contraste tela a tela ainda não foi feita (só os tokens
  base).~~ **Resolvido em 2026-09-06.** Auditoria estática versionada em
  `scripts/contrast-audit.mjs` (`npm run audit:contrast`, aceita `THEME=dark`)
  — varre `app/**/*.tsx` + `components/**/*.tsx`, resolve token/paleta real e
  calcula a razão WCAG composta sobre o fundo. Método, limitações conhecidas e
  tabela de valores em `docs/AUDITORIA-CONTRASTE.md`. Verificação visual
  complementar (os dois temas, rota a rota, com o app rodando) capturada em
  `docs/baseline-escuro/` (referência do escuro **antes** de qualquer mudança:
  `login-1.png`, `login-2.png`, `lista.png`, `historico.png`, `perfil.png`,
  `os-4.png`) — usada para confirmar que o escuro não mudou de aparência além
  do que foi explicitamente autorizado ao longo do plano. Comparação
  pixel-a-pixel contra a baseline, o que foi coberto e o que ficou de fora
  estão em `docs/AUDITORIA-CONTRASTE.md`.

### Técnico Qualificação
- **Notificação push no celular — levantado em 2026-09-06, NÃO decidido.** É viável: o app já
  tem service worker registrado e instalável, que é o pré-requisito. Falta, do lado do
  cliente: pedir permissão, assinar com `PushManager.subscribe` usando uma chave VAPID, e
  tratar o evento `push` no service worker. Do lado do Odoo: um endpoint para guardar a
  assinatura por usuário (endpoint + chaves p256dh/auth), e o disparo a partir de algum
  gatilho de negócio. Custo maior não é o código, é decidir **o que** notifica e manter as
  assinaturas vivas (elas expiram e precisam ser renovadas/limpas).
  Ressalvas: no iOS só funciona com o app instalado na tela de início (Safari 16.4+); no
  Android funciona no Chrome instalado, que é o caso já testado. Nada disso está começado.
- ~~**Voltar depois de fechar o relatório caía no formulário já fechado.**~~ **Resolvido em
  2026-09-05** (relatado em campo pelo user). Era `router.push` no `onSuccess` do fechamento:
  a tela concluída ficava no histórico, o botão voltar do navegador levava de volta a ela,
  tentar fechar de novo dava erro no servidor, e só o segundo "voltar" chegava na OS. Virou
  `router.replace`. Varrendo o resto apareceram **mais dois do mesmo defeito**, corrigidos
  junto: o **logout** (voltar trazia a tela autenticada sem sessão, com o `AuthGuard`
  expulsando depois — origem do POST de logout com 502 que já estava catalogado como benigno)
  e o **login** (voltar levava o técnico já autenticado de volta ao formulário de
  credenciais).
  Cobertura, a pedido do user, pensada para pegar o **próximo**, não só estes três:
  `FinalizarPage.test.tsx`, `PerfilLogout.test.tsx` e `LoginRedirect.test.tsx` (comportamento,
  incluindo o caso oposto — falhar ao finalizar não pode navegar) mais
  `navegacaoHistorico.test.ts`, que lê o código-fonte e **exige que todo `router.push` esteja
  declarado com justificativa**, recusa entrada morta na lista de permitidos e proíbe
  `router.push` dentro de `onSuccess`. As quatro guardas foram verificadas por mutação:
  desfiz cada `replace` e confirmei a falha antes de reverter.
- ~~**Rolagem longa pra ver o que já foi coletado.**~~ **Resolvido em 2026-09-05.**
  As duas seções eram empilhadas, então com 25 itens ver as feitas custava rolar a lista
  inteira de pendentes. Entrou `ColetaFilter`: filtro segmentado grudado no topo da coluna
  (`Pendentes N` / `Feitas N`), um toque troca o recorte. **Não é aba** — `role="group"` com
  `aria-pressed`, nunca `tablist`; o DESIGN.md ganhou a seção que registra a diferença e o
  porquê do ARIA. Os `<h2>` visíveis viraram `sr-only` (o filtro já mostra rótulo e
  contagem). Três regras de estado: nasce em `Feitas` se não há pendente ou se o deep link
  já traz uma coleta feita aberta; abrir coleta do outro segmento troca o segmento sozinho
  (senão a linha com `aria-current` ficaria escondida — o defeito recém-fechado voltando por
  outra porta); segmento vazio diz o que houve. 7 testes novos; conferido no browser a
  1280px: filtro gruda com `scrollTop` 800, troca de segmento, e voltar pelo histórico de
  uma coleta feita para uma pendente traz o segmento junto. O rótulo do segundo segmento é
  "Realizadas".
- ~~**Grupos de equipamento não recolhiam.**~~ **Resolvido em 2026-09-05, na mesma passada.**
  `EquipmentHeader` virou o próprio controle do grupo: `<button aria-expanded aria-controls>`
  com chevron, alvo de 44px. Não é `<details>` porque o grupo precisa abrir por decisão de
  fora (abrir uma coleta expande o grupo dela). Regras: recolhido por padrão só quando há
  mais de um grupo no segmento; grupo único nasce aberto; o cabeçalho mostra o progresso do
  **equipamento** ("10 de 23", `tabular-nums`), não a contagem do recorte; grupo fechado não
  gruda nem monta os cartões (o container do `aria-controls` fica no DOM, vazio). Dois
  defeitos achados no browser e corrigidos: o cabeçalho grudado subia 2px por baixo do filtro
  (o filtro tem 54px, não 52 — o fio de 1px conta) e o tom translúcido deixava os cartões
  atravessarem o nome do equipamento (agora camada de tom sobre `bg-background`). 10 testes
  novos.
- ~~**`sticky` não funcionava abaixo de 1024px.**~~ **Resolvido em 2026-09-05**, com o
  aval do user. O invólucro do `app/tecnico/qualificacao/layout.tsx` usava `min-h-screen`,
  crescia com o conteúdo, quem rolava era a janela e o scrollport do `<main overflow-auto>`
  nunca rolava — todo `sticky` lá dentro ficava inerte (medido a 375px: o filtro saía da tela
  junto com a lista). Agora o invólucro tem `h-dvh min-h-0 overflow-hidden` em toda largura,
  o `main` ganhou `min-h-0` e a coluna interna também. Dois efeitos que precisaram de
  conserto próprio, os dois vistos no browser:
  - O `p-3` saiu do `main` e foi para um wrapper interno: sticky ancora na borda do padding
    do scrollport, então com o padding no `main` sobrava uma faixa de 12px acima do filtro
    por onde o conteúdo continuava passando.
  - Esse wrapper precisou de `h-full`: o `SplitPane` usa `lg:h-full` pra dar altura à linha
    do grid, e sem altura definida no wrapper a rolagem independente das duas colunas parava
    de funcionar (medido: `scrollTop` da coluna travado em 0).
  Os deslocamentos de `sticky` viraram `top-0` (filtro) e `top-[54px]` (cabeçalho de grupo),
  sem prefixo de breakpoint — o cabeçalho do app está fora do scrollport, então o `top-14`
  que havia compensava algo que nunca esteve no caminho. O mesmo `top-14` obsoleto do
  Histórico foi corrigido (e o `bg-background/80 backdrop-blur` virou fundo opaco).
  Efeito colateral aceito: a barra de navegação inferior não rola mais junto, fica sempre à
  vista. Medido depois: a 375px o `main` rola (500 de 1261) e a janela não; filtro fixo em
  51px, grupo em 105px, nav no rodapé. A 1280px a coluna da lista voltou a rolar sozinha
  (`scrollTop` 504) com filtro em 63px e grupo em 117px. `TecnicoShell.test.tsx` (2 testes)
  trava a decisão por classe, já que o happy-dom não faz layout.
  Ressalva: o agrupamento do Histórico não pôde ser visto rolando — a conta de teste não tem
  relatório fechado; a mudança lá é só o deslocamento do `sticky`.
- Busca por nome do ciclo na lista de coletas: com 25 itens, achar um ciclo específico ainda
  é rolagem dentro do segmento. Decidido em 2026-09-05 ficar fora do escopo do filtro.
- ~~**Layout preso em 480px: ruim no notebook.**~~ **Resolvido em 2026-09-04.**
  A casca do app (`pwa/app/tecnico/qualificacao/layout.tsx`) cresce por
  breakpoint: `<640px` → `max-w-[480px]`, `640–1023px` → `max-w-[720px]`,
  `≥1024px` → coluna lateral de 200px + área de conteúdo (grade OS
  lista/detalhe até `max-w-[1440px]`, demais páginas até `max-w-[880px]`). A
  navegação vira barra lateral a partir de 1024px; alvos de toque seguem
  ≥44px em toda largura. `PRODUCT.md` princípio 6 e `DESIGN.md` (Key
  Characteristics, Navigation, Cards/Containers) foram reescritos na mesma
  passada para permitir o layout. Spec:
  `docs/superpowers/specs/2026-09-04-pwa-tecnico-layout-desktop-design.md`.
- ~~**Bloco de comemoração viola o DESIGN.md.**~~ **Resolvido em 2026-09-05.** O bloco
  tinha migrado de `[osId]/page.tsx` para `[osId]/(painel)/layout.tsx` com o painel
  persistente, e lá seguia com gradiente esmeralda, dois blocos `animate-pulse` com
  `blur-3xl`, `animate-bounce` e 🎉🏆🎊 — três Don'ts do DESIGN.md contra o "a tela não
  comemora, informa" do PRODUCT.md. Virou confirmação sóbria: superfície tonal esmeralda
  com fio de 1px, ícone `CheckCircle2` do lucide, "Todas as coletas concluídas", contagem
  em `tabular-nums` e a linha de estado em texto puro (o pill `bg-muted/70 ring-1` dentro
  do bloco era cartão aninhado, outro Don't). De quebra, a pluralização quebrada
  ("2 de 2 **items** coletados") saiu junto. 1 teste novo em `PainelLayout.test.tsx`
  varre o DOM por emoji, `animate-pulse`, `animate-bounce`, `bg-gradient-to-br` e
  `blur-3xl`. Conferido na tela na OS26-08-0005-1 (tudo coletado, sem relatório aberto).
- ~~CollectedCard: mostrar campo `description` (observação) nos itens já coletados
  (OsDetail + RelatorioDetail).~~ **Já estava feito** (constatado em 2026-09-05):
  `CollectedCard.tsx:95-99` renderiza a observação, `description` está na lista de campos
  do `getOsDetail`/`getRelatorioDetail` (`lib/odoo/tecnico.ts:181,306`), e os dois
  consumidores usam o mesmo componente. Item estava vencido no TODO.
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
- ~~Lista voltava ao topo a cada clique no desktop.~~ **Resolvido em 2026-09-04.**
  `SplitPane` e `ColetaList` eram renderizados por cada página, então o Next
  desmontava e remontava a coluna esquerda a cada navegação e o painel renascia
  com `scrollTop 0` — a linha marcada sumia da vista justo quando deveria
  orientar. As duas rotas passaram para um route group `(painel)` cujo
  `layout.tsx` é dono do `SplitPane`, do `useOsDetail` e da coluna esquerda
  inteira; as páginas ficaram só com o painel direito. As rotas de `relatorio/`
  seguem fora do grupo. Medido no browser: `scrollTop` 2405 antes e 2405 depois
  do clique, no mesmo nó do DOM. Spec em
  `docs/superpowers/specs/2026-09-04-pwa-tecnico-painel-persistente-design.md`.
- ~~**Item já coletado abre sem marcação no painel.**~~ **Resolvido em 2026-09-05.**
  `ColetaList` agora passa `selected={item.id === selectedId}` também para o
  `CollectedCard`, que aplica `variant="selected"` e `aria-current="true"` **no cartão** —
  não num link, como faz o `ColetaCard`: aqui o único link é "Recoletar", que some quando
  não há relatório aberto, e o deep link para a coleta continua valendo nesse caso.
  2 testes em `ColetaList.test.tsx`; conferido no browser em 1280px nos dois ramos — com
  relatório aberto (OS 4, item 213, clicando em "Recoletar") e **sem** relatório aberto
  (OS 4830, deep link em `/coleta/3519`, onde não existe link nenhum para a coleta): o
  painel direito diz "Inicie um relatório do dia antes de coletar" e o cartão coletado
  aparece marcado do mesmo jeito.
- ~~**Troca do painel direito não é anunciada.**~~ **Resolvido em 2026-09-05.**
  `(painel)/layout.tsx` ganhou uma região viva (`aria-live="polite"`, `aria-atomic`,
  `sr-only`) que diz "Coleta aberta: <nome>". Dois cuidados que o teste trava: ela fica
  **fora** do `SplitPane` (a coluna da lista recebe `hidden` abaixo de 1024px, e conteúdo
  em `display:none` não é anunciado — ficaria inerte justo no celular) e o nó existe
  sempre, com o texto vazio quando nada está aberto (inserir região e texto juntos não
  dispara anúncio na maioria dos leitores). 3 testes em `PainelLayout.test.tsx`;
  conferido no browser lendo `textContent` da região depois do clique.
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
- **Deep link para uma coleta perde o destino no login.** Abrir
  `/tecnico/qualificacao/<osId>/coleta/<itemId>` sem sessão manda pro login e,
  depois de autenticar, cai na home em vez da coleta pedida — o middleware não
  guarda a URL original. Atrapalha suporte ("abre este link") e o retorno do PWA
  depois de a sessão expirar. Apontado pela bateria de aceitação do painel
  persistente (2026-09-05); é anterior àquele trabalho.

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
- ~~`next build` quebrado no `main` por binding morto.~~ **Corrigido em 2026-09-05.**
  `const { data, isLoading, isFetching, ... } = useOsDetail(...)` no `(painel)/layout.tsx`:
  `isFetching` deixou de ser usado quando `atualizandoManual` entrou, e
  `@typescript-eslint/no-unused-vars` é **erro** — a build de produção já falhava sem
  estas mudanças. Verificado com `git stash` (arquivos rastreados de volta ao conteúdo de
  `20add57`): o mesmo erro aparecia em `33:28`, e o lint só lê o fonte, então nada do
  working tree entrava na conta. Binding removido.
- ~~**Débito de lint herdado da origem.**~~ **Fechado em 2026-09-05.** O `next build` da origem
  nunca rodou de fato (lá o `next lint` aborta por conflito de plugin com o `.eslintrc.json` do
  repo pai). Aqui ele roda e acusava 41 erros; os 5 defeitos reais (imports/bindings mortos) saíram
  na migração e `@typescript-eslint/no-explicit-any` virou `"warn"` pra deixar o resto visível.
  Agora **o código de produção não tem mais nenhum `any` explícito** e a regra voltou a `"error"`.
  Os dez que restavam eram dois padrões: `catch (e: any)` seguido de `e.message` num toast (seis
  lugares) e `let json: any` no retorno das rotas de IA (dois). Viraram `lib/utils/erro.ts`
  (`mensagemDoErro`/`nomeDoErro`, 10 testes) e tipos de resposta declarados. O `any` calava o
  compilador, não o problema: `e.message` em algo que não é `Error` põe `undefined` no toast, e
  erro que atravessa realm (worker, iframe, JSON de API) não passa em `instanceof Error` — o
  helper cobre os dois e nunca devolve string vazia.
  Junto saiu `error?.response?.status` sobre `any` no interceptor do `odooClient`: virou leitura
  passo a passo (`statusHttp`), e `mensagemDeFalha` ganhou os 8 testes que nunca teve — as frases
  em pt-BR que o técnico lê quando a rede cai não tinham nada segurando. Conferido de ponta a
  ponta parando o container do Odoo: "O servidor não respondeu (erro 502). O que você preencheu
  continua aqui — tente de novo em instantes." (container religado depois).
  **Ressalva:** em arquivo de teste a regra fica `off` por `overrides`. Ali `as any` é honesto — o
  fixture é dublê deliberadamente parcial (`{data, isLoading} as any` no lugar do retorno inteiro
  do React Query) e escrever o objeto completo afogaria a asserção. São ~52 ocorrências, todas em
  teste.
- **5 warnings de `@next/next/no-img-element` continuam.** São `<img>` de foto de coleta e de logo,
  servidos pelo proxy `/api/odoo` com sessão. Trocar por `next/image` obrigaria a passar pelo
  otimizador (mais um salto, `remotePatterns`, custo) para imagem autenticada que o app precisa
  poder mostrar offline — provavelmente a escolha certa é ficar com `<img>` e silenciar com
  motivo, não migrar. Decidir: hoje são ruído permanente na build, que é justo o padrão que este
  item acima combateu.
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
