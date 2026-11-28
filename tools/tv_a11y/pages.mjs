// Accessibility checks of the TV channel plug-in's own pages (desktop only: 1280 and 1024 wide, light, dark and forced colours):
// axe (WCAG 2 A and AA, 2.1 and 2.2 AA, best practice) on each page, and a keyboard walk of Shows at set times. Run by tools/tv_a11y.sh.
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
const BASE = process.env.BASE, TOKEN = process.env.TOKEN;
const axeSource = readFileSync(process.env.AXE, "utf8");
const pages = [["times", `/t/${TOKEN}/times`], ["grid", `/t/${TOKEN}/grid`], ["breaks", `/t/${TOKEN}/breaks?grid=between`], ["files", `/t/${TOKEN}/files`]];
const sizes = [[1280, 800], [1024, 768]];
const modes = [["light", {}], ["dark", {}], ["forced-colors", { forcedColors: "active" }]];
const browser = await chromium.launch();
const out = { axe: [], walk: [], notes: [] };
let bad = 0;
for (const [name, path] of pages) {
  for (const [w, h] of sizes) {
    for (const [mode, opts] of modes) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, ...opts });
      if (mode === "dark") await ctx.addInitScript(() => { try { localStorage.setItem("tvgrid-theme", "dark"); } catch {} });
      const page = await ctx.newPage();
      await page.goto(BASE + path);
      await page.waitForTimeout(700);
      await page.evaluate(axeSource);
      const r = await page.evaluate(() => axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] } }));
      const v = r.violations.map((x) => ({ id: x.id, impact: x.impact, nodes: x.nodes.length, first: x.nodes[0]?.target?.join(" ") }));
      out.axe.push({ page: name, size: `${w}x${h}`, mode, violations: v });
      bad += v.length;
      await ctx.close();
    }
  }
}
// Keyboard walk of Shows at set times at 1280 wide.
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/t/${TOKEN}/times`);
  await page.waitForTimeout(500);
  const order = [];
  const label = () => page.evaluate(() => { const a = document.activeElement; return a ? `${a.tagName.toLowerCase()}${a.id ? "#" + a.id : ""}:${(a.getAttribute("aria-label") || a.textContent || a.value || "").trim().slice(0, 30)}` : "none"; });
  for (let i = 0; i < 9; i++) { await page.keyboard.press("Tab"); order.push(await label()); }
  out.walk.push({ step: "tab order", order });
  await page.focus("#q");
  await page.keyboard.type("harbour");
  await page.keyboard.press("Enter");
  await page.waitForSelector("input[name=pick]");
  out.walk.push({ step: "focus after Find", at: await label() });
  await page.keyboard.press("Space");
  await page.focus("button[data-days='0,1,2,3,4']");
  await page.keyboard.press("Enter");
  await page.focus("#go");
  await page.keyboard.press("Enter");
  await page.waitForSelector("#list li");
  out.walk.push({ step: "focus after Add", at: await label(), said: await page.textContent("#said") });
  await page.keyboard.press("Shift+Tab");
  await page.focus("#list li button");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(500);
  out.walk.push({ step: "focus after Remove", at: await label(), said: await page.textContent("#said"), none: await page.isVisible("#none") });
  await page.focus("#go");
  await page.keyboard.press("Enter");
  out.walk.push({ step: "Add with nothing chosen", problem: await page.textContent("#problem"), at: await label(), role: await page.getAttribute("#problem", "role") });
  await ctx.close();
}
// The narrow-screen notice: shown under 48rem, never over it.
{
  const ctx = await browser.newContext({ viewport: { width: 700, height: 800 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/t/${TOKEN}/times`);
  out.notes.push({ narrow_notice_visible: await page.isVisible(".desktop-note"), text: await page.textContent(".desktop-note") });
  await page.setViewportSize({ width: 1024, height: 768 });
  out.notes.push({ at_1024_visible: await page.isVisible(".desktop-note") });
  await ctx.close();
}
await browser.close();
console.log(JSON.stringify(out, null, 1));
process.exit(bad ? 1 : 0);
