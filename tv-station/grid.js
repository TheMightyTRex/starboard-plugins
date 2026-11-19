// The schedule grid page: draws the week from the plug-in's answers and sends each change back. Every rule (what
// fits, which episode plays, copy and stripe) is in grid.py on the plug-in; this only draws and asks.
"use strict";
(function () {
  // Desktop browsers only (owner, 19 November 2026). A phone or tablet is found by the device, never by the width,
  // so a desktop zoomed to 400% (a narrow window) keeps the full page.
  const uaMobile = navigator.userAgentData && typeof navigator.userAgentData.mobile === "boolean"
    ? navigator.userAgentData.mobile
    : /Android|iPhone|iPad|iPod|Mobile|Tablet|Silk|Kindle|Opera Mini/i.test(navigator.userAgent) ||
      (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
  const touchOnly = window.matchMedia("(pointer: coarse) and (hover: none)").matches;
  if (uaMobile && touchOnly) {
    document.getElementById("app").hidden = true;
    document.getElementById("desktop-only").hidden = false;
    document.title = "Use a computer: Schedule grid";
    return;
  }
  // Light unless dark is chosen here (the page is on its own address, so it cannot read Starboard's choice).
  const theme = (() => { try { return localStorage.getItem("tvgrid-theme") === "dark" ? "dark" : "light"; } catch { return "light"; } })();
  document.documentElement.dataset.theme = theme;
  document.getElementById("theme").value = theme;
  document.getElementById("theme").addEventListener("change", (e) => {
    document.documentElement.dataset.theme = e.target.value === "dark" ? "dark" : "light";
    try { localStorage.setItem("tvgrid-theme", document.documentElement.dataset.theme); } catch { /* private window */ }
  });
  const base = location.pathname.replace(/\/grid\/?$/, "/grid");
  const $ = (id) => document.getElementById(id);
  const STEP = 15;
  const DAY = 1440;
  let st = null; // the last answer
  let picked = null; // a slot picked up to move, without dragging
  let addAt = null; // {day, start} when Add was opened from an empty time
  let returnTo = null; // where focus goes when a dialog closes
  let chosen = null; // the search result chosen in Add
  let current = null; // the slot whose actions are open
  const hm = (m) => `${String(Math.floor((m % DAY) / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  const params = new URLSearchParams(location.search);

  function say(words) { $("said").textContent = ""; setTimeout(() => { $("said").textContent = words || ""; }, 30); }
  function problem(words) { $("problem").textContent = words || ""; }

  async function get(path) {
    const r = await fetch(base + path, { headers: { Accept: "application/json" } });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || "The plug-in did not answer");
    return body;
  }
  async function op(body) {
    problem("");
    const r = await fetch(base + "/api/op", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ cid: st.cid, ...body }) });
    const got = await r.json().catch(() => ({}));
    if (!r.ok) { problem(got.error || "That did not work"); return null; }
    draw(got);
    say(got.said);
    return got;
  }

  function fillTimes(sel, value) {
    sel.textContent = "";
    for (let m = 0; m < DAY; m += STEP) sel.add(new Option(hm(m), String(m), false, m === value));
  }
  function fillDays(sel, value) {
    sel.textContent = "";
    st.days.forEach((d, i) => sel.add(new Option(d, String(i), false, i === value)));
  }

  function shownDays() {
    return $("view").value === "day" ? [Number($("day").value)] : [0, 1, 2, 3, 4, 5, 6];
  }

  function draw(got) {
    st = got;
    const ch = $("channel");
    if (!ch.options.length || ch.dataset.n !== String(st.channels.length)) {
      ch.textContent = "";
      st.channels.forEach((c) => ch.add(new Option(`${c.number} ${c.name}`, c.id)));
      ch.dataset.n = String(st.channels.length);
    }
    ch.value = st.cid;
    // No channels yet: the page says to add one, and nothing can be placed (0.2.0).
    ["add", "copy", "suggest"].forEach((id) => { $(id).disabled = !st.channels.length; });
    if (!$("day").options.length) fillDays($("day"), st.today);
    $("undo").disabled = !st.can_undo;
    $("draft").hidden = !st.draft;
    const notes = $("draft-notes");
    notes.textContent = "";
    (st.note || []).forEach((n) => { const li = document.createElement("li"); li.textContent = n; notes.append(li); });
    drawGrid();
    if (got.focus) focusSlot(got.focus);
  }

  function drawGrid() {
    const days = shownDays();
    const table = $("grid");
    table.textContent = "";
    const cap = table.createCaption();
    const name = (st.channels.find((c) => c.id === st.cid) || {}).name || "";
    cap.textContent = `${name}: ${days.length === 1 ? st.days[days[0]] : "the week"}, in 15 minute steps`;
    cap.className = "visually-hidden";
    const head = table.createTHead().insertRow();
    const corner = document.createElement("th");
    corner.textContent = "Time";
    corner.scope = "col";
    head.append(corner);
    days.forEach((d) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = st.days[d] + (d === st.today ? " (today)" : "");
      if (d === st.today) th.className = "today";
      head.append(th);
    });
    const body = table.createTBody();
    const covered = new Set();
    const starts = new Map();
    for (const s of st.slots) {
      starts.set(`${s.day}:${s.start}`, s);
      for (let m = s.start + STEP; m < Math.min(DAY, s.start + s.length); m += STEP) covered.add(`${s.day}:${m}`);
    }
    for (let m = 0; m < DAY; m += STEP) {
      const tr = body.insertRow();
      if (m % 60 === 0) tr.className = "hour";
      const th = document.createElement("th");
      th.scope = "row";
      th.textContent = hm(m);
      tr.append(th);
      for (const d of days) {
        const key = `${d}:${m}`;
        if (covered.has(key)) continue;
        const td = tr.insertCell();
        if (d === st.today) td.className = "today";
        const s = starts.get(key);
        if (s) {
          td.rowSpan = Math.max(1, Math.min((DAY - m) / STEP, s.length / STEP));
          td.append(slotButton(s));
        } else {
          td.append(cellButton(d, m));
        }
      }
    }
    roving();
  }

  function slotButton(s) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `slot ${s.kind}` + (picked && picked.id === s.id ? " picked" : "");
    b.dataset.slot = s.id;
    b.dataset.day = s.day;
    b.dataset.start = s.start;
    b.draggable = true;
    b.setAttribute("aria-label", `${st.days[s.day]} ${hm(s.start)} to ${hm(s.start + s.length)}: ${s.title}${s.detail ? ", " + s.detail : ""}. ` +
      `${s.kind === "series" ? "Series" : "Film"}, ${s.minutes} minutes. Open its actions`);
    const t = document.createElement("span"); t.className = "t"; t.textContent = `${hm(s.start)} ${s.title}`;
    const dd = document.createElement("span"); dd.className = "d"; dd.textContent = s.detail || (s.kind === "film" ? "Film" : "");
    b.append(t, dd);
    b.addEventListener("click", () => openSlot(s, b));
    b.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/plain", s.id); e.dataTransfer.effectAllowed = "move"; b.classList.add("dragging"); });
    b.addEventListener("dragend", () => b.classList.remove("dragging"));
    return b;
  }

  function cellButton(d, m) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "cell";
    b.dataset.day = d;
    b.dataset.start = m;
    b.textContent = "+";
    b.setAttribute("aria-label", `${st.days[d]} ${hm(m)}, empty. ` + (picked ? `Place ${picked.title} here` : "Add a programme here"));
    b.addEventListener("click", () => emptyChosen(d, m, b));
    b.addEventListener("dragover", (e) => { e.preventDefault(); b.classList.add("over"); });
    b.addEventListener("dragleave", () => b.classList.remove("over"));
    b.addEventListener("drop", async (e) => {
      e.preventDefault();
      b.classList.remove("over");
      const id = e.dataTransfer.getData("text/plain");
      if (id) await op({ op: "move", slot: id, day: d, start: m });
    });
    return b;
  }

  // One Tab stop for the whole grid; the arrow keys move between times and days (a roving tab index).
  function cells() { return [...$("grid").querySelectorAll("tbody button")]; }
  function roving() {
    const all = cells();
    all.forEach((b) => { b.tabIndex = -1; });
    const first = all.find((b) => b.classList.contains("slot")) || all.find((b) => Number(b.dataset.start) === 1200) || all[0];
    if (first) first.tabIndex = 0;
  }
  $("grid").addEventListener("focusin", (e) => {
    if (e.target.matches("tbody button")) { cells().forEach((b) => { b.tabIndex = -1; }); e.target.tabIndex = 0; }
  });
  $("grid").addEventListener("keydown", (e) => {
    const b = e.target.closest("tbody button");
    if (!b) return;
    const days = shownDays();
    let d = Number(b.dataset.day), m = Number(b.dataset.start);
    const here = st.slots.find((s) => s.id === b.dataset.slot);
    if (e.key === "ArrowDown") m = here ? here.start + here.length : m + STEP;
    else if (e.key === "ArrowUp") m -= STEP;
    else if (e.key === "ArrowRight") d = days[Math.min(days.length - 1, days.indexOf(d) + 1)];
    else if (e.key === "ArrowLeft") d = days[Math.max(0, days.indexOf(d) - 1)];
    else if (e.key === "Home") m = 0;
    else if (e.key === "End") m = DAY - STEP;
    else if (e.key === "PageDown") m += 60;
    else if (e.key === "PageUp") m -= 60;
    else if (e.key === "Escape" && picked) { unpick(); return; }
    else return;
    e.preventDefault();
    m = Math.max(0, Math.min(DAY - STEP, m));
    const target = buttonAt(d, m);
    if (target) target.focus();
  });
  function buttonAt(d, m) {
    const s = st.slots.find((x) => x.day === d && x.start <= m && m < x.start + x.length);
    if (s) return $("grid").querySelector(`button[data-slot="${s.id}"]`);
    return $("grid").querySelector(`button.cell[data-day="${d}"][data-start="${m}"]`);
  }
  function focusSlot(id) {
    const b = $("grid").querySelector(`button[data-slot="${id}"]`);
    if (b) { b.focus(); b.scrollIntoView({ block: "nearest" }); }
  }

  // Dialogs: focus goes to the heading, and back to what opened it on closing.
  function open(dlg, from) {
    returnTo = from || document.activeElement;
    dlg.showModal();
    const h = dlg.querySelector("h2");
    if (h) h.focus();
  }
  document.querySelectorAll("dialog").forEach((dlg) => dlg.addEventListener("close", () => {
    if (returnTo && document.contains(returnTo)) returnTo.focus();
  }));
  function closeTo(dlg, el) { returnTo = el; dlg.close(); }

  // A slot's actions: every drag has a button here (WCAG 2.2, 2.5.7).
  function openSlot(s, from) {
    if (picked) { problem("Choose an empty time to place the programme picked up, or put it back"); return; }
    current = s;
    $("slot-title").textContent = `${s.title}, ${st.days[s.day]} ${hm(s.start)}`;
    $("slot-detail").textContent = [s.detail, `${s.minutes} minutes`, s.kind === "series" ? (st.series[s.ref.slice(2)] || {}).start : "Film"]
      .filter(Boolean).join(". ");
    fillDays($("move-day"), s.day);
    fillTimes($("move-time"), s.start);
    $("series-acts").hidden = s.kind !== "series";
    open($("slot-dialog"), from);
  }
  $("slot-dialog").addEventListener("click", async (e) => {
    const act = e.target.dataset && e.target.dataset.act;
    if (!act || !current) return;
    const s = current;
    const dlg = $("slot-dialog");
    if (act === "earlier" || act === "later") {
      dlg.close();
      await op({ op: "nudge", slot: s.id, minutes: act === "earlier" ? -STEP : STEP });
    } else if (act === "move") {
      dlg.close();
      await op({ op: "move", slot: s.id, day: Number($("move-day").value), start: Number($("move-time").value) });
    } else if (act === "pick") {
      picked = s;
      $("picked-words").textContent = `${s.title} is picked up.`;
      $("picked").hidden = false;
      document.body.classList.add("picking");
      drawGrid();
      closeTo(dlg, buttonAt(s.day, s.start));
      say(`${s.title} picked up. Choose an empty time to place it, or press Escape to put it back`);
    } else if (act === "remove") {
      const near = s;
      dlg.close();
      const got = await op({ op: "remove", slot: s.id });
      if (got) { const b = buttonAt(near.day, near.start); if (b) b.focus(); }
    } else if (act === "stripe") {
      openStripe(s);
    } else if (act === "start") {
      openStart(s);
    }
  });
  function unpick() {
    const s = picked;
    picked = null;
    $("picked").hidden = true;
    document.body.classList.remove("picking");
    drawGrid();
    if (s) { focusSlot(s.id); say(`${s.title} put back where it was`); }
  }
  $("unpick").addEventListener("click", unpick);

  async function emptyChosen(d, m, from) {
    if (picked) {
      const s = picked;
      picked = null;
      $("picked").hidden = true;
      document.body.classList.remove("picking");
      const got = await op({ op: "move", slot: s.id, day: d, start: m });
      if (!got) { picked = s; $("picked").hidden = false; document.body.classList.add("picking"); }
      return;
    }
    openAdd(d, m, from);
  }

  // Add: search Jellyfin, choose a film or a series, and for a series where it starts.
  function openAdd(d, m, from) {
    addAt = { day: d, start: m };
    chosen = null;
    fillDays($("add-day"), d);
    fillTimes($("add-time"), m);
    $("results").textContent = "";
    $("results-set").hidden = true;
    $("add-start").hidden = true;
    open($("add-dialog"), from);
  }
  $("add").addEventListener("click", (e) => openAdd(shownDays()[0], 1200, e.currentTarget));
  async function search() {
    const q = $("search").value.trim();
    if (!q) { problem("Enter a name to search for"); $("search").focus(); return; }
    let got;
    try { got = await get(`/api/search?q=${encodeURIComponent(q)}`); } catch (err) { problem(err.message); return; }
    const box = $("results");
    box.textContent = "";
    $("results-set").hidden = false;
    if (!got.items.length) { box.textContent = `Nothing in Jellyfin matches ${q}`; say(box.textContent); return; }
    got.items.forEach((it, i) => {
      const div = document.createElement("div"); div.className = "choice";
      const r = document.createElement("input"); r.type = "radio"; r.name = "result"; r.id = `res-${i}`; r.value = it.id;
      r.addEventListener("change", () => { chosen = it; $("add-start").hidden = it.kind !== "series"; });
      const l = document.createElement("label"); l.htmlFor = r.id; l.textContent = `${it.name}, ${it.kind === "series" ? "series" : "film"}`;
      div.append(r, l);
      box.append(div);
    });
    say(`${got.items.length} found. Choose one, then Add to the grid`);
    box.querySelector("input").focus();
  }
  $("search-go").addEventListener("click", search);
  $("search").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); search(); } });
  $("add-go").addEventListener("click", async () => {
    if (!chosen) { problem("Search, then choose a film or series"); return; }
    const mode = document.querySelector("input[name=add-mode]:checked").value;
    const body = { op: "add", kind: chosen.kind, id: chosen.id, day: Number($("add-day").value), start: Number($("add-time").value), start_mode: mode,
      s: Number($("add-s").value), e: Number($("add-e").value) };
    const got = await op(body);
    if (got) { returnTo = null; $("add-dialog").close(); focusSlot(got.focus); }
  });

  // Copy a day.
  $("copy").addEventListener("click", (e) => {
    fillDays($("copy-from"), shownDays()[0]);
    drawCopyTo();
    open($("copy-dialog"), e.currentTarget);
  });
  function drawCopyTo() {
    const box = $("copy-to");
    box.textContent = "";
    st.days.forEach((d, i) => {
      if (String(i) === $("copy-from").value) return;
      const div = document.createElement("div"); div.className = "choice";
      const c = document.createElement("input"); c.type = "checkbox"; c.id = `copy-${i}`; c.value = String(i);
      const l = document.createElement("label"); l.htmlFor = c.id; l.textContent = d;
      div.append(c, l); box.append(div);
    });
  }
  $("copy-from").addEventListener("change", drawCopyTo);
  const tick = (want) => $("copy-to").querySelectorAll("input").forEach((c) => { c.checked = want(Number(c.value)); });
  $("copy-weekdays").addEventListener("click", () => tick((d) => d < 5));
  $("copy-all").addEventListener("click", () => tick(() => true));
  $("copy-go").addEventListener("click", async () => {
    const to = [...$("copy-to").querySelectorAll("input:checked")].map((c) => Number(c.value));
    if (!to.length) { problem("Choose at least one day to copy to"); return; }
    const got = await op({ op: "copy_day", from: Number($("copy-from").value), to });
    if (got) $("copy-dialog").close();
  });

  // Stripe: the same time on the chosen weekdays, a number of episodes a day, weekends on or off.
  function openStripe(s) {
    $("stripe-about").textContent = `${s.title} at ${hm(s.start)}, from ${st.days[s.day]}. Each slot plays the next episode.`;
    const box = $("stripe-days");
    box.textContent = "";
    st.days.slice(0, 5).forEach((d, i) => {
      const div = document.createElement("div"); div.className = "choice";
      const c = document.createElement("input"); c.type = "checkbox"; c.id = `stripe-${i}`; c.value = String(i); c.checked = true;
      const l = document.createElement("label"); l.htmlFor = c.id; l.textContent = d;
      div.append(c, l); box.append(div);
    });
    $("stripe-weekends").checked = s.day >= 5;
    $("slot-dialog").close();
    open($("stripe-dialog"), buttonAt(s.day, s.start));
  }
  $("stripe-go").addEventListener("click", async () => {
    const days = [...$("stripe-days").querySelectorAll("input:checked")].map((c) => Number(c.value));
    const got = await op({ op: "stripe", slot: current.id, weekdays: days, per_day: Number($("stripe-n").value), weekends: $("stripe-weekends").checked });
    if (got) { returnTo = null; $("stripe-dialog").close(); focusSlot(current.id); }
  });

  // Where a series starts.
  async function openStart(s) {
    const sid = s.ref.slice(2);
    $("start-now").textContent = `Now: ${(st.series[sid] || {}).start || "From the first episode"}.`;
    const sel = $("start-pick");
    sel.textContent = "";
    try {
      const got = await get(`/api/episodes?channel=${encodeURIComponent(st.cid)}&series=${encodeURIComponent(sid)}`);
      got.items.forEach((e) => sel.add(new Option(`Series ${e.s}, episode ${e.e}${e.name ? ": " + e.name : ""}`, `${e.s}:${e.e}`)));
    } catch (err) { problem(err.message); }
    $("slot-dialog").close();
    open($("start-dialog"), buttonAt(s.day, s.start));
  }
  $("start-pick").addEventListener("change", () => { $("start-episode").checked = true; });
  $("start-go").addEventListener("click", async () => {
    const mode = document.querySelector("input[name=start-mode]:checked").value;
    const [s, e] = $("start-pick").value.split(":").map(Number);
    const got = await op({ op: "set_start", series: current.ref.slice(2), mode, s, e });
    if (got) { returnTo = null; $("start-dialog").close(); focusSlot(current.id); }
  });

  // Suggest, save, discard, undo.
  // Suggest asks first what to make the week from (owner, 19 November 2026), starting on the channel's last choice.
  // The hours it fills (owner, 19 November 2026): weekdays and the weekend, each from and to, in half hours.
  const halfHours = [...Array(49).keys()].map((i) => `${String(Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`);
  const fillSelect = (sel, value, last) => {
    sel.replaceChildren(...halfHours.filter((t, i) => (last ? i > 0 : i < 48)).map((t) => new Option(t, t, false, t === value)));
  };
  const showHours = () => {
    const h = st.suggest_hours || {};
    for (const key of ["weekdays", "weekends"]) {
      const pair = h[key];
      $(`fill-${key}`).checked = Boolean(pair);
      fillSelect($(`${key}-from`), (pair || [key === "weekdays" ? "18:00" : "12:00"])[0], false);
      fillSelect($(`${key}-to`), (pair || [null, "23:00"])[1], true);
      for (const id of [`${key}-from`, `${key}-to`]) $(id).disabled = !pair;
    }
  };
  for (const key of ["weekdays", "weekends"]) {
    $(`fill-${key}`).addEventListener("change", (e) => { for (const id of [`${key}-from`, `${key}-to`]) $(id).disabled = !e.target.checked; });
  }
  $("suggest").addEventListener("click", (e) => {
    const want = document.getElementById(`from-${st.suggest_from || "history"}`) || $("from-history");
    want.checked = true;
    showHours();
    open($("suggest-dialog"), e.currentTarget);
  });
  $("suggest-go").addEventListener("click", async () => {
    const from = document.querySelector("input[name=suggest-from]:checked").value;
    const hours = {};
    for (const key of ["weekdays", "weekends"]) hours[key] = $(`fill-${key}`).checked ? [$(`${key}-from`).value, $(`${key}-to`).value] : null;
    if (!hours.weekdays && !hours.weekends) { say("Choose hours for weekdays, the weekend or both"); $("fill-weekdays").focus(); return; }
    for (const key of ["weekdays", "weekends"]) {
      if (hours[key] && hours[key][1] <= hours[key][0]) { say(`Choose an end time after the start time for ${key === "weekdays" ? "weekdays" : "the weekend"}`); $(`${key}-to`).focus(); return; }
    }
    const b = $("suggest-go");
    b.disabled = true;
    say("Suggesting a week. This takes a moment");
    const got = await op({ op: "suggest", from, hours });
    b.disabled = false;
    if (got) { returnTo = got.draft ? $("draft-title") : $("suggest"); $("suggest-dialog").close(); }
  });
  $("save-draft").addEventListener("click", async () => { const got = await op({ op: "save_draft" }); if (got) $("grid").querySelector("tbody button[tabindex='0']")?.focus(); });
  $("discard-draft").addEventListener("click", async () => { const got = await op({ op: "discard_draft" }); if (got) $("suggest").focus(); });
  $("undo").addEventListener("click", async () => { await op({ op: "undo" }); if ($("undo").disabled) $("add").focus(); });

  $("channel").addEventListener("change", async () => { try { draw(await get(`/api/state?channel=${encodeURIComponent($("channel").value)}`)); say("Showing " + $("channel").selectedOptions[0].text); } catch (err) { problem(err.message); } });
  $("view").addEventListener("change", () => { $("day-field").hidden = $("view").value !== "day"; drawGrid(); });
  $("day").addEventListener("change", drawGrid);

  get(`/api/state?channel=${encodeURIComponent(params.get("channel") || "")}`).then((got) => {
    draw(got);
    say(got.said || "");
    const b = buttonAt(shownDays()[0], 1200);
    if (b) b.scrollIntoView({ block: "center" });
  }).catch((err) => problem(err.message));
})();
