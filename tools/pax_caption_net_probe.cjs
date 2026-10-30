"use strict";
// Probe 2: log what the browser actually receives for /api/jobs and
// /api/candidates/<id>, then dump the caption group state.
const fs = require("node:fs");
const {chromium} = require("playwright");
const base = process.argv[2];
const key = "job_7422d0f93cd1/c_b08dcd6a3b97";
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe"].find(v => fs.existsSync(v));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  page.on("pageerror", e => console.log("PAGEERROR:", e.message));
  page.on("response", async response => {
    const url = response.url();
    try {
      if (url.includes("/api/jobs")) {
        const data = await response.json();
        const rec = (data.candidates || []).find(r => r.id === "c_b08dcd6a3b97" && r.job_id === "job_7422d0f93cd1");
        console.log("JOBS caption_controls:", JSON.stringify(rec?.decision?.caption_controls));
      }
      if (url.includes("/api/candidates/job_7422d0f93cd1/c_b08dcd6a3b97?")) {
        const data = await response.json();
        console.log("FRESH caption_controls:", JSON.stringify(data?.decision?.caption_controls));
      }
      if (url.includes("caption-cues")) {
        const data = await response.json();
        console.log("CUES style/font/dy:", data.style, data.font_size, data.dy);
      }
    } catch (e) { console.log("probe parse err", e.message); }
  });
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
  await page.waitForFunction(() => document.querySelector("#review-view .edit-saved-headline")?.textContent.startsWith("Saved headline:"), null, {timeout: 20000});
  await sleep(1500);
  await review.locator(".edit-accordion-trigger", {hasText: "Captions"}).first().click();
  await review.locator(".caption-toggle").waitFor({timeout: 15000});
  await sleep(2500);
  const dump = await page.evaluate(() => {
    const slider = document.querySelector(".caption-size-slider");
    const activeSwatch = document.querySelector(".caption-swatch.active");
    return {slider: slider ? slider.value : null, swatch: activeSwatch ? activeSwatch.dataset.color : null};
  });
  console.log("GROUP:", JSON.stringify(dump));
  await browser.close();
})();
