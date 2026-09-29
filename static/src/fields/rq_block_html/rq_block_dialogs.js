/** @odoo-module **/
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState } from "@odoo/owl";

// Busca case/acento-insensível: "tolerancia" acha "Tolerância".
function fold(s) {
    return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export class RqVariableDialog extends Component {
    setup() {
        this.state = useState({ search: "" });
    }
    get groups() {
        const term = fold(this.state.search.trim());
        const groups = [];
        const byName = {};
        for (const item of this.props.catalog) {
            if (term && !fold(item.label).includes(term) && !fold(item.expr).includes(term)) {
                continue;
            }
            const name = item.group || "Outros";
            if (!byName[name]) {
                byName[name] = { name, items: [] };
                groups.push(byName[name]);
            }
            byName[name].items.push(item);
        }
        return groups;
    }
    hasValue(item) {
        return item.value !== undefined && item.value !== null && item.value !== "";
    }
    pick(item) {
        this.props.onPick(item);
        this.props.close();
    }
}
RqVariableDialog.template = "afr_qualificacao.RqVariableDialog";
RqVariableDialog.components = { Dialog };
RqVariableDialog.props = {
    catalog: Array,
    showValues: { type: Boolean, optional: true },
    onPick: Function,
    close: Function,
};
