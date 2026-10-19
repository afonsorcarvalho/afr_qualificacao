"""Anexos unificados (spec 2026-09-29): o kind `anexo_separador` saiu de
REPORT_BLOCK_KINDS — a página separadora nasce do próprio anexo. Apaga os
separadores legados dos relatórios e templates antes do registry carregar a
selection nova. Idempotente.

Bancos que pulam de <8.x direto para cá (ex.: 7.5.3 -> 8.9.x) ainda não têm
essas tabelas — elas nascem no próprio -u, depois dos pre-migrates. Nada a
apagar nesse caso."""

TABLES = ("afr_relatorio_block", "afr_relatorio_template_line")


def migrate(cr, version):
    for table in TABLES:
        cr.execute("SELECT to_regclass(%s)", ("public.%s" % table,))
        if cr.fetchone()[0] is None:
            continue
        cr.execute(
            "DELETE FROM %s WHERE block_kind = 'anexo_separador'" % table)
