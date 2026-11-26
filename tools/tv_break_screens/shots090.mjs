// The 0.9.0 help pictures (DASH-549, DASH-546), marked up with Starboard's annotate.js: tools/tv_break_screens/shots.sh 090 [starboard checkout]
// Example data only. Look at every picture.
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
const S = (g, rest) => `section.grid[data-grid=${g}] ${rest}`;
await page.setViewportSize({ width: 1100, height: 3400 });
async function snap(name, marks, sel, high) {
  await page.evaluate(() => scrollTo(0, 0));
  await page.evaluate(annotate);
  await page.evaluate(({ marks }) => { for (const m of marks) window.Annotate.mark(document.querySelector(m.sel), { step: m.step, side: m.side || "right" }); }, { marks });
  const box = await page.locator(sel).first().boundingBox();
  await page.screenshot({ path: `${out}/${name}.png`, clip: { x: Math.max(0, box.x - 40), y: Math.max(0, box.y - 20), width: Math.min(1100, box.width + 80), height: Math.min(high || box.height + 40, 760) }, fullPage: true });
  await page.evaluate(() => window.Annotate.clear());
}
// Fit and the break length on the In between programmes grid
await op("between", { op: "reset" });
await op("between", { op: "mode", mode: "sequence" }); await op("between", { op: "count", count: 2 });
await op("between", { op: "clear", column: 0 }); await op("between", { op: "clear", column: 1 });
await op("between", { op: "add", kind: "bumper", column: 0 }); await op("between", { op: "add", kind: "adverts", column: 0, times: "fit" });
await op("between", { op: "add", kind: "holding", column: 0 }); await op("between", { op: "add", kind: "ident", column: 0 });
await op("between", { op: "length", column: 0, seconds: 180 });
await op("between", { op: "add", kind: "promo", column: 1, times: 6 }); await op("between", { op: "add", kind: "psa", column: 1, times: 2 }); await op("between", { op: "add", kind: "ident", column: 1 }); await op("between", { op: "length", column: 1, seconds: 120 });
await page.goto(base); await page.waitForSelector("section.grid"); await wait(300);
await snap("grid-fit-times", [{ sel: S("between", "#times-between-0-1"), step: 1, side: "left" }, { sel: S("between", "#len-between-0"), step: 2, side: "right" }], S("between", ".col[data-col='0']"));
await snap("grid-length-warning", [{ sel: S("between", "#len-between-1"), step: 1, side: "right" }], S("between", ".col[data-col='1']"));
await op("between", { op: "reset" }); await op("between", { op: "mode", mode: "sequence" });
// The file lists
await page.goto(base.replace(/\/breaks$/, "/files")); await page.waitForSelector("#table tbody tr"); await wait(300);
await page.setViewportSize({ width: 1100, height: 1300 });
await page.locator('#table tbody tr:nth-child(2) input').check(); await page.locator('#table tbody tr:nth-child(3) input').check(); await wait(100);
await snap("files-list", [{ sel: "#q", step: 1, side: "top" }, { sel: "#sort", step: 2, side: "top" }, { sel: "#table tbody tr:nth-child(2) input", step: 3, side: "left" }, { sel: "#add", step: 4, side: "top" }], "main", 760);
await page.selectOption("#kind", "extras"); await page.selectOption("#scope", "unused"); await wait(400);
await snap("files-filters", [{ sel: "#kind", step: 1, side: "top" }, { sel: "#scope", step: 2, side: "top" }, { sel: "#length", step: 3, side: "top" }], ".filters", 220);
await page.selectOption("#kind", "psa"); await page.selectOption("#scope", "all"); await wait(400);
await snap("files-psa", [{ sel: "#kind", step: 1, side: "top" }, { sel: "#table tbody tr:nth-child(1) th", step: 2, side: "right" }], "main", 560);
await b.close();
