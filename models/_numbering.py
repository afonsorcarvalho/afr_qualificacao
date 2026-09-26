"""Numeração hierárquica compartilhada (cotação e relatório final).

Função pura: não depende do ORM. Recebe qualquer iterável de objetos com
`sequence`, `id`, `parent_id` (objeto com `.id`, falsy quando vazio) e
`show_number`. Quem chama decide o que entra (ex.: só blocos `included`).
"""


def sort_key(record):
    """(sequence, id) — NewId (registro virtual de onchange) usa `origin` ou 0."""
    rec_id = record.id
    if not isinstance(rec_id, int):
        rec_id = getattr(rec_id, "origin", 0) or 0
    return (record.sequence, rec_id)


def hierarchical_numbering(records):
    """Retorna {record.id: '1' | '3.1' | '1.1.1' | ''}.

    Registros com show_number=False recebem ''. Filho de pai sem número (ou
    de pai fora do conjunto) numera a partir de 1 sem prefixo — comportamento
    histórico da cotação, mantido sem mudança.
    """
    numbers = {}
    root_counter = 0
    child_counters = {}
    for rec in sorted(records, key=sort_key):
        if not rec.parent_id:
            if rec.show_number:
                root_counter += 1
                numbers[rec.id] = str(root_counter)
                child_counters[rec.id] = 0
            else:
                numbers[rec.id] = ""
        else:
            pid = rec.parent_id.id
            child_counters.setdefault(pid, 0)
            if rec.show_number:
                child_counters[pid] += 1
                parent_num = numbers.get(pid, "")
                numbers[rec.id] = (
                    f"{parent_num}.{child_counters[pid]}"
                    if parent_num
                    else str(child_counters[pid])
                )
            else:
                numbers[rec.id] = ""
    return numbers
