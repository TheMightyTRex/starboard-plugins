// The break grids' help pictures (DASH-537), marked up with Starboard's annotate.js (red outline, curved arrow, step badge):
// tools/tv_break_screens/shots.sh. Example data only. Look at every picture.
import { chromium } from "playwright";
import fs from "fs";

const base = process.env.URL, out = process.env.OUT || "/work/out";
const annotate = fs.readFileSync(process.env.ANNOTATE, "utf8");
fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch();
const page = await (await b.newContext({ viewport: { width: 1100, height: 700 }, bypassCSP: true, deviceScaleFactor: 1 })).newPage();
const wait = (ms) => page.waitForTimeout(ms);
const api = (path, body) => page.evaluate(async ([u, p, d]) => (await fetch(`${u}/api/${p}`, d ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d) } : {})).json(), [base, path, body]);
await page.goto(base); await page.waitForSelector("section.grid");
const cid = (await api("state?channel=")).cid;
const op = (grid, o) => api("op", { cid, grid, op: o });
async function reset() { for (const g of ["between", "inside"]) await op(g, { op: "reset" }); await page.goto(base); await page.waitForSelector("section.grid"); await wait(200); }
async function shot(name, grid, marks, steps, clip, high) {
  await page.evaluate(() => scrollTo(0, 0));
  await page.evaluate(annotate);
  await page.evaluate(({ marks }) => { for (const m of marks) window.Annotate.mark(document.querySelector(m.sel), { step: m.step, side: m.side || "right" }); }, { marks });
  const sec = page.locator(`section.grid[data-grid=${grid}]`);
  const box = clip ? await page.locator(clip).first().boundingBox() : await sec.boundingBox();
  await page.screenshot({ path: `${out}/${name}.png`, clip: { x: Math.max(0, box.x - 70), y: Math.max(0, box.y - 20), width: Math.min(1100, box.width + 140), height: Math.min(high || box.height + 40, 760) }, fullPage: true });
  await page.evaluate(() => window.Annotate.clear());
}
const S = (g, rest) => `section.grid[data-grid=${g}] ${rest}`;
await page.setViewportSize({ width: 1100, height: 3400 });

// In between programmes 1: the mode and the columns
await reset();
await op("between", { op: "mode", mode: "sequence" }); await op("between", { op: "count", count: 3 });
await op("between", { op: "add", kind: "bumper", column: 1 }); await op("between", { op: "add", kind: "other_promo", column: 1, times: 2 }); await op("between", { op: "add", kind: "holding", column: 1 });
await op("between", { op: "add", kind: "ident", column: 2 }); await op("between", { op: "add", kind: "back_soon", column: 2 });
await page.goto(base); await page.waitForSelector("section.grid"); await wait(200);
await shot("between-modes", "between", [{ sel: S("between", "#mode-between"), step: 1, side: "top" }, { sel: S("between", "#count-between"), step: 2, side: "top" }], [1, 2], S("between", ""), 330);
// 2: the list of items and Add
await shot("between-items", "between", [{ sel: S("between", ".palette li:nth-child(2) .add-row"), step: 1 }], [1], S("between", ".layout"));
// 3: picked up with the keyboard
await page.locator(S("between", "[data-pal=ident]")).focus(); await page.keyboard.press("Space"); await page.keyboard.press("ArrowRight"); await wait(100);
await shot("between-pick-up", "between", [{ sel: S("between", ".drop-marker"), step: 1, side: "left" }], [1], S("between", ".layout"));
await page.keyboard.press("Escape");
// Breaks 1: day of week
await op("inside", { op: "mode", mode: "day" });
for (const [c, k] of [[0, "adverts"], [5, "promo"], [6, "promo"]]) await op("inside", { op: "add", kind: k, column: c, times: 2 });
await page.goto(base); await page.waitForSelector("section.grid"); await wait(200);
await shot("breaks-days", "inside", [{ sel: S("inside", "#mode-inside"), step: 1, side: "top" }], [1], S("inside", ""), 330);
// 2: times shown and move or remove
await page.locator(S("inside", "details[data-for=inside-0-1] summary")).click().catch(() => {});
await op("inside", { op: "mode", mode: "time" });
await page.goto(base); await page.waitForSelector("section.grid"); await wait(200);
await page.locator(S("inside", "details[data-for=inside-0-1] summary")).click(); await wait(100);
await shot("breaks-item-actions", "inside", [{ sel: S("inside", "#times-inside-0-1"), step: 1, side: "left" }, { sel: S("inside", "details[data-for=inside-0-1] .acts"), step: 2, side: "right" }], [1, 2], S("inside", ".col[data-col='0']"));
// 3: the time of day
await page.locator(S("inside", "details[data-for=inside-0-1] summary")).click(); await wait(100);
await shot("breaks-times-of-day", "inside", [{ sel: S("inside", ".col[data-col='0'] h3"), step: 1, side: "top" }, { sel: S("inside", ".col[data-col='1'] h3"), step: 2, side: "top" }], [1, 2], S("inside", ".cols-wrap"), 330);
await b.close();
