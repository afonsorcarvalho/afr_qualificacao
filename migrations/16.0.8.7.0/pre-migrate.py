"""Anexos unificados, Task 3: a página `page_anexos` sai da aba Texto (o
conteúdo passa a viver dentro de `page_texto`, junto do corpo). A view de
Verificação (P5) ainda referencia `page[@name='page_anexos']` via xpath.

Sem corrigir isso ANTES de `views/relatorio_texto_views.xml` ser recarregado,
o `-u` quebra: `ir.ui.view._check_xml()` recombina a árvore inteira (raiz +
todas as views que herdam dela) a cada write de view do módulo — inclusive as
ainda não recarregadas nesta mesma execução. Como o manifest carrega a
Verificação depois da Texto, no instante em que a Texto perde `page_anexos`
a Verificação ainda está no banco com o xpath antigo, e a validação falha com
"Element ... cannot be located in parent view". Reordenar o manifest não
resolve: a Verificação também depende do botão `action_gerar_minuta`, que só
existe depois de `relatorio_emissao_views.xml` carregar.

Corrige o xpath direto no banco antes do carregamento dos dados/views do
módulo (todos os idiomas presentes em `arch_db`). Idempotente."""


def migrate(cr, version):
    cr.execute("""
        SELECT v.id
        FROM ir_ui_view v
        JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
        WHERE d.module = 'afr_qualificacao'
          AND d.name = 'view_afr_qualificacao_relatorio_form_verificacao'
    """)
    row = cr.fetchone()
    if not row:
        return
    cr.execute("""
        UPDATE ir_ui_view
        SET arch_db = (
            SELECT jsonb_object_agg(
                kv.key,
                to_jsonb(replace(kv.value, 'page_anexos', 'page_texto'))
            )
            FROM jsonb_each_text(arch_db) AS kv(key, value)
        )
        WHERE id = %s
          AND arch_db::text LIKE '%%page_anexos%%'
    """, (row[0],))
