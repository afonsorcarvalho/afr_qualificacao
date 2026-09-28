# Relatório Final — layout do PDF no estilo do manual AFR-ETO (cores LabQuali)

Data: 2026-09-28 · Módulo: `afr_qualificacao` (branch `feat/relatorio-final`) · Versão alvo: 16.0.8.5.0

## Objetivo

O PDF do Relatório Final (corpo QWeb + carimbo) passa a seguir o estilo visual do
manual `MANUAL SOFTWARE AFR-ETO-1.3.pdf` (referência renderizada em
`.superpowers/handoff-2026-09-28/man-0*.png` e `big-08.png`), com as cores da logo
LabQuali. Nenhuma mudança de conteúdo, fluxo, numeração do índice ou pipeline de
montagem além do necessário para o cabeçalho saber a seção de cada página.

## Decisões (aprovadas pelo usuário)

- Paginação: **"Página X de Y"** global (não por seção).
- Cabeçalho das páginas internas mostra a **seção atual** à direita.
- **Capa limpa**: sem cabeçalho/rodapé do carimbo; faixa colorida no topo + linha
  de propriedade no pé. Marca d'água da minuta continua na capa.
- Fonte **Helvetica/Arial** (Inter só existe em .woff2 — wkhtmltopdf 0.12 e
  reportlab não leem).
- Fora do escopo: registro de revisões, lista de páginas efetivas, fonte Inter,
  paginação por seção.

## Paleta

| Token | Cor | Uso |
|---|---|---|
| navy | `#0A3D62` | faixa da capa, títulos, filetes de cabeçalho/tabela, texto de seção |
| orange | `#F86A30` | número de seção nível 1, filete sob título da capa/seção, barra de caixas |
| slate | `#5A7184` | subtítulos, legendas, rótulos da tabela de identificação, rodapé |
| light | `#EEF2F5` | fundo de caixas |
| texto | `#212529` | corpo |

## 1. Corpo QWeb (`reports/relatorio_corpo_templates.xml`)

Só CSS e marcação. **Invariantes**: `.rq-mark` continua `position:absolute`,
branco, 1pt, 1º filho do container que quebra página; `rq-page-break`,
`rq-anexo-sep`, `rq-toc-page` e `data-rq-*` mantidos; paperformat inalterado
(35/25/20/20 mm). wkhtmltopdf 0.12: sem flex/grid — usar tabelas e floats.

- **Título nível 1** (bloco sem `parent_id`): número com 2 dígitos (`4` → `04`)
  grande em laranja, título em CAIXA ALTA navy, filete fino slate abaixo.
  **Nível 2**: `4.1  Título` em negrito navy, sem caixa alta. O zero à esquerda
  vale só para o número inteiro de nível 1 (`4.1` fica `4.1`); o sumário usa a
  mesma formatação.
- **Tabelas** (`.rq-table`): sem grade vertical; cabeçalho em negrito navy com
  filete navy de 1px embaixo; linhas separadas por filete fino `#C9D3DC`;
  tabelas "chave/valor" (th na 1ª coluna) com rótulo em slate caixa alta
  pequena, como a tabela de identificação da capa do manual.
- **Sumário**: título "SUMÁRIO" no estilo nível 1 (sem número); linhas com
  pontilhado; entradas nível 1 em negrito, filhas recuadas; anexos iguais a
  nível 1.
- **Caixas**: dentro de `.rq-body`, `blockquote` vira caixa com barra lateral
  laranja 3px e fundo `light`; classes `.rq-box-warn` (barra `#C0392B`, fundo
  `#FBECEC`, rótulo opcional `.rq-box-label` vermelho) e `.rq-box-info` (barra
  navy, fundo light) disponíveis para quem editar o corpo dos blocos.
- **Separador de anexo**: "ANEXO" em slate caixa alta pequena, número grande em
  laranja, título navy caixa alta, filete laranja curto; o texto
  `Anexo N: Título` pode mudar de forma, mas o marcador e a quebra de página não.
- **Capa** (`rq_block_capa`): logo da empresa grande (≈ 60 mm de largura) à
  esquerda, "RELATÓRIO DE QUALIFICAÇÃO TÉRMICA" em CAIXA ALTA navy grande,
  filete laranja de largura total abaixo, subtítulo slate
  (`<equipamento> — <cliente>`), e tabela de identificação com filetes finos:
  Código (`doc.name`), Revisão, Data de emissão (data da emissão vigente ou
  "MINUTA"), Equipamento, Nº de série / TAG, Cliente, Emitente (empresa),
  Período dos ensaios. A faixa superior e a linha de propriedade da capa são
  desenhadas pelo carimbo (a margem de 35 mm impede o QWeb de desenhar no topo).
- **Documentos internos** (protocolo, laudo micro): cabeçalho `rq-doc-header`
  no mesmo estilo de título de capa em menor escala; subtítulos numerados
  `1. …` no estilo nível 2.

## 2. Carimbo (`models/relatorio_pdf.py`)

`_overlay_page` ganha dois modos:

- **Capa** (`page_index == header["cover_page_index"]`): faixa navy de ponta a
  ponta com ~12 mm no topo, filete laranja de 1 mm sob ela, linha de
  propriedade no pé (6–7 pt, slate). Sem logo, título, número de página nem QR.
  Marca d'água se `watermark`.
- **Interna**: logo pequena à esquerda (altura ≈ 12 mm); à direita da logo,
  "RELATÓRIO DE QUALIFICAÇÃO TÉRMICA" (Helvetica-Bold 8 pt navy) e subtítulo
  (7 pt slate) `<código> · <equipamento> · TAG: <tag>`; na borda direita a
  seção atual (número em laranja bold + nome em navy bold, 8 pt, truncado a
  ~45 caracteres); filete navy 0.8 pt sob o cabeçalho. Rodapé: filete fino
  slate; esquerda código do documento, centro `Rev.00 · <data>` (ou
  `Rev.00 · MINUTA`), direita **"Página X de Y"** bold navy; abaixo, linha de
  propriedade 6 pt slate. QR (página de assinaturas) continua no canto inferior
  direito; quando presente, "Página X de Y" desloca para a esquerda do QR como
  hoje.
- Linha de propriedade: `"Documento emitido por <empresa> · <e-mail>. Este
  relatório só pode ser reproduzido integralmente, sem alterações."` (e-mail
  omitido se vazio).

Todo o desenho fica dentro de margem superior 35 mm / inferior 25 mm, exceto a
faixa da capa (topo absoluto da página, onde o corpo da capa não desenha).

### Seção por página

Função pura nova `section_labels(markers, layout, sections, total)`:

- `sections`: lista ordenada `[(marker_key, label)]` com os blocos de nível 1
  titulados do corpo (exceto `capa`) e os anexos incluídos; `label` do bloco =
  `"<NN> <TÍTULO EM CAIXA ALTA>"` (índice: `"SUMÁRIO"`), do anexo =
  `"ANEXO <n>"`.
- Retorna lista com `total` strings (1 por página final, 0-based): cada página
  recebe o label da última seção cuja página inicial (via `layout["page_map"]`)
  é ≤ à página; páginas de anexo intercaladas recebem o label do anexo (a página
  inicial do anexo já está em `page_map`). Páginas antes da 1ª seção: `""`.
- `cover_page_index`: índice final (0-based) da página do marcador do bloco
  `capa` se ele for o 1º bloco do corpo e seu marcador existir; senão `None`.

`_stage_body` calcula ambos e guarda em `st` (`section_labels`,
`cover_page_index`; JSON serializável). `_stage_stamp` passa-os em `header`.
`_overlay_page` recebe o label de sua página (`header["section_labels"][idx]`
quando existir, senão `""`). `stamp_pdf` continua funcionando sem essas chaves
(compatível com os testes atuais).

`_header` acrescenta `company_name`, `code` (`relatorio.name`) e
`subtitle`; mantém as chaves atuais (`title`, `equipment`, `revision`, `date`,
`footer`, `verify_url`, `qr_page_index`). Os textos "TAG: <tag>", o e-mail da
empresa e "Página X de Y" continuam presentes nas páginas internas (testes
existentes os procuram).

## 3. Testes e validação

- Unitários: `section_labels` (seções, anexo intercalado, anexo no fim, página
  antes da 1ª seção); `stamp_pdf` com `cover_page_index` (capa sem "Página",
  interna com label da seção); `_stage_body` popula `section_labels` com
  `len == total`.
- Suíte `afr_relatorio_final` + módulo inteiro verdes (ajustar só asserções de
  texto/markup que mudaram de forma, sem afrouxar invariantes de marcador).
- Visual: `-u afr_qualificacao` no `qualificacao-dev`, gerar minuta do relatório
  id 1, rasterizar com `pdftocairo` e comparar com `man-01.png`/`big-08.png`
  (capa, sumário, seção de texto, protocolo com tabelas, separador, página de
  gráfico, assinaturas com QR na emissão não é testável na minuta — só minuta).
- Bump `__manifest__.py` 16.0.8.4.1 → 16.0.8.5.0.
