// Shows at set times: draws the rules the plug-in reads from a channel's grid, and sends each change back. The rules
// themselves are in grid.py (add_rule, remove_rule, rules); this only draws and asks, through the grid's own answers.
"use strict";
(function () {
  const theme = (() => { try { return localStorage.getItem("tvgrid-theme") === "dark" ? "dark" : "light"; } catch { return "light"; } })();
  document.documentElement.dataset.theme = theme;
  document.getElementById("theme").value = theme;
  document.getElementById("theme").addEventListener("change", (e) => {
    document.documentElement.dataset.theme = e.target.value === "dark" ? "dark" : "light";
    try { localStorage.setItem("tvgrid-theme", document.documentElement.dataset.theme); } catch { /* private window */ }
  });
  const base = location.pathname.replace(/\/times\/?$/, "");
  const $ = (id) => document.getElementById(id);
  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  let st = null;
  let chosen = null;
  const params = new URLSearchParams(location.search);
  const say = (w) => { $("said").textContent = ""; setTimeout(() => { $("said").textContent = w || ""; }, 30); };
  const problem = (w) => { $("problem").textContent = w || ""; };

  async function get(path) {
    const r = await fetch(`${base}/${path}`, { headers: { Accept: "application/json" } });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || "The plug-in did not answer");
    return body;
  }
  async function op(body) {
    problem("");
    const r = await fetch(`${base}/grid/api/op`, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ cid: st.cid, ...body }) });
    const got = await r.json().catch(() => ({}));
    if (!r.ok) { problem(got.error || "That did not work"); return null; }
    draw(got);
    say(got.said);
    return got;
  }

  function draw(got) {
    st = got;
    const sel = $("channel");
    if (!sel.options.length || sel.dataset.cid !== got.cid) {
      sel.textContent = "";
      for (const c of got.channels) sel.append(new Option(`${c.number} ${c.name}`, c.id, false, c.id === got.cid));
      sel.dataset.cid = got.cid;
    }
    sel.value = got.cid;
    $("gridlink").href = `${base}/grid?channel=${encodeURIComponent(got.cid)}`;
    const list = $("list");
    list.textContent = "";
    $("none").hidden = got.rules.length > 0;
    for (const r of got.rules) {
      const li = document.createElement("li");
      const words = document.createElement("span");
      words.textContent = r.words;
      const rm = document.createElement("button");
      rm.type = "button";
      rm.textContent = "Remove";
      const sr = document.createElement("span");
      sr.className = "visually-hidden";
      sr.textContent = ` ${r.words}`;
      rm.append(sr);
      rm.addEventListener("click", async () => {
        if (await op({ op: "rule_remove", rule: r.id })) $("rules").focus();
      });
      li.append(words, rm);
      list.append(li);
    }
  }

  // Times on the quarter hour.
  const at = $("at");
  for (let m = 0; m < 1440; m += 15) at.append(new Option(`${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`, String(m), false, m === 19 * 60));
  const days = $("days");
  DAYS.forEach((d, i) => {
    const l = document.createElement("label");
    l.className = "day";
    const c = document.createElement("input");
    c.type = "checkbox";
    c.name = "d";
    c.value = String(i);
    l.append(c, document.createTextNode(d));
    days.append(l);
  });
  document.querySelectorAll("button[data-days]").forEach((b) => b.addEventListener("click", () => {
    const want = new Set(b.dataset.days.split(","));
    days.querySelectorAll("input").forEach((c) => { c.checked = want.has(c.value); });
  }));

  async function find() {
    const q = $("q").value.trim();
    if (!q) { problem("Enter part of a name first."); return; }
    problem("");
    try {
      const got = await get(`grid/api/search?q=${encodeURIComponent(q)}`);
      const box = $("results");
      box.textContent = "";
      $("results-set").hidden = false;
      if (!got.items.length) { box.textContent = "Nothing matches. Try another part of the name."; return; }
      got.items.forEach((it, i) => {
        const l = document.createElement("label");
        l.className = "pick";
        const r = document.createElement("input");
        r.type = "radio";
        r.name = "pick";
        r.value = `${it.kind}:${it.id}`;
        r.id = `pick-${i}`;
        r.addEventListener("change", () => {
          chosen = it;
          $("chosen").hidden = false;
          $("chosen").textContent = `Chosen: ${it.name} (${it.kind === "film" ? "film" : "series"})`;
        });
        l.append(r, document.createTextNode(`${it.name} (${it.kind === "film" ? "film" : "series"})`));
        box.append(l);
      });
      box.querySelector("input").focus();
    } catch (e) { problem(e.message); }
  }
  $("find").addEventListener("click", find);
  $("q").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); find(); } });

  $("add").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!chosen) { problem("Find a show or film and choose one first."); $("q").focus(); return; }
    const picked = [...days.querySelectorAll("input:checked")].map((c) => Number(c.value));
    if (!picked.length) { problem("Choose at least one day."); days.querySelector("input").focus(); return; }
    const got = await op({ op: "rule_add", kind: chosen.kind, id: chosen.id, days: picked, start: Number(at.value), n: Number($("n").value) });
    if (got) { chosen = null; $("chosen").hidden = true; $("results-set").hidden = true; $("q").value = ""; $("q").focus(); }
  });
  $("channel").addEventListener("change", async () => {
    try { draw(await get(`grid/api/state?channel=${encodeURIComponent($("channel").value)}`)); say(""); } catch (e) { problem(e.message); }
  });
  get(`grid/api/state?channel=${encodeURIComponent(params.get("channel") || "")}`).then(draw).catch((e) => problem(e.message));
})();
