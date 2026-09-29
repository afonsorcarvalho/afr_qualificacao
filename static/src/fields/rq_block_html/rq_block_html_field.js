/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { HtmlField } from "@web_editor/js/backend/html_field";
import { markup, useState } from "@odoo/owl";
import { normalizeVars, decorateVars, cleanVarsHtml, makeVarNode } from "./rq_var_dom";
import { RqSnippetDialog, RqVariableDialog } from "./rq_block_dialogs";

// Editor de corpo de bloco do relatório: variáveis viram etiquetas
// ({{ expr }} → chip com o rótulo). A decoração vive só no DOM do editor;
// tudo que sai do editor (getValue/getEditingValue) passa por cleanVarsHtml,
// então o valor salvo é sempre <span class="rq-var">{{ EXPR }}</span>.
export class RqBlockHtmlField extends HtmlField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this.rq = useState({ mode: "edit", previewHtml: "", missing: [], loading: false });
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
    get canPreview() {
        return !this.isStatic && Boolean(this.relatorioId);
    }
    get wysiwygOptions() {
        const opts = super.wysiwygOptions;
        // Categoria declarada com prioridade alta: o Powerbox agrupa por
        // categoria (ordem por prioridade) e categorias NÃO declaradas vão
        // para o fim — "/bloco" teria Aspas/Texto/Assinatura antes e o
        // Enter pegaria o primeiro.
        opts.powerboxCategories = [
            ...(opts.powerboxCategories || []),
            { name: "Relatório", priority: 300 },
        ];
        opts.powerboxCommands = [
            ...(opts.powerboxCommands || []),
            {
                category: "Relatório",
                name: "Bloco pronto",
                priority: 20,
                description: "Tabela, lista, destaque ou layout pronto",
                fontawesome: "fa-th-large",
                callback: () => this.openSnippets(),
            },
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
            this.decorate({ normalize: true });
            return res;
        };
        await super.startWysiwyg(wysiwyg);
        await this.loadCatalog();
        this.decorate({ normalize: true });
    }
    // Fora do histórico (observer inativo). normalize troca nós de texto
    // ({{ x }} nu → span), então só roda com histórico recém-criado: na
    // abertura e após resetEditor. Rodar a cada inserção quebraria o undo
    // de um {{ x }} digitado à mão (o histórico apontaria para o nó de
    // texto que o normalize substituiu). decorateVars é idempotente.
    decorate({ normalize = false } = {}) {
        const editor = this.wysiwyg && this.wysiwyg.odooEditor;
        if (!editor || !editor.editable) {
            return;
        }
        editor.observerUnactive("rqDecorate");
        if (normalize) {
            normalizeVars(editor.editable);
        }
        decorateVars(editor.editable, this.catalogByExpr);
        editor.observerActive("rqDecorate");
    }
    // Sem override de getEditingValue: HtmlField.getEditingValue (16.0,
    // html_field.js) devolve this.wysiwyg.getValue() — já limpo pelo patch
    // de instância acima — ou o textarea do codeview, semeado com o
    // props.value (limpo). O patch de getValue é a única guarda.
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
    async openSnippets() {
        if (this.props.readonly || !this.wysiwyg) {
            return;
        }
        // RPC antes do saveRange: se o user digitar durante a chamada, o
        // range salvo antes ficaria velho.
        const snippets = await this.orm.call("afr.relatorio.snippet", "rq_snippet_list", []);
        this.saveRange();
        this.dialogService.add(RqSnippetDialog, {
            snippets,
            onPick: (body) => {
                // Prepara o conteúdo FORA do editor (container solto):
                // normaliza {{ }} nus e decora já aqui, para o passo de
                // histórico registrar os nós decorados (o decorate pós-insert
                // vira no-op; redo não traz etiqueta crua).
                const doc = this.wysiwyg.odooEditor.document;
                const tmp = doc.createElement("div");
                tmp.innerHTML = body;
                normalizeVars(tmp);
                decorateVars(tmp, this.catalogByExpr);
                // UMA inserção só (execCommand('insert') aceita fragment:
                // container.replaceChildren(content)). Inserir filho a filho
                // com o mesmo Range pode inverter a ordem.
                const frag = doc.createDocumentFragment();
                frag.append(...tmp.childNodes);
                this.insertNode(frag);
            },
        });
    }
    openImage() {
        if (this.props.readonly || !this.wysiwyg) {
            return;
        }
        // Diálogo de mídia nativo (Wysiwyg.openMediaDialog, o mesmo do
        // /image). Ele exige seleção dentro do editável e restaura o cursor
        // a partir dela.
        if (!this._selectionInEditable()) {
            this.wysiwyg.focus();
        }
        this.wysiwyg.openMediaDialog();
    }
    async openVariables() {
        if (this.props.readonly || !this.wysiwyg) {
            return;
        }
        await this.loadCatalog();
        this.saveRange();
        this.dialogService.add(RqVariableDialog, {
            catalog: this.catalog,
            showValues: !this.isStatic && Boolean(this.relatorioId),
            onPick: (item) => {
                const doc = this.wysiwyg.odooEditor.document;
                this.insertNode(makeVarNode(doc, item.expr, item.label));
            },
        });
    }
    async setMode(mode) {
        if (mode === this.rq.mode || this.rq.loading) {
            return;
        }
        if (mode === "preview") {
            if (!this.canPreview) {
                return;
            }
            this.rq.loading = true;
            let res;
            try {
                // Erro (ex.: sem direito de escrita) sobe para o error
                // service do Odoo (diálogo padrão); o modo fica em "edit".
                res = await this.orm.call("afr.qualificacao.relatorio", "rq_preview_block",
                    [[this.relatorioId], this.getEditingValue() || ""]);
            } finally {
                this.rq.loading = false;
            }
            this.rq.previewHtml = markup(res.html);
            this.rq.missing = res.missing.map((e) => (this.catalogByExpr[e] || {}).label || e);
            // Editor fica oculto (d-none), não destruído: tirar o foco evita
            // digitação às cegas no editável escondido.
            if (this.wysiwyg && this.wysiwyg.odooEditor) {
                this.wysiwyg.odooEditor.editable.blur();
            }
        }
        this.rq.mode = mode;
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
