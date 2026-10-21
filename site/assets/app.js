/* norapi site: client-side search over search-index.json, a ⌘K palette, copy buttons. No framework. */
(function () {
  "use strict";
  const root = document.documentElement.dataset.root || "./";
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

  const ACCESS = { open: "Åpen", restricted: "Begrenset", "non-public": "Ikke offentlig", unknown: "Tilgang ukjent" };
  const AUTH = { none: "Ingen auth", "api-key": "API-nøkkel", maskinporten: "Maskinporten", "id-porten": "ID-porten", oauth2: "OAuth2", unknown: "" };

  let apis = null, ops = null, apisPromise = null, opsPromise = null;

  function norm(s) {
    return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/æ/g, "ae").replace(/ø/g, "o").replace(/å/g, "a");
  }
  function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  function loadApis() {
    if (!apisPromise) {
      apisPromise = fetch(root + "search-index.json").then((r) => r.json()).then((rows) => {
        apis = rows.map((a) => ({ ...a, _t: norm(a.t + " " + (a.e || "")), _k: norm((a.k || []).join(" ")), _p: norm(a.p), _s: norm((a.s || "") + " " + (a.n || "")) }));
        return apis;
      });
    }
    return apisPromise;
  }
  function loadOps() {
    if (!opsPromise) {
      opsPromise = fetch(root + "ops-index.json").then((r) => (r.ok ? r.json() : [])).then((rows) => {
        ops = rows.map((o) => ({ ...o, _x: norm(o.p + " " + (o.s || "")) }));
        return ops;
      }).catch(() => (ops = []));
    }
    return opsPromise;
  }

  function scoreApi(a, terms) {
    let total = 0;
    for (const t of terms) {
      let s = 0;
      if (a._t.includes(t)) s += a._t.startsWith(t) ? 9 : 6;
      if (a._k.includes(t)) s += 4;
      if (a._p.includes(t)) s += 3;
      if (a._s.includes(t)) s += 1;
      if (!s) return 0;
      total += s;
    }
    return total + (a.src === "fdk" ? 0 : 2) + (a.q ? 1 : 0);
  }
  function searchApis(query, filters, limit) {
    const terms = norm(query).split(/\s+/).filter(Boolean);
    const out = [];
    for (const a of apis) {
      if (filters.access && a.a !== filters.access) continue;
      if (filters.auth && a.u !== filters.auth) continue;
      if (filters.source === "curated" && a.src === "fdk") continue;
      if (filters.provider && a.p !== filters.provider) continue;
      if (filters.category && a.c !== filters.category) continue;
      const s = terms.length ? scoreApi(a, terms) : (a.src === "fdk" ? 1 : 2);
      if (s > 0) out.push([s, a]);
    }
    out.sort((x, y) => y[0] - x[0] || x[1].t.localeCompare(y[1].t, "nb"));
    return { total: out.length, hits: out.slice(0, limit).map((x) => x[1]) };
  }
  function searchOps(query, limit) {
    const terms = norm(query).split(/\s+/).filter((t) => t.length >= 2);
    if (!terms.length || !ops) return [];
    const out = [];
    for (const o of ops) {
      let s = 0;
      for (const t of terms) { if (!o._x.includes(t)) { s = 0; break; } s += o._x.indexOf(t) < o.p.length ? 3 : 1; }
      if (s) out.push([s, o]);
    }
    out.sort((x, y) => y[0] - x[0]);
    return out.slice(0, limit).map((x) => x[1]);
  }

  function badges(a) {
    const b = [`<span class="badge badge--${esc(a.a)}">${esc(ACCESS[a.a] || a.a)}</span>`];
    if (a.w) b.push(`<span class="badge badge--caveat">Forbehold</span>`);
    if (AUTH[a.u]) b.push(`<span class="badge badge--plain">${esc(AUTH[a.u])}</span>`);
    (a.f || []).slice(0, 3).forEach((f) => b.push(`<span class="badge badge--plain">${esc(f)}</span>`));
    if (a.o) b.push(`<span class="badge badge--plain">${a.o} endepunkt${a.o === 1 ? "" : "er"}</span>`);
    return b.join("");
  }
  function row(a) {
    return `<li class="row">
      <h3 class="row__title"><a href="${root}api/${esc(a.id)}/">${esc(a.t)}</a></h3>
      <p class="row__provider">${esc(a.p)}${a.src !== "fdk" ? " · håndplukket" : ""}</p>
      <p class="row__summary">${esc(a.s || "")}</p>
      <div class="row__meta">${badges(a)}</div>
    </li>`;
  }

  /* ---------- Index page search ---------- */
  const form = $("#search-form");
  if (form) {
    const input = $("#q");
    const results = $("#results");
    const list = $("#result-list");
    const status = $("#search-status");
    const rails = $("#rails");
    const more = $("#more");
    const opsBox = $("#op-results");
    const facets = $$("[data-facet]");
    const filters = { access: "", auth: "", source: "", provider: "", category: "" };
    let shown = 30, timer = null, lastQuery = "";

    const params = new URLSearchParams(location.search);
    input.value = params.get("q") || "";
    for (const k of Object.keys(filters)) if (params.get(k)) filters[k] = params.get(k);

    function syncUrl() {
      const p = new URLSearchParams();
      if (input.value.trim()) p.set("q", input.value.trim());
      for (const [k, v] of Object.entries(filters)) if (v) p.set(k, v);
      const qs = p.toString();
      history.replaceState(null, "", qs ? "?" + qs : location.pathname);
    }
    function active() { return Boolean(input.value.trim()) || Object.values(filters).some(Boolean); }
    async function render() {
      facets.forEach((btn) => btn.setAttribute("aria-pressed", String(filters[btn.dataset.facet] === btn.dataset.value)));
      if (!active()) {
        results.hidden = true; rails.hidden = false; status.textContent = ""; syncUrl();
        return;
      }
      status.textContent = apis ? "" : "Laster register …";
      await loadApis();
      const query = input.value.trim();
      if (query !== lastQuery) { shown = 30; lastQuery = query; }
      const { total, hits } = searchApis(query, filters, shown);
      results.hidden = false; rails.hidden = true;
      list.innerHTML = hits.length ? hits.map(row).join("") : "";
      $("#empty").hidden = hits.length > 0;
      more.hidden = total <= shown;
      status.textContent = total === 1 ? "1 API" : `${total.toLocaleString("nb-NO")} API-er`;
      syncUrl();
      if (query.length >= 3) {
        await loadOps();
        const opHits = searchOps(query, 12);
        opsBox.innerHTML = opHits.length ? `<h2>Endepunkter som matcher <span class="count">(${opHits.length})</span></h2><ul class="ops">` +
          opHits.map((o) => `<li><span class="method method--${esc(o.m.toLowerCase())}">${esc(o.m)}</span><code>${esc(o.p)}</code><span class="op__summary">${esc(o.s || "")} · <a href="${root}api/${esc(o.a)}/">${esc(o.n)}</a></span></li>`).join("") + "</ul>" : "";
      } else {
        opsBox.innerHTML = "";
      }
    }
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(render, 150); });
    form.addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(timer); render(); });
    facets.forEach((btn) => btn.addEventListener("click", () => {
      const k = btn.dataset.facet; filters[k] = filters[k] === btn.dataset.value ? "" : btn.dataset.value; render();
    }));
    more.addEventListener("click", () => { shown += 30; render(); });
    $$("[data-try]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); input.value = a.dataset.try; render(); input.focus(); }));
    $$("[data-source-link]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); filters.source = "curated"; render(); window.scrollTo({ top: 0 }); }));
    if (active()) render(); else loadApis();
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) { e.preventDefault(); input.focus(); }
    });
  }

  /* ---------- ⌘K palette ---------- */
  const dialog = $("#cmdk");
  if (dialog && typeof dialog.showModal === "function") {
    const field = $("#cmdk-input");
    const box = $("#cmdk-results");
    let items = [], selected = 0, timer = null;

    function open() { if (!dialog.open) { dialog.showModal(); field.value = ""; field.focus(); draw(); loadApis(); } }
    function close() { if (dialog.open) dialog.close(); }
    function draw() {
      const q = field.value.trim();
      if (!apis) { box.innerHTML = `<p class="cmdk__empty">Laster register …</p>`; return; }
      const { hits } = searchApis(q, {}, 8);
      const opHits = q.length >= 3 && ops ? searchOps(q, 5) : [];
      const providers = q.length >= 2 ? Array.from(new Set(apis.filter((a) => a._p.includes(norm(q))).map((a) => a.p))).slice(0, 3) : [];
      items = [];
      let html = "";
      if (hits.length) { html += `<p class="cmdk__group">API-er</p>`; hits.forEach((a) => { items.push(`${root}api/${a.id}/`); html += `<button class="cmdk__item" type="button" data-i="${items.length - 1}"><span>${esc(a.t)}</span><small>${esc(a.p)}</small></button>`; }); }
      if (opHits.length) { html += `<p class="cmdk__group">Endepunkter</p>`; opHits.forEach((o) => { items.push(`${root}api/${o.a}/`); html += `<button class="cmdk__item" type="button" data-i="${items.length - 1}"><code>${esc(o.m)} ${esc(o.p)}</code><small>${esc(o.n)}</small></button>`; }); }
      if (providers.length) { html += `<p class="cmdk__group">Leverandører</p>`; providers.forEach((p) => { const a = apis.find((x) => x.p === p); items.push(`${root}leverandor/${a.ps}/`); html += `<button class="cmdk__item" type="button" data-i="${items.length - 1}"><span>${esc(p)}</span><small>leverandør</small></button>`; }); }
      if (!items.length) html = `<p class="cmdk__empty">${q ? "Ingen treff. Prøv et annet ord, eller søk på engelsk." : "Skriv for å søke i " + apis.length.toLocaleString("nb-NO") + " API-er."}</p>`;
      box.innerHTML = html;
      selected = 0; mark();
    }
    function mark() { $$(".cmdk__item", box).forEach((el, i) => el.setAttribute("aria-selected", String(i === selected))); const el = $$(".cmdk__item", box)[selected]; if (el) el.scrollIntoView({ block: "nearest" }); }
    field.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { if (field.value.trim().length >= 3) loadOps().then(draw); draw(); }, 120); });
    field.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); selected = Math.min(selected + 1, items.length - 1); mark(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); selected = Math.max(selected - 1, 0); mark(); }
      else if (e.key === "Enter" && items[selected]) { e.preventDefault(); location.href = items[selected]; }
    });
    box.addEventListener("click", (e) => { const b = e.target.closest(".cmdk__item"); if (b) location.href = items[Number(b.dataset.i)]; });
    dialog.addEventListener("click", (e) => { if (e.target === dialog) close(); });
    $$("[data-cmdk-open]").forEach((b) => b.addEventListener("click", open));
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); dialog.open ? close() : open(); }
    });
    apisPromise && apisPromise.then(() => dialog.open && draw());
  }

  /* ---------- Copy buttons: the label is the feedback, no toast ---------- */
  $$("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const target = $(btn.dataset.copy);
      try { await navigator.clipboard.writeText(target.textContent.trim()); btn.dataset.state = "copied"; btn.textContent = "Kopiert"; }
      catch { btn.textContent = "Kunne ikke kopiere"; }
      setTimeout(() => { delete btn.dataset.state; btn.textContent = "Kopier"; }, 2500);
    });
  });
})();
