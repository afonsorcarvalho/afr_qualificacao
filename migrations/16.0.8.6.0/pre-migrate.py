"""Anexos unificados (spec 2026-09-29): o kind `anexo_separador` saiu de
REPORT_BLOCK_KINDS — a página separadora nasce do próprio anexo. Apaga os
separadores legados dos relatórios e templates antes do registry carregar a
selection nova. Idempotente."""


def migrate(cr, version):
    cr.execute("DELETE FROM afr_relatorio_block WHERE block_kind = 'anexo_separador'")
    cr.execute(
        "DELETE FROM afr_relatorio_template_line WHERE block_kind = 'anexo_separador'")
