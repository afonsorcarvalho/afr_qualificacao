"""Remove a Tabela de Ciclos e o box "Itens Não Solicitados" da cotação.

- `cycle_specs` saiu da seleção de `block_kind`: apaga as linhas de template
  e os blocos materializados nas cotações antes do ORM carregar a seleção nova.
- O box `qq-declined-box` não é mais renderizado, mas blocos editados à mão
  guardam o HTML do snapshot no `body` — remove o `<div>` de lá.
"""
import logging

from lxml import html as lhtml

_logger = logging.getLogger(__name__)


def _strip_declined_box(body):
    root = lhtml.fragment_fromstring(body, create_parent="div")
    boxes = root.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' qq-declined-box ')]")
    if not boxes:
        return None
    for box in boxes:
        box.getparent().remove(box)
    inner = (root.text or "") + "".join(
        lhtml.tostring(child, encoding="unicode") for child in root
    )
    return inner


def migrate(cr, version):
    cr.execute("DELETE FROM afr_proposal_block WHERE block_kind = 'cycle_specs'")
    blocks = cr.rowcount
    cr.execute("DELETE FROM afr_proposal_template_line WHERE block_kind = 'cycle_specs'")
    lines = cr.rowcount
    _logger.info("cycle_specs removido: %d bloco(s), %d linha(s) de template", blocks, lines)

    cr.execute("SELECT id, body FROM afr_proposal_block WHERE body ILIKE '%%qq-declined-box%%'")
    for block_id, body in cr.fetchall():
        new_body = _strip_declined_box(body)
        if new_body is not None:
            cr.execute("UPDATE afr_proposal_block SET body = %s WHERE id = %s", (new_body, block_id))
            _logger.info("box Itens Não Solicitados removido do bloco %d", block_id)
