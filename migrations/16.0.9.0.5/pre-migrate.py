"""Backfill company_id NULL em afr_qualificacao_config_template.

company_id virou required em 16.0.9.0.0; linhas antigas sem empresa
impediriam o NOT NULL. Atribui a primeira empresa (menor id).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('afr_qualificacao_config_template')")
    if not cr.fetchone()[0]:
        return
    cr.execute("""
        UPDATE afr_qualificacao_config_template
           SET company_id = (SELECT id FROM res_company ORDER BY id LIMIT 1)
         WHERE company_id IS NULL
    """)
    if cr.rowcount:
        _logger.info("config_template: company_id preenchido em %s linhas",
                     cr.rowcount)
