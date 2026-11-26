/* The file lists' page (0.9.0, DASH-546). One page of rows is asked for at a time (50 at most), so a thousand files cost the
   same as fifty. Ticks are kept across pages and filters. Everything said is in the live region under the filters. */
(() => {
  const base = location.pathname.replace(/\/files\/?$/, "");
  const $ = (id) => document.getElementById(id);
  const said = $("said"), problem = $("problem"), table = $("table");
  let S = null;
  let page = 1;
  const ticked = new Map();   // key -> title, kept across pages
  let timer = 0;

  const themeSel = $("theme");
  const paint = (v) => { document.documentElement.dataset.theme = v === "dark" ? "dark" : "light"; document.documentElement.classList.toggle("pref-contrast", v === "contrast"); };
  let theme = "";
  try { theme = localStorage.getItem("tvbreaks-theme") || ""; } catch { /* a private window */ }
  if (!theme) theme = matchMedia("(prefers-contrast: more)").matches ? "contrast" : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  themeSel.value = theme; paint(theme);
  themeSel.addEventListener("change", () => { paint(themeSel.value); try { localStorage.setItem("tvbreaks-theme", themeSel.value); } catch { /* private */ } });

  const el = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === false || v == null) continue;
      if (k === "class") e.className = v; else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k != null) e.append(k);
    return e;
  };
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const say = (t) => { said.textContent = ""; setTimeout(() => { said.textContent = t; }, 30); };
  const fail = (t) => { problem.textContent = ""; setTimeout(() => { problem.textContent = t; }, 30); };
  const words = (s) => { const m = Math.floor(s / 60), r = Math.round(s % 60); return m ? `${m} min ${r} s` : `${r} s`; };
  const bytes = (n) => (n == null ? "Not known" : n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
  const date = (t) => (t ? new Date(t * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "Not known");
  const fill = (sel, map, blank) => { const keep = sel.value; sel.replaceChildren(...(blank ? [el("option", { value: "", text: blank })] : []), ...Object.entries(map).map(([v, n]) => el("option", { value: v, text: n }))); if ([...sel.options].some((o) => o.value === keep)) sel.value = keep; };

  const params = () => new URLSearchParams({ q: $("q").value, kind: $("kind").value, channel: $("channel").value, scope: $("scope").value,
    length: $("length").value, sound: $("sound").value, sort: $("sort").value, order: $("order").value, page });

  async function load(announce) {
    const r = await fetch(`${base}/files/api/state?${params()}`, { cache: "no-store" });
    S = await r.json();
    page = S.page;
    draw(announce);
  }

  function draw(announce) {
    if (!$("kind").options.length) {
      fill($("kind"), S.kinds, "All kinds"); fill($("scope"), S.scopes); fill($("length"), S.lengths); fill($("sound"), S.sounds); fill($("sort"), S.sorts);
      $("channel").replaceChildren(...S.channels.map((c) => el("option", { value: c.id, text: `${c.number}  ${c.name}` })));
      $("to").replaceChildren(el("option", { value: "station", text: "The station" }), ...S.channels.map((c) => el("option", { value: c.id, text: `${c.number}  ${c.name}` })));
      $("channel").value = S.cid; $("to").value = S.cid || "station";
    }
    $("count").textContent = S.total ? `${plural(S.total, "file", "files")}, showing ${S.first} to ${S.last}.` : "No files match. Change the search or the filters, or add files in Starboard.";
    const head = el("thead", {}, el("tr", {}, el("th", { scope: "col" }, el("input", { type: "checkbox", id: "all", "aria-label": "Tick every file on this page" })),
      ...["Name", "Kind", "Length", "Sound", "Size", "Added", "Kept in", "Used by"].map((h) => el("th", { scope: "col", text: h }))));
    const body = el("tbody", {}, S.rows.map((r) => el("tr", {},
      el("td", {}, el("input", { type: "checkbox", "data-key": r.key, "aria-label": `Tick ${r.title}`, ...(ticked.has(r.key) ? { checked: true } : {}) })),
      el("th", { scope: "row", text: r.title }), el("td", { text: r.kind }), el("td", { text: words(r.dur) }), el("td", { text: r.audio ? "With sound" : "No sound" }),
      el("td", { text: bytes(r.size) }), el("td", { text: date(r.added) }), el("td", { text: r.held_names.join(", ") }),
      el("td", { text: r.used_names.length ? r.used_names.join(", ") : "No channel" }))));
    table.replaceChildren(el("caption", { class: "sr", text: "Files, with the ones you can tick" }), head, body);
    const all = $("all");
    const sync = () => { all.checked = S.rows.length > 0 && S.rows.every((r) => ticked.has(r.key)); };
    sync();
    all.addEventListener("change", () => { S.rows.forEach((r) => { if (all.checked) ticked.set(r.key, r.title); else ticked.delete(r.key); }); draw(); say(all.checked ? `${plural(S.rows.length, "file", "files")} on this page ticked.` : "Ticks on this page cleared."); });
    body.addEventListener("change", (e) => { const k = e.target.dataset.key; if (!k) return; const r = S.rows.find((x) => x.key === k); if (e.target.checked) ticked.set(k, r.title); else ticked.delete(k); sync(); count(); });
    $("where").textContent = `Page ${S.page} of ${S.pages}`;
    $("prev").disabled = S.page <= 1; $("next").disabled = S.page >= S.pages;
    count();
    if (announce) say(`${S.total ? `${plural(S.total, "file", "files")}, page ${S.page} of ${S.pages}` : "No files match"}.`);
  }
  const count = () => { $("ticked").textContent = ticked.size ? `${plural(ticked.size, "file", "files")} ticked` : "No files ticked"; };

  async function change(op) {
    problem.textContent = "";
    if (!ticked.size) { fail("Tick at least one file first."); say("Tick at least one file first."); return; }
    const r = await fetch(`${base}/files/api/op`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ op, to: $("to").value, keys: [...ticked.keys()] }) });
    const b = await r.json();
    if (!r.ok) { fail(b.error || "That did not work. Try again."); say(b.error || "That did not work."); return; }
    ticked.clear();
    await load(false);
    say(b.said);
    $(op).focus();
  }

  const refresh = () => { page = 1; load(true).catch(() => fail("The plug-in did not answer. Check it is running, then reload.")); };
  ["kind", "channel", "scope", "length", "sound", "sort", "order"].forEach((id) => $(id).addEventListener("change", refresh));
  $("q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(refresh, 300); });
  $("filters").addEventListener("submit", (e) => { e.preventDefault(); refresh(); });
  $("prev").addEventListener("click", () => { page -= 1; load(true).then(() => $("results").scrollIntoView()); });
  $("next").addEventListener("click", () => { page += 1; load(true).then(() => $("results").scrollIntoView()); });
  $("add").addEventListener("click", () => change("add"));
  $("remove").addEventListener("click", () => change("remove"));
  $("clear").addEventListener("click", () => { ticked.clear(); draw(); say("Ticks cleared."); });
  load(false).catch(() => fail("The plug-in did not answer. Check it is running, then reload."));
})();
