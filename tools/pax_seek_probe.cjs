"use strict";
// Probe: can the Edit video actually seek? What does the add button see?
const fs = require("node:fs");
const {chromium} = require("playwright");
const base = process.argv[2];
const key = "job_7422d0f93cd1/c_b08dcd6a3b97";
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(v => fs.existsSync(v));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const review = page.locator("#review-view");
  await page.goto(base, {waitUntil: "domcontentloaded"});
  await page.locator("#home-view .add-box").waitFor({timeout: 30000});
  await page.locator(".step[data-view='review']").click();
  const row = review.locator(`.clip-row[data-review-key='${key}']`);
  await row.waitFor({timeout: 25000});
  await row.click();
  await sleep(700);
  await review.getByRole("button", {name: "Edit", exact: true}).click();
  await review.locator(".edit-headline-field input").waitFor({timeout: 20000});
  await sleep(2500);
  const before = await page.evaluate(() => {
    const v = document.querySelector("#review-view .video-shell video");
    return {src: (v.currentSrc || "").split("/").slice(-2).join("/"), readyState: v.readyState, duration: v.duration, currentTime: v.currentTime, seekable: v.seekable.length ? [v.seekable.start(0), v.seekable.end(0)] : null, error: v.error?.message || null};
  });
  await page.evaluate(() => { const v = document.querySelector("#review-view .video-shell video"); v.currentTime = 291.11 + 20; });
  await sleep(2500);
  const after = await page.evaluate(() => {
    const v = document.querySelector("#review-view .video-shell video");
    return {currentTime: v.currentTime, readyState: v.readyState, seeking: v.seeking};
  });
  await review.locator(".edit-accordion-trigger", {hasText: "Framing"}).first().click();
  await sleep(900);
  const btn = await review.locator(".framing-add-pin").textContent().catch(() => "NO-BTN");
  console.log("RESULT:" + JSON.stringify({before, after, addButtonLabel: (btn || "").trim()}));
  await browser.close().catch(() => {});
})();
