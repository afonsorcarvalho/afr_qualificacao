"""Inicializa os modelos do módulo afr_qualificacao."""

from . import product_service_mixin
from . import sensor_kind
from . import qualificacao_standard
from . import cycle_type
from . import malha_type
from . import config_template
from . import proposal_section          # F8.1 (16.0.4.0.0)
from . import proposal_template         # F8.1 (16.0.4.0.0)
from . import proposal_optional         # F8.1 (16.0.4.0.0)
from . import proposal_block            # F8.2 (16.0.4.1.0)
from . import qualificacao_type_config
from . import qualificacao_cycle
from . import qualificacao_malha
from . import qualificacao_os           # F1 (16.0.3.0.0)
from . import qualificacao_os_relatorio # F1 (16.0.3.0.0)
from . import qualificacao_procedimento # F3 (16.0.3.2.0)
from . import qualificacao_collect_item # F3 (16.0.3.2.0)
from . import qualificacao
from . import docx_template
from . import sale_order_line
from . import sale_order
from . import sale_order_form_panels
from . import engc_os
from . import res_config_settings        # F4 (16.0.3.3.0)
from . import calibration_instruments    # F4 (16.0.3.3.0)
from . import resource_plan              # F10 (16.0.5.0.0)
from . import engc_equipment             # F10.5 (16.0.5.4.0)
from . import res_partner                 # F10.6 (16.0.5.5.0)
from . import engc_equipment_category
from . import product_product
