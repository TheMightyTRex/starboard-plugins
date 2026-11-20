// The Philips Hue plug-in's pages in Starboard, checked and pictured (tools/hue_screens/run.sh): axe-core WCAG 2.2 AA
// in Light, Dark and High contrast on every tab and opened menu; the main tasks done by keyboard, with where focus is
// after each and what the live region says; a Tab walk of each tab; reading order of headings; pictures of each screen.
// Against Starboard's example server and the made-up bridge: nothing real is touched.
import { chromium } from "playwright";
import fs from "fs";

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";  // the made-up bridge's own certificate, for its /_press only
const base = process.env.BASE;
const bridge = process.env.BRIDGE;  // 127.0.0.1:port of the made-up bridge
const out = process.env.OUT || "/work/out";
const password = fs.readFileSync(process.env.PASSWORD_FILE, "utf8").trim();
const AXE = fs.readFileSync(process.env.AXE, "utf8");
fs.mkdirSync(out, { recursive: true });
const findings = [], notes = [];
const add = (where, rule, detail) => findings.push({ where, rule, detail: String(detail).slice(0, 400) });
const note = (where, what) => notes.push({ where, what: String(what).slice(0, 400) });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, bypassCSP: true });
const page = await ctx.newPage();
page.on("pageerror", (e) => add("page", "script error", e.message));
await page.goto(`${base}/login.html`);
await page.locator("#password").fill(password);
await page.locator("#password").press("Enter");
await page.waitForURL((u) => !u.pathname.endsWith("login.html"), { timeout: 15000 });

const wait = (ms) => page.waitForTimeout(ms);
async function settle() {
  await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
  await page.waitForFunction(() => !document.querySelector("[aria-busy=true]") && ![...document.querySelectorAll("p")].some((p) => p.textContent === "Loading…"), null, { timeout: 10000 }).catch(() => {});
  await wait(600);
}
async function axe(where) {
  for (const [mode, set] of [["light", () => document.documentElement.setAttribute("data-theme", "light")],
    ["dark", () => document.documentElement.setAttribute("data-theme", "dark")],
    ["high contrast", () => { document.documentElement.removeAttribute("data-theme"); document.documentElement.classList.add("pref-contrast"); }]]) {
    await page.evaluate(set);
    await wait(150);
    await page.addScriptTag({ content: AXE });
    const r = await page.evaluate(async () => (await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] }, resultTypes: ["violations"] }))
      .violations.map((v) => `${v.id} (${v.impact}): ${v.help} at ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`));
    for (const v of r) add(`${where}, ${mode}`, "axe", v);
  }
  await page.evaluate(() => { document.documentElement.classList.remove("pref-contrast"); document.documentElement.setAttribute("data-theme", "light"); });
  note(where, "axe: Light, Dark and High contrast checked");
}
async function shot(name, locator) {
  await page.evaluate(() => document.activeElement?.blur?.());
  if (locator) await locator.screenshot({ path: `${out}/${name}.png` });
  else await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
}
const focusNow = () => page.evaluate(() => {
  const e = document.activeElement;
  return e ? `${e.tagName.toLowerCase()}${e.dataset.key ? `[${e.dataset.key}]` : ""} "${(e.getAttribute("aria-label") || e.textContent || e.value || "").trim().replace(/\s+/g, " ").slice(0, 70)}"` : "nothing";
});
// What was said: Starboard puts a row's answer in a saved note beside its control, and the rest in the line above the list.
const said = (section) => section.evaluate((s) => [...s.querySelectorAll("[role=status], .saved-note")].map((e) => e.textContent.trim()).filter(Boolean).join(" | "));
async function tab(name) {
  await page.locator("#topic-tabs [role=tab]", { hasText: new RegExp(`^${name}$`) }).click();
  await settle();
  return page.locator(".topic-on, section:not(.topic-off)").filter({ has: page.locator("h2", { hasText: new RegExp(`^${name}$`) }) }).first();
}
async function tabWalk(where, count = 40) {
  await page.evaluate(() => { document.activeElement?.blur?.(); });
  const seen = [];
  for (let i = 0; i < count; i++) {
    await page.keyboard.press("Tab");
    const f = await page.evaluate(() => {
      const e = document.activeElement;
      if (!e || e === document.body) return null;
      const r = e.getBoundingClientRect();
      const st = getComputedStyle(e);
      const ring = st.outlineStyle !== "none" && parseFloat(st.outlineWidth) > 0 || st.boxShadow !== "none";
      return { name: (e.getAttribute("aria-label") || e.labels?.[0]?.textContent || e.textContent || e.value || "").trim().replace(/\s+/g, " ").slice(0, 60),
        tag: e.tagName.toLowerCase(), y: Math.round(r.top + window.scrollY), visible: r.width > 0 && r.height > 0, ring };
    });
    if (!f) { add(where, "Tab walk", `focus went to the page itself after ${i} presses`); break; }
    if (!f.visible) add(where, "Tab walk", `an unseen element took focus: ${f.tag} ${f.name}`);
    if (!f.ring) add(where, "Tab walk", `no visible focus on ${f.tag} "${f.name}"`);
    seen.push(f);
  }
  note(where, `Tab walk: ${seen.map((f) => f.name || f.tag).join(" > ")}`);
}
async function order(where, section) {
  const hs = await section.evaluate((s) => [...s.querySelectorAll("h2,h3,h4,h5")].filter((h) => h.getClientRects().length).map((h) => `${h.tagName}:${h.textContent.trim()}`));
  note(where, `Headings in reading order: ${hs.join(" | ")}`);
  const levels = hs.map((h) => Number(h[1]));
  for (let i = 1; i < levels.length; i++) if (levels[i] > levels[i - 1] + 1) add(where, "headings", `h${levels[i - 1]} then h${levels[i]}: ${hs[i]}`);
}

await page.goto(`${base}/settings-plugin.html?id=philips-hue`);
await settle();
await axe("Plug-in page, first tab");

// Bridge: pair by address, wait for the button, then paired ---------------------------------------------------------
let s = await tab("Bridge");
await order("Bridge", s);
await shot("1-bridge-not-paired", s);
await axe("Bridge, not paired");
await tabWalk("Bridge, not paired", 25);
const addBox = s.getByLabel("Pair with a bridge");
await addBox.fill(bridge);
await addBox.press("Enter");
await settle();
note("Bridge, after Pair", `focus: ${await focusNow()}; said: ${await said(s)}`);
if (!/Press the round link button/.test(await said(s))) add("Bridge, after Pair", "live region", `said: ${await said(s)}`);
await shot("2-bridge-waiting-for-button", s);
await axe("Bridge, waiting for the button");
await fetch(`https://${bridge}/_press`).catch((e) => add("Bridge", "press", e.message));
await page.waitForFunction(() => [...document.querySelectorAll(".notice")].some((n) => /Paired with/.test(n.textContent)), null, { timeout: 15000 })
  .catch(() => add("Bridge", "pairing", "the page did not say Paired within 15 seconds"));
await settle();
await shot("3-bridge-paired", s);
await axe("Bridge, paired");
const pairedNote = await page.evaluate(() => { const n = [...document.querySelectorAll(".notice")].find((x) => /Paired with/.test(x.textContent)); return n ? `${n.getAttribute("role") || "no role"}: ${n.textContent.trim().slice(0, 120)}` : ""; });
note("Bridge, paired", `the notice: ${pairedNote}`);

// Starboard loads each tab once, when the page opens: the notice says to reload, as a person would.
await page.reload();
await settle();

// Rooms: open a room, switch, dim, colour, every light ----------------------------------------------------------------
s = await tab("Rooms");
await order("Rooms", s);
await shot("4-rooms", s);
await axe("Rooms");
await tabWalk("Rooms", 20);
await s.getByRole("button", { name: "Kitchen", exact: true }).focus();
await page.keyboard.press("Enter");
await settle();
note("Rooms, Kitchen opened", `focus: ${await focusNow()}`);
if (!/h3/.test(await focusNow())) add("Rooms, Kitchen opened", "focus", `expected the room's heading, got ${await focusNow()}`);
await order("Rooms, Kitchen", s);
await shot("5-room-kitchen", s);
await axe("Rooms, Kitchen");
const toggle = s.getByRole("button", { name: /Activate Under cupboard/ });
await toggle.focus();
await page.keyboard.press("Enter");
await settle();
let f = await focusNow();
note("Rooms, after Activate Under cupboard", `focus: ${f}; said: ${await said(s)}`);
if (!/toggle/.test(f)) add("Rooms, after Activate", "focus", `focus moved to ${f}`);
if (!(await said(s)).includes("Under cupboard is on")) add("Rooms, after Activate", "live region", `said: ${await said(s)}`);
const bri = s.getByLabel("Brightness: Ceiling", { exact: true });
await bri.focus();
await bri.selectOption("40");
await settle();
note("Rooms, after Brightness 40%", `focus: ${await focusNow()}; said: ${await said(s)}`);
if (!/choose/.test(await focusNow())) add("Rooms, after Brightness", "focus", `focus moved to ${await focusNow()}`);
const col = s.getByLabel("Colour: Ceiling colour", { exact: true });
await col.selectOption("blue");
await settle();
note("Rooms, after Colour blue", `said: ${await said(s)}; the row says: ${(await s.locator("li.row", { hasText: "Ceiling colour" }).first().textContent()).replace(/\s+/g, " ").trim().slice(0, 140)}`);
const sw = s.getByRole("switch", { name: "Every light in Kitchen" });
await sw.focus();
await page.keyboard.press("Space");
await settle();
note("Rooms, after the Kitchen switch", `focus: ${await focusNow()}; saved note: ${await s.locator(".saved-note").first().textContent().catch(() => "")}`);
await shot("6-room-kitchen-after-changes", s);
await s.getByRole("button", { name: /Back to Rooms/ }).click();
await settle();
note("Rooms, back", `focus: ${await focusNow()}`);

// Zones and Device types ----------------------------------------------------------------------------------------------
s = await tab("Zones");
await shot("7-zones", s);
await axe("Zones");
await s.getByRole("button", { name: "Downstairs", exact: true }).click();
await settle();
await shot("8-zone-downstairs", s);
await axe("Zones, Downstairs");
s = await tab("Device types");
await shot("9-device-types", s);
await axe("Device types");
await s.getByRole("button", { name: "Lamps", exact: true }).click();
await settle();
await shot("10-device-type-lamps", s);
await axe("Device types, Lamps");

// Scenes --------------------------------------------------------------------------------------------------------------
s = await tab("Scenes");
await shot("11-scenes", s);
await axe("Scenes");
await s.getByRole("button", { name: "Lounge", exact: true }).click();
await settle();
const film = s.getByRole("button", { name: /Activate Film night/ });
await film.focus();
await page.keyboard.press("Enter");
await settle();
note("Scenes, after Activate Film night", `focus: ${await focusNow()}; said: ${await said(s)}`);
await shot("12-scenes-lounge", s);
await axe("Scenes, Lounge");

// Schedules -----------------------------------------------------------------------------------------------------------
s = await tab("Schedules");
await shot("13-schedules-empty", s);
const sched = s.getByLabel("Add a schedule");
for (const text of ["Every weekday at 07:00, Kitchen to 80%", "Every day at sunset, Lounge to Film night", "Every day at 23:30, every light off"]) {
  await sched.fill(text);
  await sched.press("Enter");
  await settle();
  note("Schedules, after Add", `focus: ${await focusNow()}; said: ${await said(s)}`);
}
await sched.fill("Every day at 7, Garage on");
await sched.press("Enter");
await settle();
const err = await page.evaluate(() => [...document.querySelectorAll("[role=alert], .field__error, .notice--danger, .error")].map((e) => e.textContent.trim()).filter(Boolean).join(" | "));
note("Schedules, a mistake", `focus: ${await focusNow()}; shown: ${err}`);
await shot("14-schedules-a-mistake", s);
await sched.fill("");
await s.getByRole("button", { name: /Change for Every weekday at 07:00/ }).click();
await settle();
note("Schedules, Change opened", `focus: ${await focusNow()}`);
await shot("15-schedules-change", s);
await axe("Schedules, Change open");
await s.getByRole("textbox", { name: "The schedule in words" }).focus();  // shot() takes focus off, so the picture has no focus ring
await page.keyboard.press("Control+a");
await page.keyboard.type("Every weekday at 07:30, Kitchen to warm white at 60%");
await page.keyboard.press("Enter");
await settle();
note("Schedules, after Change", `focus: ${await focusNow()}; said: ${await said(s)}`);
await shot("16-schedules", s);
await axe("Schedules");
await tabWalk("Schedules", 30);

// When something plays --------------------------------------------------------------------------------------------------
s = await tab("When something plays");
await shot("17-when-something-plays", s);
await axe("When something plays");

// The buttons and the dashboard cards ------------------------------------------------------------------------------------
await page.evaluate(async () => fetch("/api/config/general", { method: "PUT", headers: { "Content-Type": "application/json", "X-Starboard": "1" },
  body: JSON.stringify({ dashboard: { layout: "glance", cards: [{ id: "plugin:philips-hue:rooms", size: "half" }, { id: "plugin:philips-hue:lights", size: "half" },
    { id: "health", size: "half" }, { id: "disk", size: "half" }] } }) }));
await page.goto(`${base}/dashboard.html`);
await settle();
await wait(1500);
const saved = await page.evaluate(async () => (await fetch("/api/config/general")).status);
note("Dashboard", `the dashboard was saved, Starboard answered ${saved}`);
const cards = page.locator("main section, main article, main .card").filter({ hasText: "Philips Hue" });
note("Dashboard", `${await cards.count()} Philips Hue cards: ${(await cards.allTextContents()).map((t) => t.replace(/\s+/g, " ").trim().slice(0, 160)).join(" || ")}`);
await shot("18-dashboard-cards");
await axe("Dashboard with the cards");

fs.writeFileSync(`${out}/check.json`, JSON.stringify({ findings, notes }, null, 1));
for (const n of notes) console.log(`NOTE ${n.where}: ${n.what}`);
for (const x of findings) console.log(`FIND ${x.where} [${x.rule}] ${x.detail}`);
console.log(`${findings.length} findings`);
await browser.close();
