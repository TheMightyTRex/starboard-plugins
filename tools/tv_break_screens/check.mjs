// The break grids' page, checked (DASH-537): the standard accessibility test, run against tools/tv_break_screens/demo_server.py.
//   axe-core WCAG 2.2 AA in Light, Dark and High contrast, at desktop, phone and 175% text; reading order (headings and the
//   order of the grids); keyboard: pick up, move, drop and cancel with Space, Enter, the arrows and Escape; the same changes with
//   the buttons and selects; where focus is after each; what the live region says after each; a Tab walk with the visible focus
//   ring on every stop; target sizes of 44 pixels; no horizontal scroll at 320, 375 and 175% text; reduced motion; forced colours;
//   and a pointer drag. Nothing real is touched. Run by tools/tv_break_screens/run.sh.
import { chromium } from "playwright";
import fs from "fs";

const base = process.env.URL;                       // http://127.0.0.1:port/t/<token>/breaks
const out = process.env.OUT || "/work/out";
const AXE = fs.readFileSync(process.env.AXE, "utf8");
fs.mkdirSync(out, { recursive: true });
const findings = [], notes = [];
const add = (where, rule, detail) => findings.push({ where, rule, detail: String(detail).slice(0, 500) });
const note = (where, what) => notes.push({ where, what: String(what).slice(0, 600) });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, bypassCSP: true });
const page = await ctx.newPage();
page.on("pageerror", (e) => add("page", "script error", e.message));
page.on("console", (m) => { if (m.type() === "error" && !/status of 400/.test(m.text())) add("page", "console error", m.text()); });
const wait = (ms) => page.waitForTimeout(ms);
const api = async (path, body) => (await page.evaluate(async ([b, p, d]) => {
  const r = await fetch(`${b.replace(/\/breaks$/, "")}/breaks/api/${p}`, d ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d) } : {});
  return r.json();
}, [base, path, body]));
const saidNow = async () => { await wait(120); return page.evaluate(() => document.getElementById("said").textContent.trim()); };
const problemNow = async () => { await wait(120); return page.evaluate(() => document.getElementById("problem").textContent.trim()); };
const focusNow = () => page.evaluate(() => {
  const e = document.activeElement;
  if (!e || e === document.body) return "nothing";
  const name = (e.getAttribute("aria-label") || e.labels?.[0]?.textContent || e.textContent || "").trim().replace(/\s+/g, " ").slice(0, 60);
  return `${e.tagName.toLowerCase()}${e.dataset.key ? `[${e.dataset.key}]` : ""}${e.dataset.act ? `{${e.dataset.act}}` : ""} "${name}"`;
});
async function settle() { await wait(250); await page.waitForLoadState("networkidle").catch(() => {}); await wait(150); }
async function fresh(width = 1280, height = 900) {
  await page.setViewportSize({ width, height });
  if (page.url() === "about:blank") await page.goto(base);
  const s = await api("state?channel=");
  for (const g of ["between", "inside"]) await api("op", { cid: s.cid, grid: g, op: { op: "reset" } });
  await page.goto(base);
  await page.waitForSelector("section.grid");
  await settle();
  return s.cid;
}
async function axe(where) {
  for (const [mode, set] of [["light", () => { document.documentElement.dataset.theme = "light"; document.documentElement.classList.remove("pref-contrast"); }],
    ["dark", () => { document.documentElement.dataset.theme = "dark"; document.documentElement.classList.remove("pref-contrast"); }],
    ["high contrast", () => { document.documentElement.dataset.theme = "light"; document.documentElement.classList.add("pref-contrast"); }],
    ["high contrast dark", () => { document.documentElement.dataset.theme = "dark"; document.documentElement.classList.add("pref-contrast"); }]]) {
    await page.evaluate(set);
    await wait(100);
    await page.addScriptTag({ content: AXE });
    const r = await page.evaluate(async () => (await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] }, resultTypes: ["violations"] }))
      .violations.map((v) => `${v.id} (${v.impact}): ${v.help} at ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`));
    for (const v of r) add(`${where}, ${mode}`, "axe", v);
  }
  await page.evaluate(() => { document.documentElement.dataset.theme = "light"; document.documentElement.classList.remove("pref-contrast"); });
  note(where, "axe: Light, Dark, High contrast and High contrast dark checked (WCAG 2.2 AA and best practice)");
}
async function overflow(where) {
  const o = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
  if (o.sw > o.iw + 1) add(where, "reflow", `the page scrolls sideways: ${o.sw} wide in ${o.iw}`);
}
async function targets(where) {
  const small = await page.evaluate(() => [...document.querySelectorAll("button, select, summary, input, a")].filter((e) => e.getClientRects().length && !(e.classList.contains("skip") && e !== document.activeElement))
    .map((e) => { const r = e.getBoundingClientRect(); return { n: `${e.tagName.toLowerCase()} ${(e.getAttribute("aria-label") || e.textContent || "").trim().slice(0, 30)}`, w: r.width, h: r.height }; })
    .filter((x) => x.h < 43.5 || x.w < 43.5).map((x) => `${x.n} ${Math.round(x.w)}x${Math.round(x.h)}`));
  for (const s of small.slice(0, 8)) add(where, "target size", `under 44 pixels: ${s}`);
  note(where, `target sizes: ${small.length ? small.length + " under 44 pixels" : "every button, select and summary is at least 44 by 44"}`);
}
async function tabWalk(where, count) {
  await page.evaluate(() => { document.activeElement?.blur?.(); window.scrollTo(0, 0); });
  const seen = [];
  for (let i = 0; i < count; i++) {
    await page.keyboard.press("Tab");
    const f = await page.evaluate(() => {
      const e = document.activeElement;
      if (!e || e === document.body) return null;
      const r = e.getBoundingClientRect(), st = getComputedStyle(e);
      const ring = (st.outlineStyle !== "none" && parseFloat(st.outlineWidth) > 0) || st.boxShadow !== "none";
      return { name: (e.getAttribute("aria-label") || e.labels?.[0]?.textContent || e.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40),
        tag: e.tagName.toLowerCase(), visible: r.width > 0 && r.height > 0, ring, top: Math.round(r.top + scrollY) };
    });
    if (!f) { add(where, "Tab walk", `focus went to the page after ${i} presses`); break; }
    if (!f.visible) add(where, "Tab walk", `an unseen element took focus: ${f.tag} ${f.name}`);
    if (!f.ring) add(where, "Tab walk", `no visible focus on ${f.tag} "${f.name}"`);
    seen.push(f);
  }
  note(where, `Tab walk (${seen.length} stops): ${seen.slice(0, 18).map((f) => f.name || f.tag).join(" > ")} ...`);
  return seen;
}
const sec = (w) => page.locator(`section.grid[data-grid=${w}]`);
const expect = (where, rule, got, want) => { const ok = want instanceof RegExp ? want.test(got) : got === want; if (!ok) add(where, rule, `expected ${want}, got "${got}"`); else note(where, `${rule}: ${String(got).slice(0, 160)}`); return ok; };

// ---- 1. the page, structure, axe -------------------------------------------------------------------------------------
const cid = await fresh();
note("start", `title: ${await page.title()}`);
const heads = await page.evaluate(() => [...document.querySelectorAll("h1,h2,h3,h4")].filter((h) => h.getClientRects().length).map((h) => `${h.tagName}:${h.textContent.trim()}`));
note("Reading order", `headings: ${heads.slice(0, 14).join(" | ")}`);
let prev = 0;
for (const h of heads) { const l = Number(h[1]); if (l > prev + 1) add("Reading order", "heading levels", `h${prev} then ${h}`); prev = l; }
const order = await page.evaluate(() => [...document.querySelectorAll("main h1, main h2, main label, main button, main select, main summary")].filter((e) => e.getClientRects().length).slice(0, 40)
  .map((e) => ({ t: e.tagName, y: Math.round(e.getBoundingClientRect().top + scrollY) })));
const lists = await page.evaluate(() => ({ ul: document.querySelectorAll("ul").length, ol: document.querySelectorAll("ol").length, listitems: document.querySelectorAll("li").length,
  grids: document.querySelectorAll("[role=grid],[role=treegrid],table").length }));
note("Roles", `lists ${lists.ul} unordered and ${lists.ol} ordered, ${lists.listitems} list items, ${lists.grids} grid or table roles`);
if (lists.grids) add("Roles", "grid role", "a grid or table role is used without being fully implemented");
await axe("Standard order, desktop");
await targets("Standard order, desktop");
await overflow("Standard order, desktop");
await page.screenshot({ path: `${out}/1-standard-order.png`, fullPage: true });

// ---- 2. keyboard: pick up an item from the list, move it, drop it ------------------------------------------------------
await sec("between").locator("#count-between").selectOption("3");
await settle();
expect("Number of columns", "live region", await saidNow(), "3 columns.");
expect("Number of columns", "focus stays on the select", await focusNow(), /select.*Number of columns/);
const bumper = sec("between").locator("[data-pal=bumper]");
await bumper.focus();
await page.keyboard.press("Space");
let said = await saidNow();
expect("Pick up", "live region", said, /^Bumper picked up\..*Now over Column 1, position 6 of 6\.$/);
expect("Pick up", "pressed", await bumper.getAttribute("aria-pressed"), "true");
await page.keyboard.press("ArrowRight");
expect("Move right", "live region", await saidNow(), "Column 2, position 1 of 1.");
await page.keyboard.press("ArrowRight");
expect("Move right again", "live region", await saidNow(), "Column 3, position 1 of 1.");
await page.keyboard.press("ArrowLeft");
await page.keyboard.press("ArrowDown");
expect("Move down in an empty column", "live region", await saidNow(), "Column 2, position 1 of 1.");
const marker = await page.locator("section.grid[data-grid=between] .drop-marker").count();
if (marker !== 1) add("Pick up", "drop marker", `${marker} markers shown, expected 1`);
await page.screenshot({ path: `${out}/2-picked-up.png`, fullPage: false });
await page.keyboard.press("Space");
await settle();
expect("Drop", "live region", await saidNow(), "Bumper added to Column 2, position 1 of 1.");
expect("Drop", "focus on the dropped item", await focusNow(), /button\[between-1-0\] "Bumper"/);
let st = await api("state?channel=" + cid);
const between = st.grids.find((g) => g.which === "between");
expect("Drop", "kept: column 1 keeps the order it had", between.columns[0].items.map((i) => i.name).join(", "), "Bumper, Promo, Adverts, Holding countdown, Ident");
expect("Drop", "kept: column 2", between.columns[1].items.map((i) => i.name).join(", "), "Bumper");
expect("Drop", "kept: saved", String(between.saved), "true");

// ---- 3. keyboard: pick up a placed item, move it with arrows, cancel, then drop in another column ----------------------
const item = sec("between").locator("[data-key=between-0-1]");   // Promo, column 1 position 2
await item.focus();
await page.keyboard.press("Enter");
expect("Pick up a placed item", "live region", await saidNow(), /^Promo picked up\..*Now over Column 1, position 2 of 5\.$/);
await page.keyboard.press("ArrowUp");
expect("Up", "live region", await saidNow(), "Column 1, position 1 of 5.");
await page.keyboard.press("ArrowUp");
expect("Up at the top", "live region", await saidNow(), "Column 1, position 1 of 5.");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("Escape");
expect("Cancel", "live region", await saidNow(), "Cancelled. Promo stays where it was.");
expect("Cancel", "pressed again off", await item.getAttribute("aria-pressed"), "false");
expect("Cancel", "focus stays", await focusNow(), /button\[between-0-1\] "Promo"/);
st = await api("state?channel=" + cid);
expect("Cancel", "nothing changed", st.grids[0].columns[0].items.map((i) => i.name).join(", "), "Bumper, Promo, Adverts, Holding countdown, Ident");
await page.keyboard.press("Space");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("Space");
await settle();
expect("Move to column 3", "live region", await saidNow(), "Promo moved to Column 3, position 1 of 1.");
expect("Move to column 3", "focus", await focusNow(), /button\[between-2-0\] "Promo"/);
// leaving the item while it is held cancels it
await sec("between").locator("[data-key=between-0-0]").focus();
await page.keyboard.press("Space");
await page.keyboard.press("Tab");
expect("Tab away while held", "live region", await saidNow(), "Cancelled. Bumper stays where it was.");
// walking about with the arrows
await sec("between").locator("[data-key=between-0-0]").focus();
await page.keyboard.press("ArrowDown");
expect("Arrows walk", "down", await focusNow(), /\[between-0-1\]/);
await page.keyboard.press("ArrowRight");
expect("Arrows walk", "right goes to column 2", await focusNow(), /\[between-1-0\]/);

// ---- 4. the buttons and selects ---------------------------------------------------------------------------------------
await fresh();
const add1 = sec("between").locator("#addto-between-ident");
await add1.selectOption("0");
await sec("between").getByRole("button", { name: "Add Ident to the chosen column" }).click();
await settle();
expect("Add button", "live region", await saidNow(), "Ident added to Column 1, position 6 of 6.");
expect("Add button", "focus stays on the select", await focusNow(), /select.*Add to/);
await sec("between").locator("[data-key=between-0-1] ~ details summary, details[data-for=between-0-1] summary").first().click();
await sec("between").locator("details[data-for=between-0-1] [data-act=down]").click();
await settle();
expect("Move down button", "live region", await saidNow(), "Promo moved down to position 3 of 6 in Column 1.");
expect("Move down button", "focus on the same button at the new place", await focusNow(), /button\[\] "Move down"|\{down\}/);
const where = await page.evaluate(() => document.activeElement.closest("details")?.dataset.for);
expect("Move down button", "its item is now at position 3", where, "between-0-2");
await page.keyboard.press("Enter");
await settle();
expect("Move down again", "live region", await saidNow(), "Promo moved down to position 4 of 6 in Column 1.");
await sec("between").locator("details[data-for=between-0-3] [data-act=up]").click();
await settle();
expect("Move up button", "live region", await saidNow(), "Promo moved up to position 3 of 6 in Column 1.");
await sec("between").locator("#count-between").selectOption("3");
await settle();
await sec("between").locator("details[data-for=between-0-2] summary").click().catch(() => {});
const moveTo = sec("between").locator("#moveto-between-0-2");
if (!(await moveTo.isVisible())) await sec("between").locator("details[data-for=between-0-2] summary").click();
await moveTo.selectOption("2");
await sec("between").locator("details[data-for=between-0-2] [data-act=moveto]").click();
await settle();
expect("Move to select", "live region", await saidNow(), "Promo moved to Column 3, position 1 of 1.");
expect("Move to select", "focus", await focusNow(), /\[between-2-0\] "Promo"/);
const times = sec("between").locator("#times-between-2-0");
await times.selectOption("3");
await settle();
expect("Times shown", "live region", await saidNow(), "Promo is now shown 3 times in Column 3.");
expect("Times shown", "focus stays", await focusNow(), /select.*Times shown/);
await sec("between").locator("details[data-for=between-2-0] summary").click();
await sec("between").locator("details[data-for=between-2-0] [data-act=remove]").click();
await settle();
expect("Remove", "live region", await saidNow(), "Promo removed from Column 3. The column is empty.");
expect("Remove", "focus goes to the column heading", await focusNow(), /Column 3/);
await sec("between").locator("details[data-for=between-0-0] summary").click();
await sec("between").locator("details[data-for=between-0-0] [data-act=remove]").click();
await settle();
expect("Remove first", "focus goes to the next item", await focusNow(), /\[between-0-0\]/);

// a second holding slide in a column is refused, and the page says so where it can be heard
await sec("between").locator("#addto-between-back_soon").selectOption("0");
await sec("between").getByRole("button", { name: "Add Back soon to the chosen column" }).click();
await settle();
expect("A second holding slide", "alert", await problemNow(), /one holding slide at most/);
expect("A second holding slide", "live region", await saidNow(), /one holding slide at most/);
expect("A second holding slide", "alert role", await page.locator("#problem").getAttribute("role"), "alert");

// ---- 5. modes ------------------------------------------------------------------------------------------------------
const mode = sec("between").locator("#mode-between");
await mode.selectOption("day");
await settle();
expect("Day of week", "live region", await saidNow(), /^Day of week: 7 columns, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday\.$/);
expect("Day of week", "columns", String(await sec("between").locator(".col").count()), "7");
expect("Day of week", "no number of columns", String(await sec("between").locator("#count-between").count()), "0");
expect("Day of week", "focus stays on the mode", await focusNow(), /select.*How a break picks its column/);
await axe("Day of week");
await page.screenshot({ path: `${out}/3-day-of-week.png`, fullPage: true });
await mode.selectOption("time");
await settle();
expect("Morning, afternoon and evening", "live region", await saidNow(), "Morning, afternoon and evening: 3 columns, Morning, Afternoon, Evening.");
await mode.selectOption("sequence");
await settle();
expect("Sequence", "columns", String(await sec("between").locator(".col").count()), "3");
await sec("between").locator("#count-between").selectOption("7");
await settle();
expect("Seven columns", "count", String(await sec("between").locator(".col").count()), "7");
await page.screenshot({ path: `${out}/4-sequence-seven.png`, fullPage: true });
await sec("between").getByRole("button", { name: "Use the standard order again" }).click();
await settle();
expect("Use the standard order again", "live region", await saidNow(), "Back to the order the channel has always played.");
expect("Use the standard order again", "focus", await focusNow(), /select.*How a break picks its column/);

// ---- 6. the second grid, Breaks ---------------------------------------------------------------------------------------
await sec("inside").locator("#mode-inside").selectOption("time");
await settle();
const inside = sec("inside");
await inside.locator("[data-pal=coming_promo]").focus();
await page.keyboard.press("Space");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("Space");
await settle();
expect("Breaks grid", "live region", await saidNow(), "Coming soon promo added to Evening, position 1 of 1.");
await page.screenshot({ path: `${out}/5-breaks-grid.png`, fullPage: true });

// ---- 7. a pointer drag ----------------------------------------------------------------------------------------------
await fresh(1280, 3200);
const palette = sec("between").locator("li.pal[data-kind=other_promo]");
const col2 = sec("between").locator(".col ol").first();
await palette.dragTo(col2, { targetPosition: { x: 20, y: 10 } });
await settle();
const afterDrag = (await api("state?channel=" + cid)).grids[0].columns[0].items.map((i) => i.name).join(", ");
expect("Pointer drag", "dropped at the top of the column", afterDrag, "Other channel promo, Bumper, Promo, Adverts, Holding countdown, Ident");
expect("Pointer drag", "live region", await saidNow(), "Other channel promo added to Column 1, position 1 of 6.");

// ---- 8. phone, 320 wide, 175% text, zoom ----------------------------------------------------------------------------------
for (const [name, w, h] of [["Phone 375", 375, 800], ["Narrow 320", 320, 700]]) {
  await fresh(w, h);
  await overflow(name);
  await targets(name);
  await axe(name);
  await page.screenshot({ path: `${out}/6-${name.replace(/ /g, "-").toLowerCase()}.png`, fullPage: false });
}
await fresh(1280, 900);
await page.evaluate(() => document.documentElement.classList.add("pref-text-175"));
await wait(200);
await overflow("175% text, desktop");
await targets("175% text, desktop");
await axe("175% text, desktop");
await page.screenshot({ path: `${out}/7-text-175.png`, fullPage: false });
await page.setViewportSize({ width: 375, height: 800 });
await wait(200);
await overflow("175% text, phone");
await page.screenshot({ path: `${out}/8-text-175-phone.png`, fullPage: false });
await page.evaluate(() => document.documentElement.classList.remove("pref-text-175"));
// browser zoom 200% is a 640 wide window at 1280: the same reflow
await page.setViewportSize({ width: 640, height: 450 });
await overflow("200% zoom");

// ---- 9. Tab walk, reduced motion, forced colours ----------------------------------------------------------------------
await fresh(1280, 900);
const walk = await tabWalk("Tab walk", 60);
if (walk.length < 40) add("Tab walk", "reach", `only ${walk.length} stops in 60 presses`);
await page.emulateMedia({ reducedMotion: "reduce" });
const motion = await page.evaluate(() => [...document.querySelectorAll("button, .col")].map((e) => getComputedStyle(e).transitionDuration).filter((d) => d !== "0s").length);
expect("Reduced motion", "elements that still transition", String(motion), "0");
await page.emulateMedia({ reducedMotion: "no-preference", forcedColors: "active" });
await wait(200);
const ring = await page.evaluate(() => { document.querySelector("[data-pal=bumper]").focus(); const st = getComputedStyle(document.activeElement); return `${st.outlineStyle} ${st.outlineWidth}`; });
expect("Forced colours", "focus outline", ring, /solid|auto/);
await page.screenshot({ path: `${out}/9-forced-colours.png`, fullPage: false });
await page.emulateMedia({ forcedColors: "none" });

fs.writeFileSync(`${out}/check.json`, JSON.stringify({ findings, notes }, null, 1));
console.log(`${findings.length} findings, ${notes.length} notes`);
for (const f of findings) console.log(`FINDING ${f.where} | ${f.rule} | ${f.detail}`);
await browser.close();
process.exit(findings.length ? 1 : 0);
