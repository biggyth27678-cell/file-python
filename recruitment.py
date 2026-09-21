from ..stats import agg_by, count_by, kpi, mean, one, pct

META = {"id": "recruitment", "title": "การสรรหา", "desc": "แหล่งที่มาของพนักงานและคุณภาพของแต่ละช่องทาง"}


def compute(recs):
    labels, counts = count_by(recs, "source")
    top = f"{labels[0]}" if labels else None
    n = len(recs)
    referral = sum(1 for r in recs if "referral" in r["source"].lower())
    diversity = sum(1 for r in recs if r["source"] == "Diversity Job Fair")
    return {
        "kpis": [
            kpi("จำนวนช่องทางสรรหา", len(labels), "int"),
            kpi("ช่องทางอันดับ 1", top, "text", hint=f"{counts[0]:,} คน" if counts else None),
            kpi("มาจากการแนะนำ (Referral)", pct(referral, n), "pct"),
            kpi("มาจาก Diversity Job Fair", pct(diversity, n), "pct"),
        ],
        "charts": [
            one("พนักงานแยกตามแหล่งสรรหา (12 อันดับแรก)", "hbar", count_by(recs, "source", top=12), name="พนักงาน"),
            one("Engagement เฉลี่ยตามแหล่งสรรหา (≥ 10 คน)", "hbar",
                agg_by(recs, "source", lambda rs: mean((r["engagement"] for r in rs), 2), min_n=10, top=10),
                "dec", name="Engagement"),
            one("สัดส่วนผลงานระดับ Exceeds ตามแหล่งสรรหา (≥ 10 คน)", "hbar",
                agg_by(recs, "source", lambda rs: pct(sum(1 for r in rs if r["perf"] == "Exceeds"), len(rs)),
                       min_n=10, top=10), "pct", name="Exceeds"),
            one("ค่าจ้างเฉลี่ยตามแหล่งสรรหา (≥ 10 คน)", "hbar",
                agg_by(recs, "source", lambda rs: mean((r["pay"] for r in rs), 2), min_n=10, top=10),
                "dec", name="ค่าจ้างเฉลี่ย"),
        ],
    }