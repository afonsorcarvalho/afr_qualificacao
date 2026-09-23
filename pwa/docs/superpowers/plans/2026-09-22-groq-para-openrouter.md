# Plano — migrar as três features de IA do Groq para o OpenRouter

## O problema que começou isto

O gestor clica no microfone do chat e nada acontece — em dev e em produção.
Investigado em 2026-09-22; a causa tem duas camadas.

**Camada 1, configuração.** Não existe `GROQ_API_KEY` em ambiente nenhum.
`/api/groq/status`, cujo corpo é literalmente
`{ enabled: !!process.env.GROQ_API_KEY }`, devolve `{"enabled":false}` tanto em
`localhost:3010` quanto em `labquali.afrsistemas.com.br` — medido. O
`.env.local` do dev não tem a variável; o `.env` do labquali tem, vazia. A
chave antiga vazou em 2026-09-05 e a rotação foi adiada; nunca foi feita. As
**três** features de IA estão mortas desde então: ditado, auto-resumo e revisão
pré-fechamento.

**Camada 2, código.** Mesmo sem chave, a UI do chat convida o clique e depois
engole a recusa (detalhe na Task 4).

## A decisão (user, 2026-09-22)

Migrar **tudo** para o OpenRouter e apagar o Groq do projeto. Uma plataforma,
uma chave, uma fatura — e a chave do OpenRouter **já está configurada nos dois
ambientes**, então as três features voltam a funcionar sem gerar credencial
nova. A dívida da chave vazada deixa de existir junto com a variável.

## Fatos medidos contra a API real — não re-derivar

Levantados em 2026-09-22 com a chave de dev. Quem implementar pode confiar
nestes números e formatos:

- O endpoint existe: `POST https://openrouter.ai/api/v1/audio/transcriptions`.
  Rota inexistente no OpenRouter devolve 404; esta devolve 400 quando o corpo
  está errado, ou seja, ela roteia de verdade.
- **O corpo é JSON com base64, não multipart.** É a diferença real em relação
  ao Groq, que usa `FormData` com campo `file`:
  ```json
  {"model":"openai/whisper-large-v3-turbo",
   "input_audio":{"data":"<base64>","format":"wav"},
   "language":"pt"}
  ```
- Resposta verificada: `{"text":" E aí","usage":{"seconds":1,"cost":0.00000333}}`
  — HTTP 200. (O texto é alucinação do Whisper sobre um tom de 440 Hz sem fala;
  o que o teste provou é o transporte e o formato.)
- Os modelos de transcrição **não aparecem** em `/api/v1/models`. Para listá-los:
  `GET /api/v1/models?output_modalities=transcription` (22 modelos hoje).
- Modelo escolhido: **`openai/whisper-large-v3-turbo`**, US$ 0,00000333/s —
  o teto de 60 s do botão custa 0,02 centavo de dólar por ditado. É o **mesmo
  modelo** que o Groq já servia (`whisper-large-v3-turbo`), então a qualidade em
  pt-BR é a que o time já conhecia.
- Equivalente do modelo de texto: **`meta-llama/llama-3.3-70b-instruct`**
  (prompt US$ 0,0000001 / completion US$ 0,00000032), contra o
  `llama-3.3-70b-versatile` que o Groq servia.

## Onde o Groq está hoje

| Rota | Modelo | Chamada por |
|---|---|---|
| `app/api/groq/transcribe` | `whisper-large-v3-turbo` | `MicButton`, `useDitado` |
| `app/api/groq/summary` | `llama-3.3-70b-versatile` | `SummaryButton`, `ReviewPanel`, finalizar |
| `app/api/groq/review` | `llama-3.3-70b-versatile` | `ReviewPanel` |
| `app/api/groq/status` | — | `useGroqStatus` |

`lib/groq/client.ts` expõe `groqChat` e `groqTranscribe`. **`groqChat` já é um
envelope fino sobre `llmChat` de `lib/llm/client.ts`** (mesmo cliente que o chat
de agendamento usa) — só troca `baseUrl`, chave e modelo, e converte `LlmError`
em `GroqError`. `groqTranscribe`, esse sim, fala multipart direto com o Groq e
precisa ser reescrito.

## Global Constraints

- **Mudança só de front: NÃO bumpar `__manifest__.py`.** A versão do PWA vive no
  `package.json`.
- **Os caminhos `/api/groq/*` NÃO mudam nesta migração.** Renomear para
  `/api/ia/*` obrigaria a acrescentar a rota no Apache do labquali e a coordenar
  a ordem do deploy, por ganho cosmético. Fica como follow-up registrado. Quem
  implementar deve deixar um comentário no topo de cada rota dizendo que o nome
  é histórico e o provedor é OpenRouter.
- Texto de UI e mensagens em **pt-BR**, seguindo os arquivos vizinhos.
- `npx tsc --noEmit` precisa ficar **limpo, sem nenhuma saída**. A antiga
  "exceção pré-existente do `.next/types`" era um defeito real, corrigido em
  `214f142`; qualquer erro agora é regressão.
- **Não rodar `npm run build`** — o dev server de :3010 usa o mesmo `.next/`.
  Para lint, `npx next lint`, que não escreve em `.next/`.
- Baseline de testes: `docs/BASELINE.md`. Nenhuma falha é ambiental.
- **Nunca** escrever valor de chave em arquivo versionado, nem em teste.

## Task 1 — cliente de transcrição do OpenRouter

**Arquivo novo:** `lib/llm/transcribe.ts`, com `lib/llm/transcribe.test.ts`.

Função que recebe um `Blob` e devolve `{ text, usage }`, falando o formato
JSON+base64 documentado acima. Fica ao lado de `lib/llm/client.ts` e reaproveita
o que já existe lá: `LlmError` para o erro e `readError` para extrair a
mensagem do corpo. **Não** criar uma hierarquia de erro nova.

Pontos que o teste precisa fixar, cada um por um motivo:
- o corpo enviado é JSON com `input_audio.data` em base64 e `input_audio.format`
  derivado do mime do blob (`webm`, `mp4`, `wav`) — enviar multipart é o modo
  de falhar silenciosamente com 400;
- `language` entra quando informado;
- resposta sem `text` string vira `LlmError`, não `undefined` vazando pro
  chamador;
- resposta não-ok vira `LlmError` com a mensagem do corpo;
- o timeout de 60 s (`AbortController`) do `groqTranscribe` atual é preservado —
  sem ele um provedor pendurado trava o botão em "transcrevendo" pra sempre.

Modelo default: `openai/whisper-large-v3-turbo`, sobrescrevível por
`OPENROUTER_STT_MODEL`, no mesmo espírito do `OPENROUTER_MODELS` do chat.

## Task 2 — as três rotas passam a usar o OpenRouter

**Arquivos:** `app/api/groq/{transcribe,summary,review,status}/route.ts`.

- `transcribe`: trocar `groqTranscribe` pela função da Task 1.
- `summary` e `review`: trocar `groqChat` por `llmChat` direto
  (`lib/llm/client.ts`), com `baseUrl` do OpenRouter, `apiKey` de
  `OPENROUTER_API_KEY` e modelo `meta-llama/llama-3.3-70b-instruct`. Os prompts
  e o `response_format` **não mudam** — a migração não é o momento de mexer no
  que o modelo recebe.
- Todas as quatro: o feature flag passa a ser `OPENROUTER_API_KEY`. A mensagem
  de 503 continua "IA não configurada".
- `status`: `{ enabled: !!process.env.OPENROUTER_API_KEY }`.

Os testes existentes dessas rotas (`app/api/groq/**/*.test.ts`) manipulam
`process.env.GROQ_API_KEY`; precisam passar a manipular `OPENROUTER_API_KEY`.
**Não** apagar asserção para fazer teste passar — o que se testa (503 sem
chave, 401 sem sessão, limites de tamanho) continua valendo.

## Task 3 — apagar o Groq do projeto

- Remover `lib/groq/client.ts` e seus testes.
- Remover `GROQ_API_KEY` de `pwa/docker-compose.yml`, do `README.md` (seção
  Produção) e dos `.env*.example`. Acrescentar `OPENROUTER_STT_MODEL` como
  opcional onde o `OPENROUTER_MODELS` já é citado.
- `grep -rn "groq\|GROQ" --include=*.ts --include=*.tsx --include=*.md --include=*.yml`
  não pode sobrar nada além dos nomes de caminho `/api/groq/*` (que ficam, por
  decisão acima) e da nota histórica no `TODO.md`.
- O hook `useGroqStatus` e o componente `MicButton` seguem com esses nomes; um
  rename de símbolo entra no mesmo follow-up do rename de rota.

## Task 4 — o mic do chat para de falhar em silêncio

Independente da migração: mesmo com chave, hoje uma falha some.

**A — esconder o mic quando a IA está desligada.**
`app/tecnico/qualificacao/agenda/_ChatAgenda.tsx` (~linha 152) renderiza o botão
de microfone sem consultar `useGroqStatus`, ao contrário de
`_components/MicButton.tsx:171`, que faz `return null`. Igualar o comportamento.
Esconder e não desabilitar: é o que o `MicButton` faz, e botão desabilitado sem
explicação é tão mudo quanto o problema atual.

⚠️ **Armadilha nos testes.** `ChatAgenda.test.tsx` mocka `@/lib/chat/machine` e
`@/lib/chat/tools`, mas **não** mocka `useGroqStatus` nem a rota de status. Como
o hook devolve `{enabled:false}` quando o `fetch` falha, os testes que hoje
encontram o botão de mic vão quebrar. Eles precisam declarar o estado que
exercitam. Não remover as asserções: o ponto delas é que o botão existe quando
deve.

**B — falha de transcrição precisa aparecer.**
`lib/hooks/useDitado.ts` (~linha 182) faz `if (res.ok) { ...onTexto... }` e mais
nada: um 503 cai fora sem passar por lugar nenhum. O `catch` marcado "Silencioso
de propósito" só pega exceção de rede, e de todo modo aquele raciocínio
justifica **não bloquear**, não ser **invisível**. Tratar o caminho não-ok lendo
`{error}` do corpo e avisando com `toast.error`, no mesmo formato do
`MicButton.tsx:67-72`. O gestor continua podendo digitar. Corrigir o comentário,
que deixa de descrever o código.

Testes:
- em `lib/hooks/useDitado.test.ts` (14 testes hoje): 503 avisa e não chama
  `onTexto`; falha de rede avisa; sucesso continua chamando `onTexto` **sem**
  aviso — a regressão que importa é o caminho feliz virar barulhento;
- em `ChatAgenda.test.tsx`: IA desligada → sem botão de mic; IA ligada → com
  botão. O segundo protege contra "resolver" escondendo o mic pra sempre.

## Verificação final (controller, não implementer)

Com o dev server de pé e sessão válida, ditar de verdade no chat e conferir que
o texto aparece no campo. Um `curl` na rota não substitui: o defeito relatado é
de UI, e foi a UI que ficou muda.

## Fora de escopo

- Renomear `/api/groq/*` → `/api/ia/*`, `useGroqStatus`, `MicButton`. Follow-up.
- Unificar `MicButton` e `useDitado` numa implementação só: são duas interações
  diferentes de propósito — segurar-para-falar na coleta (uma mão, em campo) e
  clicar-para-alternar no chat. Débito, não tarefa.
- Mexer nos prompts de `summary` e `review`.
