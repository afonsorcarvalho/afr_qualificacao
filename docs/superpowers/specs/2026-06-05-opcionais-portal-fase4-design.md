# Opcionais no Portal Interativo — Fase 4 Design Spec
Date: 2026-06-05
Module: afr_qualificacao

## Contexto

Fases 1-3 entregues. Hoje a caixa ☑/☐ no portal é **estática** (só leitura). Fase 4 torna-a **interativa**: o cliente clica e a seleção grava `optional_accepted` via endpoint POST com `access_token`, recalculando qty/total. É a última fase.

Decisões:
- **Editável só em `state in ('draft','sent')`** (cotação em negociação). Confirmada/cancelada → read-only (mostra ☑/☐ estático como na Fase 3).
- **Seleção do cliente já conta** (grava direto, sem aprovação do comercial — decisão da arquitetura global).
- **Após marcar → reload da página** (total/subtotais recalculam server-side; mínimo de JS).

## Arquitetura

Lógica de negócio num método do `sale.order` (testável via TransactionCase). Controller de portal fino (só autorização via `_document_check_access`, delega ao método). Template: checkbox interativo quando editável. JS leve (POST + reload).

## 1. Model — `sale.order._portal_toggle_optional`

Novo método em `sale.order` (models/sale_order.py):
```python
    def _portal_toggle_optional(self, line_id, accepted):
        """Grava optional_accepted numa linha opcional, a partir do portal.
        Valida estado editável + pertença + tipo. Retorna dict de estado."""
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            raise UserError(_(
                "Esta cotação já foi confirmada; os opcionais não podem "
                "mais ser alterados."))
        line = self.order_line.filtered(lambda l: l.id == int(line_id))
        if not line or not line.is_proposal_optional:
            raise UserError(_("Item opcional inválido."))
        line.optional_accepted = bool(accepted)
        line._sync_optional_qty()
        return {
            "accepted": line.optional_accepted,
            "amount_total": self.amount_total,
        }
```

> `UserError`/`_` já importados em sale_order.py. O método opera sobre `self` (a SO já validada pelo controller via token). `_sync_optional_qty` (Fase 1) recalcula `product_uom_qty`; o `amount_total` recomputa nativamente.

## 2. Controller — `controllers/portal.py` (novo)

Herda o `CustomerPortal` (reusa `_document_check_access`). Route JSON:
```python
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.addons.portal.controllers.portal import CustomerPortal


class QualifPortalOptional(CustomerPortal):

    @http.route(
        ["/my/orders/<int:order_id>/optional/<int:line_id>/toggle"],
        type="json", auth="public", website=True, methods=["POST"])
    def portal_optional_toggle(self, order_id, line_id, access_token=None,
                               accepted=False, **kw):
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token=access_token)
        except (AccessError, MissingError):
            return {"error": "access"}
        try:
            result = order_sudo._portal_toggle_optional(line_id, accepted)
        except UserError as e:
            return {"error": str(e)}
        return result
```
Registar em `controllers/__init__.py`: `from . import portal`.

> `auth="public"` + `_document_check_access` com token = o padrão do portal Odoo (escrita validada por token, sem login). `type="json"` → CSRF tratado pelo handler JSON-RPC. A escrita usa o `order_sudo` (já SUDOED pelo helper) só após validação de token + estado.

## 3. Template — checkbox interativo (`views/sale_order_portal_template.xml`)

No bloco `block_kind == 'optionals'`, a célula da caixa (hoje `<t t-if="ol.optional_accepted">☑</t><t t-else="">☐</t>`) passa a:
```xml
                                            <td class="text-center">
                                                <t t-if="sale_order.state in ('draft', 'sent')">
                                                    <input type="checkbox"
                                                           class="o_qualif_opt_toggle"
                                                           t-att-checked="ol.optional_accepted and 'checked' or None"
                                                           t-att-data-order-id="sale_order.id"
                                                           t-att-data-line-id="ol.id"
                                                           t-att-data-token="sale_order.access_token"/>
                                                </t>
                                                <t t-else="">
                                                    <t t-if="ol.optional_accepted">&#9745;</t>
                                                    <t t-else="">&#9744;</t>
                                                </t>
                                            </td>
```
A nota abaixo da tabela ganha (quando editável) uma frase: "Marque os opcionais desejados — o total atualiza automaticamente."

## 4. JS — `static/src/js/optional_portal.js` (novo)

Listener nos checkboxes; POST JSON-RPC; em sucesso recarrega:
```javascript
/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.QualifOptionalToggle = publicWidget.Widget.extend({
    selector: ".o_portal_sale_sidebar, #sale_order_online, body",
    events: {
        "change .o_qualif_opt_toggle": "_onToggle",
    },
    async _onToggle(ev) {
        const cb = ev.currentTarget;
        const orderId = cb.dataset.orderId;
        const lineId = cb.dataset.lineId;
        const token = cb.dataset.token;
        cb.disabled = true;
        try {
            const res = await jsonrpc(
                `/my/orders/${orderId}/optional/${lineId}/toggle`,
                { access_token: token, accepted: cb.checked });
            if (res && res.error) {
                cb.checked = !cb.checked;
                alert(res.error === "access"
                    ? "Sessão inválida. Recarregue a página."
                    : res.error);
                cb.disabled = false;
                return;
            }
            window.location.reload();
        } catch (e) {
            cb.checked = !cb.checked;
            cb.disabled = false;
        }
    },
});
export default publicWidget.registry.QualifOptionalToggle;
```

> Usa `publicWidget` (frontend Odoo 16) + `jsonrpc`. O `selector` amplo garante que o widget anexa na página do portal de SO; o delegate `change` filtra pelos checkboxes. Reload simples mostra total/subtotais recomputados.

## 5. Manifest — registar JS

Em `__manifest__.py` `assets.web.assets_frontend`, adicionar após o SCSS:
```python
            "afr_qualificacao/static/src/js/optional_portal.js",
```

## 6. Segurança (revisão)

- **Token:** `_document_check_access('sale.order', order_id, access_token)` — comparação constante (`consteq`), padrão Odoo. Sem token válido + sem login → `AccessError` → `{"error":"access"}`.
- **Estado:** `_portal_toggle_optional` rejeita se `state not in (draft, sent)` → cotação confirmada não muda.
- **Pertença + tipo:** a linha tem de pertencer à `self` (SO validada) E `is_proposal_optional=True` — não dá para tocar linhas de outra SO nem linhas normais.
- **Escopo da escrita:** só `optional_accepted` (1 bool) + `product_uom_qty` (via sync). Nada mais.
- `auth="public"` é necessário (cliente do portal não está logado); a autorização é o token, não a sessão.

## Fora de âmbito
- Update ao vivo do total sem reload (reload é suficiente e robusto).
- Notificação ao comercial quando o cliente marca (futuro: chatter/activity).

## Testes (TDD)

`tests/test_portal_optional.py` (herda `AfrQualificacaoTestCommon`) — testa o método do model (lógica + segurança de estado/pertença), não o HTTP:
1. `test_toggle_accepts` — SO draft + opcional → `_portal_toggle_optional(line, True)` → optional_accepted=True, product_uom_qty>0, retorna amount_total.
2. `test_toggle_unaccepts` — aceito → toggle False → optional_accepted=False, qty=0.
3. `test_toggle_confirmed_raises` — SO confirmada (state='sale') → UserError, não grava.
4. `test_toggle_non_optional_raises` — line_id de linha normal → UserError.
5. `test_toggle_foreign_line_raises` — line_id de outra SO → UserError (não encontrada em self).
