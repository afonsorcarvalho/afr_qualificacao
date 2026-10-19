import '@testing-library/jest-dom'

// O app roda sob `basePath: '/app'` (next.config.mjs injeta a env no build);
// os testes reproduzem o mesmo valor para `lib/basePath.ts`.
process.env.NEXT_PUBLIC_BASE_PATH = '/app'

// Fallback global de `AudioContext`: desde a Task 2 de "ditado em rajadas",
// `useDitado.ts` liga um `AnalyserNode` sobre o stream do microfone toda
// vez que grava — happy-dom (o ambiente DOM usado pelos testes) não
// implementa Web Audio, e sem isto QUALQUER teste que exercite o ditado
// (mesmo indiretamente, via `_ChatAgenda.tsx`) cairia no catch de
// "Falha ao acessar microfone" antes de conseguir gravar. Testes que
// precisam CONTROLAR o nível de áudio (ex. `useDitado.test.ts`, pra testar
// fechamento de rajada por silêncio) sobrescrevem `globalThis.AudioContext`
// com o próprio dublê no `beforeEach` — este aqui só cobre quem nunca
// mexeu em rajada/silêncio e só precisa que a construção não estoure.
if (typeof (globalThis as { AudioContext?: unknown }).AudioContext === 'undefined') {
  class AudioContextFallback {
    createMediaStreamSource() {
      return { connect: () => {} }
    }
    createAnalyser() {
      return {
        fftSize: 2048,
        getFloatTimeDomainData: () => {},
      }
    }
    close() {
      return Promise.resolve()
    }
  }
  ;(globalThis as unknown as { AudioContext: unknown }).AudioContext = AudioContextFallback
}
