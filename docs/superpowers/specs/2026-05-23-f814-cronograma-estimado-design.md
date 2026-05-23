# F8.14 — Cronograma estimado + rodapé tabelas escopo

**Versão alvo:** 16.0.4.13.0
**Status:** Design aprovado
**Autor:** afonso (sessão 2026-05-23)

## Objetivo

Adicionar estimativa de horas por execução de ciclo/malha/QI/QS no catálogo (override por cotação no configurador), com agregação em horas + dias úteis (8h/dia) por equipamento. Exibir cronograma no rodapé do bloco Equipment Scope do PDF. Corrigir CSS das tabelas QO/QD/Calib (sem rodapé/border inferior).

## Decisões

1. **Unidade:** horas (`estimated_hours` Float, digits='Product Price').
2. **Edição:** type (catálogo) + override na subline configurador + override em SO line + override em template line.
3. **Display PDF:** (a) rodapé `<tfoot>` em cada tabela QO/QD/Calib com subtotal da seção; (b) rodapé do Equipment Scope com total agregado do equipamento; (c) novo `block_kind='schedule'` opcional no template com tabela por equipamento + total geral.
4. **Sem migration:** `estimated_days` (F8.1, não usado em código) renomeado direto pra `estimated_hours`. Valores perdidos (risk baixo).

## Modelos

### Rename
- `afr.qualificacao.cycle.type.estimated_days` → `estimated_hours` (help atualizado).
- `afr.qualificacao.malha.type.estimated_days` → `estimated_hours`.

### Novos campos
- `afr.qualificacao.type.config.estimated_hours` (Float) — horas pra QI/QS.
- `afr.qualificacao.config.template.qd.estimated_hours` (Float, opcional).
- `afr.qualificacao.config.template.qo.estimated_hours` (Float, opcional).
- `afr.qualificacao.config.template.calib.estimated_hours` (Float, opcional).
- `sale.order.line.estimated_hours` (Float) — persist override do configurador.
- `afr.qualificacao.configurator.qd.line.estimated_hours` (Float).
- `afr.qualificacao.configurator.qo.line.estimated_hours` (Float).
- `afr.qualificacao.configurator.calib.line.estimated_hours` (Float).
- `afr.qualificacao.configurator.bulk.qd.estimated_hours` (Float).
- `afr.qualificacao.configurator.bulk.qo.estimated_hours` (Float).
- `afr.qualificacao.configurator.bulk.calib.estimated_hours` (Float).
- `afr.qualificacao.configurator.equipment.estimated_hours_total` (computed, Float).
- `afr.qualificacao.configurator.equipment.estimated_days_total` (computed, Float = hours/8).
- `afr.qualificacao.configurator.estimated_hours_total` (computed wizard-level).
- `afr.qualificacao.configurator.estimated_days_total` (computed wizard-level).

## Onchange + Autofill

- `_onchange_cycle_type_defaults` da subline:
  - `line.estimated_hours = line.cycle_type_id.estimated_hours` (se vazio).
- `_onchange_malha_type_defaults` idem.
- `_onchange_config_template` (template autofill): passa `line.estimated_hours or line.cycle_type_id.estimated_hours` (mesma lógica de description/unit_price).
- `action_duplicate` (equipment line): copia estimated_hours das sublines.

## Action Apply (subline → SO line)

```python
qo_vals["estimated_hours"] = qo.estimated_hours or qo.cycle_type_id.estimated_hours
qd_vals["estimated_hours"] = qd.estimated_hours or qd.cycle_type_id.estimated_hours
c_vals["estimated_hours"] = c.estimated_hours or c.malha_type_id.estimated_hours
```

QI/QS (sem subline): pega `type.config.estimated_hours`.

## Helpers sale.order

```python
def _qualif_estimated_hours(self, equipment=None):
    """Soma horas das qualif lines do SO (opc filtrado por equipment)."""
    lines = self.order_line.filtered("is_qualificacao_managed")
    if equipment:
        lines = lines.filtered(lambda l: l.equipment_id == equipment)
    total = 0.0
    for line in lines:
        hours = line.estimated_hours
        if not hours:
            if line.cycle_type_id:
                hours = line.cycle_type_id.estimated_hours
            elif line.malha_type_id:
                hours = line.malha_type_id.estimated_hours
            elif line.qualification_type in ("installation", "software"):
                cfg = self.env["afr.qualificacao.type.config"].get_config_for(
                    line.qualification_type, self.company_id,
                )
                if cfg:
                    hours = cfg.estimated_hours
        total += hours * (line.product_uom_qty or 0)
    return total

def _qualif_estimated_days(self, equipment=None):
    """Horas / 8 (Float decimal — 12h = 1.5 dias)."""
    return self._qualif_estimated_hours(equipment) / 8.0
```

## UI Configurador

- Equipment line modal header: `estimated_hours_total` + `estimated_days_total` (read-only, ao lado de Subtotal).
- Wizard root: total cronograma "N dias úteis (M horas)" perto do total geral.
- Tree sublines QO/QD/Calib: coluna `Horas` editável.
- Template form: coluna Horas editável nas 3 abas QD/QO/Calib.

## PDF

### Tabelas QO/QD/Calib — rodapé `<tfoot>` (item 1)

Cada tabela ganha `<tfoot>` com subtotal da seção:

```html
<tfoot>
  <tr class="qq-table-footer">
    <td colspan="3">Total: {{ N }} ciclos</td>
    <td class="text-right">{{ hours }} h · {{ days }} dias</td>
  </tr>
</tfoot>
```

CSS:
```css
.qq-table tfoot td {
    border-top: 2px solid #333;
    font-weight: bold;
    padding: 6px 10px;
    background-color: #fafafa;
}
```

Resolve simultaneamente item 1 (border-bottom faltante) + breakdown por seção.

### Equipment Scope bloco — rodapé total

Após tabelas + lists QI/Calib, novo div agregado:

```html
<div class="qq-equip-schedule">
  <strong>Cronograma estimado:</strong>
  {{ days }} dias úteis ({{ hours }} horas — base 8h/dia)
</div>
```

CSS:
```css
.qq-equip-schedule {
    border-top: 1px solid #999;
    padding-top: 8px;
    margin-top: 10px;
    font-size: 14px;
    color: #222;
    text-align: right;
}
```

### Novo bloco `schedule` (template-opcional)

Block kind `schedule` adicionado em `proposal_block`. `_html_schedule(order)` renderiza:

```html
<table class="qq-table">
  <thead><tr><th>Equipamento</th><th>Horas</th><th>Dias úteis</th></tr></thead>
  <tbody>
    {% for row in rows %}
    <tr><td>{{ row.equipment.display_name }}</td><td>{{ row.hours }}</td><td>{{ row.days }}</td></tr>
    {% endfor %}
  </tbody>
  <tfoot><tr><td><strong>TOTAL</strong></td><td><strong>{{ total_hours }}</strong></td><td><strong>{{ total_days }}</strong></td></tr></tfoot>
</table>
```

Helper `sale.order._qualif_schedule_rows()` → `[{equipment, hours, days}]` + total geral.

Bloco NÃO incluído no seed default — cliente adiciona via editor de template.

### cycle_specs bloco

Mesmo padrão de `<tfoot>` que tabelas QO/QD/Calib.

## Seeds opcionais

Atualizar `data/cycle_type_seed.xml` + `data/malha_type_seed.xml` com valores iniciais (ex):
- Bowie Dick = 0.5h
- Vazio Sensíveis = 1h
- Carga Mista = 2h
- Carga Sensíveis = 3h
- Malha Temp = 4h
- Malha Press = 4h

Em `type.config` seed (se existir): QI=8h, QS=4h.

User pode editar via UI.

## Tests novos

### tests/test_estimated_hours.py
- `test_cycle_type_default_propagates_to_subline` — onchange seta estimated_hours.
- `test_subline_override_persists_to_so_line` — action_apply copia override.
- `test_qualif_estimated_hours_aggregates_per_equipment` — soma horas por equip.
- `test_qualif_estimated_hours_aggregates_total` — soma SO inteira.
- `test_qualif_estimated_days_divides_by_8` — 24h = 3 dias, 12h = 1.5.
- `test_template_autofill_propagates_estimated_hours` — `_onchange_config_template`.
- `test_bulk_wizard_propagates_estimated_hours` — bulk apply.
- `test_fallback_to_type_when_subline_zero` — line.estimated_hours=0 usa type.

### tests/test_proposal_report.py (existente)
- `test_render_table_tfoot_subtotals` — asserta `<tfoot>` com "Total: N ciclos" + horas/dias em cada tabela QO/QD/Calib.
- `test_render_equipment_scope_footer_cronograma` — asserta "Cronograma estimado" + "N dias úteis" no HTML.
- `test_render_schedule_block` — adiciona template line block_kind='schedule' + asserta tabela equipamentos + total geral no HTML.

## Roadmap

- Bump `__manifest__.py` 16.0.4.12.1 → 16.0.4.13.0.
- Entry F8.14 no roadmap description.
- TODO.md entry em "Feito".

## Out of scope

- Sem migration formal (estimated_days descartado).
- Sem campo no Resumo Financeiro (user não escolheu).
- Sem cálculo paralelizado (multi-técnico em dias overlapping) — total assume sequencial.
- Bloco `schedule` não entra no seed default — só disponível como tipo (cliente adiciona se quiser).
