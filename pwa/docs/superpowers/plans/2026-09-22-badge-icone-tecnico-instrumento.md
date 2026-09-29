# Plano — badge ícone+cor de técnico/instrumento nas views lista/semana

## Contexto

Hoje as views Lista e Semana da agenda de visitas (`app/tecnico/qualificacao/agenda/`)
mostram técnico e instrumento como texto puro, sem cor — diferente do modo Mês
(`_VistaMes.tsx`), que já desenha um marcador colorido por recurso (bolinha para
técnico, triângulo para instrumento), usando `corDoTecnico`/`corDoInstrumento`
de `mes.ts`. O usuário pediu para levar essa identificação visual (cor por
recurso) também para Lista/Semana, mas trocando o marcador geométrico por um
ícone: `User` (lucide-react) para técnico, `Wrench` (lucide-react) para
instrumento — mesma cor já usada no resto da agenda para aquele id.

Superfícies afetadas:
- **Semana → painel de recursos** (`_PainelRecursos.tsx`): linhas de técnico e
  de instrumento, hoje sem nenhuma cor.
- **Lista e Semana → card da visita** (`_components/VisitaCard.tsx`): linha
  "Técnico: {nome}" e linha "Instr.: {lista}", hoje texto puro.

Não é escopo: equipamento (`Equip.:` no card) continua texto puro — não foi
pedido, e `fa-wrench`/chave-de-boca já é usado para EQUIPAMENTO no board OWL
de `afr_qualificacao_agendamento` (arquivo Python/OWL irmão, fora deste
submodule/PWA). Nesta base (lucide-react, TypeScript) não há esse conflito de
nome, mas mantenha o escopo: só técnico e instrumento ganham ícone+cor aqui.

## Global Constraints

- **Não alterar a assinatura nem o nome do export `horaOdoo`** em
  `_components/VisitaCard.tsx` — `lib/chat/tools.ts` (fora do escopo deste
  plano, mantido por outra sessão em paralelo) importa esse símbolo. Pode
  adicionar código ao arquivo livremente; só não mexer nesse export.
- Reutilizar `corDoTecnico(id, color)` e `corDoInstrumento(id, color)` de
  `./mes.ts` (ou `../agenda/mes` dependendo do arquivo) — não reimplementar
  paleta/lógica de cor. `color` ausente/`undefined` já cai automaticamente no
  fallback determinístico por id (`PALETA[id % 12]`); não é preciso paperar
  esse caso.
- Ícones: `User` e `Wrench` de `lucide-react` (já é dependência do projeto).
  Tamanho `h-4 w-4 shrink-0` nas linhas do painel de recursos (mesmo padrão
  dos ícones existentes em `_PainelRecursos.tsx`/`VisitaCard.tsx`), `h-3.5
  w-3.5 shrink-0` nos chips menores do card (mesmo tamanho do `AlertTriangle`
  existente em `VisitaCard.tsx`). Sempre `aria-hidden` no ícone — o nome
  textual ao lado já carrega a informação para leitor de tela (mesmo
  princípio do aviso de calibração vencida em `_PainelRecursos.tsx`: cor
  sozinha nunca é o único portador).
- Cor aplicada via `style={{ color: <hex> }}` (as funções `corDoTecnico`/
  `corDoInstrumento` devolvem uma string hex do `PALETA`, não uma classe
  Tailwind — é o mesmo padrão usado em `_VistaMes.tsx` para os triângulos).
- Rode `npx vitest run` e `npx tsc --noEmit` (dentro de
  `addons/afr_qualificacao/pwa/`) antes de reportar DONE. `npm run lint`
  (`next lint`) também deve passar limpo no diff.
- **Não reinicie nem derrube o devserver de `:3010`** (rodando nesta mesma
  pasta, sessão `chat-agenda` de outra pessoa). Editar os arquivos é seguro —
  o Next.js recompila sozinho; só não mate/reinicie o processo.
- Não toque em `lib/chat/*` nem em `_ChatAgenda.tsx` — fora do escopo, outra
  sessão trabalha lá em paralelo.
- Comentários no estilo do arquivo (curtos, só quando o "porquê" não é óbvio)
  — este código-base já documenta bastante o raciocínio de a11y/estabilidade
  de cor; siga o padrão, não repita o óbvio.

## Task 1 — Painel de recursos da Semana: ícone+cor em técnico e instrumento

**Arquivos:** `app/tecnico/qualificacao/agenda/carga.ts`,
`app/tecnico/qualificacao/agenda/_PainelRecursos.tsx`

### 1a. `carga.ts` — propagar `color` até `CargaTecnico` e `UsoInstrumento`

Hoje `cargaPorTecnico`/`usoPorInstrumento` recebem `Opcao[]`/`InstrumentoOpcao[]`
(que já têm `color?: number`, vindo do roster) mas não copiam esse campo para
os tipos de retorno `CargaTecnico`/`UsoInstrumento`. `rosterTecnicos` já faz
esse mesmo tipo de propagação (guarda o `Opcao` inteiro) — siga o padrão.

```ts
export interface CargaTecnico {
  id: number
  name: string
  horas: number
  color?: number
}
```

Em `cargaPorTecnico`, no `.map`, adicione `color: t.color,` ao objeto
retornado (junto de `id`/`name`/`horas`).

```ts
export interface UsoInstrumento {
  id: number
  name: string
  vencido: boolean
  usos: UsoDeVisita[]
  color?: number
}
```

Em `usoPorInstrumento`, no `.map`, adicione `color: i.color,` ao objeto
retornado.

Não mude a assinatura de nenhuma das duas funções — só o shape do retorno.

### 1b. `_PainelRecursos.tsx` — renderizar ícone colorido

Import: `import { User, Wrench, AlertTriangle } from 'lucide-react'` (troque
o import existente de `AlertTriangle` por essa linha combinada) e
`import { corDoTecnico, corDoInstrumento } from './mes'`.

Na linha do técnico (hoje só `<span className="w-28 shrink-0 truncate">{t.name}</span>`),
anteceda com o ícone:

```tsx
<User
  className="h-4 w-4 shrink-0"
  style={{ color: corDoTecnico(t.id, t.color) }}
  aria-hidden
/>
<span className="w-28 shrink-0 truncate">{t.name}</span>
```

Ajuste o `className` do `<span>` de nome se necessário para o ícone não
quebrar o alinhamento com `gap-3` já existente no `LINHA` — confira
visualmente (ou pelo teste) que o texto não estoura a largura fixa `w-28`.

Na linha do instrumento (hoje `<span className="w-20 shrink-0 truncate">{i.name}</span>`),
mesmo padrão com `Wrench` e `corDoInstrumento(i.id, i.color)`.

### Testes (Task 1)

Em `app/tecnico/qualificacao/__tests__/carga.test.ts`: nos blocos
`describe('cargaPorTecnico', ...)` e `describe('usoPorInstrumento', ...)`
existentes, adicione um `it` cobrindo que `color` do roster/catálogo
sobrevive no retorno (mesmo padrão do teste já existente
"preserva o color do roster oficial na união" em `rosterTecnicos`, ~linha 173).

Em `app/tecnico/qualificacao/__tests__/PainelSemana.test.tsx`: adicione
asserção de que a linha do técnico e a do instrumento renderizam um ícone
(`svg` do lucide fica no DOM; busque por `container.querySelector('svg')`
dentro da linha, ou por `aria-hidden` — veja o padrão já usado no arquivo
para o ícone de "calibração vencida") com o `style.color` esperado batendo
`corDoTecnico`/`corDoInstrumento` chamado com os mesmos ids/colors do fixture
do teste.

## Task 2 — Card da visita (Lista e Semana): ícone+cor em técnico e instrumento

**Arquivos:** `app/tecnico/qualificacao/_components/VisitaCard.tsx`,
`app/tecnico/qualificacao/agenda/page.tsx`

### 2a. `VisitaCard.tsx` — props novas e render

O card só tem o `VisitaAgenda` (que carrega `tecnico_id`/`tecnico_name` e
`instrument_ids`/`instrument_list`, arrays paralelos na mesma ordem — vem de
`os_visita.py`, `instrument_ids.mapped(...)` preserva ordem do recordset) —
não a cor configurada no Odoo por id. Essa cor mora no roster/catálogo que já
existe em `page.tsx` (`roster`, `opcoesInstrumento`). Passe dois `Map`
opcionais como prop nova:

```ts
tecnicoColorPorId?: Map<number, number | undefined>
instrumentoColorPorId?: Map<number, number | undefined>
```

Adicione as duas props à assinatura de `VisitaCard` (mantendo as existentes:
`visita`, `onSelect`, `onAjustar`, `emAjuste`) e repasse para `Corpo`
(`Corpo` também precisa recebê-las).

Import: `import { User, Wrench, Lock, AlertTriangle, Clock, MapPin } from 'lucide-react'`
e `import { corDoTecnico, corDoInstrumento } from '../agenda/mes'`.

Troque a linha do técnico:

```tsx
{!visita.is_mine && (
  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
    <User
      className="h-3.5 w-3.5 shrink-0"
      style={{ color: corDoTecnico(visita.tecnico_id, tecnicoColorPorId?.get(visita.tecnico_id === false ? -1 : visita.tecnico_id)) }}
      aria-hidden
    />
    {visita.tecnico_name}
  </p>
)}
```

(`visita.tecnico_id === false` nunca bate uma chave real do `Map`, `-1` é só
para o `.get` não reclamar de tipo — resultado é sempre `undefined`, que é o
comportamento certo: `corDoTecnico(false, ...)` já devolve o cinza neutro
independente do `color`.)

Troque o bloco de instrumento — hoje uma string única `.join(', ')`, precisa
virar uma linha por instrumento porque cada um pode ter cor própria (mesmo
motivo documentado em `_PainelRecursos.tsx` para não concatenar usos: cor por
item exige elemento por item):

```tsx
{visita.instrument_list.length > 0 && (
  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
    {visita.instrument_list.map((nome, idx) => {
      const id = visita.instrument_ids[idx]
      return (
        <span key={id ?? nome} className="flex min-w-0 items-center gap-1">
          <Wrench
            className="h-3.5 w-3.5 shrink-0"
            style={{ color: corDoInstrumento(id, instrumentoColorPorId?.get(id)) }}
            aria-hidden
          />
          <span className="truncate">{nome}</span>
        </span>
      )
    })}
  </div>
)}
```

Remova o comentário acima do bloco de equipamento que hoje justifica "não
usar ícone aqui" citando os ícones fixos do card (`/* Rótulo curto (não
ícone): ... */`, linhas ~31-34) — ele ficou desatualizado (o card passa a ter
`User`/`Wrench` com sentido claro por linha; o comentário original defendia
exatamente o oposto do que este plano pede). Pode substituir por uma nota
curta, se fizer sentido, mas não é obrigatório — só não deixe o comentário
velho contradizendo o código novo.

Não mude a linha do equipamento (`Equip.: ...`) — fica texto puro, fora do
escopo.

### 2b. `page.tsx` — wiring dos dois `Map`

`page.tsx` já computa `roster` (técnicos, com `color`) e
`opcoesInstrumento`/`instrumentos.data ?? []` (instrumentos, com `color`).
Adicione dois `useMemo` perto de onde `roster`/`opcoesInstrumento` são
definidos:

```ts
const tecnicoColorPorId = useMemo(
  () => new Map(roster.map((t) => [t.id, t.color])),
  [roster],
)
const instrumentoColorPorId = useMemo(
  () => new Map(opcoesInstrumento.map((o) => [o.id, o.color])),
  [opcoesInstrumento],
)
```

Passe `tecnicoColorPorId={tecnicoColorPorId}` e
`instrumentoColorPorId={instrumentoColorPorId}` nos DOIS pontos onde
`<VisitaCard ...>` é renderizado (modo Lista, dentro do `grupos.map`; modo
Semana, dentro do `doDia.map`).

### Testes (Task 2)

Em `app/tecnico/qualificacao/__tests__/AgendaLista.test.tsx`: o teste
"mostra o instrumento junto do equipamento quando houver" (linha ~46) usa
`instrument_list: ['Termômetro TH-02']` mas `instrument_ids: []` no fixture
padrão (`visita()` helper, linha ~15) — ajuste esse `it` para também passar
`instrument_ids: [77]` (ou outro id fixo) e assira que o texto ainda aparece
(`screen.getByText(/Termômetro TH-02/)`, sem mais o prefixo `Instr\.: `
porque ele foi removido) e que existe um ícone (svg) na linha. Adicione
também um `it` novo cobrindo o ícone do técnico quando `is_mine: false` (o
fixture padrão é `is_mine: true`, que esconde a linha — use
`visita({ is_mine: false, tecnico_name: 'Ariel Neves' })`) — assira presença
do nome e de um `svg` na mesma linha.

Não precisa cobrir `tecnicoColorPorId`/`instrumentoColorPorId` com valor real
nesses testes de `VisitaCard` isolado — testar que o fallback automático (sem
os Maps, como os testes já chamam `<VisitaCard visita={...} onSelect={...} />`)
renderiza cor via `corDoTecnico`/`corDoInstrumento` já cobre a função pura
(coberta em `mes.test.ts`); aqui o que importa é que o ícone aparece e que o
`style.color` bate o que `corDoTecnico`/`corDoInstrumento` devolveriam para
aquele id sem `color` configurado.

## Task 3 — Trocar ícone outline por preenchido (Painel Semana + Card)

**Adicionada depois do Task 1/2, decisão do usuário via comparativo visual**
(artifact de legibilidade): o traço fino do lucide (`stroke-width` 2 sobre
`viewBox` 24) perde definição abaixo de ~12px. Nos 14-16px do Painel/Card o
ícone preenchido (silhueta sólida) lê melhor — decisão confirmada. **Fora do
escopo desta task:** a grade e a legenda do modo Mês (`_GradeMes.tsx`,
`_VistaMes.tsx`, marcas de 6-8px) continuam com bolinha/triângulo — nesse
tamanho nem outline nem preenchido leem bem, e na legenda o par
preenchido/contorno já codifica estado ligado/desligado (não é só estilo).
Não toque em `_GradeMes.tsx` nem `_VistaMes.tsx` nesta task.

**Arquivos:** novo `app/tecnico/qualificacao/_components/IconesRecurso.tsx`;
edições em `app/tecnico/qualificacao/agenda/_PainelRecursos.tsx` e
`app/tecnico/qualificacao/_components/VisitaCard.tsx`.

### 3a. Novo arquivo `IconesRecurso.tsx`

`lucide-react` não tem variante preenchida (é outline-only) — trocar
`fill="currentColor"` direto num `<User>`/`<Wrench>` do lucide produz uma
forma quebrada (os paths deles são abertos, pensados pra `stroke`, não pra
preenchimento — fecham com uma linha reta esquisita se você força `fill`).
Por isso: dois componentes locais com paths fechados de verdade (silhueta),
testados visualmente no comparativo. Props livres via spread — uso quase
idêntico ao `<User>`/`<Wrench>` que eles substituem (`className`,
`style={{ color }}`, `aria-hidden` ou `role`/`aria-label`, o que o call site
já usa).

```tsx
import type { SVGProps } from 'react'

/**
 * Silhueta preenchida de pessoa — substitui `User` do lucide (outline) nos
 * tamanhos 14-16px do Painel/Card, onde o traço fino do lucide perde
 * definição. `fill="currentColor"` lê a cor do `style.color` do call site,
 * mesmo mecanismo do `stroke="currentColor"` que ele substitui.
 */
export function IconeTecnico(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M12 12q-1.65 0-2.825-1.175Q8 9.65 8 8t1.175-2.825Q10.35 4 12 4t2.825 1.175Q16 6.35 16 8t-1.175 2.825Q13.65 12 12 12Zm-8 8v-2.8q0-.85.438-1.563.437-.712 1.162-1.087 1.55-.775 3.15-1.163Q10.35 13 12 13t3.25.387q1.6.388 3.15 1.163.725.375 1.163 1.087Q20 16.35 20 17.2V20Z" />
    </svg>
  )
}

/** Silhueta preenchida de chave de boca — substitui `Wrench` do lucide, mesmo raciocínio de `IconeTecnico`. */
export function IconeInstrumento(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z" />
    </svg>
  )
}
```

### 3b. `_PainelRecursos.tsx`

Troque o import `import { User, Wrench, AlertTriangle } from 'lucide-react'`
por `import { AlertTriangle } from 'lucide-react'` +
`import { IconeTecnico, IconeInstrumento } from '../_components/IconesRecurso'`.
Troque `<User ...>` → `<IconeTecnico ...>` e `<Wrench ...>` → `<IconeInstrumento ...>`,
mesmas props (`className`, `style`, `aria-hidden`) que o Task 1 já deixou.

### 3c. `VisitaCard.tsx`

Mesma troca: import de `IconeTecnico`/`IconeInstrumento` de
`'../_components/IconesRecurso'` (mesmo diretório), `User`/`Wrench` saem do
import de `lucide-react` (mantenha `Lock`/`AlertTriangle`/`Clock`/`MapPin`
que continuam lucide). Troque `<User ...>`/`<Wrench ...>` pelos novos
componentes, mantendo as props exatas que a Task 2 (+ fix round 1) já
deixou — inclusive `role="img" aria-label="Técnico"`/`"Instrumento"` se essa
já foi a forma final depois do fix round.

### Testes (Task 3)

Os testes de Task 1/2 (`PainelSemana.test.tsx`, `AgendaLista.test.tsx`)
já buscam por `svg` genérico e checam `style.color` — não precisam de
mudança estrutural, só confirme que ainda passam com o novo componente
(o `<svg>` continua sendo um `<svg>`, só o conteúdo interno muda de
`<path stroke=...>` pra `<path fill=...>`). Se algum teste tiver asserção
que dependa de atributo específico do ícone lucide (ex.: `data-lucide` ou
contagem de `<path>` filhos), ajuste pra não depender de detalhe interno do
ícone — só do `style.color` e da presença do `svg`.

## Ordem e independência

Task 1 e Task 2 tocam arquivos disjuntos (`carga.ts`+`_PainelRecursos.tsx` vs
`VisitaCard.tsx`+`page.tsx`) e usam a mesma dupla de funções puras
(`corDoTecnico`/`corDoInstrumento`) sem modificá-las — podem rodar em
qualquer ordem. Rode Task 1 primeiro (mais simples, menor superfície) só para
o revisor pegar prática no padrão do PR antes do Task 2, que é maior.

Task 3 depende de Task 1 E Task 2 estarem FECHADAS (review clean ou parked) —
toca os mesmos dois arquivos que elas (`_PainelRecursos.tsx`, `VisitaCard.tsx`),
só que depois, trocando o ícone que elas introduziram. Nunca despachar Task 3
em paralelo com Task 1/2 nem com um fix round delas ainda aberto.

## Verificação final

- `npx vitest run` limpo (sem quebrar nenhum teste pré-existente).
- `npx tsc --noEmit` limpo.
- `npm run lint` limpo no diff.
- Leitura visual: se o devserver de `:3010` estiver de pé, abrir
  `/tecnico/qualificacao/agenda` (modo Lista e modo Semana) e conferir que os
  ícones aparecem com cor plausível (não preto/cinza para técnico/instrumento
  com cor configurada) — sem reiniciar o servidor.
