"use strict";
// Probe: reopen Edit on the clip with ONE saved pin (zoom 2.0) and
// dump what the Framing editor actually shows + media state.
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
  await page.waitForFunction(() => {
    const el = document.querySelector("#review-view .edit-saved-headline");
    return el && el.textContent.startsWith("Saved headline:");
  }, null, {timeout: 20000});
  await sleep(800);
  await review.locator(".edit-accordion-trigger", {hasText: "Framing"}).first().click();
  await review.locator(".framing-pin-strip").waitFor({timeout: 15000});
  await sleep(1500);
  const dump = await page.evaluate(() => {
    const v = document.querySelector("#review-view .video-shell video");
    return {
      header: document.querySelector(".framing-pin-header")?.textContent?.trim(),
      slider: document.querySelector(".framing-zoom")?.value,
      dots: document.querySelectorAll(".framing-pin-dot").length,
      status: document.querySelector(".framing-save-status")?.textContent?.trim(),
      currentTime: v?.currentTime, duration: v?.duration,
      src: (v?.currentSrc || "").split("/").slice(-1)[0],
    };
  });
  console.log("RESULT:" + JSON.stringify(dump));
  await browser.close().catch(() => {});
})();
