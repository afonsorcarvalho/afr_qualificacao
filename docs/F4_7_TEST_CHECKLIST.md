# Checklist F4.7 — Coletas só via Relatório (16.0.3.4.0)

## Ambiente

- **URL:** http://localhost:8083/web?db=odoo_ecm_test (janela anônima se loop)
- **Banco:** `odoo_ecm_test`
- **Upgrade:** Apps → afr_qualificacao → Upgrade + hard reload

---

## Bloco A — Warning visual em collect.item

Menu: **Qualificações → Coletas / Checklist**

- [x] **A.1** Abrir um collect.item state=pending → confirmar **sem alert amarelo**
- [x] **A.2** Subir arquivo direto no form (sem setar `Relatório`) → salvar
- [x] **A.3** State vira `collected` automaticamente
- [x] **A.4** **Alert AMARELO** aparece: "Coleta sem relatório vinculado. Coletas devem ser realizadas via Relatório da OS. Aprovação da qualificação será bloqueada."
  -- quero que apareça no Coletas/Checklist da OS de qualificação o alerta dizendo que coleta x tá sem relatorio
- [x] **A.5** Editar campo "Relatório que coletou" → selecionar relatório existente da mesma OS → salvar
- [x] **A.6** Alert desaparece

---

## Bloco B — Tabs novas no relatório

Menu: **Qualificações → OS de Qualificação** → abrir OS → tab Relatórios → criar/abrir relatório

- [x] **B.1** No form do relatório, conferir 2 tabs novas:
  - **Coletas Realizadas** (O2M `collect_item_ids` neste relatório)
  - **Coletas Pendentes da OS** (computed, todos state=pending+required da OS pai)
- [x] **B.2** Tab "Coletas Pendentes": lista todos os items required em state=pending da OS
- [x] **B.3** Click num item pendente → abre form do collect.item
- [F] **B.4** No form, anexar arquivo + setar `Relatório que coletou` = este relatório → salvar
    -- não consigo anexar arquivo e nem Setar Relatorio que coletou que tem que ser automatico quando adiciono o arquivo, e se excluir tirar o apontamento do relatorio.
- [F] **B.5** Voltar ao relatório → item aparece em **"Coletas Realizadas"** e some de **"Coletas Pendentes"**


---

## Bloco C — Gate hard na aprovação

- [ ] **C.1** Qualif draft com collect.item required, state=collected, **sem relatorio_id** (cenário A.4)
- [ ] **C.2** Clicar **Aprovar** no qualif (ou via OS.action_approve)
- [ ] **C.3** **ValidationError** com mensagem: "Coletas marcadas como coletadas mas sem relatório vinculado: <nomes>. Coletas devem ser realizadas através de um Relatório da OS."
- [ ] **C.4** Estado **permanece draft/in_progress**

### C.1 — Reabilitar com relatório

- [ ] **C.5** Editar collect.item → setar `Relatório que coletou`
- [ ] **C.6** Clicar Aprovar de novo → passa

### C.2 — Itens não-required

- [ ] **C.7** Qualif com collect.item `required=False`, collected sem relatório → Aprovar passa (gate só bloqueia required)

---

## Reportar

- [ ] Tudo OK → confirmar para commitar v16.0.3.4.0 (inclui F4.3 + F4.4 + F4.7)
- [ ] Falha → bloco/passo + screenshot
