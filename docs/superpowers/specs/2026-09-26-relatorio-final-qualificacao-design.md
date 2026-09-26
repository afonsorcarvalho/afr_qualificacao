# Relatório Final de Qualificação Térmica — Design (Fase 1)

**Data:** 2026-09-26
**Módulo:** `afr_qualificacao` (submodule `addons/afr_qualificacao`)
**Status:** aprovado em brainstorming (sessão 2026-09-26), aguardando plano

## 1. Objetivo

Automatizar a geração do relatório entregue ao cliente após uma qualificação
térmica de autoclave (hoje montado à mão em Word + PDFCreator, 60–160 páginas),
com flexibilidade de texto no mesmo padrão dos blocos da cotação, emissão
segura (revisão congelada, hash, QR) e uma varredura de inconsistências
(regras + IA) antes da emissão.

Fase 1 = **montador**: o Odoo gera o texto próprio (relatório, protocolo,
laudo microbiológico, quadros) e junta, em ordem, os PDFs externos (dados e
gráficos do validador, curvas F0, impressões da autoclave, certificados).
Não interpreta o arquivo bruto do validador.

## 2. Anatomia do relatório atual (análise de 4 exemplos reais)

Os exemplos estão em `dados_sensiveis/exemplos_relatorios/` (fora de git;
não citar nomes de clientes em código, seeds ou docs).

| Parte | Origem hoje | No Odoo (Fase 1) |
|---|---|---|
| Capa, índice, seções 1–9 (objetivo, normas, definições, QI/QO/QD/micro, certificação, critérios, validade, conclusão, quadro de assinaturas) | Texto padrão + dados | Blocos QWeb |
| Anexo 1 — Protocolo PrQT (cliente, equipamento, ambiente, metodologia, ciclos, checklist QI, disposição de sensores, padrões, procedimentos, segurança da informação, responsabilidades) | Tabelas preenchidas | Bloco dinâmico `protocolo` |
| Anexo 2/3 — Dados e gráficos do validador por ciclo | PDF do software do validador (Yokogawa) | Anexo PDF (item de coleta) |
| Registros impressos pela autoclave | Scan/foto | Anexo (foto → página) |
| Laudo microbiológico ReQM | Texto + tabela IB/IQ | Bloco dinâmico `laudo_micro` **ou** PDF do cliente (industrial) |
| Curvas F0 | PDF do validador | Anexo PDF |
| Certificados das malhas de controle (temperatura, pressão, temporizador) | Certificado próprio | `engc_os` quando vinculado, senão PDF anexado |
| Certificados do validador antes/depois | Mesmo PDF reaproveitado entre OSs | Biblioteca por instrumento |
| Certificados dos padrões (terceiros, RBC) | PDF de terceiros | Biblioteca por instrumento |
| Protocolo do próprio cliente (industrial) | PDF do cliente | Anexo upload |

Variantes observadas:
- **Hospitalar** (autoclave de bancada): QI, QO, QD, micro; 8 anexos; 1 aprovador do cliente.
- **Industrial** (autoclave de laboratório): QI, QO, QDF, QDM; pressão/pré-vácuo/Bowie-Dick;
  protocolo e laudo microbiológico do cliente anexados; 9 anexos; N aprovadores.
- Parâmetros que mudam por cliente: tolerância acima da temperatura nominal (3 °C / 4 °C),
  edição da norma, critério F0 (`12×D` SAL, `7×D` sobre-morte para líquidos).

Erros encontrados nos relatórios entregues (motivam a varredura, §7):
- gráfico de um ciclo com data de outro ano (arquivo reaproveitado);
- laudo embutido com "Página 6 de 5";
- numeração do relatório ignora as páginas dos anexos.

## 3. Decisões tomadas

| # | Decisão |
|---|---|
| D1 | Fase 1 é montador. Extração do arquivo bruto do validador por IA fica para fase futura, mas o modelo de ciclo já reserva `extracted_json`. |
| D2 | Motor: **blocos QWeb** no padrão da cotação (não DOCX). |
| D3 | Unidade: **um relatório por equipamento × OS**, agregando os `afr.qualificacao` (QI/QO/QD) daquele equipamento na OS. |
| D4 | Certificados de malha: **híbrido** — imprime certificado `engc_os` quando a malha tem calibração vinculada; senão usa PDF anexado. Não altera `engc_os` (congelado). |
| D5 | Certificados do validador (antes/depois) e padrões: **biblioteca por instrumento**, seleção automática por data; emissão bloqueada sem o "depois". |
| D6 | PWA **não muda** na Fase 1. Técnico envia o que já envia (arquivos, fotos). Escritório digita os dados estruturados no backend. |
| D7 | Numeração: derivada da OS — `ReQT-<nome da OS>-<i>`; `PrQT-…` e `ReQM-…` com o mesmo sufixo. |
| D8 | Numeração de páginas **única** no documento inteiro (anexos incluídos), via carimbo. |
| D9 | Assinaturas: aprovação interna no Odoo por papel (elaborador, emissor), executor vindo do relatório diário, cliente aprova pelo portal. Emissão com hash + QR. |
| D10 | Varredura de inconsistência antes de emitir: **regras determinísticas + IA** (OpenRouter), já na Fase 1. |

## 4. Modelos

### 4.1 `afr.qualificacao.relatorio` (novo)

Um por (OS, equipamento). `_inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]`.

| Campo | Tipo | Nota |
|---|---|---|
| `name` | Char | `ReQT-<os.name>-<index>`; readonly |
| `index` | Integer | posição do equipamento na OS (1..n), estável |
| `os_id` | M2O `afr.qualificacao.os` | required, cascade |
| `equipment_id` | M2O `engc.equipment` | required; unique (os_id, equipment_id) |
| `partner_id` | related `os_id.partner_id` | store |
| `qualificacao_ids` | M2M computado/stored | `os_id.qualificacao_ids` filtrado por equipamento |
| `template_id` | M2O `afr.relatorio.template` | sugerido por categoria do equipamento |
| `block_ids` | O2M `afr.relatorio.block` | cópia editável do template |
| `state` | Selection | ver §4.6 |
| `revision` | Integer | 0, 1, 2… (exibido `Rev.00`) |
| `data_inicio_ensaios`, `data_fim_ensaios` | Date | default das datas reais da OS |
| `amb_temperatura`, `amb_umidade` | Char | texto livre ("22 a 25 °C", "41 %UR") |
| `tolerancia_acima` | Float | °C acima da nominal (default 3.0) |
| `criterio_f0_fator` | Float | default 12.0 |
| `checklist_ids` | O2M `afr.relatorio.checklist` | |
| `indicador_ids` | O2M `afr.relatorio.indicador` | |
| `leitura_ib_ids` | O2M `afr.relatorio.leitura.ib` | |
| `anexo_ids` | O2M `afr.relatorio.anexo` | posições ordenadas |
| `aprovacao_ids` | O2M `afr.relatorio.aprovacao` | papéis e aprovações |
| `achado_ids` | O2M `afr.relatorio.achado` | resultado da varredura |
| `emissao_ids` | O2M `afr.relatorio.emissao` | revisões emitidas |
| `current_emissao_id` | M2O `afr.relatorio.emissao` | última emitida válida |
| `minuta_attachment_id` | M2O `ir.attachment` | último PDF de minuta |
| `proxima_qualificacao` | Date computado | emissão + 12 meses (mês/ano no PDF) |

### 4.2 Dados de campo (filhos do relatório)

- `afr.relatorio.checklist`: `grupo` (Char: "Instalações elétricas"…), `descricao`, `status`
  (`aprovado`/`reprovado`/`na`), `comentario`, `sequence`. Semeado a partir de uma lista
  padrão por template (`afr.relatorio.template.checklist.line`).
- `afr.relatorio.indicador`: `tipo` (`biologico`/`quimico`), `marca`, `modelo_tipo`
  ("Geobacillus stearothermophilus", "Type 5"), `lote`, `validade` (Date), `valor_d` (Float,
  min), `populacao` (Char, "1,7 x 10^6"), `evidencia_collect_item_id` (foto da bula).
- `afr.relatorio.leitura.ib`: `cycle_id`, `indicador_id`, `data_incubacao`, `data_leitura`,
  `leitor` (Char), `resultado` (`negativo`/`positivo`), `controle_positivo_ok` (Boolean).

### 4.3 Extensão de `afr.qualificacao.cycle`

- `janela_inicio`, `janela_fim` (Datetime) — período de esterilização.
- `sensor_pos_ids` → `afr.relatorio.sensor.pos` (`canal` Char "CH006", `posicao` Char,
  `ib_label` Char "IB1", `sequence`). Ação "copiar do ciclo anterior".
- `extracted_json` (Text, JSON) — reservado para a extração futura (min/max/média/F0 por canal).
  Fase 1: vazio; nenhuma UI obrigatória.

### 4.4 Biblioteca de certificados (extensão, sem tocar `engc_os`)

`engc.calibration.instruments.certificates` já tem `certificate_calibration` (Binary),
`certificate_number`, `certificate_partner`, `date_calibration`, `validate_calibration`,
`superseded_by_id`. Via `_inherit` em `afr_qualificacao/models/calibration_instruments.py`:

- `afr_role` Selection: `antes` (pré-campanha), `depois` (pós-campanha), `externo`
  (certificado de terceiro do padrão). Default `externo`.

Seleção, dado o instrumento e as datas de ensaio do relatório:
- **antes** = `afr_role='antes'` com maior `date_calibration ≤ data_inicio_ensaios`;
- **depois** = `afr_role='depois'` com menor `date_calibration ≥ data_fim_ensaios`;
- **padrão** = `afr_role='externo'` com `date_calibration ≤ data_inicio_ensaios ≤ validate_calibration`.

Instrumentos considerados = `os_id.resource_plan_line_ids.instrument_id` (validador →
antes/depois; padrão → externo).

### 4.5 Anexos

`afr.relatorio.anexo`:

| Campo | Nota |
|---|---|
| `sequence`, `included` | ordem e liga/desliga |
| `title` | "Resultados dos Valores Coletados" |
| `slot_kind` | `collect_section` (itens de coleta com `docx_section` ∈ `collect_sections`), `instrument_certs` (antes/depois/externo), `malha_certs`, `bloco` (bloco próprio renderizado como anexo, ex.: protocolo, laudo), `upload` |
| `collect_sections` | Char, lista de `docx_section` separada por vírgula |
| `cert_roles` | Char, lista de `afr_role` |
| `block_id` | M2O `afr.relatorio.block` (quando `slot_kind='bloco'`) |
| `attachment_ids` | M2M `ir.attachment` (upload e override manual) |
| `numero` | computado: 1..N sobre os incluídos |
| `code` | chave estável ("dados", "graficos", "micro", "f0", "malhas", "validador", "padroes", "impressoes", "protocolo_cliente") usada pelo token `anexo('code')` |

`_resolve_files()` devolve a lista ordenada de `(bytes, mimetype, legenda)` do anexo.
Imagem → página PDF via QWeb (1 foto por página com legenda). Não-PDF/não-imagem →
ignorado com achado de verificação.

### 4.6 Estados e revisão

```
draft ──(Emitir: gate §7.3, inclui aprovações internas)──► issued ──(todos aprovadores cliente)──► client_approved
  ▲                                                          │
  └──────────────── (Revisar: Rev.N+1) ◄─────────────────────┘ (também a partir de client_approved)
```

Aprovações internas são registros (`afr.relatorio.aprovacao`), não estado: editar dados,
texto ou anexos em `draft` zera as aprovações internas já dadas (evita aprovar uma versão e
emitir outra).

`waiting` não é estado persistido: "aguardando IB / calibração pós" é derivado dos achados
bloqueantes (§7) e mostrado como badge. Menos estado para manter em sincronia.

`afr.relatorio.emissao` (imutável após criar): `relatorio_id`, `revision`, `pdf_attachment_id`,
`sha256`, `token` (uuid4 hex), `issued_at`, `issued_by`, `blocks_snapshot` (Html congelado
por bloco, JSON), `scan_snapshot` (JSON dos achados + decisões), `superseded` (Boolean).
Write/unlink bloqueados (padrão `_CERTIFICATE_FIELDS` do `afr.qualificacao`).

"Revisar" em `issued`: `revision += 1`, `state = draft`, aprovações internas zeradas; a
emissão anterior só vira `superseded` quando a nova for emitida.

### 4.7 Aprovações

`afr.relatorio.aprovacao`: `papel` (`elaborador`, `emissor`, `executor`, `cliente`),
`user_id` (interno) ou `partner_id` (cliente), `nome_exibicao`, `registro` (CREA etc.),
`approved_at`, `ip`, `access_token` (cliente). Executor é preenchido a partir dos técnicos
dos relatórios diários da OS (`os_id.relatorio_ids.tecnico_ids`) e aprovado implicitamente
pela assinatura já coletada no PWA. Aprovação do cliente não altera o PDF (hash preservado);
fica registrada na página pública de verificação.

## 5. Template, blocos e texto

- **Biblioteca única de seções**: `afr.proposal.section` ganha `document_type`
  Selection (`proposal`, `report`), default `proposal`. As views/filtros da cotação passam a
  filtrar `document_type = proposal`.
- **Novos modelos**, espelhando a cotação: `afr.relatorio.template`,
  `afr.relatorio.template.line`, `afr.relatorio.block`. **Não** se refatora a cotação para
  um mixin nesta fase (risco de regressão alto para ganho pequeno). O único código
  compartilhado é a numeração hierárquica, extraída para função pura
  `hierarchical_numbering(records)` em `models/_numbering.py`, usada pela cotação
  (`_proposal_block_numbering`, sem mudança de comportamento) e pelo relatório.
- **Tipos de bloco** (`REPORT_BLOCK_KINDS`): `static`, `capa`, `indice`, `protocolo`,
  `laudo_micro`, `assinaturas`, `anexo_separador`.
- **Tokens** no corpo (`inline_template`, contexto restrito): `relatorio`, `os`, `partner`,
  `equipment`, `company`, `criterio` (dict: `tolerancia`, `f0_fator`, `f0_minimo`, `valor_d`),
  `anexo` (callable `anexo('micro') → "4"` ou `""` se excluído).
- **Seeds** em `hooks.py` (padrão `PROPOSAL_TEMPLATE_LINES`, só em `post_init_hook` +
  migração para bases existentes): template **Hospitalar** e **Industrial**, seções de texto
  genéricas (sem nome de cliente), checklist padrão, posições de anexo padrão.
- **Congelamento**: na emissão, cada bloco é renderizado para HTML final e gravado em
  `emissao.blocks_snapshot`. Mudanças posteriores em template/seção não afetam emissões.

## 6. Montagem do PDF

`relatorio._build_pdf(watermark: bool) -> bytes`:

1. **Corpo**: `ir.actions.report` QWeb (`report_relatorio_final`) com os blocos incluídos,
   margens superior/inferior reservadas para o carimbo, sem header/footer do layout.
   Cada `anexo_separador` e cada início de bloco carrega um marcador invisível
   (`<span class="rq-mark">@@RQ:<kind>:<id>@@</span>`, texto branco 1pt).
2. **Localizar marcadores**: `pdfminer` (já no container) extrai o texto por página do corpo;
   mapa `marcador → página`.
3. **Intercalar**: após a página de cada separador de anexo, insere as páginas de
   `anexo._resolve_files()` (PyPDF2 1.26, `odoo.tools.pdf`).
4. **Índice**: com o mapa final `bloco/anexo → página`, re-renderiza o corpo passando
   `page_map` no contexto (o índice tem altura fixa por nº de entradas, então não desloca
   páginas); repete 2–3. Se a contagem de páginas do corpo mudar entre as passagens,
   repete uma terceira vez e, persistindo, gera achado.
5. **Carimbo** (reportlab 3.5): para cada página, overlay com cabeçalho (logo, `name`,
   "Equipamento: <descrição> TAG: <tag>", `Rev.NN`, data de emissão) e rodapé
   ("Página X de Y", e-mails da empresa). Páginas de anexo com tamanho ≠ A4 ou sem margem
   são escaladas para caber na área útil antes do overlay. `watermark=True` adiciona
   "MINUTA — SEM VALIDADE" diagonal.
6. Retorna bytes. Minuta → `minuta_attachment_id`. Emissão → `emissao.pdf_attachment_id`.

Execução síncrona na Fase 1 (botão com aviso). Libs confirmadas no container
`odoo_engenapp-web-qualificacao-1` (`/usr/bin/python3`): PyPDF2 1.26.0, reportlab 3.5.59,
pdfminer.six. **Conferir no servidor remoto antes do deploy.**

## 7. Varredura de inconsistência

`relatorio.action_verificar()` apaga achados não-decididos, roda as duas camadas e grava
`afr.relatorio.achado`: `origem` (`regra`/`ia`), `codigo`, `gravidade`
(`bloqueia`/`alerta`/`info`), `mensagem`, `onde` (Char: bloco/anexo/campo),
`decisao` (`pendente`/`procede`/`descartado`), `motivo`, `decidido_por`, `decidido_em`.

### 7.1 Regras (código Python, uma função por regra, registro em dict)

| Código | Gravidade | Regra |
|---|---|---|
| `CERT_DEPOIS_AUSENTE` | bloqueia | validador sem certificado `depois` ≥ fim dos ensaios |
| `CERT_ANTES_AUSENTE` | bloqueia | validador sem certificado `antes` ≤ início |
| `PADRAO_VENCIDO` | bloqueia | padrão sem certificado vigente na data dos ensaios |
| `IB_SEM_LEITURA` | bloqueia | ciclo com carga sem leitura de IB |
| `IB_VENCIDO` | bloqueia | validade do indicador < data dos ensaios |
| `ANEXO_VAZIO` | bloqueia | posição incluída sem arquivo |
| `ANEXO_ILEGIVEL` | bloqueia | PDF corrompido/criptografado |
| `TOKEN_NAO_RESOLVIDO` | bloqueia | `{{` remanescente após render |
| `ANEXO_REF_EXCLUIDO` | alerta | texto referencia `anexo('x')` excluído |
| `CICLOS_CONTAGEM` | alerta | ciclos executados ≠ contratados por tipo |
| `CICLO_SEM_DADOS` | alerta | ciclo sem PDF do validador |
| `CICLO_SEM_JANELA` | alerta | ciclo sem `janela_inicio/fim` |
| `DATA_FORA_JANELA` | alerta | `captured_at` de item de coleta fora de [início, fim] dos ensaios |
| `AMBIENTE_VAZIO` | alerta | temperatura/umidade vazias |
| `CHECKLIST_REPROVADO` | alerta | item de checklist reprovado |
| `CANAL_SEM_CERT` | alerta | canal em `sensor_pos` fora da faixa de canais do validador |
| `APROVACAO_INTERNA` | bloqueia | elaborador ou emissor sem aprovação (checado só no Emitir) |

### 7.2 IA (assistiva, nunca bloqueia)

- Serviço `afr.relatorio.ai` (AbstractModel) com cliente HTTP OpenRouter (`requests`),
  parâmetros em `ir.config_parameter`: `afr_qualificacao.ai_enabled` (default `False`),
  `afr_qualificacao.ai_api_key`, `afr_qualificacao.ai_model` (default um modelo pago barato;
  modelos `:free` dão 429), `afr_qualificacao.ai_timeout` (60).
- Chunking: 1 chamada para o corpo (texto dos blocos renderizados + dados estruturados em
  JSON) + 1 por anexo (texto extraído com pdfminer, truncado a N caracteres), cada uma com o
  "cartão de identidade" do relatório (cliente, TAG, série, datas, ciclos contratados).
- Resposta exigida: JSON `{"achados": [{"gravidade": "alerta|info", "onde": str,
  "trecho": str, "explicacao": str}]}`. Parse tolerante (bloco ```json```); resposta inválida
  ou erro de rede → um achado `IA_INDISPONIVEL` (info), sem quebrar a varredura.
- Achados de IA sempre `alerta` ou `info`, marcados "IA — verificar".

### 7.3 Gate de emissão

`action_emitir()` exige: nenhum achado `bloqueia` pendente; todo `alerta` com decisão
(`procede` = corrigido e re-verificado, `descartado` com motivo). O conjunto de achados e
decisões vai para `emissao.scan_snapshot`.

## 8. Emissão, portal e verificação pública

- `action_emitir()`: roda verificação, checa gate, gera PDF sem marca d'água, calcula
  SHA-256 dos bytes, cria `emissao` (token uuid4), marca anterior `superseded`,
  `state = issued`, posta no chatter.
- QR no rodapé da última página do corpo aponta para `/qualificacao/relatorio/verify/<token>`
  (controller público, mesmo padrão de `/qualificacao/verify/<token>`), que mostra nº,
  revisão, data, hash, status (válido/substituído) e aprovações do cliente. O QR aponta
  para o token, não depende do hash — por isso o PDF pode ser gerado depois do token.
- Portal do cliente: rota com `access_token` da aprovação; mostra o PDF e botão "Aprovar";
  grava `approved_at`, `ip`, nome. Quando todos os aprovadores cliente aprovaram →
  `client_approved`.

## 9. UI do backend

- OS: botão **"Relatórios Finais"** (smart button + ação "Gerar relatórios" que cria um por
  equipamento, idempotente).
- Form do relatório: header com *Gerar minuta · Verificar · Aprovar (papel) · Emitir ·
  Revisar*; statusbar; badge "aguardando …" quando houver bloqueantes.
- Abas: **Dados de campo** (datas, ambiente, critérios, checklist, indicadores, leituras de
  IB; coluna lateral com os itens de coleta da OS para consulta) · **Ciclos** (janelas,
  sensores, PDFs por ciclo) · **Texto** (blocos, mesma UX da cotação) · **Anexos** ·
  **Verificação** (achados + decisões) · **Revisões** (emissões, hash, QR, aprovações).
- Grupos: `user` edita dados/texto/anexos, verifica e gera minuta; aprovação interna pelo
  usuário designado no papel; `manager` emite e revisa.

## 10. Testes

- Numeração hierárquica compartilhada: suíte existente da cotação continua verde.
- Seleção de certificados por data (antes/depois/externo, bordas de data igual).
- Cada regra de verificação com teste positivo e negativo.
- IA com `requests.post` mockado: contrato JSON, JSON inválido, timeout, desligada.
- Anexos: numeração calculada, token `anexo()`, resolução de arquivos, imagem → página.
- PDF: PDFs sintéticos (reportlab) → merge + carimbo → contagem de páginas, texto
  "Página X de Y" presente em todas (pdfminer), marcadores removidos/invisíveis.
- Emissão: hash bate com bytes; emissão imutável; revisão cria Rev.N+1 e marca
  `superseded` só ao emitir a nova.
- Portal: token errado 403/404; aprovação grava dados; estado `client_approved`.

## 11. Fora de escopo (Fase 1) → TODO

- Captura estruturada no PWA (ambiente, checklist, sensores, janelas, IB).
- Extração do arquivo bruto do validador por IA (usa `extracted_json` + `afr.relatorio.ai`).
- Certificado de malha com L.E.Adm / Inc.Total / status no `engc_os` (após descongelar).
- Assinatura ICP-Brasil / gov.br.
- Execução assíncrona (queue_job) da montagem.
- Tabelas de resultado por canal geradas pelo Odoo.

## 12. Ajustes fixados no planejamento

Decididos ao escrever os planos (prevalecem sobre o texto acima; detalhes em
`docs/superpowers/plans/2026-09-26-relatorio-final-00-indice.md`, listas "Fatos fixados"):

- `qualificacao_ids` exclui qualificações canceladas.
- "Copiar sensores do ciclo anterior" busca no relatório inteiro (QI < QO < QD), não só na mesma qualificação.
- Seleção de certificados considera só linhas do plano de recursos do equipamento do relatório (ou sem equipamento).
- `page_map`/`with_markers` vão no `data` do report; `_apply_template()` não roda no `create()`.
- QR é carimbado via reportlab (não por herança do template de assinaturas).
- Achado `bloqueia` não aceita decisão — só sai corrigindo o dado e re-verificando.
- Achado de IA com gravidade `alerta` passa pelo gate (exige decisão); `info` não.
- `action_emitir` levanta `UserError`; `action_aprovar_interno` aprova todas as linhas pendentes do usuário.
- Template industrial semeia 10 posições de anexo (o §2 citava 9 no exemplo).
- Gate de desempenho no fim de P4: minuta de ~150 págs acima de metade do `limit_time_real` ⇒ parar e decidir fila.

## 13. Riscos

- **wkhtmltopdf + marcadores**: texto 1pt branco pode não ser extraído de forma estável →
  fallback: renderizar blocos em PDFs separados e concatenar (contagem direta de páginas).
  Decidir no primeiro task de montagem com spike de 30 min.
- **PDFs de terceiros exóticos** (rotação, CropBox, criptografia) → achado `ANEXO_ILEGIVEL`
  em vez de exceção.
- **Tamanho** (160 págs, dezenas de MB) → attachment em filestore; testar tempo com o maior
  exemplo antes de fechar o sub-projeto 4.
- **IA e dado sensível** → desligada por padrão; ligar é decisão explícita do gestor.
