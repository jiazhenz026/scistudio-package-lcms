// Background Subtraction interactive panel (ADR-051 package panel).
//
// A dependency-free ES module served at the block's PanelManifest.module_url.
// The frontend host calls `mount(container, host)`; `host.panelPayload` is the
// block's prepare_prompt() output, and the user's decision is returned via
// `host.confirm(response)`. The response shape matches what the block's run()
// reads: { tables: [ { assignments: {sample: [bgCol...]}, aggregation, drop } ] }.
//
// Pre-filled from the per-table name heuristic (suggestion); the user corrects
// roles and sample→background matches, with wildcard rules for bulk edits.

const ROLES = ["sample", "background", "qc", "ignore"];

function matchColumn(name, mode, text) {
  const n = String(name).toLowerCase();
  const t = String(text).toLowerCase();
  if (!t) return false;
  if (mode === "contains") return n.includes(t);
  if (mode === "starts") return n.startsWith(t);
  if (mode === "ends") return n.endsWith(t);
  if (mode === "equals") return n === t;
  if (mode === "wildcard") {
    const escaped = t.replace(/[.+^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp("^" + escaped.replace(/\*/g, ".*").replace(/\?/g, ".") + "$");
    return re.test(n);
  }
  return false;
}

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k === "style") node.style.cssText = v;
    else if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v != null) node.setAttribute(k, v);
  }
  for (const c of children || []) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  return node;
}

function select(options, value, onChange) {
  const s = el("select", { style: "padding:2px 4px;" }, []);
  for (const opt of options) {
    const o = el("option", { value: opt.value }, [opt.label]);
    if (opt.value === value) o.selected = true;
    s.appendChild(o);
  }
  s.addEventListener("change", () => onChange(s.value));
  return s;
}

function initTableState(table) {
  const suggestion = table.suggestion || {};
  const roles = suggestion.roles || {};
  const groups = suggestion.groups || {};
  const assignments = suggestion.assignments || {};
  const state = {};
  for (const col of table.columns) {
    const role = roles[col] || "sample";
    // The background group a sample subtracts: derive from the suggested
    // assignment, falling back to the column's own group key / global.
    let bgGroup = groups[col] || "_global";
    const assigned = assignments[col];
    if (assigned && assigned.length) {
      for (const [g, cols] of Object.entries(suggestion.background_groups || {})) {
        if (cols.length === assigned.length && cols.every((c) => assigned.includes(c))) { bgGroup = g; break; }
      }
    }
    state[col] = { role, group: groups[col] || "_global", bgGroup };
  }
  return state;
}

function backgroundGroups(table, state) {
  const groups = {};
  for (const col of table.columns) {
    if (state[col].role === "background") {
      const g = state[col].group || "_global";
      (groups[g] = groups[g] || []).push(col);
    }
  }
  return groups;
}

export default {
  apiVersion: "1",
  mount(container, host) {
    const payload = host.panelPayload || {};
    const tables = payload.tables || [];
    const states = tables.map(initTableState);
    let aggregation = (tables[0] && tables[0].suggestion && tables[0].suggestion.aggregation) || "median";
    let active = 0;

    const root = el("div", { style: "font:13px system-ui,sans-serif;color:#1a1a1a;min-width:640px;" }, []);
    const tabBar = el("div", { style: "display:flex;gap:4px;border-bottom:1px solid #ddd;margin-bottom:8px;" }, []);
    const toolbar = el("div", { style: "display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px;" }, []);
    const tableWrap = el("div", { style: "max-height:420px;overflow:auto;border:1px solid #eee;" }, []);
    const summary = el("div", { style: "margin-top:8px;color:#444;" }, []);
    const footer = el("div", { style: "display:flex;justify-content:flex-end;gap:8px;margin-top:10px;" }, []);
    root.append(tabBar, toolbar, tableWrap, summary, footer);

    function renderTabs() {
      tabBar.replaceChildren();
      tables.forEach((t, i) => {
        const isActive = i === active;
        tabBar.appendChild(el("button", {
          style: `padding:6px 12px;border:none;border-bottom:2px solid ${isActive ? "#2d6cdf" : "transparent"};` +
            `background:none;cursor:pointer;font-weight:${isActive ? "600" : "400"};`,
          onclick: () => { active = i; renderAll(); },
        }, [t.label || `Table ${i + 1}`]));
      });
    }

    function renderToolbar() {
      toolbar.replaceChildren();
      // Aggregation for multi-replicate backgrounds.
      toolbar.append(el("span", {}, ["Background replicate aggregation:"]),
        select([{ value: "median", label: "median" }, { value: "mean", label: "mean" }], aggregation, (v) => { aggregation = v; }));
      // Wildcard rule: match columns -> set a role.
      const modeSel = select([
        { value: "contains", label: "contains" }, { value: "starts", label: "starts with" },
        { value: "ends", label: "ends with" }, { value: "equals", label: "equals" }, { value: "wildcard", label: "wildcard (*?)" },
      ], "contains", () => {});
      const textIn = el("input", { style: "padding:3px 6px;width:120px;", placeholder: "e.g. blank or A_*" }, []);
      const roleSel = select(ROLES.map((r) => ({ value: r, label: r })), "background", () => {});
      const apply = el("button", { style: "padding:4px 10px;cursor:pointer;" }, ["Apply rule"]);
      apply.addEventListener("click", () => {
        const t = tables[active], st = states[active];
        for (const col of t.columns) if (matchColumn(col, modeSel.value, textIn.value)) st[col].role = roleSel.value;
        renderAll();
      });
      toolbar.append(el("span", { style: "margin-left:16px;border-left:1px solid #ddd;padding-left:16px;" }, ["Rule: columns"]),
        modeSel, textIn, el("span", {}, ["→ set role"]), roleSel, apply);
    }

    function renderTable() {
      const t = tables[active], st = states[active], stats = t.stats || {};
      const bgGroups = backgroundGroups(t, st);
      const groupOptions = Object.keys(bgGroups).map((g) => ({ value: g, label: g === "_global" ? "(global)" : g }));

      const head = el("tr", { style: "position:sticky;top:0;background:#f7f7f7;text-align:left;" },
        ["Column", "Role", "Background", "median"].map((h) => el("th", { style: "padding:5px 8px;border-bottom:1px solid #e5e5e5;" }, [h])));
      const body = el("tbody", {}, []);
      for (const col of t.columns) {
        const s = st[col];
        const roleCell = select(ROLES.map((r) => ({ value: r, label: r })), s.role, (v) => { s.role = v; renderTable(); renderSummary(); });
        let bgCell;
        if (s.role === "sample") {
          const opts = groupOptions.length ? groupOptions : [{ value: "", label: "— none —" }];
          if (!bgGroups[s.bgGroup]) s.bgGroup = opts[0].value;
          bgCell = select(opts, s.bgGroup, (v) => { s.bgGroup = v; });
        } else {
          bgCell = el("span", { style: "color:#aaa;" }, ["—"]);
        }
        const stat = stats[col];
        body.appendChild(el("tr", {}, [
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;font-family:ui-monospace,monospace;" }, [col]),
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;" }, [roleCell]),
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;" }, [bgCell]),
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;color:#666;" }, [stat == null ? "" : String(Math.round(stat))]),
        ]));
      }
      tableWrap.replaceChildren(el("table", { style: "border-collapse:collapse;width:100%;" }, [el("thead", {}, [head]), body]));
    }

    function renderSummary() {
      const t = tables[active], st = states[active];
      const counts = { sample: 0, background: 0, qc: 0, ignore: 0 };
      for (const col of t.columns) counts[st[col].role]++;
      const bgGroups = backgroundGroups(t, st);
      let unassigned = 0;
      for (const col of t.columns) if (st[col].role === "sample" && !bgGroups[st[col].bgGroup]) unassigned++;
      summary.replaceChildren(el("span", {}, [
        `${counts.sample} samples → ${Object.keys(bgGroups).length} backgrounds · ${counts.qc} QC · ${counts.ignore} ignored`,
      ]));
      if (unassigned) summary.appendChild(el("span", { style: "color:#c0392b;margin-left:8px;" }, [`· ⚠ ${unassigned} unassigned`]));
    }

    function renderFooter() {
      footer.replaceChildren(
        el("button", { style: "padding:6px 14px;cursor:pointer;", onclick: () => host.cancel() }, ["Cancel"]),
        el("button", {
          style: "padding:6px 14px;cursor:pointer;background:#2d6cdf;color:#fff;border:none;border-radius:4px;",
          onclick: () => host.confirm(buildResponse()),
        }, ["Confirm"]),
      );
    }

    function buildResponse() {
      const responseTables = tables.map((t, ti) => {
        const st = states[ti];
        const bgGroups = backgroundGroups(t, st);
        const assignments = {};
        const drop = [];
        for (const col of t.columns) {
          const role = st[col].role;
          if (role === "sample") {
            const g = bgGroups[st[col].bgGroup];
            if (g && g.length) assignments[col] = g.slice();
          } else if (role === "background" || role === "ignore") {
            drop.push(col);
          }
        }
        return { assignments, aggregation, drop };
      });
      return { tables: responseTables };
    }

    function renderAll() { renderTabs(); renderToolbar(); renderTable(); renderSummary(); renderFooter(); }
    renderAll();
    container.replaceChildren(root);
    return { unmount() { container.replaceChildren(); } };
  },
};
