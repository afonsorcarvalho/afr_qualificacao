# TODO — PWA Técnico

## Pendente

### Técnico Qualificação
- CollectedCard: mostrar campo `description` (observação) nos itens já coletados (OsDetail + RelatorioDetail)
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
- **`getHistoricoSummary`/`todayRangeOdoo` ainda calculam "hoje" pelo relógio do dispositivo.**
  Mesmo viés que o fix de 2026-09-03 eliminou do caminho de abertura do relatório do dia
  (`dayWindowOdoo`/`action_start_daily_relatorio`), só que aqui em `todayRangeOdoo`
  (`pwa/lib/odoo/tecnico.ts`), usado por `getHistoricoSummary` e pelos contadores "hoje" do
  histórico (coletas/OS/relatórios fechados do dia). Um aparelho com relógio torto mostra contadores
  errados — janela do dia calculada local, comparada contra `captured_at`/`signature_technician_date`
  gravados pelo servidor. Fix seria análogo: um método RPC somente-leitura que devolve os contadores
  já calculados no servidor, com a janela do dia decidida lá.
- ~~Bloco H do `pwa/app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md` (H1-H12).~~ **Executado em
  2026-09-03: 12/12 verdes** no db `qualificacao-dev` (uid 2), evidência por item no próprio
  checklist. O gate de aceitação end-to-end da adequação PWA↔backend está fechado. Blocos A–G
  (funcionalidade geral, PWA, IA, record rules) continuam sem execução manual — o Bloco F em
  particular precisa de uma conta **só** com o grupo Técnico, que ainda não existe no db.

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
