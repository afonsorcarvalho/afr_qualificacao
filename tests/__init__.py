"""Testes do módulo afr_qualificacao."""

from . import test_configurator
from . import test_so_confirm_generation
from . import test_qty_delivered_propagation
from . import test_certificate
from . import test_quotation_report
# F1 (16.0.3.0.0)
from . import test_os_workflow
from . import test_relatorio_time_compute
# F2 (16.0.3.1.0)
from . import test_quote_first_os
# F3 (16.0.3.2.0)
from . import test_procedimento_explosion
from . import test_collect_item_lifecycle
# F4 (16.0.3.3.0)
from . import test_standard_instruments
# F4.3 (16.0.3.4.0)
from . import test_coverage
# F6.1 (16.0.3.5.0)
from . import test_docx_render
# F8.1 (16.0.4.0.0)
from . import test_proposal_catalog
# F8.2 (16.0.4.1.0)
from . import test_proposal_builder
# F8.3 (16.0.4.2.0)
from . import test_proposal_report
# F8.4 (16.0.4.3.0)
from . import test_configurator_steps
# F8.5 (16.0.4.4.0)
from . import test_proposal_block_edit
# F8.8 (16.0.4.7.0)
from . import test_qo_cycles
# F8.14 (16.0.4.x.0)
from . import test_estimated_hours
# 16.0.4.20.0 — billing em horas × contagem de ciclos
from . import test_hours_vs_cycles
# F10 (16.0.5.0.0) — plano de recursos metrológicos
from . import test_resource_plan

from . import test_qi_qs_seed

from . import test_proposal_venda_calibracao

from . import test_work_hours_per_day

# 16.0.5.9.0 — atributo Parte + variantes QI/QO
from . import test_partes_qi_qo

# 16.0.5.10.0 — SO/OS sequence naming C[YY]-[MM]-NNNN
from . import test_sequence_naming

# Process type label for equipment category
from . import test_process_type

# Opcional aceito — qty/total/geração condicionados a optional_accepted
from . import test_optional_accepted

# Fase 2 — opcionais no wizard configurador (serviço + qualificação)
from . import test_optional_wizard

# Fase 3 — subtotal de referência dos opcionais (mesmo não aceitos)
from . import test_optional_ref_subtotal

# Fase 4 — toggle de opcional pelo portal
from . import test_portal_optional

# Descrição de venda por variante (product.product)
from . import test_variant_description

# 16.0.5.20.0 — remoção step/deviation + aba Coletas
from . import test_remove_models_coletas
