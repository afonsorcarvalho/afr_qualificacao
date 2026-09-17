# Baseline de testes — PWA Técnico

Medida em 2026-09-02, logo após a migração de `frontend_odoo@4cd26dd`
para `addons/afr_qualificacao/pwa/`.

| Métrica | Valor |
|---|---|
| Arquivos de teste | 11 |
| Testes | 39 pass / 0 skip / 0 fail |
| Comando | `npm test` (vitest run) |
| `npx tsc --noEmit` | limpo |
| `npm run build` | verde |

Esta é uma execução única e verde — não estabelece ausência de flakiness,
só o estado no momento da medição. Ainda assim, qualquer falha em execução
futura deve ser tratada como regressão a investigar, não como ruído
ambiental conhecido: nenhuma falha ambiental foi identificada nesta
baseline. As 3 falhas de rede da suíte antiga do `frontend_odoo`
(`odoo-connection`, `reports`, `pdf-viewer`) pertenciam a módulos que não
migraram.

## Atualização — 2026-09-03 (fix/relatorio-dia-relogio-servidor)

Fix do acoplamento ao relógio do dispositivo no "relatório do dia"
(`action_get_daily_relatorio` no backend substitui a janela local
`dayWindowOdoo` calculada no front). `dayWindowOdoo` e seus 2 testes foram
removidos (código morto); `getOsDetail` ganhou 1 teste (split em 2: acha o
id / recebe `false`); `startDailyRelatorio` manteve 1 teste (assertiva
trocada: sem `day_start`/`day_end`). Delta líquido: -1 teste.

| Métrica | Valor |
|---|---|
| Arquivos de teste | 11 |
| Testes | 38 pass / 0 skip / 0 fail |
| Comando | `npm test` (vitest run) |
| `npx tsc --noEmit` | limpo |
| `npm run build` | não rodado (dev server em uso na porta 3010) |

## Atualização — 2026-09-03 (fix/relatorio-dia-relogio-servidor, fechamento)

Mesma classe de fix, agora no **fechamento** do relatório do dia:
`finalizeRelatorio` deixa de fazer `write` (com `data_fim`/
`signature_technician_date` carimbados no dispositivo) + `action_done`, e
passa a chamar só `action_finish_daily_relatorio` (servidor carimba tudo).
Os 2 testes de `describe('finalizeRelatorio', ...)` foram reescritos para o
novo contrato de 1 RPC só — contagem de testes não muda (2 → 2).

| Métrica | Valor |
|---|---|
| Arquivos de teste | 11 |
| Testes | 38 pass / 0 skip / 0 fail |
| Comando | `npm test` (vitest run) |
| `npx tsc --noEmit` | limpo |
| `npm run build` | não rodado (dev server em uso na porta 3010) |

## Atualização — 2026-09-16 (onda de correções do review final — agenda do técnico)

Fixes pontuais do review final da feature "Agenda" (`app/tecnico/qualificacao/agenda`):
`listTecnicoOptions()` passou a chamar `pwa_tecnico_options` (novo teste em
`lib/odoo/__tests__/agenda.test.ts`); `VisitaSheet` ganhou validação de
obrigatórios no modo criar antes do `mutateAsync` (novo teste em
`__tests__/VisitaSheet.test.tsx`). Delta: +2 testes; contagem de arquivos
não muda (39).

| Métrica | Valor |
|---|---|
| Arquivos de teste | 39 |
| Testes | 268 pass / 0 skip / 0 fail |
| Comando | `npx vitest run` |
| `npx tsc --noEmit` | **1 erro pré-existente, não introduzido por esta onda** — `.next/types/app/tecnico/qualificacao/agenda/page.ts` acusa `agruparPorDia`/`GrupoDia` como export não-padrão de um `page.tsx` (Next.js só aceita `default`/`metadata`/etc. como export nomeado de uma rota). Confirmado via `git stash` do arquivo: o erro persiste com o `page.tsx` original, sem a mudança desta onda (que só adicionou um `useState`). Fora do escopo desta onda corrigir (exigiria mover os helpers para um módulo à parte). |
| `npm run build` | não rodado (dev server ativo na porta 3012, sessão `agenda16`) |

## Atualização — 2026-09-17 (modo Semana e a máquina de seleção)

Task 7 do plano "agenda modo semana": monta `FaixaDias` + `PainelRecursos`
(Task 6) e `carga.ts` (Task 4) na rota `/agenda`, com o botão "Ajustar" do
`VisitaCard` como gatilho — um toque seleciona a visita, e a faixa de dias e
o painel de recursos passam a ser alvo do gesto (toque grava direto via
`pwa_visita_update`, sem endpoint novo).

Arquivos novos: `__tests__/ModoSemana.test.tsx` (7 testes). Modificados:
`lib/store/tecnicoSettings.ts` (`modoAgenda: 'lista' | 'semana'` persistido),
`_components/VisitaCard.tsx` (`onAjustar`/`emAjuste` opcionais, card some
embrulhado com o botão "Ajustar"/"Concluir"), `agenda/page.tsx` (monta o
modo Semana; janela encurta para 7 dias; filtro "Só minhas" desliga no modo
Semana; aria-label das setas de navegação passou de "Semanas
anteriores"/"Próximas semanas" para "Período anterior"/"Próximo período" —
a antiga ficava ambígua com o novo botão "Semana" e falava de uma janela
fixa de 14 dias que não existe mais no modo Semana).

O erro pré-existente do `tsc` documentado na atualização de 2026-09-16
(`agruparPorDia`/`GrupoDia` como export não-padrão de `page.tsx`) **não
reproduz mais** — os helpers já vivem em `janela.ts`/`carga.ts`, separados
da rota, e `tsc --noEmit` está limpo nesta rodada.

| Métrica | Valor |
|---|---|
| Arquivos de teste | 42 |
| Testes | 307 pass / 0 skip / 0 fail |
| Comando | `npx vitest run` |
| `npx tsc --noEmit` | limpo (erro pré-existente da atualização anterior não reproduz mais) |
| `npm run build` | não rodado (dev server em uso na porta 3010 — instrução explícita da task) |

Nota sobre a aritmética do brief: o passo 6 previa "281 + 12 (Task 6) + 7
(Task 7) = 300" testes finais. A baseline já estava em 300/41 arquivos
*antes* desta task (Tasks 4-6 já tinham fechado nesse número); com os 7
testes desta task, o total real é 307/42. Meta do brief já estava
atingida antes desta rodada; delta líquido desta task é +7 testes / +1
arquivo, como esperado.
