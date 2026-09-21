from ..stats import agg_by, count_by, cross, kpi, mean, one, pct

META = {"id": "performance", "title": "ผลงานและความผูกพัน", "desc": "ผลประเมิน Engagement และความพึงพอใจ"}

PERF_ORDER = ["PIP", "Needs Improvement", "Fully Meets", "Exceeds"]


def _eng(rs):
    return mean((r["engagement"] for r in rs), 2)


def compute(recs):
    n = len(recs)
    exceeds = sum(1 for r in recs if r["perf"] == "Exceeds")
    watch = sum(1 for r in recs if r["perf"] in ("PIP", "Needs Improvement"))
    rows, series = cross(recs, "dept", "perf", col_order=PERF_ORDER)
    sat_labels, sat_counts = count_by([r for r in recs if r["satisfaction"] is not None], "satisfaction", sort="label")
    sat_labels = [int(x) if float(x).is_integer() else x for x in sat_labels]
    return {
        "kpis": [
            kpi("Engagement เฉลี่ย", mean(r["engagement"] for r in recs), "dec", hint="เต็ม 5"),
            kpi("ความพึงพอใจเฉลี่ย", mean(r["satisfaction"] for r in recs), "dec", hint="เต็ม 5"),
            kpi("ผลงานเกินเป้าหมาย", pct(exceeds, n), "pct", hint="Exceeds"),
            kpi("ต้องติดตาม", pct(watch, n), "pct", hint="PIP + Needs Improvement"),
            kpi("Special Projects เฉลี่ย", mean(r["projects"] for r in recs), "dec", hint="ต่อคน"),
        ],
        "charts": [
            one("การกระจายผลการประเมิน", "doughnut", count_by(recs, "perf", order=PERF_ORDER), name="พนักงาน"),
            {"title": "ผลการประเมินแยกตามแผนก", "type": "bar", "labels": [str(x) for x in rows],
             "series": series, "fmt": "int", "stacked": True, "note": None},
            one("Engagement เฉลี่ยตามแผนก", "bar", agg_by(recs, "dept", _eng), "dec", name="Engagement"),
            one("Engagement เฉลี่ยตามผลการประเมิน", "bar", agg_by(recs, "perf", _eng, order=PERF_ORDER),
                "dec", name="Engagement"),
            one("คะแนนความพึงพอใจ (1–5)", "bar", (sat_labels, sat_counts), name="พนักงาน"),
        ],
    }