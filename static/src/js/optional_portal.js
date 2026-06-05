/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import ajax from "web.ajax";

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
            const res = await ajax.jsonRpc(
                `/my/orders/${orderId}/optional/${lineId}/toggle`,
                "call",
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
