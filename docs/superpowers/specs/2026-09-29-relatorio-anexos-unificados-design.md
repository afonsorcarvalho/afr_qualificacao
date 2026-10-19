# Relatório Final — anexos unificados (fim do bloco "Separador de Anexo")

Data: 2026-09-29 · Módulo: `afr_qualificacao` · Branch: `feat/relatorio-final`

## Problema

O Relatório Final tem duas listas que falam do mesmo assunto:

- **Aba Texto → blocos** (`afr.relatorio.block`): corpo do relatório + um bloco
  `anexo_separador` por anexo (seed `hooks.py::_rqt_separators`, seq 500+) +
  blocos de conteúdo de anexo (`c_protocolo`, `c_micro`, seq 900+).
- **Aba Anexos** (`afr.relatorio.anexo`): quem de fato decide ordem, inclusão e
  numeração dos anexos no PDF.

O vínculo separador↔anexo é só o texto `anexo_code`, resolvido no render
(`relatorio_texto.py::_anexo_separator_block`). Consequência para o usuário:

- Reordenar separadores, ou mexer em Numerado/Titulado/Nova Página, não faz
  nada; o Nº fica vazio.
- Desligar "Incluir" do separador só apaga um texto (vazio em todos os seeds);
  a página "Anexo N" continua impressa.
- Excluir um anexo deixa o separador na lista, parecendo ativo; anexo novo não
  ganha separador; renomear `code` desconecta em silêncio.
- Protocolo/micro aparecem na lista de blocos numa posição que não é a do PDF.

## Objetivo

Uma só leitura, na ordem do PDF: **corpo do relatório**, depois **anexos** na
ordem da tabela de anexos. Nada na tela que pareça controlar algo que não
controla.

## Decisões

1. **Separador deixa de ser bloco.** A página separadora é gerada só a partir
   do anexo: "Anexo N" + título. Sem texto próprio (nenhum seed nem dado de dev
   usa; se precisar no futuro, vira campo do anexo).
2. **Conteúdo de anexo "Bloco do relatório"** (protocolo, laudo micro) continua
   sendo um `afr.relatorio.block`, ligado pelo `anexo.block_id` (já existe). É
   editado a partir do anexo, não da lista do corpo.
3. **Tela:** a aba Texto passa a ter, nesta ordem, template + "Recarregar
   template", **Corpo do relatório** (blocos), **Anexos** (tabela atual). A aba
   Anexos separada é removida.
4. Sem mudança em numeração, tokens `{{ anexo('code') }}` ou tipos de origem.

## Design

### Modelo

- `REPORT_BLOCK_KINDS` (`models/relatorio_template.py`) perde
  `anexo_separador`. Remove também a constraint de template que exige
  `anexo_code` para esse kind.
- `hooks.py`: remove `_rqt_separators` e seu uso nos specs de template.
- `afr.relatorio.block`:
  - novo `anexo_ids = One2many("afr.relatorio.anexo", "block_id")`;
  - novo `is_anexo_content = Boolean(compute, store=True)`, depende de
    `anexo_ids` — verdadeiro quando algum anexo aponta para o bloco.
- `afr.qualificacao.relatorio`: novo
  `body_block_ids = One2many("afr.relatorio.block", "relatorio_id",
  domain=[("is_anexo_content", "=", False)])` — é o que a tela mostra.
  `block_ids` continua existindo (template, regras, testes).
- `anexo_code` no bloco e na linha de template continua, **só** como chave de seed:
  `_apply_template_anexos` usa para preencher `anexo.block_id`. Deixa de
  decidir impressão.
- Numeração do corpo do relatório (`_block_numbering` /
  `_compute_display_number` do bloco) passa a pular blocos por
  `is_anexo_content` (hoje: `anexo_code`), mesmo critério do `_body_blocks()`,
  para corpo impresso e numeração nunca divergirem. Na linha de template (onde
  não há anexo real) o critério continua `anexo_code`.

### Montagem do PDF

- `_body_blocks()`: filtra `included and not is_anexo_content` (hoje:
  `not anexo_code`). Um bloco com `anexo_code` mas sem anexo apontando volta a
  ser corpo normal — corrige o caso "bloco some sem motivo".
- `rq_anexo` (`reports/relatorio_corpo_templates.xml`): remove a busca e o
  render do separador-bloco; mantém página "Anexo N" + título + marcador
  `@@RQ:anexo:<code>@@` + conteúdo do `block_id` quando origem = bloco.
- `rq_block`: remove `anexo_separador` da lista de kinds sem body.
- Remove `_anexo_separator_block`.
- `relatorio_rules.py::rendered_blocks`: remove o separador; mantém corpo +
  `block_id` dos anexos "bloco" incluídos. Atualiza comentários.

### Tela

`views/relatorio_texto_views.xml`, aba Texto:

1. `template_id` + "Recarregar template" (como hoje).
2. Separador **Corpo do relatório**: tree editável de `body_block_ids` (mesmas
   colunas de hoje; `anexo_code` sai da tree).
3. Separador **Anexos**: tabela atual de `anexo_ids` + legenda do token.
4. Remove a page "Anexos".

Form do anexo: quando `slot_kind == 'bloco'`, botão **"Editar conteúdo"** que
abre `block_id` no mesmo modal do `action_edit_block` (reusa o método).

`views/relatorio_template_views.xml`: tira `anexo_separador` do que existir de
filtro/decoration; mantém `anexo_code` na linha de template.

### Dados existentes (dev)

Labquali em desenvolvimento, sem produção → sem migração de dados reais. Mas os
bancos de dev têm linhas/blocos `anexo_separador` e o seed é `post_init` (não
roda em upgrade). Script `migrations/16.0.8.6.0/pre-migrate.py`: `DELETE` em
`afr_relatorio_block` e `afr_relatorio_template_line` com
`block_kind = 'anexo_separador'`. Bump de versão para `16.0.8.6.0`.

### Casos de borda

- Anexo "bloco" sem `block_id` ou bloco vazio/excluído: alerta `PROBLEM_EMPTY`
  existente (`relatorio_anexo_files.py`) — sem mudança.
- Anexo "bloco" excluído: o bloco segue `is_anexo_content`, fica fora do corpo e
  não é impresso.
- Anexo apagado: `block_id` some → bloco volta ao corpo. Aceitável (usuário vê e
  exclui/apaga); não apagar em cascata.

## Testes

- Ajustar os que esperam `anexo_separador`: `tests/test_relatorio_template.py`,
  `tests/test_relatorio_rules.py`, `tests/test_relatorio_pdf.py`,
  `tests/relatorio_fakes.py` (`FakeCorpo.render`).
- Novos:
  - seed não cria bloco/linha `anexo_separador`;
  - `body_block_ids` exclui conteúdo de anexo; `is_anexo_content` recalcula ao
    trocar `block_id`;
  - corpo não inclui bloco de anexo; ordem dos anexos no HTML do corpo segue
    `anexo.sequence`; anexo excluído não aparece;
  - "Editar conteúdo" abre o `block_id` certo;
  - pre-migrate remove separadores legados.
- Validação de UI via agent-browser em `qualificacao-dev` (:8084): aba Texto com
  as duas seções, sem aba Anexos, "Editar conteúdo" funcionando, minuta gerada
  com anexos na ordem da tabela.

## Fora do escopo

Numeração, tokens, tipos de origem, texto customizado no separador.
