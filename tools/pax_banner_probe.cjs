"use strict";
// Read-only probe: fresh load -> Review -> jo's clip -> read banner text.
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");
const base = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(v => fs.existsSync(v));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const review = page.locator("#review-view");
  await page.goto(base, {waitUntil: "domcontentloaded"});
  await page.locator("#home-view .add-box").waitFor({timeout: 30000});
  await page.locator(".step[data-view='review']").click();
  const row = review.locator(".clip-row[data-review-key='job_7422d0f93cd1/c_b08dcd6a3b97']");
  await row.waitFor({timeout: 20000});
  await row.click();
  await sleep(2500);
  const shellText = await review.locator(".video-shell").first().evaluate(el => el.textContent).catch(() => "NO-SHELL");
  const overlayText = await page.evaluate(() => {
    const els = [...document.querySelectorAll("#review-view .video-shell *")].map(e => (e.textContent || "").trim()).filter(t => t.length > 3 && t.length < 200);
    return els;
  });
  console.log("RESULT:" + JSON.stringify({shellText: (shellText || "").replace(/\s+/g, " ").slice(0, 200), overlayText}));
  await page.screenshot({path: path.join("work", "deploy_validation", "phase4b_checks", "b_fresh_banner.png")}).catch(() => {});
  await browser.close().catch(() => {});
})();
