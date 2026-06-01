# Design — Proposta de Venda + Calibração + Bloco Dados Cadastrais

**Data:** 2026-05-31
**Módulo:** `afr_qualificacao` (submodule)
**Versão alvo:** 16.0.5.7.0
**Fontes:** `docs/Exemplos diversos/4 - Proposta de Venda + Calibração.doc` e
`docs/Exemplos diversos/REFERENCIA_PROPOSTAS_LABQUALI.md` (§5, §6, §7).

## Objetivo

Adicionar o 3º arquétipo de proposta da LabQuali — **Venda + Calibração de
instrumentos** — reusando o sistema LEGO de propostas existente
(`afr.proposal.template` → `afr.proposal.block` → relatório
`quotation_template.xml`). Sem wizard, sem flag de produto, sem geração de
registros no confirm: o comercial adiciona os produtos manualmente nas linhas
do `sale.order`, escolhe o template e gera o PDF.

Adicionalmente: criar um bloco institucional **"Dados Cadastrais – LabQuali"**
(razão social, CNPJ, IE/IM, endereço, dados bancários/PIX, responsáveis,
registros CREA) e torná-lo **padrão em TODAS as propostas** (template QI/QO/QD
existente + novo template venda+calibração).

## Escopo

**Inclui:**
1. Novo `block_kind` `sales_items` — tabela de itens de venda do SO.
2. Seções de texto (seed) com o conteúdo institucional do doc 4.
3. Seção `SEC-DADOS-CADASTRAIS` (institucional, comum a todas as propostas).
4. Template seed "Proposta Venda + Calibração".
5. Inclusão do bloco Dados Cadastrais no template QI/QO/QD existente
   (fresh-install via hook + deploy `-u` via migration).
6. Testes.

**Fora de escopo:** wizard/configurador; flag/categoria de produto; geração de
`engc.calibration`/`engc.os` no confirm; doc 3 (calibração pura, embora o bloco
`sales_items` já o suporte para uso futuro).

## Componentes

### C1 — `block_kind` `sales_items` (código)

**Arquivo:** `models/proposal_template.py`
Adicionar à constante `PROPOSAL_BLOCK_KINDS` (compartilhada por
`afr.proposal.template` e `afr.proposal.block`):

```python
("sales_items", "Tabela de Itens (Venda + Calibração)"),
```

**Arquivo:** `reports/quotation_template.xml`
Novo ramo `<t t-if="block.block_kind == 'sales_items'">` renderizando tabela
`qq-table` com colunas: **Descrição | Quant. | Valor Unitário | Valor Total**.

- Fonte das linhas: `doc.order_line.filtered(lambda l: not l.display_type and
  not l.is_proposal_optional)` — linhas de venda comuns (numa proposta
  venda+calib não há linhas `is_qualificacao_managed`).
- Por linha: `l.name` (descrição), `int/float l.product_uom_qty`,
  `l.price_unit`, `l.price_subtotal` (monetário, `doc.currency_id`).
- Linha de total (`qq-total-table`): `doc.amount_untaxed` / `amount_tax` /
  `amount_total`, espelhando o bloco `financial`.
- Respeita `block.show_title` / `block.title` (default "Equipamentos a serem
  Calibrados"), `blk_num`, `is_child` — igual aos outros ramos.

Helper opcional `sale.order._sales_item_lines()` se a expressão inline ficar
densa; preferir inline simples (mirroring do ramo `optionals`).

### C2 — Seções de texto institucional (seed XML)

**Arquivo novo:** `data/proposal_venda_calibracao_seed.xml` (`noupdate="1"`).
Registros `afr.proposal.section` (categoria reusada entre parênteses):

| xmlid | code | categoria | conteúdo (do doc 4 / ref §3, §5, §6) |
|---|---|---|---|
| `sec_vc_objetivo` | SEC-VC-OBJETIVO | objetivo | Fornecimento de serviços de Calibração + fornecimento de instrumentos p/ monitoramento/controle/segurança, conforme necessidade do cliente. `{{ partner.name }}`. |
| `sec_vc_metodologia` | SEC-VC-METODOLOGIA | metodologia | Padrões calibrados rastreados à RBC/INMETRO; confiabilidade metrológica. |
| `sec_vc_escopo` | SEC-VC-ESCOPO | escopo | Limitado aos itens listados; pode incluir instrumentos calibrados temp/umidade, controle de processos, válvulas de segurança. |
| `sec_vc_procedimento` | SEC-VC-PROCEDIMENTO | normas | Def. de Calibração (NBR 16328:2014) + bullets: critérios de aceitação pelo cliente; certificado com incerteza 95% e coef. de abrangência (K); dados dos padrões; instrumentos entregues com certificado. |
| `sec_vc_condicoes` | SEC-VC-CONDICOES | condicoes | Valor total (impostos inclusos); frete (Correios SEDEX HOJE / SEDEX D+1 / Motoboy 50 min); previsão dias execução; prazo certificados 15 dias. |
| `sec_vc_documentacao` | SEC-VC-DOCUMENTACAO | condicoes | Documentação digital assinada eletronicamente; pastas impressas opcionais (valor + correio). |
| `sec_vc_pagamento` | SEC-VC-PAGAMENTO | financeiro | À vista, faturado na aprovação. |
| `sec_vc_validade` | SEC-VC-VALIDADE | condicoes | Validade 60 dias. |
| `sec_vc_observacoes` | SEC-VC-OBSERVACOES | custom | Preço sofre alteração se quantidade alterada. |

Reusa `proposal_section_aceite` (SEC-ACEITE) existente.

### C3 — Seção Dados Cadastrais (seed XML, institucional comum)

No mesmo arquivo: `afr.proposal.section` `sec_dados_cadastrais`
(SEC-DADOS-CADASTRAIS, categoria `credenciais`). Corpo HTML estático (LabQuali,
ref §7): Nome Fantasia, Razão Social, CNPJ, IE, IM, Endereço, e-mail comercial;
Dados Bancários (Itaú Ag 666-4 CC 99108-7, PIX CNPJ); Responsáveis (Paulo Neves
RT, Bruno Neves Gerente Técnico, Ariel Neves Adm/Financeiro + celulares);
Registros Técnicos (CREA-SP empresa 2535551; RT Paulo Rogério das Neves Eng.
Mecânico CREA 0682576030, Certidão CI 3381050/2024). Conteúdo hardcoded
(editável, `noupdate`) — campos PIX/responsáveis/CREA não existem em
`res.company`, não vale custom fields para single-tenant.

### C4 — Template seed Venda + Calibração (seed XML)

No mesmo arquivo: `afr.proposal.template` `proposal_template_venda_calib`
(name "Proposta Venda + Calibração", code "TPL-VENDA-CALIB") +
`afr.proposal.template.line` na ordem:

1. static → SEC-VC-OBJETIVO
2. static → SEC-VC-METODOLOGIA
3. static → SEC-VC-ESCOPO
4. static → SEC-VC-PROCEDIMENTO
5. **sales_items** (tabela de itens)
6. static → SEC-VC-CONDICOES
7. static → SEC-VC-DOCUMENTACAO
8. static → SEC-VC-PAGAMENTO
9. static → SEC-VC-VALIDADE
10. static → SEC-VC-OBSERVACOES
11. static → SEC-DADOS-CADASTRAIS
12. acceptance → SEC-ACEITE

(O `sales_items` já mostra o total; não inclui bloco `financial` separado para
evitar duplicação.)

### C5 — Dados Cadastrais padrão no template QI/QO/QD existente

O template `proposal_template_labquali` é criado pelo `post_init_hook`
(`hooks._install_proposal_template_seed`), que **só roda no install**. Para que
o bloco Dados Cadastrais apareça tanto em fresh-install quanto na labquali (já
instalada, atualizada via `-u`), usar helper idempotente partilhado.

**`hooks.py`:** nova fn `_ensure_company_data_block(env)`:
- localiza `afr.proposal.section` SEC-DADOS-CADASTRAIS (via `env.ref`);
- localiza template `proposal_template_labquali`;
- se o template existe e **não** tem linha com essa seção, acrescenta uma
  `afr.proposal.template.line` (block_kind static, section SEC-DADOS-CADASTRAIS)
  com `sequence` logo antes da linha de `acceptance` (ou no fim).
- Idempotente: não duplica se a linha já existe.

Chamada de:
- `_install_proposal_template_seed` (fresh install) — após criar o template.
- **`migrations/16.0.5.7.0/post-migrate.py`** (`-u`): `Environment(cr, SUPERUSER_ID)`
  → `_ensure_company_data_block(env)`. Roda após o load dos dados novos
  (seção SEC-DADOS-CADASTRAIS já existe). Fresh-install não roda migration;
  `-u` não roda hook → mutuamente exclusivos, sem dupla criação.

### C6 — Manifest

`__manifest__.py`:
- `version` → `16.0.5.7.0`.
- adicionar `"data/proposal_venda_calibracao_seed.xml"` na lista `data`
  (após `proposal_template.xml`/seções, antes das views).

## Fluxo de uso (comercial)

1. Cria `sale.order`, adiciona produtos ("Venda + Calibração de Termômetro"
   etc.) com qtd/preço nas linhas.
2. Seleciona `proposal_template_id` = "Proposta Venda + Calibração".
3. "Carregar Blocos" copia os slots → `proposal_block_ids` (edita texto/ordem).
4. Gera o PDF (relatório de cotação existente). O bloco `sales_items` puxa as
   linhas; Dados Cadastrais aparece no fim.

## Testes (`tests/test_proposal_venda_calibracao.py`)

1. **`test_sales_items_renders_lines`** — SO com 2 produtos comuns + template
   venda+calib; render contém nome do produto, qtd, preço unitário e total por
   linha + total geral.
2. **`test_template_seed_structure`** — template TPL-VENDA-CALIB existe, tem
   bloco `sales_items` e linha SEC-DADOS-CADASTRAIS, na ordem esperada.
3. **`test_sales_items_excludes_sections_and_optionals`** — linhas
   `display_type` (section/note) e `is_proposal_optional` não entram na tabela.
4. **`test_render_contains_institucional`** — render contém "NBR 16328",
   frete/"SEDEX", "60 dias", e dados cadastrais ("CNPJ", "52.230.210/0001-70").
5. **`test_ensure_company_data_block_idempotent`** — chamar
   `_ensure_company_data_block` 2× no template labquali adiciona no máx. 1 linha
   SEC-DADOS-CADASTRAIS.

Validação fresh-install: criar db limpo, `-i afr_qualificacao`, conferir que
ambos templates contêm o bloco Dados Cadastrais e o template venda+calib existe.

## Riscos / notas

- **Sanitização HTML**: corpos de seção passam por `sanitize=True`; usar HTML
  simples (p/ul/strong/table). Sem `<script>`/atributos perigosos.
- **`sales_items` total vs impostos**: doc diz "impostos inclusos"; mostrar
  untaxed + tax + total cobre ambos os casos. Preço/imposto configurados no SO.
- **Migration só dispara em `-u` a partir de versão anterior**: deploy na
  labquali precisa `-u afr_qualificacao` (já é o procedimento).
- Conteúdo dos textos institucionais é lift direto do doc 4 / ref §; ajustes
  finos de redação ficam editáveis pós-seed (noupdate).
