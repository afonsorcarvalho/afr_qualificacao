# TODO — afr_qualificacao

## Em curso
- <nada>

## Pendente — outros
- F4 (16.0.3.3.0): padrões metrológicos M2M `engc.calibration.instruments` em qualif/collect.item (vincular qualificador cadastrado, rastreio cert. calibração + validade)
- F5 (16.0.3.4.0): reports completos + record rules technician + **flag `qualif_block_approval_without_collects`** em `res.config.settings` (default False = warning não-bloqueante atual; True = bloqueia `action_request_approval` se há collect.items required pending)
- F6 (16.0.3.5.0): relatório qualificação PDF/DOCX baseado em template Word com tags — render fields Odoo + anexar no final: fotos, PDFs, certificados qualificadores+padrões, tabelas de dados coletados, gráficos com curvas dos parâmetros (cliente recebe arquivo editável)
- Avaliar QR code de aceite digital (cliente assina no portal) — fase futura
- Avaliar multi-idioma (PT/EN) no relatório — se cliente internacional aparecer
- Avaliar capa com imagem de fundo / branding personalizado

## Feito
- 2026-05-17 — F3 batch 16.0.3.2.1: tracking procedimento + chatter (F3.1), reorder stat buttons Pendentes/Coletadas + Aprovadas só visível >0 (F3.2), tree collect.items sem editable=bottom (F3.3), `ir.module.category` Qualificações + grupos com category_id (F3.4), menu raiz com grupo Técnico (F3.5), wizard descrição width full via separator (F3.6), `name_get` cycle/malha (F3.7), labels "cobertos"→"realizados" + "Cobertura técnica"→"Execução" (F3.8), domain `cycle_ids`/`malha_ids` filtra por `qualificacao_id.os_id` (F3.9). Smoke test 117/117 PASS.
- 2026-05-17 — F3 (16.0.3.2.0): procedimento template + collect.items unificados + wizard apply_procedimento (commit bba0a0d)
- 2026-05-16 — Fontes PDF +30% (parágrafos e tabelas) p/ melhor legibilidade
- 2026-05-16 — Painel HTML `qualif_subtotals_html` no form SO (subtotal por equipamento)
- 2026-05-16 — Section lines por equipamento no SO (display_type='line_section' via wizard apply)
- 2026-05-16 — PDF escopo usa `line.name` (descrição Sales) em vez de nome produto
- 2026-05-16 — Fix views: notebook+page para text/html fields (memória `feedback_odoo_text_field_width`)
- 2026-05-16 — Fix views: group nesting para renderizar label (memória `feedback_odoo_group_label`)
- 2026-05-16 — Modelo `afr.qualificacao.standard` + M2M cycle_type/malha_type + 8 normas seed (ISO 17025, FDA 21 CFR Part 11, ANVISA RDC 658/665, ISPE GAMP 5, WHO TRS 961, VIM, ABNT NBR ISO/IEC 17025)
- 2026-05-16 — Template QWeb dedicado `quotation_template.xml` (capa+sumário+descritivo+escopo+normas+resumo+condições+aceite) inherit condicional `sale.report_saleorder_document`
- 2026-05-16 — Helpers sale.order: `has_qualif_lines`, `qualif_standard_ids`, `_qualif_equipment_summary`, `_qualif_type_descriptions`
- 2026-05-16 — 13 testes novos em `test_quotation_report.py` (agregação, fallback, render PDF/HTML) — 43/43 pass
- 2026-05-16 — Bump versão 16.0.2.1.0 → 16.0.2.2.0
