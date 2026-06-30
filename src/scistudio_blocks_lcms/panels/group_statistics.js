// Group Statistics interactive panel (ADR-051 package panel).
//
// Dependency-free ES module. host.panelPayload is prepare_prompt()'s output;
// the decision returns via host.confirm(response). Response matches run():
//   { test, fdr, alpha,
//     tables: [ { groups: {col: group}, pair: [a, b], levels: {group: number} } ] }
//
// Per table the user assigns each sample column to a group (pre-filled). The
// test is global: ttest needs a group pair; linear_trend needs an ordered level
// per group; anova uses all groups.

const TEST_LABELS = { ttest: "Welch t-test (2 groups)", anova: "One-way ANOVA", linear_trend: "Linear trend" };
const FDR_LABELS = { bh: "Benjamini-Hochberg", bonferroni: "Bonferroni", none: "none" };

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

function uniqueGroups(table, state) {
  const seen = [];
  for (const col of table.columns) {
    const g = state.groups[col];
    if (g && !seen.includes(g)) seen.push(g);
  }
  return seen;
}

export default {
  apiVersion: "1",
  mount(container, host) {
    const payload = host.panelPayload || {};
    const tables = payload.tables || [];
    const tests = payload.tests || Object.keys(TEST_LABELS);
    const fdrMethods = payload.fdr_methods || Object.keys(FDR_LABELS);
    let test = payload.test || "ttest";
    let fdr = payload.fdr || "bh";
    let alpha = payload.alpha != null ? payload.alpha : 0.05;
    let active = 0;

    const states = tables.map((t) => {
      const groups = Object.assign({}, (t.suggestion && t.suggestion.groups) || {});
      return { groups, pair: [null, null], levels: {} };
    });

    const root = el("div", { style: "font:13px system-ui,sans-serif;color:#1a1a1a;min-width:600px;" }, []);
    const header = el("div", { style: "display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:8px;" }, []);
    const tabBar = el("div", { style: "display:flex;gap:4px;border-bottom:1px solid #ddd;margin-bottom:8px;" }, []);
    const bodyWrap = el("div", { style: "max-height:360px;overflow:auto;border:1px solid #eee;" }, []);
    const testWrap = el("div", { style: "margin-top:8px;" }, []);
    const footer = el("div", { style: "display:flex;justify-content:flex-end;gap:8px;margin-top:10px;" }, []);
    root.append(header, tabBar, bodyWrap, testWrap, footer);

    function renderHeader() {
      header.replaceChildren();
      header.append(
        el("span", { style: "font-weight:600;" }, ["Test:"]),
        select(tests.map((t) => ({ value: t, label: TEST_LABELS[t] || t })), test, (v) => { test = v; renderAll(); }),
        el("span", {}, ["FDR:"]),
        select(fdrMethods.map((m) => ({ value: m, label: FDR_LABELS[m] || m })), fdr, (v) => { fdr = v; }),
      );
      const a = el("input", { type: "number", step: "0.01", style: "width:64px;padding:2px 4px;" }, []);
      a.value = String(alpha);
      a.addEventListener("change", () => { const x = parseFloat(a.value); if (!Number.isNaN(x)) alpha = x; });
      header.append(el("label", { style: "display:flex;gap:4px;align-items:center;" }, ["α", a]));
    }

    function renderTabs() {
      tabBar.replaceChildren();
      tabBar.style.display = tables.length > 1 ? "flex" : "none";
      tables.forEach((t, i) => {
        const isActive = i === active;
        tabBar.appendChild(el("button", {
          style: `padding:6px 12px;border:none;border-bottom:2px solid ${isActive ? "#2d6cdf" : "transparent"};` +
            `background:none;cursor:pointer;font-weight:${isActive ? "600" : "400"};`,
          onclick: () => { active = i; renderBody(); renderTest(); },
        }, [t.label || `Table ${i + 1}`]));
      });
    }

    function renderBody() {
      const t = tables[active], st = states[active];
      const head = el("tr", { style: "position:sticky;top:0;background:#f7f7f7;text-align:left;" },
        ["Sample column", "Group"].map((h) => el("th", { style: "padding:5px 8px;border-bottom:1px solid #e5e5e5;" }, [h])));
      const tbody = el("tbody", {}, []);
      for (const col of t.columns) {
        const input = el("input", { style: "padding:2px 6px;width:140px;", value: st.groups[col] || "" }, []);
        input.addEventListener("input", () => { st.groups[col] = input.value.trim(); renderTest(); });
        tbody.appendChild(el("tr", {}, [
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;font-family:ui-monospace,monospace;" }, [col]),
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;" }, [input]),
        ]));
      }
      bodyWrap.replaceChildren(el("table", { style: "border-collapse:collapse;width:100%;" }, [el("thead", {}, [head]), tbody]));
    }

    function renderTest() {
      const t = tables[active], st = states[active];
      const groups = uniqueGroups(t, st);
      testWrap.replaceChildren();
      if (test === "ttest") {
        const opts = [{ value: "", label: "— pick —" }].concat(groups.map((g) => ({ value: g, label: g })));
        if (!groups.includes(st.pair[0])) st.pair[0] = groups[0] || null;
        if (!groups.includes(st.pair[1])) st.pair[1] = groups[1] || null;
        testWrap.append(
          el("span", { style: "color:#444;" }, ["Compare group "]),
          select(opts, st.pair[0] || "", (v) => { st.pair[0] = v || null; }),
          el("span", {}, [" vs "]),
          select(opts, st.pair[1] || "", (v) => { st.pair[1] = v || null; }),
        );
      } else if (test === "linear_trend") {
        testWrap.append(el("div", { style: "color:#444;margin-bottom:4px;" }, ["Numeric level per group (the trend's x):"]));
        const wrap = el("div", { style: "display:flex;flex-wrap:wrap;gap:10px;" }, []);
        groups.forEach((g, idx) => {
          if (st.levels[g] == null) st.levels[g] = idx + 1;
          const inp = el("input", { type: "number", step: "any", style: "width:60px;padding:2px 4px;" }, []);
          inp.value = String(st.levels[g]);
          inp.addEventListener("change", () => { const x = parseFloat(inp.value); if (!Number.isNaN(x)) st.levels[g] = x; });
          wrap.append(el("label", { style: "display:flex;gap:4px;align-items:center;" }, [g, inp]));
        });
        testWrap.appendChild(wrap);
      } else {
        testWrap.appendChild(el("div", { style: "color:#666;" }, [`ANOVA across ${groups.length} group(s): ${groups.join(", ")}`]));
      }
    }

    function buildResponse() {
      const responseTables = tables.map((t, ti) => {
        const st = states[ti];
        const out = { groups: st.groups };
        if (test === "ttest" && st.pair[0] && st.pair[1]) out.pair = [st.pair[0], st.pair[1]];
        if (test === "linear_trend") {
          const groups = uniqueGroups(t, st);
          out.levels = {};
          for (const g of groups) if (st.levels[g] != null) out.levels[g] = st.levels[g];
        }
        return out;
      });
      return { test, fdr, alpha, tables: responseTables };
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

    function renderAll() { renderHeader(); renderTabs(); renderBody(); renderTest(); renderFooter(); }
    renderAll();
    container.replaceChildren(root);
    return { unmount() { container.replaceChildren(); } };
  },
};
