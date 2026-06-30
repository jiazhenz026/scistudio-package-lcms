// Consumption / Release interactive panel (ADR-051 package panel).
//
// Dependency-free ES module. host.panelPayload is prepare_prompt()'s output;
// the decision returns via host.confirm(response). Response matches run():
//   { tables: [ { groups: {col: group}, reference_group: name } ] }
//
// Per table the user assigns sample columns to groups (pre-filled) and picks the
// reference group (fresh / unspent medium, t0 ...). Δt and cell-number metadata
// are block config / an input port, not set here.

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
    const states = tables.map((t) => {
      const groups = Object.assign({}, (t.suggestion && t.suggestion.groups) || {});
      return { groups, reference_group: (t.suggestion && t.suggestion.reference_group) || null };
    });
    let active = 0;

    const root = el("div", { style: "font:13px system-ui,sans-serif;color:#1a1a1a;min-width:560px;" }, []);
    const tabBar = el("div", { style: "display:flex;gap:4px;border-bottom:1px solid #ddd;margin-bottom:8px;" }, []);
    const refWrap = el("div", { style: "margin-bottom:8px;" }, []);
    const bodyWrap = el("div", { style: "max-height:360px;overflow:auto;border:1px solid #eee;" }, []);
    const footer = el("div", { style: "display:flex;justify-content:flex-end;gap:8px;margin-top:10px;" }, []);
    root.append(tabBar, refWrap, bodyWrap, footer);

    function renderTabs() {
      tabBar.replaceChildren();
      tabBar.style.display = tables.length > 1 ? "flex" : "none";
      tables.forEach((t, i) => {
        const isActive = i === active;
        tabBar.appendChild(el("button", {
          style: `padding:6px 12px;border:none;border-bottom:2px solid ${isActive ? "#2d6cdf" : "transparent"};` +
            `background:none;cursor:pointer;font-weight:${isActive ? "600" : "400"};`,
          onclick: () => { active = i; renderRef(); renderBody(); },
        }, [t.label || `Table ${i + 1}`]));
      });
    }

    function renderRef() {
      const t = tables[active], st = states[active];
      const groups = uniqueGroups(t, st);
      if (!groups.includes(st.reference_group)) st.reference_group = groups[0] || null;
      const opts = [{ value: "", label: "— pick —" }].concat(groups.map((g) => ({ value: g, label: g })));
      refWrap.replaceChildren(
        el("span", { style: "font-weight:600;margin-right:6px;" }, ["Reference group (fresh / t0):"]),
        select(opts, st.reference_group || "", (v) => { st.reference_group = v || null; }),
      );
    }

    function renderBody() {
      const t = tables[active], st = states[active];
      const head = el("tr", { style: "position:sticky;top:0;background:#f7f7f7;text-align:left;" },
        ["Sample column", "Group"].map((h) => el("th", { style: "padding:5px 8px;border-bottom:1px solid #e5e5e5;" }, [h])));
      const tbody = el("tbody", {}, []);
      for (const col of t.columns) {
        const input = el("input", { style: "padding:2px 6px;width:140px;", value: st.groups[col] || "" }, []);
        input.addEventListener("input", () => { st.groups[col] = input.value.trim(); renderRef(); });
        tbody.appendChild(el("tr", {}, [
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;font-family:ui-monospace,monospace;" }, [col]),
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;" }, [input]),
        ]));
      }
      bodyWrap.replaceChildren(el("table", { style: "border-collapse:collapse;width:100%;" }, [el("thead", {}, [head]), tbody]));
    }

    function buildResponse() {
      return {
        tables: tables.map((t, ti) => ({ groups: states[ti].groups, reference_group: states[ti].reference_group })),
      };
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

    renderTabs(); renderRef(); renderBody(); renderFooter();
    container.replaceChildren(root);
    return { unmount() { container.replaceChildren(); } };
  },
};
