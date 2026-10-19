"""Module install hooks (post_init).

post_init_hook roda APENAS no install inicial — NÃO em upgrades.
Permite que dados seed (template de proposta) sejam criados uma vez
e o utilizador possa editar/eliminar sem que voltem em upgrades futuros.

Para dados que devem permanecer atualizáveis (sections, opcionais, etc.),
manter em data/*.xml com noupdate="1".
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


# Estrutura do template default "Proposta LabQuali QI/QO/QD".
# Tuple por linha: (xmlid_suffix, sequence, block_kind, section_xmlid|None,
#                   page_break, parent_xmlid_suffix|None)
PROPOSAL_TEMPLATE_LINES = [
    ("l01", 10, "static", "proposal_section_objetivo", True, None),
    ("l02", 20, "static", "proposal_section_metodologia", False, None),
    ("l02b", 25, "static", "proposal_section_qualif_termica", False, None),
    ("l03", 30, "static", "proposal_section_qi", False, "l02b"),
    ("l04", 40, "static", "proposal_section_qo", False, "l02b"),
    ("l05", 50, "static", "proposal_section_qd", False, "l02b"),
    ("l06", 60, "equipment_scope", None, True, None),
    ("l08", 80, "static", "proposal_section_validadores", False, None),
    ("l09", 90, "standards_table", None, False, None),
    ("l10", 100, "static", "proposal_section_normas", False, None),
    ("l11", 110, "static", "proposal_section_entregaveis", False, None),
    ("l14", 140, "static", "proposal_section_responsabilidades", True, None),
    ("l15", 150, "static", "proposal_section_condicoes", False, None),
    ("l16", 160, "static", "proposal_section_credenciais", False, None),
    ("l17", 170, "acceptance", None, True, None),
    ("l18", 180, "static", "proposal_section_aceite", False, None),
]


PARTE_01_NAME = "Parte 01"

# Produtos serviço genéricos por tipo (preço 0; comercial ajusta no
# orçamento). Tuple: (xmlid_suffix, nome, has_parte).
# NOTA: os sufixos usam o pós-fixo `_tmpl` para NÃO colidirem com os xmlids
# antigos `product_qi_service`/`product_qs_service` que o 16.0.5.7.0 registrou
# como `product.product`. Estes aqui são `product.template`. Ver migration
# 16.0.5.9.0 / _ensure_parte_repoint.
QUALIF_SERVICE_PRODUCTS = {
    "installation": ("product_qi_service_tmpl", "Qualificação de Instalação (QI)", True),
    "operational": ("product_qo_service_tmpl", "Qualificação de Operação (QO)", True),
    "software": ("product_qs_service_tmpl", "Qualificação de Software (QS)", False),
}


def _parte_variant(template, value_name):
    """Retorna o product.product do template cujo valor de atributo Parte == value_name."""
    for variant in template.product_variant_ids:
        names = variant.product_template_variant_value_ids.mapped("name")
        if value_name in names:
            return variant
    _logger.warning(
        "Parte variant '%s' não encontrado no template %s — usando variante padrão.",
        value_name, template.display_name,
    )
    return template.product_variant_id  # fallback (sem atributo)


def _install_qualif_type_configs(env):
    """Garante produtos serviço + type.config p/ QI, QO e QS no install.

    QI e QO recebem o atributo 'Parte' (Parte 01 / Parte 02) → 2 variantes cada.
    type_config installation/operational apontam para o variante Parte 01.

    Idempotente e multi-company: só cria o que falta. Em DBs que já têm os
    registros (labquali configurado manualmente), não faz nada — preserva
    a customização. Roda só no install (post_init), nunca em upgrade, logo
    nunca colide com a constraint unique(qualification_type, company_id).
    """
    Template = env["product.template"]
    TypeConfig = env["afr.qualificacao.type.config"]
    ImdData = env["ir.model.data"]
    attr = env.ref("afr_qualificacao.product_attribute_parte", raise_if_not_found=False)
    val01 = env.ref("afr_qualificacao.product_attribute_value_parte_01", raise_if_not_found=False)
    val02 = env.ref("afr_qualificacao.product_attribute_value_parte_02", raise_if_not_found=False)

    tmpl_by_type = {}
    for qtype, (suffix, name, has_parte) in QUALIF_SERVICE_PRODUCTS.items():
        tmpl = env.ref(f"afr_qualificacao.{suffix}", raise_if_not_found=False)
        if not tmpl:
            tmpl = Template.create({
                "name": name,
                "type": "service",
                "detailed_type": "service",
                "sale_ok": True,
                "purchase_ok": False,
                "list_price": 0.0,
            })
            ImdData.create({
                "name": suffix,
                "module": "afr_qualificacao",
                "model": "product.template",
                "res_id": tmpl.id,
                "noupdate": True,
            })
        # Adiciona atributo Parte se ainda não tiver e o atributo seed existe.
        if has_parte and attr and val01 and val02 and not tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id == attr
        ):
            tmpl.write({"attribute_line_ids": [(0, 0, {
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [val01.id, val02.id])],
            })]})
        tmpl_by_type[qtype] = tmpl

    # type.config por empresa. active_test=False p/ não recriar sobre um
    # registro inativo e violar a constraint unique.
    for company in env["res.company"].search([]):
        for qtype in ("installation", "operational", "software"):
            has_parte = QUALIF_SERVICE_PRODUCTS[qtype][2]
            exists = TypeConfig.with_context(active_test=False).search([
                ("qualification_type", "=", qtype),
                ("company_id", "=", company.id),
            ], limit=1)
            if exists:
                # software (sem Parte): preserva a config existente como antes.
                if not has_parte:
                    continue
                # installation/operational: em DBs upgradeadas de <16.0.5.9.0,
                # a config existente aponta para o produto QI/QO ANTIGO (sem
                # atributo Parte / sem variantes). Repointa SIMETRICAMENTE para
                # a variante Parte 01 do PRODUTO-SEMENTE (_tmpl), tal como o
                # fresh-install — não muta o produto antigo do utilizador.
                _ensure_parte_repoint(exists, tmpl_by_type[qtype])
                continue
            tmpl = tmpl_by_type[qtype]
            product = _parte_variant(tmpl, PARTE_01_NAME) if has_parte else tmpl.product_variant_id
            TypeConfig.create({
                "qualification_type": qtype,
                "company_id": company.id,
                "service_product_id": product.id,
                "default_unit_price": 0.0,
                "estimated_hours": 0.0,
            })


def _ensure_parte_repoint(cfg, seed_tmpl):
    """Repointa um type_config installation/operational existente para a
    variante 'Parte 01' do PRODUTO-SEMENTE (`seed_tmpl`).

    Comportamento SIMÉTRICO ao fresh-install: em vez de mutar o produto antigo
    do utilizador (anexando o atributo Parte / arquivando variantes), aponta a
    config para a variante Parte 01 do template-semente já preparado (que tem
    o atributo Parte + 2 variantes desde o 1º loop de _install_qualif_type_configs).
    O produto antigo fica intocado (apenas deixa de ser usado).

    Idempotente: se a config já aponta para a variante Parte 01 do seed, não
    faz nada.
    """
    if not seed_tmpl:
        return
    target = _parte_variant(seed_tmpl, PARTE_01_NAME)
    if cfg.service_product_id != target:
        cfg.service_product_id = target


# Backward-compat alias — mantém imports existentes funcionando.
_install_qi_qs_type_config = _install_qualif_type_configs


def _ensure_company_data_block(env):
    """Garante o bloco institucional 'Dados Cadastrais' no template QI/QO/QD.

    Idempotente: acrescenta 1 linha static (seção SEC-DADOS-CADASTRAIS) ao
    template proposal_template_labquali se ainda não existir, posicionada
    logo antes do bloco de aceite (ou ao final, se não houver aceite).
    Chamado pelo post_init (fresh-install) e pela migration 16.0.5.7.0
    (upgrade na labquali).
    """
    section = env.ref(
        "afr_qualificacao.sec_dados_cadastrais", raise_if_not_found=False
    )
    template = env.ref(
        "afr_qualificacao.proposal_template_labquali", raise_if_not_found=False
    )
    if not section or not template:
        return
    if template.line_ids.filtered(lambda l: l.section_id == section):
        return  # já tem
    used = set(template.line_ids.mapped("sequence"))
    acceptance = template.line_ids.filtered(
        lambda l: l.block_kind == "acceptance"
    )
    if acceptance:
        seq = min(acceptance.mapped("sequence")) - 1
    else:
        seq = max(used or [0]) + 10
    # evita colisão de sequence (ordem determinística: _order = sequence, id)
    while seq in used:
        seq -= 1
    env["afr.proposal.template.line"].create({
        "template_id": template.id,
        "sequence": seq,
        "block_kind": "static",
        "section_id": section.id,
    })


# ─────────────────────────────────────────────────────────────────────────
# Relatório Final de Qualificação (P3) — seções, templates, checklist, anexos
# Texto genérico (sem cliente). Edições de norma NÃO fixadas: a edição
# aplicável varia por cliente e é citada no protocolo.
# ─────────────────────────────────────────────────────────────────────────

# (xmlid_suffix, code, name, category, body_html)
RELATORIO_SECTIONS = [
    ("rqt_sec_objetivo", "RQT-OBJETIVO", "Objetivo", "objetivo",
     "<p>Este relatório apresenta os resultados da Qualificação Térmica do "
     "equipamento <strong>{{ equipment.name }}</strong>, número de série "
     "<strong>{{ equipment.serial_number }}</strong>, de <strong>{{ partner.name }}</strong>, "
     "realizada para demonstrar, por meio de evidências documentadas, que o equipamento "
     "está instalado adequadamente, opera dentro dos limites especificados e produz, de "
     "forma reprodutível, resultados que atendem aos critérios de aceitação estabelecidos.</p>"
     "<p>Os ensaios seguiram o protocolo apresentado no Anexo {{ anexo('protocolo') }} "
     "deste relatório.</p>"),
    ("rqt_sec_normas", "RQT-NORMAS", "Normas e Referências", "normas",
     "<ul>"
     "<li>ABNT NBR ISO 17665 — Esterilização de produtos para saúde — Vapor — Requisitos "
     "para o desenvolvimento, validação e controle de rotina de processos de esterilização.</li>"
     "<li>ABNT NBR 16328 — Esterilização de produtos para saúde — Vapor — Esterilizadores "
     "a vapor de pequeno porte.</li>"
     "<li>ABNT NBR ISO 11138 — Esterilização de produtos para saúde — Indicadores biológicos.</li>"
     "<li>ABNT NBR ISO 11140 — Esterilização de produtos para saúde — Indicadores químicos.</li>"
     "<li>Legislação sanitária aplicável ao processamento de produtos para saúde.</li>"
     "</ul>"
     "<p>Aplicam-se as edições indicadas no protocolo (Anexo {{ anexo('protocolo') }}).</p>"),
    ("rqt_sec_definicoes", "RQT-DEFINICOES", "Termos e Definições", "tecnico",
     "<ul>"
     "<li><strong>Qualificação de Instalação (QI):</strong> verificação documentada de que o "
     "equipamento e suas utilidades foram fornecidos e instalados conforme a especificação.</li>"
     "<li><strong>Qualificação de Operação (QO):</strong> verificação documentada de que o "
     "equipamento opera dentro dos limites predeterminados, com a câmara vazia.</li>"
     "<li><strong>Qualificação de Desempenho (QD):</strong> verificação documentada de que o "
     "equipamento, operando com cargas de referência, produz resultados consistentes com os "
     "critérios de aceitação.</li>"
     "<li><strong>Tempo de equilíbrio:</strong> intervalo entre o instante em que o ponto de "
     "referência atinge a temperatura de esterilização e o instante em que todos os pontos a "
     "atingem.</li>"
     "<li><strong>Tempo de manutenção (período de esterilização):</strong> intervalo em que todos "
     "os pontos permanecem na faixa de temperatura de esterilização.</li>"
     "<li><strong>F0:</strong> letalidade acumulada expressa em minutos equivalentes a 121,1 °C, "
     "com z = 10 °C.</li>"
     "<li><strong>Valor D:</strong> tempo, em minutos, para reduzir em 90% a população do "
     "microrganismo de referência na condição especificada.</li>"
     "<li><strong>Indicador biológico (IB) / Indicador químico (IQ):</strong> dispositivos de "
     "desafio usados para evidenciar a letalidade e a exposição ao agente esterilizante.</li>"
     "</ul>"),
    ("rqt_sec_procedimento", "RQT-PROCEDIMENTO", "Procedimento de Qualificação", "tecnico",
     "<p>A qualificação foi executada conforme o protocolo do Anexo {{ anexo('protocolo') }}, "
     "com sensores de temperatura calibrados distribuídos na câmara e nas cargas segundo a "
     "disposição registrada no protocolo. Os valores coletados pelo sistema de aquisição "
     "encontram-se no Anexo {{ anexo('dados') }} e os gráficos no Anexo {{ anexo('graficos') }}.</p>"),
    ("rqt_sec_qi", "RQT-QI", "Qualificação de Instalação (QI)", "tecnico",
     "<p>Foram verificados as instalações elétricas, as utilidades, a documentação, os "
     "componentes, as calibrações das malhas de controle e o treinamento dos operadores, "
     "conforme a lista de verificação do protocolo. Itens reprovados, quando houver, estão "
     "registrados com comentário e ação recomendada.</p>"),
    ("rqt_sec_qo", "RQT-QO", "Qualificação de Operação (QO)", "tecnico",
     "<p>Foram executados ciclos com a câmara vazia para verificar a distribuição de "
     "temperatura, o funcionamento dos controles, indicadores e alarmes, e a repetibilidade "
     "dos parâmetros programados.</p>"),
    ("rqt_sec_qd", "RQT-QD", "Qualificação de Desempenho (QD)", "tecnico",
     "<p>Foram executados ciclos com carga de referência representativa da pior condição de "
     "uso, com sensores posicionados nos pontos de mais difícil penetração de calor e "
     "indicadores biológicos e químicos distribuídos conforme o protocolo.</p>"),
    ("rqt_sec_micro", "RQT-MICRO", "Avaliação Microbiológica", "tecnico",
     "<p>Os indicadores biológicos processados foram incubados juntamente com um controle "
     "positivo não processado do mesmo lote. Os resultados constam do laudo microbiológico "
     "no Anexo {{ anexo('micro') }}.</p>"),
    ("rqt_sec_qdf", "RQT-QDF", "Qualificação de Desempenho Física (QDF)", "tecnico",
     "<p>Foram executados ciclos com carga de referência, com sensores de temperatura e "
     "pressão posicionados nos pontos críticos da carga e da câmara. Quando aplicável, foram "
     "realizados o teste de estanqueidade (vazamento de ar) e o teste de remoção de ar e "
     "penetração de vapor (Bowie-Dick).</p>"),
    ("rqt_sec_qdm", "RQT-QDM", "Qualificação de Desempenho Microbiológica (QDM)", "tecnico",
     "<p>Os indicadores biológicos foram posicionados nos pontos de pior caso da carga e "
     "encaminhados ao laboratório indicado pelo cliente. O laudo emitido pelo laboratório "
     "consta do Anexo {{ anexo('micro') }}.</p>"),
    ("rqt_sec_certificacao", "RQT-CERTIFICACAO", "Certificação dos Instrumentos", "normas",
     "<p>O sistema de aquisição de dados foi calibrado antes e depois da campanha de ensaios "
     "(Anexo {{ anexo('validador') }}), contra padrões com rastreabilidade metrológica "
     "(Anexo {{ anexo('padroes') }}). Os certificados das malhas de controle do equipamento "
     "constam do Anexo {{ anexo('malhas') }}.</p>"),
    ("rqt_sec_criterios", "RQT-CRITERIOS", "Critérios de Aceitação", "tecnico",
     "<ul>"
     "<li>Durante o período de esterilização, todas as temperaturas medidas devem permanecer "
     "entre a temperatura nominal do ciclo e a temperatura nominal acrescida de "
     "{{ criterio['tolerancia'] }} °C.</li>"
     "<li>O F0 acumulado em cada ponto deve ser igual ou superior a {{ criterio['f0_fator'] }} "
     "vezes o valor D do indicador biológico utilizado (valor D = {{ criterio['valor_d'] }} min; "
     "F0 mínimo = {{ criterio['f0_minimo'] }} min).</li>"
     "<li>Todos os indicadores biológicos processados devem apresentar resultado negativo e o "
     "controle positivo, crescimento.</li>"
     "<li>Todos os indicadores químicos devem apresentar viragem completa.</li>"
     "</ul>"),
    ("rqt_sec_validade", "RQT-VALIDADE", "Validade", "condicoes",
     "<p>Os resultados deste relatório são válidos por 12 (doze) meses a partir da data de "
     "emissão, ou até que ocorra manutenção corretiva relevante, mudança do local de "
     "instalação, alteração dos parâmetros dos ciclos ou da configuração das cargas — "
     "situações que exigem requalificação.</p>"),
    ("rqt_sec_conclusao", "RQT-CONCLUSAO", "Conclusão", "custom",
     "<p>Com base nos resultados obtidos e nos critérios de aceitação estabelecidos, o "
     "equipamento {{ equipment.name }}, número de série {{ equipment.serial_number }}, foi "
     "considerado <strong>QUALIFICADO</strong> para os ciclos avaliados, conforme detalhado "
     "nos anexos deste relatório.</p>"),
    ("rqt_sec_protocolo_textos", "RQT-PROTOCOLO-TEXTOS",
     "Procedimentos, Segurança da Informação e Responsabilidades", "custom",
     "<p><strong>Procedimentos.</strong> Os sensores são instalados conforme a disposição "
     "registrada neste protocolo; os ciclos são executados na quantidade e nos parâmetros "
     "indicados; a aquisição é contínua, com intervalo configurado no sistema de aquisição.</p>"
     "<p><strong>Segurança da informação.</strong> Os dados brutos do sistema de aquisição são "
     "preservados sem edição, com acesso restrito à equipe técnica; os arquivos anexados a este "
     "relatório são cópias fiéis dos originais.</p>"
     "<p><strong>Responsabilidades.</strong> Contratada: planejamento, execução dos ensaios, "
     "análise dos dados e emissão do relatório. Cliente ({{ partner.name }}): disponibilizar o "
     "equipamento, as utilidades e as cargas representativas, e designar responsável para "
     "acompanhar os ensaios.</p>"),
]

# Checklist QI: (grupo, descricao)
RELATORIO_CHECKLIST_BASE = [
    ("Instalações elétricas", "Tensão de alimentação compatível com a placa de identificação"),
    ("Instalações elétricas", "Aterramento elétrico presente e adequado"),
    ("Instalações elétricas", "Circuito de alimentação exclusivo, com proteção"),
    ("Utilidades", "Água de alimentação com qualidade conforme recomendação do fabricante"),
    ("Utilidades", "Ponto de drenagem/exaustão adequado"),
    ("Utilidades", "Ventilação do ambiente de instalação adequada"),
    ("Documentação", "Manual de operação do fabricante disponível"),
    ("Documentação", "Registro do equipamento no órgão sanitário (quando aplicável)"),
    ("Documentação", "Registros de manutenção preventiva disponíveis"),
    ("Componentes", "Placa de identificação legível (fabricante, modelo, número de série)"),
    ("Componentes", "Porta, trava e guarnição de vedação íntegras"),
    ("Componentes", "Indicadores de temperatura e pressão funcionais"),
    ("Componentes", "Registrador/impressora de ciclo funcional (quando aplicável)"),
    ("Calibrações", "Malhas de controle (temperatura, pressão e tempo) com calibração vigente"),
    ("Treinamentos", "Operadores treinados na operação do equipamento"),
]
RELATORIO_CHECKLIST_IND_EXTRA = [
    ("Utilidades", "Linha de vapor/gerador de vapor com pressão e qualidade adequadas"),
    ("Utilidades", "Ar comprimido com pressão adequada (quando aplicável)"),
    ("Componentes", "Bomba de vácuo funcional"),
    ("Componentes", "Filtro de ar de admissão íntegro e dentro da validade"),
]

# Linhas: (suffix, seq, block_kind, section_suffix|None, page_break,
#          parent_suffix|None, show_number, show_title, anexo_code|None, title|None)
_RQT_HEAD = [
    ("l010", 10, "capa", None, False, None, False, False, None, "Capa"),
    ("l020", 20, "indice", None, True, None, False, True, None, "Sumário"),
    ("l030", 30, "static", "rqt_sec_objetivo", True, None, True, True, None, None),
    ("l040", 40, "static", "rqt_sec_normas", False, None, True, True, None, None),
    ("l050", 50, "static", "rqt_sec_definicoes", False, None, True, True, None, None),
    ("l060", 60, "static", "rqt_sec_procedimento", True, None, True, True, None, None),
    ("l070", 70, "static", "rqt_sec_qi", False, "l060", True, True, None, None),
    ("l080", 80, "static", "rqt_sec_qo", False, "l060", True, True, None, None),
]
_RQT_TAIL = [
    ("l110", 110, "static", "rqt_sec_certificacao", True, None, True, True, None, None),
    ("l120", 120, "static", "rqt_sec_criterios", False, None, True, True, None, None),
    ("l130", 130, "static", "rqt_sec_validade", False, None, True, True, None, None),
    ("l140", 140, "static", "rqt_sec_conclusao", False, None, True, True, None, None),
    ("l150", 150, "assinaturas", None, False, None, True, True, None, "Quadro de Assinaturas"),
]


# Anexos: (code, seq, title, slot_kind, collect_sections, cert_roles, included_default)
_RQT_DADOS_SECTIONS = (
    "qo_mapeamento_ciclo1,qo_mapeamento_ciclo2,qo_mapeamento_ciclo3,"
    "qd_penetracao_ciclo1,qd_penetracao_ciclo2,qd_penetracao_ciclo3"
)
RELATORIO_ANEXOS_HOSP = [
    ("protocolo", 10, "Protocolo de Qualificação Térmica", "bloco", "", "", True),
    ("dados", 20, "Resultados dos Valores Coletados", "collect_section", _RQT_DADOS_SECTIONS, "", True),
    ("graficos", 30, "Gráficos dos Ciclos", "upload", "", "", True),
    ("micro", 40, "Laudo Microbiológico", "bloco", "", "", True),
    ("f0", 50, "Curvas de Letalidade (F0)", "upload", "", "", True),
    ("malhas", 60, "Certificados de Calibração das Malhas de Controle", "malha_certs", "", "", True),
    ("validador", 70, "Certificados de Calibração do Sistema de Aquisição", "instrument_certs", "", "antes,depois", True),
    ("padroes", 80, "Certificados dos Padrões de Referência", "instrument_certs", "", "externo", True),
]
RELATORIO_ANEXOS_IND = [
    ("protocolo", 10, "Protocolo de Qualificação Térmica", "bloco", "", "", True),
    ("protocolo_cliente", 20, "Protocolo do Cliente", "upload", "", "", True),
    ("dados", 30, "Resultados dos Valores Coletados", "collect_section", _RQT_DADOS_SECTIONS, "", True),
    ("graficos", 40, "Gráficos dos Ciclos", "upload", "", "", True),
    ("impressoes", 50, "Registros Impressos pelo Equipamento", "upload", "", "", True),
    ("micro", 60, "Laudo Microbiológico (Laboratório do Cliente)", "upload", "", "", True),
    ("f0", 70, "Curvas de Letalidade (F0)", "upload", "", "", True),
    ("malhas", 80, "Certificados de Calibração das Malhas de Controle", "malha_certs", "", "", True),
    ("validador", 90, "Certificados de Calibração do Sistema de Aquisição", "instrument_certs", "", "antes,depois", True),
    ("padroes", 100, "Certificados dos Padrões de Referência", "instrument_certs", "", "externo", True),
]

RELATORIO_TEMPLATES = [
    {
        "xmlid": "relatorio_template_hosp",
        "name": "Relatório de Qualificação — Hospitalar",
        "code": "RQT-HOSP",
        "sequence": 10,
        "category_xmlids": ["cat_autoclave_vapor"],
        "lines": (
            _RQT_HEAD
            + [
                ("l090", 90, "static", "rqt_sec_qd", False, "l060", True, True, None, None),
                ("l100", 100, "static", "rqt_sec_micro", False, "l060", True, True, None, None),
            ]
            + _RQT_TAIL
            + [
                ("c_protocolo", 900, "protocolo", "rqt_sec_protocolo_textos", False, None,
                 False, False, "protocolo", "Protocolo de Qualificação Térmica"),
                ("c_micro", 910, "laudo_micro", None, False, None,
                 False, False, "micro", "Laudo Microbiológico"),
            ]
        ),
        "checklist": RELATORIO_CHECKLIST_BASE,
        "anexos": RELATORIO_ANEXOS_HOSP,
    },
    {
        "xmlid": "relatorio_template_ind",
        "name": "Relatório de Qualificação — Industrial",
        "code": "RQT-IND",
        "sequence": 20,
        "category_xmlids": [],
        "lines": (
            _RQT_HEAD
            + [
                ("l090", 90, "static", "rqt_sec_qdf", False, "l060", True, True, None, None),
                ("l100", 100, "static", "rqt_sec_qdm", False, "l060", True, True, None, None),
            ]
            + _RQT_TAIL
            + [
                ("c_protocolo", 900, "protocolo", "rqt_sec_protocolo_textos", False, None,
                 False, False, "protocolo", "Protocolo de Qualificação Térmica"),
            ]
        ),
        "checklist": RELATORIO_CHECKLIST_BASE + RELATORIO_CHECKLIST_IND_EXTRA,
        "anexos": RELATORIO_ANEXOS_IND,
    },
]


def _upsert_xmlid(env, name, record):
    """Registra/reaponta afr_qualificacao.<name> (noupdate) para `record`."""
    Imd = env["ir.model.data"]
    imd = Imd.search([("module", "=", "afr_qualificacao"), ("name", "=", name)], limit=1)
    vals = {"model": record._name, "res_id": record.id, "noupdate": True}
    if imd:
        imd.write(vals)
    else:
        Imd.create(dict(vals, name=name, module="afr_qualificacao"))


def _seed_relatorio_templates(env):
    """Cria seções de relatório e templates RQT-HOSP / RQT-IND.

    Idempotente: registro cujo xmlid já resolve não é tocado (o usuário
    controla o conteúdo depois do seed). Chamado pelo hook de install e pela
    migração 16.0.8.2.0.
    """
    Section = env["afr.proposal.section"]
    sections = {}
    for seq, (suffix, code, name, category, body) in enumerate(RELATORIO_SECTIONS, start=1):
        rec = env.ref("afr_qualificacao.%s" % suffix, raise_if_not_found=False)
        if not rec:
            rec = Section.create({
                "name": name, "code": code, "category": category,
                "document_type": "report", "body": body, "sequence": 1000 + seq * 10,
            })
            _upsert_xmlid(env, suffix, rec)
        sections[suffix] = rec

    Template = env["afr.relatorio.template"]
    Line = env["afr.relatorio.template.line"]
    for spec in RELATORIO_TEMPLATES:
        if env.ref("afr_qualificacao.%s" % spec["xmlid"], raise_if_not_found=False):
            continue
        categories = [
            env.ref("afr_qualificacao.%s" % x, raise_if_not_found=False)
            for x in spec["category_xmlids"]
        ]
        template = Template.create({
            "name": spec["name"],
            "code": spec["code"],
            "sequence": spec["sequence"],
            "equipment_category_ids": [(6, 0, [c.id for c in categories if c])],
            "checklist_line_ids": [
                (0, 0, {"sequence": (i + 1) * 10, "grupo": grupo, "descricao": desc})
                for i, (grupo, desc) in enumerate(spec["checklist"])
            ],
            "anexo_line_ids": [
                (0, 0, {
                    "code": code, "sequence": seq, "title": title, "slot_kind": slot,
                    "collect_sections": sects or False, "cert_roles": roles or False,
                    "included_default": inc,
                })
                for code, seq, title, slot, sects, roles, inc in spec["anexos"]
            ],
        })
        _upsert_xmlid(env, spec["xmlid"], template)
        by_suffix = {}
        for (suffix, seq, kind, sec_suffix, page_break, _parent,
             show_number, show_title, anexo_code, title) in spec["lines"]:
            section = sections.get(sec_suffix) if sec_suffix else False
            line = Line.create({
                "template_id": template.id,
                "sequence": seq,
                "block_kind": kind,
                "section_id": section.id if section else False,
                "page_break": page_break,
                "show_number": show_number,
                "show_title": show_title,
                "anexo_code": anexo_code or False,
                "title": title or False,
            })
            by_suffix[suffix] = line
        for (suffix, _seq, _kind, _sec, _pb, parent_suffix, *_rest) in spec["lines"]:
            if parent_suffix and parent_suffix in by_suffix:
                by_suffix[suffix].parent_id = by_suffix[parent_suffix].id


def _install_proposal_template_seed(cr, registry):
    """Cria o template default ‘Proposta LabQuali QI/QO/QD’ no install.

    Idempotente: se o xmlid já existe, retorna sem fazer nada.
    Registra ir.model.data com noupdate=True para que env.ref() funcione
    em código (tests, futuros hooks) mas updates do módulo não recriem
    nem modifiquem o template — utilizador controla 100%.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Seed QI/QO/QS type.config (independente do template; idempotente).
    _install_qualif_type_configs(env)

    # Relatório Final (P3) — seções/templates de relatório (idempotente).
    _seed_relatorio_templates(env)

    template = env.ref(
        "afr_qualificacao.proposal_template_labquali",
        raise_if_not_found=False,
    )
    if template:
        _ensure_company_data_block(env)  # retrofit em template já existente
        return  # já instalado

    Template = env["afr.proposal.template"]
    TemplateLine = env["afr.proposal.template.line"]
    ImdData = env["ir.model.data"]

    # 1) Template
    template = Template.create({
        "name": "Proposta LabQuali QI/QO/QD",
        "code": "TPL-LABQUALI",
        "sequence": 10,
    })
    ImdData.create({
        "name": "proposal_template_labquali",
        "module": "afr_qualificacao",
        "model": "afr.proposal.template",
        "res_id": template.id,
        "noupdate": True,
    })

    # 2) Linhas — 1ª passagem: criar todas sem parent_id
    suffix_to_line = {}
    for suffix, seq, kind, section_xmlid, page_break, _parent in PROPOSAL_TEMPLATE_LINES:
        section = (
            env.ref(f"afr_qualificacao.{section_xmlid}", raise_if_not_found=False)
            if section_xmlid else False
        )
        line = TemplateLine.create({
            "template_id": template.id,
            "sequence": seq,
            "block_kind": kind,
            "section_id": section.id if section else False,
            "page_break": page_break,
        })
        ImdData.create({
            "name": f"proposal_template_labquali_{suffix}",
            "module": "afr_qualificacao",
            "model": "afr.proposal.template.line",
            "res_id": line.id,
            "noupdate": True,
        })
        suffix_to_line[suffix] = line

    # 3) 2ª passagem — propagar parent_id (hierarquia)
    for suffix, _seq, _kind, _section, _pb, parent_suffix in PROPOSAL_TEMPLATE_LINES:
        if parent_suffix:
            parent = suffix_to_line.get(parent_suffix)
            if parent:
                suffix_to_line[suffix].parent_id = parent.id

    # Bloco institucional Dados Cadastrais (após template recém-criado).
    _ensure_company_data_block(env)
