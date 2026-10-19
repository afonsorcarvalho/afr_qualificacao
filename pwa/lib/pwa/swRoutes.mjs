// Funções de match do runtimeCaching do service worker. São serializadas
// (toString) para dentro do public/sw.js: precisam ser AUTOCONTIDAS — sem
// closures, sem constantes externas, sem imports. Por isso o prefixo `/app/`
// é repetido dentro de cada função.
//
// Todo o PWA vive sob o basePath `/app` (spec §9): casar por prefixo basta,
// rota nova do app não exige mudança aqui nem no Apache. `/app/api/` é
// NetworkOnly (regra anterior no next.config.mjs) e é excluído aqui também.

export function matchPageNavigation({ request, url }) {
  return (
    request.mode === 'navigate' &&
    (url.pathname === '/app' || url.pathname.startsWith('/app/')) &&
    !url.pathname.startsWith('/app/api/')
  )
}

export function matchRscRequest({ request, url }) {
  return (
    request.headers.get('RSC') === '1' &&
    (url.pathname === '/app' || url.pathname.startsWith('/app/')) &&
    !url.pathname.startsWith('/app/api/')
  )
}

export function matchAppImage({ url }) {
  return (
    url.origin === self.location.origin &&
    (url.pathname.startsWith('/app/_next/') || url.pathname.startsWith('/app/icons/')) &&
    /\.(png|jpg|jpeg|svg|gif|webp|woff2?)$/.test(url.pathname)
  )
}
