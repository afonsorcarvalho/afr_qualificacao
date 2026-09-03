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
