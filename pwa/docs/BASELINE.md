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
