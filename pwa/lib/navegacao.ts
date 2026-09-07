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
 * Segunda âncora de parse, com host DIFERENTE da primeira de propósito — não
 * é redundância acidental, é o que faz a checagem de saída morder (ver o
 * bloco de `destinoSeguro`). Como `ORIGEM_INTERNA`: TLD inexistente,
 * nunca usada para navegar.
 */
const ORIGEM_TESTEMUNHA = 'https://outra.invalid'

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
 *
 * SEGUNDA E TERCEIRA VERSÕES (revisão final de 2026-09-06). Validar a
 * ENTRADA não basta: quem consome o retorno (`router.replace`) re-parseia a
 * string devolvida contra OUTRA base — a `location.href` real do app. E
 * `ORIGEM_INTERNA` é constante pública no código-fonte: o atacante a lê e a
 * nomeia. Sentinela não é segredo, e o desenho não pode depender de que
 * seja. Duas famílias de payload já saíram daí:
 *
 *   `//interno.invalid//evil.example`        -> `//evil.example`
 *   `http://interno.invalid//evil.example/x` -> `//evil.example/x`
 *   `http://interno.invalid/\evil.example`   -> `///evil.example`
 *   `.//interno.invalid`                     -> `//interno.invalid`
 *   `..//interno.invalid`                    -> `//interno.invalid`
 *   `/.//interno.invalid`                    -> `//interno.invalid`
 *
 * Em todos, o `origin` do PRIMEIRO parse é `ORIGEM_INTERNA` (o host é
 * consumido como autoridade, ou o `.` inicial faz o WHATWG tratar a string
 * como caminho relativo) e o `pathname` resolvido começa com `//` — que num
 * parse seguinte é autoridade de novo. Link de ataque, sem encoding nenhum:
 * `/login?next=.//interno.invalid`.
 *
 * A SEGUNDA VERSÃO tentou fechar isso re-parseando a saída contra
 * `ORIGEM_INTERNA` e chamou a regra de "ponto fixo sob re-parse", dizendo
 * que era mecanismo-independente e fechava a família inteira. **Estava
 * errado, e o erro é instrutivo o bastante para ficar escrito.** Re-parsear
 * contra a MESMA sentinela não testa estabilidade: uma saída que NOMEIA
 * essa sentinela (`//interno.invalid`) é ponto fixo daquela checagem
 * específica — e continua protocol-relative, logo muda de origem contra
 * qualquer OUTRA base, inclusive a real do app. A regra parecia geral e era
 * uma tautologia sobre a própria constante.
 *
 * A TERCEIRA VERSÃO usa DUAS defesas independentes. Esta função já falhou
 * três vezes na mesma família; redundância aqui é barata, e nenhuma das duas
 * deve ser "simplificada" para fora:
 *
 * 1. **Segunda base testemunha, com host diferente de propósito.** O
 *    argumento que sustenta isso, e que precisa sobreviver a quem for
 *    encurtar o código: *a saída pode nomear no máximo UM host, então uma
 *    segunda base com host distinto sempre pega a saída que nomeia a
 *    primeira.* `//interno.invalid` é ponto fixo de `ORIGEM_INTERNA` mas
 *    resolve para `https://interno.invalid` contra `ORIGEM_TESTEMUNHA` — e
 *    vice-versa. Não existe string que nomeie as duas ao mesmo tempo.
 * 2. **Invariante explícita de FORMA:** a saída começa com exatamente uma
 *    barra (`/^\/(?!\/)/`). É a mesma propriedade dita de um jeito que um
 *    humano confere lendo, sem simular parser na cabeça — e é a defesa que
 *    continua valendo se algum dia o WHATWG mudar de comportamento.
 *
 * ⚠️ `ORIGEM_INTERNA` e `ORIGEM_TESTEMUNHA` TÊM que continuar em TLDs
 * inexistentes (`.invalid`, reservado pela RFC 2606) e diferentes entre si.
 * Trocar `interno.invalid` por `localhost` ou pela origem real do app
 * converteria isto num open redirect controlado pelo atacante — ele nomeia
 * a sentinela, a saída vira `//host-real` e o navegador vai para um host que
 * EXISTE — e os testes continuariam verdes, porque comparam com o destino
 * padrão. Elas são âncoras de parse, nunca destinos.
 *
 * Lição das três rodadas, para quem for mexer: **não confie em raciocínio
 * sobre esta função sem rodar payload contra ela.** As três versões vieram
 * com um argumento que soava geral, e duas estavam erradas. O que pega o
 * erro é o teste com base de app REALISTA (`https://pwa.real.app/login`) —
 * ver `LoginRedirect.test.tsx`; comparar a saída com `DESTINO_PADRAO`, que é
 * o que todos os testes faziam, não podia ter pego nenhuma destas.
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
    const destino = url.pathname + url.search + url.hash
    // Defesa 1a e 1b — DUAS bases, hosts diferentes de propósito. Ver o
    // comentário acima: a saída pode nomear no máximo um host, então a base
    // testemunha sempre pega a saída que nomeia a interna (e vice-versa).
    // Reduzir isto a uma base só reabre `?next=.//interno.invalid`.
    if (new URL(destino, ORIGEM_INTERNA).origin !== ORIGEM_INTERNA) return DESTINO_PADRAO
    if (new URL(destino, ORIGEM_TESTEMUNHA).origin !== ORIGEM_TESTEMUNHA) return DESTINO_PADRAO
    // Defesa 2 — forma: exatamente uma barra inicial. Redundante com as duas
    // acima por construção, e é esse o ponto: é a única das três que um
    // humano confere de olho, sem simular o parser do WHATWG.
    if (!/^\/(?!\/)/.test(destino)) return DESTINO_PADRAO
    return destino
  } catch {
    return DESTINO_PADRAO
  }
}
