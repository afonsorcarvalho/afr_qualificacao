/** @odoo-module **/
import { normalizeVars, decorateVars, cleanVarsHtml } from "@afr_qualificacao/fields/rq_block_html/rq_var_dom";

function el(html) { const d = document.createElement("div"); d.innerHTML = html; return d; }
const CAT = { "criterio['tolerancia']": { label: "Tolerância acima (°C)", value: "3" } };

QUnit.module("afr_qualificacao.rq_var_dom", () => {
    QUnit.test("normalize wraps bare tokens once", (assert) => {
        const d = el("<p>A {{ criterio['tolerancia'] }} B</p>");
        normalizeVars(d); normalizeVars(d);
        assert.strictEqual(d.innerHTML,
            '<p>A <span class="rq-var">{{ criterio[\'tolerancia\'] }}</span> B</p>');
    });
    QUnit.test("decorate then clean is identity", (assert) => {
        const src = '<p>A <span class="rq-var">{{ criterio[\'tolerancia\'] }}</span> B</p>';
        const d = el(src);
        decorateVars(d, CAT);
        const span = d.querySelector(".rq-var");
        assert.strictEqual(span.getAttribute("contenteditable"), "false");
        assert.strictEqual(span.textContent, "Tolerância acima (°C)");
        assert.strictEqual(cleanVarsHtml(d.innerHTML), src);
        decorateVars(d, CAT);
        assert.strictEqual(cleanVarsHtml(d.innerHTML), src);
    });
    QUnit.test("unknown expr decorates with expr as label", (assert) => {
        const d = el('<p><span class="rq-var">{{ foo.bar }}</span></p>');
        decorateVars(d, {});
        assert.strictEqual(d.querySelector(".rq-var").textContent, "foo.bar");
        assert.ok(d.querySelector(".rq-var").classList.contains("rq-var-unknown"));
        assert.strictEqual(cleanVarsHtml(d.innerHTML), '<p><span class="rq-var">{{ foo.bar }}</span></p>');
    });
    QUnit.test("redecorate keeps the same text node (idempotent)", (assert) => {
        const d = el('<p><span class="rq-var">{{ criterio[\'tolerancia\'] }}</span></p>');
        decorateVars(d, CAT);
        const textNode = d.querySelector(".rq-var").firstChild;
        decorateVars(d, CAT);
        assert.strictEqual(d.querySelector(".rq-var").firstChild, textNode);
    });
    QUnit.test("clean leaves html without variables untouched", (assert) => {
        const src = '<p style="color:red">A&nbsp;B</p>';
        assert.strictEqual(cleanVarsHtml(src), src);
    });
});
