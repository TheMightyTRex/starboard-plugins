/* Choose a style for my channel (0.10.0): a wizard drawn with the design system's classes (docs/WIZARD.md). Import a kit is
   the one path so far, so the first question (which job) is left out until there is more than one. Nothing runs by itself:
   the page asks the plug-in for its state when a step needs it, and polls only while branding is being made. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const app = $("app"), said = $("said");
  const themeSel = $("theme");
  const paint = (v) => { document.documentElement.dataset.theme = v === "dark" ? "dark" : "light"; document.documentElement.classList.toggle("pref-contrast", v === "contrast"); };
  let theme = "";
  try { theme = localStorage.getItem("tvbreaks-theme") || ""; } catch { /* a private window */ }
  if (!theme) theme = matchMedia("(prefers-contrast: more)").matches ? "contrast" : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  themeSel.value = theme; paint(theme);
  themeSel.addEventListener("change", () => { paint(themeSel.value); try { localStorage.setItem("tvbreaks-theme", themeSel.value); } catch { /* private */ } });

  const S = { kit: null, channels: [], busy: false, playing: false, step: "path", error: "", note: "", to: "station", sameAs: "", poll: 0, mode: "", pv: 0 };
  const PATHS = [
    { id: "make", label: "Make a style here (recommended)", line: "Choose a style, enter your channel's name and two colours, and Starboard draws the title clips and cards on your own server. 4 steps." },
    { id: "import", label: "Import a kit", line: "Add the video and picture files you made in Canva, Figma or another tool, or a zip of them. 5 steps." }];

  const h = (tag, attrs, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === "on") for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
      else if (k === "text") el.textContent = v;
      else if (k in el && k !== "list" && k !== "style") el[k] = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    return el;
  };
  const say = (t) => { said.textContent = ""; setTimeout(() => { said.textContent = t; }, 30); };
  const size = (s) => (s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min` : s >= 60 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${Math.round(s * 10) / 10} s`);
  const notice = (tone, title, lines) => h("div", { class: "notice", "data-tone": tone, role: tone === "danger" ? "alert" : null }, h("span", { "aria-hidden": "true" }),
    h("div", { class: "notice__body" }, title ? h("p", { class: "notice__title" }, title) : null, lines.map((l) => h("p", {}, l))));

  async function api(path, opts) {
    const r = await fetch(path, opts);
    let body = {};
    try { body = await r.json(); } catch { /* not JSON */ }
    if (!r.ok) throw new Error(body.error || `The plug-in answered ${r.status}`);
    return body;
  }
  const op = (body) => api("style/api/op", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  function remember(id) { try { if (id) localStorage.setItem("tvstyle-kit", id); else localStorage.removeItem("tvstyle-kit"); } catch { /* private */ } }
  function take(o) { S.kit = o.kit; remember(o.kit && o.kit.id); S.channels = o.channels || S.channels; S.playing = !!o.playing; if (o.said) S.note = o.said; }

  // The steps for this job: a ready made pack in a zip leaves out What is each file.
  const mode = () => (S.kit && S.kit.mode) || S.mode || "import";
  function steps() {
    if (mode() === "make") return [["style", "Choose a style"], ["details", "Name and colours"], ["make", "Make the style"], ["use", "Use the style"]];
    const ready = S.kit && S.kit.ready === "pack";
    return ready ? [["add", "Add your files"], ["where", "Where did this pack come from?"], ["make", "Name it and make the branding"], ["use", "Use the branding"]]
      : [["add", "Add your files"], ["what", "What is each file?"], ["where", "Where did each file come from?"], ["make", "Name it and make the branding"], ["use", "Use the branding"]];
  }
  const at = () => steps().findIndex((s) => s[0] === S.step);

  function go(id) { S.step = id; S.error = ""; render(true); }
  function move(by) { const list = steps(); const i = Math.max(0, Math.min(list.length - 1, at() + by)); go(list[i][0]); }

  function frame(title, body, foot) {
    const list = steps(), i = at(), n = list.length;
    const words = `${mode() === "make" ? "Make a style here" : "Import a kit"} · step ${i + 1} of ${n} · ${title}`;
    return h("div", { class: "wizard-main" },
      h("div", { class: "meter wizard-progress" }, h("div", { class: "meter__label" }, h("span", {}, words), h("span", { class: "numeric" }, i + 1 === n ? "Last step" : `${n - i - 1} to go`)),
        h("div", { class: "progress", role: "progressbar", "aria-label": `Progress through ${mode() === "make" ? "Make a style here" : "Import a kit"}`, "aria-valuemin": "1", "aria-valuemax": String(n), "aria-valuenow": String(i + 1),
          "aria-valuetext": `Step ${i + 1} of ${n}: ${title}` }, h("span", { style: `width:${Math.round(((i + 1) / n) * 100)}%` }))),
      h("div", { class: "wizard" }, h("div", { class: "stack-4" }, h("h2", { tabindex: "-1", id: "step-h" }, title), S.error ? notice("danger", "That did not work", [S.error]) : null, body), foot));
  }
  function foot(next, nextLabel, canNext = true) {
    const first = at() === 0;
    return h("div", { class: "wizard__foot" },
      next ? h("button", { class: "btn btn--primary", type: "button", disabled: !canNext, on: { click: next } }, nextLabel || "Continue") : null,
      first && PATHS.length < 2 ? null : h("button", { class: "btn", type: "button", on: { click: () => (first ? go("path") : move(-1)) } }, "Back"));
  }

  // 1 Add
  function addStep() {
    const k = S.kit, files = (k && k.files) || [];
    const pick = h("input", { type: "file", id: "pick", multiple: true, class: "input", accept: ".mp4,.mov,.webm,.mkv,.png,.jpg,.jpeg,.mp3,.m4a,.wav,.flac,.ogg,.opus,.zip" });
    const list = files.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("caption", { class: "visually-hidden" }, "Files added"),
      h("thead", {}, h("tr", {}, ["File", "What it is", "Length", "Remove"].map((t) => h("th", { scope: "col" }, t)))),
      h("tbody", {}, files.map((f) => h("tr", {}, h("th", { scope: "row" }, f.name), h("td", {}, { video: "Video", still: "Picture", audio: "Sound" }[f.kind] + (f.w ? `, ${f.w} by ${f.h}` : "")),
        h("td", {}, f.kind === "still" ? "A picture" : size(f.dur)),
        h("td", {}, h("button", { class: "btn", type: "button", "aria-label": `Take out ${f.name}`, on: { click: () => doRemove(f.name) } }, "Take out"))))))) : null;
    const body = [
      h("p", { class: "muted" }, "Made something in Canva, Figma, Descript, Adobe Express or another tool? Save it as a video or a picture, or as a zip of them, and add it here. Starboard checks each file and turns them into your channel's branding."),
      h("div", { class: "field" }, h("label", { for: "pick" }, "Videos, pictures, sounds or a zip"),
        h("p", { class: "hint", id: "pick-hint" }, "MP4, MOV, WebM, MKV, PNG, JPG, MP3, M4A, WAV, FLAC, OGG or OPUS, up to 90 MB each, or a zip up to 60 MB. SVG pictures are not used: export a PNG."), pick),
      h("div", { class: "row" }, h("button", { class: "btn", type: "button", id: "add", disabled: S.busy, on: { click: () => doUpload(pick.files) } }, S.busy ? "Adding" : "Add the files")),
      S.playing ? notice("warning", "A channel is being watched", ["Adding files is fine, but making the branding waits until nobody is watching."]) : null,
      (k && k.skipped && k.skipped.length) ? notice("warning", "Left out of the zip", [h("ul", { class: "notes" }, k.skipped.slice(0, 8).map((t) => h("li", {}, t)))]) : null,
      list,
      h("p", { class: "help-links" }, h("a", { class: "help-link", href: "https://github.com/TheMightyTRex/starboard-plugins/blob/main/help/plugins/tv-station/styles.md", target: "_blank", rel: "noreferrer" },
        "Help with this step", h("span", { class: "visually-hidden" }, " (opens in a new tab)")))];
    return frame("Add your files", body, foot(() => move(1), "Continue", !!(k && (k.files.length || k.ready))));
  }
  async function doUpload(fl) {
    if (!fl || !fl.length) { S.error = "Choose at least one file first."; return render(true); }
    S.busy = true; S.error = ""; render();
    let kid = (S.kit && S.kit.id) || "";
    try {
      let n = 0;
      for (const f of fl) {
        say(`Adding ${f.name}, ${++n} of ${fl.length}`);
        const o = await api(`style/api/upload?kit=${encodeURIComponent(kid)}&name=${encodeURIComponent(f.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: f });
        take(o); kid = o.kit.id;
      }
      say(`${fl.length === 1 ? "One file" : fl.length + " files"} added`);
    } catch (e) { S.error = e.message; }
    S.busy = false; render(true);
  }
  async function doRemove(name) {
    try { take(await op({ op: "remove", kit: S.kit.id, name })); say(`${name} taken out`); } catch (e) { S.error = e.message; }
    render(true);
  }

  // 2 What
  function whatStep() {
    const k = S.kit;
    const rows = k.files.map((f, i) => {
      const sel = h("select", { class: "select", id: `role${i}`, "data-name": f.name }, f.roles.map((r) => h("option", { value: r, selected: r === f.role }, k.roles[r])));
      const tip = f.kind === "still" && (f.role === "ident" || f.role === "bumper") ? `A picture becomes a ${f.role === "ident" ? "5 second" : "2 second"} clip that fades in and out.` : "";
      return h("tr", {}, h("th", { scope: "row" }, h("label", { for: `role${i}` }, f.name)), h("td", {}, { video: "Video", still: "Picture", audio: "Sound" }[f.kind]), h("td", {}, sel, tip ? h("p", { class: "hint" }, tip) : null));
    });
    const body = [h("p", { class: "muted" }, "Say what each file is. Starboard made a first guess from its name and length. Choose Leave it out for a file you do not want."),
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("caption", { class: "visually-hidden" }, "What each file is"),
        h("thead", {}, h("tr", {}, ["File", "Kind", "What it is"].map((t) => h("th", { scope: "col" }, t)))), h("tbody", {}, rows))),
      h("p", { class: "hint" }, "A trailer is the short film about a programme that plays in a break. A Coming up next card shows what is on next. A logo is a picture with a clear background that sits in a corner of the picture.")];
    return frame("What is each file?", body, foot(async () => {
      const files = [...app.querySelectorAll("select[data-name]")].map((s) => ({ name: s.dataset.name, role: s.value }));
      try { take(await op({ op: "set", kit: k.id, files })); move(1); } catch (e) { S.error = e.message; render(true); }
    }, "Continue to where each file came from", k.files.some((f) => f.role !== "skip") || true));
  }

  // 3 Where
  function whereStep() {
    const k = S.kit, ready = k.ready === "pack";
    const items = ready ? [{ name: "The whole pack", origin: k.pack_origin, link: k.pack_link, pack: true }] : k.files.filter((f) => f.role !== "skip");
    const opts = (cur) => [h("option", { value: "" }, "Choose one"), ...Object.entries(k.origins).map(([v, t]) => h("option", { value: v, selected: v === cur }, t))];
    const rows = items.map((f, i) => {
      const warn = h("p", { class: "hint", id: `rem${i}`, hidden: f.origin !== "other" }, k.reminder);
      const sel = h("select", { class: "select", id: `org${i}`, "data-name": f.name, "aria-describedby": `rem${i}`, on: { change: (e) => { warn.hidden = e.target.value !== "other"; } } }, opts(f.origin));
      const link = h("input", { class: "input", id: `lnk${i}`, type: "url", value: f.link || "", placeholder: "https://", "data-link": f.name, "aria-describedby": `lh${i}` });
      return h("tr", {}, h("th", { scope: "row" }, f.name), h("td", {}, h("div", { class: "field" }, h("label", { for: `org${i}` }, "Where did this come from?"), sel, warn)),
        h("td", {}, h("div", { class: "field" }, h("label", { for: `lnk${i}` }, "A link to the page it came from (optional)"), link, h("p", { class: "hint", id: `lh${i}` }, "Written down only. Starboard never opens it."))));
    });
    const all = h("select", { class: "select", id: "same" }, opts(S.sameAs));
    const body = [h("p", { class: "muted" }, "Starboard writes your answers into a file called LICENCE.txt inside the branding, so the pack says where each file came from. Starboard cannot check them: you say."),
      items.length > 1 ? h("div", { class: "row" }, h("div", { class: "field" }, h("label", { for: "same" }, "Use one answer for every file"), all),
        h("button", { class: "btn", type: "button", on: { click: () => { S.sameAs = all.value; app.querySelectorAll("select[data-name]").forEach((s) => { s.value = all.value; s.dispatchEvent(new Event("change")); }); say("Answer copied to every file"); } } }, "Copy to every file")) : null,
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("caption", { class: "visually-hidden" }, "Where each file came from"),
        h("thead", {}, h("tr", {}, ["File", "Source", "Link"].map((t) => h("th", { scope: "col" }, t)))), h("tbody", {}, rows)))];
    return frame(ready ? "Where did this pack come from?" : "Where did each file come from?", body, foot(async () => {
      const ans = [...app.querySelectorAll("select[data-name]")];
      if (ans.some((s) => !s.value)) { S.error = "Choose where each file came from. Choose Something else if you are not sure."; return render(true); }
      const links = Object.fromEntries([...app.querySelectorAll("input[data-link]")].map((i) => [i.dataset.link, i.value]));
      try {
        take(await op(ready ? { op: "set", kit: k.id, pack_origin: ans[0].value, pack_link: links["The whole pack"] }
          : { op: "set", kit: k.id, files: ans.map((s) => ({ name: s.dataset.name, origin: s.value, link: links[s.dataset.name] })) }));
        move(1);
      } catch (e) { S.error = e.message; render(true); }
    }, "Continue to naming it"));
  }

  // 4 Make
  function makeStep() {
    const k = S.kit, job = k.job || {}, res = k.result;
    const name = h("input", { class: "input", id: "name", maxlength: 40, value: k.name || "", "aria-describedby": "name-h", disabled: !!job.running });
    const c1 = h("input", { type: "color", class: "input", id: "c1", value: k.colours[0], disabled: !!job.running }), c2 = h("input", { type: "color", class: "input", id: "c2", value: k.colours[1], disabled: !!job.running });
    const body = [
      h("div", { class: "field" }, h("label", { for: "name" }, "Channel name"), h("p", { class: "hint", id: "name-h" }, "Up to 40 characters. It names the branding, and is drawn as the logo if you did not add one."), name),
      h("div", { class: "colours" }, h("div", { class: "field" }, h("label", { for: "c1" }, "Main colour"), c1), h("div", { class: "field" }, h("label", { for: "c2" }, "Second colour"), c2)),
      h("div", { class: "row" }, h("button", { class: "btn btn--primary", type: "button", id: "make", disabled: !!job.running || S.playing, on: { click: doMake } }, res ? "Make it again" : "Make the branding")),
      S.playing ? notice("warning", "A channel is being watched", ["Making branding waits until nobody is watching. Try again then."]) : null,
    ];
    if (job.running) {
      body.push(h("div", { class: "meter" }, h("div", { class: "meter__label" }, h("span", { id: "job-words" }, `${job.words} (${job.step} of ${job.of})`)),
        h("div", { class: "progress progress--running", role: "progressbar", "aria-label": "Making the branding", "aria-valuemin": "0", "aria-valuemax": String(job.of), "aria-valuenow": String(job.step),
          "aria-valuetext": `${job.words}, ${job.step} of ${job.of}` }, h("span", { style: `width:${Math.round((job.step / Math.max(1, job.of)) * 100)}%` }))));
    }
    if (job.error) body.push(notice("danger", "The branding was not made", [job.error]));
    if (res) {
      if (res.ok) body.push(notice("success", "The branding passed every check", [res.summary + ". One FFmpeg thread at the lowest priority did the work, and nothing left your server."]));
      else body.push(notice("danger", "The branding did not pass", [h("ul", { class: "notes" }, res.problems.map((t) => h("li", {}, t)))]));
      const flashes = k.files.filter((f) => f.flash);
      if (flashes.length) body.push(notice("warning", "Fast flashing", [h("ul", { class: "notes" }, flashes.map((f) => h("li", {}, `${f.name}: ${f.flash}.`)))]));
      if (res.notes.length) body.push(notice("info", "Notes from the check", [h("ul", { class: "notes" }, res.notes.map((t) => h("li", {}, t)))]));
    }
    return frame("Name it and make the branding", body, foot(() => move(1), "Continue to using it", !!(res && res.ok) && !job.running));
  }
  async function doMake() {
    try {
      const name = $("name").value.trim();
      take(await op({ op: "set", kit: S.kit.id, name, colours: [$("c1").value, $("c2").value] }));
      take(await op({ op: "build", kit: S.kit.id }));
      say("Making the branding");
    } catch (e) { S.error = e.message; }
    render(true); poll();
  }
  function poll() {
    clearTimeout(S.poll);
    if (!(S.kit && S.kit.job && S.kit.job.running) || S.step !== "make") return;
    S.poll = setTimeout(async () => {
      try {
        const o = await api(`style/api/state?kit=${encodeURIComponent(S.kit.id)}`); const was = S.kit.job.running; take(o);
        if (was && !S.kit.job.running) { say(S.kit.result && S.kit.result.ok ? "The branding is made and passed every check" : "The branding is not made: the page says why"); render(true); }
        else { const w = $("job-words"); if (w) { w.textContent = `${S.kit.job.words} (${S.kit.job.step} of ${S.kit.job.of})`; } const bar = app.querySelector(".progress--running"); if (bar) { bar.setAttribute("aria-valuenow", S.kit.job.step); bar.firstChild.style.width = Math.round((S.kit.job.step / Math.max(1, S.kit.job.of)) * 100) + "%"; } }
      } catch (e) { S.error = e.message; render(); return; }
      poll();
    }, 1500);
  }

  // 0 Which job
  function pathStep() {
    const cur = S.mode || "make";
    const body = [h("p", { class: "muted" }, "Both ways make your channel's branding: short title clips, bumpers, the cards and the on-screen logo. Nothing is sent anywhere."),
      h("fieldset", { class: "option-cards" }, h("legend", { class: "visually-hidden" }, "How do you want to start?"),
        PATHS.map((p) => h("label", { class: "option-card" }, h("input", { type: "radio", name: "path", value: p.id, checked: p.id === cur, on: { change: () => { S.mode = p.id; } } }), h("strong", {}, p.label), h("small", {}, p.line))))];
    return h("div", { class: "wizard-main" }, h("div", { class: "wizard" }, h("div", { class: "stack-4" }, h("h2", { tabindex: "-1", id: "step-h" }, "How do you want to start?"), S.error ? notice("danger", "That did not work", [S.error]) : null, body),
      h("div", { class: "wizard__foot" }, h("button", { class: "btn btn--primary", type: "button", id: "path-go", on: { click: choosePath } }, "Continue"))));
  }
  async function choosePath() {
    S.mode = S.mode || "make";
    try {
      if (S.mode === "make") {
        const o = await op({ op: "new" }); take(o);
        take(await op({ op: "set", kit: o.kit.id, mode: "make" }));
        go("style");
      } else go("add");
    } catch (e) { S.error = e.message; render(true); }
  }

  // Make: 1 Choose a style
  function styleStep() {
    const k = S.kit;
    if (!k.style) k.style = k.styles[0].id;  // a good answer is already chosen
    const body = [h("p", { class: "muted" }, "Each style draws 4 short title clips, 2 bumpers, the background for the Coming up next card, the background for coming-up trailers and your logo, from your channel's name and two colours."),
      h("fieldset", { class: "option-cards" }, h("legend", { class: "visually-hidden" }, "Style"),
        k.styles.map((st, i) => h("label", { class: "option-card" }, h("input", { type: "radio", name: "style", value: st.id, checked: st.id === k.style, on: { change: () => { k.style = st.id; } } }), h("strong", {}, st.name + (i === 0 ? " (recommended)" : "")), h("small", {}, st.blurb))))];
    return frame("Choose a style", body, foot(async () => {
      if (!k.style) { S.error = "Choose a style."; return render(true); }
      try { take(await op({ op: "set", kit: k.id, style: k.style })); move(1); } catch (e) { S.error = e.message; render(true); }
    }, "Continue to name and colours"));
  }

  // Make: 2 Name and colours, with a still to look at first
  function detailsStep() {
    const k = S.kit;
    const name = h("input", { class: "input", id: "name", maxlength: 40, value: k.name || "", "aria-describedby": "name-h" });
    const c1 = h("input", { type: "color", class: "input", id: "c1", value: k.colours[0] }), c2 = h("input", { type: "color", class: "input", id: "c2", value: k.colours[1] });
    const still = h("input", { type: "checkbox", id: "still", checked: !!k.still });
    const pick = h("input", { type: "file", id: "logo", class: "input", accept: ".png" });
    const pics = h("div", { class: "pictures", id: "pics" }, [["title", "A short title clip"], ["card", "The Coming up next card"], ["bumper", "A bumper (half way through)"]].map(([p, t]) =>
      h("figure", {}, h("img", { id: `pv-${p}`, alt: `${t}, drawn from your name and colours`, width: 320, height: 180 }), h("figcaption", { class: "hint" }, t))));
    const refresh = () => { clearTimeout(S.pv); S.pv = setTimeout(drawPictures, 500); };
    [name, c1, c2].forEach((e) => e.addEventListener("input", refresh));
    const body = [
      h("div", { class: "field" }, h("label", { for: "name" }, "Channel name"), h("p", { class: "hint", id: "name-h" }, "Up to 40 characters."), name),
      h("div", { class: "colours" }, h("div", { class: "field" }, h("label", { for: "c1" }, "Main colour"), c1), h("div", { class: "field" }, h("label", { for: "c2" }, "Second colour"), c2)),
      h("p", { class: "hint" }, "The words are black or white. If they would be hard to read on a colour, Starboard makes that colour a little darker or lighter, so they reach 7 to 1."),
      h("div", { class: "field" }, h("label", { for: "logo" }, "Your logo (optional)"), h("p", { class: "hint", id: "logo-h" }, k.logo ? `Added: ${k.logo}. Choose another to change it.` : "A PNG with a clear background. With none, your channel's name is drawn as the logo."), pick,
        h("div", { class: "row" }, h("button", { class: "btn", type: "button", on: { click: () => addLogo(pick.files) } }, "Add the logo"), k.logo ? h("button", { class: "btn", type: "button", on: { click: dropLogo } }, "Take the logo out") : null)),
      h("div", { class: "field" }, h("label", { class: "check" }, still, " Make the clips with no movement"), h("p", { class: "hint" }, "For people who ask for it. The same words, held still.")),
      h("h3", {}, "How it will turn out"), h("p", { class: "hint", id: "pv-note", role: "status" }, "Drawn from your words and colours, not video. They change when you change a choice."), pics,
    ];
    setTimeout(drawPictures, 50);
    return frame("Name and colours", body, foot(async () => {
      try { take(await op({ op: "set", kit: k.id, name: name.value.trim(), colours: [c1.value, c2.value], still: still.checked })); if (!S.kit.name) throw new Error("Give the channel a name."); move(1); }
      catch (e) { S.error = e.message; render(true); }
    }, "Continue to making it"));
  }
  async function drawPictures() {
    const n = $("name"); if (!n || !$("pics")) return;
    const q = (p) => `style/api/preview?style=${encodeURIComponent(S.kit.style)}&name=${encodeURIComponent(n.value)}&c1=${encodeURIComponent($("c1").value)}&c2=${encodeURIComponent($("c2").value)}&part=${p}`;
    const mine = ++S.pvn || (S.pvn = 1);
    const note = $("pv-note");
    for (const p of ["title", "card", "bumper"]) {
      if (mine !== S.pvn || !$(`pv-${p}`)) return;
      try {
        const r = await fetch(q(p));
        if (!r.ok) { let m = "The picture could not be drawn."; try { m = (await r.json()).error || m; } catch { /* not JSON */ } if (note) note.textContent = m; return; }
        const url = URL.createObjectURL(await r.blob()); const img = $(`pv-${p}`); if (img) { const old = img.src; img.src = url; if (old.startsWith("blob:")) URL.revokeObjectURL(old); }
      } catch { if (note) note.textContent = "The picture could not be drawn."; return; }
    }
    if (note && mine === S.pvn) note.textContent = "Drawn from your words and colours, not video. The pictures are up to date.";
  }
  async function addLogo(fl) {
    if (!fl || !fl.length) { S.error = "Choose a PNG first."; return render(true); }
    try { const f = fl[0]; take(await api(`style/api/upload?kit=${encodeURIComponent(S.kit.id)}&name=${encodeURIComponent(f.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: f })); say("Logo added"); S.error = ""; }
    catch (e) { S.error = e.message; }
    render(true);
  }
  async function dropLogo() { try { take(await op({ op: "set", kit: S.kit.id, drop_logo: true })); say("Logo taken out"); } catch (e) { S.error = e.message; } render(true); }

  // Make: 3 Make the style
  function makeStyleStep() {
    const k = S.kit, job = k.job || {}, res = k.result;
    const st = k.styles.find((x) => x.id === k.style) || { name: "" };
    const body = [
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("caption", { class: "visually-hidden" }, "What will be made"), h("tbody", {},
        [["Style", st.name], ["Channel name", k.name], ["Colours", `${k.colours[0]} and ${k.colours[1]}`], ["Logo", k.logo || "Drawn from the name"], ["Movement", k.still ? "None: held still" : "Fades and slides"]]
          .map(([a, b]) => h("tr", {}, h("th", { scope: "row" }, a), h("td", {}, b)))))),
      h("p", { class: "muted" }, "It takes about a minute. It uses one processor thread at the lowest priority, makes one thing at a time, and stops at once if anyone starts to watch a channel."),
      h("div", { class: "row" }, h("button", { class: "btn btn--primary", type: "button", id: "make", disabled: !!job.running || S.playing, on: { click: doMakeStyle } }, res ? "Make it again" : "Make the style")),
      S.playing ? notice("warning", "A channel is being watched", ["Making the style waits until nobody is watching. Try again then."]) : null];
    if (job.running) body.push(h("div", { class: "meter" }, h("div", { class: "meter__label" }, h("span", { id: "job-words" }, `${job.words} (${job.step} of ${job.of})`)),
      h("div", { class: "progress progress--running", role: "progressbar", "aria-label": "Making the style", "aria-valuemin": "0", "aria-valuemax": String(job.of), "aria-valuenow": String(job.step),
        "aria-valuetext": `${job.words}, ${job.step} of ${job.of}` }, h("span", { style: `width:${Math.round((job.step / Math.max(1, job.of)) * 100)}%` }))));
    if (job.error) body.push(notice("danger", "The style was not made", [job.error]));
    if (res) {
      body.push(res.ok ? notice("success", "The style passed every check", [res.summary + ". Drawn on your own server, and nothing left it."]) : notice("danger", "The style did not pass", [h("ul", { class: "notes" }, res.problems.map((t) => h("li", {}, t)))]));
      if (res.notes.length) body.push(notice("info", "Notes from the check", [h("ul", { class: "notes" }, res.notes.map((t) => h("li", {}, t)))]));
    }
    return frame("Make the style", body, foot(() => move(1), "Continue to using it", !!(res && res.ok) && !job.running));
  }
  async function doMakeStyle() {
    try { take(await op({ op: "build", kit: S.kit.id })); say("Making the style"); } catch (e) { S.error = e.message; }
    render(true); poll();
  }

  // 5 Use
  function useStep() {
    const k = S.kit;
    const cards = [["station", "Every channel without a pack of its own (recommended)", "This replaces the station's pack. A channel with its own pack keeps it."],
      ...S.channels.map((c) => [c.id, c.name, "Only this channel uses it, as its own pack."])];
    const body = [h("p", { class: "muted" }, `${k.name} is ready. Choose where to use it.`),
      h("fieldset", { class: "option-cards" }, h("legend", { class: "visually-hidden" }, "Where to use the branding"),
        cards.map(([v, t, d]) => h("label", { class: "option-card" }, h("input", { type: "radio", name: "to", value: v, checked: v === S.to, on: { change: () => { S.to = v; } } }), h("strong", {}, t), h("small", {}, d))))];
    return frame(mode() === "make" ? "Use the style" : "Use the branding", body, h("div", { class: "wizard__foot" },
      h("button", { class: "btn btn--primary", type: "button", id: "use", on: { click: doUse } }, "Use this branding"), h("button", { class: "btn", type: "button", on: { click: () => move(-1) } }, "Back")));
  }
  async function doUse() {
    try { const o = await op({ op: "use", kit: S.kit.id, to: S.to }); S.kit = null; remember(""); S.note = o.said; S.step = "done"; say(o.said); }
    catch (e) { S.error = e.message; }
    render(true);
  }
  function doneStep() {
    return h("div", { class: "wizard" }, h("div", { class: "stack-4" }, h("h2", { tabindex: "-1", id: "step-h" }, "Done"), notice("success", null, [S.note]),
      h("p", {}, "Channels pick it up the next time a break plays. Promos made before are made again in the next quiet hour."),
      h("div", { class: "wizard__foot" }, h("button", { class: "btn btn--primary", type: "button", on: { click: () => { S.step = "path"; S.note = ""; S.mode = ""; render(true); } } }, "Start another"))));
  }

  function render(moveFocus) {
    app.replaceChildren();
    let view;
    if (S.step === "done") view = doneStep();
    else if (S.step === "path") view = pathStep();
    else if (S.step === "add" && !S.kit) view = addStep();
    else if (!S.kit && S.step !== "add") { S.step = "path"; view = pathStep(); }
    else view = ({ add: addStep, style: styleStep, details: detailsStep, what: whatStep, where: whereStep, make: mode() === "make" ? makeStyleStep : makeStep, use: useStep }[S.step] || pathStep)();
    app.append(view);
    if (moveFocus) { const hd = $("step-h"); if (hd) { hd.focus(); say(hd.textContent); } }
    poll();
  }

  (async () => {
    let last = "";
    try { last = localStorage.getItem("tvstyle-kit") || ""; } catch { /* private */ }
    try { take(await api("style/api/state?kit=" + encodeURIComponent(last))); if (S.kit) S.step = S.kit.job && S.kit.job.running ? "make" : S.kit.mode === "make" ? "style" : "add"; } catch (e) { S.error = e.message; }
    render(false);
  })();
})();
