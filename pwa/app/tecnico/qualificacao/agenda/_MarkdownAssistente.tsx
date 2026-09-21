'use client'
import ReactMarkdown, { type Components } from 'react-markdown'

// Lista branca do que o modelo realmente usa nas respostas de agendamento:
// parágrafo, quebra de linha, negrito, itálico, lista com marcador/numerada,
// item de lista, código inline e bloco de código. Link (`a`) e imagem
// (`img`) ficam de fora de propósito — ver comentário de segurança abaixo.
const ELEMENTOS_PERMITIDOS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre']

// Estilo das bolhas do chat usa `text-sm` e tema escuro (ver `_ChatAgenda.tsx`);
// o reset do Tailwind (preflight) zera `list-style`/`margin` de `ul`/`ol`, por
// isso o recuo e o marcador são repostos aqui à mão.
const componentesEstilo: Components = {
  p: ({ children }) => <p className="[&:not(:first-child)]:mt-2">{children}</p>,
  ul: ({ children }) => <ul className="ml-4 list-disc space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="ml-4 list-decimal space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  code: ({ children }) => (
    <code className="rounded bg-background/60 px-1 py-0.5 font-mono text-[0.85em]">
      {children}
    </code>
  ),
  // Um bloco de código (```) vira `<pre><code>...</code></pre>` — o mesmo
  // componente `code` acima também é usado AQUI DENTRO. Sem neutralizar o
  // fundo/padding/arredondamento do `code` aninhado, o bloco duplica o
  // "quadradinho" do inline dentro do próprio fundo do bloco. `v10` do
  // `react-markdown` tirou a prop `inline` que distinguia os dois — a
  // seletor `[&_code]:...` resolve isso via CSS, sem precisar detectar
  // contexto em JS (e funciona mesmo em bloco sem linguagem anotada, que
  // não ganha `className` nenhuma do `code`).
  pre: ({ children }) => (
    <pre className="mt-1 overflow-x-auto rounded bg-background/60 p-2 font-mono text-[0.85em] [&_code]:rounded-none [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
}

/**
 * Renderiza o texto do ASSISTENTE como markdown. Nunca usar para a bolha do
 * gestor nem para bolhas de erro — essas são montadas pelo nosso próprio
 * código (não pelo modelo) e ficam em texto puro de propósito, inclusive
 * pra não abrir formatação indesejada no card de confirmação de escrita.
 *
 * Segurança (inegociável — spec da tarefa):
 * - SEM `rehype-raw` (nem qualquer plugin equivalente): HTML cru que o
 *   modelo mande (`<script>`, `<b>`...) nunca é interpretado, só aparece
 *   escapado como texto — é o comportamento padrão do `react-markdown`
 *   quando `rehype-raw` não está no pipeline. Verificado empiricamente:
 *   `<script>alert(1)</script>` vira o texto literal `<script>alert(1)...`,
 *   sem nenhum nó `<script>` no DOM.
 * - `allowedElements` fecha a lista a só o que está em `ELEMENTOS_PERMITIDOS`
 *   acima — nada de link ou imagem, mesmo que o modelo tente.
 * - `unwrapDisallowed`: um elemento fora da lista não some com o conteúdo
 *   junto — vira texto puro. É isto que cumpre "link aparece como texto,
 *   não como âncora": o `<a>` que o parser monta é descartado, mas o texto
 *   do link (`clique aqui`) sobra na tela.
 */
export function MarkdownAssistente({ texto }: { texto: string }) {
  return (
    <ReactMarkdown allowedElements={ELEMENTOS_PERMITIDOS} unwrapDisallowed components={componentesEstilo}>
      {texto}
    </ReactMarkdown>
  )
}
