# Plano — Confirmação ao mover visita + filtro nos badges da legenda

Data: 2026-09-17
Branch: `feat/agenda-instrumentos-mes` (submodule `addons/afr_qualificacao`), a
mesma da feature de instrumentos, ainda não mergeada.
Escopo: **somente frontend** em `pwa/`. Nenhuma mudança em Python.

## Contexto

A agenda do PWA Técnico tem três modos (Lista, Semana, Mês). Nos modos Semana e
Mês, o Gestor arma uma visita com o botão "Ajustar" e toca num dia da faixa
(`_FaixaDias`) ou da grade (`_GradeMes`) para movê-la — a gravação é imediata,
sem confirmação. O modo Mês mostra ainda duas faixas de legenda ("Técnicos:" e
"Instrumentos:"), hoje meramente informativas, com uma bolinha por técnico e um
triângulo por instrumento usados nos 42 dias da grade.

O usuário pediu duas coisas:

1. **Confirmação antes de mudar a data de uma visita** pelo gesto de mover.
2. **Os chips da legenda viram badges de filtro**, clicáveis para ligar/desligar,
   com um badge "Todos" por faixa.

## Decisões já tomadas com o usuário (não reabrir)

- O filtro altera **apenas as marcas desenhadas na grade**. Os `VisitaCard` do
  dia selecionado e a seção "Instrumentos do dia" continuam completos — nenhuma
  visita some da tela por causa do filtro.
- As duas faixas se combinam por **interseção (E)**.
- Consequência aceita explicitamente: com a faixa de instrumentos restrita, uma
  visita **sem nenhum instrumento** não passa no filtro, e a bolinha do técnico
  dela some da grade.
- O filtro vive **só enquanto a tela está aberta**: recarregar ou trocar de modo
  volta a mostrar tudo. Nada de persistir em `tecnicoSettings`.
- A confirmação **não** se aplica ao campo Data da folha de edição
  (`VisitaSheet`), que já tem um "Salvar" explícito.

## Global Constraints

1. **Nenhuma mudança em arquivo Python, nem bump de `__manifest__.py`.**
2. **Nunca ler o relógio do aparelho:** só `Date.UTC`/`setUTCDate`, strings ISO
   `YYYY-MM-DD`, `Intl` sempre com `timeZone:'UTC'`. O "hoje" vem de
   `data.server_today`.
3. **Sem dependência nova.**
4. **Acessibilidade:** alvos de toque `min-h-[44px]`; **cor nunca é o único
   portador** — nos badges a cor já é a identidade do recurso, então o estado
   ligado/desligado precisa de outro portador (borda, contorno, `aria-pressed`).
5. **UI em pt-BR**; comentários em pt-BR explicando o PORQUÊ.
6. **Testes:** `npm run test` e `npx tsc --noEmit` a partir de `pwa/`. Baseline
   **416 testes verdes** — qualquer falha é regressão.
7. **TDD:** teste que falha primeiro.
8. Dev server em `:3010` a partir de `pwa/`: não derrubar, não subir outro, não
   rodar `npm run build`.

## Task 1 — Confirmação antes de mudar a data

### Comportamento

- Vale nos modos **Semana e Mês** (os dois compartilham o caminho `ajustar` em
  `agenda/page.tsx`).
- Tocar num dia com visita armada **não grava mais direto**: abre um diálogo de
  confirmação com o texto, em pt-BR:
  `Tem certeza que deseja mudar a data da visita OS26-08-0006-1 de 18/09/2026 para 01/10/2026?`
  (nome da OS = `visita.os_name`; datas formatadas `dd/MM/yyyy` via `Intl` com
  `timeZone:'UTC'` — nunca `toLocaleDateString()` sem fuso).
- **Confirmar** chama o `ajustar({ date })` que já existe, com todo o
  comportamento atual (avanço da âncora do mês quando o destino está fora do mês
  visível, `setDiaSel`, tarja de erro do servidor).
- **Cancelar** fecha o diálogo, **não grava**, e mantém a visita armada — o
  Gestor precisa poder escolher outro dia sem recomeçar.
- Tocar no **mesmo dia** em que a visita já está não abre diálogo nenhum (não há
  o que confirmar). Decida entre não fazer nada ou apenas selecionar o dia, e
  deixe o motivo num comentário.
- Os outros ajustes por toque (técnico e instrumento, no painel do modo Semana)
  **continuam sem confirmação** — o pedido do usuário é sobre data.

### Implementação

- Componente novo `agenda/_ConfirmarMudancaData.tsx`, usando o `BottomSheet` de
  `@/components/ui/BottomSheet` (o mesmo que a `VisitaSheet` usa). Sem estado
  próprio além do necessário para renderizar; quem decide o que fazer é a
  `page.tsx`.
- Em `page.tsx`, um estado `dataPendente: string | null` (o ISO do destino).
  O `onSelecionar` da grade/faixa passa a armar esse estado em vez de chamar
  `ajustar` direto.
- A rede de segurança que já existe (o `useEffect` que encerra o ajuste quando a
  visita some do payload ou perde `editable`) precisa **também fechar o diálogo
  pendente** — senão sobra um diálogo perguntando sobre uma visita que não
  aceita mais gravação.

### Testes (`__tests__/ModoMes.test.tsx` e `__tests__/ModoSemana.test.tsx`)

- Modo Mês: armar visita + tocar em outro dia **não** chama `pwa_visita_update`;
  o diálogo aparece com as duas datas no texto; Confirmar chama o update com o
  `date` do destino; Cancelar não chama e a visita continua armada.
- Modo Semana: mesmo fluxo pela `_FaixaDias`.
- Tocar no mesmo dia da visita não abre diálogo.
- Ajuste de técnico/instrumento no painel da Semana continua gravando direto,
  sem diálogo (guarda de escopo).
- A visita armada sumindo do payload fecha o diálogo pendente.

## Task 2 — Badges de filtro nas duas faixas

### Comportamento

- Cada chip das faixas "Técnicos:" e "Instrumentos:" vira um botão
  (`aria-pressed`), alvo `min-h-[44px]`. O chip "Sem técnico", quando existir,
  participa do filtro como os demais.
- Cada faixa ganha um badge **"Todos"**, à frente dos demais, ativo quando não
  há restrição naquela faixa; tocá-lo limpa a restrição da faixa.
- Estado em `page.tsx`, **em memória apenas**: `tecnicosSel: Set<number|false> |
  null` e `instrumentosSel: Set<number> | null`, onde `null` = "Todos".
  Trocar de modo ou recarregar zera.
- **As faixas continuam listando todos os recursos da janela**, ligados ou
  desligados — senão não haveria como religar o que foi desligado.

### Regra do filtro (duas camadas)

1. Uma visita contribui com marcas se
   (`tecnicosSel === null` **ou** `tecnicosSel` contém `visita.tecnico_id`)
   **e**
   (`instrumentosSel === null` **ou** `visita.instrument_ids` intersecta
   `instrumentosSel`).
   Note a consequência já aceita pelo usuário: com `instrumentosSel` restrito,
   visita sem instrumento nenhum **não** passa.
2. Das visitas que passaram, só são desenhadas as marcas dos recursos ligados.

O filtro alimenta **apenas** `tecnicosPorDia` e `instrumentosPorDia` (as marcas
da grade). `doDiaMes` (os `VisitaCard`) e `instrumentosDoDiaSel` (a seção
"Instrumentos do dia") continuam usando a lista completa de visitas.

### Implementação

- `_VistaMes.tsx`: a `FaixaLegenda` local passa a receber o conjunto
  selecionado, um `onAlternar(id)` e um `onTodos()`, e renderiza o badge
  "Todos". Estado desligado indicado por borda/contorno e opacidade do FUNDO
  (nunca opacidade sobre token de texto — `temaTokens.test.ts` proíbe), além de
  `aria-pressed={false}`.
- `page.tsx`: `visitasVisiveis` derivado com `useMemo` (as dependências têm de
  incluir os dois conjuntos), passado só para as duas agregações de marcas.
- Cuidado com os `useMemo` que já existem (`pontosDia`,
  `pontosInstrumentoDia`, `legendaInstrumentos`, `instrumentosDoDiaSel`): as
  listas de dependência precisam continuar completas.

### Testes (`__tests__/ModoMes.test.tsx`)

- Desligar um técnico tira a bolinha dele das células **e** o `aria-label` da
  célula deixa de citá-lo.
- Desligar um técnico **não** tira o `VisitaCard` dele do dia selecionado nem a
  seção "Instrumentos do dia" (o alcance combinado com o usuário).
- Interseção: com um instrumento selecionado, a visita de outro técnico que não
  usa aquele instrumento perde as marcas.
- A consequência aceita: com a faixa de instrumentos restrita, a visita sem
  instrumento nenhum perde a bolinha do técnico.
- "Todos" restaura a faixa; o badge "Todos" reflete `aria-pressed` corretamente.
- Os badges desligados continuam na faixa (dá para religar).
- Trocar de modo e voltar zera o filtro.
- O estado ligado/desligado é legível sem cor (`aria-pressed`).

## Task 3 — Validação no navegador (o controlador faz, não subagente)

PWA em `:3010` contra o Odoo de `qualificacao-dev` em `:8084`: mover visita com
confirmação (confirmar e cancelar), filtro nas duas faixas, "Todos", tema claro
e escuro, viewport de 390px.
