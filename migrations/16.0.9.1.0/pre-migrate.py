"""Task 9: remove unicidade série+marca de engc.equipment (herdada do engc_os)."""


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE IF EXISTS engc_equipment "
        "DROP CONSTRAINT IF EXISTS engc_equipment_serial_marca_company_id_no_uniq"
    )
