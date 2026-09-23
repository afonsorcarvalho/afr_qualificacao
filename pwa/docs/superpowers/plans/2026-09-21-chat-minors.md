# Plano — dois minors parqueados do chat de agendamento

Contexto: o chat de agendamento do PWA (drawer da tela de agenda) foi entregue
em 2026-09-20/21. O review final parqueou dois minors, registrados em
`pwa/TODO.md` na seção "Chat de agendamento — limpeza pós-entrega". Este plano
fecha os dois. São edições pequenas e independentes, no mesmo módulo — uma
tarefa só, em lote.

Spec de origem: `docs/superpowers/specs/2026-09-20-chat-agendamento-design.md`.

## Global Constraints

- **Mudança só de front: NÃO bumpar `__manifest__.py`.** A versão do PWA vive
  no `package.json`. Política registrada no `TODO.md`.
- Texto de UI e mensagens para o modelo em **pt-BR**; código e identificadores
  em inglês quando já for o padrão do arquivo (aqui o padrão é pt-BR, seguir o
  arquivo).
- A suíte roda com `npm test` (vitest). Baseline: `pwa/docs/BASELINE.md` — sem
  falhas ambientais, qualquer falha é regressão.
- `npx tsc --noEmit` precisa continuar limpo. **Exceção pré-existente**, não
  introduzida aqui e fora de escopo: `.next/types/app/api/chat/route.ts`
  reclama dos helpers exportados por `app/api/chat/route.ts`. Ignorar essa e
  só essa.
- Não rodar `npm run build` — o dev server de :3010 está de pé e os dois usam
  `.next/`.

## Task 1 — os dois minors, em lote

### Minor A — botão Cancelar do card de proposta sem `disabled`

**Arquivo:** `app/tecnico/qualificacao/agenda/_ChatAgenda.tsx`

O card de confirmação de escrita tem dois botões. `Confirmar` já traz
`disabled={ocupado}`; `Cancelar`, não:

```tsx
<button
  type="button"
  className="min-h-[44px] flex-1 rounded-md border border-border px-3"
  onClick={cancelar}
>
  Cancelar
</button>
```

**O defeito:** com a escrita em voo (`ocupado === true`), o Cancelar continua
clicável. Um duplo clique em menos de um frame (~16 ms) dispara `cancelar`
enquanto `confirmar` ainda não voltou — duplicando a resposta `tool` no
transcript e travando a conversa (a API rejeita a próxima chamada quando um
`tool_call_id` aparece respondido duas vezes).

**A mudança:** acrescentar `disabled={ocupado}` ao botão Cancelar e a mesma
classe de estado visual que o Confirmar já usa (`disabled:opacity-50`), para
o botão não ficar clicável-em-aparência e inerte-de-fato.

**Teste (novo), em `app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx`:**
com uma proposta pendente e a confirmação em voo (`ocupado`), o botão
`Cancelar` está desabilitado. O teste precisa falhar antes da mudança — se
passar contra o código atual, ele não está testando o que diz. Os testes de
Cancelar que já existem (`Cancelar repara o transcript`, `Cancelar não executa
a escrita`, linhas ~259/~302) clicam em Cancelar com a conversa ociosa e devem
continuar passando sem edição; se algum quebrar, é sinal de que `ocupado`
estava verdadeiro num caminho ocioso — investigar antes de mexer no teste.

### Minor B — erro de formato em lista de ids manda reconsultar à toa

**Arquivo:** `lib/chat/machine.ts`, função `validar`, laço sobre
`CAMPOS_DE_LISTA_DE_ID` (`instrument_ids`, `equipment_ids`).

Hoje o ramo de formato inválido diz:

```ts
if (!Number.isInteger(n)) {
  return `O ${rotulo} "${JSON.stringify(item)}" não é um id inteiro válido. Chame ${ferramenta} primeiro.`
}
```

**O defeito:** "não é um id inteiro" e "id que nunca apareceu" são problemas
diferentes e só um deles se resolve consultando de novo. Mandar o modelo
chamar `listar_instrumentos` porque ele escreveu `"abc"` ou `1.5` gasta uma
volta inteira de cota para devolver uma lista que ele já tinha. O ramo escalar
logo acima (`CAMPOS_DE_ID`) já faz a distinção certa, e o comentário dele
explica exatamente este raciocínio — esta é a mesma regra, aplicada ao ramo de
lista que ficou para trás.

**A mudança:** no ramo `!Number.isInteger`, tirar o "Chame X primeiro" e
manter só a descrição do erro de formato, no mesmo espírito da mensagem
escalar. O ramo seguinte (`!idsVistos.has(n)`) **continua** mandando chamar a
ferramenta — ali reconsultar é o conserto certo. Acrescentar um comentário
curto apontando a assimetria deliberada, como o ramo escalar já faz.

**Teste, em `lib/chat/machine.test.ts`:** o teste da linha ~248 já casa
`/não é um id inteiro válido/i` e continua válido. Acrescentar a asserção que
falta: a mensagem de formato inválido **não** contém "Chame" — é isso que
distingue as duas mensagens e é o que a mudança garante. Confirmar que o caso
de id-não-visto (que deve seguir mandando chamar a ferramenta) tem cobertura;
se não tiver, acrescentar.

### Verificação da task

1. `npx vitest run lib/chat/machine.test.ts app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx`
2. `npm test` (suíte inteira, comparar com `docs/BASELINE.md`)
3. `npx tsc --noEmit` (ignorando só a exceção pré-existente listada acima)

### Fora de escopo

- O bug da janela de "semana que vem" em `lib/chat/prompt.ts` — é o próximo
  item, tem plano próprio.
- O bloco "VISITAS NA JANELA ABERTA NA TELA" sem datas (achado da validação
  empírica) — item separado no `TODO.md`.
- Qualquer coisa em `addons/afr_qualificacao_agendamento` (backend).
