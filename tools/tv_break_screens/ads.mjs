// Help pictures for where breaks go inside a programme (DASH-538), and an accessibility check of Starboard's own page for the
// plug-in (Channels card Breaks, and the Break grids tab) with axe: tools/tv_break_screens/ads.sh. Example data only.
import { chromium } from "playwright";
import fs from "fs";
const base = process.env.SB, out = process.env.OUT || "/work/out";
const pw = fs.readFileSync(process.env.PASSWORD_FILE, "utf8").trim();
const annotate = fs.readFileSync(process.env.ANNOTATE, "utf8"), AXE = fs.readFileSync(process.env.AXE, "utf8");
fs.mkdirSync(out, { recursive: true });
const findings = [];
const b = await chromium.launch();
const page = await (await b.newContext({ viewport: { width: 1100, height: 1500 }, bypassCSP: true })).newPage();
await page.goto(`${base}/login.html`);
await page.locator("#password").fill(pw); await page.locator("#password").press("Enter");
await page.waitForURL((u) => !u.pathname.endsWith("login.html"), { timeout: 15000 });
await page.goto(`${base}/settings-plugin.html?id=tv-station`); await page.waitForTimeout(2500);
const wait = (ms) => page.waitForTimeout(ms);
async function axe(where) {
  for (const [mode, set] of [["light", () => { document.documentElement.setAttribute("data-theme", "light"); }], ["dark", () => document.documentElement.setAttribute("data-theme", "dark")],
    ["high contrast", () => { document.documentElement.removeAttribute("data-theme"); document.documentElement.classList.add("pref-contrast"); }]]) {
    await page.evaluate(set); await wait(150);
    await page.addScriptTag({ content: AXE });
    const r = await page.evaluate(async () => (await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] }, resultTypes: ["violations"] }))
      .violations.map((v) => `${v.id} (${v.impact}) at ${v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(" | ")}`));
    for (const v of r) findings.push(`${where}, ${mode}: ${v}`);
  }
  await page.evaluate(() => { document.documentElement.classList.remove("pref-contrast"); document.documentElement.setAttribute("data-theme", "light"); });
}
async function mark(titles, name, steps, from, to) {
  await page.evaluate(annotate);
  await wait(200);
  const box = await page.evaluate(({ titles, from, to }) => {
    const row = (t) => [...document.querySelectorAll(".row__title")].find((h) => h.textContent.trim() === t)?.closest("li, .row, div[class*=row]") || null;
    row(from).scrollIntoView({ block: "start" }); window.scrollBy(0, -60);
    const rows = titles.map(row);
    rows.forEach((r, i) => { if (r) window.Annotate.mark(r, { step: i + 1, side: "left" }); });
    const a = row(from).getBoundingClientRect(), z = row(to).getBoundingClientRect();
    return { x: a.left, y: a.top, w: a.width, h: z.bottom - a.top };
  }, { titles, from, to });
  await page.screenshot({ path: `${out}/${name}.png`, clip: { x: Math.max(0, box.x - 60), y: Math.max(0, box.y - 20), width: Math.min(1100, box.w + 120), height: box.h + 50 } });
  await page.evaluate(() => window.Annotate.clear());
}
await page.locator("[role=tab]", { hasText: /^Channels$/ }).click(); await wait(1500);
await axe("Channels list");
await page.getByRole("button", { name: /1 Comedy/ }).first().click(); await wait(2000);
await axe("A channel's cards");
const T = { inside: "Breaks inside programmes", how: "Where breaks go inside a programme", per: "Breaks in each 30 minutes", film: "Breaks in a film", between: "In between programmes grid", breaks: "Breaks grid" };
await mark([T.inside, T.how], "ads-where", [1, 2], T.inside, T.how);
await mark([T.per, T.film], "ads-how-many", [1, 2], T.per, T.film);
await mark([T.between, T.breaks], "ads-grid-links", [1, 2], T.between, T.breaks);
await page.goto(`${base}/settings-plugin.html?id=tv-station`); await wait(2500);
await page.locator("[role=tab]", { hasText: /^Break grids$/ }).click(); await wait(1500);
await axe("Break grids tab");
await page.screenshot({ path: `${out}/ads-grids-tab.png`, clip: { x: 100, y: 240, width: 980, height: 520 } });
fs.writeFileSync(`${out}/ads.json`, JSON.stringify(findings, null, 1));
console.log(findings.length ? findings.join("\n") : "0 findings");
await b.close();
