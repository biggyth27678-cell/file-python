(() => {
  "use strict";

  const FILTER_LABELS = {
    dept: "แผนก", status: "สถานะ", position: "ตำแหน่ง", sex: "เพศ", race: "เชื้อชาติ",
    marital: "สถานภาพสมรส", perf: "ผลประเมิน", source: "แหล่งสรรหา", state: "รัฐ",
  };
  const PALETTE = ["#2a5c8a", "#d99a1e", "#2f8f83", "#b04a64", "#7566a8", "#86994f", "#4fa3c7", "#8a94a0"];
  const TABLE_COLS = [
    ["name", "ชื่อ"], ["dept", "แผนก"], ["position", "ตำแหน่ง"], ["status", "สถานะ"], ["sex", "เพศ"],
    ["pay", "ค่าจ้าง", true], ["hire", "เริ่มงาน"], ["perf", "ผลประเมิน"], ["engagement", "Engagement", true],
  ];
  const MAX_UPLOAD = 4 * 1024 * 1024;

  const nf = new Intl.NumberFormat("en-US");
  const FMT = {
    int: (v) => nf.format(v),
    dec: (v) => v.toFixed(2),
    pct: (v) => v.toFixed(1) + "%",
    yrs: (v) => v.toFixed(1) + " ปี",
    text: (v) => String(v),
  };
  const fmt = (kind, v) => (v === null || v === undefined || Number.isNaN(v) ? "–" : (FMT[kind] || FMT.int)(v));

  const $ = (sel, root = document) => root.querySelector(sel);

  function h(tag, props = {}, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) node.append(kid);
    return node;
  }

  const LS = {
    get(key, fallback) { try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } },
    del(key) { try { localStorage.removeItem(key); } catch { /* ignore */ } },
  };

  const saved = LS.get("hr_upload", null);
  const state = {
    ds: saved && saved.id ? saved.id : "sample",
    meta: null, catalog: null, data: null, filters: {},
    active: new Set(LS.get("hr_modules", ["overview", "workforce"])),
    table: { page: 1, sort: "name", dir: "asc" },
    charts: [], req: 0,
  };

  class ResetError extends Error {}

  /* ---------- UI helpers ---------- */
  let toastTimer;
  function toast(message, isError = false) {
    const t = $("#toast");
    t.textContent = message;
    t.className = "toast" + (isError ? " error" : "");
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 5500);
  }
  const setBusy = (on) => document.body.classList.toggle("busy", on);
  const fail = (e) => { if (!(e instanceof ResetError)) toast(e.message || "เกิดข้อผิดพลาด", true); };

  /* ---------- API (re-sends the saved upload if the server lost it) ---------- */
  async function restoreDataset() {
    const s = LS.get("hr_upload", null);
    if (s && s.text && s.id === state.ds) {
      const form = new FormData();
      form.append("file", new Blob([s.text], { type: "text/plain" }), s.filename || "upload.txt");
      const res = await fetch("/api/upload", { method: "POST", body: form });
      if (res.ok) {
        const info = await res.json();
        state.ds = info.id;
        LS.set("hr_upload", { ...s, id: info.id });
        return true;
      }
    }
    LS.del("hr_upload");
    state.ds = "sample";
    toast("ชุดข้อมูลที่อัปโหลดหมดอายุบนเซิร์ฟเวอร์ จึงกลับไปใช้ข้อมูลตัวอย่าง");
    setTimeout(boot, 0);
    return false;
  }

  async function api(path, body = {}) {
    const send = () => fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ds: state.ds, ...body }),
    });
    let res = await send();
    if (res.status === 404) {
      const err = await res.clone().json().catch(() => ({}));
      if (err.error === "dataset_not_found") {
        if (!(await restoreDataset())) throw new ResetError();
        res = await send();
      }
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.message || `เกิดข้อผิดพลาด (${res.status})`);
    return data;
  }

  /* ---------- dataset / upload ---------- */
  function renderDataset() {
    const d = state.meta.dataset;
    const box = $("#dataset-info");
    box.replaceChildren(
      h("strong", { text: d.filename }),
      h("span", { text: d.sample ? "ข้อมูลตัวอย่างที่มากับระบบ" : "ไฟล์ที่คุณอัปโหลด" }),
      h("span", { text: `${nf.format(d.rows)} แถว · ข้อมูลถึง ${d.as_of}` }),
      ...d.warnings.map((w) => h("span", { class: "warn", text: w })),
    );
    $("#use-sample").hidden = d.sample;
  }

  async function uploadFile(file) {
    if (!file) return;
    if (file.size > MAX_UPLOAD) return toast("ไฟล์ใหญ่เกิน 4 MB", true);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.message || `อัปโหลดไม่สำเร็จ (${res.status})`);
      const text = await file.text();
      if (!LS.set("hr_upload", { id: data.id, filename: data.filename, text })) LS.del("hr_upload");
      state.ds = data.id;
      state.filters = {};
      state.table.page = 1;
      toast(`อัปโหลด ${data.filename} สำเร็จ (${nf.format(data.rows)} แถว)`);
      await boot();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
      $("#file-input").value = "";
    }
  }

  function initUpload() {
    $("#file-input").addEventListener("change", (e) => uploadFile(e.target.files[0]));
    const zone = $("#dropzone");
    ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("over"); }));
    zone.addEventListener("drop", (e) => uploadFile(e.dataTransfer.files[0]));
    $("#use-sample").addEventListener("click", () => {
      LS.del("hr_upload");
      state.ds = "sample"; state.filters = {}; state.table.page = 1;
      boot();
    });
  }

  /* ---------- module toggles ---------- */
  function renderModuleNav() {
    const nav = $("#module-nav");
    nav.replaceChildren(...state.catalog.map((m) => h("button", {
      type: "button", "aria-pressed": String(state.active.has(m.id)), "data-id": m.id,
      onclick: () => toggleModule(m.id),
    }, m.title, h("small", { text: m.desc }))));
  }
  function setActive(ids) {
    state.active = new Set(ids);
    LS.set("hr_modules", [...state.active]);
    renderModuleNav();
    refresh();
  }
  function toggleModule(id) {
    const next = new Set(state.active);
    next.has(id) ? next.delete(id) : next.add(id);
    setActive([...next]);
  }

  /* ---------- filters ---------- */
  let refreshTimer;
  function scheduleRefresh() {
    state.table.page = 1;
    updateFilterState();
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refresh, 220);
  }
  function setFilter(key, value) {
    if (value === "" || value === null || value === undefined || (Array.isArray(value) && !value.length) || Number.isNaN(value)) delete state.filters[key];
    else state.filters[key] = value;
    scheduleRefresh();
  }
  function toggleValue(key, value, on) {
    const cur = new Set(state.filters[key] || []);
    on ? cur.add(value) : cur.delete(value);
    setFilter(key, [...cur]);
  }
  function updateFilterState() {
    document.querySelectorAll(".fdrop").forEach((dd) => {
      const n = (state.filters[dd.dataset.key] || []).length;
      const badge = $(".badge", dd);
      badge.textContent = n;
      badge.hidden = !n;
      dd.classList.toggle("on", n > 0);
    });
    $("#filters-reset").hidden = !Object.keys(state.filters).length;
  }

  function dropdown(key) {
    const opts = state.meta.options[key] || [];
    const current = new Set(state.filters[key] || []);
    const panel = h("div", { class: "fpanel" },
      h("div", { class: "fpanel-head" }, h("button", {
        class: "link", type: "button",
        onclick: () => { panel.querySelectorAll("input").forEach((i) => { i.checked = false; }); setFilter(key, []); },
      }, "ล้างที่เลือก")),
      ...opts.map((o, i) => {
        const id = `f-${key}-${i}`;
        const cb = h("input", { type: "checkbox", id, value: o.v });
        cb.checked = current.has(o.v);
        cb.addEventListener("change", () => toggleValue(key, o.v, cb.checked));
        return h("label", { class: "fopt", for: id }, cb, h("span", { text: o.v }), h("span", { class: "fopt-n", text: nf.format(o.n) }));
      }));
    const dd = h("details", { class: "fdrop", "data-key": key },
      h("summary", {}, h("span", { text: FILTER_LABELS[key] }), h("span", { class: "badge", hidden: true })), panel);
    dd.addEventListener("toggle", () => {
      if (dd.open) document.querySelectorAll(".fdrop[open]").forEach((o) => { if (o !== dd) o.open = false; });
    });
    return dd;
  }

  function rangeInput(label, key, placeholder, step = "1") {
    const input = h("input", { type: "number", id: `r-${key}`, placeholder: placeholder ?? "", step, inputmode: "decimal" });
    if (state.filters[key] !== undefined) input.value = state.filters[key];
    input.addEventListener("input", () => setFilter(key, input.value === "" ? "" : Number(input.value)));
    return [h("label", { for: `r-${key}`, text: label }), input];
  }

  function renderFilters() {
    const box = $("#filter-controls");
    box.replaceChildren();
    for (const key of Object.keys(FILTER_LABELS)) {
      if ((state.meta.options[key] || []).length > 1) box.append(dropdown(key));
    }
    const yr = state.meta.ranges.hire_year, pay = state.meta.ranges.pay;
    if (yr) box.append(h("span", { class: "range" }, h("span", { class: "range-title", text: "ปีที่เริ่มงาน" }),
      ...rangeInput("ตั้งแต่", "hire_from", yr[0]), ...rangeInput("ถึง", "hire_to", yr[1])));
    if (pay) box.append(h("span", { class: "range" }, h("span", { class: "range-title", text: "ค่าจ้าง" }),
      ...rangeInput("ตั้งแต่", "pay_min", pay[0], "0.5"), ...rangeInput("ถึง", "pay_max", pay[1], "0.5")));
    const q = h("input", { type: "search", placeholder: "ค้นหาชื่อหรือตำแหน่ง", "aria-label": "ค้นหาชื่อหรือตำแหน่ง" });
    q.value = state.filters.q || "";
    q.addEventListener("input", () => setFilter("q", q.value.trim()));
    box.append(h("span", { class: "search" }, q));
    updateFilterState();
  }

  /* ---------- meter ---------- */
  function renderMeter(count, total) {
    $("#meter-count").textContent = nf.format(count);
    $("#meter-total").textContent = nf.format(total);
    $("#meter-fill").style.width = (total ? (count / total) * 100 : 0) + "%";
  }

  /* ---------- charts ---------- */
  function destroyCharts() {
    state.charts.forEach((c) => c.destroy());
    state.charts = [];
  }

  function drawChart(canvas, c) {
    const horizontal = c.type === "hbar";
    const kind = horizontal ? "bar" : c.type;
    const pie = kind === "doughnut";
    const multi = c.series.length > 1;
    const datasets = c.series.map((s, i) => {
      const color = PALETTE[(multi ? i : 0) % PALETTE.length];
      if (pie) return { label: s.name, data: s.data, backgroundColor: c.labels.map((_, j) => PALETTE[j % PALETTE.length]), borderColor: "#fff", borderWidth: 2 };
      if (kind === "line") return { label: s.name, data: s.data, borderColor: color, backgroundColor: color, tension: 0.25, pointRadius: 3, borderWidth: 2 };
      return { label: s.name, data: s.data, backgroundColor: color, borderRadius: 2, maxBarThickness: 38 };
    });
    const category = {
      grid: { display: false }, stacked: c.stacked,
      ticks: { callback(v) { const l = String(this.getLabelForValue(v)); return l.length > 28 ? l.slice(0, 27) + "…" : l; } },
    };
    const value = {
      beginAtZero: true, stacked: c.stacked, grid: { color: "#e3e8ee" },
      ticks: { callback: (v) => (c.fmt === "pct" ? v + "%" : nf.format(v)) },
    };
    const total = pie ? c.series[0].data.reduce((a, b) => a + b, 0) : 0;
    state.charts.push(new Chart(canvas, {
      type: kind,
      data: { labels: c.labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? "y" : "x",
        cutout: pie ? "62%" : undefined,
        plugins: {
          legend: { display: pie || multi, position: "bottom", labels: { boxWidth: 10, usePointStyle: true } },
          tooltip: {
            callbacks: {
              label(ctx) {
                const raw = typeof ctx.parsed === "number" ? ctx.parsed : (horizontal ? ctx.parsed.x : ctx.parsed.y);
                if (pie) return `${ctx.label}: ${fmt(c.fmt, raw)} (${total ? ((raw / total) * 100).toFixed(1) : 0}%)`;
                return `${ctx.dataset.label}: ${fmt(c.fmt, raw)}`;
              },
            },
          },
        },
        scales: pie ? {} : horizontal ? { y: category, x: value } : { x: category, y: value },
      },
    }));
  }

  function chartPanel(c, pending) {
    const empty = !c.labels.length || c.series.every((s) => s.data.every((v) => !v));
    const height = c.type === "hbar" ? Math.max(200, c.labels.length * 26 + 56) : 260;
    const box = h("div", { class: "chart-box", style: `height:${empty ? 120 : height}px` });
    if (empty) box.append(h("p", { class: "no-data", text: "ไม่มีข้อมูลสำหรับตัวกรองนี้" }));
    else if (typeof Chart === "undefined") box.append(h("p", { class: "no-data", text: "โหลด Chart.js ไม่สำเร็จ ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต" }));
    else { const canvas = h("canvas", { role: "img", "aria-label": c.title }); box.append(canvas); pending.push([canvas, c]); }
    return h("article", { class: "panel" + (c.type === "line" ? " wide" : "") }, h("h3", { text: c.title }), box);
  }

  const kpiRow = (kpis) => h("div", { class: "kpis" }, ...kpis.map((k) => h("div", { class: "kpi" },
    h("p", { class: "kpi-label", text: k.label }),
    h("p", { class: "kpi-value" + (k.fmt === "text" ? " text" : ""), text: fmt(k.fmt, k.value) }),
    k.hint ? h("p", { class: "kpi-hint", text: k.hint }) : null)));

  /* ---------- employee table ---------- */
  async function loadTable() {
    const host = $("#table-host");
    if (!host) return;
    const t = state.table;
    const data = await api("/api/employees", { filters: state.filters, sort: t.sort, dir: t.dir, page: t.page, page_size: 25 });
    t.page = data.page;
    const head = h("tr", {}, ...TABLE_COLS.map(([key, label, num]) => h("th", {
      class: num ? "num" : null, scope: "col",
      "aria-sort": t.sort === key ? (t.dir === "asc" ? "ascending" : "descending") : "none",
    }, h("button", {
      type: "button", text: label,
      onclick: () => { t.dir = t.sort === key && t.dir === "asc" ? "desc" : "asc"; t.sort = key; t.page = 1; loadTable().catch(fail); },
    }))));
    const body = data.rows.map((r) => h("tr", {}, ...TABLE_COLS.map(([key, , num]) => h("td", {
      class: num ? "num" : null,
      text: r[key] === null || r[key] === undefined ? "–" : key === "pay" ? Number(r[key]).toFixed(2) : String(r[key]),
    }))));
    const go = (p) => { t.page = p; loadTable().catch(fail); };
    host.replaceChildren(
      h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, head), h("tbody", {}, body))),
      h("div", { class: "pager" },
        h("span", { text: `${nf.format(data.total)} คน · หน้า ${data.page} จาก ${data.pages}` }),
        h("button", { class: "btn", type: "button", text: "ก่อนหน้า", disabled: data.page <= 1, onclick: () => go(data.page - 1) }),
        h("button", { class: "btn", type: "button", text: "ถัดไป", disabled: data.page >= data.pages, onclick: () => go(data.page + 1) })),
    );
  }

  /* ---------- dashboard ---------- */
  function renderModules() {
    destroyCharts();
    const host = $("#modules");
    host.replaceChildren();
    const active = state.catalog.filter((m) => state.active.has(m.id));
    if (!active.length) {
      host.append(h("p", { class: "empty", text: "ยังไม่ได้เลือกโมดูล เลือกโมดูลจากรายการทางซ้ายเพื่อแสดงข้อมูล" }));
      return;
    }
    const noRows = state.data.count === 0;
    const pending = [];
    for (const m of active) {
      const sec = h("section", { class: "module", id: `mod-${m.id}`, "aria-labelledby": `h-${m.id}` },
        h("header", { class: "mod-head" }, h("h2", { id: `h-${m.id}`, text: m.title }), h("p", { text: m.desc })));
      if (noRows) {
        sec.append(h("p", { class: "empty", text: "ไม่มีพนักงานที่ตรงกับตัวกรอง ลองผ่อนเงื่อนไขบางข้อ" }));
      } else if (m.id === "employees") {
        sec.append(h("div", { id: "table-host" }));
      } else if (state.data.modules[m.id]) {
        const d = state.data.modules[m.id];
        sec.append(kpiRow(d.kpis), h("div", { class: "charts" }, d.charts.map((c) => chartPanel(c, pending))));
      }
      host.append(sec);
    }
    pending.forEach(([canvas, c]) => drawChart(canvas, c));
  }

  async function refresh() {
    const id = ++state.req;
    const modules = state.catalog.filter((m) => state.active.has(m.id) && m.id !== "employees").map((m) => m.id);
    setBusy(true);
    try {
      const data = await api("/api/dashboard", { filters: state.filters, modules });
      if (id !== state.req) return;
      state.data = data;
      renderMeter(data.count, data.total);
      renderModules();
      if (state.active.has("employees") && data.count > 0) await loadTable();
    } catch (e) {
      fail(e);
    } finally {
      if (id === state.req) setBusy(false);
    }
  }

  async function boot() {
    setBusy(true);
    try {
      if (!state.catalog) state.catalog = await (await fetch("/api/modules")).json();
      state.active = new Set([...state.active].filter((id) => state.catalog.some((m) => m.id === id)));
      state.meta = await api("/api/meta");
      renderDataset();
      renderModuleNav();
      renderFilters();
      await refresh();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  /* ---------- init ---------- */
  if (typeof Chart !== "undefined") {
    Chart.defaults.font.family = '"IBM Plex Sans Thai", system-ui, sans-serif';
    Chart.defaults.color = "#5b6b7b";
  }
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".fdrop")) document.querySelectorAll(".fdrop[open]").forEach((d) => { d.open = false; });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") document.querySelectorAll(".fdrop[open]").forEach((d) => { d.open = false; });
  });
  $("#filters-reset").addEventListener("click", () => { state.filters = {}; renderFilters(); scheduleRefresh(); });
  $("#mods-all").addEventListener("click", () => setActive(state.catalog.map((m) => m.id)));
  $("#mods-none").addEventListener("click", () => setActive([]));
  initUpload();
  boot();
})();