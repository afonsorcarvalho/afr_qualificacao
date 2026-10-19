import withPWAInit from 'next-pwa'
import { matchPageNavigation, matchRscRequest, matchAppImage } from './lib/pwa/swRoutes.mjs'

const withPWA = withPWAInit({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
  register: true,
  skipWaiting: true,
  buildExcludes: [/app-build-manifest\.json$/],
  // Escopo `/` é seguro em origem compartilhada com o Odoo porque pages/rsc/
  // imagens são restritos por path (ver lib/pwa/swRoutes.mjs). Rota nova do app
  // deve ir no Apache E nas regexes de lá.
  // Ordem importa (primeira que casa vence). As funções são serializadas para
  // dentro do sw.js: precisam ser autocontidas (sem closures).
  runtimeCaching: [
    {
      urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
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
}

export default withPWA(nextConfig)
