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
 * Origem opaca só para ancorar o parse de `next` como URL relativa e ler o
 * `origin` resultante — nunca é usada para navegar de verdade.
 */
const ORIGEM_INTERNA = 'http://interno.invalid'

/**
 * Só caminho interno vale. `?next=https://evil.example` transformaria o
 * login num open redirect: o técnico autentica e o app o joga para fora, num
 * site que pode imitar a tela de login.
 *
 * PRIMEIRA VERSÃO desta função checava a string crua (`startsWith('/')`,
 * `startsWith('//')`, `includes('\\')`) — e foi derrubada em revisão
 * adversarial: `/\t/evil.example` passa por três checagens de prefixo/`\`
 * intacto (é tab, não contrabarra), mas quem CONSOME o valor devolvido
 * (`router.replace` do Next, via `new URL(href, location.href)` dentro do
 * app-router) segue o parser WHATWG, que remove todo tab/LF/CR da string
 * ANTES de resolver — `/\t/evil.example` colapsa para `//evil.example`,
 * URL absoluta. Checar prefixo contra uma string que outra camada vai
 * canonicalizar é sempre alcançável por uma variante nova (a próxima pode
 * ser percent-encoding, `..`, ou algo ainda não catalogado).
 *
 * A correção: delegar a canonicalização ao MESMO parser que o consumidor
 * usa. `new URL(next, ORIGEM_INTERNA)` aplica a normalização completa do
 * WHATWG (tab/LF/CR removidos, barras colapsadas, `..` resolvido) e o
 * resultado é comparado por `origin`, não por prefixo de string — se `next`
 * conseguiu mudar de origem (esquema absoluto, `//host`, `\` normalizado
 * para `//`, tab/LF/CR virando `//`), o `origin` não bate com
 * `ORIGEM_INTERNA` e o destino é recusado. `pathname + search + hash` do
 * resultado (não o `next` original) é o que volta — por isso
 * `/tecnico/../../evil` normaliza para `/evil` em vez de vazar literal, e
 * um `next` malformado (`new URL` lança) cai no mesmo padrão via `catch`.
 */
export function destinoSeguro(next: string | null): string {
  if (!next) return DESTINO_PADRAO
  try {
    const url = new URL(next, ORIGEM_INTERNA)
    if (url.origin !== ORIGEM_INTERNA) return DESTINO_PADRAO
    // A checagem de origem acima só protege porque devolvemos só
    // pathname+search+hash: um refactor que trocasse esta linha por
    // `url.href` reabriria o open redirect, já que `url.origin` bateria
    // com `ORIGEM_INTERNA` (sentinela opaca) e não com um host real.
    return url.pathname + url.search + url.hash
  } catch {
    return DESTINO_PADRAO
  }
}
