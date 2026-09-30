# -*- coding: utf-8 -*-
"""Procedimento de Qualificação (template master) + linhas (procedimento.item).

Template pré-programado que define o que deve ser COLETADO em campo durante
a execução de uma qualificação (fotos cargas, dados qualificador, planilhas,
indicadores biológicos, fitas etc.).

Resolve por equipment_category_id (vazio = fallback). Explosão para
collect.items acontece em sale_order._explode_collect_items() na confirmação
do SO (F3 16.0.3.2.0).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


KIND_SELECTION = [
    ("foto", "Foto"),
    ("excel", "Planilha Excel/CSV"),
    ("pdf", "PDF"),
    ("qualificador_data", "Arquivo do Qualificador (raw)"),
    ("outro", "Outro"),
]

PHASE_SELECTION = [
    ("installation", "QI"),
    ("operational", "QO"),
    ("performance", "QD"),
    ("software", "QS"),
    ("calibration", "Calibração"),
]

# F4.3: default de requires_instrument conforme natureza do item.
DEFAULT_REQUIRES_INSTRUMENT_BY_KIND = {
    "foto": False,
    "excel": True,
    "pdf": False,
    "qualificador_data": True,
    "outro": False,
}

# F6.1 (16.0.3.5.0): seção do relatório DOCX onde a coleta será listada.
# Os valores correspondem aos blocos de loop esperados pelos templates
# docs/MODELO_QUALIFICACAO_*.docx (e estrutura de docs/exemplo_contexto.json).
DOCX_SECTION_SELECTION = [
    # QI
    ("qi_utilidades", "QI — Utilidades"),
    ("qi_documentos", "QI — Documentos"),
    ("qi_componentes", "QI — Componentes"),
    ("qi_instalacao", "QI — Instalação"),
    ("qi_calibracoes", "QI — Calibrações"),
    ("qi_treinamentos", "QI — Treinamentos"),
    # QO
    ("qo_testes_funcionais", "QO — Testes Funcionais"),
    ("qo_testes_seguranca", "QO — Testes de Segurança"),
    ("qo_mapeamento_ciclo1", "QO — Mapeamento Ciclo 1"),
    ("qo_mapeamento_ciclo2", "QO — Mapeamento Ciclo 2"),
    ("qo_mapeamento_ciclo3", "QO — Mapeamento Ciclo 3"),
    # QD
    ("qd_carga", "QD — Carga"),
    ("qd_penetracao_ciclo1", "QD — Penetração Ciclo 1"),
    ("qd_penetracao_ciclo2", "QD — Penetração Ciclo 2"),
    ("qd_penetracao_ciclo3", "QD — Penetração Ciclo 3"),
    ("qd_indicadores_quimicos", "QD — Indicadores Químicos"),
    ("qd_indicadores_biologicos", "QD — Indicadores Biológicos"),
    ("qd_bowie_dick", "QD — Bowie-Dick"),
    ("qd_repetibilidade", "QD — Repetibilidade"),
    # Catch-all
    ("anexos", "Anexos (genérico)"),
]


class AfrQualificacaoProcedimento(models.Model):
    _name = "afr.qualificacao.procedimento"
    _description = "Procedimento de Qualificação (Template)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True, tracking=True)
    code = fields.Char(tracking=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    equipment_category_id = fields.Many2one(
        "engc.equipment.category",
        string="Categoria do equipamento",
        help="Vazio = aplica a qualquer categoria (fallback). Específica = match preferencial.",
        tracking=True,
    )
    item_ids = fields.One2many(
        "afr.qualificacao.procedimento.item",
        "procedimento_id",
        copy=True,
        string="Itens (esperados)",
    )
    item_count = fields.Integer(compute="_compute_item_count")
    is_default = fields.Boolean(
        string="Padrão da categoria",
        default=False,
        tracking=True,
        help=(
            "Procedimento padrão para a categoria (ou, sem categoria, padrão "
            "genérico). No máximo 1 ativo por (categoria, empresa). "
            "`resolve_for`/`_resolve_for_equipment` usam este campo — "
            "procedimentos não-padrão só são aplicados por escolha explícita "
            "(equipamento/cliente/wizard)."
        ),
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Primeiro procedimento de uma (categoria, empresa) nasce padrão.

        Sem isso, a primeira categoria cadastrada após 16.0.8.9.0 nunca
        resolveria por categoria (`is_default` nasceria False). Só quando
        `is_default` não veio explícito (vals nem `default_is_default` no
        contexto) e não há padrão ativo para a mesma (categoria, empresa) —
        mesmo escopo de `_check_is_default_unique`. Controla também as chaves
        já promovidas neste mesmo `vals_list`, senão dois procedimentos da
        mesma categoria num create só violariam a unicidade."""
        if "default_is_default" not in self.env.context:
            defaults = self.default_get(["company_id", "equipment_category_id", "active"])
            promoted = set()
            for vals in vals_list:
                key = (
                    vals.get("equipment_category_id", defaults.get("equipment_category_id")) or False,
                    vals.get("company_id", defaults.get("company_id")) or False,
                )
                active = vals.get("active", defaults.get("active", True))
                if "is_default" in vals:
                    if vals["is_default"] and active:
                        promoted.add(key)
                    continue
                if not active or key in promoted:
                    continue
                exists = self.with_context(active_test=True).search_count([
                    ("is_default", "=", True),
                    ("equipment_category_id", "=", key[0]),
                    ("company_id", "=", key[1]),
                ])
                if not exists:
                    vals["is_default"] = True
                    promoted.add(key)
        return super().create(vals_list)

    @api.depends("item_ids")
    def _compute_item_count(self):
        for r in self:
            r.item_count = len(r.item_ids)

    @api.constrains("is_default", "equipment_category_id", "company_id", "active")
    def _check_is_default_unique(self):
        for rec in self:
            if not rec.is_default or not rec.active:
                continue
            domain = [
                ("id", "!=", rec.id),
                ("is_default", "=", True),
                ("active", "=", True),
                ("company_id", "=", rec.company_id.id),
                (
                    "equipment_category_id",
                    "=",
                    rec.equipment_category_id.id if rec.equipment_category_id else False,
                ),
            ]
            if self.search_count(domain):
                cat_name = rec.equipment_category_id.name if rec.equipment_category_id else _("(genérico)")
                raise ValidationError(
                    _(
                        "Já existe um procedimento padrão para a categoria "
                        "'%(cat)s' nesta empresa."
                    ) % {"cat": cat_name}
                )

    @api.model
    def _company_first(self, records, company):
        """Da busca `company_id in [company, False]`, prefere o registro da
        empresa; senão o compartilhado (sem empresa). A unicidade de
        `is_default` é por empresa EXATA, então um padrão da empresa e um
        compartilhado podem coexistir — sem esta preferência o vencedor
        dependeria da `_order`."""
        return (records.filtered(lambda r: r.company_id == company) or records)[:1]

    @api.model
    def _search_company_first(self, domain, company, order=None):
        records = self.search(
            domain + [("active", "=", True), ("company_id", "in", [company.id, False])],
            order=order,
        )
        return self._company_first(records, company)

    @api.model
    def _resolve_defaults(self, category, company):
        """(procedimento, origem) pelos passos categoria → genérico padrão →
        genérico mais antigo, na empresa `company` ou compartilhados
        (`company_id` vazio), preferindo o da empresa."""
        if category:
            rec = self._search_company_first(
                [("equipment_category_id", "=", category.id), ("is_default", "=", True)],
                company,
            )
            if rec:
                return rec, "categoria"
        rec = self._search_company_first(
            [("equipment_category_id", "=", False), ("is_default", "=", True)], company
        )
        if rec:
            return rec, "generico"
        rec = self._search_company_first(
            [("equipment_category_id", "=", False)], company, order="id"
        )
        if rec:
            return rec, "generico"
        return self.browse(), False

    @api.model
    def resolve_for(self, equipment_category):
        """Retorna o procedimento padrão da categoria (ou fallback genérico).

        Preferência: 1) padrão (`is_default`) da categoria → 2) padrão
        genérico (sem categoria) → 3) genérico mais antigo (menor id).
        Retorna recordset vazio se nenhum. Restrito à empresa corrente
        (self.env.company) ou a procedimentos sem empresa, preferindo os da
        empresa (mesmos passos de `_resolve_for_equipment`).
        """
        return self._resolve_defaults(equipment_category, self.env.company)[0]

    @api.model
    def _resolve_for_equipment(self, equipment, partner, company=None):
        """Resolve o procedimento aplicável a `equipment` (e `partner`).

        Ordem: 1) procedimento explícito no equipamento (ativo, da empresa ou
        sem empresa) → 'equipamento'; 2) procedimento do cliente
        (commercial_partner_id) da mesma categoria → 'cliente'; 3) padrão da
        categoria → 'categoria'; 4) padrão genérico → 'generico'; 5) genérico
        mais antigo (menor id) → 'generico'; senão recordset vazio + False.
        Um passo que não se aplica (arquivado / outra empresa) cai para o
        próximo.

        `company` (opcional, `res.company` record) restringe todos os passos
        a `company_id in [company, False]` (preferindo o da empresa); por
        padrão `self.env.company`. Chamadores com cotação/OS já resolvida
        (wizard Gerar OS, materialização) devem passar a empresa DELA — sob
        cron/sudo/multi-company `env.company` pode divergir e a busca acharia
        o procedimento errado (ou nenhum).
        """
        company = company or self.env.company

        def in_company(proc):
            return proc.active and proc.company_id in (company, self.env["res.company"])

        equip_proc = equipment.afr_procedimento_id
        if equip_proc and in_company(equip_proc):
            return equip_proc, "equipamento"

        category = equipment.category_id
        commercial = partner.commercial_partner_id if partner else self.env["res.partner"]
        if category and commercial:
            proc = commercial.afr_procedimento_ids.filtered(
                lambda p: p.equipment_category_id == category and in_company(p)
            )
            if proc:
                return self._company_first(proc, company), "cliente"

        return self._resolve_defaults(category, company)

    def _explode_into(self, qualif, phase=None):
        """Cria N collect.items em `qualif` conforme target_level de cada item.

        Compartilhado por sale_order._explode_collect_items (auto-explosão no
        confirm da SO, onde `phase` vem explícito do loop de qtype) e pelo
        wizard "Aplicar Procedimento" (aplicação manual/re-aplicação, onde
        `phase` é omitido e cai no default = qualif.qualification_type).

        target_level=qualificacao → 1 item por qualif
        target_level=cycle → 1 item por ciclo existente (qualif QD)
        target_level=malha → 1 item por malha existente (qualif Calib)

        Retorna a quantidade de collect.items criados.
        """
        self.ensure_one()
        phase = phase or qualif.qualification_type
        CollectItem = self.env["afr.qualificacao.collect.item"]
        created = 0
        items = self.item_ids.filtered(lambda pi: pi.phase == phase)
        for pi in items:
            base_vals = {
                "name": pi.name,
                "sequence": pi.sequence,
                "kind": pi.kind,
                "required": pi.required,
                "instruction": pi.instruction,
                "procedimento_item_id": pi.id,
                "qualif_id": qualif.id,
            }
            if pi.target_level == "qualificacao":
                CollectItem.create(base_vals)
                created += 1
            elif pi.target_level == "cycle":
                for cycle in qualif.cycle_ids:
                    vals = dict(base_vals)
                    vals["cycle_id"] = cycle.id
                    vals["name"] = cycle.display_name
                    CollectItem.create(vals)
                    created += 1
            elif pi.target_level == "malha":
                for malha in qualif.malha_ids:
                    vals = dict(base_vals)
                    vals["malha_id"] = malha.id
                    vals["name"] = malha.display_name
                    CollectItem.create(vals)
                    created += 1
        return created


class AfrQualificacaoProcedimentoItem(models.Model):
    _name = "afr.qualificacao.procedimento.item"
    _description = "Item do Procedimento (Esperado de Coleta)"
    _order = "procedimento_id, sequence, id"

    procedimento_id = fields.Many2one(
        "afr.qualificacao.procedimento",
        required=True,
        ondelete="cascade",
        index=True,
    )
    phase = fields.Selection(
        PHASE_SELECTION,
        required=True,
        default="installation",
        string="Fase",
        help="Fase de qualificação a que este item pertence. Setado "
             "automaticamente pela aba do editor.",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    kind = fields.Selection(
        KIND_SELECTION,
        required=True,
        default="foto",
        string="Tipo de mídia",
    )
    required = fields.Boolean(default=True)
    instruction = fields.Text(translate=True, help="Instrução para o técnico em campo.")
    mimetypes_hint = fields.Char(
        string="Mime types sugeridos",
        help="Ex: image/png,image/jpeg,application/pdf (informativo apenas).",
    )
    target_level = fields.Selection(
        [
            ("qualificacao", "Qualificação (1 por qualif)"),
            ("cycle", "Ciclo (1 por ciclo da qualif QD)"),
            ("malha", "Malha (1 por malha da qualif Calib)"),
        ],
        required=True,
        default="qualificacao",
        help="Cycle/malha explodem N collect.items conforme qty da qualif.",
    )

    # F4.3 — Exigência de instrumento padrão
    requires_instrument = fields.Boolean(
        string="Requer padrão metrológico",
        default=lambda self: self._default_requires_instrument(),
        help=(
            "Quando ativo, o collect.item gerado por este template exige que "
            "o técnico associe ao menos um instrumento padrão cobrindo as "
            "grandezas listadas. Default automático por tipo de mídia: "
            "Planilha/Arquivo Qualificador = True; Foto/PDF/Outro = False."
        ),
    )
    required_sensor_kind_ids = fields.Many2many(
        "afr.qualificacao.sensor.kind",
        "afr_proc_item_sensor_kind_rel",
        "procedimento_item_id",
        "sensor_kind_id",
        string="Grandezas requeridas",
        help=(
            "Grandezas que os instrumentos padrão devem cobrir (ex: TEMP, "
            "PRESS). Para itens multi-medida (ex: Dados do Qualificador), "
            "liste todas as grandezas que aparecem no arquivo bruto. Cobertura "
            "do collect.item é validada contra a união das grandezas dos "
            "instrumentos selecionados."
        ),
    )

    # F6.1 (16.0.3.5.0) — seção do relatório DOCX onde o item aparece.
    docx_section = fields.Selection(
        DOCX_SECTION_SELECTION,
        string="Seção no relatório DOCX",
        help=(
            "Classifica em qual tabela do relatório DOCX (QI/QO/QD) o "
            "collect.item gerado a partir deste template será listado. "
            "Vazio = não aparece em tabela específica (aparece em 'anexos' "
            "se for required ou se tiver arquivo). Os valores casam com "
            "os blocos {% for %} dos templates em static/docx/."
        ),
    )

    @api.model
    def _default_requires_instrument(self):
        kind = self.env.context.get("default_kind", "foto")
        return DEFAULT_REQUIRES_INSTRUMENT_BY_KIND.get(kind, False)

    @api.onchange("kind")
    def _onchange_kind_requires_instrument(self):
        for r in self:
            r.requires_instrument = DEFAULT_REQUIRES_INSTRUMENT_BY_KIND.get(
                r.kind, False
            )
