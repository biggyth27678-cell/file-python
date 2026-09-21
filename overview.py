from collections import Counter

from ..stats import chart, count_by, kpi, mean, one, pct

META = {"id": "overview", "title": "ภาพรวม", "desc": "จำนวนพนักงาน สถานะ และแนวโน้มการจ้าง/ลาออก"}

STATUS_ORDER = ["Active", "Leave of Absence", "Future Start", "Voluntarily Terminated", "Terminated for Cause"]


def compute(recs):
    n = len(recs)
    active = sum(1 for r in recs if r["status"] == "Active")
    left = sum(1 for r in recs if r["terminated"])
    hires = Counter(r["hire_year"] for r in recs if r["hire_year"])
    terms = Counter(r["term_year"] for r in recs if r["term_year"])
    years = sorted(set(hires) | set(terms))
    return {
        "kpis": [
            kpi("พนักงานทั้งหมด", n, "int"),
            kpi("กำลังทำงาน", active, "int", hint=f"{pct(active, n)}% ของทั้งหมด" if n else None),
            kpi("อัตราการลาออก", pct(left, n), "pct", hint=f"{left:,} คน"),
            kpi("อัตราค่าจ้างเฉลี่ย", mean(r["pay"] for r in recs), "dec"),
            kpi("Engagement เฉลี่ย", mean(r["engagement"] for r in recs), "dec", hint="เต็ม 5"),
            kpi("อายุงานเฉลี่ย", mean((r["tenure"] for r in recs), 1), "yrs"),
        ],
        "charts": [
            one("จำนวนพนักงานแยกตามแผนก", "hbar", count_by(recs, "dept"), name="พนักงาน"),
            one("สถานะการจ้างงาน", "doughnut", count_by(recs, "status", order=STATUS_ORDER), name="พนักงาน"),
            chart("การจ้างและการลาออกรายปี", "line", years,
                  [{"name": "จ้างเข้า", "data": [hires[y] for y in years]},
                   {"name": "ลาออก/สิ้นสุด", "data": [terms[y] for y in years]}]),
        ],
    }