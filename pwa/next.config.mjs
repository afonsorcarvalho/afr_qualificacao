import withPWAInit from 'next-pwa'

const withPWA = withPWAInit({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
  register: true,
  skipWaiting: true,
  buildExcludes: [/app-build-manifest\.json$/],
  // Ordem importa (primeira que casa vence). As funções são serializadas para
  // dentro do sw.js: precisam ser autocontidas (sem closures).
  runtimeCaching: [
    {
      urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
      handler: 'NetworkOnly',
    },
    {
      urlPattern: ({ request }) => request.mode === 'navigate',
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
      urlPattern: ({ request, url }) =>
        request.headers.get('RSC') === '1' && !url.pathname.startsWith('/api/'),
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
      urlPattern: /^https?.*\.(png|jpg|jpeg|svg|gif|webp|woff2?)$/,
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
