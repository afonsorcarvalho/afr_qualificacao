/** @odoo-module **/
import { Dialog } from "@web/core/dialog/dialog";
import { Component, markup, useState } from "@odoo/owl";

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

// Ordem declarada das abas (NÃO derivar dos dados: rq_snippet_list ordena
// pela chave armazenada, alfabética).
export const RQ_SNIPPET_TABS = [
    { key: "tabela", label: "Tabelas técnicas" },
    { key: "lista", label: "Listas e texto" },
    { key: "destaque", label: "Destaques" },
    { key: "layout", label: "Layout" },
];

export class RqSnippetDialog extends Component {
    setup() {
        this.tabs = RQ_SNIPPET_TABS;
        this.state = useState({ cat: "tabela" });
    }
    get visibleSnippets() {
        return this.props.snippets
            .filter((s) => s.category === this.state.cat)
            .map((s) => ({ ...s, html: markup(s.body || "") }));
    }
    count(cat) {
        return this.props.snippets.filter((s) => s.category === cat).length;
    }
    pick(snippet) {
        this.props.onPick(snippet.body || "");
        this.props.close();
    }
}
RqSnippetDialog.template = "afr_qualificacao.RqSnippetDialog";
RqSnippetDialog.components = { Dialog };
RqSnippetDialog.props = {
    snippets: Array,
    onPick: Function,
    close: Function,
};
