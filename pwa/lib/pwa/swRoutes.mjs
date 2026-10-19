// Funções de match do runtimeCaching do service worker. São serializadas
// (toString) para dentro do public/sw.js: precisam ser AUTOCONTIDAS — sem
// closures, sem constantes externas, sem imports. Por isso a regex de rotas
// é repetida dentro de cada função.
//
// Rotas do app: /cliente, /levantamento, /tecnico (e subpaths) e /login.
// Rota nova do app deve ser adicionada AQUI e no Apache (proxy).

export function matchPageNavigation({ request, url }) {
  return (
    request.mode === 'navigate' &&
    /^\/(cliente|levantamento|tecnico|login)(\/|$)/.test(url.pathname)
  )
}

export function matchRscRequest({ request, url }) {
  return (
    request.headers.get('RSC') === '1' &&
    /^\/(cliente|levantamento|tecnico|login)(\/|$)/.test(url.pathname)
  )
}

export function matchAppImage({ url }) {
  return (
    url.origin === self.location.origin &&
    /^\/(_next|icons)\//.test(url.pathname) &&
    /\.(png|jpg|jpeg|svg|gif|webp|woff2?)$/.test(url.pathname)
  )
}
