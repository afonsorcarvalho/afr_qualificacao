/** @odoo-module **/
// Etiquetas de variável do editor de bloco. Formato salvo:
// <span class="rq-var">{{ EXPR }}</span>. Decoração (label, contenteditable,
// data-rq-expr, title, rq-var-unknown) existe SÓ no DOM do editor.
const TOKEN_RE = /\{\{\s*(.+?)\s*\}\}/g;
const DECOR_CLASSES = ["rq-var-unknown"];

export function makeVarNode(doc, expr, label) {
    const span = doc.createElement("span");
    span.className = "rq-var";
    span.textContent = `{{ ${expr} }}`;
    if (label !== undefined) {
        decorateOne(span, expr, label, false, `{{ ${expr} }}`);
    }
    return span;
}

export function normalizeVars(root) {
    const doc = root.ownerDocument;
    const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const texts = [];
    while (walker.nextNode()) {
        const n = walker.currentNode;
        if (n.parentElement && n.parentElement.closest(".rq-var")) {
            continue;
        }
        TOKEN_RE.lastIndex = 0;
        if (TOKEN_RE.test(n.nodeValue)) {
            texts.push(n);
        }
    }
    TOKEN_RE.lastIndex = 0;
    for (const n of texts) {
        const frag = doc.createDocumentFragment();
        const text = n.nodeValue;
        let last = 0;
        text.replace(TOKEN_RE, (m, expr, idx) => {
            frag.append(text.slice(last, idx), makeVarNode(doc, expr.trim()));
            last = idx + m.length;
        });
        frag.append(text.slice(last));
        n.replaceWith(frag);
    }
}

function exprOf(span) {
    if (span.dataset.rqExpr) {
        return span.dataset.rqExpr;
    }
    const m = /\{\{\s*(.+?)\s*\}\}/.exec(span.textContent);
    return m ? m[1].trim() : span.textContent.trim();
}

// Idempotente: só toca no DOM quando algo difere. Redecorar trocando o nó de
// texto sem necessidade (observer do editor inativo) deixaria o histórico
// apontando para nós que não existem mais (undo quebrado).
function decorateOne(span, expr, label, unknown, title) {
    if (span.dataset.rqExpr !== expr) {
        span.dataset.rqExpr = expr;
    }
    if (span.getAttribute("contenteditable") !== "false") {
        span.setAttribute("contenteditable", "false");
    }
    if (span.title !== title) {
        span.title = title;
    }
    if (span.textContent !== label) {
        span.textContent = label;
    }
    if (span.classList.contains("rq-var-unknown") !== unknown) {
        span.classList.toggle("rq-var-unknown", unknown);
    }
}

export function decorateVars(root, catalogByExpr) {
    for (const span of root.querySelectorAll("span.rq-var")) {
        const expr = exprOf(span);
        const item = catalogByExpr[expr];
        let title = `{{ ${expr} }}`;
        if (item && item.value !== undefined && item.value !== "") {
            title = `${title} → ${item.value}`;
        }
        decorateOne(span, expr, item ? item.label : expr, !item, title);
    }
}

export function cleanVarsHtml(html) {
    // Sem etiqueta ⇒ devolve a string intacta (re-serializar via innerHTML
    // faria o HtmlField achar que um bloco intocado mudou).
    if (!html || !html.includes("rq-var")) {
        return html;
    }
    const d = document.createElement("div");
    d.innerHTML = html;
    for (const span of d.querySelectorAll("span.rq-var")) {
        const expr = exprOf(span);
        for (const a of [...span.attributes]) {
            if (a.name !== "class") {
                span.removeAttribute(a.name);
            }
        }
        DECOR_CLASSES.forEach((c) => span.classList.remove(c));
        span.className = "rq-var";
        span.textContent = `{{ ${expr} }}`;
    }
    return d.innerHTML;
}
