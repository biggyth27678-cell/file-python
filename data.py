"""Load, validate and clean HR data files, and keep parsed datasets available.

Vercel functions are stateless: parsed datasets are cached in memory and in the
temp directory (/tmp), and the browser re-sends the raw file if a cold start
lost it (see public/app.js).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import tempfile
import threading
from collections import OrderedDict
from datetime import date
from pathlib import Path

from .stats import UNKNOWN

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_PATH = BASE_DIR / "data" / "HR_DATA.txt"
CACHE_DIR = Path(tempfile.gettempdir())
SAMPLE_ID = "sample"
MAX_MEM = 4

REQUIRED = ["Employee_Name", "EmpID", "Department", "EmploymentStatus", "PayRate", "Sex", "DateofHire"]
TERMINATED_STATUS = {"voluntarily terminated", "terminated for cause"}
AGE_BANDS = ["<25", "25-34", "35-44", "45-54", "55+"]


class DataError(ValueError):
    """Raised with a user-facing (Thai) message when a file can't be used."""


# ---------- low-level parsing ----------

def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp874"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _txt(v) -> str:
    return re.sub(r"\s+", " ", v or "").strip()


def _num(v):
    s = _txt(v).replace(",", "").replace("$", "")
    if not s:
        return None
    try:
        x = float(s)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")
_DMY = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})")


def _full_year(y: int, dob: bool) -> int:
    if y >= 100:
        return y
    this_year = date.today().year
    if dob:  # employees are at least ~16, so 2-digit birth years fall in the past
        return 2000 + y if 2000 + y <= this_year - 16 else 1900 + y
    return 2000 + y if 2000 + y <= this_year + 5 else 1900 + y


def _date(v, dob=False):
    s = _txt(v)
    if not s:
        return None
    m = _ISO.match(s)
    if m:
        y, mo, d = (int(g) for g in m.groups())
    else:
        m = _DMY.match(s)
        if not m:
            return None
        d, mo, y = int(m.group(1)), int(m.group(2)), _full_year(int(m.group(3)), dob)
        if mo > 12 >= d:  # looks like mm/dd/yy
            d, mo = mo, d
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _age_band(age):
    if age is None:
        return UNKNOWN
    for limit, label in ((25, "<25"), (35, "25-34"), (45, "35-44"), (55, "45-54")):
        if age < limit:
            return label
    return "55+"


# ---------- delimiter detection ----------

_SPACE_RUN = re.compile(r" {2,}")


def _detect_delimiter(text: str) -> tuple[str, str]:
    """Return (delimiter, possibly-rewritten text).

    Tries the standard single-character delimiters first (Tab, comma,
    semicolon, pipe). Some HRIS/Excel exports instead pad every column to a
    fixed width with plain spaces (no real Tab byte at all) -- e.g. exactly
    8 spaces between every field. If none of the standard delimiters are
    found, look for that fixed-width space run on the header line and use
    its *exact* width as a literal separator to split every line.

    Splitting on the exact width (rather than collapsing any run of 2+
    spaces) is what makes this safe for empty fields: an empty field between
    two delimiters shows up as a run that is a whole multiple of the unit
    width (e.g. 16 spaces = two back-to-back 8-space delimiters with
    nothing in between), and `str.split(unit)` naturally yields an empty
    string for it instead of silently merging the two delimiters into one
    and shifting every later column left.
    """
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise DataError("ไฟล์ว่างเปล่าหรือไม่มีแถวหัวตาราง")

    header = lines[0]
    counts = {d: header.count(d) for d in "\t,;|"}
    delim = max(counts, key=counts.get)
    if counts[delim] > 0:
        return delim, text

    gaps = [len(m.group()) for m in _SPACE_RUN.finditer(header)]
    if gaps:
        unit = " " * min(gaps)  # the narrowest run on the header = one delimiter
        # Rebuild as Tab-separated so csv.reader (with its quote handling)
        # can be reused unchanged. Rejoin with "\n" since splitlines()
        # already stripped the original line endings (CR included).
        text = "\n".join("\t".join(line.split(unit)) for line in lines)
        return "\t", text

    raise DataError("อ่านคอลัมน์ไม่ได้ กรุณาใช้ไฟล์ที่คั่นคอลัมน์ด้วย Tab, comma, semicolon หรือ |")


# ---------- dataset building ----------

def build_dataset(text: str, filename: str, ds_id: str, sample: bool = False) -> dict:
    delim, text = _detect_delimiter(text)

    reader = csv.reader(io.StringIO(text), delimiter=delim)
    header = next(reader)
    cols = {_txt(h).lower(): i for i, h in enumerate(header)}
    missing = [c for c in REQUIRED if c.lower() not in cols]
    if missing:
        raise DataError("ไฟล์ขาดคอลัมน์ที่จำเป็น: " + ", ".join(missing))

    def col(row, name):
        i = cols.get(name.lower())
        return row[i] if i is not None and i < len(row) else ""

    raws, skipped, bad_pay = [], 0, 0
    for row in reader:
        if not any(_txt(c) for c in row):
            continue
        name, emp_id = _txt(col(row, "Employee_Name")), _txt(col(row, "EmpID"))
        if not name and not emp_id:
            skipped += 1
            continue
        pay = _num(col(row, "PayRate"))
        if pay is None:
            bad_pay += 1
        status = _txt(col(row, "EmploymentStatus")) or UNKNOWN
        sex = _txt(col(row, "Sex")).upper()[:1]
        raws.append({
            "id": emp_id, "name": name,
            "dept": _txt(col(row, "Department")) or UNKNOWN,
            "position": _txt(col(row, "Position")) or UNKNOWN,
            "state": _txt(col(row, "State")).upper() or UNKNOWN,
            "sex": {"F": "Female", "M": "Male"}.get(sex, UNKNOWN),
            "marital": _txt(col(row, "MaritalDesc")) or UNKNOWN,
            "citizen": _txt(col(row, "CitizenDesc")) or UNKNOWN,
            "hispanic": _txt(col(row, "HispanicLatino")).title() or UNKNOWN,
            "race": _txt(col(row, "RaceDesc")) or UNKNOWN,
            "status": status,
            "term_reason": _txt(col(row, "TermReason")) or UNKNOWN,
            "manager": _txt(col(row, "ManagerName")) or UNKNOWN,
            "source": _txt(col(row, "RecruitmentSource")) or UNKNOWN,
            "perf": _txt(col(row, "PerformanceScore")) or UNKNOWN,
            "engagement": _num(col(row, "EngagementSurvey")),
            "satisfaction": _num(col(row, "EmpSatisfaction")),
            "projects": _num(col(row, "SpecialProjectsCount")),
            "pay": pay,
            "_hire": _date(col(row, "DateofHire")),
            "_term": _date(col(row, "DateofTermination")),
            "_dob": _date(col(row, "DOB"), dob=True),
            "_review": _date(col(row, "LastPerformanceReview_Date")),
        })
    if not raws:
        raise DataError("ไม่พบข้อมูลพนักงานในไฟล์")

    # "as of" date = latest real event in the data, so tenure/age are reproducible.
    events = [r["_term"] for r in raws if r["_term"]] + [r["_review"] for r in raws if r["_review"]]
    events += [r["_hire"] for r in raws if r["_hire"] and r["status"].lower() != "future start"]
    as_of = max(events) if events else date.today()

    records = []
    for r in raws:
        hire, term, dob = r.pop("_hire"), r.pop("_term"), r.pop("_dob")
        review = r.pop("_review")
        end = term or as_of
        tenure = max(0.0, round((end - hire).days / 365.25, 2)) if hire else None
        age = int((as_of - dob).days / 365.25) if dob else None
        if age is not None and not 14 <= age <= 90:
            age = None
        r.update({
            "hire": hire.isoformat() if hire else None,
            "term": term.isoformat() if term else None,
            "review": review.isoformat() if review else None,
            "hire_year": hire.year if hire else None,
            "term_year": term.year if term else None,
            "tenure": tenure,
            "age": age,
            "age_band": _age_band(age),
            "terminated": bool(term) or r["status"].lower() in TERMINATED_STATUS,
        })
        records.append(r)

    warnings = []
    if skipped:
        warnings.append(f"ข้ามแถวที่ไม่มีชื่อและรหัสพนักงาน {skipped:,} แถว")
    if bad_pay:
        warnings.append(f"พบ PayRate ที่อ่านไม่ได้ {bad_pay:,} แถว (ไม่นำไปคำนวณค่าจ้าง)")

    return {
        "id": ds_id, "filename": filename, "sample": sample, "rows": len(records),
        "as_of": as_of.isoformat(), "warnings": warnings, "records": records,
    }


# ---------- storage ----------

_mem: "OrderedDict[str, dict]" = OrderedDict()
_lock = threading.Lock()


def _remember(ds: dict) -> None:
    with _lock:
        _mem[ds["id"]] = ds
        _mem.move_to_end(ds["id"])
        while len(_mem) > MAX_MEM:
            _mem.popitem(last=False)


def _cache_path(ds_id: str) -> Path:
    return CACHE_DIR / f"hrdash_{ds_id}.json"


def load_sample() -> dict:
    text = _decode(SAMPLE_PATH.read_bytes())
    ds = build_dataset(text, "HR_DATA.txt", SAMPLE_ID, sample=True)
    _remember(ds)
    return ds


def ingest_upload(raw: bytes, filename: str) -> dict:
    ds_id = "u" + hashlib.sha1(raw).hexdigest()[:12]
    ds = build_dataset(_decode(raw), filename, ds_id)
    try:
        _cache_path(ds_id).write_text(json.dumps(ds, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # memory cache still works; the browser can re-send the file
    _remember(ds)
    return ds


def get_dataset(ds_id) -> dict | None:
    ds_id = re.sub(r"[^a-z0-9]", "", str(ds_id or SAMPLE_ID).lower())
    with _lock:
        ds = _mem.get(ds_id)
    if ds:
        return ds
    if ds_id == SAMPLE_ID:
        return load_sample()
    path = _cache_path(ds_id)
    if path.exists():
        try:
            ds = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        _remember(ds)
        return ds
    return None