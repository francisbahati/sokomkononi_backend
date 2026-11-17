# apps/bundles/stats.py
"""
Hesabu za manunuzi ya bundles (hazitegemei database, kwa hiyo zinajaribika).

`credits_snapshot` ya kila BundlePurchase ni dict ya huduma -> idadi, mfano
{"listing": 10, "boost": 2}. Tunatumia snapshot (si `Bundle.credits`) kwa sababu
admin akibadilisha bundle baadaye, manunuzi ya zamani yanabaki kama yalivyokuwa.
"""


def _as_count(value):
    """Rudisha int >= 0, au None kama si namba halali (bool haihesabiwi)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = int(value)
    elif isinstance(value, str):
        try:
            n = int(value.strip())
        except ValueError:
            return None
    else:
        return None
    return n if n >= 0 else None


def sum_credits(snapshot):
    """{"listing": 10, "boost": "2", "x": None} -> {"listing": 10, "boost": 2}."""
    out = {}
    if not isinstance(snapshot, dict):
        return out
    for key, value in snapshot.items():
        n = _as_count(value)
        if n is not None:
            out[str(key)] = n
    return out


def credits_total(snapshot):
    return sum(sum_credits(snapshot).values())


def aggregate_purchase_rows(rows):
    """
    rows: iterable ya (bundle_id, credits_snapshot) za manunuzi YALIYOLIPWA.
    Rudisha {bundle_id: {"purchases": n, "creditsByService": {...}, "creditsTotal": n}}.
    """
    stats = {}
    for bundle_id, snapshot in rows:
        entry = stats.setdefault(
            bundle_id,
            {"purchases": 0, "creditsByService": {}, "creditsTotal": 0},
        )
        entry["purchases"] += 1
        for key, n in sum_credits(snapshot).items():
            entry["creditsByService"][key] = entry["creditsByService"].get(key, 0) + n
            entry["creditsTotal"] += n
    return stats
