/**
 * Regra de destino pós-login, compartilhada entre `app/login/page.tsx` e
 * `middleware.ts`.
 *
 * Mora aqui, em `lib/`, e não dentro da página de login: o `middleware.ts`
 * vai precisar da MESMA regra no dia em que ecoar `next` de volta (hoje ele
 * só grava o parâmetro), e duas cópias de uma regra de segurança divergem —
 * uma delas vira o buraco.
 */

const DESTINO_PADRAO = '/tecnico/qualificacao'

/**
 * Só caminho interno vale. `?next=https://evil.example` transformaria o
 * login num open redirect: o técnico autentica e o app o joga para fora, num
 * site que pode imitar a tela de login.
 *
 * Três formas de burlar "começa com barra" e por que cada uma é recusada:
 *   - `//evil.example`     — barra dupla é URL absoluta (protocolo relativo)
 *     para o navegador, não caminho relativo, mesmo começando com `/`.
 *   - `/\evil.example`     — alguns navegadores normalizam `\` para `/` ao
 *     resolver a URL, virando `//evil.example` na prática.
 *   - `https:/evil`        — não começa com `/`, já cai na primeira checagem.
 *
 * Qualquer `\` no destino é recusado, não só no começo, pelo mesmo motivo da
 * normalização de navegador.
 */
export function destinoSeguro(next: string | null): string {
  if (!next) return DESTINO_PADRAO
  if (!next.startsWith('/') || next.startsWith('//')) return DESTINO_PADRAO
  if (next.includes('\\')) return DESTINO_PADRAO
  return next
}
