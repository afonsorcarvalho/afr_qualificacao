"""Relatório Final P4 Task 9, fix round 4 (ruling R4).

O token do aprovador do cliente saiu da coluna `access_token` de
`afr_relatorio_aprovacao` para o modelo `afr.relatorio.aprovacao.secret`.
Copia os tokens existentes (só linhas `cliente`), esvazia a coluna antiga
(que o Odoo não remove) e apaga o mail.template antigo (noupdate, editável
por usuário interno). Idempotente: rodar de novo não copia nada.
"""

from odoo import SUPERUSER_ID, api

LEGACY_TEMPLATE = "afr_qualificacao.mail_template_relatorio_aprovacao"


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = 'afr_relatorio_aprovacao' AND column_name = 'access_token'
    """)
    if cr.fetchone():
        cr.execute("""
            INSERT INTO afr_relatorio_aprovacao_secret
                   (aprovacao_id, token, create_uid, write_uid, create_date, write_date)
            SELECT id, access_token, %s, %s, now() at time zone 'UTC', now() at time zone 'UTC'
              FROM afr_relatorio_aprovacao
             WHERE papel = 'cliente' AND COALESCE(access_token, '') <> ''
            ON CONFLICT (aprovacao_id) DO NOTHING
        """, [SUPERUSER_ID, SUPERUSER_ID])
        cr.execute("""
            UPDATE afr_relatorio_aprovacao SET access_token = NULL
             WHERE access_token IS NOT NULL
        """)
    env = api.Environment(cr, SUPERUSER_ID, {})
    template = env.ref(LEGACY_TEMPLATE, raise_if_not_found=False)
    if template:
        template.unlink()
