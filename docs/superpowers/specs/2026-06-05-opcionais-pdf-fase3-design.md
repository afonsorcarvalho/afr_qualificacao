# Opcionais no PDF/Portal — Fase 3 Design Spec
Date: 2026-06-05
Module: afr_qualificacao

## Contexto

Fase 1 (núcleo) + Fase 2 (wizard) entregues. Hoje o opcional não-aceito tem `product_uom_qty=0`, logo o PDF/portal mostram **Qtd 0 e Subtotal 0** — o cliente não vê o preço da oferta. Fase 3 ajusta a apresentação: opcionais mostram **preço de referência** + **caixa ☑/☐** (autorizado), e a secção fica claramente **fora do total** (que já exclui não-aceitos).

## 1. Campo de subtotal de referência (`sale.order.line`)

Hoje `_optional_target_qty()` devolve a qty efetiva (0 se não aceito). Para o preço de referência, extrair a "qty quando aceito":

```python
    def _optional_full_qty(self):
        """Qty de uma linha opcional SE aceita (ignora o estado aceito):
        ciclo/malha → qualif_cycle_qty × estimated_hours; serviço → optional_qty."""
        self.ensure_one()
        if self.cycle_type_id or self.malha_type_id:
            return (self.qualif_cycle_qty or 0) * (self.estimated_hours or 0.0)
        return self.optional_qty

    def _optional_target_qty(self):
        """Qty efetiva: 0 se não aceito, senão a qty cheia."""
        self.ensure_one()
        return self._optional_full_qty() if self.optional_accepted else 0.0
```

> `_optional_target_qty` é chamado só para linhas opcionais (em `_sync_optional_qty`, guardado por `if not is_proposal_optional: continue`). A refatoração apenas extrai `_optional_full_qty()` — comportamento idêntico ao da Fase 1.

Campo computed (não-stored, só display):
```python
    optional_ref_subtotal = fields.Monetary(
        string="Subtotal Referência",
        compute="_compute_optional_ref_subtotal",
        currency_field="currency_id",
        help="Preço de referência do opcional (preço unit. × qtd pretendida), "
             "mostrado na proposta mesmo quando ainda não aceito.",
    )

    @api.depends("is_proposal_optional", "price_unit", "optional_qty",
                 "qualif_cycle_qty", "estimated_hours", "cycle_type_id",
                 "malha_type_id")
    def _compute_optional_ref_subtotal(self):
        for line in self:
            if line.is_proposal_optional:
                line.optional_ref_subtotal = (
                    line.price_unit * line._optional_full_qty())
            else:
                line.optional_ref_subtotal = 0.0
```

## 2. Template PDF — `reports/templates_blocos/block_optionals.xml`

Substituir a tabela (mantendo o wrapper `div`/título):
- Cabeçalho ganha 1ª coluna vazia (caixa) e renomeia "Subtotal" → "Subtotal (ref.)".
- Cada linha: célula com `☑` se `ol.optional_accepted` senão `☐`; Qtd = `ol.optional_qty`; Valor Unit = `ol.price_unit`; Subtotal = `ol.optional_ref_subtotal`.
- Linha de nota após a tabela: "☑ = autorizado pelo cliente. Apenas os itens marcados entram no total da proposta."

```xml
                                <table class="qq-table">
                                    <tr>
                                        <th style="width: 6%;"></th>
                                        <th>Serviço</th>
                                        <th style="width: 10%;">Qtd</th>
                                        <th style="width: 18%; text-align: right;">Valor Unit.</th>
                                        <th style="width: 18%; text-align: right;">Subtotal (ref.)</th>
                                    </tr>
                                    <t t-foreach="opt_lines" t-as="ol">
                                        <tr>
                                            <td style="text-align: center; font-size: 13px;">
                                                <t t-if="ol.optional_accepted">&#9745;</t>
                                                <t t-else="">&#9744;</t>
                                            </td>
                                            <td><span t-esc="ol.name"/></td>
                                            <td>
                                                <span t-esc="int(ol.optional_qty) if ol.optional_qty == int(ol.optional_qty) else ol.optional_qty"/>
                                            </td>
                                            <td style="text-align: right;">
                                                <span t-esc="ol.price_unit"
                                                      t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                            </td>
                                            <td style="text-align: right;">
                                                <span t-esc="ol.optional_ref_subtotal"
                                                      t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                            </td>
                                        </tr>
                                    </t>
                                </table>
                                <p style="font-size: 10px; color: #666; margin-top: 4px;">
                                    &#9745; = autorizado pelo cliente. Apenas os itens marcados entram no total da proposta.
                                </p>
```

> `&#9745;` = ☑ (U+2611), `&#9744;` = ☐ (U+2610).

## 3. Template Portal — `views/sale_order_portal_template.xml` (linhas 461-502)

Mesma transformação no bloco `block_kind == 'optionals'`: 1ª coluna caixa, Qtd = `optional_qty`, Subtotal = `optional_ref_subtotal`, header "Subtotal (ref.)", nota abaixo da tabela.

```xml
                                <thead>
                                    <tr>
                                        <th style="width: 6%;"></th>
                                        <th>Serviço</th>
                                        <th>Qtd</th>
                                        <th class="text-end">Valor Unit.</th>
                                        <th class="text-end">Subtotal (ref.)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <t t-foreach="opt_lines" t-as="ol">
                                        <tr>
                                            <td class="text-center">
                                                <t t-if="ol.optional_accepted">&#9745;</t>
                                                <t t-else="">&#9744;</t>
                                            </td>
                                            <td t-esc="ol.name"/>
                                            <td>
                                                <span t-esc="int(ol.optional_qty) if ol.optional_qty == int(ol.optional_qty) else ol.optional_qty"/>
                                            </td>
                                            <td class="text-end">
                                                <span t-esc="ol.price_unit"
                                                      t-options="{'widget': 'monetary', 'display_currency': sale_order.currency_id}"/>
                                            </td>
                                            <td class="text-end">
                                                <span t-esc="ol.optional_ref_subtotal"
                                                      t-options="{'widget': 'monetary', 'display_currency': sale_order.currency_id}"/>
                                            </td>
                                        </tr>
                                    </t>
                                </tbody>
```
E após a `</table>` (antes de `</div>` da table-responsive):
```xml
                            <p class="text-muted" style="font-size: 12px;">
                                &#9745; = autorizado pelo cliente. Apenas os itens marcados entram no total da proposta.
                            </p>
```

## 4. Snapshot — `models/proposal_block.py` `_html_optionals`

Atualizar para espelhar: coluna da caixa (texto ☑/☐), Qtd = `optional_qty`, subtotal = `optional_ref_subtotal`.
```python
    def _html_optionals(self, order):
        opt_lines = order.order_line.filtered("is_proposal_optional")
        rows = Markup("").join(
            Markup(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            ) % (
                "☑" if line.optional_accepted else "☐",
                escape(line.name or ""),
                line.optional_qty,
                escape(self._money(order, line.price_unit)),
                escape(self._money(order, line.optional_ref_subtotal)),
            )
            for line in opt_lines
        )
        return Markup(
            "<table><thead><tr><th></th><th>Serviço</th><th>Qtd</th>"
            "<th>Valor Unit.</th><th>Subtotal (ref.)</th></tr></thead>"
            "<tbody>%s</tbody></table>"
            "<p style='font-size:10px;color:#666'>☑ = autorizado pelo "
            "cliente. Apenas os itens marcados entram no total.</p>"
        ) % rows
```

## 5. Total geral — sem mudança

`block_sales_items.xml` exclui opcionais (`not l.is_proposal_optional`). O `amount_total` (Odoo) soma só linhas com qty>0 → opcional aceito (qty>0) **entra** no total, não-aceito (qty=0) **não**. Comportamento correto para Fase 3; nada a alterar.

## Fora de âmbito
- Portal interativo (checkbox que grava `optional_accepted` via controller) — Fase 4.

## Testes (TDD)

`tests/test_optional_ref_subtotal.py` (herda `AfrQualificacaoTestCommon`):
1. `test_ref_subtotal_service_not_accepted` — serviço opcional não aceito, optional_qty=2, price_unit=150 → `optional_ref_subtotal == 300` (mesmo com product_uom_qty=0).
2. `test_ref_subtotal_service_accepted` — aceito → `optional_ref_subtotal == 300` e `price_subtotal == 300`.
3. `test_ref_subtotal_cycle` — opcional ciclo (qualif_cycle_qty=3, estimated_hours=2, price_unit=100), não aceito → `optional_ref_subtotal == 600` (3×2×100).
4. `test_ref_subtotal_non_optional_zero` — linha normal (não opcional) → `optional_ref_subtotal == 0`.
