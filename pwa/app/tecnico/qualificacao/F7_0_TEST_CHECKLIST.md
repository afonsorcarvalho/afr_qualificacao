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
- [ ] A.1 GET / → redireciona /login
- [ ] A.2 Login com user técnico → http://localhost:3010/tecnico/qualificacao
- [ ] A.3 Lista mostra OSs agrupadas (Em andamento / Agendadas / Rascunhos)
- [ ] A.4 Toggle "Só minhas" off → mais OSs aparecem (se user em grupos maiores)
- [ ] A.5 OS sem coletas pendentes mostra "0 coletas pendentes"
- [ ] A.6 Empty state visível quando lista vazia

## Bloco B — Detalhe OS + Iniciar relatório
- [ ] B.1 Click OS → /tecnico/qualificacao/{osId}
- [ ] B.2 Header mostra nome OS + partner
- [ ] B.3 Botão "Iniciar relatório do dia" visível (sem relatório aberto)
- [ ] B.4 Click "Iniciar" → loading → card "REL #N" aparece + botão "Continuar"
- [ ] B.5 Reload → mesmo REL #N persiste (idempotência via action_start_daily_relatorio)
- [ ] B.6 Lista coletas pendentes aparece agrupada

## Bloco C — Coleta item
- [ ] C.1 Click coleta pendente → /tecnico/qualificacao/{osId}/coleta/{itemId}
- [ ] C.2 Banner instrução (amarelo) renderiza se item.instruction existe
- [ ] C.3 Botão câmera: tocar → abre câmera nativa (testar em tablet/mobile real)
- [ ] C.4 Selecionar imagem → preview thumbnail aparece
- [ ] C.5 Trocar foto funciona (botão Trocar foto)
- [ ] C.6 Click "Salvar coleta" sem foto (kind=foto/excel/pdf/qualificador_data) → toast erro
- [ ] C.7 Com foto → "Salvando..." → toast sucesso → volta detalhe OS
- [ ] C.8 Coleta some da lista pendentes (refetcha automático)
- [ ] C.9 Backend Odoo: collect.item.state=collected, file preenchido, relatorio_id linked

## Bloco D — Finalizar relatório
- [ ] D.1 Após >0 coletas, click "Finalizar relatório do dia"
- [ ] D.2 /tecnico/qualificacao/{osId}/relatorio/{relId}/finalizar
- [ ] D.3 Resumo mostra "N realizadas / M pendentes"
- [ ] D.4 Descrição vazia + Fechar → toast erro
- [ ] D.5 Assinatura vazia + Fechar → toast erro
- [ ] D.6 Desenhar assinatura → botão "Limpar" funciona
- [ ] D.7 Preencher tudo + Fechar → toast sucesso → volta detalhe OS
- [ ] D.8 Backend Odoo: relatorio state=done, signature_technician preenchido (base64), signature_technician_date hoje

## Bloco E — PWA
- [ ] E.1 Chrome DevTools → Application → Manifest carrega corretamente
- [ ] E.2 "Add to Home Screen" disponível (DevTools Application)
- [ ] E.3 Service worker registrado e ativo (DevTools Application > Service Workers)
- [ ] E.4 Offline com cache: navegação para tela já visitada funciona (static assets cached)
- [ ] E.5 Offline + tentar salvar coleta → toast erro claro (sem queue MVP)

## Bloco F — Record rules (record-level security)
- [ ] F.1 Login como Técnico A → vê só OSs onde tecnico_default_id = Técnico A
- [ ] F.2 Login como Técnico B → vê só OSs onde tecnico_default_id = Técnico B
- [ ] F.3 Login como Gerente → vê todas OSs (rule não aplica)

## Reportar
- [ ] Tudo OK → confirmar pra merge F7.0 (backend + frontend) no main
- [ ] Falha → bloco/passo + screenshot + log

## Bloco G — IA (Groq)

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
