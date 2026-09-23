// Config separada da suíte: `vitest.config.ts` roda offline e determinístico,
// esta bate na API real do modelo e no Odoo. Manter as duas separadas é o que
// impede um `npm test` de gastar cota sem querer.
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  // O plugin de React entra porque `lib/chat/tools.ts` importa `horaOdoo` de um
  // componente .tsx; sem ele o parse do JSX quebra antes de qualquer teste.
  plugins: [react()],
  test: {
    environment: 'node',
    globals: true,
    include: ['scripts/**/*.live.ts'],
    testTimeout: 900_000,
    hookTimeout: 60_000,
    reporters: ['verbose'],
    fileParallelism: false,
  },
  resolve: { alias: { '@': path.resolve(__dirname, '.') } },
})
