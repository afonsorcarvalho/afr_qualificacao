# Checklist de Teste — F4.3 + F4.4 (16.0.3.4.0)

## Ambiente

- **URL:** http://localhost:8083/web?db=odoo_ecm_test (use janela anônima se loop selector)
- **Banco:** `odoo_ecm_test`
- **Container:** `odoo_engenapp-web-1`

## Pré-requisitos

- [x] **0.1** Apps → buscar `afr_qualificacao` → **Upgrade**
- [x] **0.2** Verificar versão `16.0.3.4.0`
- [x] **0.3** Hard reload (Ctrl+Shift+R)

---

## Bloco A — F4.4 Calendar OS (rápido)

Menu: **Qualificações → OS de Qualificação**

- [x] **A.1** Botão **Calendar** aparece junto a tree/kanban (3º ícone)
- [x] **A.2** Click Calendar → grid mensal mostra OS pelas datas `date_planned_start`/`date_planned_end`
- [x] **A.3** Eventos coloridos por técnico (`tecnico_default_id`)
- [x] **A.4** Click numa OS → popup com nome, cliente, técnico, estado
  - preciso que mostre a lista de instrumentos que serão utilizados
- [x] **A.5** Filtros laterais funcionam (técnico, cliente, estado)
- [x] **A.6** Trocar entre views month/week/day (canto superior direito)

---

## Bloco B — F4.3 Setup: mapear unidade → grandeza

Menu: **Manutenção → Calibrações → Unidades de medida** *(via engc_os; ou pelo form de uncertainty line)*

- [x] **B.1** Abrir uma unidade existente (ex: `°C`) → confirmar campo novo **"Grandeza (AFR)"**
- [x] **B.2** Setar **Grandeza (AFR)** = `Temperatura` → salvar
- [x] **B.3** Repetir para `bar` → grandeza `Pressão`
- [x] **B.4** Se faltar unidade, criar `Celsius` (`°C`) + grandeza Temperatura

---

## Bloco C — F4.3 Cobertura derivada no instrumento

Menu: **Qualificações → Configurações → Padrões Metrológicos (Instrumentos)**

- [x] **C.1** Abrir `PAD-VALIDO` criado no F4 (Termômetro)
- [x] **C.2** No certificado existente, adicionar/editar linha de **Incerteza** com `unit_of_measurement = Celsius` (a unidade que recebeu Grandeza Temperatura)
- [x] **C.3** Salvar instrumento → conferir aba **"Cobertura Metrológica"**:
  - **Grandezas cobertas:** Temperatura
  - **Unidades cobertas:** Celsius
- [x] **C.4** Criar instrumento novo `PAD-MULTI` com 2 linhas de incerteza (Celsius + bar) → conferir aba lista as 2 grandezas

---

## Bloco D — F4.3 Procedimento.item com requisitos

Menu: **Qualificações → Configurações → Procedimentos de Qualificação**

- [x] **D.1** Abrir um procedimento existente (ou criar novo) → na tree de itens novas colunas:
  - **Requer padrão** (toggle)
  - **Grandezas requeridas** (tags)
- [x] **D.2** Criar/editar item com `kind="Foto"` → confirmar **Requer padrão = OFF** automaticamente
- [x] **D.3** Criar item com `kind="Arquivo do Qualificador (raw)"` → **Requer padrão = ON** automaticamente
- [x] **D.4** Trocar `kind` de Foto para Excel → toggle muda para ON
- [x] **D.5** No item com Requer padrão = ON, adicionar **Grandezas requeridas** = Temperatura → salvar

---

## Bloco E — F4.3 Cobertura na coleta

Menu: **Qualificações → Coletas / Checklist** (ou via qualif form)

- [x] **E.1** Criar nova qualif que use procedimento com item exigindo Temperatura *(ou aproveitar existente — explosão SO confirm deve trazer)*
- [x] **E.2** Abrir collect.item criado a partir desse procedimento
- [x] **E.3** Aba **"Padrões Metrológicos"** mostra:
  - **Grandezas requeridas:** Temperatura (readonly)
  - Alert **VERMELHO** "Cobertura incompleta. Grandezas faltantes: Temperatura"
      - O alerta não é vermelho. 
- [x] **E.4** Adicionar `PAD-VALIDO` (com Celsius mapeado) → salvar
- [x] **E.5** Alert vermelho desaparece (coverage_complete = True)
- [x] **E.6** Tree de instrumentos mostra coluna `Grandezas` populada
- [x] **E.7** Remover instrumento → alert volta

**Caso multi-grandeza:**
- [x] **E.8** Item exigindo Temperatura + Pressão. Selecionar só `PAD-VALIDO` (temp) → alert "Grandezas faltantes: Pressão"
- [x] **E.9** Adicionar `PAD-MULTI` ou instrumento de pressão → alert some

---

## Bloco F — F4.3 Agregação no qualif form

Menu: **Qualificações → Qualificações**

- [x] **F.1** Abrir qualif que tem coleta com cobertura incompleta
- [x] **F.2** Aba **"Padrões Metrológicos"** sempre visível (mesmo sem instruments)
- [F] **F.3** Alert **VERMELHO** lista coletas incompletas: `• Coleta X — Temperatura, Pressão`
    - onde verifica esse alerta VERMELHO não consegui indentificar
- [F] **F.4** Corrigir uma coleta → alert mostra só as restantes
- [x] **F.5** Tree de instrumentos no qualif tem coluna `Grandezas`

---

## Bloco G — F4.3 Gate aprovação

- [ ] **G.1** **Configurações → AFR Qualificação** → nova flag **"Bloquear aprovação com cobertura incompleta"**

### G.1 — Flag OFF (default)
- [x] **G.2** Flag OFF + qualif com coleta required incompleta → clicar **Aprovar**
- [x] **G.3** Estado vira **Aprovada**. Chatter recebe mensagem amarela "Coletas com cobertura de grandezas incompleta"

### G.2 — Flag ON
- [x] **G.4** Ligar flag → salvar
- [x] **G.5** Nova qualif draft com coleta required incompleta → clicar **Aprovar**
- [F] **G.6** Modal **ValidationError** com lista das coletas incompletas. Estado **permanece draft**
- [x] **G.7** Completar instruments → Aprovar → passa
#### OBS 
  - Deve verificar ao cancelar ordem de serviço de Qualificação voltar qualificações para não aprovadas, e reabrir todos os relatorios
### G.3 — Coleta não-required ou non-requires_instrument
- [x] **G.8** Qualif só com itens `required=False` ou `requires_instrument=False` → aprovação passa mesmo sem instruments

---

## Reportar

- [ ] Tudo OK → confirmar para commitar v16.0.3.4.0
- [X] Falha → bloco/passo + screenshot/log
