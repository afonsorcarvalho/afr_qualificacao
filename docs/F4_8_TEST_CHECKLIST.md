# Checklist F4.8 — Ciclos + Malhas via Relatório (16.0.3.4.0)

## Ambiente
- **URL:** http://localhost:8083/web?db=odoo_ecm_test (janela anônima se loop)
- **Upgrade:** Apps → afr_qualificacao → Upgrade + hard reload (Ctrl+Shift+R)

---

## Bloco A — Ciclos (QD) via Relatório

Menu: **Qualificações → OS de Qualificação** → abrir OS QD → tab Relatórios → abrir/criar relatório

- [ ] **A.1** Tab nova **"Ciclos (QD)"** no form do relatório
- [ ] **A.2** Sub-seção **"Ciclos executados neste relatório"** — vazia inicialmente
- [ ] **A.3** Sub-seção **"Ciclos pendentes na OS"** — lista todos cycles pending da OS
- [ ] **A.4** Click no botão **Coletar** (paperclip azul) numa linha pendente
- [ ] **A.5** Form do ciclo abre **em modo edit** (target=current)
- [ ] **A.6** Campo `Relatório que coletou` já pré-preenchido com este relatório
- [ ] **A.7** Mudar status para **Aprovado** (statusbar topo) → `executed_date` auto-preenche
- [ ] **A.8** Salvar → voltar ao relatório (breadcrumb)
- [ ] **A.9** Ciclo agora em **"executados neste relatório"** e some de pendentes
- [ ] **A.10** Alternativa: botão "Abrir lista completa" embaixo abre vista filtrada

---

## Bloco B — Malhas Calibração via Relatório

Menu: **Qualificações → OS de Qualificação** → OS de calibração → relatório

- [ ] **B.1** Tab **"Malhas (Calibração)"** aparece
- [ ] **B.2** Click **Coletar** numa malha pendente → form abre editavel
- [ ] **B.3** Header tem **2 botões**:
  - **"Criar Calibração"** (azul, fa-flask) — visível quando `engc_calibration_measurement_id` vazio
  - **"Abrir Calibração"** (cinza, fa-external-link) — visível quando vinculada
- [ ] **B.4** Click **"Criar Calibração"** → confirm dialog → cria engc.calibration auto-populada e abre form dela
- [ ] **B.5** Voltar à malha → `relatorio_id` já preenchido (via context)
- [ ] **B.6** Marcar state=Aprovado → `executed_date` auto
- [ ] **B.7** Salvar → volta ao relatório → malha em "Malhas executadas"

### B.8 — Pré-requisitos faltantes
- [ ] **B.8.1** Sem **Técnico Padrão** na OS → UserError "Defina o Técnico Padrão na OS..."
- [ ] **B.8.2** Sem **Padrão Metrológico** em nenhuma coleta da qualif → UserError "Vincule pelo menos um Padrão Metrológico..."
- [ ] **B.8.3** Sem procedure cadastrado em engc_os → UserError "Nenhum Procedimento/Norma..."

---

## Bloco C — Gate hard na aprovação

- [ ] **C.1** Qualif QD com cycle.state=passed mas **sem relatorio_id** (manipule via debug ou tree edit)
- [ ] **C.2** Clicar **Aprovar** no qualif → ValidationError com lista dos ciclos órfãos
- [ ] **C.3** Mesmo para malha — ValidationError lista malhas órfãs
- [ ] **C.4** Após vincular relatorio_id em todos → Aprovar passa

---

## Bloco D — Onchange & auto-clear

- [ ] **D.1** Abrir ciclo passed → trocar state para **Pendente** → `relatorio_id` e `executed_date` limpam
- [ ] **D.2** Mesmo para malha
- [ ] **D.3** Tree decorations: linha **vermelha** se `collected_without_relatorio=True`

---

## Reportar

- [ ] Tudo OK → confirmar para commit v16.0.3.4.0 (F4.3 + F4.4 + F4.7 + F4.8 juntos)
- [ ] Falha → bloco/passo + screenshot
