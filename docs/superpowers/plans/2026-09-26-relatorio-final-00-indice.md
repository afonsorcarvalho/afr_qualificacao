# Relatório Final de Qualificação — Índice dos Planos + Contrato de Interfaces

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement
> each plan task-by-task. Execute the plans **in order** (P1 → P5). Each plan is independently
> testable and ends green; do not start plan N+1 with plan N red.

**Spec:** `docs/superpowers/specs/2026-09-26-relatorio-final-qualificacao-design.md` (read it first).

## Ordem e dependências

| Plano | Arquivo | Depende de | Versão do manifest ao final |
|---|---|---|---|
| P1 — Modelo do relatório + dados de campo + ciclos | `2026-09-26-relatorio-final-p1-modelo-dados-campo.md` | — | `16.0.8.0.0` |
| P2 — Biblioteca de certificados | `2026-09-26-relatorio-final-p2-certificados.md` | P1 | `16.0.8.1.0` |
| P3 — Template, blocos, anexos (posições), aprovações (registro) + corpo QWeb | `2026-09-26-relatorio-final-p3-template-blocos.md` | P1 | `16.0.8.2.0` |
| P4 — Montagem do PDF, minuta, emissão, revisão, verificação pública, portal | `2026-09-26-relatorio-final-p4-montagem-emissao.md` | P1, P2, P3 | `16.0.8.3.0` |
| P5 — Varredura (regras + IA) + gate de emissão | `2026-09-26-relatorio-final-p5-verificacao.md` | P1–P4 | `16.0.8.4.0` |

## Global Constraints (valem para todos os planos)

- Odoo **16.0**. Módulo `afr_qualificacao` é **git submodule** em `addons/afr_qualificacao/`.
  Trabalhar numa branch `feat/relatorio-final` criada **dentro do submodule** a partir de `main`.
- Commits: sempre de dentro de `addons/afr_qualificacao/`, via agente `git-commit-push` (haiku),
  paths relativos ao submodule. **Não** fazer push nem bump do pointer no monorepo sem o usuário pedir.
  Mensagens de commit em inglês, Conventional Commits.
- Testes: via agente `test-runner` (sonnet) quando rodado pelo orquestrador. Comando base:
  `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http`
  (`-u` obrigatório quando tocar XML; `--no-http` obrigatório).
  **Estado conferido em 2026-09-26:** `odoo_engenapp-web-1` e `odoo_engenapp-db-1` existem mas estão
  **parados** (Exited); o db `odoo_ecm_test` vive no `db-1`. O `db-qualificacao` só tem `qualificacao-dev`
  — **não** usar o container `web-qualificacao` para a suíte. Antes do primeiro teste:
  `cd /home/afonso/docker/odoo_engenapp && docker compose up -d db web` (serviços `db`/`web` do
  `docker-compose.yml`) e confirmar com `docker ps`. Validação manual de UI usa o `web-qualificacao`
  (http://localhost:8084, db `qualificacao-dev`). Falhas pré-existentes conhecidas:
  `TestResourcePlan.test_fleet_single_logger_two_temp_standards`,
  `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`,
  `TestProposalReport.test_render_schedule_block`.
- Novos testes herdam de `tests/common.py::AfrQualificacaoTestCommon` quando precisarem de
  SO/OS/equipamento; registrar cada novo arquivo em `tests/__init__.py`.
- Todo novo model: entrada em `models/__init__.py`, ACL em `security/ir.model.access.csv`
  (technician: read; user: read/write/create; manager: full), salvo indicação contrária.
- Grupos: `afr_qualificacao.group_afr_qualificacao_technician`, `..._user`, `..._manager`.
- **Nunca** usar nomes de clientes, pessoas ou números de certificados reais dos exemplos em
  `dados_sensiveis/` em código, seeds, testes ou docs. Usar "Cliente Teste", "Eng. Responsável".
- `engc_os` está **congelado**: não editar nada em `engenapp/engc_os/`. Extensões só por
  `_inherit` dentro de `afr_qualificacao`.
- PWA (`pwa/`) **não muda** nesta fase.
- Bibliotecas PDF disponíveis no Odoo (`/usr/bin/python3` do container): `PyPDF2==1.26.0`
  (API antiga: `PdfFileReader`, `PdfFileWriter`, `getPage`, `mergePage`, `addPage`,
  `getNumPages`), `reportlab 3.5`, `pdfminer.six 20200726`. `odoo.tools.pdf.merge_pdf` existe.
  Não adicionar dependência pip.
- Cada plano faz bump de `__manifest__.py` `version` para o valor da tabela acima e, se criar
  dado seed, adiciona script em `migrations/<versão>/post-migrate.py` que chama a mesma função
  do `hooks.py` (idempotente) — bases existentes não rodam `post_init_hook`.
- Textos de UI e seeds em pt-BR.

## Contrato de interfaces (nomes exatos — não renomear)

### P1 produz
- Model `afr.qualificacao.relatorio` (`models/relatorio.py`), `_inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]`.
  Campos: `name` (Char, readonly, compute store), `index` (Integer), `os_id` (M2O `afr.qualificacao.os`, required, ondelete cascade),
  `equipment_id` (M2O `engc.equipment`, required), `partner_id` (related `os_id.partner_id`, store),
  `company_id` (related `os_id.company_id`, store),
  `qualificacao_ids` (M2M `afr.qualificacao`, compute store: `os_id.qualificacao_ids` do mesmo equipamento, excluindo `state='cancelled'`),
  `cycle_ids` (M2M `afr.qualificacao.cycle`, compute: `qualificacao_ids.cycle_ids`),
  `state` Selection `[("draft","Rascunho"),("issued","Emitido"),("client_approved","Aprovado pelo cliente")]` default `draft`,
  `revision` (Integer, default 0), `revision_label` (Char compute: `"Rev.%02d" % revision`),
  `data_inicio_ensaios`, `data_fim_ensaios` (Date), `amb_temperatura`, `amb_umidade` (Char),
  `tolerancia_acima` (Float, default 3.0), `criterio_f0_fator` (Float, default 12.0),
  `checklist_ids`, `indicador_ids`, `leitura_ib_ids` (O2M), `proxima_qualificacao` (Date compute).
  SQL constraint `unique(os_id, equipment_id)`.
- `name` = `"ReQT-%s-%d" % (os_id.name, index)`; helpers `_doc_number(prefix)` → `"%s-%s-%d" % (prefix, os_id.name, index)` (prefix ∈ `ReQT`, `PrQT`, `ReQM`).
- `afr.relatorio.checklist` (`relatorio_id`, `sequence`, `grupo`, `descricao`, `status` Selection `aprovado/reprovado/na`, `comentario`).
- `afr.relatorio.indicador` (`relatorio_id`, `tipo` Selection `biologico/quimico`, `marca`, `modelo_tipo`, `lote`, `validade` Date, `valor_d` Float, `populacao` Char, `evidencia_collect_item_id` M2O `afr.qualificacao.collect.item`).
- `afr.relatorio.leitura.ib` (`relatorio_id`, `cycle_id` M2O cycle, `indicador_id`, `data_incubacao`, `data_leitura` Date, `leitor` Char, `resultado` Selection `negativo/positivo`, `controle_positivo_ok` Boolean).
- `afr.qualificacao.cycle` ganha: `janela_inicio`, `janela_fim` (Datetime), `sensor_pos_ids` (O2M `afr.relatorio.sensor.pos`), `extracted_json` (Text), método `action_copy_sensor_pos_from_previous()`.
- `afr.relatorio.sensor.pos` (`cycle_id`, `sequence`, `canal` Char, `posicao` Char, `ib_label` Char).
- `afr.qualificacao.relatorio._seed_checklist(lines)` — `lines`: list of dict `{grupo, descricao, sequence}`; idempotente (não duplica se já houver linhas).
- `proxima_qualificacao` é **stored**; P4 acrescenta `current_emissao_id.issued_at` ao `depends` (recompute automático).
- `action_copy_sensor_pos_from_previous()` busca o ciclo anterior em **todo o relatório** (ordem QI < QO < QD, depois `cycle_type_id`, `sequence`, `id`).
- `afr.qualificacao.os.action_generate_relatorios()` → recordset (botão usa wrapper `action_generate_relatorios_open()` que devolve action) dos relatórios (cria os faltantes, um por equipamento, `index` pela ordem canônica `(name, id)` de `_relatorio_final_equipments()`); `relatorio_final_ids` (O2M), `relatorio_final_count`.
- Views em `views/relatorio_views.xml`, xmlids `view_afr_qualificacao_relatorio_form`, `view_afr_qualificacao_relatorio_tree`, `view_afr_qualificacao_relatorio_search`, action `action_afr_qualificacao_relatorio`: form/tree/search do relatório com `<notebook>` contendo páginas `name="page_dados_campo"` e `name="page_ciclos"` (planos seguintes adicionam páginas por herança com xpath nesses `name`), header com `<header>` vazio exceto statusbar (planos seguintes adicionam botões por xpath `//header`). Menu `menu_afr_relatorio_final` sob o menu de Qualificação.

### P2 produz
- `engc.calibration.instruments.certificates.afr_role` Selection `[("antes","Antes da campanha"),("depois","Depois da campanha"),("externo","Certificado externo (padrão)")]` default `externo`.
- `engc.calibration.instruments._afr_select_certificate(role, date_start, date_end)` → record (0 ou 1) de certificado. Regras: spec §4.4.
- `afr.qualificacao.relatorio._afr_certificate_selection()` → `list[dict]` com chaves
  `instrument` (record), `resource_role` (`"validador"`/`"padrao"`), `role` (`"antes"`/`"depois"`/`"externo"`), `certificate` (record, possivelmente vazio). Um dict por (instrumento, role) esperado: validador → antes + depois; padrão → externo. Linhas do plano de recursos consideradas: as que têm `instrument_id` **e** (`equipment_ids` vazio **ou** `relatorio.equipment_id in equipment_ids`) — instrumentos de outro equipamento da mesma OS não entram.
- `afr.qualificacao.malha.collect_item_ids` (O2M inverso de `collect.item.malha_id`) é criado em P2 se não existir.
- `afr.qualificacao.relatorio._afr_certificate_files(roles)` → `list[tuple[bytes, str, str]]` = `(conteúdo, mimetype, legenda)` dos certificados selecionados com `role in roles` e arquivo presente.
- `afr.qualificacao.relatorio._afr_malha_certificate_files()` → mesma tupla; por malha dos `qualificacao_ids`: PDF do report engc_os quando `malha.engc_calibration_measurement_id.calibration_id` existe, senão PDFs dos `collect_item_ids` da malha com `file`.
- Página `name="page_certificados"` no form do relatório (readonly, lista a seleção).

### P3 produz
- `models/_numbering.py::hierarchical_numbering(records)` → `dict[int, str]` (records com `sequence`, `id`, `parent_id`, `show_number`; a função ordena por `(sequence, id)` tratando NewId como na cotação; o chamador é quem filtra `included`). `sale.order._proposal_block_numbering` passa a usá-la sem mudança de resultado.
- `afr.proposal.section.document_type` Selection `[("proposal","Proposta"),("report","Relatório")]` default `proposal`.
- `REPORT_BLOCK_KINDS` em `models/relatorio_template.py`: `static, capa, indice, protocolo, laudo_micro, assinaturas, anexo_separador`.
- Models `afr.relatorio.template` (`name`, `code`, `line_ids`, `checklist_line_ids`, `anexo_line_ids`, `equipment_category_ids` M2M `engc.equipment.category`, `sequence`, `active`, `company_id`),
  `afr.relatorio.template.line` (espelho de `afr.proposal.template.line` com `block_kind` em `REPORT_BLOCK_KINDS` + `anexo_code` Char para `anexo_separador`),
  `afr.relatorio.template.checklist.line` (`template_id`, `sequence`, `grupo`, `descricao`),
  `afr.relatorio.template.anexo.line` (`template_id`, `sequence`, `code`, `title`, `slot_kind`, `collect_sections`, `cert_roles`, `included_default` Boolean).
- `afr.relatorio.block` (`relatorio_id`, `sequence`, `block_kind`, `section_id`, `title`, `body`, `included`, `page_break`, `parent_id`, `show_number`, `show_title`, `anexo_code`).
- `afr.relatorio.anexo` (`relatorio_id`, `sequence`, `included`, `code`, `title`, `slot_kind` Selection `collect_section/instrument_certs/malha_certs/bloco/upload`, `collect_sections`, `cert_roles`, `block_id`, `attachment_ids` M2M `ir.attachment`, `numero` Integer compute).
- `afr.relatorio.aprovacao` (`relatorio_id`, `sequence`, `papel` Selection `elaborador/emissor/executor/cliente`, `user_id`, `partner_id`, `nome_exibicao`, `registro`, `approved_at` Datetime, `ip` Char, `access_token` Char compute não armazenado, só su/Gestor; o token vive em `afr.relatorio.aprovacao.secret` (sem ACL, sudo only)).
- Em `afr.qualificacao.relatorio`: `template_id`, `block_ids`, `anexo_ids`, `aprovacao_ids`;
  `_apply_template()` (cria blocos, anexos, checklist via `_seed_checklist`, aprovações default: elaborador/emissor vazios, executor dos técnicos dos relatórios diários, cliente = `partner_id`), idempotente;
  `action_reload_template()`; `_block_numbering()` → dict; `_anexo_number(code)` → `str` (`""` se excluído/inexistente);
  `_token_context()` → dict (`relatorio, os, partner, equipment, company, criterio, anexo`);
  `_render_block_body(block)` → `Markup`.
- `ir.actions.report` `afr_qualificacao.action_report_relatorio_corpo` (QWeb-pdf, template `afr_qualificacao.report_relatorio_corpo`), paperformat próprio `paperformat_relatorio_final` (A4, margens top 35 mm / bottom 25 mm, sem header/footer do layout). O template aceita no contexto de render `page_map` (dict `"bloco:<id>"`/`"anexo:<code>"` → nº página) e `with_markers` (bool): quando `with_markers`, emite `<span class="rq-mark">@@RQ:bloco:<id>@@</span>` e `@@RQ:anexo:<code>@@` no início de cada bloco/separador.
- **Fatos fixados pelo plano P3 (consumidores devem seguir):**
  - `page_map` e `with_markers` são passados como chaves do dict **`data`** do report
    (`_render_qweb_pdf(report_ref, res_ids, data={"page_map": ..., "with_markers": True})`), não via `env.context`.
  - `_apply_template()` **não** roda no `create()` nem em `action_generate_relatorios()`; roda em
    `action_generate_relatorios_open()` e em `action_reload_template()`. Fixtures de P4/P5 chamam
    `_apply_template()` **ou** criam blocos/anexos/aprovações diretamente (P5 faz assim).
  - Ordem física e numeração dos anexos vêm de `anexo_ids` (`_anexos_included()`); marcadores esperados =
    `_body_blocks()` + `_anexos_included()` (não `block_ids.filtered("included")`).
  - Token `anexo` é callable (`{{ anexo('micro') }}`).
  - Hook real do manifest: `_install_proposal_template_seed` (seed do relatório no topo, antes do `return` antecipado).
- Seeds em `hooks.py::_seed_relatorio_templates(env)` (templates Hospitalar `RQT-HOSP` e Industrial `RQT-IND`), chamada por `post_init_hook` e pela migração de P3.
- Páginas `name="page_texto"`, `name="page_anexos"`, `name="page_aprovacoes"`.

### P4 produz
- `afr.relatorio.anexo._resolve_files()` → `list[tuple[bytes, str, str]]` (só arquivos utilizáveis).
- `afr.relatorio.anexo._check_files()` → `list[str]` (problemas: vazio, PDF ilegível/criptografado, tipo não suportado) — consumido por P5 (`ANEXO_VAZIO`, `ANEXO_ILEGIVEL`).
- `afr.relatorio.pdf` (AbstractModel, `models/relatorio_pdf.py`): `build(relatorio, watermark=False)` → `bytes` (síncrono — testes e fixtures; a UI monta pelo pipeline em etapas `_stage_init`/`_stage_run`, o mesmo código de `_build`); helpers `_image_to_pdf`, `_find_markers(pdf_bytes)` → `dict[str, int]` (0-based), `_stamp(pdf_bytes, header: dict, watermark: bool)` → `bytes`.
- `afr.relatorio.emissao` (`relatorio_id`, `revision`, `pdf_attachment_id`, `sha256`, `token`, `issued_at`, `issued_by`, `blocks_snapshot` Text/JSON, `scan_snapshot` Text/JSON, `superseded` Boolean); imutável (write/unlink bloqueados fora de sudo interno).
- `afr.relatorio.build.job` (`relatorio_id`, `kind` `minuta/emissao`, `state` `queued/running/done/failed/cancelled`, `requested_by`, `token`, `issued_at`, `scan_snapshot`, `blocks_snapshot`, `progress`, `error`); cron `afr_qualificacao.ir_cron_relatorio_build_job` (`model._cron_process()`); um job ativo por relatório.
- Em `afr.qualificacao.relatorio`: `emissao_ids`, `current_emissao_id`, `minuta_attachment_id`, `verify_url` (compute), `rq_editorial_seq`, `rq_build_job_id` (+ `rq_build_state/kind/progress/error`);
  `action_baixar_minuta()`, `action_cancelar_montagem()`, `action_enviar_aprovacao_cliente()` (só Gestor);
  `action_gerar_minuta()`, `action_aprovar_interno()` (aprova a linha do papel cujo `user_id == env.user`), `action_emitir()`, `action_revisar()`; `action_gerar_minuta()` e `action_emitir()` **enfileiram** e devolvem `display_notification`;
  `_check_emission_gate()` → `list[str]` de impedimentos (P4: aprovações internas elaborador+emissor; P5 estende com `super()`);
  `_scan_snapshot()` → `str` JSON (P4: `"[]"`; P5 sobrescreve);
  `_invalidate_internal_approvals()` chamado em `write()` de campos editoriais quando `state == draft`.
- **Fatos fixados pelo plano P4:** `action_emitir` levanta `UserError` se o gate falhar;
  gate e aprovações são síncronos no clique (`UserError` antes de enfileirar); emissão, `state`, `revision`,
  reset das aprovações do cliente e minuta são gravados só no finalize do job; edição editorial recusada
  enquanto houver emissão em montagem;
  `action_aprovar_interno` aprova **todas** as linhas pendentes (elaborador/emissor) do usuário;
  itens de `_check_files()` = constante `PROBLEM_EMPTY` ou `"<legenda>: <motivo>"`; anexo `bloco` →
  `_resolve_files()` devolve `[]` (conteúdo já está no corpo); QR carimbado via reportlab;
  testes mockam `ir.actions.report._render_qweb_pdf` (em modo teste ele devolve HTML); testes que emitem ou
  geram minuta chamam `tests/relatorio_fakes.py::run_build_jobs(env)` dentro do `FakeCorpo().patch(env)`.
- Controllers: `/qualificacao/relatorio/verify/<token>` (público), `/my/relatorio/<int:aprovacao_id>?access_token=` (aprovação cliente), `/my/relatorio/<int:aprovacao_id>/pdf?access_token=` (PDF inline), `/my/relatorio/<int:aprovacao_id>/aprovar` (POST com CSRF).

### P5 produz
- `afr.relatorio.achado` (`relatorio_id`, `origem` `regra/ia`, `codigo`, `gravidade` `bloqueia/alerta/info`, `mensagem`, `onde`, `decisao` `pendente/procede/descartado`, `motivo`, `decidido_por`, `decidido_em`).
- `models/relatorio_rules.py`: registro `RULES: dict[str, callable(relatorio) -> list[dict]]`.
- `afr.relatorio.ai` (AbstractModel): `review(relatorio)` → `list[dict]`; `_call(messages)` → `str`.
- Em `afr.qualificacao.relatorio`: `achado_ids`, `action_verificar()`, `has_blocking` (compute), override de `_check_emission_gate` e `_scan_snapshot`. Página `name="page_verificacao"`.
