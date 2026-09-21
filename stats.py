"""Small aggregation helpers shared by every dashboard module (pure Python)."""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median as _median

UNKNOWN = "ไม่ระบุ"


def mean(values, nd=2):
    v = [x for x in values if x is not None]
    return round(sum(v) / len(v), nd) if v else None


def median(values, nd=2):
    v = [x for x in values if x is not None]
    return round(_median(v), nd) if v else None


def pct(part, whole, nd=1):
    return round(part * 100 / whole, nd) if whole else None


def kpi(label, value, fmt="int", hint=None):
    return {"label": label, "value": value, "fmt": fmt, "hint": hint}


def _ordered(keys, order):
    keys = list(keys)
    head = [k for k in order if k in keys]
    tail = sorted((k for k in keys if k not in order), key=str)
    return head + tail


def count_by(recs, key, order=None, top=None, sort="count"):
    """Return (labels, counts) for a categorical field."""
    c = Counter(r[key] for r in recs if r[key] not in (None, ""))
    if order:
        labels = _ordered(c, order)
    elif sort == "label":
        labels = sorted(c, key=str)
    else:
        labels = [k for k, _ in c.most_common()]
    if top:
        labels = labels[:top]
    return labels, [c[k] for k in labels]


def agg_by(recs, key, fn, order=None, top=None, min_n=1, sort="desc"):
    """Group records by `key`, apply `fn(list_of_records)`, return (labels, values)."""
    groups = defaultdict(list)
    for r in recs:
        if r[key] not in (None, ""):
            groups[r[key]].append(r)
    vals = {k: fn(v) for k, v in groups.items() if len(v) >= min_n}
    vals = {k: v for k, v in vals.items() if v is not None}
    if order:
        labels = _ordered(vals, order)
    else:
        labels = sorted(vals, key=lambda k: vals[k], reverse=(sort == "desc"))
    if top:
        labels = labels[:top]
    return labels, [vals[k] for k in labels]


def cross(recs, row_key, col_key, row_order=None, col_order=None, top=None):
    """Stacked-chart data: rows on the axis, one series per column value."""
    row_labels, _ = count_by(recs, row_key, order=row_order, top=top)
    col_labels, _ = count_by(recs, col_key, order=col_order)
    table = Counter((r[row_key], r[col_key]) for r in recs)
    series = [{"name": str(c), "data": [table[(rl, c)] for rl in row_labels]} for c in col_labels]
    return row_labels, series


def chart(title, kind, labels, series, fmt="int", stacked=False, note=None):
    return {
        "title": title, "type": kind, "labels": [str(x) for x in labels],
        "series": series, "fmt": fmt, "stacked": stacked, "note": note,
    }


def one(title, kind, pair, fmt="int", name=None, note=None):
    labels, values = pair
    return chart(title, kind, labels, [{"name": name or title, "data": values}], fmt, note=note)