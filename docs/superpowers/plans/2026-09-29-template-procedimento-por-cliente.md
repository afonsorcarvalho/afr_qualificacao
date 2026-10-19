# Template e procedimento por cliente/equipamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cliente/equipamento guardam procedimento e template padrão; wizard de Gerar OS escolhe procedimento+template por equipamento; Gerar Relatórios pergunta template quando faltar; sem fallback silencioso.

**Architecture:** Dois resolvedores únicos (procedimento, template) consumidos por três wizards (Gerar OS, Relatórios, Aplicar procedimento) e pelos caminhos sem wizard. Procedimento vira N por categoria com `is_default`. Qualificação passa a registrar `procedimento_id` e `relatorio_template_id`.

**Tech Stack:** Odoo 16 (ORM, TransientModel wizards, XML views), migração post-script.

**Spec:** `addons/afr_qualificacao/docs/superpowers/specs/2026-09-29-template-procedimento-por-cliente-design.md`

## Global Constraints

- Módulo `addons/afr_qualificacao` (submodule git próprio), branch `feat/relatorio-final`. Commit de dentro do submodule, linha final `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Não fazer push.** Não stagear f7.png, __pycache__, .superpowers/.
- Versão: `16.0.8.8.4` → `16.0.8.9.0` (Task 1, junto com `migrations/16.0.8.9.0/post-migrate.py`).
- Nomes de campo exatos: `res.partner.afr_relatorio_template_id`, `res.partner.afr_procedimento_ids`, `engc.equipment.afr_procedimento_id`, `afr.qualificacao.procedimento.is_default`, `afr.qualificacao.procedimento_id`, `afr.qualificacao.relatorio_template_id`.
- Origem (string): `equipamento` | `cliente` | `categoria` | `generico` | `False`. Labels UI pt-BR: "Equipamento", "Cliente", "Categoria", "Genérico", "—".
- Sem fallback silencioso de template ("menor sequence") em lugar nenhum.
- Testes: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http` (nunca `odoo -d`). Falha pré-existente conhecida: `TestRelatorioCorpoReport.test_level1_title_zero_padded_and_toc_uses_same_number`.
- UI: :8084 db `qualificacao-dev` (container `odoo_engenapp-web-qualificacao-1`); `-u` + restart; credenciais em `~/.config/engenapp/secrets.md` (nunca escrever). Browser `agent-browser`; recarregar com `location.reload()` (troca de `#` não recarrega). Odoo 16 salva diálogo sujo ao descarregar página — fechar com Descartar.
- Dados de `dados_sensiveis/` nunca em código/testes.
- Textos UI pt-BR.

## Review Focus

1. Cliente com procedimento de OUTRA categoria não deve influenciar equipamento de categoria diferente (cai para padrão da categoria). Teste: Task 1.
2. Dois procedimentos `is_default` na mesma categoria+empresa ⇒ ValidationError; categorias/empresas diferentes ok. Teste: Task 1.
3. Relatório de equipamento sem template resolvível nasce SEM template (nunca o "primeiro"). Teste: Task 2.
4. Wizard Gerar OS com linha desmarcada (incluir=False) não gera nada para ela e não bloqueia por falta de procedimento. Teste: Task 3.
5. Equipamento que já tem OS aberta nesta cotação (rota "cai na OS existente") também recebe o procedimento escolhido e grava `procedimento_id`. Teste: Task 3.

---

### Task 1: Dados, resolvedor de procedimento e migração

**Files:**
- Modify: `models/qualificacao_procedimento.py` (remove `_sql_constraints` uniq; `is_default`; constraint; `resolve_for`; `_resolve_for_equipment`)
- Modify: `models/res_partner.py` (campos)
- Modify: `models/engc_equipment.py` (campo)
- Modify: model de `afr.qualificacao` (arquivo `models/qualificacao.py` ou onde está `_name = "afr.qualificacao"` — localizar) (campos `procedimento_id`, `relatorio_template_id`)
- Modify: views: form do procedimento (`is_default`), form do cliente (aba/grupo "Qualificação": template + procedimentos), form do equipamento (procedimento padrão), form da qualificação (os dois campos readonly/visíveis)
- Create: `migrations/16.0.8.9.0/post-migrate.py`
- Modify: `__manifest__.py` version `16.0.8.9.0`
- Test: `tests/test_template_procedimento_cliente.py` (novo; registrar em `tests/__init__.py`), classe `TestProcedimentoResolver`

**Interfaces (Produces):**
- `afr.qualificacao.procedimento._resolve_for_equipment(equipment, partner) -> tuple(recordset(0..1), str|False)` — `@api.model`, respeita `self.env.company` como `resolve_for`.
- `resolve_for(category)` mantém assinatura; retorna padrão da categoria; se não houver, genérico `is_default`; senão genérico de menor id; senão vazio.
- `res.partner._afr_commercial()` não é necessário: resolvedores recebem `partner` e usam `partner.commercial_partner_id`.

- [ ] Step 1: testes falhando (`TestProcedimentoResolver`, base `AfrQualificacaoTestCommon` de `tests/common.py`; criar categorias A e B, procedimentos: `pA_def` (cat A, default), `pA_alt` (cat A), `pB_def` (cat B, default), `pGen` (sem categoria, default)):
  - equipamento cat A sem nada → `(pA_def, 'categoria')`
  - equipamento com `afr_procedimento_id = pA_alt` → `(pA_alt, 'equipamento')`
  - cliente com `afr_procedimento_ids = [pA_alt]` → equipamento cat A → `(pA_alt, 'cliente')`; equipamento cat B → `(pB_def, 'categoria')` (Review Focus 1)
  - equipamento cat C (sem procedimento) → `(pGen, 'generico')`; sem genérico → `(empty, False)`
  - contato filho do cliente: usa `commercial_partner_id`
  - dois `is_default` cat A mesma empresa → `ValidationError`; cat A empresa diferente → ok (Review Focus 2)
  - cliente com 2 procedimentos da mesma categoria → `ValidationError`
  - `resolve_for(catA) == pA_def`
  - equipamento: atribuir procedimento de outra categoria (não genérico) → `ValidationError` (constraint no equipamento, não só domínio)
- [ ] Step 2: rodar, ver falhar.
- [ ] Step 3: implementar modelos/constraints/resolvedor; views; migração:
  ```python
  # migrations/16.0.8.9.0/post-migrate.py
  def migrate(cr, version):
      cr.execute("ALTER TABLE afr_qualificacao_procedimento DROP CONSTRAINT IF EXISTS afr_qualificacao_procedimento_uniq_category_company")
      cr.execute("UPDATE afr_qualificacao_procedimento SET is_default = TRUE")
  ```
  (conferir nome real da constraint no banco: `\d afr_qualificacao_procedimento` no db de teste; ajustar.) Remover a entrada de `_sql_constraints` do código.
- [ ] Step 4: testes verdes; rodar também classes existentes de procedimento (grep `tests/` por `procedimento`) — sem regressão.
- [ ] Step 5: upgrade qualificacao-dev, conferir no banco que a constraint sumiu e os procedimentos estão `is_default`; abrir form do cliente/equipamento/procedimento via agent-browser (screenshot).
- [ ] Step 6: commit `feat(qualificacao): procedimento e template padrão no cliente/equipamento`.

### Task 2: Resolvedor de template sem fallback silencioso

**Files:** `models/relatorio_texto.py` (`_suggest_template_from_vals`, `_suggest_template`, `create`), testes afetados (`grep -rn "_suggest_template\|template_id" tests/`), `tests/test_template_procedimento_cliente.py` (classe `TestTemplateResolver`).

**Interfaces:**
- Consumes: campos da Task 1.
- Produces: `afr.qualificacao.relatorio._resolve_template(equipment, partner, qualificacoes) -> tuple(recordset(0..1), str|False)` (`@api.model`); origem `qualificacao|cliente|categoria|False` (label "Definido na OS" para `qualificacao`). `_suggest_template_from_vals(vals)` passa a usar `_resolve_template` com `partner = os.partner_id` (ou `vals['partner_id']`) e `qualificacoes = os.qualificacao_ids.filtered(equipment)`.

- [ ] Step 1: testes falhando:
  - qualificação do equipamento na OS com `relatorio_template_id=T_ind` → `(T_ind,'qualificacao')` mesmo com cliente `T_hosp`
  - cliente `T_ind` → `(T_ind,'cliente')`
  - só categoria ligada a `T_hosp` → `(T_hosp,'categoria')`
  - nada → `(empty, False)` e relatório criado nasce com `template_id` vazio e sem blocos após `action_generate_relatorios()` (Review Focus 3)
  - `default_template_id` no contexto continua vencendo
- [ ] Step 2–4: implementar; ajustar testes existentes que dependiam do fallback (ligar template à categoria no setup em vez de depender do "primeiro"); registrar no relatório cada teste ajustado e por quê.
- [ ] Step 5: commit `feat(relatorio): template resolvido por OS/cliente/categoria, sem fallback silencioso`.

### Task 3: Wizard Gerar OS com procedimento e template por equipamento

**Files:** `wizards/qualificacao_os_generate_wizard.py` (+ model `afr.qualificacao.os.generate.wizard.line`), `wizards/qualificacao_os_generate_wizard_views.xml`, `models/sale_order.py` (`_materialize_qualificacoes`, `_explode_collect_items` — aceitar escolha por equipamento), `security/ir.model.access.csv` (linha do wizard line, mesmos grupos do wizard), testes (classe `TestGenerateOsWizardLines`).

**Interfaces:**
- Consumes: `_resolve_for_equipment`, `_resolve_template`.
- Produces: wizard line fields `wizard_id, include (bool, default True), equipment_id, category_id (related), procedimento_id, procedimento_origem (selection), relatorio_template_id, template_origem (selection)`; wizard field `save_as_default (bool)`. `sale.order._materialize_qualificacoes(lines, os, choices=None)` onde `choices = {equipment_id: {'procedimento': rec, 'template': rec}}`; `choices=None` ⇒ comportamento via `_resolve_for_equipment` (compatível com PWA/API/testes).
- Materialização grava `procedimento_id` e `relatorio_template_id` em cada `afr.qualificacao` criada e explode itens do procedimento escolhido (`_explode_into(qualif, phase=qtype)`).

- [ ] Step 1: testes falhando:
  - `default_get`/onchange cria 1 linha por equipamento pendente, com procedimento/template/origem pré-preenchidos
  - linha incluída sem procedimento → `UserError` listando o equipamento; linha excluída sem procedimento → não bloqueia e não gera (Review Focus 4)
  - geração grava `procedimento_id`/`relatorio_template_id` nas qualificações e collect items vêm do procedimento escolhido (ex.: `pA_alt`, não `pA_def`)
  - rota "equipamento já tem OS aberta nesta cotação" também usa/grava a escolha (Review Focus 5)
  - `save_as_default=True` ⇒ `equipment.afr_procedimento_id` e `partner.commercial_partner_id.afr_relatorio_template_id` gravados; False ⇒ não grava
  - caminho sem wizard (`_materialize_qualificacoes(lines, os)` sem choices) continua explodindo o procedimento resolvido
- [ ] Step 2–4: implementar; view: `<field name="line_ids"><tree editable="bottom" create="0" delete="0">` com `include` (boolean_toggle), `equipment_id` readonly, `category_id` readonly, `procedimento_id` (domain `['|',('equipment_category_id','=',category_id),('equipment_category_id','=',False)]`, `options="{'no_create': True}"`), `procedimento_origem` (widget badge), `relatorio_template_id` (`no_create`), `template_origem` (badge); `save_as_default` no rodapé do form com label "Salvar escolhas como padrão (equipamento e cliente)". Colunas/visual iguais ao wizard Aplicar procedimento.
- [ ] Step 5: UI no qualificacao-dev: configurar cliente da cotação C26-09-0019 com template Industrial; criar cotação de teste nova (cópia simples) e abrir Gerar OS — screenshot das linhas com origem; gerar; conferir campos gravados. Limpar dados de teste criados, exceto se úteis ao user (listar no relatório).
- [ ] Step 6: commit `feat(os): wizard de gerar OS escolhe procedimento e template por equipamento`.

### Task 4: Wizard de template ao gerar Relatórios Finais + Aplicar procedimento

**Files:** `models/relatorio_texto.py` (override `action_generate_relatorios_open` em `AfrQualificacaoOs`), novo `wizards/relatorio_template_wizard.py` + views (`afr.qualificacao.relatorio.template.wizard` + `.line`), ACL, `wizards/apply_procedimento_wizard.py` (+ view se preciso), testes (classes `TestRelatorioTemplateWizard`, ajuste em testes do apply wizard), manifest `data` para views novas.

**Interfaces:**
- Consumes: `_resolve_template`, `_resolve_for_equipment`.
- Produces: `action_generate_relatorios_open()` retorna ação do wizard quando algum equipamento de `_relatorio_final_equipments()` sem relatório existente não resolve template; senão comportamento atual (gera + aplica template + abre lista). Wizard: linhas `equipment_id, relatorio_template_id, origem`, bool `save_as_default` ("Salvar como padrão do cliente"); `action_confirm` grava `relatorio_template_id` nas qualificações do equipamento na OS (+ cliente se save), depois chama o fluxo normal. Bloqueia confirmar se linha sem template.
- Apply procedimento: default da linha via `_resolve_for_equipment`; domínio da linha = categoria do equipamento + genéricos; ao aplicar grava `qualif.procedimento_id`.

- [ ] Step 1: testes falhando: tudo resolvido ⇒ retorno é a ação da lista (não wizard) e relatórios criados com template; falta template ⇒ retorno `res_model == 'afr.qualificacao.relatorio.template.wizard'` e nenhum relatório criado; confirmar wizard ⇒ relatórios com o template escolhido; `save_as_default` grava no cliente; linha sem template ⇒ UserError; apply procedimento grava `procedimento_id` e default segue a regra (equipamento > cliente > categoria).
- [ ] Step 2–4: implementar.
- [ ] Step 5: suíte completa do módulo (sem falhas novas).
- [ ] Step 6: UI: na OS26-09-0019 (qualificacao-dev) com cliente sem template → Gerar Relatórios abre wizard (screenshot); com cliente Industrial → gera direto com Industrial. Não apagar o relatório id 2 existente (o botão é idempotente).
- [ ] Step 7: commit `feat(relatorio): perguntar template ao gerar relatórios finais; aplicar procedimento registra o procedimento`.
