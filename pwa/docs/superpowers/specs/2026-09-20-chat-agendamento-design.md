# Chat de agendamento no PWA — design

Data: 2026-09-20
Módulo: `addons/afr_qualificacao/pwa` (submodule `afr_qualificacao`)
Instância alvo: labquali (onde o `afr_qualificacao` roda hoje)

## Problema

Remarcar uma visita de campo hoje exige navegar a agenda, achar o card,
abrir a folha e editar campo a campo. O gestor quer dizer "remarca a visita
do João de quinta pra sexta" e ver aquilo acontecer.

## Decisões fechadas

| Questão | Decisão |
|---|---|
| Público | Só Gestor (`can_manage`). Técnico não vê o chat. |
| Onde o loop roda | Servidor faz UM turno de LLM, stateless. As ferramentas executam no cliente. |
| Escrita | Duas fases: o modelo propõe, a UI mostra card, o gestor confirma. |
| Provider | OpenRouter como SEGUNDO provider, só para o chat. Groq segue em review/summary/transcribe. |
| Histórico | Client-side (`sessionStorage`). Nenhum modelo novo no Odoo. |
| Voz | Reusa `/api/groq/transcribe`. |
| Sugestão | O modelo lê os campos de conflito já serializados e propõe slot livre. |
| Cota | Tier gratuito puro, sem compra de crédito. Teto de ~5-16 mensagens/dia aceito: é prova de conceito, não uso diário. |

## Constraint central: nenhuma RPC de escrita nova

As RPCs `pwa_*` de `afr.qualificacao.os.visita` já carregam
`_check_manager_only`, a whitelist `_PWA_WRITABLE_FIELDS`, o
`_board_check_not_done`, a trava de estado da OS e a sanitização de
`instrument_ids` para `(6, 0, ids)`. O chat é mais um cliente delas.

**Nenhum arquivo de `addons/afr_qualificacao_agendamento/` é tocado.**
Qualquer caminho de escrita novo seria um buraco nessa camada.

`pwa_visita_delete` existe mas **não é exposto ao modelo** — apagar visita
não estava no pedido, e é a operação menos reversível do conjunto.

## Arquitetura

### Peças novas

| Arquivo | Papel |
|---|---|
| `lib/llm/client.ts` | `chatCompletion(messages, {baseUrl, key, model, tools})`. Generaliza o cliente OpenAI-compatível que hoje vive em `lib/groq/client.ts` (timeout, mapeamento de erro). `lib/groq/client.ts` passa a delegar para ele, preservando `GroqError` e seus testes. |
| `lib/chat/toolDefs.ts` | Só os JSON Schemas e a marca `read`/`write`. Fica separado do dispatch porque a rota precisa importá-lo sem ganhar acesso ao Odoo. |
| `lib/chat/tools.ts` | O dispatch: nome de ferramenta → função de `lib/odoo/agenda.ts`. |
| `lib/chat/prompt.ts` | O system prompt, montado a partir de `server_today`, do roster de técnicos e da janela visível. Fica em arquivo próprio porque é load-bearing (instrução pt-BR, regra de id, regra de ambiguidade) e precisa ser versionado e testável, não inline num componente. |
| `lib/chat/machine.ts` | O loop. Sem React: recebe transcript, devolve próximo estado. Executa ferramentas de leitura, PARA nas de escrita. |
| `app/api/chat/route.ts` | Stateless. `{messages, tools}` → um turno do OpenRouter. **O bloco `provider` (filtro de treino + `require_parameters`) e a cadeia de modelos são injetados aqui, no servidor** — é política, o cliente não pode sobrescrever. Não importa nada de `lib/odoo`. |
| `app/api/chat/status/route.ts` | `{enabled: !!process.env.OPENROUTER_API_KEY}`, espelhando `/api/groq/status`. |
| `lib/hooks/useChatAgenda.ts` | Cola React → `machine.ts`, invalidação do React Query após escrita confirmada. |
| `app/tecnico/qualificacao/agenda/_ChatAgenda.tsx` | Drawer na agenda. Só renderiza com `can_manage` **e** IA ligada. |

### Fluxo de uma volta

1. O cliente monta o system prompt com `server_today` (vindo de
   `pwa_agenda_fetch`, nunca do relógio do aparelho), o papel do usuário e
   a janela de visitas já carregada na tela.
2. `POST /api/chat` → OpenRouter → o turno volta com texto ou `tool_calls`.
3. Ferramenta de **leitura**: o cliente executa via `lib/odoo/agenda.ts`,
   anexa o resultado como `role: "tool"` e volta ao passo 2.
4. Ferramenta de **escrita**: o loop para. Nada é gravado.
5. A UI renderiza o card de proposta com o diff campo a campo, mais OS,
   cliente, cidade e data — contexto suficiente para o gestor perceber um
   alvo errado. Botões Confirmar / Cancelar.
6. Confirmar dispara a RPC real. O retorno entra no transcript como
   `role: "tool"`, o modelo fecha com texto e a agenda revalida.
7. Erro do Odoo (`UserError`) já vem em pt-BR voltado ao usuário: entra no
   transcript, o modelo explica ou tenta outro caminho.

### Ferramentas expostas

Leitura: `buscar_agenda(date_from, date_to)`, `listar_tecnicos()`,
`listar_instrumentos()`, `listar_os()`.

Escrita (sempre confirmadas): `criar_visita(os_id, tecnico_id, date)`,
`atualizar_visita(visita_id, vals)` com `vals` restrito aos campos de
`VisitaVals` — `date`, `time_start`, `time_stop`, `tecnico_id`, `note`,
`instrument_ids`.

Cada uma mapeia 1:1 para uma função já existente em `lib/odoo/agenda.ts`.

## Invariantes

### Relógio

O modelo **nunca** deduz a data de hoje. `server_today` é injetado no
prompt; todo argumento de data é ISO absoluta (`2026-10-16`). O
`machine.ts` valida o formato antes de despachar e rejeita o turno se vier
`"quinta"` ou data relativa, devolvendo o erro ao modelo.

Isto não é preferência: o skew de relógio do aparelho já quebrou este app
antes, e é por isso que `pwa_agenda_fetch` devolve `server_today`.

### Ids nunca são inventados

O `machine.ts` mantém o conjunto de ids que apareceram em resultado de
ferramenta ou no contexto da tela. Uma escrita com id fora desse conjunto
**não é despachada**: volta ao modelo como
`"id 999 não apareceu em nenhuma consulta; busque a visita primeiro"`.

Nome → id é sempre resolvido por ferramenta (`listar_tecnicos`), nunca por
memória do modelo.

### Ambiguidade

Duas visitas do João na quinta: o prompt manda perguntar, não escolher. O
card de confirmação é a segunda rede.

### A fronteira de escrita é física

`app/api/chat/route.ts` não importa `lib/odoo`. O servidor não consegue
gravar no Odoo nem se o prompt for subvertido. Há teste para isso.

## Sugestão de horário e técnico

`buscar_agenda` já devolve `tecnico_conflict`, `travel_conflict`,
`instrument_conflict` e `calibration_conflict` com mensagem. O prompt
instrui: consulte a janela antes de propor, evite dia com conflito e, se o
gestor insistir num horário conflitante, proponha mas avise no card.

Nenhum otimizador é construído — o servidor já calcula o conflito.

## Erros e limites

- `429` ou indisponibilidade do OpenRouter: cadeia de fallback por env
  (`OPENROUTER_MODELS`, separado por vírgula). Esgotada, a mensagem é
  "IA indisponível, use a agenda manual".
- Sem `OPENROUTER_API_KEY`: `/api/chat/status` devolve `enabled: false` e o
  botão não aparece — mesmo padrão de `useGroqStatus`.
- Timeout de 30s, igual ao cliente atual.
- **Teto de 4 voltas de ferramenta por pedido.** Era 8 enquanto a cota não
  estava decidida; com o tier gratuito puro (ver "Cota") cada volta é uma
  requisição contra um limite de 50/dia, então o teto deixou de ser só um
  freio de emergência e virou o principal regulador da capacidade diária.
  Quatro voltas cobrem o fluxo mais longo previsto (listar técnicos →
  buscar agenda → propor → confirmar); o típico é 2 a 3.
- **20 requisições por minuto**, limite do OpenRouter por conta. O chat
  serializa os pedidos (um de cada vez, entrada travada enquanto processa),
  o que já mantém um usuário humano abaixo do limite; se ainda assim vier
  `429`, a cadeia de fallback tenta o próximo modelo e, esgotada, a
  mensagem de indisponibilidade aparece na conversa. Nunca repetir em laço.

A chave vive só no servidor, em `pwa/.env.local` (que ainda não existe
neste checkout). Nunca em `NEXT_PUBLIC_*`.

## Interface

Botão flutuante na agenda, condicionado a `can_manage` e à IA ligada.
Drawer Radix seguindo o padrão do `VisitaSheet`. Bolhas de usuário e
assistente; chamada de ferramenta como linha discreta ("consultando
agenda…"); card de proposta destacado.

Entrada por voz: botão de microfone → `/api/groq/transcribe` → o texto cai
no **input**, não é enviado sozinho. O gestor revisa antes de mandar.

Transcript em `useState` + `sessionStorage`: fechar e reabrir mantém, F5
limpa. Sem streaming no v1.

## Testes

Vitest, sem rede real, seguindo o padrão de `lib/groq/client.test.ts`.

- `lib/llm/client.test.ts` — monta o corpo com `tools`; timeout; mapeia
  429/503; erro quando falta `choices`.
- `lib/chat/tools.test.ts` — cada schema aceita o argumento válido e
  rejeita o inválido; `criar_visita`/`atualizar_visita` marcadas `write`;
  **`excluir_visita` não existe no registro** (guarda contra reintrodução).
- `lib/chat/machine.test.ts` — leitura executa e realimenta; escrita para e
  vira proposta; id fora do conjunto visto não despacha; data não-ISO é
  rejeitada; teto de 4 voltas; erro de ferramenta vira `role: "tool"` e o
  loop continua.
- `app/api/chat/route.test.ts` — corpo inválido → 400; sem chave → 503; a
  rota não importa `lib/odoo` (teste de fronteira).
- `_ChatAgenda.test.tsx` — não renderiza com `can_manage: false`; o card
  mostra o diff; Cancelar não chama RPC; Confirmar chama uma vez só.

O baseline do front está limpo (`pwa/docs/BASELINE.md`): qualquer falha
nova é regressão.

## Escolha do modelo

Pesquisa documental de 2026-09-20 sobre os ~20 modelos gratuitos do
OpenRouter que declaram `tools` em `supported_parameters`. Nenhum teste
empírico foi feito — não há `OPENROUTER_API_KEY` neste checkout.

### Cadeia

```
OPENROUTER_MODELS=google/gemma-4-31b-it:free,google/gemma-4-26b-a4b-it:free,qwen/qwen3.8-27b:free
```

**Primário `google/gemma-4-31b-it:free`.** Tool calling é nativo no nível
do tokenizer, não emulado por template: os tokens `<|tool_call>` /
`<tool_call|>` (ids 46–51) são `special: true` no `tokenizer.json`, e o
`tokenizer_config.json` embarca a spec de parsing (`x-parser:
"gemma4-tool-call"`, `repeats: true` = chamadas paralelas). O Gemma 3, por
contraste, não tinha nenhum token de tool e o template nem aceitava o
parâmetro `tools` — era emulação por prosa.

Números de uso de ferramenta (tech report, Table 5; τ²-bench):

| | 31B | 26B-A4B | Gemma 3 27B |
|---|---|---|---|
| τ² airline | 75,0 | **76,0** | 39,0 |
| τ² retail | 86,4 | 85,5 | 6,6 |
| τ² telecom | **69,3** | 43,0 | 3,1 |
| média | **76,9** | 68,2 | 16,2 |
| IFEval | 98,9 | 98,5 | 90,4 |

**Fallback 1 `google/gemma-4-26b-a4b-it:free`.** A média de 68,2 engana:
toda a diferença vem de *telecom*. Em **airline o MoE ganha (76,0 × 75,0)**
e em retail empata (85,5 × 86,4). Nossa carga — consultar agenda, achar
registro, propor escrita — tem a forma de airline/retail, não de telecom.
Ativa 3,8B de 25,2B, então é bem mais rápido.

**Fallback 2 `qwen/qwen3.8-27b:free`.** Único do trio com provedor
diferente (o Gemma é servido **exclusivamente** pelo Google AI Studio;
quando ele cai, os dois primeiros caem juntos). Fica por último por três
motivos concretos: **zero evidência de português** (o model card não tem
nem a tag `language:`; a linha "201 languages" do README é do Qwen3.5, não
do 3.8); thinking ligado por padrão e **desligar quebra o tool calling** em
prompts longos (issue aberta QwenLM/Qwen3.8#236); e o default
`reasoning_effort: xhigh` devolve resposta vazia em ~19% das chamadas
(#216). Se cair nele, forçar `reasoning_effort: "low"`.

**`openrouter/free` é rejeitado**: seleciona modelo ao acaso, então a
política de dados fica desconhecida por chamada.

### Thinking: desligado, e no Gemma isso é seguro

No Gemma 4 o thinking é **opt-in** — liga incluindo o token `<|think|>` no
início do system prompt; o default do template é `enable_thinking=false`, e
nesse caso o próprio template pré-preenche o bloco vazio, então não se paga
tokens gerados. Medição independente (Artificial Analysis): com reasoning,
*time to first answer token* 50,3s e E2E 64,5s; sem, 2,1s e 14,1s — **~4,6×
mais rápido**.

Com 2 a 5 chamadas sequenciais por mensagem do gestor, isto é decisivo:
rodamos sem thinking. Pela API do OpenRouter isso é
`reasoning: {enabled: false}` no corpo — **e isso precisa ser verificado na
prática**, porque o endpoint gratuito do Gemma 4 expõe `reasoning` e
`include_reasoning` mas não `reasoning_effort`; se o flag não suprimir o
bloco, a latência por si só derruba a escolha.

A ressalva honesta: os 76,9% de τ² foram medidos **com** thinking, e o
Google não publica o número sem. Entra na validação empírica.

### Privacidade: filtro por provedor, não por ZDR

Três fornecedores de modelos gratuitos **treinam nos prompts**: Nvidia
(todos os Nemotron 3), Thinking Machines (inkling) e Liquid. Isso elimina o
`nemotron-3-ultra-550b:free`, que seria forte em tool calling. Dados de
cliente hospitalar não vão para treino.

Também descartados por origem ou contrato, não por qualidade: Cohere
`north-mini-code:free` (trial key **não** é coberta pelos Enterprise Data
Commitments; o Terms of Use §4 concede direito de usar o conteúdo para
melhorar os serviços e compartilhar com terceiros), Nex AGI (sediada em
Xangai, sem Terms of Service e com política de privacidade ilegível — SPA
vazio), Dots 3 (Xiaohongshu) e Ling 3.0 (Ant Group) — os dois últimos sem
qualquer evidência de português.

O corpo da requisição carrega:

```json
"provider": {
  "ignore": ["nvidia", "liquid", "thinkingmachines"],
  "require_parameters": true
}
```

**Não usar `provider: {zdr: true}` nem `data_collection: "deny"`.** Esses
filtram *retenção*, não treino, e excluiriam o próprio primário — o Google
AI Studio não treina mas retém 55 dias. A proteção ficaria ligada e o
modelo sumiria em silêncio.

`require_parameters: true` resolve um problema separado: nem todo endpoint
do OpenRouter para esses modelos declara `tools` (há um DeepInfra do 31B e
dois do 26B-A4B sem). Sem esse flag, o roteamento pode cair num endpoint
que ignora as ferramentas e o modelo parece incapaz.

### pt-BR precisa de instrução explícita

O P3B3 (arXiv 2606.16753), benchmark multi-turno de viés pt-PT/pt-BR,
avalia o `gemma-4-31B-it` nominalmente. Escala 0 = pt-BR, 100 = pt-PT,
coluna LLM-as-judge: **49,2 sem instrução, 7,3 com instrução pt-BR**. Para
referência, o Sabiá-4 (nativo pt-BR) fica em 8,1 sem instrução. O paper
observa que a aderência se mantém estável ao longo dos turnos.

Ou seja: sem instrução o modelo fica neutro entre as variedades. O system
prompt diz "responda em português do Brasil" explicitamente.

### `tool_choice: "required"` não é confiável

O OpenRouter lista `tool_choice` em `supported_parameters`, mas o vLLM
declara `supports_required_and_named = False` para o Gemma 4. O design não
depende disso: o modelo escolhe livremente e o `machine.ts` trata o caso de
turno sem ferramenta como resposta de texto normal.

### Contrapeso independente, registrado

A Artificial Analysis conta história oposta à do Google: no índice dela o
Gemma 4 31B fica atrás do Qwen3.5 27B *"primarily due to weaker agentic
performance"* (Agentic Index 32 para o 26B-A4B contra 44 do Qwen3.5 35B).
São benchmarks diferentes — τ²-bench é chat com ferramentas, o índice da AA
pesa muito computer-use e coding — mas a divergência é material e fica
registrada: o vendor vende como força justamente o que o único avaliador
independente aponta como fraqueza.

### Não existe medição independente de function calling

O BFCL (Berkeley Function-Calling Leaderboard) **não cobre nenhum
candidato**. Verificado baixando os 6 CSVs do leaderboard: 109 modelos, o
topo é Claude-Opus-4-5 com 77,47%, e não há **um único modelo de 2026**.
Cuidado com dois falsos positivos: `Qwen3-8B` no BFCL é o Qwen3 de 8
bilhões, não a família Qwen3.8; e `Llama-3.1-Nemotron-Ultra` não é o
Nemotron 3.

O taubench.com oficial também não cobre o Gemma 4. Portanto os 76,9% são
número do próprio fornecedor, e os números da NVIDIA que colocam o Gemma à
frente (τ³ Banking 14,02; IFBench 77,25) são de concorrente, porém em
harness proprietário.

Tratar `benchmarklist.com` como não confiável: republica figuras de vendor
afirmando serem avaliação independente.

### Validação empírica antes de fechar o modelo

A pesquisa documental ordenou os candidatos; não resolve "declara `tools`
mas falha na prática" — e o padrão de falha observado no campo com Gemma 4
é justamente **parser da stack de serving**, não o modelo (o formato nativo
dele não é JSON válido: chaves sem aspas, strings delimitadas por token).

Antes de considerar a feature pronta, rodar ~10 fixtures em pt-BR coloquial
e pontuar: ferramenta correta escolhida; data ISO derivada do
`server_today` injetado e nunca deduzida; nenhum id alucinado (contar a
frequência, já que o `machine.ts` barra); a segunda chamada consome mesmo o
resultado da primeira; e wall-clock por mensagem.

## Cota: tier gratuito puro, teto aceito

Decisão do usuário: **sem comprar crédito**. Consequência registrada aqui
porque ela limita o uso, não o código.

Os limites do OpenRouter são globais por conta (chaves ou contas extras não
mudam nada): **20 req/min** sempre, e **50 requisições/dia** com menos de
US$ 10 de crédito vitalício comprado — contra 1000/dia acima disso.

O teto que importa é por requisição *upstream*, e cada mensagem do gestor
gasta 2 a 5 delas:

| Requisições por mensagem | Mensagens/dia no tier free |
|---|---|
| 2 (consulta simples) | 25 |
| 3 (típico) | 16 |
| 5 (teto: 4 voltas + resposta final) | 10 |

O limite de 20 req/min também morde: são 4 a 6 mensagens por minuto no
melhor caso, o que é folgado para uso humano mas não para teste automatizado.

**Isso serve para prova de conceito e demonstração, não para uso diário.**
O produto degrada limpo quando a cota estoura: a cadeia de fallback tenta o
próximo modelo, e esgotada ela a mensagem é "IA indisponível, use a agenda
manual" — a agenda continua inteira e editável à mão.

Se um dia o uso justificar, a saída é barata e não mexe em código: US$ 10
de crédito elevam para 1000 req/dia mantendo o `:free` em custo zero, e o
mesmo modelo **sem** o `:free` custa cerca de US$ 1,59 por 1000 pedidos.
Ambos são troca de variável de ambiente.

## Fora de escopo

Excluir visita pelo chat. Persistir a conversa no Odoo. Streaming. Chat
para o técnico. Widget OWL no backend. Harness de avaliação de prompt.

## Entrega

Tudo em `addons/afr_qualificacao/pwa/`. Push no submodule `afr_qualificacao`
**antes** do bump do pointer no monorepo. Mudança só de front: **sem bump de
`__manifest__.py`**; a versão do PWA vive no `package.json`.

## Risco aceito

Modelo gratuito de tool calling erra mais que modelo pago. O dano é contido
pela confirmação humana e pela validação de id: o pior caso é "o card
mostrou besteira, cancelei", não escrita errada. Trocar de modelo é uma
variável de ambiente.
