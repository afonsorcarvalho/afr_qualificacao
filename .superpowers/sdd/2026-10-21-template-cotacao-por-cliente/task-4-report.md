# Task 4 report — Gravar como padrão deste cliente

Status: DONE. Suite: afr_qualificacao 1490 tests, 0 failed (baseline 1481).
Red step: TestSaveClientTemplate errored with AttributeError (action_save_as_client_default missing) before implementation.

Decisions
- price_base = section.equipment_target_price (if the SO already has a managed section for the equipment with a target) else wizard line `subtotal`.
- estimated_days = section.equipment_target_days else `estimated_hours_total / work_hours_per_day` (not `estimated_days_total`, which is rounded to 1 decimal).
- Scope copy refactored into `configurator.equipment._template_scope_vals()`, now shared with `action_save_as_template` (which now also copies QO lines/hours/jornada).
- Existing active (partner, category, company) template -> transient confirm wizard `afr.qualificacao.client.default.confirm` (old vs new price/days); confirm replaces qo/qd/calib lines (qd_point_ids of the existing template are kept). New template copies qd_point_ids from the line's config_template_id.
- Notification: "Padrão de <categoria> salvo para <cliente>". Category missing -> UserError pt-BR.
- Version 16.0.9.0.3.
