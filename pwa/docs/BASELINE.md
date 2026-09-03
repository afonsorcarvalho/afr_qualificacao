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

Qualquer falha em execução futura é regressão: esta baseline não tem
falhas ambientais. As 3 falhas de rede da suíte antiga do `frontend_odoo`
(`odoo-connection`, `reports`, `pdf-viewer`) pertenciam a módulos que não
migraram.
