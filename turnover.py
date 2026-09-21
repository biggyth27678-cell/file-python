from ..stats import agg_by, count_by, kpi, mean, one, pct

META = {"id": "turnover", "title": "การลาออก", "desc": "อัตราและสาเหตุการสิ้นสุดการจ้างงาน"}


def _rate(rs):
    return pct(sum(1 for r in rs if r["terminated"]), len(rs))


def compute(recs):
    n = len(recs)
    left = [r for r in recs if r["terminated"]]
    vol = sum(1 for r in left if r["status"] == "Voluntarily Terminated")
    cause = sum(1 for r in left if r["status"] == "Terminated for Cause")
    return {
        "kpis": [
            kpi("ลาออก/สิ้นสุดการจ้าง", len(left), "int"),
            kpi("อัตราการลาออก", pct(len(left), n), "pct"),
            kpi("ลาออกเอง", vol, "int"),
            kpi("เลิกจ้างเพราะเหตุ", cause, "int"),
            kpi("อายุงานเฉลี่ยก่อนออก", mean((r["tenure"] for r in left), 1), "yrs"),
        ],
        "charts": [
            one("สาเหตุการออก", "hbar", count_by(left, "term_reason"), name="พนักงาน"),
            one("จำนวนผู้ออกรายปี", "bar", count_by(left, "term_year", sort="label"), name="พนักงาน"),
            one("อัตราการลาออกตามแผนก", "bar", agg_by(recs, "dept", _rate), "pct", name="อัตราลาออก"),
            one("อัตราการลาออกตามแหล่งสรรหา (แหล่งที่มีพนักงาน ≥ 10 คน)", "hbar",
                agg_by(recs, "source", _rate, min_n=10, top=10), "pct", name="อัตราลาออก"),
            one("ลาออกเอง vs เลิกจ้างเพราะเหตุ", "doughnut", count_by(left, "status"), name="พนักงาน"),
        ],
    }