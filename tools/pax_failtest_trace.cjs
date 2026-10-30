"use strict";

// Disposable export-failure check (2026-10-12): open the disposable
// job's clip, click Export (its source media is missing, so the
// app's own render fails), wait for the "Export failed — Try again"
// button state, then measure that button (wrapping, overflow,
// overlap) and screenshot it. No real job is touched.

const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");
const base = process.argv[2];
const key = "pax_failtest_20261012/c_failtest01";
const outDir = path.join("work", "deploy_validation", "phase4b_checks");
fs.mkdirSync(outDir, {recursive: true});
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
    await page.locator(".step[data-view='review']").click();
    const row = review.locator(`.clip-row[data-review-key='${key}']`);
    await row.waitFor({timeout: 20000});
    await row.click();
    await sleep(1000);
    const exportBtn = review.locator(".review-actions .export");
    await exportBtn.waitFor({timeout: 15000});
    out.evidence.initialLabel = (await exportBtn.textContent())?.trim();
    await exportBtn.click();
    let label = "";
    const deadline = Date.now() + 240000;
    while (Date.now() < deadline) {
      await sleep(5000);
      label = ((await exportBtn.textContent().catch(() => "")) || "").trim();
      if (/Export failed/.test(label)) break;
    }
    out.evidence.finalLabel = label;
    check("export reached the failed state via the app itself", /Export failed — Try again/.test(label), label);
    if (/Export failed/.test(label)) {
      const metrics = await page.evaluate(() => {
        const btn = document.querySelector("#review-view .review-actions .export");
        const actions = [...document.querySelectorAll("#review-view .review-actions .review-action")].map(el => {
          const r = el.getBoundingClientRect();
          return {text: (el.textContent || "").trim().slice(0, 30), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), bottom: Math.round(r.bottom), scrollW: el.scrollWidth, clientW: el.clientWidth, scrollH: el.scrollHeight, clientH: el.clientHeight};
        });
        const overlaps = [];
        for (let i = 0; i < actions.length; i++) for (let j = i + 1; j < actions.length; j++) {
          const a = actions[i], b = actions[j];
          const ox = Math.min(a.right, b.right) - Math.max(a.x, b.x);
          const oy = Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y);
          if (ox > 2 && oy > 2) overlaps.push(`${a.text} <-> ${b.text}`);
        }
        return {actions, overlaps};
      });
      out.evidence.actions = metrics.actions;
      out.evidence.overlaps = metrics.overlaps;
      const failed = metrics.actions.find(a => /Export failed/.test(a.text));
      check("failed button does not overlap neighbours", metrics.overlaps.length === 0, metrics.overlaps.join(" | ") || "none");
      check("long label fits inside its button (no overflow)", !!failed && failed.scrollW <= failed.clientW + 1, JSON.stringify(failed));
      await page.screenshot({path: path.join(outDir, "failtest_failed_button.png")}).catch(() => {});
    }
  } catch (error) {
    out.harnessError = String(error && error.message || error);
  } finally {
    await browser.close().catch(() => {});
  }
  console.log("RESULT:" + JSON.stringify(out));
})();
