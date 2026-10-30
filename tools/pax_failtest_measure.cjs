"use strict";
// Second pass: fresh load; the disposable clip's failed attempt is
// already stored server-side, so its button must render as
// "Export failed — Try again" immediately. Measure it while visible.
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");
const base = process.argv[2];
const key = "pax_failtest_20261012/c_failtest01";
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(v => fs.existsSync(v));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  const out = {checks: [], evidence: {}, errors: []};
  const check = (name, pass, detail) => out.checks.push({name, pass: !!pass, detail: String(detail ?? "")});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    page.on("pageerror", e => out.errors.push(e.message));
    const review = page.locator("#review-view");
    await page.goto(base, {waitUntil: "domcontentloaded"});
    await page.locator("#home-view .add-box").waitFor({timeout: 30000});
    const row = review.locator(`.clip-row[data-review-key='${key}']`);
    let attached = false;
    for (let attempt = 0; attempt < 4 && !attached; attempt++) {
      await page.locator(".step[data-view='review']").click();
      try {
        await row.waitFor({state: "attached", timeout: 15000});
        attached = true;
      } catch {
        await page.locator(".step[data-view='home']").click().catch(() => {});
        await sleep(3000);
      }
    }
    if (!attached) throw new Error("disposable row never rendered after retries");
    await row.evaluate(el => el.click());
    await sleep(1500);
    const exportBtn = review.locator(".review-actions .export");
    await exportBtn.waitFor({state: "visible", timeout: 15000});
    const label = ((await exportBtn.textContent()) || "").trim();
    out.evidence.label = label;
    check("failed state persists on fresh load", /Export failed — Try again/.test(label), label);
    await exportBtn.scrollIntoViewIfNeeded();
    await sleep(400);
    const box = await exportBtn.boundingBox();
    out.evidence.failedBox = box;
    const metrics = await page.evaluate(() => {
      const els = [...document.querySelectorAll("#review-view .review-actions .review-action")];
      const list = els.map(el => {
        const r = el.getBoundingClientRect();
        return {text: (el.textContent || "").trim().slice(0, 30), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), bottom: Math.round(r.bottom), scrollW: el.scrollWidth, clientW: el.clientWidth};
      }).filter(a => a.w > 0 && a.h > 0);
      const overlaps = [];
      for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
        const a = list[i], b = list[j];
        const ox = Math.min(a.right, b.right) - Math.max(a.x, b.x);
        const oy = Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y);
        if (ox > 2 && oy > 2) overlaps.push(`${a.text} <-> ${b.text} (${ox}x${oy})`);
      }
      return {list, overlaps};
    });
    out.evidence.actions = metrics.list;
    out.evidence.overlaps = metrics.overlaps;
    const failed = metrics.list.find(a => /Export failed/.test(a.text));
    check("failed button has real size", !!failed && failed.w > 100 && failed.h > 20, JSON.stringify(failed));
    check("no overlap with neighbours", metrics.overlaps.length === 0, metrics.overlaps.join(" | ") || "none");
    check("long label fits inside button (scrollW <= clientW)", !!failed && failed.scrollW <= failed.clientW + 1, failed ? `scrollW=${failed.scrollW} clientW=${failed.clientW} h=${failed.h}` : "missing");
    check("button clickable (visible + enabled)", await exportBtn.isEnabled() && !!box, label);
    await page.screenshot({path: path.join("work", "deploy_validation", "phase4b_checks", "failtest_failed_button.png")}).catch(() => {});
  } catch (error) {
    out.harnessError = String(error && error.message || error);
  } finally {
    await browser.close().catch(() => {});
  }
  console.log("RESULT:" + JSON.stringify(out));
})();
