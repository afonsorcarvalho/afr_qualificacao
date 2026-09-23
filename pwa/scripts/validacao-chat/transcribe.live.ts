// scripts/validacao-chat/transcribe.live.ts
// Exercita o cliente de transcrição REAL contra a API real do OpenRouter.
//
// Não faz parte da suíte (`npm test` só pega `*.test.ts`): gasta cota e
// depende de rede. O que ele prova, e os testes unitários não podem provar:
// que o FORMATO que `openrouterTranscribe` monta é aceito pelo provedor. Os
// unitários checam o corpo contra o que nós achamos que o provedor quer;
// este checa contra o que ele de fato aceita.
//
//   npx vitest run --config vitest.live.config.ts scripts/validacao-chat/transcribe.live.ts
//
// LIMITAÇÃO CONHECIDA (deixando o buraco visível em vez de implícito): este
// script só monta e envia um blob `wav` (`tomWav()` abaixo). O `MediaRecorder`
// do app — nos dois mics, `MicButton.tsx` (coleta) e `useDitado.ts` (chat) —
// NUNCA produz wav: ambos emitem `audio/webm;codecs=opus`, caindo para
// `audio/webm` e depois `audio/mp4` conforme o suporte do navegador (ver a
// cascata de `MediaRecorder.isTypeSupported` nos dois arquivos). Ou seja: o
// único formato provado contra a API real aqui é exatamente o formato que a
// produção nunca manda. O caminho webm/opus (o que a produção de fato envia)
// NÃO foi verificado contra a API ao vivo por este script — essa verificação
// está sendo tratada separadamente por um teste manual de UI (gravar de
// verdade no navegador e observar o resultado), não por uma fixture webm
// sintética aqui.
import { readFileSync } from 'node:fs'
import { it, expect } from 'vitest'
import { openrouterTranscribe } from '@/lib/llm/transcribe'

// `dotenv` não é dependência deste projeto (o Next carrega `.env.local`
// sozinho, e aqui não há Next). Ler as duas variáveis à mão é mais honesto
// que acrescentar uma dependência só para um script fora da suíte.
for (const linha of readFileSync('.env.local', 'utf8').split('\n')) {
  const m = /^(OPENROUTER_API_KEY|OPENROUTER_STT_MODEL)=(.*)$/.exec(linha.trim())
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2]
}

/** WAV de 1s, 440Hz, mono 16kHz — áudio VÁLIDO e sem fala. */
function tomWav(): Blob {
  const sr = 16000, n = sr
  const buf = Buffer.alloc(44 + n * 2)
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write('WAVE', 8)
  buf.write('fmt ', 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20)
  buf.writeUInt16LE(1, 22); buf.writeUInt32LE(sr, 24); buf.writeUInt32LE(sr * 2, 28)
  buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34)
  buf.write('data', 36); buf.writeUInt32LE(n * 2, 40)
  for (let i = 0; i < n; i++) {
    buf.writeInt16LE(Math.round(12000 * Math.sin((2 * Math.PI * 440 * i) / sr)), 44 + i * 2)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

it('o cliente de transcrição é aceito pela API real do OpenRouter', async () => {
  expect(process.env.OPENROUTER_API_KEY, 'sem chave não há o que testar').toBeTruthy()

  const r = await openrouterTranscribe(tomWav(), { language: 'pt' })

  // Sem fala no áudio, o texto pode vir vazio ou alucinado — o que este teste
  // afirma é o CONTRATO (200, formato aceito, campo `text` string), não o
  // conteúdo. Afirmar conteúdo aqui seria testar o Whisper, não o nosso código.
  expect(typeof r.text).toBe('string')
  // eslint-disable-next-line no-console
  console.log(`texto: ${JSON.stringify(r.text)} | usage: ${JSON.stringify(r.usage ?? null)}`)
}, 120_000)
