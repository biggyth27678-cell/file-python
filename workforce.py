from ..data import AGE_BANDS
from ..stats import count_by, cross, kpi, mean, one, pct

META = {"id": "workforce", "title": "โครงสร้างกำลังคน", "desc": "เพศ อายุ เชื้อชาติ สถานภาพ และพื้นที่"}


def compute(recs):
    n = len(recs)
    female = sum(1 for r in recs if r["sex"] == "Female")
    hisp = sum(1 for r in recs if r["hispanic"] == "Yes")
    us = sum(1 for r in recs if r["citizen"] == "US Citizen")
    rows, series = cross(recs, "dept", "sex")
    return {
        "kpis": [
            kpi("สัดส่วนหญิง", pct(female, n), "pct"),
            kpi("อายุเฉลี่ย", mean((r["age"] for r in recs), 1), "yrs"),
            kpi("Hispanic/Latino", pct(hisp, n), "pct"),
            kpi("US Citizen", pct(us, n), "pct"),
        ],
        "charts": [
            one("เพศ", "doughnut", count_by(recs, "sex"), name="พนักงาน"),
            one("ช่วงอายุ", "bar", count_by(recs, "age_band", order=AGE_BANDS), name="พนักงาน"),
            {"title": "เพศแยกตามแผนก", "type": "bar", "labels": [str(x) for x in rows], "series": series,
             "fmt": "int", "stacked": True, "note": None},
            one("เชื้อชาติ", "hbar", count_by(recs, "race"), name="พนักงาน"),
            one("สถานภาพสมรส", "doughnut", count_by(recs, "marital"), name="พนักงาน"),
            one("สถานะพลเมือง", "bar", count_by(recs, "citizen"), name="พนักงาน"),
            one("รัฐที่อยู่อาศัย (10 อันดับแรก)", "hbar", count_by(recs, "state", top=10), name="พนักงาน"),
        ],
    }