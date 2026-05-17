# Checklist de Teste — F4 (16.0.3.3.0) Padrões Metrológicos

## Ambiente

- **URL:** http://localhost:8083/web?db=odoo_ecm_test
- **Banco:** `odoo_ecm_test`
- **Container:** `odoo_engenapp-web-1` (porta host 8083 → 8069 container)
- **Login admin:** usuário/senha do ambiente local (mesmo já usado nos testes do F3)
- **Seletor de DB:** http://localhost:8083/web/database/selector — caso `odoo_ecm_test` não apareça por default

## Pré-requisitos

- [x] **0.1** Atualizar o módulo: `Apps` → buscar `afr_qualificacao` → `Upgrade`
- [x] **0.2** Verificar versão exibida = `16.0.3.3.0`
- [x] **0.3** Recarregar browser (Ctrl+Shift+R) para limpar cache de assets/views
- [x] **0.4** Ter pelo menos 1 OS de qualificação existente com ao menos 1 collect.item (ou criar via SO confirmado)
- [x] **0.5** *(após hotfix do bloco 1)* Re-upgrade do módulo via `Apps → afr_qualificacao → Upgrade` + F5 hard reload

---

## Bloco 1 — Cadastro de instrumentos padrão  *(REVISÃO — após hotfix)*

**Mudanças nesta revisão:**
1. Novo menu **Qualificações → Configurações → Padrões Metrológicos (Instrumentos)** — CRUD interno ao módulo (não precisa mais ir em Manutenção → Calibrações)
2. Badge **"Certificado Válido"** (verde) / **"Sem Certificado Válido"** (vermelho) agora aparece no **header do form** do instrumento
3. Tree de instrumentos agora tem coluna **"Cert. Válido"** (toggle readonly)
4. Tree de certificados dentro do instrumento agora tem coluna **"Válido"** por linha
5. Fallback de nome corrigido — usa `name → id_number → tag → marca+modelo` antes de cair em `Instrumento #<id>`

> **Reexecutar bloco 1 inteiro** (apagar os instrumentos antigos `PAD-VALIDO`/`PAD-EXPIRADO`/`PAD-SEM-CERT` antes, ou criar com novo nome — o cache do compute pode ficar inconsistente nos antigos).

Menu novo: **Qualificações → Configurações → Padrões Metrológicos (Instrumentos)** *(grupo Técnico ou superior)*

- [x] **1.0** Abrir o menu novo e confirmar que carrega lista de instrumentos
- [x] **1.1** Criar instrumento **`PAD-VALIDO`** (Nome: "Termômetro Padrão Válido", Nº Identificação: T-001) → salvar
- [x] **1.2** Em "Certificados", adicionar um certificado com:
  - Nº Certificado: `CERT-VAL-001`
  - Data da Calibração: hoje
  - Data de Validade: hoje + 180 dias (o onchange preenche automaticamente, mantenha)
- [x] **1.3** Salvar e voltar ao instrumento → confirmar:
  - **Badge VERDE "Certificado Válido"** no header do form
  - Na tree de certificados: coluna **"Válido"** marcada (toggle ON)
  - Volte à lista de instrumentos: coluna **"Cert. Válido"** marcada
- [x] **1.4** Criar instrumento **`PAD-EXPIRADO`** (Nome: "Termômetro Padrão Expirado", Nº Identificação: T-002)
- [x] **1.5** Em "Certificados", adicionar um certificado com:
  - Nº Certificado: `CERT-EXP-001`
  - Data da Calibração: hoje - 400 dias
  - **Editar manualmente** Data de Validade para hoje - 30 dias
- [x] **1.6** Salvar → confirmar:
  - **Badge VERMELHO "Sem Certificado Válido"** no header
  - Coluna "Válido" do certificado: desmarcada
  - Lista de instrumentos: coluna "Cert. Válido" desmarcada
- [x] **1.7** Criar instrumento **`PAD-SEM-CERT`** (Nome: "Manômetro Sem Certificado", Nº Identificação: M-003) — não adicionar nenhum certificado
- [x] **1.8** Salvar → confirmar:
  - **Badge VERMELHO "Sem Certificado Válido"** no header
  - Lista de instrumentos: "Cert. Válido" desmarcada
- [x] **1.9** Verificar que ao adicionar padrões em coleta, o warning mostra **nome correto** (não "(sem nome)") — feito em Bloco 2


---

## Bloco 2 — Vinculação de padrões no collect.item

Menu: **Qualificações → Coletas / Checklist** (ou abrir collect.item via qualif existente)

- [x] **2.1** Abrir um collect.item qualquer em modo edição
- [x] **2.2** Verificar que existe nova aba **"Padrões Metrológicos"** no notebook
- [x] **2.3** Clicar na aba → tree vazia, sem alert
- [x] **2.4** Adicionar `PAD-VALIDO` via "Add a line" → salvar
- [x] **2.5** Confirmar: **sem alert amarelo** exibido
- [x] **2.6** Adicionar `PAD-EXPIRADO` → salvar
- [x] **2.7** Confirmar: alert amarelo aparece com texto **"Padrões com certificado expirado / ausente: Termômetro Padrão Expirado"**
- [x] **2.8** Adicionar `PAD-SEM-CERT` → salvar
- [x] **2.9** Alert deve listar **dois** nomes (separados por vírgula): Expirado e Sem Cert
- [x] **2.10** Remover `PAD-VALIDO` → texto permanece com Expirado e Sem Cert
- [x] **2.11** Remover `PAD-EXPIRADO` e `PAD-SEM-CERT` → alert desaparece

---

## Bloco 3 — Agregação no afr.qualificacao

Menu: **Qualificações → Qualificações**

- [x] **3.1** Abrir uma qualif que tenha vários collect.items
- [x] **3.2** Em 2 ou 3 collect.items diferentes, vincular padrões variados (ex.: item A → `PAD-VALIDO`; item B → `PAD-EXPIRADO`)
- [x] **3.3** Voltar ao form da qualif → recarregar (F5)
- [x] **3.4** Confirmar que apareceu a aba **"Padrões Metrológicos"** no notebook (entre "Malhas" e "Certificado")
- [x] **3.5** Conferir tree readonly listando **a união** dos padrões dos collect.items (sem duplicar)
- [x] **3.6** Alert amarelo deve aparecer com o(s) padrão(ões) expirado(s)
- [x] **3.7** Adicionar `PAD-VALIDO` a um terceiro collect.item → recarregar qualif → ainda 2 itens na tree (sem duplicar)
- [x] **3.8** Esvaziar todos os collect.items dessa qualif → a aba desaparece (`standard_instrument_count = 0`)

---

## Bloco 4 — Política de aprovação: flag DESLIGADA (default)

- [x] **4.1** Garantir flag desligada: **Configurações → AFR Qualificação → "Bloquear aprovação com padrão expirado"** = **OFF**
- [x] **4.2** Salvar configurações
- [x] **4.3** Abrir uma qualif em estado `draft` ou `in_progress` com ao menos 1 collect.item vinculado a `PAD-EXPIRADO`
- [x] **4.4** Clicar em **"Aprovar"** (action_mark_approved)
- [x] **4.5** Verificar:
  - Estado da qualif mudou para **`Aprovada`**
  - No chatter aparece mensagem amarela: **"Padrões metrológicos sem certificado de calibração válido: Termômetro Padrão Expirado"**
  - Token + hash do certificado foram emitidos

---

## Bloco 5 — Política de aprovação: flag LIGADA

- [x] **5.1** Ligar flag: **Configurações → AFR Qualificação → "Bloquear aprovação com padrão expirado"** = **ON** → Salvar
- [x] **5.2** Criar/reusar nova qualif em `draft` com collect.item vinculado a `PAD-EXPIRADO`
- [x] **5.3** Clicar em **"Aprovar"**
- [ ] **5.4** Verificar:
  - Aparece modal de **erro** (ValidationError) com texto "Padrões metrológicos sem certificado de calibração válido: …"
  - Estado **permanece em `draft`** (não passou para approved)
  - Nenhum certificado emitido
- [x] **5.5** Trocar collect.item: remover `PAD-EXPIRADO`, deixar só `PAD-VALIDO`
- [x] **5.6** Clicar em **"Aprovar"** novamente
- [x] **5.7** Verificar: aprovação passa, estado = `Aprovada`, sem warning no chatter

---

## Bloco 6 — Qualif sem padrões (caso vazio)

- [x] **6.1** Manter flag ligada
- [x] **6.2** Criar qualif sem nenhum collect.item OU sem nenhum collect.item com padrão vinculado
- [x] **6.3** Aprovar → deve passar sem erro nem warning (não bloqueia, não loga aviso)
    - já coloquei em TODO, verifique, fazer a obragatoriedade de instrumentos em coletas, e caso seja obrigatório não deve ser passado nem para aprovação e muito menos aprovado.

---

## Bloco 7 — Sanidade UI

- [x] **7.1** Em **Configurações → AFR Qualificação**: a seção aparece apenas para grupo `AFR Qualificação / Gestor`
- [x] **7.2** Usuário do grupo `AFR Qualificação / Técnico` (sem manager) **não** vê a seção em Configurações
- [x] **7.3** Tree de padrões no collect.item form é editável (pode adicionar/remover)
  - ok. mas o tecnico não deve adicionar e remover instrumentos de medição, nem editá-los.
- [x] **7.4** Tree de padrões no qualif form é **readonly** (apenas leitura)
  
- [x] **7.5** Recarregar form com F5 várias vezes — alertas se mantêm consistentes (compute não-stored)

---

## Reportar

- [ ] Tudo OK → confirmar para eu commitar v16.0.3.3.0
- [x] Algum item falhou → informar bloco/passo + screenshot ou trecho do log
