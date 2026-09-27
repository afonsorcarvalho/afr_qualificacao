# Checklist — Relatório Final de Qualificação (P1–P5, 16.0.8.4.0)

## Ambiente
- **URL:** http://localhost:8084/web?db=qualificacao-dev (container `odoo_engenapp-web-qualificacao-1`)
- **Upgrade:** `docker exec odoo_engenapp-web-qualificacao-1 /entrypoint.sh -d qualificacao-dev -u afr_qualificacao --stop-after-init --no-http` + `docker restart odoo_engenapp-web-qualificacao-1`
- **Browser:** `agent-browser` — sempre `open .../web/session/logout` antes de logar de novo; `snapshot -i` após cada mudança de tela.
- **Dados:** usar só "Cliente Teste" / equipamentos de teste. Nunca dados de `dados_sensiveis/`.
- **IA:** desligada por padrão; a chave do OpenRouter é colada **só** em Configurações → AFR Qualificação (nunca em arquivo, chat ou print). Modelo pago `google/gemma-4-31b-it` (a variante `:free` devolve 429). Orçamento total de 60 s por verificação.
- **Montagem do PDF (minuta e emissão) é ENFILEIRADA**, não síncrona: um clique em "Gerar minuta" ou "Emitir" cria/agenda um `afr.relatorio.build.job`, processado em unidades de trabalho (≤~15 s de CPU cada) pelo cron `afr_qualificacao.ir_cron_relatorio_build_job`, acordado a cada enfileiramento por `_trigger()` (o intervalo do cron — 5 min — é só rede de segurança). Enquanto o job roda, o form mostra um banner "Montagem do PDF em andamento" com barra de progresso; ao terminar, o botão **"Baixar minuta"** (Minuta) ou o estado **Emitido** (Emissão) aparece. Um botão **"Cancelar"** permite abortar um job travado.

---

## Bloco A — Preparação
- [ ] **A.1** Configurações → AFR Qualificação → bloco "Relatório Final — Verificação por IA" visível; IA desligada por padrão.
- [ ] **A.2** Instrumento validador com certificados `Antes da campanha` (data ≤ início dos ensaios) e `Depois da campanha` (data ≥ fim) na biblioteca; padrão com certificado externo vigente.
- [ ] **A.3** OS de qualificação com QD (≥ 2 ciclos com carga), plano de recursos com o validador e o padrão.

## Bloco B — Gerar relatórios a partir da OS
- [ ] **B.1** OS → smart button **Relatórios Finais** → ação **Gerar relatórios** cria 1 relatório por equipamento (`ReQT-<OS>-<n>`).
- [ ] **B.2** Clicar de novo em Gerar não duplica (idempotente).
- [ ] **B.3** Relatório abre em **Rascunho**, `Rev.00`, com template sugerido pela categoria (blocos, anexos, checklist, aprovações).

## Bloco C — Dados de campo e ciclos
- [ ] **C.1** Aba **Dados de campo**: datas dos ensaios, ambiente (temperatura/umidade), tolerância, fator F0.
- [ ] **C.2** Checklist: marcar itens aprovados; marcar 1 como **reprovado** (para o Bloco E).
- [ ] **C.3** Indicadores: cadastrar IB com lote e validade; leituras de IB por ciclo (resultado negativo).
- [ ] **C.4** Aba **Ciclos**: janela início/fim por ciclo; posições de sensores (canal/posição/IB); "copiar do ciclo anterior" funciona.
- [ ] **C.5** Aba **Certificados**: seleção automática mostra antes/depois/padrão corretos.

## Bloco D — Texto, anexos e minuta (fluxo enfileirado)
- [ ] **D.1** Aba **Texto**: editar um bloco estático com token `{{ relatorio.name }}` → minuta mostra o nº.
- [ ] **D.2** Aba **Anexos**: numeração 1..N só sobre incluídos; excluir um anexo renumera.
- [ ] **D.3** Clicar **Gerar minuta** → botão some/desabilita e aparece o banner **"Montagem do PDF em andamento (Minuta)"** com barra de progresso; atualizar a página (F5) mantém o banner até o job terminar.
- [ ] **D.4** Job de minuta em andamento → botão **Cancelar** (grupo Usuário) visível e funcional; job cancelado libera o form para gerar de novo.
- [ ] **D.5** Job termina → banner some, botão **"Baixar minuta"** aparece; baixar → PDF com marca "MINUTA — SEM VALIDADE", "Página X de Y" em todas as páginas (anexos incluídos), índice com páginas corretas.
- [ ] **D.6** Forçar uma falha na montagem (ex.: anexo PDF com binário inválido/corrompido anexado ao slot) → banner vermelho "A última montagem falhou" com uma mensagem de erro legível (não uma tela em branco/crash); clicar em "Gerar minuta" de novo tenta outra vez. Se o anexo corrompido só gerar `ANEXO_ILEGIVEL` na aba Verificação (sem falhar o build), tentar outro tipo de falha para exercitar este item.

## Bloco E — Verificar (P5)
- [ ] **E.1** Remover temporariamente o certificado "depois" → **Verificar** → aba **Verificação** lista `CERT_DEPOIS_AUSENTE` (vermelho) e banner **"Aguardando: …"** no topo.
- [ ] **E.2** Linha `bloqueia`: coluna Decisão não editável.
- [ ] **E.3** `CHECKLIST_REPROVADO` (amarelo): escolher **Descartado** sem motivo → campo Motivo obrigatório; com motivo salva e mostra "Decidido por".
- [ ] **E.4** Restaurar o certificado "depois" → **Verificar** → bloqueio some, banner some; decisão do checklist **mantida** (mesma linha).
- [ ] **E.5** Esvaziar umidade → Verificar → `AMBIENTE_VAZIO`; preencher → Verificar → some.
- [ ] **E.6** Anexo incluído sem arquivo → `ANEXO_VAZIO`; texto citando `anexo('x')` excluído → `ANEXO_REF_EXCLUIDO`.
- [ ] **E.7** (Opcional, com chave válida) Ligar IA → Verificar → achados "IA — verificar" em itálico; alerta de IA pendente impede Emitir até ser decidido; chave inválida → um único `IA_INDISPONIVEL` (info), sem erro na tela.
- [ ] **E.8** Após decidir um achado de IA como "procede", rodar **Verificar** de novo → **esperado:** o achado tende a voltar como pendente (achado de IA usa `onde` livre, o carry-over por chave não casa) — isto é comportamento conhecido/aceito, não é bug; não reportar como falha.

## Bloco F — Aprovar e emitir
- [ ] **F.1** Com alerta pendente (de regra ou de IA), **Emitir** → erro listando "Alerta sem decisão [...]".
- [ ] **F.2** Decidir todos os alertas; **Aprovar** como elaborador e como emissor (usuários designados).
- [ ] **F.2b** **Designação do emissor é só de Gestor:** logado como Usuário (não-Gestor), tentar definir/trocar o usuário da linha de aprovação com papel **emissor** → não permitido (campo bloqueado ou erro de acesso). Logado como Gestor, a troca funciona. A linha **elaborador** continua editável por Usuário normalmente.
- [ ] **F.3** Editar um campo editorial após aprovar → aprovações internas zeradas; decidir achado **não** zera.
- [ ] **F.4** Clicar **Emitir** (gestor) → botão some, banner **"Montagem do PDF em andamento (Emissão)"** aparece; só **Gestor** vê/usa o botão "Cancelar" desse job (Usuário não pode cancelar job de emissão). Ao terminar: estado **Emitido**, aba **Revisões** mostra emissão com SHA-256 e token; chatter registra.
- [ ] **F.5** PDF emitido sem marca d'água, QR no rodapé da última página do corpo.
- [ ] **F.6** Verificar CSS/layout do PDF emitido pela fila (fonte, cores, cabeçalho, faixas) conforme o esperado do template — se vier só com a estrutura HTML "crua" (sem estilo), ver nota de deploy sobre `report.url` abaixo.

## Bloco G — Verificação pública, portal e sigilo
- [ ] **G.1** Abrir `/qualificacao/relatorio/verify/<token>` em janela anônima → nº, revisão, data, hash, status **Válido**.
- [ ] **G.2** Token inválido → 404.
- [ ] **G.3** **Token de aprovação do cliente não visível a não-Gestor:** na linha de aprovação com papel **cliente** (não a emissão — o `token` da emissão, usado no QR/`verify_url`, é público por design), logado como Usuário → campo `access_token`/link do portal ausente/oculto; logado como Gestor (ou via `sudo`) → visível.
- [ ] **G.4** **Envio de aprovação ao cliente é só de Gestor:** logado como Usuário, o botão "Enviar para aprovação do cliente" não aparece (ou é bloqueado); logado como Gestor, aparece e funciona.
- [ ] **G.5** Disparar "Enviar para aprovação do cliente" → e-mail usa o **layout fixo** do template (não um texto livre digitado na hora) e vai **só para o contato da linha de aprovação do cliente** (não para toda a empresa nem para contatos genéricos do parceiro) — confirmar destinatário no e-mail recebido/log de chatter.
- [ ] **G.6** Link de aprovação do cliente (`/my/relatorio/<id>?access_token=...`) → PDF + botão **Aprovar** → grava data/IP/nome; com todos os aprovadores → estado **Aprovado pelo cliente**; página pública lista a aprovação.
- [ ] **G.7** (Se atrás de proxy/Apache) Confirmar que o IP gravado na aprovação é o IP real do cliente, não o IP do proxy — depende de `proxy_mode=True` (ver DEPLOY).

## Bloco H — Revisar
- [ ] **H.1** **Revisar** → `Rev.01`, estado Rascunho, aprovações internas zeradas; emissão anterior ainda **Válida**.
- [ ] **H.2** Emitir a Rev.01 (fluxo enfileirado, como no Bloco F) → emissão anterior vira **Substituída** na página pública; nova emissão válida.
- [ ] **H.3** Emissão anterior continua imutável (tentar editar pela interface não é possível).
- [ ] **H.4** Antes de Revisar, decidir um achado `alerta` (de regra ou de IA) como "Procede" ou "Descartado" → **Revisar** → aba **Verificação** mostra o mesmo achado (se o dado que o gerou continuar valendo) de volta como **Pendente**, sem motivo/"Decidido por" — mesmo princípio das aprovações internas (H.1): decisão da revisão anterior não vale para a nova. **Emitir** a Rev.01 sem decidir de novo → bloqueado até decidir.

---

## DEPLOY — ler antes de subir em produção

- **Pull + upgrade sempre juntos.** Esta versão (16.0.8.4.0) depende de campos/tabelas novas e das migrations `16.0.8.2.0` e `16.0.8.3.0` (seeds; o token do cliente foi movido para um modelo "secret" separado). Fazer `git pull` sem rodar `-u afr_qualificacao` na mesma janela de manutenção (ou vice-versa) quebra o form e o cron. Sempre `pull` + `-u afr_qualificacao` no mesmo passo.
- **`report.url` precisa ser um endereço que o próprio servidor Odoo alcance** (ex.: `http://127.0.0.1:8069`) e que passe pelo `dbfilter` configurado. Caso contrário, os PDFs montados pela fila (cron) saem **sem o CSS do layout** — só a estrutura HTML "crua". Testar isso é o item F.6 acima.
- **Ativar "Restringir renderização de modelo" ("Restrict Template Rendering")** (Configurações → Discussão/E-mail) em toda base de produção. Por padrão, o Odoo 16 permite que qualquer usuário interno execute código dentro de templates de e-mail — risco de segurança relevante, não específico deste módulo, mas que este fluxo (e-mail de aprovação ao cliente) expõe.
- **`proxy_mode = True`** no Odoo atrás do Apache, para que a aprovação do cliente grave o IP real (e não o IP do proxy). Ver item G.7.
- **Diretório de sessões:** subdiretórios de sessão pertencentes a um uid diferente do uid do Odoo fazem o Odoo **descartar sessões silenciosamente** (login parece funcionar e cai depois). Corrigir a propriedade (`chown`) dos subdiretórios de sessão para o uid do processo Odoo.
- **Ordem de deploy com `engc_os`:** as fases 0–2 da calibração do `engc_os` precisam estar em produção **antes** de subir `afr_qualificacao` ≥ 16.0.8.1.0. Após o upgrade, certificados existentes passam a ser classificados como `externo` e precisam ser **reclassificados manualmente** (antes/depois da campanha) para que os validadores voltem a ser reconhecidos pelas regras de verificação. (Fonte: revisão final de P2 — P2 lê `superseded_by_id`/`certificate_file_ids` de commits da calibração do `engc_os`.)
- **`limit_time_cpu` / `limit_time_real(_cron)` em produção:** confirmar que os limites de produção acomodam o orçamento de ~15 s de CPU por unidade de trabalho da fila — medição em ambiente de teste chegou a ~17,6 s de CPU no pior caso. Ajustar os limites do worker/cron em produção com essa margem em mente. (Fonte: leva de correção final de P4 — medição numa minuta pesada de 150 páginas na fila, orçamento de 15 s.)
- **Cron `afr_qualificacao.ir_cron_relatorio_build_job` precisa estar ativo.** Sem ele, minutas e emissões ficam enfileiradas para sempre (banner "em andamento" que nunca termina). Jobs travados são cancelados por um **Gestor** pelo botão "Cancelar" no form do relatório.
- **IA desligada por padrão.** Se for ligar em produção, usar modelo pago `google/gemma-4-31b-it` (a variante `:free` do OpenRouter devolve HTTP 429 — não funciona na prática). Orçamento total de 60 s por verificação, repartido entre os pedaços de texto/anexo analisados.
