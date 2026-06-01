# Design — Jornada de Trabalho (horas/dia) por equipamento

**Data:** 2026-06-01
**Módulo:** `afr_qualificacao` (submodule)
**Versão alvo:** 16.0.5.8.0

## Objetivo

O cálculo de dias úteis hoje usa divisor fixo `8` (`horas / 8`). Tornar a
**jornada (horas/dia) configurável por equipamento**, default **8.0**,
cadastrada no **template de equipamento** (`afr.qualificacao.config.template`)
e puxada ao selecioná-lo no configurador, **editável por equipamento (override)**.
Dias = horas ÷ jornada. A jornada (h/dia) é exibida **apenas nas tabelas
resumo** (cronograma do report PDF/portal + painel de subtotais do SO); a nota
fixa "Base: 8 horas por dia útil" é removida.

## Componentes

### C1 — Campo no template
`models/config_template.py` → `afr.qualificacao.config.template`:
```python
work_hours_per_day = fields.Float(
    string="Jornada (h/dia)",
    default=8.0,
    help="Horas úteis por dia usadas no cálculo de dias do cronograma "
         "(dias = horas estimadas ÷ jornada). Default 8h.",
)
```
`views/config_template_views.xml`: adicionar o campo próximo a `estimated_days`/
`price_base`.

### C2 — Linha de equipamento do configurador (override)
`wizards/qualificacao_configurator.py` → `AfrQualificacaoConfiguratorEquipment`:
```python
work_hours_per_day = fields.Float(
    string="Jornada (h/dia)", default=8.0,
    help="Horas úteis/dia deste equipamento (puxada do template, editável).",
)
```
- `_onchange_config_template`: ao puxar template, setar
  `work_hours_per_day = template.work_hours_per_day or 8.0`.
- `_compute_estimated_totals` (linha ~688): trocar `hours / 8.0` por
  `hours / (el.work_hours_per_day or 8.0)`.
- Total do wizard `_compute_estimated_totals_wizard` (linha ~139-144): trocar
  `hours / 8.0` por **soma dos dias por-equipamento**:
  `wiz.estimated_days_total = sum(wiz.equipment_line_ids.mapped("estimated_days_total"))`.
  (a soma de horas total deixa de servir, pois jornadas podem diferir.)
- `views/qualificacao_configurator_views.xml`: adicionar `work_hours_per_day`
  editável na linha de equipamento (form da equipment line, junto de
  `estimated_days_total`).
- **Bulk wizard** (`AfrQualificacaoConfiguratorBulk` + `_compute`/apply que cria
  equipment lines): propagar `work_hours_per_day` (default 8.0; do template se
  houver) ao criar as equipment lines, p/ não regredir o default.

### C3 — Snapshot na SO
`models/sale_order_line.py`:
```python
work_hours_per_day = fields.Float(
    string="Jornada (h/dia)", default=8.0,
    help="Horas úteis/dia do equipamento (congelado da proposta; "
         "usado no cronograma). Editável.",
)
```
`wizards/qualificacao_configurator.py` `action_apply`: nos vals da **section line
por equipamento** (linha ~318-327), adicionar
`"work_hours_per_day": eq_line.work_hours_per_day or 8.0`.
(A section line é única por equipamento e já carrega `equipment_id`/
`config_template_id` — é o portador natural do valor congelado.)

### C4 — Helper + cálculo de dias na SO
`models/sale_order.py`:
```python
def _qualif_work_hours_per_day(self, equipment):
    """Jornada (h/dia) do equipamento — lê da section line; fallback 8.0."""
    self.ensure_one()
    section = self.order_line.filtered(
        lambda l: l.display_type == "line_section"
        and l.equipment_id == equipment
    )[:1]
    return section.work_hours_per_day or 8.0
```
Substituir os `/ 8.0` por jornada do equipamento:
- `_qualif_estimated_days(equipment)` (426):
  `return self._qualif_estimated_hours(equipment) / self._qualif_work_hours_per_day(equipment)`.
- `_qualif_schedule_rows` (459-478): cada row inclui
  `"work_hours_per_day": wh` e `"days": hours / wh` (com `wh = self._qualif_work_hours_per_day(eq)`).
- `qualif_subtotals_html` (compute, linha ~233): a linha TOTAL deixa de usar
  `total_hours / 8.0`; passa a **somar os dias por-equipamento** já calculados
  no loop (acumular `total_days += days`). Adicionar coluna "h/dia" por linha
  (C5).
- `models/proposal_block.py` `_html_schedule` (300-325): usar `r["work_hours_per_day"]`
  e `r["days"]` das rows; TOTAL de dias = soma de `r["days"]` (não `total_h/8`);
  adicionar coluna "h/dia" (C5).

### C5 — Jornada exibida só nas tabelas resumo
Adicionar coluna **"Jornada (h/dia)"** (valor `work_hours_per_day` por
equipamento) e **remover** a nota fixa "Base de cálculo: 8 horas por dia útil":
- `reports/quotation_template.xml` — bloco `schedule` (tabela Equipamento |
  **h/dia** | Horas | Dias úteis). Remover o `<p>` "8 horas por dia útil".
- `views/sale_order_portal_template.xml` — bloco `schedule` (idem). Remover o
  `<p>` "8 horas por dia útil".
- `qualif_subtotals_html` (painel de subtotais no form do SO) — adicionar coluna
  h/dia por equipamento (linha TOTAL: célula h/dia vazia/"—").

Linha TOTAL: coluna jornada vazia (não há jornada agregada); dias = soma.

### C6 — Manifest
`__manifest__.py`: `version` → `16.0.5.8.0`.

## Testes (`tests/test_work_hours_per_day.py`)
1. `test_template_onchange_pulls_work_hours` — equipment line `_onchange_config_template`
   com template `work_hours_per_day=6` → linha fica 6.0.
2. `test_apply_snapshots_to_section_line` — configurar com override `work_hours_per_day=4`,
   apply → section line do equipamento tem `work_hours_per_day=4`.
3. `test_estimated_days_uses_work_hours` — equip com 16h e jornada 4 →
   `_qualif_estimated_days(equip)` = 4.0 dias.
4. `test_fallback_8_when_no_section_or_zero` — `_qualif_work_hours_per_day` retorna
   8.0 quando não há section line / valor 0.
5. `test_schedule_rows_include_work_hours` — `_qualif_schedule_rows` traz
   `work_hours_per_day` e `days = hours/wh` por equipamento.
6. `test_total_days_sums_per_equipment` — 2 equips com jornadas diferentes:
   total de dias = soma dos dias por-equip (não `total_horas/8`).

## Fora de escopo
- Arredondamento de dias (mantém Float).
- Jornada na `engc.os` / execução (só cotação/proposta por ora).
- `config.template.estimated_days` (campo manual pré-existente) — inalterado.

## Notas
- Default **8.0** em todos os fallbacks (campo default + `or 8.0` nos cálculos).
- Override editável: na linha do configurador, no form do SO (campo na section
  line) e no template. Valor congela na proposta via snapshot (C3).
- 3 renderizações do cronograma (`quotation_template.xml`, portal,
  `_html_schedule`) consomem `_qualif_schedule_rows()` → ao enriquecer as rows
  (C4), as 3 ficam consistentes; só falta a coluna na view (C5).
