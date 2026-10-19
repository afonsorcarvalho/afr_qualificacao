# Plano — ditado em rajadas, cortando no silêncio

## O que muda para o usuário

Hoje o gestor clica no mic, fala, clica de novo e **só então** o texto aparece.
Depois desta mudança ele clica uma vez, fala, e o texto vai aparecendo em
blocos de alguns segundos enquanto ele continua falando.

Não é palavra a palavra. O STT do OpenRouter não tem streaming — conferido em
2026-09-22 na documentação (`/audio/speech` e `/audio/transcriptions`, as duas
requisição/resposta, sem websocket, sem resultado parcial, sem `stream: true`).
Palavra a palavra exigiria um segundo fornecedor e websocket atravessando o
Apache multi-inquilino do labquali; foi descartado por decisão do user.

Uso real, dito pelo user: **perguntas curtas, não laudos.** Rajadas de 5 a 10 s
cortando no silêncio.

## A ideia central, e por que as duas metades se encaixam

`MediaRecorder` com `timeslice` entrega pedaços em que **só o primeiro tem
cabeçalho de container** — o pedaço 2 isolado não é arquivo válido e o provedor
recusa. A saída correta é **parar e recomeçar** o gravador a cada rajada, o que
produz arquivos completos.

Isso custa uma fresta de alguns milissegundos entre parar e recomeçar, onde
áudio se perde. **Como o corte acontece no silêncio, o que se perde é
silêncio.** É essa coincidência que torna o picotamento seguro — não é
detalhe de implementação, é a razão do desenho.

## Fatos medidos, não re-derivar

- Cobrança do `openai/whisper-large-v3-turbo` é **linear, sem unidade mínima**:
  1/3/5/15 s de áudio cobraram 1/3/5/15 s (2026-09-22). Picotar **não** tem
  penalidade de custo; o tamanho da rajada é latência contra qualidade, só.
- O provedor estoura em ~60 s por requisição. Rajadas de até 8 s ficam
  folgadas.
- O Whisper transcreve cada rajada **sem contexto das anteriores**: palavra
  partida na borda vira lixo dos dois lados. É o que o corte no silêncio evita.

## Global Constraints

- **Mudança só de front: NÃO bumpar `__manifest__.py`.** Versão do PWA no
  `package.json`.
- Comentários e texto de UI em **pt-BR**, seguindo os arquivos vizinhos.
- `npx tsc --noEmit` **limpo, sem nenhuma saída**.
- **Não rodar `npm run build`** — o dev server de :3010 usa o mesmo `.next/`.
  Lint com `npx next lint`.
- Baseline: `docs/BASELINE.md`. Suíte em 804.
- Escopo é o mic do **chat** (`lib/hooks/useDitado.ts`). O `MicButton` da
  coleta é segurar-para-falar, curto por natureza — não mexer.

## Task 1 — detector de silêncio, função pura

**Arquivos novos:** `lib/audio/deteccaoSilencio.ts` + teste.

Fica fora do hook de propósito: decidir "isto é silêncio" é aritmética sobre
amostras e deve ser testável sem `MediaRecorder`, sem `AudioContext` e sem
React.

Exportar:
- uma função que recebe um bloco de amostras (`Float32Array`) e devolve o RMS;
- uma máquina de decisão que, alimentada com leituras de RMS ao longo do tempo,
  responde "fecha a rajada agora" ou "continua". Ela guarda o estado mínimo
  (há quanto tempo está abaixo do limiar, há quanto tempo a rajada dura) e é
  alimentada por quem tem o relógio — ela mesma **não** lê `Date.now()`, recebe
  o instante. Sem isso o teste vira espera real em vez de aritmética.

Parâmetros, com os valores acordados como default e sobrescrevíveis:
limiar de silêncio, `silencioMs` ≈ 700, `minRajadaMs` ≈ 1500, `maxRajadaMs` ≈ 8000.

Casos que o teste precisa fixar, cada um com o motivo no nome:
- silêncio curto no meio da fala (uma vírgula) **não** fecha a rajada;
- silêncio sustentado acima de `silencioMs` fecha;
- silêncio sustentado **antes** de `minRajadaMs` não fecha — senão cada
  respiração vira uma requisição;
- fala contínua sem pausa fecha ao bater `maxRajadaMs`;
- depois de fechar, o estado reinicia (a rajada seguinte não herda o
  contador da anterior);
- RMS de sinal nulo é zero; de senóide conhecida, o valor esperado.

## Task 2 — `useDitado` grava em rajadas

**Arquivos:** `lib/hooks/useDitado.ts` e seu teste (26 testes hoje).

Ao iniciar, além do que já faz: liga um `AnalyserNode` da Web Audio sobre o
MESMO `MediaStream` e amostra o RMS a cada ~50 ms, alimentando a máquina da
Task 1. Quando ela manda fechar: para o `MediaRecorder`, envia aquele blob, e
**imediatamente recomeça** um gravador novo sobre o mesmo stream. O gestor não
percebe; para ele a gravação é contínua até o segundo clique.

**Ordem é obrigatória.** A rajada 3 pode voltar antes da 2. Numerar cada rajada
e montar o texto por número, nunca por ordem de chegada. Um `+=` em `onTexto`
na ordem das respostas embaralha a frase, e embaralha de forma que parece erro
do Whisper.

**Dois comportamentos que quebram se ninguém cuidar:**

1. O piso `MIN_BLOB_BYTES` hoje avisa "Gravação muito curta" por gravação. Com
   rajadas, a última costuma ser um resto de silêncio e o aviso passaria a
   aparecer em toda sessão. O piso continua descartando a rajada minúscula, mas
   o **aviso** passa a valer para a sessão: só se a sessão inteira não produziu
   texto nenhum.
2. Falha de uma rajada **não** derruba a sessão: avisa uma vez e segue gravando.
   Sem isso, uma instabilidade de rede vira chuva de toast, um por rajada.

**Invariantes que já existem e NÃO podem se perder na reestruturação** — cada
um custou uma rodada de review, e o arquivo explica o porquê de cada um em
comentário; ler antes de mexer:

- `ControleDaTentativa` por tentativa, **não** contador de geração: "existe uma
  tentativa mais nova" e "esta tentativa foi cancelada" são fatos diferentes, e
  confundi-los descartava transcrição legítima em silêncio;
- o guarda `iniciando`, contra segundo clique enquanto o `getUserMedia` do
  primeiro ainda não resolveu (abria um segundo stream e órfãozava o primeiro);
- desarme do auto-stop em `parar()` **e** em `pararEDescartar()`;
- descarte ao fechar a folha, inclusive com permissão ainda pendente;
- todo caminho de falha para as tracks do stream — o microfone não pode ficar
  aceso sem controle na tela;
- os avisos de aquisição (`suportado`, `navigator.onLine`, branching de
  `nomeDoErro`) e os de transcrição (não-ok, rede, "Transcrição vazia").

O teto total de `MAX_DURATION_MS` (60 s) continua valendo para a **sessão**, não
por rajada.

**Testes:** além de preservar os 26, cobrir — fechamento por silêncio dispara
envio e recomeça a gravação; respostas fora de ordem são montadas na ordem
certa; rajada abaixo do piso é descartada sem aviso; sessão inteira sem texto
avisa uma vez; falha de uma rajada não interrompe a sessão nem repete o aviso;
o `AudioContext` é fechado em todos os caminhos de parada (senão fica contexto
de áudio vazando a cada ditado).

## Task 3 — a barra de gravação (desenho aprovado pelo user em 2026-09-23)

Depende da Task 2 ter exposto o nível de áudio. **Arquivo:** apenas
`app/tecnico/qualificacao/agenda/_ChatAgenda.tsx` e seu teste.

Referência que o user mandou: barra escura com o campo mostrando "Ouvindo…",
um medidor de nível à direita, e dois botões — **✕** e **✓** — no lugar do
envio.

Durante a gravação a linha do input troca de forma: o campo continua onde
está, com placeholder "Ouvindo…"; o botão de mic e o de enviar dão lugar a ✕
e ✓; entre o campo e os botões aparece o medidor.

- **✓** chama `parar()` — o que o segundo clique no mic faz hoje.
- **✕** chama `pararEDescartar()`. Essa função existe no hook desde sempre e a
  interface **nunca a ofereceu**: hoje, começou a gravar, o gestor é obrigado a
  transcrever. O print do user resolve um buraco que estava aberto em silêncio.

**"Ouvindo…" sai de graça.** Placeholder de HTML só aparece com campo vazio,
então ele se apaga sozinho quando a primeira rajada traz texto — que é
exatamente o comportamento que o user escolheu (placeholder enquanto não ouvi
nada; texto acumulando a partir daí). Não inventar estado para isso.

**O medidor passa na regra de movimento do `DESIGN.md`**, que aposentou
animação decorativa em loop, porque ele **se move em função do áudio, não de
keyframe** — é dado, não enfeite. Escrever isso no comentário, senão a próxima
limpeza de animação o remove por engano. Sob `prefers-reduced-motion`, tirar a
transição entre valores, não os valores.

**Acessibilidade:** as barras vão `aria-hidden` (leitor de tela não ganha nada
com elas) e entra um `role="status"` invisível anunciando "Gravando" e depois
"Transcrevendo" — sem isso quem usa leitor de tela perde toda a mudança de
estado que a barra comunica visualmente.

**O "+" do print fica de fora**: é botão de anexo, feature que o chat não tem.
Entrar com ele aqui seria escopo novo disfarçado de detalhe visual.

**Testes:** gravando mostra ✕/✓ e esconde mic/enviar; ✕ descarta sem
transcrever; ✓ transcreve; o medidor reflete o nível exposto pelo hook; parada
a gravação, a barra volta ao normal.

## Fora de escopo

- `MicButton` e as telas de coleta/finalizar.
- Botão de anexo ("+") na barra do chat.
- Qualquer tentativa de reconciliar bordas entre rajadas (sobreposição,
  dedupe). O corte no silêncio existe justamente para não precisar disso; se a
  qualidade decepcionar em uso real, aí sim vira tarefa própria, com o problema
  medido em vez de suposto.
- Trocar de fornecedor ou introduzir websocket.
