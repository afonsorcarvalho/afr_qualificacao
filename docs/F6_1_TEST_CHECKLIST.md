# Checklist F6.1 — Relatório DOCX individual por qualificação (16.0.3.5.0)

## Ambiente
- **URL:** http://localhost:8083/web?db=odoo_ecm_test (janela anônima se loop)
- **Upgrade:** Apps → afr_qualificacao → Upgrade + hard reload (Ctrl+Shift+R)

## Pré-condições
- Módulo upgraded para 16.0.3.5.0 sem WARNING/ERROR no log
- Templates default carregados: `Configurações → Técnico → Templates DOCX` deve listar 3 (QI, QO, QD)
- `python-docx` e `docxtpl` instalados no Python do container Odoo

---

## Bloco A — Data seed + UI templates

- [ ] **A.1** Menu **Qualificações → Configuração → Templates DOCX** lista 3 records:
  - Qualificação de Instalação (QI)
  - Qualificação Operacional (QO)
  - Qualificação de Desempenho (QD)
- [ ] **A.2** Cada template tem `filename` preenchido e `datas` > 10KB (download de teste funciona)
- [ ] **A.3** Template legado `qualificacao_template.docx` **não** aparece mais

---

## Bloco B — Campo docx_section em procedimento.item

Menu: **Qualificações → Configuração → Procedimentos de Qualificação**

- [ ] **B.1** Abrir procedimento existente (ou criar QI novo)
- [ ] **B.2** Coluna nova **"Seção no relatório DOCX"** visível na tree de itens (optional=show)
- [ ] **B.3** Selection oferece ~20 opções agrupadas por prefixo (QI/QO/QD/anexos)
- [ ] **B.4** Setar valor diferente por item (ex: `qi_documentos`, `qi_utilidades`, `qi_componentes`)
- [ ] **B.5** Salvar → persistência OK

---

## Bloco C — Propagação para collect.item (related stored)

- [ ] **C.1** Criar nova qualif QI a partir de SO (fluxo quote-first) → explosão materializa collect.items
- [ ] **C.2** Abrir um collect.item gerado a partir do procedimento → campo **"Seção no relatório DOCX"** já populado conforme procedimento.item
- [ ] **C.3** Tree de coletas no form da qualif: coluna `docx_section` disponível (optional=hide)
- [ ] **C.4** Ajustar manualmente em um collect.item → grava (related editável)

---

## Bloco D — Geração DOCX (fallback automático por tipo)

- [ ] **D.1** Qualif QI **sem** `docx_template_id` selecionado → botão **Gerar DOCX** abre arquivo `.docx` em nova aba
- [ ] **D.2** Mesmo para QO e QD (fallback resolve template default por `qualification_type` via xmlid)
- [ ] **D.3** QS gera com template QI (gap declarado — F6.x futuro adiciona template específico)
- [ ] **D.4** Qualif tipo Calibração: action mantém comportamento legado (não passa por este fluxo)

---

## Bloco E — Geração DOCX (template manual)

- [ ] **E.1** Selecionar `docx_template_id` = "Qualificação Operacional (QO)" numa qualif QI
- [ ] **E.2** Clicar **Gerar DOCX** → render usa template QO (manual prevalece sobre fallback automático)
- [ ] **E.3** Trocar para template inexistente / corrompido → UserError claro

---

## Bloco F — Conteúdo do DOCX renderizado

Baixar DOCX gerado de uma qualif QI completa (com partner, equipment, instrumentos, coletas em várias seções) e abrir em LibreOffice/Word.

- [ ] **F.1** Cabeçalho: nome do cliente, fantasia, CNPJ, endereço corretos
- [ ] **F.2** Bloco equipamento: descrição, fabricante, modelo, número de série
- [ ] **F.3** Bloco aprovação: elaborado/revisado/aprovado com nomes corretos
- [ ] **F.4** Tabela **Utilidades** povoada (caso haja coletas com `docx_section=qi_utilidades`)
- [ ] **F.5** Tabela **Documentos** povoada (caso haja `qi_documentos`)
- [ ] **F.6** Tabela **Instrumentos padrão** lista padrões dos collect.items (sem duplicatas)
- [ ] **F.7** Sem traços `—` ou strings tipo `{{ var }}` aparentes nos blocos cobertos
- [ ] **F.8** Tabelas técnicas (mapeamento_ciclo, penetracao_ciclo, repetibilidade) renderizam linhas com **metadados básicos** (nome, captured_at, conforme=Sim/Não); colunas técnicas (t_min, t_max, etc.) ficam vazias — GAP F6.x

---

## Bloco G — Anexo persistido

- [ ] **G.1** Após gerar DOCX, abrir tab **Anexos** (paperclip) do form da qualif → arquivo `.docx` listado com nome `<qualif.name>.docx`
- [ ] **G.2** Mimetype `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- [ ] **G.3** Re-gerar DOCX cria **novo** attachment (não sobrescreve)

---

## Bloco H — Testes automatizados

```bash
docker exec -it <container> odoo --test-enable --test-tags afr_qualificacao --stop-after-init -d <db>
```

- [ ] **H.1** 12 tests em `test_docx_render.py` passam (tag `f6_1`)
- [ ] **H.2** Suíte F1-F5 mantém verde (sem regressão)

---

## Bloco I — Gaps declarados (NÃO devem ser bloqueio)

- [ ] **I.1** Coletas QD sem `docx_section` configurada → não aparecem em nenhuma tabela do DOCX (esperado). User adiciona via procedimento.
- [ ] **I.2** Dados granulares de sensores (sensor/t_min/t_max) não aparecem — F6.x próximo (parse XLSX/CSV)
- [ ] **I.3** Blocos `revisoes[]` e `conclusao.validade` ficam vazios — F7 ou descartado
- [ ] **I.4** Sem template UNIFICADO por OS — F6.2
- [ ] **I.5** Sem geração PDF — F6.3

---

## Reportar

- [ ] Tudo OK → confirmar para commit v16.0.3.5.0
- [ ] Falha → bloco/passo + screenshot + log Odoo se aplicável
