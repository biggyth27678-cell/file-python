from ..stats import agg_by, chart, kpi, mean, median, one

META = {"id": "compensation", "title": "ค่าตอบแทน", "desc": "อัตราค่าจ้างตามแผนก ตำแหน่ง เพศ และผลงาน"}

PERF_ORDER = ["PIP", "Needs Improvement", "Fully Meets", "Exceeds"]
BINS = [(0, 20, "ต่ำกว่า 20"), (20, 30, "20–29"), (30, 40, "30–39"), (40, 50, "40–49"),
        (50, 60, "50–59"), (60, 70, "60–69"), (70, float("inf"), "70 ขึ้นไป")]


def _avg_pay(rs):
    return mean((r["pay"] for r in rs), 2)


def compute(recs):
    pays = [r["pay"] for r in recs if r["pay"] is not None]
    hist = [sum(1 for p in pays if lo <= p < hi) for lo, hi, _ in BINS]
    female = _avg_pay([r for r in recs if r["sex"] == "Female"])
    male = _avg_pay([r for r in recs if r["sex"] == "Male"])
    gap = round((female - male) * 100 / male, 1) if female is not None and male else None
    return {
        "kpis": [
            kpi("ค่าเฉลี่ย", mean(pays), "dec"),
            kpi("มัธยฐาน", median(pays), "dec"),
            kpi("ต่ำสุด", min(pays) if pays else None, "dec"),
            kpi("สูงสุด", max(pays) if pays else None, "dec"),
            kpi("ส่วนต่างหญิง vs ชาย", gap, "pct", hint="ค่าเฉลี่ยหญิงเทียบชาย"),
        ],
        "charts": [
            one("ค่าจ้างเฉลี่ยตามแผนก", "bar", agg_by(recs, "dept", _avg_pay), "dec", name="ค่าจ้างเฉลี่ย"),
            one("ตำแหน่งที่ค่าจ้างเฉลี่ยสูงสุด (10 อันดับ)", "hbar",
                agg_by(recs, "position", _avg_pay, top=10), "dec", name="ค่าจ้างเฉลี่ย"),
            chart("การกระจายของอัตราค่าจ้าง", "bar", [b[2] for b in BINS], [{"name": "พนักงาน", "data": hist}]),
            one("ค่าจ้างเฉลี่ยตามเพศ", "bar", agg_by(recs, "sex", _avg_pay), "dec", name="ค่าจ้างเฉลี่ย"),
            one("ค่าจ้างเฉลี่ยตามผลการประเมิน", "bar", agg_by(recs, "perf", _avg_pay, order=PERF_ORDER),
                "dec", name="ค่าจ้างเฉลี่ย"),
        ],
    }