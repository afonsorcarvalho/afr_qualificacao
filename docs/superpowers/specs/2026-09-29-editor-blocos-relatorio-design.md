# Editor de blocos do Relatório Final — design

Data: 2026-09-29 · Módulo: `afr_qualificacao` · Branch: `feat/relatorio-final`
Status: aprovado pelo user (abordagem C, piloto no Relatório Final).

## Problema

O form do bloco (`afr.relatorio.block`, `views/relatorio_texto_views.xml`)
usa o campo html padrão com `codeview` e uma legenda crua
("aceita {{ expressões }}: relatorio, os, … criterio['tolerancia'], anexo('code')").
Leigo precisa decorar sintaxe (`{{ criterio['f0_fator'] }}`), não vê o valor
real, erra digitação que só aparece na varredura/PDF, e não tem blocos
prontos (tabelas, destaques) — monta tudo à mão.

## Objetivo

Editar um bloco deve parecer um construtor de site: inserir blocos prontos
(tabelas, listas, destaques, layout, figura) e só trocar o texto; inserir
variáveis por nome amigável; conferir o resultado com dados reais.
**A saída continua sendo HTML** renderizado pelo motor atual — PDF inalterado.

## Escopo

Dentro (fase A, piloto):
- Form do bloco do Relatório Final reorganizado + widget `rq_block_html`.
- Biblioteca de blocos prontos (`afr.relatorio.snippet`) editável pelo Gestor, com seed.
- Inserção de variável por catálogo com valor atual.
- Modo Editar | Visualizar (preview com dados reais).
- Imagem: upload, largura e crop pela toolbar nativa do web_editor.

Fora (depois):
- Fase B: painel lateral de blocos arrastáveis (estilo website/mass_mailing),
  reusando a mesma biblioteca.
- Proposta, seção de proposta, cotação e templates `RQT-*`.

## Decisões fixadas

1. **Formato da variável salvo:** `<span class="rq-var">{{ EXPR }}</span>`.
   Motivo: `body` é `fields.Html(sanitize=True)`; o sanitizer (`odoo/tools/mail.py`
   `safe_attrs`) remove `data-*` arbitrário e `contenteditable`, mas mantém `class`.
   O widget, ao montar, marca cada `span.rq-var` como `contenteditable=false`
   e mostra o label do catálogo **só no DOM do editor**; ao salvar, grava de
   volta apenas `class` + texto `{{ EXPR }}`.
2. **Retrocompatibilidade sem migração:** ao carregar, `{{ … }}` solto no texto
   (blocos antigos) é embrulhado em `span.rq-var` pelo widget. Nada muda no banco
   até o usuário salvar.
3. **Render inalterado:** `_render_block_body` (`inline_template`) resolve o
   `{{ }}` dentro do span. CSS do relatório PDF neutraliza `.rq-var`
   (sem cor/borda). Saída de texto idêntica à atual.
4. **Biblioteca = modelo**, não arquivos: Gestor cria blocos sem deploy.
   Seed `noupdate="1"`. Miniatura = o próprio HTML reduzido via CSS (sem imagem).
5. **Sem lib de editor nova.** Estende o `HtmlField` do `web_editor` 16;
   comandos `/` via `wysiwygOptions.powerboxCommands` (suportado em
   `web_editor/static/src/js/backend/html_field.js` e `wysiwyg.js`).
6. **Preview** reusa o motor de render; não amplia o risco do `sudo()` já
   registrado no TODO 1.11 de `_render_block_body` (mesmo grupo que edita o bloco).

## Experiência (UX)

**Modal do bloco** — tamanho extra-grande:
- Cabeçalho compacto: Título, Tipo; chaves Incluir / Nova página / Numerado /
  Titulado em uma linha; Bloco Pai e Seção de Origem em "Mais opções" (grupo recolhível).
- Remove a legenda crua de expressões.
- **Barra fixa** acima do texto: `+ Inserir bloco` · `{x} Variável` ·
  chave `Editar | Visualizar`. (Imagem já é comando nativo `/image`; a barra
  também oferece `Imagem` como atalho.)
- Área de edição com largura/fonte próximas da página A4 do PDF.

**Inserir bloco** (botão ou `/bloco`): diálogo galeria com abas por categoria
(Tabelas técnicas, Listas e texto, Destaques, Layout); card = nome + miniatura
HTML reduzida. Clique insere no cursor (ou no fim, se sem cursor).

**Variável** (botão ou `/variavel`): diálogo com busca, lista agrupada
("Relatório", "Critérios", "Cliente/Equipamento", "Anexos"), cada item com
label amigável e **valor atual** (ex.: "Tolerância acima → 3"). Anexos: uma
entrada por anexo do relatório ("Nº do anexo — Certificados → 4").
Clique insere a etiqueta. Hover na etiqueta mostra expressão + valor.

**Visualizar:** substitui a área de edição por um painel read-only com o HTML
renderizado com os dados do relatório; variáveis sem valor/inválidas ficam
destacadas em vermelho com o nome. Voltar para Editar preserva o conteúdo.

**Gestor:** menu Configuração → *Blocos prontos*: lista (nome, categoria,
sequência, ativo) e form com o mesmo editor (sem catálogo de valores; variável
insere a expressão com label).

## Componentes

### Backend
- `models/relatorio_snippet.py` — `afr.relatorio.snippet`:
  `name` (Char, req), `category` (Selection: `tabela`, `lista`, `destaque`,
  `layout`; req), `sequence` (Integer), `body` (Html, sanitize=True),
  `active` (Boolean). Ordem `category, sequence, id`.
  Método `rq_snippet_list()` (api.model) → `[{id, name, category, body}]` ativos.
- `models/relatorio_texto.py` (em `afr.qualificacao.relatorio`):
  - `rq_variable_catalog()` → `[{expr, label, group, value}]`. Fonte única dos
    labels. Entradas fixas: campos úteis de relatorio/os/partner/equipment/company
    + 4 chaves de `criterio`; dinâmicas: `anexo('CODE')` por `anexo_ids`.
    `value` é o valor renderizado (string, `''` quando vazio).
  - `rq_preview_block(body)` → `{html, missing: [expr…]}`. Renderiza HTML
    não salvo pelo mesmo caminho de `_render_block_body` (refatorar o núcleo
    para aceitar string); `missing` = variáveis do catálogo presentes no corpo
    com valor vazio + expressões que falharam. Nunca levanta exceção por
    expressão inválida (devolve corpo cru + a expressão em `missing`).
  - Método de classe sem catálogo de valores para o form do snippet:
    `rq_variable_catalog_static()` (api.model) → mesmas entradas fixas, `value=''`.
- `data/relatorio_snippet_seed.xml` (`noupdate="1"`), ~10 blocos:
  Tabelas (critérios de aceitação; instrumentos/sensores; resultados por ciclo),
  Listas e texto (lista de verificação; parágrafo com variáveis; definições),
  Destaques (nota/aviso; conclusão aprovada/reprovada; citação de norma),
  Layout (duas colunas; figura com legenda; quebra de página).
  Tabelas usam só HTML/estilo inline compatível com wkhtmltopdf (sem flex/grid;
  duas colunas via `<table>`). Nenhum dado real de cliente.
- `security/ir.model.access.csv`: snippet — technician/user leitura,
  manager CRUD.
- `views/relatorio_snippet_views.xml`: tree + form + action + menu em
  `menu_afr_qualificacao_config` (grupo manager).

### Frontend (`static/src/fields/rq_block_html/`)
- `rq_block_html_field.js` — estende `HtmlField` (`@web_editor/js/backend/html_field`),
  registrado como `rq_block_html`. Responsabilidades:
  - `wysiwygOptions` com `powerboxCommands` `/bloco` e `/variavel`.
  - Ao montar/após inserção: normaliza `{{ }}` solto → `span.rq-var`; decora
    `span.rq-var` (contenteditable=false, `title`, label do catálogo).
  - Antes de commit do valor: remove decoração (label/atributos), deixa
    `<span class="rq-var">{{ EXPR }}</span>`.
  - Barra fixa (template OWL) e estado `mode: 'edit'|'preview'`.
  - Catálogo: `rq_variable_catalog` do relatório (`record.data.relatorio_id`)
    quando o modelo é o bloco; `rq_variable_catalog_static` no snippet
    (opção do widget `catalog="static"`).
- `rq_snippet_dialog.js` — diálogo galeria (OWL `Dialog`).
- `rq_variable_dialog.js` — diálogo de variáveis com busca.
- `rq_block_html.xml`, `rq_block_html.scss` — templates e estilos
  (etiqueta, página A4, miniaturas, preview com `.rq-missing` vermelho).
- Lógica pura (normalizar/decorar/limpar HTML) num módulo JS separado
  `rq_var_dom.js`, testável isolado.
- Manifest: incluir `static/src/fields/rq_block_html/*` em `web.assets_backend`.

### Report
- CSS no template do corpo (`reports/relatorio_corpo_templates.xml`):
  `.rq-var { all: unset; }` equivalente compatível com wkhtmltopdf
  (sem cor, borda, padding).

### Form do bloco
- `views/relatorio_texto_views.xml` `view_relatorio_block_form`: layout novo,
  `body` com `widget="rq_block_html"`; `action_edit_block` abre o dialog em
  tamanho extra-grande (`context`/`target` conforme padrão Odoo 16:
  `'dialog_size': 'extra-large'`).

## Riscos e verificações

1. **Imagem no PDF:** imagem enviada vira anexo `/web/image/<id>`; wkhtmltopdf
   pode não conseguir baixar anexo privado. Verificar gerando a minuta com
   figura. Se sair em branco: no render do bloco, trocar `src` de
   `/web/image/<id>` por data-URI base64 do anexo (teste cobre).
2. **Etiqueta x cursor:** editor pode partir o span ao apagar/colar ao redor.
   Teste manual via agent-browser: backspace depois da etiqueta remove a
   etiqueta inteira; colar texto não duplica spans.
3. **Upgrade para Odoo 17** muda o editor: widget isolado em uma pasta; o HTML
   salvo continua válido sem o widget (`{{ }}` visível).
4. **Performance do preview:** RPC por clique em Visualizar (não por tecla).

## Testes

Python (`tests/test_relatorio_editor.py`):
- catálogo: contém chaves de critério com valor formatado; uma entrada
  `anexo('X')` por anexo; `value=''` quando campo vazio.
- `rq_preview_block`: valor resolvido; variável vazia vai para `missing`;
  expressão inválida não levanta e vai para `missing`.
- render de `<span class="rq-var">{{ criterio['tolerancia'] }}</span>` via
  `_render_block_body` produz o valor dentro do span (texto igual ao formato
  antigo).
- sanitizer: salvar `body` com `span.rq-var` preserva `class="rq-var"` e o `{{ }}`.
- snippet: seed carrega ≥10 ativos; `rq_snippet_list` filtra inativos;
  ACL — user não escreve, manager escreve.
- imagem: render com `<img src="/web/image/<id>">` gera PDF com imagem
  (ou data-URI se fallback for aplicado).

JS: lógica pura de `rq_var_dom.js` coberta por QUnit (normalizar, decorar,
limpar idempotente) se a infraestrutura de testes JS do módulo permitir;
senão validação via agent-browser.

UI (agent-browser, db `qualificacao-dev` :8084): abrir bloco, inserir bloco
pronto, inserir variável, alternar Visualizar, imagem + crop, salvar, reabrir
(etiquetas voltam), gerar minuta PDF e conferir valores e imagem.

Manifest: bump `16.0.8.7.0` → `16.0.8.8.0`.
