// Normalization interactive panel (ADR-051 package panel).
//
// Dependency-free ES module served at the block's PanelManifest.module_url.
// host.panelPayload is the block's prepare_prompt() output; the decision is
// returned via host.confirm(response). Response shape matches run():
//   { method, drop_reference,
//     tables: [ { reference: {compound, isotopeLabel?}, pairs: [{compound, is_label}] } ] }
//
// Method is global; the reference (single feature) or per-metabolite internal
// standard is chosen per table. total / median need no reference.

const METHOD_LABELS = {
  single_reference: "Single reference feature",
  isotope_internal_standard: "Isotope internal standard (per metabolite)",
  total: "Total (÷ column sum)",
  median: "Median (÷ column median)",
};

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
  // reference: {compound, isotopeLabel}; pairs: {compound -> is_label}
  const suggestion = table.suggestion || {};
  const compounds = table.compounds || [];
  const refCompound = suggestion.single_reference || (compounds[0] && compounds[0].compound) || "";
  return { reference: { compound: refCompound, isotopeLabel: "__all__" }, pairs: {} };
}

export default {
  apiVersion: "1",
  mount(container, host) {
    const payload = host.panelPayload || {};
    const tables = payload.tables || [];
    const methods = payload.methods || Object.keys(METHOD_LABELS);
    const states = tables.map(initTableState);
    let method = payload.method || "total";
    let dropReference = payload.drop_reference !== false;
    let active = 0;

    const root = el("div", { style: "font:13px system-ui,sans-serif;color:#1a1a1a;min-width:560px;" }, []);
    const header = el("div", { style: "display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:8px;" }, []);
    const tabBar = el("div", { style: "display:flex;gap:4px;border-bottom:1px solid #ddd;margin-bottom:8px;" }, []);
    const bodyWrap = el("div", { style: "min-height:80px;max-height:420px;overflow:auto;" }, []);
    const footer = el("div", { style: "display:flex;justify-content:flex-end;gap:8px;margin-top:10px;" }, []);
    root.append(header, tabBar, bodyWrap, footer);

    function renderHeader() {
      header.replaceChildren();
      header.append(
        el("span", { style: "font-weight:600;" }, ["Method:"]),
        select(methods.map((m) => ({ value: m, label: METHOD_LABELS[m] || m })), method, (v) => { method = v; renderAll(); }),
      );
      const drop = el("input", { type: "checkbox" }, []);
      drop.checked = dropReference;
      drop.addEventListener("change", () => { dropReference = drop.checked; });
      header.append(el("label", { style: "display:flex;gap:4px;align-items:center;" }, [drop, "drop reference rows"]));
    }

    function renderTabs() {
      tabBar.replaceChildren();
      const needsTabs = method === "single_reference" || method === "isotope_internal_standard";
      tabBar.style.display = needsTabs && tables.length > 1 ? "flex" : "none";
      if (!needsTabs) return;
      tables.forEach((t, i) => {
        const isActive = i === active;
        tabBar.appendChild(el("button", {
          style: `padding:6px 12px;border:none;border-bottom:2px solid ${isActive ? "#2d6cdf" : "transparent"};` +
            `background:none;cursor:pointer;font-weight:${isActive ? "600" : "400"};`,
          onclick: () => { active = i; renderBody(); },
        }, [t.label || `Table ${i + 1}`]));
      });
    }

    function renderBody() {
      bodyWrap.replaceChildren();
      if (method === "total" || method === "median") {
        bodyWrap.appendChild(el("div", { style: "color:#666;padding:12px 4px;" }, [
          `Each sample column is divided by its ${method === "total" ? "sum" : "median"}. No reference to pick.`,
        ]));
        return;
      }
      const t = tables[active], st = states[active];
      const compounds = t.compounds || [];

      if (method === "single_reference") {
        const compOpts = compounds.map((c) => ({ value: c.compound, label: c.compound }));
        const compSel = select(compOpts.length ? compOpts : [{ value: "", label: "— none —" }], st.reference.compound,
          (v) => { st.reference.compound = v; st.reference.isotopeLabel = "__all__"; renderBody(); });
        const chosen = compounds.find((c) => c.compound === st.reference.compound);
        const labelOpts = [{ value: "__all__", label: "(all rows — summed)" }]
          .concat((chosen && chosen.labels || []).map((l) => ({ value: l, label: l })));
        const labelSel = select(labelOpts, st.reference.isotopeLabel, (v) => { st.reference.isotopeLabel = v; });
        bodyWrap.append(
          el("div", { style: "margin-bottom:6px;color:#444;" }, ["Reference feature (every feature ÷ this, per sample):"]),
          el("div", { style: "display:flex;gap:10px;align-items:center;" }, [
            el("span", {}, ["compound"]), compSel, el("span", {}, ["isotopologue"]), labelSel,
          ]),
        );
        return;
      }

      // isotope_internal_standard: per-compound IS-label picker.
      bodyWrap.appendChild(el("div", { style: "margin-bottom:6px;color:#444;" }, [
        "Pick each metabolite's internal-standard isotopologue (divides that compound's other rows):",
      ]));
      const head = el("tr", { style: "position:sticky;top:0;background:#f7f7f7;text-align:left;" },
        ["Compound", "Internal standard (isotopeLabel)"].map((h) => el("th", { style: "padding:5px 8px;border-bottom:1px solid #e5e5e5;" }, [h])));
      const tbody = el("tbody", {}, []);
      for (const c of compounds) {
        const opts = [{ value: "", label: "— none —" }].concat((c.labels || []).map((l) => ({ value: l, label: l })));
        const sel = select(opts, st.pairs[c.compound] || "", (v) => { if (v) st.pairs[c.compound] = v; else delete st.pairs[c.compound]; });
        tbody.appendChild(el("tr", {}, [
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;font-family:ui-monospace,monospace;" }, [c.compound]),
          el("td", { style: "padding:4px 8px;border-bottom:1px solid #f0f0f0;" }, [sel]),
        ]));
      }
      bodyWrap.appendChild(el("table", { style: "border-collapse:collapse;width:100%;" }, [el("thead", {}, [head]), tbody]));
    }

    function buildResponse() {
      const responseTables = tables.map((t, ti) => {
        const st = states[ti];
        const out = {};
        if (method === "single_reference") {
          const ref = { compound: st.reference.compound };
          if (st.reference.isotopeLabel && st.reference.isotopeLabel !== "__all__") ref.isotopeLabel = st.reference.isotopeLabel;
          out.reference = ref;
        } else if (method === "isotope_internal_standard") {
          out.pairs = Object.entries(st.pairs).map(([compound, is_label]) => ({ compound, is_label }));
        }
        return out;
      });
      return { method, drop_reference: dropReference, tables: responseTables };
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

    function renderAll() { renderHeader(); renderTabs(); renderBody(); renderFooter(); }
    renderAll();
    container.replaceChildren(root);
    return { unmount() { container.replaceChildren(); } };
  },
};
