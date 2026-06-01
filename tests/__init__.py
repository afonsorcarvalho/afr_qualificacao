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
