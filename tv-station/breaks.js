/* The break grids' page (0.8.0, DASH-537). Two grids for a channel, In between programmes and Breaks. Each has a mode, up to
   7 columns, and a list of items to put in them. There are three ways to do everything, and none is only a pointer's:
     1. Drag an item into a column (a pointer).
     2. Pick it up with the keyboard: Space or Enter on the item, Left and Right for the column, Up and Down for the place,
        Space or Enter to drop it, Escape to cancel. Every step is said in the live region under the channel.
     3. Plain buttons and selects: Add to a column, Move up, Move down, Move to a column, Remove, and how many times.
   Every change is sent at once and the page draws what the plug-in answers, so what is shown is what is kept. */
(() => {
  const base = location.pathname.replace(/\/breaks\/?$/, "");
  const said = document.getElementById("said");
  const problem = document.getElementById("problem");
  const root = document.getElementById("grids");
  const channel = document.getElementById("channel");
  let S = null;            // what the plug-in last said
  let held = null;         // an item picked up: {grid, from: {kind} | {col, index}, kind, name, col, pos}
  let dragging = null;     // an item being dragged by a pointer, the same shape
  let after = null;        // where focus goes once the page is drawn again: a function that returns an element
  const open = new Set();  // the items whose Move or remove is open, by grid, column and index

  // Colours: light, dark or high contrast, from the device unless chosen here.
  const themeSel = document.getElementById("theme");
  function paint(v) {
    document.documentElement.dataset.theme = v === "dark" ? "dark" : "light";
    document.documentElement.classList.toggle("pref-contrast", v === "contrast");
  }
  let theme = "";
  try { theme = localStorage.getItem("tvbreaks-theme") || ""; } catch { /* a private window */ }
  if (!theme) theme = matchMedia("(prefers-contrast: more)").matches ? "contrast" : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  themeSel.value = theme;
  paint(theme);
  themeSel.addEventListener("change", () => { paint(themeSel.value); try { localStorage.setItem("tvbreaks-theme", themeSel.value); } catch { /* private */ } });

  const el = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === false || v == null) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k != null) e.append(k);
    return e;
  };
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  let warned = "";         // a column's warning, said after the next change to its grid
  const say = (text) => { const t = text + (warned ? ` ${warned}` : ""); warned = ""; said.textContent = ""; setTimeout(() => { said.textContent = t; }, 30); };
  const fail = (text) => { problem.textContent = ""; setTimeout(() => { problem.textContent = text; }, 30); };
  const clearFail = () => { problem.textContent = ""; };
  const grid = (which) => S.grids.find((g) => g.which === which);
  const kindName = (k) => (S.kinds.find((x) => x.kind === k) || {}).name || k;
  const takes = (k) => !!(S.kinds.find((x) => x.kind === k) || {}).times;
  const colName = (g, c) => g.columns[c].name;

  async function load(cid) {
    const r = await fetch(`${base}/breaks/api/state?channel=${encodeURIComponent(cid || "")}`, { cache: "no-store" });
    S = await r.json();
    draw();
  }

  async function send(which, op, then) {
    clearFail();
    try {
      const r = await fetch(`${base}/breaks/api/op`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cid: S.cid, grid: which, op }) });
      const body = await r.json();
      if (!r.ok) { fail(body.error || "That did not work. Try again."); say(body.error || "That did not work."); after = null; return false; }
      S = body;
      draw();
      const g = grid(which);
      warned = g ? g.columns.map((c, i) => (c.warning ? `${c.name}: ${c.warning}` : "")).filter(Boolean).join(" ") : "";
      if (then) then(S);
      warned = "";
      return true;
    } catch {
      fail("The plug-in did not answer. Check it is running, then try again.");
      return false;
    }
  }

  // Where focus goes after the page is drawn: a selector to find again.
  const focusSel = (sel) => { after = () => root.querySelector(sel); };
  const itemKey = (which, c, i) => `${which}-${c}-${i}`;

  // ---- drawing -------------------------------------------------------------------------------------------------------
  function draw() {
    channel.replaceChildren(...S.channels.map((c) => el("option", { value: c.id, text: `${c.number}  ${c.name}` })));
    channel.value = S.cid;
    if (S.said && !S.channels.length) say(S.said);
    root.replaceChildren(...(S.channels.length ? S.grids.map(drawGrid) : [el("p", { class: "hint", text: S.said || "Add a channel first." })]));
    const params = new URLSearchParams(location.search);
    if (!draw.once) {
      draw.once = true;
      const want = params.get("grid");
      const h = want && document.getElementById(`h-${want}`);
      if (h) { h.setAttribute("tabindex", "-1"); h.scrollIntoView(); }
    }
    if (after) { const target = after(); after = null; if (target) target.focus(); }
  }

  function drawGrid(g) {
    const w = g.which;
    const n = g.columns.length;
    const modeHelp = (S.modes.find((m) => m.mode === g.mode) || {}).help || "";
    const sec = el("section", { class: "grid", "aria-labelledby": `h-${w}`, "data-grid": w });
    sec.append(...[el("h2", { id: `h-${w}`, text: g.name }),
      el("p", { class: "hint", text: w === "between" ? "What plays after a programme, before the next one starts." : "What plays in a break inside a programme, where the programme stops for adverts." }),
      g.saved ? null : el("p", { class: "banner", text: "This is the order the channel has always played. Nothing changes until you change the grid." })].filter(Boolean));
    const modeSel = el("select", { id: `mode-${w}`, "aria-describedby": `modehelp-${w}` },
      S.modes.map((m) => el("option", { value: m.mode, text: m.name, selected: m.mode === g.mode })));
    modeSel.value = g.mode;
    modeSel.addEventListener("change", () => {
      const m = S.modes.find((x) => x.mode === modeSel.value);
      focusSel(`#mode-${w}`);
      send(w, { op: "mode", mode: modeSel.value }, () => say(`${m.name}: ${plural(grid(w).columns.length, "column", "columns")}${grid(w).fixed_count ? `, ${grid(w).columns.map((c) => c.name).join(", ")}` : ""}.`));
    });
    const row = el("div", { class: "row" },
      el("div", { class: "field" }, el("label", { for: `mode-${w}`, text: "How a break picks its column" }), modeSel));
    if (!g.fixed_count) {
      const cnt = el("select", { id: `count-${w}` }, Array.from({ length: S.most_columns }, (_, i) => el("option", { value: i + 1, text: String(i + 1) })));
      cnt.value = String(g.count);
      cnt.addEventListener("change", () => { focusSel(`#count-${w}`); send(w, { op: "count", count: cnt.value }, () => say(`${plural(+cnt.value, "column", "columns")}.`)); });
      row.append(el("div", { class: "field" }, el("label", { for: `count-${w}`, text: "Number of columns" }), cnt));
    }
    if (g.saved) {
      row.append(el("button", { type: "button", onclick: () => {
        focusSel(`#mode-${w}`);
        send(w, { op: "reset" }, () => say("Back to the order the channel has always played."));
      }, text: "Use the standard order again" }));
    }
    sec.append(row, el("p", { class: "hint", id: `modehelp-${w}`, text: modeHelp + (g.unused_items ? ` ${plural(g.unused_items, "item", "items")} in columns this mode does not use ${g.unused_items === 1 ? "is" : "are"} kept, and come back if you change the mode.` : "") }),
      el("p", { class: "hint", id: `fit-help-${w}`, text: "Fit, for Adverts, adds as many whole adverts as the break has room for. It never cuts an advert or another item short. The Holding countdown, which comes last, makes up the rest of the time." }),
      el("p", { class: "hint", id: `how-${w}`, text: "With the keyboard: Tab to an item and press Space or Enter to pick it up. Left and Right choose the column, Up and Down the place in it. Space or Enter drops it, Escape cancels. Under each item, the buttons do the same." }));
    const layout = el("div", { class: "layout" }, drawPalette(g), drawColumns(g));
    sec.append(layout);
    return sec;
  }

  function colSelect(g, id, label) {
    const s = el("select", { id }, g.columns.map((c, i) => el("option", { value: i, text: c.name })));
    return [el("label", { for: id, text: label }), s];
  }

  function drawPalette(g) {
    const w = g.which;
    const box = el("div", { class: "palette", role: "group", "aria-labelledby": `pal-${w}` }, el("h3", { id: `pal-${w}`, text: "Items you can add" }));
    const list = el("ul", { "aria-label": `Items you can add to ${g.name}` });
    S.kinds.forEach((k) => {
      const ready = (S.available || {})[k.kind];
      const li = el("li", { class: "pal", draggable: "true", "data-kind": k.kind });
      const grab = el("button", { type: "button", class: "grab", "aria-pressed": "false", "aria-describedby": `how-${w}`, "data-pal": k.kind, text: k.name });
      const [lab, sel] = colSelect(g, `addto-${w}-${k.kind}`, "Add to");
      const add = el("button", { type: "button", class: "primary", "aria-label": `Add ${k.name} to the chosen column`, text: "Add", onclick: () => {
        const c = +sel.value;
        const pos = g.columns[c].items.length;
        focusSel(`#addto-${w}-${k.kind}`);
        send(w, { op: "add", kind: k.kind, column: c, position: pos }, (st) => {
          const gg = grid(w);
          say(`${k.name} added to ${colName(gg, c)}, position ${pos + 1} of ${gg.columns[c].items.length}.`);
        });
      } });
      li.append(el("div", { class: "pal-head" }, grab, el("span", { class: "avail", text: ready == null ? "" : ready ? `${ready} ready` : "none ready yet" })),
        el("p", { class: "about", text: k.about }),
        el("div", { class: "add-row", role: "group", "aria-label": `Add ${k.name}` }, lab, sel, add));
      wireDrag(li, { grid: w, kind: k.kind, name: k.name, from: { kind: k.kind } });
      wireKeys(grab, { grid: w, kind: k.kind, name: k.name, from: { kind: k.kind } });
      list.append(li);
    });
    box.append(list);
    return box;
  }

  function drawColumns(g) {
    const w = g.which;
    const wrap = el("div", { class: "columns" });
    g.columns.forEach((c, ci) => {
      const sec = el("div", { class: "col", role: "group", "aria-labelledby": `ch-${w}-${ci}`, "data-col": ci });
      const lenSel = el("select", { id: `len-${w}-${ci}`, "aria-describedby": `lenhelp-${w}-${ci}` },
        S.lengths.map((l) => el("option", { value: l.seconds, text: l.name })));
      lenSel.value = String(c.length);
      lenSel.addEventListener("change", () => {
        focusSel(`#len-${w}-${ci}`);
        send(w, { op: "length", column: ci, seconds: lenSel.value }, () => say(`${c.name}: break length ${S.lengths.find((l) => String(l.seconds) === lenSel.value).name}.`));
      });
      sec.append(el("h3", { id: `ch-${w}-${ci}`, tabindex: "-1", text: c.name }),
        el("p", { class: "count", text: c.items.length ? plural(c.items.length, "item", "items") : "Empty" }),
        el("div", { class: "field len" }, el("label", { for: `len-${w}-${ci}`, text: "Break length" }), lenSel),
        el("p", { class: "hint small", id: `lenhelp-${w}-${ci}`, text: w === "between" ? "Automatic is the gap the schedule leaves. The countdown or the cards make up the rest." : "Automatic is the longest break set for the channel." }),
        c.warning ? el("p", { class: "warning", "data-warning": `${w}-${ci}`, text: c.warning }) : null);
      const ol = el("ol", { "aria-label": `${g.name}, ${c.name}`, "data-list": `${w}-${ci}` });
      c.items.forEach((it, i) => ol.append(drawItem(g, ci, i, it)));
      wireColumn(ol, w, ci);
      sec.append(ol);
      if (!c.items.length) sec.append(el("p", { class: "empty", text: "Nothing here yet. Add an item from the list, or drag one in." }));
      wrap.append(sec);
    });
    return el("div", { class: "cols-wrap" }, wrap);
  }

  function drawItem(g, ci, i, it) {
    const w = g.which, n = g.columns[ci].items.length;
    const key = itemKey(w, ci, i);
    const li = el("li", { class: "item", draggable: "true", "data-kind": it.kind });
    const grab = el("button", { type: "button", class: "grab", "aria-pressed": "false", "aria-describedby": `how-${w}`, "data-key": key, text: it.name });
    const head = el("div", { class: "item-head" }, grab);
    if (it.counts) {
      const opts = Array.from({ length: 6 }, (_, k) => el("option", { value: k + 1, text: String(k + 1) }));
      if (it.kind === "adverts") opts.push(el("option", { value: "fit", text: "Fit" }));
      const sel = el("select", { id: `times-${key}`, ...(it.kind === "adverts" ? { "aria-describedby": `fit-help-${w}` } : {}) }, opts);
      sel.value = it.fit ? "fit" : String(it.times);
      sel.addEventListener("change", () => {
        focusSel(`#times-${key}`);
        send(w, { op: "times", column: ci, index: i, times: sel.value }, () => say(sel.value === "fit"
          ? `${it.name} is now set to Fit in ${colName(grid(w), ci)}: as many whole adverts as the break has room for.`
          : `${it.name} is now shown ${plural(+sel.value, "time", "times")} in ${colName(grid(w), ci)}.`));
      });
      head.append(el("span", { class: "times" }, el("label", { for: `times-${key}`, text: "Times shown" }), sel));
    } else {
      head.append(el("span", { class: "times fixed", text: "Shown once, takes the time that is left" }));
    }
    const more = el("details", { class: "more", ...(open.has(key) ? { open: true } : {}) },
      el("summary", { text: `Move or remove ${it.name}`, "aria-label": `Move or remove ${it.name}, position ${i + 1} of ${n}` }));
    more.addEventListener("toggle", () => { if (more.open) open.add(key); else open.delete(key); });
    const acts = el("div", { class: "acts" });
    const act = (label, disabled, fn, cls, name) => el("button", { type: "button", class: cls || "", disabled, onclick: fn, "data-act": name, text: label });
    // After a move, focus goes to the same button on the same item at its new place, and its actions stay open, so a
    // second press carries on; at the end of the column the other direction takes it.
    const stay = (newKey, name, other) => { open.delete(key); open.add(newKey);
      after = () => root.querySelector(`details[data-for="${newKey}"] [data-act="${name}"]:not([disabled])`) || root.querySelector(`details[data-for="${newKey}"] [data-act="${other}"]:not([disabled])`) || root.querySelector(`[data-key="${newKey}"]`); };
    acts.append(
      act("Move up", i === 0, () => {
        stay(itemKey(w, ci, i - 1), "up", "down");
        send(w, { op: "move", column: ci, index: i, to_column: ci, to_position: i - 1 }, () => say(`${it.name} moved up to position ${i} of ${n} in ${colName(grid(w), ci)}.`));
      }, "", "up"),
      act("Move down", i === n - 1, () => {
        stay(itemKey(w, ci, i + 1), "down", "up");
        send(w, { op: "move", column: ci, index: i, to_column: ci, to_position: i + 1 }, () => say(`${it.name} moved down to position ${i + 2} of ${n} in ${colName(grid(w), ci)}.`));
      }, "", "down"));
    const [lab, sel] = colSelect(g, `moveto-${key}`, "Move to");
    sel.value = String(ci);
    acts.append(el("div", { class: "move-to" }, lab, sel, act("Move", false, () => {
      const to = +sel.value;
      if (to === ci) { say(`${it.name} is already in ${colName(g, ci)}.`); return; }
      const pos = g.columns[to].items.length;
      open.delete(key);
      after = () => root.querySelector(`[data-key="${itemKey(w, to, pos)}"]`);
      send(w, { op: "move", column: ci, index: i, to_column: to, to_position: pos }, (st) => {
        const gg = st.grids.find((x) => x.which === w);
        say(`${it.name} moved to ${colName(gg, to)}, position ${pos + 1} of ${gg.columns[to].items.length}.`);
      });
    }, "", "moveto")));
    acts.append(act("Remove", false, () => {
      open.delete(key);
      const next = n > 1 ? itemKey(w, ci, Math.min(i, n - 2)) : null;
      after = () => (next ? root.querySelector(`[data-key="${next}"]`) : document.getElementById(`ch-${w}-${ci}`));
      send(w, { op: "remove", column: ci, index: i }, (st) => {
        const gg = st.grids.find((x) => x.which === w);
        say(`${it.name} removed from ${colName(gg, ci)}. ${gg.columns[ci].items.length ? plural(gg.columns[ci].items.length, "item", "items") + " left" : "The column is empty"}.`);
      });
    }, "danger", "remove"));
    more.setAttribute("data-for", key);
    more.append(acts);
    li.append(head, more);
    wireDrag(li, { grid: w, kind: it.kind, name: it.name, from: { col: ci, index: i } });
    wireKeys(grab, { grid: w, kind: it.kind, name: it.name, from: { col: ci, index: i } });
    return li;
  }

  // ---- pointer: drag and drop ------------------------------------------------------------------------------------------
  function slot(ol, y) {
    const items = [...ol.children].filter((x) => x.classList.contains("item") && !x.classList.contains("dragged"));
    let pos = items.length;
    for (let k = 0; k < items.length; k++) {
      const r = items[k].getBoundingClientRect();
      if (y < r.top + r.height / 2) { pos = k; break; }
    }
    return pos;
  }
  function marker(ol, pos) {
    unmark();
    const m = el("li", { class: "drop-marker", "aria-hidden": "true" });
    const items = [...ol.children].filter((x) => x.classList.contains("item") && !x.classList.contains("dragged"));
    if (pos >= items.length) ol.append(m); else ol.insertBefore(m, items[pos]);
    ol.closest(".col").classList.add("over");
  }
  function unmark() {
    root.querySelectorAll(".drop-marker").forEach((m) => m.remove());
    root.querySelectorAll(".col.over").forEach((c) => c.classList.remove("over"));
  }
  function wireDrag(li, what) {
    li.addEventListener("dragstart", (e) => {
      dragging = what;
      li.classList.add("dragged");
      e.dataTransfer.effectAllowed = "copyMove";
      e.dataTransfer.setData("text/plain", what.name);
    });
    li.addEventListener("dragend", () => { dragging = null; li.classList.remove("dragged"); unmark(); });
  }
  function wireColumn(ol, w, ci) {
    ol.addEventListener("dragover", (e) => {
      if (!dragging || dragging.grid !== w) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = dragging.from.kind ? "copy" : "move";
      marker(ol, slot(ol, e.clientY));
    });
    ol.addEventListener("dragleave", (e) => { if (!ol.contains(e.relatedTarget)) unmark(); });
    ol.addEventListener("drop", (e) => {
      if (!dragging || dragging.grid !== w) return;
      e.preventDefault();
      const d = dragging, pos = slot(ol, e.clientY);
      unmark();
      commit(d, ci, pos);
    });
  }

  // What dropping does, whichever way an item got there.
  function commit(d, c, pos) {
    const w = d.grid;
    const op = d.from.kind ? { op: "add", kind: d.kind, column: c, position: pos }
      : { op: "move", column: d.from.col, index: d.from.index, to_column: c, to_position: pos };
    after = () => root.querySelector(`[data-key="${itemKey(w, c, pos)}"]`);
    send(w, op, (st) => {
      const gg = st.grids.find((x) => x.which === w);
      say(`${d.name} ${d.from.kind ? "added to" : "moved to"} ${colName(gg, c)}, position ${pos + 1} of ${gg.columns[c].items.length}.`);
    });
  }

  // ---- keyboard: pick up, move, drop, cancel; and arrows to walk about ---------------------------------------------------
  function target() {
    const g = grid(held.grid);
    const items = g.columns[held.col].items.length - (held.from.col === held.col ? 1 : 0);
    held.pos = Math.max(0, Math.min(items, held.pos));
    const ol = root.querySelector(`[data-list="${held.grid}-${held.col}"]`);
    const kids = [...ol.children].filter((x) => x.classList.contains("item") && !(held.from.col === held.col && +x.querySelector(".grab").dataset.key.split("-").pop() === held.from.index));
    unmark();
    const m = el("li", { class: "drop-marker", "aria-hidden": "true" });
    if (held.pos >= kids.length) ol.append(m); else ol.insertBefore(m, kids[held.pos]);
    ol.closest(".col").classList.add("over");
    return { items: items + 1, col: held.col };
  }
  function whereWords() {
    const t = target();
    const g = grid(held.grid);
    return `${colName(g, t.col)}, position ${held.pos + 1} of ${t.items}`;
  }
  function pickUp(btn, what) {
    const g = grid(what.grid);
    held = { ...what, col: what.from.col != null ? what.from.col : 0, pos: what.from.col != null ? what.from.index : g.columns[0].items.length, button: btn };
    btn.setAttribute("aria-pressed", "true");
    btn.closest("li").classList.add("held");
    say(`${what.name} picked up. Left and Right choose the column, Up and Down the place. Space or Enter drops it, Escape cancels. Now over ${whereWords()}.`);
  }
  function release(msg) {
    if (!held) return;
    held.button.setAttribute("aria-pressed", "false");
    held.button.closest("li") && held.button.closest("li").classList.remove("held");
    unmark();
    held = null;
    if (msg) say(msg);
  }
  function wireKeys(btn, what) {
    btn.addEventListener("keydown", (e) => {
      if (held && held.button === btn) {
        const g = grid(held.grid);
        const k = e.key;
        if (k === "ArrowRight" || k === "ArrowLeft") {
          e.preventDefault();
          held.col = (held.col + (k === "ArrowRight" ? 1 : g.columns.length - 1)) % g.columns.length;
          held.pos = Math.min(held.pos, g.columns[held.col].items.length);
          say(`${whereWords()}.`);
        } else if (k === "ArrowDown" || k === "ArrowUp") {
          e.preventDefault();
          held.pos += k === "ArrowDown" ? 1 : -1;
          say(`${whereWords()}.`);
        } else if (k === " " || k === "Enter") {
          e.preventDefault();
          const d = held, c = held.col, pos = held.pos;
          release();
          commit(d, c, pos);
        } else if (k === "Escape") {
          e.preventDefault();
          const msg = held.from.kind ? `Cancelled. ${held.name} was not added.` : `Cancelled. ${held.name} stays where it was.`;
          release(msg);
        }
        return;
      }
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); pickUp(btn, what); return; }
      walk(btn, e);
    });
    btn.addEventListener("keyup", (e) => { if (e.key === " ") e.preventDefault(); });
    btn.addEventListener("blur", () => { if (held && held.button === btn) release(`Cancelled. ${held.name} ${held.from.kind ? "was not added" : "stays where it was"}.`); });
  }
  // Arrows with nothing picked up: from item to item in a column, and across to the next column.
  function walk(btn, e) {
    const keys = { ArrowDown: [0, 1], ArrowUp: [0, -1], ArrowRight: [1, 0], ArrowLeft: [-1, 0] };
    if (!keys[e.key] || !btn.dataset.key) return;
    const [dx, dy] = keys[e.key];
    const [w, c, i] = btn.dataset.key.split("-");
    const g = grid(w);
    let col = +c, idx = +i;
    e.preventDefault();
    if (dy) idx += dy;
    if (dx) { col = (col + dx + g.columns.length) % g.columns.length; idx = Math.min(idx, g.columns[col].items.length - 1); }
    let to = idx >= 0 && idx < g.columns[col].items.length ? root.querySelector(`[data-key="${itemKey(w, col, idx)}"]`) : null;
    if (!to && dx) to = document.getElementById(`ch-${w}-${col}`);
    if (to) to.focus();
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && held && document.activeElement !== held.button) release(`Cancelled. ${held.name} ${held.from.kind ? "was not added" : "stays where it was"}.`);
  });

  channel.addEventListener("change", () => { history.replaceState(null, "", `${location.pathname}?channel=${encodeURIComponent(channel.value)}`); load(channel.value); });
  load(new URLSearchParams(location.search).get("channel") || "").catch(() => fail("The plug-in did not answer. Check it is running, then reload."));
})();
