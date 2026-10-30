"use strict";
// Diagnostic probe: what does Review actually render right now?
const fs = require("node:fs");
const {chromium} = require("playwright");
const base = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(v => fs.existsSync(v));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const errs = [];
  page.on("pageerror", e => errs.push("pageerror: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text().slice(0, 160)); });
  await page.goto(base, {waitUntil: "domcontentloaded"});
  await page.locator("#home-view .add-box").waitFor({timeout: 30000});
  await sleep(6000);
  await page.locator(".step[data-view='review']").click();
  await sleep(4000);
  const dump = await page.evaluate(() => {
    const rows = [...document.querySelectorAll("#review-view .clip-row")].map(r => r.getAttribute("data-review-key"));
    const groups = [...document.querySelectorAll("#review-view .source-group h3")].map(h => h.textContent.trim());
    const viewText = (document.querySelector("#review-view")?.textContent || "").replace(/\s+/g, " ").slice(0, 400);
    return {rowCount: rows.length, rows: rows.slice(0, 8), hasFailtest: rows.some(k => k && k.includes("failtest")), groups, viewText};
  });
  console.log("RESULT:" + JSON.stringify({dump, errs: errs.slice(0, 5)}));
  await browser.close().catch(() => {});
})();
