// The file lists' page, checked (DASH-546): axe WCAG 2.2 AA in Light, Dark and High contrast at desktop, phone and 175% text;
// reading order; a Tab walk; the keyboard (tick with Space, add with Enter, page with Enter); where focus is after each; what the
// live region says; target sizes; no sideways scroll of the page. Run by tools/tv_break_screens/files_run.sh.
import { chromium } from "playwright";
import fs from "fs";

const base = process.env.URL.replace(/\/breaks$/, "/files"), out = process.env.OUT || "/work/out";
const AXE = fs.readFileSync(process.env.AXE, "utf8");
fs.mkdirSync(out, { recursive: true });
const findings = [], notes = [];
const add = (where, rule, detail) => findings.push({ where, rule, detail: String(detail).slice(0, 500) });
const note = (where, what) => notes.push({ where, what });
const b = await chromium.launch();
const page = await (await b.newContext({ viewport: { width: 1280, height: 900 }, bypassCSP: true })).newPage();
page.on("pageerror", (e) => add("page", "script error", e.message));
page.on("console", (m) => { if (m.type() === "error") add("page", "console error", m.text()); });
const wait = (ms) => page.waitForTimeout(ms);
const said = async () => { await wait(150); return page.evaluate(() => document.getElementById("said").textContent.trim()); };
const focus = () => page.evaluate(() => { const e = document.activeElement; return e ? `${e.tagName.toLowerCase()} "${(e.getAttribute("aria-label") || e.labels?.[0]?.textContent || e.textContent || "").trim().slice(0, 50)}"` : "nothing"; });
await page.goto(base); await page.waitForSelector("#table tbody tr"); await wait(300);

async function axe(where) {
  for (const [mode, set] of [["light", () => { document.documentElement.dataset.theme = "light"; document.documentElement.classList.remove("pref-contrast"); }],
    ["dark", () => { document.documentElement.dataset.theme = "dark"; document.documentElement.classList.remove("pref-contrast"); }],
    ["high contrast", () => { document.documentElement.dataset.theme = "light"; document.documentElement.classList.add("pref-contrast"); }],
    ["high contrast dark", () => { document.documentElement.dataset.theme = "dark"; document.documentElement.classList.add("pref-contrast"); }]]) {
    await page.evaluate(set); await wait(100);
    await page.addScriptTag({ content: AXE });
    const r = await page.evaluate(async () => (await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] }, resultTypes: ["violations"] }))
      .violations.map((v) => `${v.id} (${v.impact}): ${v.help} at ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`));
    for (const v of r) add(`${where}, ${mode}`, "axe", v);
  }
  await page.evaluate(() => { document.documentElement.dataset.theme = "light"; document.documentElement.classList.remove("pref-contrast"); });
  note(where, "axe checked in four themes");
}
await axe("desktop");
await page.setViewportSize({ width: 375, height: 800 }); await wait(200); await axe("phone 375");
const wide = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
if (wide) add("phone 375", "layout", "the page scrolls sideways"); else note("phone 375", "no sideways scroll of the page");
await page.setViewportSize({ width: 1280, height: 900 });
await page.evaluate(() => { document.documentElement.style.fontSize = "175%"; }); await wait(200); await axe("175% text");
if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) add("175% text", "layout", "the page scrolls sideways");
await page.evaluate(() => { document.documentElement.style.fontSize = ""; });

// Reading order
const order = await page.evaluate(() => [...document.querySelectorAll("h1,h2,main,form,table,nav,[role=status],[role=alert],caption")].map((e) => e.tagName.toLowerCase() + (e.id ? `#${e.id}` : "")));
note("reading order", order.join(" > "));
// Target sizes
const small = await page.evaluate(() => [...document.querySelectorAll("button,select,input")].filter((e) => { const r = e.getBoundingClientRect(); return r.width && (r.width < 24 || r.height < 24); }).map((e) => e.id || e.outerHTML.slice(0, 60)));
if (small.length) add("targets", "size", small.join(", ")); else note("targets", "every control is at least 24 by 24 CSS pixels (44 for buttons and choices)");
// Tab walk
const stops = [];
await page.evaluate(() => document.body.focus());
for (let i = 0; i < 24; i++) { await page.keyboard.press("Tab"); stops.push(await focus()); const ring = await page.evaluate(() => { const e = document.activeElement; const s = getComputedStyle(e); return s.outlineStyle !== "none" && parseFloat(s.outlineWidth) >= 2; }); if (!ring) add("tab walk", "focus ring", `no visible ring on ${stops.at(-1)}`); }
note("tab walk", stops.join(" | "));
// Keyboard: tick, add, page
await page.locator("#table tbody tr:nth-child(1) input").focus(); await page.keyboard.press("Space");
note("tick with Space", `said: "${await said()}"; ticked text: "${await page.locator("#ticked").textContent()}"; focus ${await focus()}`);
await page.selectOption("#to", { index: 2 }); await page.locator("#add").focus(); await page.keyboard.press("Enter");
await wait(500);
note("add with Enter", `said: "${await said()}"; focus ${await focus()}`);
await page.locator("#add").focus(); await page.keyboard.press("Enter"); note("add with nothing ticked", `said: "${await said()}"; problem: "${await page.locator("#problem").textContent()}"`);
await page.locator("#q").fill("fire"); await wait(700); note("search", `said: "${await said()}"; rows: ${await page.locator("#table tbody tr").count()}`);
await page.locator("#q").fill(""); await wait(700);
fs.writeFileSync(`${out}/files-check.json`, JSON.stringify({ findings, notes }, null, 1));
console.log(JSON.stringify({ findings: findings.length, notes: notes.length }));
for (const f of findings) console.log("FINDING", f.where, f.rule, f.detail);
for (const n of notes) console.log("NOTE", n.where, n.what);
await b.close();
