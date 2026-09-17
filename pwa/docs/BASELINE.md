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
