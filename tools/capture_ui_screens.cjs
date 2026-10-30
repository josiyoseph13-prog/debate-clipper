"use strict";
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");

(async () => {
  const base = process.argv[2] || "http://127.0.0.1:8765";
  const destination = process.argv[3];
  const token = process.argv[4] || "";
  if (!destination) throw new Error("output folder is required");
  fs.mkdirSync(destination, {recursive: true});
  const browserPath = [
    "C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe",
    "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe",
  ].find(candidate => fs.existsSync(candidate));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, deviceScaleFactor: 1});
    const url = pathName => `${base}${pathName}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
    await page.goto(url("/classic"));
    await page.screenshot({path: path.join(destination, "classic.png"), fullPage: true});
    await page.goto(url("/"));
    await page.locator("#home-view .add-box").waitFor();
    await page.screenshot({path: path.join(destination, "home.png"), fullPage: true});
    await page.locator(".step[data-view='find']").click();
    await page.screenshot({path: path.join(destination, "find.png"), fullPage: true});
    await page.locator(".step[data-view='review']").click();
    await page.locator("#review-view").waitFor();
    await page.waitForTimeout(500);
    await page.screenshot({path: path.join(destination, "review.png"), fullPage: true});
    await page.locator(".step[data-view='export']").click();
    await page.screenshot({path: path.join(destination, "export.png"), fullPage: true});
    await page.getByRole("button", {name: "My exports", exact: true}).click();
    await page.screenshot({path: path.join(destination, "my-exports.png"), fullPage: true});
    console.log(JSON.stringify({status: "passed", destination, screens: ["classic", "home", "find", "review", "export", "my-exports"]}));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
