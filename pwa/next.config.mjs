import withPWAInit from 'next-pwa'
import { matchPageNavigation, matchRscRequest, matchAppImage } from './lib/pwa/swRoutes.mjs'

const withPWA = withPWAInit({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
  register: true,
  skipWaiting: true,
  buildExcludes: [/app-build-manifest\.json$/],
  // Com `basePath: '/app'` o next-pwa emite o SW para `/app/sw.js`, escopo
  // `/app/`, e prefixa o precache (`/app/_next/...`). As regras abaixo casam
  // por prefixo `/app/` (lib/pwa/swRoutes.mjs): rota nova não mexe no SW.
  // Ordem importa (primeira que casa vence). As funções são serializadas para
  // dentro do sw.js: precisam ser autocontidas (sem closures).
  runtimeCaching: [
    {
      urlPattern: ({ url }) => url.pathname.startsWith('/app/api/'),
      handler: 'NetworkOnly',
    },
    {
      urlPattern: matchPageNavigation,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'pages',
        networkTimeoutSeconds: 3,
        matchOptions: { ignoreSearch: true },
        expiration: { maxEntries: 50 },
        plugins: [
          {
            // Só respostas 200 same-origin: nunca redirect (ex.: /login),
            // erro ou opaca. Autocontido: é serializado dentro do sw.js.
            cacheWillUpdate: async ({ response }) =>
              response &&
              response.status === 200 &&
              !response.redirected &&
              response.type === 'basic'
                ? response
                : null,
          },
        ],
      },
    },
    {
      urlPattern: matchRscRequest,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'rsc',
        networkTimeoutSeconds: 3,
        expiration: { maxEntries: 50 },
        plugins: [
          {
            // Só respostas 200 same-origin: nunca redirect (ex.: /login),
            // erro ou opaca. Autocontido: é serializado dentro do sw.js.
            cacheWillUpdate: async ({ response }) =>
              response &&
              response.status === 200 &&
              !response.redirected &&
              response.type === 'basic'
                ? response
                : null,
          },
        ],
      },
    },
    {
      urlPattern: matchAppImage,
      handler: 'CacheFirst',
      options: {
        cacheName: 'static-assets',
        expiration: { maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 },
      },
    },
  ],
})

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Prefixo único (spec §9): o PWA divide o domínio com o Odoo e o proxy
  // precisa de uma regra só. O valor vai ao cliente por NEXT_PUBLIC_BASE_PATH
  // (lib/basePath.ts) para os caminhos que o Next não prefixa.
  basePath: '/app',
  env: { NEXT_PUBLIC_BASE_PATH: '/app' },
}

export default withPWA(nextConfig)
