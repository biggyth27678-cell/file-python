"""Filter parsing/applying shared by every module, plus the option lists for the UI."""
from __future__ import annotations

from collections import Counter

LIST_FILTERS = ("dept", "status", "sex", "race", "marital", "perf", "source", "position", "state")


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def clean_filters(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key in LIST_FILTERS:
        vals = raw.get(key)
        if isinstance(vals, list):
            vals = [str(x) for x in vals if str(x)]
            if vals:
                out[key] = vals
    for key in ("hire_from", "hire_to"):
        if _int(raw.get(key)) is not None:
            out[key] = _int(raw[key])
    for key in ("pay_min", "pay_max"):
        if _float(raw.get(key)) is not None:
            out[key] = _float(raw[key])
    q = str(raw.get("q") or "").strip().lower()[:100]
    if q:
        out["q"] = q
    return out


def apply_filters(records: list, f: dict) -> list:
    sets = {k: set(f[k]) for k in LIST_FILTERS if k in f}
    hire_from, hire_to = f.get("hire_from"), f.get("hire_to")
    pay_min, pay_max = f.get("pay_min"), f.get("pay_max")
    q = f.get("q")
    out = []
    for r in records:
        if any(r[k] not in s for k, s in sets.items()):
            continue
        if hire_from is not None and (r["hire_year"] is None or r["hire_year"] < hire_from):
            continue
        if hire_to is not None and (r["hire_year"] is None or r["hire_year"] > hire_to):
            continue
        if pay_min is not None and (r["pay"] is None or r["pay"] < pay_min):
            continue
        if pay_max is not None and (r["pay"] is None or r["pay"] > pay_max):
            continue
        if q and q not in r["name"].lower() and q not in r["position"].lower():
            continue
        out.append(r)
    return out


def build_options(records: list) -> dict:
    """Option lists (value + headcount) computed on the full dataset."""
    options = {}
    for key in LIST_FILTERS:
        counts = Counter(r[key] for r in records)
        options[key] = [{"v": v, "n": n} for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))]
    years = [r["hire_year"] for r in records if r["hire_year"]]
    pays = [r["pay"] for r in records if r["pay"] is not None]
    return {
        "options": options,
        "ranges": {
            "hire_year": [min(years), max(years)] if years else None,
            "pay": [min(pays), max(pays)] if pays else None,
        },
    }