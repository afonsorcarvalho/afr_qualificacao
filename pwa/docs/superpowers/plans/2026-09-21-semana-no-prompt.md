# Plano — "semana que vem" no chat: convenção explícita e datas prontas

## Contexto

O chat de agendamento resolve "semana que vem" sorteando um intervalo de sete
dias. Medido com o harness de validação em 2026-09-21, com `server_today` =
2026-09-21 e a mesma pergunta repetida:

| execução | janela pedida | veredito |
|---|---|---|
| 1 | `2026-09-28` → `2026-10-04` | segunda a domingo |
| 2 | `2026-09-22` → `2026-09-28` | terça a segunda |
| 3 | `2026-09-27` → `2026-10-03` | domingo a sábado |

Três respostas diferentes, mesma pergunta, mesmo prompt, mesmo modelo. Com
`server_today` = 2026-09-14 saiu certo nas duas execuções. **Não é uma
convenção errada e estável — é ausência de convenção.**

Duas coisas que o TODO original afirmava e que são falsas, conferidas no
código:

1. Não existe convenção de semana no produto. `pwa_agenda_fetch`
   (`addons/afr_qualificacao_agendamento/models/os_visita.py:620`) monta a
   janela padrão como `today` a `today + 13`, sem alinhar a dia da semana. O
   cabeçalho "seg., 21 de set. – dom., 04 de out." que motivou o relato saiu
   assim porque o dia era uma segunda-feira.
2. Não há constante de início de semana em `mes.ts`/`carga.ts`/`janela.ts`
   para o prompt citar. `deslocarJanela` só soma dias.

**Decisão do parceiro humano (2026-09-21): a semana do produto vai de segunda
a domingo.** É o costume brasileiro e o do ISO-8601.

**Decisão de desenho:** não basta escrever a convenção em prosa no prompt.
Uma frase ainda deixa o modelo fazendo aritmética de calendário, que é
exatamente onde ele sorteia. O prompt passa a receber os intervalos **já
calculados** — o modelo lê datas, não as deriva.

Spec de origem: `docs/superpowers/specs/2026-09-20-chat-agendamento-design.md`
(seção "Validação empírica antes de fechar o modelo").
Evidência: `docs/VALIDACAO-CHAT.md`, fixture F04.

## Global Constraints

- **Mudança só de front: NÃO bumpar `__manifest__.py`.** A versão do PWA vive
  no `package.json`.
- Aritmética de data **sempre** via `Date.UTC`, nunca pelo relógio local — é a
  regra que `deslocarJanela` (`app/tecnico/qualificacao/agenda/janela.ts`) já
  segue, e a razão é registrada lá: o fuso do aparelho não pode mudar o dia.
  Este app já foi mordido por relógio de aparelho.
- A semana começa na **segunda** e termina no **domingo**. Esse número mora em
  UM lugar, exportado; nenhum outro arquivo repete `1` ou `7`.
- `npx tsc --noEmit` limpo. Exceção pré-existente e fora de escopo:
  `.next/types/app/api/chat/route.ts` reclama dos helpers exportados por
  `app/api/chat/route.ts`.
- Não rodar `npm run build` (dev server de pé em :3010 usa o mesmo `.next/`).
- Baseline de testes: `docs/BASELINE.md`.

## Task 1 — helper puro de semana

**Arquivo novo:** `lib/chat/semana.ts`, com teste `lib/chat/semana.test.ts`.

Funções puras sobre data ISO (`AAAA-MM-DD`), sem React e sem relógio local:

- uma constante exportada para o dia de início da semana, com comentário
  dizendo que é decisão de produto (segunda) e não um detalhe técnico;
- `semanaDe(iso)` → `{ from, to }`, a semana segunda-a-domingo que **contém**
  `iso`;
- `deslocarSemanas(iso, n)` → a mesma estrutura, `n` semanas adiante ou atrás.

TDD, e os casos que precisam existir porque são onde este tipo de código erra:

- `iso` numa segunda → `from === iso`;
- `iso` num domingo → `from` é a segunda **anterior**, seis dias antes (o caso
  que a maioria das implementações ingênuas erra);
- `iso` no meio da semana;
- virada de mês (`2026-09-28` … `2026-10-04`);
- virada de ano;
- **29 de fevereiro** de um ano bissexto;
- `deslocarSemanas(iso, 1)` a partir de 2026-09-21 → `2026-09-28` a
  `2026-10-04`, que é exatamente o caso do defeito;
- `deslocarSemanas(iso, -1)`.

Não escrever teste que só repita a implementação: cada caso acima existe por um
motivo nomeado acima, e o nome do teste deve dizer qual.

## Task 2 — o prompt recebe as semanas prontas

**Arquivos:** `lib/chat/prompt.ts` e `lib/chat/prompt.test.ts`.

`buildSystemPrompt` já recebe `ctx.serverToday`. Derivar dali, com o helper da
Task 1, um bloco novo no system prompt, logo depois do bloco `DATA DE HOJE`
(que fica como está — ele é a âncora):

```
SEMANA: a semana vai de segunda a domingo.
- ESTA SEMANA: <from> a <to>
- SEMANA QUE VEM: <from> a <to>
- SEMANA PASSADA: <from> a <to>
Use estes intervalos exatos quando o gestor disser "esta semana", "semana que
vem" ou "semana passada". Para qualquer outra semana, conte de segunda a
domingo a partir destes — nunca de outro dia.
```

O texto exato pode ser ajustado; o que é obrigatório: os três intervalos
calculados, a frase que manda usá-los literalmente, e a regra de contagem para
as demais semanas.

Nada muda em `PromptContext` — as três semanas saem de `serverToday`, que já
está lá. **Não** acrescentar campo novo à interface: derivar é mais difícil de
usar errado do que receber pronto de três chamadores diferentes.

Testes em `prompt.test.ts`:

- com `serverToday: '2026-09-21'`, o prompt contém `2026-09-28` e `2026-10-04`
  (a semana que vem), e contém `2026-09-21`/`2026-09-27` (esta semana);
- com `serverToday` num domingo (`2026-09-27`), "esta semana" ainda é
  `2026-09-21` a `2026-09-27` — o domingo pertence à semana que começou na
  segunda anterior. É o caso que denuncia início-de-semana errado;
- o bloco `DATA DE HOJE` continua presente e inalterado.

## Task 3 — gate de regressão contra o modelo de verdade

O defeito é probabilístico: uma execução verde tinha ~1/3 de chance de passar
mesmo com o bug intacto. O gate precisa repetir.

Rodar cinco vezes a fixture F04 do harness com `SERVER_TODAY=2026-09-21` e
exigir `2026-09-28` a `2026-10-04` nas **cinco**:

```bash
agent-browser cookies get > "$SCRATCH/cookies.txt"
for i in 1 2 3 4 5; do
  COOKIE_FILE="$SCRATCH/cookies.txt" SERVER_TODAY=2026-09-21 \
    JANELA_FROM=2026-09-21 JANELA_TO=2026-09-27 FIXTURE_FILTER=F04 \
    RELATORIO="$SCRATCH/f04-$i.md" \
    npx vitest run --config vitest.live.config.ts 2>&1 | grep ^F04
done
```

Isto **não** entra na suíte (`npm test` não pode gastar cota nem depender de
rede) — é verificação manual desta mudança, e o resultado das cinco execuções
vai no relatório da task, colado, não resumido.

Se qualquer execução divergir, a mudança não está pronta: o caminho seguinte é
endurecer o texto do bloco (ordem, ênfase, exemplo negativo), não afrouxar o
gate.

## Task 4 — fechar o registro

Atualizar `pwa/TODO.md`: marcar o item da semana como resolvido, com as cinco
execuções do gate como evidência, e apagar a correção de premissa que este
plano absorveu (ela vira histórico do commit, não pendência).

## Fora de escopo

- O bloco "VISITAS NA JANELA ABERTA NA TELA" sem datas (fixture F07) — mesmo
  arquivo, mesma classe de problema, **item separado** no `TODO.md`. Não
  misturar: são duas mudanças de prompt com gates diferentes, e juntá-las
  esconde qual delas moveu o resultado.
- Alinhar a janela de 14 dias de `pwa_agenda_fetch` à semana. Hoje ela é
  `hoje + 13` e continua assim; o chat passa datas explícitas, então não
  depende do alinhamento.
