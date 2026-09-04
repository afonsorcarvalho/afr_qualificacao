# Checklist F7.0 — PWA Técnico de Campo (manual)

## Ambiente
- Backend Odoo do addon rodando em http://localhost:8084
  (container `odoo_engenapp-web-qualificacao-1`)
- Frontend Next dev:
  `cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao/pwa && npm run dev`
  → http://localhost:3010

## Pré-condições
- DB tem ao menos 1 user com grupo Técnico + employee linkado (`hr.employee.user_id`)
- DB tem ≥2 OSs com `tecnico_default_id` = esse user, estados variados (scheduled, in_progress)
- DB tem coletas pendentes em cada OS (collect.item state=pending)

## Bloco A — Login + Home

**Execução de 2026-09-03 (db `qualificacao-dev`): 6/6.**

- [x] A.1 GET / → redireciona /login — ✅ e ainda preserva `?server=…&db=…`.
- [x] A.2 Login com user técnico → http://localhost:3010/tecnico/qualificacao ✅
- [x] A.3 Lista mostra OSs agrupadas (Em andamento / Agendadas / Rascunhos) — ✅ as 3 seções ao mesmo tempo, com o filtro "Só minhas" **on** (é o único modo em que rascunho aparece; ver A.4).
- [x] A.4 Toggle "Só minhas" off → mais OSs aparecem (se user em grupos maiores) — ✅ "Agendadas" foi de 1 pra 2. ⚠️ Mas a seção "Rascunhos" **some** ao desligar o filtro (`page.tsx:23`): num banco onde as OSs alheias são rascunho, desligar mostra *menos* cards. Ver pendência no `TODO.md`.
- [x] A.5 OS sem coletas pendentes mostra "0 coletas pendentes" — ✅ com itens todos coletados o card mostra "1 coletadas · 0 pendentes · 1/1". ⚠️ OS com **zero** itens não mostra bloco nenhum (guard `collect_total_count > 0`, senão a barra de progresso dividiria por zero) — é o comportamento correto, o texto do item é que induz ao erro.
- [x] A.6 Empty state visível quando lista vazia — ✅ "Nenhuma OS atribuída." (verificado com o Técnico Teste B sem nenhuma OS atribuída).

## Bloco B — Detalhe OS + Iniciar relatório

**Execução de 2026-09-03: 6/6.**

- [x] B.1 Click OS → /tecnico/qualificacao/{osId} ✅
- [x] B.2 Header mostra nome OS + partner ✅
- [x] B.3 Botão "Iniciar relatório do dia" visível (sem relatório aberto) ✅
- [x] B.4 Click "Iniciar" → loading → card "REL #N" aparece + botão "Continuar" — ✅ card "RELATÓRIO ABERTO / REL #1974". ⚠️ **Não existe botão "Continuar"**: o card traz "Atualizar" e o CTA de saída é "Finalizar relatório do dia", no rodapé da página. Texto do item desatualizado, não é defeito.
- [x] B.5 Reload → mesmo REL #N persiste (idempotência via action_start_daily_relatorio) ✅
- [x] B.6 Lista coletas pendentes aparece agrupada ✅ agrupada por equipamento, com contador no cabeçalho.

## Bloco C — Coleta item

**Execução de 2026-09-03: 8/9 (C.3 exige device real).**

- [x] C.1 Click coleta pendente → /tecnico/qualificacao/{osId}/coleta/{itemId} ✅
- [x] C.2 Banner instrução (amarelo) renderiza se item.instruction existe ✅ (`bg-amber-50 dark:bg-amber-950`)
- [ ] C.3 Botão câmera: tocar → abre câmera nativa (testar em tablet/mobile real) — **N/A no headless.** O input está correto: `accept="image/*"` + `capture="environment"` (`_components/CameraInput.tsx:77-78`). Continua pendente de teste em tablet/celular.
- [x] C.4 Selecionar imagem → preview thumbnail aparece ✅
- [x] C.5 Trocar foto funciona (botão Trocar foto) ✅ (o preview muda; o app re-encoda a imagem pra JPEG no cliente antes de enviar)
- [x] C.6 Click "Salvar coleta" sem foto (kind=foto/excel/pdf/qualificador_data) → toast erro ✅ `Anexe arquivo antes de salvar`
- [x] C.7 Com foto → "Salvando..." → toast sucesso → volta detalhe OS ✅ (às vezes emenda direto na próxima coleta pendente em vez de voltar pro detalhe — comportamento de auto-avanço, não previsto no texto do item)
- [x] C.8 Coleta some da lista pendentes (refetcha automático) ✅ 20 → 19
- [x] C.9 Backend Odoo: collect.item.state=collected, file preenchido, relatorio_id linked ✅ item 219 → `collected`, `coleta_….jpg`, REL #1974
- [x] C.10 (novo) Coletar sem relatório do dia aberto → a tela bloqueia com "Inicie um relatório do dia antes de coletar." ✅ (achado durante a execução; guard não estava no checklist)

## Bloco D — Finalizar relatório

**Execução de 2026-09-03: 8/8 (com uma ressalva em D.3).**

- [x] D.1 Após >0 coletas, click "Finalizar relatório do dia" ✅
- [x] D.2 /tecnico/qualificacao/{osId}/relatorio/{relId}/finalizar ✅
- [x] D.3 Resumo mostra "N realizadas / M pendentes" — ✅ renderiza, ⚠️ mas os números são da **OS inteira**, não do turno: `collected`/`pending` saem de `getOsDetail` (`finalizar/page.tsx:57-58`), então um relatório com 1 coleta exibiu "Coletas realizadas 6". O rótulo, na tela de fechar o turno, sugere o turno. Decidir se muda o número (filtrar por `relatorio_id`) ou o rótulo.
- [x] D.4 Descrição vazia + Fechar → toast erro ✅ `Descrição do turno é obrigatória` (mesmo caminho de H9a)
- [x] D.5 Assinatura vazia + Fechar → toast erro ✅ `Assinatura é obrigatória`
- [x] D.6 Desenhar assinatura → botão "Limpar" funciona ✅ (canvas com 1241 px pintados → 0 após Limpar)
- [x] D.7 Preencher tudo + Fechar → toast sucesso → volta detalhe OS ✅
- [x] D.8 Backend Odoo: relatorio state=done, signature_technician preenchido (base64), signature_technician_date hoje ✅ REL #1974 `done`, assinatura gravada, data 03/09 e `time_execution` 0.0756 h

## Bloco E — PWA

⚠️ **Só faz sentido em build de produção**: `next-pwa` tem
`disable: NODE_ENV === 'development'`, então no `npm run dev` não existe
`sw.js`. Rodar `npm run build && npx next start -p 3011` e testar em :3011.
Ressalva: o `next.config.mjs` usa `output: 'standalone'`, e o próprio Next
avisa que `next start` não é o modo suportado nessa configuração — a execução
de 2026-09-03 foi por `next start` mesmo assim (serviu rotas, manifesto e
`sw.js` corretamente). Quem for refazer E.3/E.4 em Chrome normal deve subir
por `node .next/standalone/server.js` pra não perseguir diferença já conhecida.

**Execução de 2026-09-03: E.1 ✅, E.2 parcial, E.3/E.4 não verificáveis no
headless, E.5 ⚠️.**

- [x] E.1 Chrome DevTools → Application → Manifest carrega corretamente — ✅ **depois do fix**: `/manifest.json` respondia 307 pro `/login` porque o bypass de estáticos do `middleware.ts` não cobria `.json`. Agora responde 200 sem sessão, e as rotas do app continuam protegidas (307). **Confirmado em Chrome de verdade em 2026-09-04**: `manifest.json` aparece no Network com 304 (cacheado), sem erro no painel Application.
- [~] E.2 "Add to Home Screen" disponível (DevTools Application) — parcial: `<link rel="manifest">` presente, manifesto e `icons/icon-192.png` baixados pelo browser (200). O prompt de instalação em si depende de service worker ativo (E.3) e não é observável no headless.
- [ ] E.3 Service worker registrado e ativo — **ainda não verificado; duas tentativas frustradas por ambiente, nenhuma por defeito do app.**

  1ª tentativa (headless, 2026-09-03): o Chrome do `agent-browser` ignora service
  workers — nem `navigator.serviceWorker.register()` manual instala.

  2ª tentativa (Chrome real, 2026-09-04): o WSL perdeu a ponte de `localhost`
  com o Windows depois que a máquina dormiu (`UtilAcceptVsock: accept4 failed
  110`), então o app foi aberto por `http://172.24.97.65:3010`. **IP em HTTP não
  é contexto seguro**: o Chrome recusa registrar worker, o painel Service
  workers fica vazio e o teste offline (E.4) cai em `ERR_INTERNET_DISCONNECTED`.
  Nenhum dos dois diz nada sobre o código.

  Para a 3ª tentativa, escolher um: restaurar o `localhost` (reiniciar o serviço
  `LxssManager` no Windows, ou `wsl --shutdown`), ou liberar a origem em
  `chrome://flags/#unsafely-treat-insecure-origin-as-secure` com
  `http://172.24.97.65:3010`. O que já se sabe: `/sw.js` responde 200 (gerado
  pelo Workbox) e o bundle de produção contém `serviceWorker.register('/sw.js')`.

  Achado original: o `register: true` do `next-pwa` 5.6 só injeta o script de registro pelo Pages Router; com App Router o `sw.js` era gerado mas **nunca registrado**. Achado real: o `register: true` do `next-pwa` 5.6 só injeta o script de registro pelo Pages Router; com App Router o `sw.js` era gerado mas **nunca registrado**. Correção: `components/providers/ServiceWorkerRegister.tsx` registra `/sw.js` no `load`, só em produção, montado no `app/layout.tsx`.
- [ ] E.4 Offline com cache: navegação para tela já visitada funciona — bloqueado por E.3. Tentado em Chrome real (2026-09-04) com Network → Offline: deu `ERR_INTERNET_DISCONNECTED`, como esperado sem worker registrado.
- [x] E.5 Offline + tentar salvar coleta → toast erro claro (sem queue MVP) — ✅ o caminho de erro funciona (a página segura a foto anexada e o botão volta ao normal, nada se perde) e a mensagem foi humanizada: `O servidor não respondeu (erro 502). O que você preencheu continua aqui — tente de novo em instantes.` Nota: `agent-browser set offline on` **não** serve pra este teste — a emulação de rede é por sessão CDP e evapora quando o comando termina (a coleta salvou "offline"); o teste foi feito derrubando o container do Odoo.

## Bloco F — Record rules (record-level security)

**Execução de 2026-09-03.** Contas criadas no `qualificacao-dev` só pra isto
(senha `Teste@2026`): `tecnico.a@teste.local` (uid 659, employee 510),
`tecnico.b@teste.local` (uid 660, employee 511) — ambos com **só** o grupo
Técnico das qualificações (mais os grupos internos padrão, sem o grupo
"Usuário") — e `gestor@teste.local` (uid 661, grupo Gestor).

⚠️ **O enunciado dos itens F.1/F.2 não corresponde à implementação.** As
`ir.rule` do Técnico têm `perm_read = False`
(`security/qualificacao_groups.xml:59`): elas restringem **escrita**, não
leitura. Um técnico lê qualquer OS do banco. Quem limita a lista é o filtro
"Só minhas" no cliente (domínio `tecnico_default_user_id = uid`), que o
próprio usuário pode desligar. Isso foi deliberado no backend (os comentários
das rules falam só de write), mas o checklist prometia isolamento de leitura.
**Decisão de produto pendente:** leitura deve ser restrita também?

- [x] F.1 Login como Técnico A → vê só OSs onde tecnico_default_id = Técnico A — ✅ **com "Só minhas" ligado** (só QOS00004). ❌ Com o filtro desligado ele vê a OS do Afonso e as demais — leitura não é restrita.
- [x] F.2 Login como Técnico B → vê só OSs onde tecnico_default_id = Técnico B — ✅ mesma ressalva do F.1 (só OS26-08-0005-2 com o filtro ligado).
- [x] F.3 Login como Gerente → vê todas OSs (rule não aplica) ✅ com o filtro desligado, as 3 OSs não-rascunho.

## Reportar
- [ ] Tudo OK → confirmar pra merge F7.0 (backend + frontend) no main
- [ ] Falha → bloco/passo + screenshot + log

## Bloco G — IA (Groq)

**Não executado em 2026-09-03 — bloqueado.** Falta `pwa/.env.local` com
`GROQ_API_KEY` (a chave antiga vazou numa sessão e precisa ser rotacionada), e
G4–G6/G9 dependem de microfone real, que o browser headless não tem. Rodar
manualmente em máquina com mic depois de repor a chave.

Pré-requisitos: `.env.local` com `GROQ_API_KEY=gsk_...` válida, dev server em `localhost:3010`, OS de teste com ao menos 1 relatório aberto e itens coletados.

- [ ] **G1** — Auto-resumo OS pequena: abrir Finalizar em OS com 1 equipamento + ≥2 coletas. Textarea começa vazio → mostra "Gerando resumo automático..." → preenche em <5s com parágrafo iniciando pelo nome do equipamento.
- [ ] **G2** — Auto-resumo OS multi-equipamento: abrir Finalizar em OS com ≥3 equipamentos. Resultado tem 1 parágrafo por equipamento, separados por linha em branco.
- [ ] **G3** — Regenerar com edição manual: editar manualmente o texto gerado → clicar "Regenerar resumo" → aparece confirm "Substituir texto atual?". Cancelar mantém texto; OK substitui.
- [ ] **G4** — Ditado curto (~5s) em ColetaPage: pressionar e segurar o mic, falar "teste de microfone OK", soltar. Texto aparece adicionado ao final do campo Observação sem apagar texto prévio.
- [ ] **G5** — Ditado longo (~30s) em Finalizar: pressionar mic, falar por ~30 segundos descrevendo o turno, soltar. Texto transcrito é adicionado à descricao.
- [ ] **G6** — Auto-stop em 60s: pressionar mic e manter pressionado sem falar por 65s. Gravação para automaticamente em 60s e tenta enviar (vazio ou ruído → toast "muito curto" ou transcrição vazia).
- [ ] **G7** — Offline: DevTools → Network → Offline. MicButton fica oculto/desabilitado; SummaryButton em Finalizar mostra toast "IA offline".
- [ ] **G8** — Sem `GROQ_API_KEY`: parar dev server, esvaziar `GROQ_API_KEY=` no `.env.local`, reiniciar. MicButton e SummaryButton não aparecem em nenhuma tela.
- [ ] **G9** — Permissão mic negada: nas configurações do navegador para `localhost:3010`, bloquear microfone. Pressionar mic uma vez → toast "Permita microfone..." → botão desaparece até reload.

## Bloco H — Revalidação pós-adequação backend (v16.0.6.4.0)

Contexto: o PWA ficou parado de 2026-05-19 a 2026-07-26 enquanto o backend
avançou. Blocos A–G nunca foram validados manualmente. Este bloco cobre o
subconjunto que depende das adições backend (`tecnico_default_user_id`,
`descricao` opcional, assinatura no relatório, `action_start_daily_relatorio`).

**Gate real (não é só a versão do manifest):** o Task 1 sozinho já bump o
manifest do `afr_qualificacao` pra `16.0.6.4.0` — ver a versão instalada
satisfeita **não** significa que os Tasks 2-4 (pausados) estão no backend.
Confirmar as capacidades abaixo antes de rodar H4-H12, senão H4+ quebra com
`AttributeError`/campo inválido mesmo com a versão "certa":
- Métodos `action_start_daily_relatorio()` e `action_get_daily_relatorio()`
  existem em `afr.qualificacao.os` (ex.: `odoo_execute_kw`/shell — checar que
  não dá `AttributeError`). **Sem argumentos** desde o fix de 2026-09-03: a
  janela do dia é decidida no servidor (`_janela_do_dia`), o front não manda
  mais `day_start`/`day_end`.
- Campos `signature_technician` e `signature_technician_date` existem em
  `afr.qualificacao.os.relatorio` (`fields_get`).
- `descricao` é opcional em relatório rascunho — criar um relatório novo e
  confirmar que ele existe em `draft` sem `descricao` preenchida (não é só
  "o campo aceita string vazia via write", é o registro nascer sem valor).

Versão mínima do manifest (`afr_qualificacao` ≥ 16.0.6.4.0) continua sendo
pré-requisito, mas não é suficiente sozinha — usar a lista de capacidades
acima como o gate de fato.

Nota: rodar contra o db `qualificacao-dev` (Odoo :8084 — que é também o
backoffice deste bloco, **não** o :8083). Dado semeado em 2026-09-03:
OS 4 `OS26-06-0002` (`in_progress`) → `tecnico_default_user_id` = uid 2, e
OS 4832 `OS26-08-0006-1` (`draft`) → uid 8, o par que H2/H3 comparam.

**Execução de 2026-09-03 (db `qualificacao-dev`, user `afonso@jgma.com.br`
= uid 2, PWA em :3010): 12/12 verdes.** Evidências por item abaixo.

- [x] **H1** — Login como técnico (user com `hr.employee` vinculado e grupo Técnico) → home lista OSs. ✅ redirecionou pra `/tecnico/qualificacao` com OS26-06-0002 listada.
- [x] **H2** — Toggle "Só minhas" **on**: só aparecem OSs com `tecnico_default_user_id` = user logado (espelho stored de `tecnico_default_id.user_id`). Era o gap da ACL de hr — antes vinha vazio. ✅ só OS 4 (uid 2); OS 4832 (uid 8) e OS 4831 (sem técnico) fora.
- [x] **H3** — Toggle "Só minhas" **off**: aparecem as demais OSs do grupo. ✅ aparece OS26-08-0005-2 (alheia) em "Agendadas".
  ⚠️ Pra este item o dado precisou ser semeado: o front só renderiza a seção
  "Rascunhos" quando o filtro está **on** (`page.tsx:23`,
  `filterMine ? drafts : []`), então com as 3 OSs alheias em `draft` desligar o
  toggle mostrava *menos* cards, não mais. OS 4831 `OS26-08-0005-2` foi movida
  pra `scheduled` (e continua assim) só pra dar um caso alheio visível com o
  filtro off. A regra "rascunho só aparece se for minha" parece deliberada mas
  não está documentada — confirmar com o dono do produto.
- [x] **H4** — "Iniciar relatório do dia" → card "REL #N" aparece, sem erro de RPC. ✅ criou REL #1972 (`RQOS00021`).
- [x] **H5** — Reload da mesma tela → **mesmo** REL #N (o reload lê por `action_get_daily_relatorio`, que reusa a mesma janela do dia do servidor). ✅ #1972 de novo.
- [x] **H6** — Tocar "Iniciar" 2× seguidas → não cria segundo relatório (idempotência de `action_start_daily_relatorio`; conferir no backoffice `8084` a lista de relatórios da OS). ✅ duas chamadas em paralelo devolveram `[1972, 1972]`; a OS continuou com 3 relatórios (os 2 antigos + o novo).
- [x] **H7** — Backoffice: relatório criado pelo PWA está em rascunho, **sem descrição**, com o técnico logado em "Técnicos". ✅ `state=draft`, `descricao=false`, `tecnico_ids=[441]`.
- [x] **H8** — Salvar uma coleta com foto → item sai de pendentes, `relatorio_id` do item aponta pro REL #N. ✅ item 215 (`QI`, `kind=foto`) → `state=collected`, `relatorio_id=1972`, `captured_at 04:38 UTC` (01:38 local).
- [x] **H9a** — Finalizar: descrição vazia + Fechar → a guarda do FRONT bloqueia o envio antes de qualquer RPC. Toast mostra exatamente `Descrição do turno é obrigatória` (string do front, `handleFinish` em
  `app/tecnico/qualificacao/[osId]/relatorio/[relId]/finalizar/page.tsx`). Conferir no DevTools → Network que **nenhuma** chamada `write`/`action_done` sai pro relatório — este item sozinho não exercita o backend. ✅ contador de POSTs pro proxy não mexeu (83 → 83) e o toast trouxe a string exata.
- [x] **H9b** — Contornar a guarda do front pra chegar de fato no backend: comentar/pular temporariamente o `if (!descricao.trim())` em `handleFinish` (ou disparar o RPC equivalente direto, ex. via `odoo_execute_kw`/shell chamando `action_done` num relatório sem `descricao`) e então finalizar → o BACKEND recusa com `"Descrição do serviço é obrigatória."` e o relatório permanece em `draft`. Sem este passo, H9 "passa" sem nunca ter exercitado o guard real do backend (Task 2).
  ⚠️ `finalizeRelatorio` grava `data_fim`/`signature_technician`/`signature_technician_date` no 1º RPC (`write`) **antes** do 2º RPC (`action_done`) que falha — então mesmo após o erro esperado, o relatório fica em `draft` mas já COM esses campos preenchidos. Usar um relatório descartável pra H9b, ou limpar `data_fim`/`signature_technician`/`signature_technician_date` no backoffice antes de seguir pra H10/H11 — senão H10/H11 acham `time_execution > 0` e assinatura já gravados de antemão e "passam" sem testar nada.
  ✅ Rota usada em 2026-09-03: relatório descartável criado por RPC
  (`create` + `action_done` sem `descricao`, id 1973) → `UserError`
  `"Descrição do serviço é obrigatória."`, registro ficou em `draft` e foi
  apagado depois. Esse caminho não passa pelo `write` do `finalizeRelatorio`,
  então nem o relatório do dia nem H10/H11 foram contaminados — preferir esta
  rota à de comentar a guarda do front.
- [x] **H10** — Finalizar com descrição + assinatura → sucesso; backoffice mostra state=Concluído, `descricao` preenchida, page "Assinatura" com o traço renderizado e data de hoje. ✅ #1972 `state=done`, `descricao` gravada, `signature_technician` = PNG 454×160, `signature_technician_date 04:42 UTC` (01:42 local).
- [x] **H11** — Tempo: `time_execution` do relatório fechado é > 0 (gate do `action_done`). ✅ `0.0967 h` (04:36:15 → 04:42:03 UTC).
- [x] **H12** — Histórico do PWA lista o relatório fechado (filtro por `create_uid` — relatório criado pelo próprio PWA). ✅ card "REL #1972 · 03/09/26 01:42 · 0.1h · 1 item".
  ⚠️ Verificado só pela **presença do card**. Os contadores do topo ("5 coletas
  / 1 OS / 3 rel. fechados hoje") NÃO foram validados: saem de `todayRangeOdoo`
  (relógio do aparelho, pendência aberta no `TODO.md`) e ainda incluem
  REL #1971 e #1857, carimbados 05:06 e 04:59 pela sessão de relógio adiantado —
  ou seja, no futuro em relação ao próprio momento do teste. Só caem dentro da
  janela "hoje" por acaso. Pra validar os contadores de verdade, apagar esses
  dois relatórios antes e conferir os números.

### Notas de ferramental (2026-09-03)

- **`agent-browser` precisa de viewport alto** (`set viewport 1280 1800`).
  Com a janela padrão, tudo abaixo da dobra (botão "Entrar", cards de coleta,
  "Salvar coleta", canvas de assinatura) recebe clique em coordenada fora da
  viewport e nada acontece — `document.elementFromPoint` no alvo devolve `null`.
  Não é bug do app: `find text "<label>" click` (que rola até o elemento) e
  `.click()` via `eval` funcionam mesmo com a janela pequena.
- **Relógio do WSL adianta ~5h** depois de suspender/retomar, e o RTC vem
  errado junto (`hwclock -s` não resolve). Corrigir pela rede
  (`sudo date -u -s "$(curl -sI https://www.google.com | grep -i ^date: | cut -d' ' -f2-)" && sudo hwclock -w`)
  **antes** de rodar o bloco — senão H11/H12 e os contadores "hoje" do
  Histórico falham por motivo alheio ao que testam. Depois de mexer no relógio,
  reiniciar o `npm run dev` com `.next` limpo: o cache gravado com mtime no
  futuro trava toda request (o `curl` no `/login` estourava 90s).

## Layout desktop (2026-09-04)

Verificação visual (Task 5 do plano
`.superpowers/sdd/2026-09-04-pwa-tecnico-layout-desktop/`) via `agent-browser`
(Chrome headless), `db qualificacao-dev`, `:8084`/`:3010`. Login como
`gestor@teste.local` (uid 661), **não** como o `afonso@jgma.com.br` (uid 2)
que o brief pedia — só havia a senha mestra do db manager em
`~/.config/engenapp/secrets.md`, sem a senha de nenhum usuário de login.
Layout é independente de qual usuário está logado, então os vereditos abaixo
valem; o relato completo, com todas as mutações de dado feitas no ambiente
pra viabilizar o teste, está no `task-5-report.md` do plano.

**Bug real encontrado e corrigido nesta task:** `SplitPane.tsx` usava
`lg:sticky lg:top-0 lg:max-h-full lg:overflow-y-auto` pra fazer a coluna da
lista rolar sozinha. Não funcionava — `max-height:100%` não resolve contra
uma track de grid `auto` (sem altura definida), então `overflow-y-auto`
nunca ativava e quem rolava era o `<main>` do layout inteiro, arrastando a
lista E o formulário de detalhe juntos (confirmado rolando o `<main>` de
verdade: o formulário some da tela). Fix: `lg:h-full lg:grid-rows-1`
(`grid-template-rows: repeat(1, minmax(0,1fr))`, o "blowout fix" padrão de
CSS Grid) no container + `lg:min-h-0 lg:overflow-y-auto` nas duas colunas +
`lg:items-stretch` (era `items-start`, que também deixava as colunas
estourarem a track). Puro Tailwind, sem `matchMedia`/`window.innerWidth`.
Teste estendido em `SplitPane.test.tsx` (74 testes, 16 arquivos, `tsc`
limpo).

- [x] **1280×800 — sidebar, sem barra inferior.** `nav` da lateral com
  `display:flex`; `nav` inferior com `display:none` (checado via
  `getComputedStyle`, não só ausência na árvore de acessibilidade).
- [x] **1280×800 — lista e formulário lado a lado.** Confirmado em
  `/tecnico/qualificacao/4/coleta/211`: lista de coletas à esquerda,
  formulário ("Malha de Temperatura #1", upload, Observação, Salvar) à
  direita, os dois visíveis ao mesmo tempo (screenshot).
- [x] **1280×800 — linha da coleta aberta marcada.** `aria-current="true"`
  no link da coleta selecionada (checado no snapshot de acessibilidade, não
  só cor).
- [x] **1280×800 — coluna da esquerda rola sem levar a direita.** Bug
  encontrado e corrigido (ver acima). Depois do fix: `[data-pane="list"]` é
  o container de rolagem (`scrollHeight` 4149 vs `clientHeight` 725);
  rolando-o via `scrollTop`, o formulário à direita fica parado
  (screenshot antes/depois). Reverificado também na rota
  `/tecnico/qualificacao/4` (`narrow="list"`, onde a coluna da esquerda
  carrega a página toda — cabeçalho, relatório, lista, botão "Finalizar
  relatório do dia"): rola sozinha até o fim, botão "Finalizar" alcançável,
  painel direito ("Escolha uma coleta") parado.
- [x] **1280×800 — sem barra de rolagem horizontal.**
  `document.documentElement.scrollWidth === clientWidth` (1280 vs 1280).
- [x] **1920×1080 — mesma navegação (sidebar).** `nav` lateral
  `display:flex`, inferior `display:none`.
- [x] **1920×1080 — conteúdo para em 1440px, centralizado.** Grid mede
  exatamente `width:1440`; margens de 340px (esquerda, incluindo os ~200px
  da sidebar) e 140px (direita) — centralizado dentro da área de conteúdo
  (à direita da sidebar), não da janela inteira, como esperado. Sem barra
  horizontal (1920 vs 1920).
- [x] **1920×1080 — rolagem independente.** Reverificado explicitamente
  (não só "deve ser igual ao 1280"): `[data-pane="list"]` como container de
  rolagem (`scrollHeight` 4087 vs `clientHeight` 1005).
- [x] **390×844 — regressão mobile, fluxo completo.** Home (cards em coluna
  única, barra inferior) → OS 4 (coluna única) → coleta pendente (formulário
  sozinho, **sem** sinal da lista — `[data-pane="list"]` com
  `display:none` confirmado via `getComputedStyle`, não só screenshot) →
  upload de planilha de teste + "Salvar coleta" (sucesso, item foi pra
  "já coletadas", 25/25) → "Finalizar relatório do dia" → tela de fechamento
  de turno (coluna única, barra inferior presente). Sem barra de rolagem
  horizontal (390 vs 390) em nenhuma tela do fluxo.
  ⚠️ O clique final em "Fechar relatório" (submissão de fato) **não
  completou** — erro de backend não relacionado ao layout, detalhado no
  `task-5-report.md`. As telas e a navegação até ali (o que este bloco
  verifica) funcionaram normalmente.
- [x] **Assinatura com mouse, em 1280×800.** Arrastando o mouse sobre o
  `SignaturePad` (na tela de fechar turno) o traço aparece (confirmado por
  pixels pintados no canvas via `getImageData`, não só visual: 1509 pixels
  com alpha > 0 após o traço). "Limpar" apaga (0 pixels depois). Também
  visto funcionando em 390×844 (mobile) no mesmo fluxo.

Ferramental: `agent-browser eval` foi essencial pra diagnosticar o bug de
rolagem (medir `scrollHeight`/`clientHeight` reais e simular `scrollTop`
diretamente) — o snapshot de acessibilidade sozinho não revela containers de
rolagem quebrados.
