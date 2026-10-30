"use strict";
// Probe: fresh page -> Edit jo's clip -> Captions group -> dump the
// client-side caption control state at intervals after opening.
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
  await page.evaluate(() => {
    const v = document.querySelector("#review-view .video-shell video");
    if (v && !v.currentSrc.includes("/proxy")) v.src = v.currentSrc.replace(/\/(source|clip)([?#]|$)/, "/proxy$2");
  });
  await sleep(1000);
  await review.locator(".edit-accordion-trigger", {hasText: "Captions"}).first().click();
  await review.locator(".caption-toggle").waitFor({timeout: 15000});
  const dump = label => page.evaluate(() => {
    const slider = document.querySelector(".caption-size-slider");
    const swatches = [...document.querySelectorAll(".caption-swatch")].map(s => `${s.dataset.color}${s.classList.contains("active") ? "*" : ""}`);
    const looks = [...document.querySelectorAll(".caption-look")].map(s => `${s.dataset.look}${s.classList.contains("active") ? "*" : ""}`);
    const note = document.querySelector(".caption-cue-note")?.textContent || "";
    return {slider: slider ? slider.value : null, sizeLabel: document.querySelector(".caption-size-value")?.textContent || null, swatches, looks, note};
  }).then(d => console.log(label, JSON.stringify(d)));
  await dump("t+0s:");
  await sleep(3000);
  await dump("t+3s:");
  await sleep(4000);
  await dump("t+7s:");
  await browser.close();
})();
