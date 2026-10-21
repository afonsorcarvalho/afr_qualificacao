"""Wizards transient do módulo afr_qualificacao."""

from . import qualificacao_configurator
from . import relatorio_wizard           # F1 (16.0.3.0.0)
from . import apply_procedimento_wizard  # F3 (16.0.3.2.0)
from . import qualificacao_os_generate_wizard  # 16.0.6.13.0 — OS por grupo
from . import leitura_ib_lote_wizard  # F11 P6 (16.0.8.4.1) — leituras de IB em lote
from . import relatorio_template_wizard  # 16.0.8.9.0 — template ao gerar Relatórios Finais
from . import client_default_confirm  # 16.0.9.0.3 — confirmar substituição do padrão do cliente
