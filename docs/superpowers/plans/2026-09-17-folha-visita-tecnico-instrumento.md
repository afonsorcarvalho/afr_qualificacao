# Plano — Folha da visita: técnico atual visível e instrumentos editáveis

Data: 2026-09-17
Branch: `feat/agenda-modo-mes` (submodule `addons/afr_qualificacao`) — a mesma da
feature do modo Mês, ainda não mergeada.
Escopo: **somente frontend** em `pwa/`. Nenhuma mudança em Python.

## Contexto

Dois defeitos relatados pelo usuário ao usar a folha de edição da visita
(`pwa/app/tecnico/qualificacao/_components/VisitaSheet.tsx`):

1. **O técnico atual da visita não aparece selecionado** — o `<select>` mostra
   "—" mesmo quando a visita tem técnico. Causa: `useTecnicoOptions` chama
   `pwa_tecnico_options`, que filtra `is_tecnico=True`; o técnico da visita
   (ex. "Afonso Carvalho", id 441) não tem a flag, logo não existe `<option>`
   com esse `value` e o browser cai no "—". O usuário não consegue saber quem
   está atribuído antes de trocar, e um "Salvar" sem tocar no campo
   **reatribuiria a visita para vazio**.
2. **Não há como editar os instrumentos de qualificação na folha** — só o
   painel do modo Semana permite ligar/desligar instrumento. O backend já
   aceita: `instrument_ids` está em `_PWA_WRITABLE_FIELDS` e
   `pwa_instrumento_options` existe e é exposto por
   `listInstrumentoOptions`/`useInstrumentoOptions`.

O módulo `afr_qualificacao_agendamento` (backend) não muda.

## Global Constraints

1. **Nenhuma mudança em arquivo Python, nem bump de `__manifest__.py`.**
   (A versão do PWA vive no `package.json` e não muda aqui.)
2. **Sem dependência nova.**
3. **Nunca ler o relógio do aparelho** (regra da casa; aqui vale para qualquer
   data que venha a ser derivada: só `Date.UTC`/ISO, `Intl` com
   `timeZone:'UTC'`, e o "hoje" vem do servidor).
4. **Acessibilidade:** alvos de toque `min-h-[44px]`; todo campo com rótulo
   associado ou `aria-label`; cor nunca é o único portador de informação.
5. **Texto de UI em pt-BR**; comentários em pt-BR explicando o PORQUÊ, no
   estilo dos arquivos vizinhos.
6. **Testes:** `npm run test` (vitest) e `npx tsc --noEmit` a partir de `pwa/`.
   Testes novos em `pwa/app/tecnico/qualificacao/__tests__/`, seguindo
   `VisitaSheet.test.tsx`, que já existe. Baseline limpa (`pwa/docs/BASELINE.md`):
   qualquer falha é regressão.
7. **TDD:** teste que falha primeiro, depois a implementação.

## Task 1 — Técnico atual sempre presente na lista, e instrumentos editáveis

Um único arquivo de produção (`_components/VisitaSheet.tsx`) e um de teste.

### 1a. Técnico atual na lista de opções

O padrão já existe no projeto: `rosterTecnicos(oficiais, visitas)` em
`app/tecnico/qualificacao/agenda/carga.ts` faz exatamente essa união (roster
oficial + quem aparece nas visitas, sem duplicar por id, ordenado por nome
pt-BR). **Reutilize `rosterTecnicos`**, passando a visita em edição como
lista de uma posição só — não escreva uma segunda união.

- Em modo `editar` com `visita.tecnico_id !== false`, as opções do `<select>`
  são `rosterTecnicos(tecnicos.data ?? [], visita ? [visita] : [])`.
- O `value` do `<select>` continua `String(visita.tecnico_id)`; com a opção
  presente, o técnico atual aparece selecionado.
- O `<option value="">—</option>` continua existindo e significa "sem
  técnico" (visita com `tecnico_id === false`).
- Em modo `criar` nada muda: não há visita da qual herdar técnico.

### 1b. Campo Instrumentos (modo editar)

- Novo bloco, depois de "Técnico", visível só em `modo === 'editar'`:
  um grupo de checkboxes (um por instrumento de `useInstrumentoOptions`),
  marcados conforme `visita.instrument_ids`.
- Habilite a query com `open && modo === 'editar'` — não busque a lista ao
  abrir a folha em modo criar.
- Estado local `instrumentoIds: number[]`, inicializado de
  `visita?.instrument_ids ?? []`, alternado a cada toque.
- Cada item mostra o nome e, quando o certificado estiver vencido em relação
  à **data escolhida no próprio formulário** (o campo `data`, não o `date`
  original da visita), um aviso textual "certificado vencido" além da cor —
  a regra de vencido é a mesma de `usoPorInstrumento` em `carga.ts`:
  `!validade || validade < dia`. Marcar um instrumento vencido não é
  bloqueado no front: o servidor decide, e a mensagem dele já é exibida na
  tarja de erro que a folha tem.
- O `salvar()` em modo editar passa a mandar `instrument_ids: instrumentoIds`
  junto dos campos que já manda. **Não** mandar `instrument_ids` em modo criar
  (`pwa_visita_create` tem outra assinatura).
- Envolva a lista num `<fieldset>` com `<legend>Instrumentos</legend>` (ou
  `role="group"` + `aria-labelledby`): checkboxes soltos sem agrupamento não
  anunciam a que pertencem. Alvos de toque `min-h-[44px]`.
- Lista vazia (`pwa_instrumento_options` devolve `[]`): mostrar
  "Nenhum instrumento cadastrado." em vez de um grupo vazio.

### Testes obrigatórios (`__tests__/VisitaSheetTecnicoInstrumento.test.tsx`)

Mocke os hooks de `@/lib/hooks/useAgenda`, como `VisitaSheet.test.tsx` já faz.

- Visita com `tecnico_id: 441` / `tecnico_name: 'Afonso Carvalho'` **fora** do
  retorno de `pwa_tecnico_options` (que devolve só Bruno e Paulo): o
  `<select>` de Técnico tem valor `441` e "Afonso Carvalho" aparece entre as
  opções. Este teste tem de FALHAR com o código de hoje.
- Salvar sem tocar no campo Técnico mantém `tecnico_id: 441` no
  `pwa_visita_update` — a regressão silenciosa que o defeito causava.
- Técnico oficial não é duplicado quando o técnico da visita já está no
  roster (conta as `<option>` com aquele nome).
- Visita com `tecnico_id: false`: o `<select>` fica em "—" e salvar não
  inventa técnico.
- Instrumentos: os `instrument_ids` da visita vêm marcados; marcar e
  desmarcar altera o que vai no `pwa_visita_update` (asserção sobre o
  argumento, não só sobre "foi chamado").
- Instrumento com `validade` anterior à data escolhida no formulário mostra
  o aviso textual; mudar a data do formulário para antes da validade tira o
  aviso.
- `pwa_instrumento_options` vazio → "Nenhum instrumento cadastrado.".
- Modo criar: nenhum campo de instrumento é renderizado e
  `useInstrumentoOptions` não é habilitado.

## Task 2 — Validação no navegador (o controlador faz, não subagente)

PWA em `:3010` (registro do `devserver` diz 3012, a porta real é 3010) contra
o Odoo de `qualificacao-dev` em `:8084`. Abrir uma visita com técnico fora do
roster oficial, conferir que o nome aparece selecionado, marcar/desmarcar
instrumento e salvar, conferir a persistência depois do refetch, e conferir o
tema claro e o escuro.
