"""JSON API used by the dashboard front-end."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .data import DataError, get_dataset, ingest_upload
from .filters import apply_filters, build_options, clean_filters
from .modules import MODULES, catalog

bp = Blueprint("api", __name__, url_prefix="/api")

TABLE_COLUMNS = ["name", "dept", "position", "status", "sex", "race", "pay", "hire", "perf", "engagement"]
SORTABLE = set(TABLE_COLUMNS) | {"tenure", "age"}


def _error(message, status, code=None):
    return jsonify({"error": code or "error", "message": message}), status


def _payload():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _dataset(body):
    ds = get_dataset(body.get("ds"))
    if ds is None:
        return None, _error("ไม่พบชุดข้อมูลนี้บนเซิร์ฟเวอร์ (อาจหมดอายุ)", 404, "dataset_not_found")
    return ds, None


def _summary(ds):
    return {k: ds[k] for k in ("id", "filename", "sample", "rows", "as_of", "warnings")}


@bp.get("/modules")
def modules():
    return jsonify(catalog())


@bp.post("/upload")
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        return _error("กรุณาเลือกไฟล์ก่อนอัปโหลด", 400)
    raw = file.read()
    if not raw:
        return _error("ไฟล์ว่างเปล่า", 400)
    try:
        ds = ingest_upload(raw, file.filename)
    except DataError as exc:
        return _error(str(exc), 422)
    return jsonify(_summary(ds))


@bp.post("/meta")
def meta():
    ds, err = _dataset(_payload())
    if err:
        return err
    return jsonify({"dataset": _summary(ds), **build_options(ds["records"])})


@bp.post("/dashboard")
def dashboard():
    body = _payload()
    ds, err = _dataset(body)
    if err:
        return err
    recs = apply_filters(ds["records"], clean_filters(body.get("filters")))
    wanted = [m for m in (body.get("modules") or []) if m in MODULES]
    return jsonify({
        "count": len(recs),
        "total": ds["rows"],
        "modules": {m: MODULES[m].compute(recs) for m in wanted},
    })


@bp.post("/employees")
def employees():
    body = _payload()
    ds, err = _dataset(body)
    if err:
        return err
    recs = apply_filters(ds["records"], clean_filters(body.get("filters")))
    sort = body.get("sort") if body.get("sort") in SORTABLE else "name"
    reverse = body.get("dir") == "desc"
    # None values always sort last, whichever the direction.
    have = [r for r in recs if r[sort] is not None]
    lack = [r for r in recs if r[sort] is None]
    have.sort(key=lambda r: r[sort].lower() if isinstance(r[sort], str) else r[sort], reverse=reverse)
    recs = have + lack
    try:
        size = min(max(int(body.get("page_size", 25)), 5), 100)
        page = max(int(body.get("page", 1)), 1)
    except (TypeError, ValueError):
        size, page = 25, 1
    pages = max(1, -(-len(recs) // size))
    page = min(page, pages)
    rows = [{c: r[c] for c in TABLE_COLUMNS} for r in recs[(page - 1) * size: page * size]]
    return jsonify({"total": len(recs), "page": page, "pages": pages, "rows": rows})