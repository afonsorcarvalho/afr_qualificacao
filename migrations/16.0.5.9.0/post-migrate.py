"""Wire catálogo QO (operational) + variantes 'Parte' QI/QO em upgrade.

A fiação de catálogo desta feature — type_config 'operational' (QO), as
variantes de produto QI/QO por atributo 'Parte', e a associação do atributo
'Parte' aos templates — é criada APENAS no post_init_hook
`_install_qualif_type_configs`, que roda só em install fresh, NÃO em
`-u afr_qualificacao`.

Sem esta migração, ao atualizar uma DB existente (ex.: labquali) o
`do_qo_part01` levanta UserError "Sem configuração de produto para QO",
pois o type_config operational nunca foi criado.

Os *valores* do atributo 'Parte' são seedados via data XML (que carrega em
upgrade), então neste ponto o env.ref ao atributo/valores já resolve; a
criação das variantes/type_config é código no hook, daí chamá-lo aqui.

O hook é idempotente — só cria o que falta (type_configs ausentes,
variantes ausentes), portanto re-execuções são seguras.
"""

from odoo import api, SUPERUSER_ID

from odoo.addons.afr_qualificacao.hooks import _install_qualif_type_configs


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _install_qualif_type_configs(env)
