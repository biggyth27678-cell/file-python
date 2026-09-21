"""Dashboard modules. Each module exposes META and compute(records) -> {kpis, charts}.

To add a module: create a file here, then register it in MODULES below.
"""
from . import compensation, overview, performance, recruitment, turnover, workforce

MODULES = {m.META["id"]: m for m in (overview, workforce, compensation, performance, turnover, recruitment)}

# The employee table is served by /api/employees rather than compute().
TABLE_META = {"id": "employees", "title": "รายชื่อพนักงาน", "desc": "ตารางข้อมูลตามตัวกรอง เรียงลำดับและแบ่งหน้าได้"}


def catalog():
    return [m.META for m in MODULES.values()] + [TABLE_META]