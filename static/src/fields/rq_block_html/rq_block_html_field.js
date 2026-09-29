/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { HtmlField } from "@web_editor/js/backend/html_field";
import { normalizeVars, decorateVars, cleanVarsHtml, makeVarNode } from "./rq_var_dom";
import { RqVariableDialog } from "./rq_block_dialogs";

// Editor de corpo de bloco do relatório: variáveis viram etiquetas
// ({{ expr }} → chip com o rótulo). A decoração vive só no DOM do editor;
// tudo que sai do editor (getValue/getEditingValue) passa por cleanVarsHtml,
// então o valor salvo é sempre <span class="rq-var">{{ EXPR }}</span>.
export class RqBlockHtmlField extends HtmlField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this.catalogByExpr = {};
        this.catalog = [];
        this._range = null;
    }
    get isStatic() {
        return this.props.rqCatalog === "static";
    }
    get relatorioId() {
        const r = this.props.record.data.relatorio_id;
        // m2o no OWL 16 = [id, name]
        return Array.isArray(r) ? r[0] : r && r.id ? r.id : r;
    }
    get wysiwygOptions() {
        const opts = super.wysiwygOptions;
        opts.powerboxCommands = [
            ...(opts.powerboxCommands || []),
            {
                category: "Relatório",
                name: "Variável",
                priority: 19,
                // Filtro do powerbox é por regex sem dobrar acento: o termo
                // "variavel" sem acento na descrição faz /variavel achar.
                description: "Dado do relatório: critério, cliente, anexo (variavel)",
                fontawesome: "fa-tag",
                callback: () => this.openVariables(),
            },
        ];
        return opts;
    }
    async loadCatalog() {
        this.catalog = this.isStatic || !this.relatorioId
            ? await this.orm.call("afr.qualificacao.relatorio", "rq_variable_catalog_static", [])
            : await this.orm.call("afr.qualificacao.relatorio", "rq_variable_catalog", [[this.relatorioId]]);
        this.catalogByExpr = Object.fromEntries(this.catalog.map((c) => [c.expr, c]));
    }
    async startWysiwyg(wysiwyg) {
        // Patches na instância ANTES do super (startEdition grava
        // _initialValue via getValue):
        // - getValue limpo: toggleCodeView e outros consumidores leem
        //   wysiwyg.getValue() direto, sem passar por getEditingValue; sem
        //   isto o rótulo da etiqueta iria para o banco e a expressão se
        //   perderia (o sanitizer remove data-rq-expr).
        // - resetEditor redecora: o adapter chama resetEditor sem await e
        //   dispara env.onWysiwygReset antes do resetValue efetivo, então
        //   o hook do env decoraria o DOM antigo.
        const origGetValue = wysiwyg.getValue.bind(wysiwyg);
        wysiwyg.getValue = (...args) => cleanVarsHtml(origGetValue(...args));
        const origReset = wysiwyg.resetEditor.bind(wysiwyg);
        wysiwyg.resetEditor = async (...args) => {
            const res = await origReset(...args);
            this.decorate();
            return res;
        };
        await super.startWysiwyg(wysiwyg);
        await this.loadCatalog();
        this.decorate();
    }
    decorate() {
        const editor = this.wysiwyg && this.wysiwyg.odooEditor;
        if (!editor || !editor.editable) {
            return;
        }
        editor.observerUnactive("rqDecorate");
        normalizeVars(editor.editable);
        decorateVars(editor.editable, this.catalogByExpr);
        editor.observerActive("rqDecorate");
    }
    getEditingValue() {
        const v = super.getEditingValue();
        return v === null ? v : cleanVarsHtml(v);
    }
    _selectionInEditable() {
        const editor = this.wysiwyg.odooEditor;
        const sel = editor.document.getSelection();
        return sel && sel.rangeCount && editor.editable.contains(sel.anchorNode) ? sel : null;
    }
    saveRange() {
        // Clique fora do editor antes do botão: a seleção saiu do editável;
        // focus() restaura o último cursor conhecido pelo histórico.
        if (!this._selectionInEditable()) {
            this.wysiwyg.focus();
        }
        const sel = this._selectionInEditable();
        this._range = sel ? sel.getRangeAt(0).cloneRange() : null;
    }
    insertNode(node) {
        const editor = this.wysiwyg.odooEditor;
        editor.editable.focus();
        if (this._range) {
            const sel = editor.document.getSelection();
            sel.removeAllRanges();
            sel.addRange(this._range);
        } else if (!this._selectionInEditable()) {
            this.wysiwyg.focus();
        }
        this._range = null;
        editor.execCommand("insert", node);
        editor.sanitize(editor.editable);
        this.decorate();
    }
    async openVariables() {
        if (this.props.readonly || !this.wysiwyg) {
            return;
        }
        this.saveRange();
        await this.loadCatalog();
        this.dialogService.add(RqVariableDialog, {
            catalog: this.catalog,
            showValues: !this.isStatic && Boolean(this.relatorioId),
            onPick: (item) => {
                const doc = this.wysiwyg.odooEditor.document;
                this.insertNode(makeVarNode(doc, item.expr, item.label));
            },
        });
    }
}
RqBlockHtmlField.template = "afr_qualificacao.RqBlockHtmlField";
RqBlockHtmlField.props = { ...HtmlField.props, rqCatalog: { type: String, optional: true } };
RqBlockHtmlField.extractProps = (...args) => {
    const [{ attrs }] = args;
    return { ...HtmlField.extractProps(...args), rqCatalog: attrs.options.catalog };
};
registry.category("fields").add("rq_block_html", RqBlockHtmlField);
// Classe no wrapper do campo (Field.additionalClasses): escopo do SCSS
// independente da view que usa o widget.
RqBlockHtmlField.additionalClasses = [...(HtmlField.additionalClasses || []), "rq-block-editor"];
