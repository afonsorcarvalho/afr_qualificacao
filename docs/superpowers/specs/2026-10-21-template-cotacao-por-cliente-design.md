# Template de cotação por cliente + tempo-alvo — Design (Etapa A, Odoo)

Data: 2026-10-21 · Módulo: `afr_qualificacao` · Etapa B (cotação no celular) virá em spec própria e consome esta.

## 1. Intenção

Cotar cliente com muitos equipamentos é lento: quase tudo se repete. Equipamentos
da mesma categoria no mesmo cliente costumam ter o mesmo escopo (qualificações,
ciclos, tempo) e o mesmo preço; a exceção típica é um ciclo a mais. O user quer
que cada cliente tenha o seu "jeito padrão" por categoria de equipamento,
aplicado sozinho quando o equipamento entra na cotação, com preço e tempo
acordados.

Sucesso: cotar um cliente recorrente vira "adicionar equipamentos e conferir";
só exceções são editadas à mão.

## 2. Decisões do user

1. **Template por cliente e por categoria** de equipamento (um por categoria por cliente).
2. **Aplicação automática**: ao adicionar um equipamento à cotação, o template do
   cliente para a categoria do equipamento é escolhido e aplicado.
3. **Preço**: uma **tabela geral** para todos os clientes (preço de lista por
   hora dos serviços). Preço específico de cliente mora **só no template do
   cliente**, como **preço-alvo do equipamento**, rateado entre as linhas como o
   preço-alvo atual. Não se usa tabela de preços por cliente.
4. **Tempo-alvo**: informar o tempo total do equipamento (ex.: 1,5 dia) e ratear
   em horas entre as linhas, **proporcional às horas atuais de cada linha** (igual
   ao rateio de preço).
5. **Preço e tempo são independentes**: com preço acordado (preço-alvo), o total
   do equipamento **não muda** quando o tempo muda — o preço por hora se ajusta
   para manter o total.
6. **Manutenção do template do cliente** só pelo botão **"Gravar como padrão
   deste cliente"** (sem aprendizado automático).
7. **"Gravar como padrão" sem preço-alvo grava o total atual como preço combinado**
   (`price_base` congela); idem tempo (`estimated_days` = horas totais / jornada).
8. **Reajuste anual dos preços combinados**, por cliente, na **data de aniversário**
   do contrato dele: por **índice** (busca automática no Banco Central; digitação
   manual como reserva), por **porcentagem** ou por **valor absoluto**.

## 3. Estado atual (código, 2026-10-21)

- `afr.qualificacao.config.template` (models/config_template.py): `equipment_category_id`,
  `do_qi/do_qo/do_qs`, linhas `qo_line_ids`/`qd_line_ids`/`calib_line_ids`/`qd_point_ids`
  (cada uma com `qty`, `estimated_hours`), `work_hours_per_day`, **`price_base` e
  `estimated_days` existem mas não são aplicados**.
- Configurador (wizards/qualificacao_configurator.py): template escolhido à mão por
  equipamento (filtro de categoria só no domínio da view); onchange copia o template;
  `action_save_as_template` cria template novo.
- Preço da linha = `list_price` do produto por hora; `product_uom_qty = qualif_cycle_qty × estimated_hours`.
- Preço-alvo: `equipment_target_price` na linha de seção; `_apply_equipment_target` →
  `allocate_target` (models/price_allocation.py), peso = `price_subtotal` atual;
  `is_rateio_priced` protege `price_unit`.
- Tempo: só somado (`estimated_hours_total`, `_qualif_estimated_days` = horas / `work_hours_per_day`).
- Padrão "por cliente" já existente a seguir: procedimento — `res.partner.afr_procedimento_ids`
  (no máx. 1 por categoria, constraint) + `_resolve_for_equipment` com cadeia equipamento →
  cliente (parceiro comercial) → padrão da categoria → genérico.

## 4. Design

### 4.1 Template do cliente
- `afr.qualificacao.config.template` ganha `partner_id` (M2o `res.partner`, parceiro
  comercial; vazio = template geral). Constraint: no máximo **um template ativo por
  (partner_id, equipment_category_id, company_id)** quando `partner_id` setado.
- `res.partner` ganha `afr_config_template_ids` (O2m inverso) e aba
  **"Templates de cotação"** no form do cliente (lista por categoria, editável).
- Resolver `config_template._resolve_for_equipment(equipment, partner, company)`:
  template do cliente (parceiro comercial) da categoria → template geral da categoria
  (menor `sequence`) → nenhum. Retorna também a origem (`cliente` / `categoria` / `none`)
  para exibir no configurador.

### 4.2 Aplicação automática
- No configurador, ao adicionar/escolher um equipamento numa linha sem template, o
  resolver preenche `config_template_id` e dispara o onchange existente de aplicação.
  Mostra a origem ("Template do cliente" / "Template da categoria").
- Template escolhido à mão sempre vence (não sobrescrever escolha do user).
- Cotações existentes não são alteradas.

### 4.3 Preço-alvo vindo do template
- Ao aplicar (`action_apply`), se o template tem `price_base > 0` e a linha de seção do
  equipamento **não** tem `equipment_target_price` já definido pelo user, grava
  `equipment_target_price = price_base` e aplica o rateio existente.
- Linhas nascem com preço de lista (tabela geral), como hoje.
- Exibir no configurador/cotação a diferença: total pela tabela vs. preço acordado.

### 4.4 Tempo-alvo
- Linha de seção do equipamento ganha `equipment_target_days` (Float, dias).
  Template `estimated_days > 0` preenche esse campo na aplicação (mesma regra do preço:
  não sobrescreve valor do user).
- `_apply_equipment_time_target`: horas-alvo = dias × `work_hours_per_day` do equipamento;
  rateia entre as linhas-base (mesmo conjunto de `_rateio_base_lines`) **proporcional a
  `qualif_cycle_qty × estimated_hours` atual** de cada linha; ajusta `estimated_hours`
  por linha (horas por ciclo = horas da linha / `qualif_cycle_qty`); arredondamento em
  0,25 h com resíduo na maior linha, garantindo soma exata.
- **Ordem**: tempo primeiro, depois preço-alvo (se houver). Assim, com preço acordado,
  `allocate_target` recalcula `price_unit` sobre as novas quantidades e o total do
  equipamento permanece igual ao alvo. Sem preço-alvo, o preço acompanha as horas
  (preço de lista por hora) — **escolha do builder/controller, ver §6**.
- Botão "Aplicar tempo-alvo" por equipamento e "Aplicar tempos-alvo" na cotação, ao lado
  dos de preço; delta/estado do tempo como o do preço (alvo vs. soma atual).

### 4.5 "Gravar como padrão deste cliente"
- No configurador (por equipamento) e na linha de seção da cotação: cria ou **atualiza**
  o template do cliente para a categoria do equipamento a partir do escopo atual
  (QI/QO/QS, ciclos, malhas, horas, jornada) + `price_base` = preço-alvo atual (ou total
  atual do equipamento se não houver alvo) + `estimated_days` = tempo-alvo atual (ou
  horas totais / jornada).
- Se já existe, pede confirmação ("Substituir o padrão de Autoclave do cliente X?").
- Reaproveita a lógica de `action_save_as_template`.

### 4.6 Reajuste dos preços combinados
- `res.partner` (parceiro comercial) ganha `afr_reajuste_data` (Date, aniversário) e
  `afr_reajuste_indice` (Selection: `ipca`, `igpm`, `inpc`, vazio).
- Cron diário: clientes com aniversário hoje (dia/mês) e templates com `price_base > 0`
  recebem **atividade** "Reajustar preços combinados" para o responsável comercial
  (`user_id` do parceiro, fallback admin).
- Wizard **"Reajustar preços combinados"** (botão no cliente): tipo = índice / % / valor;
  índice → busca acumulado 12 meses até o mês anterior ao aniversário na API SGS do
  Banco Central (`api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados`, séries IPCA 433,
  IGP-M 189, INPC 188, variação mensal %; acumulado = Π(1+v/100)−1); falha/timeout →
  campo % editável com aviso; % → multiplica; valor → soma ao `price_base` de cada
  template. Prévia linha a linha (template, categoria, antes, depois) antes de confirmar;
  arredondamento a centavos.
- Aplica só ao `price_base` dos templates **daquele cliente**; cotações existentes não mudam.
- Histórico `afr.qualificacao.reajuste` (cliente, data, tipo, índice, período, percentual
  aplicado, usuário) + linhas (template, valor antigo, novo); visível numa aba do cliente
  e postado no chatter do cliente.
- HTTP com `urllib.request`, timeout 10 s (padrão do `afr_brasil_lookup`); testes com mock.

### 4.7 Usabilidade (requisito do user)
Forms e wizards o mais simples e intuitivos possível:
- Campos avançados escondidos até serem necessários (`invisible`/grupos colapsados);
  o caminho comum cabe numa tela sem rolagem.
- Linguagem do usuário nos rótulos ("Preço combinado", "Tempo combinado (dias)",
  "Padrão deste cliente"), com `help` curto; nunca nomes técnicos.
- Origem do template sempre visível como selo ("Padrão do cliente" / "Padrão da categoria").
- Ações principais como botões claros no topo; confirmações só onde há perda (substituir
  padrão, aplicar reajuste), com prévia do efeito.
- Validar views no navegador (agent-browser) antes de declarar pronto.

## 5. Não-objetivos / anti-objetivos

- Não: tabela de preços por cliente (`property_product_pricelist` não é usado).
- Não: aprendizado automático do template do cliente.
- Não: alterar cotações já existentes ao criar/editar templates.
- Anti: aplicar template e sobrescrever silenciosamente preço/tempo que o user digitou.
- Anti: o total acordado mudar por causa de mudança de tempo.
- Fora: tela de cotação no celular (Etapa B).

## 6. Escolhas do controller (sem confirmação explícita do user)

- Sem preço-alvo, mudança de tempo altera o preço (preço de lista por hora), como hoje.
- Template do cliente modelado como `partner_id` no próprio config template (não M2M
  como procedimento), para reaproveitar todo o editor existente.
- Arredondamento do tempo: **horas da linha** em múltiplos de 0,25 h, soma exata (resíduo
  na maior linha); horas por ciclo derivadas (podem ser fracionárias quando ciclos > 1).
  Pesos todos zero → distribui igualmente.
- Re-apply do configurador: `equipment_target_days` é capturado e regravado como o
  `equipment_target_price`; após recriar as linhas, reaplica tempo e depois preço quando
  houver alvos. Horas rateadas relidas pelo wizard são aceitas como escopo atual.
- Preço/tempo-alvo do template só são gravados quando o **equipamento entra pela primeira
  vez** na cotação (não repõe alvo zerado pelo user num re-apply).
- Auto-aplicação: onchange novo de `equipment_id` na linha do configurador + o wizard de
  lote ganha opção "Usar template do cliente/categoria" (ligada por padrão quando existe
  template), resolvendo por equipamento; linhas carregadas de cotação existente sem
  template não são auto-preenchidas.
- "Aplicar tempo-alvo" sempre reencadeia o rateio de preço quando há preço-alvo; edição
  manual de horas mantém o comportamento atual (delta visível + botão).
- "Gravar como padrão" só no configurador (onde existe o escopo estruturado).
- Unicidade do template de cliente: constraint Python considerando só `active=True`;
  `company_id` obrigatório (empresa da cotação); aba "Templates de cotação" e reajuste
  só em parceiros comerciais (`is_company` ou sem pai).
- Reajuste: índice de referência padrão IPCA; acumulado 12 meses até o mês anterior.

## 7. Testes esperados

Resolver (cliente > categoria > nenhum; parceiro comercial; empresa); constraint de
unicidade; auto-aplicação no configurador sem sobrescrever escolha manual; preço-alvo do
template aplicado e não sobrescrevendo alvo do user; rateio de tempo (soma exata,
proporcional, arredondamento); tempo depois do preço mantém total; "gravar como padrão"
cria e atualiza; migração não necessária (campos novos com default vazio).
