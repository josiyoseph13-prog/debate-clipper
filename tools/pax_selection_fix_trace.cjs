"use strict";

// Pax verification trace for the wrong-job selection fix (2026-10-12).
// Against the REAL colliding jobs job_7422d0f93cd1 + deploy_e2e_raw
// (same source, same candidate IDs):
//  1. Click the DEPLOY job's row -> Edit headline must be that job's
//     own (auto) headline.
//  2. Click JO's job row -> Edit headline must be jo's saved
//     "what is an invasion?" (before the fix this showed the auto
//     headline = the other job's record).
//  3. Trim save on jo's clip; the caller then inspects both jobs'
//     decisions files. 4. Restore trim to 291.11/358.79.

const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");

const base = process.argv[2];
const candidateId = "c_b08dcd6a3b97";
const keyJo = `job_7422d0f93cd1/${candidateId}`;
const keyDeploy = `deploy_e2e_raw/${candidateId}`;
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

    const gotoReview = async key => {
      await page.goto(base, {waitUntil: "domcontentloaded"});
      await page.locator("#home-view .add-box").waitFor({timeout: 30000});
      await page.locator(".step[data-view='review']").click();
      const row = review.locator(`.clip-row[data-review-key='${key}']`);
      await row.waitFor({timeout: 20000});
      await row.click();
      await sleep(800);
    };
    const openEdit = async () => {
      await review.getByRole("button", {name: "Edit", exact: true}).click();
      const input = review.locator(".edit-headline-field input");
      await input.waitFor({timeout: 20000});
      await page.waitForFunction(() => {
        const el = document.querySelector("#review-view .edit-saved-headline");
        return el && (el.textContent.startsWith("Saved headline:") || el.textContent.startsWith("Could not load"));
      }, null, {timeout: 20000});
      await sleep(400);
      return input;
    };
    const openGroup = async label => {
      await review.locator(".edit-accordion-trigger", {hasText: label}).first().click();
      await sleep(600);
    };
    const saveAndDone = async () => {
      await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
      await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"), null, {timeout: 15000});
    };
    const cancelClose = async () => {
      const btn = review.getByRole("button", {name: "Cancel Edit", exact: true}).first();
      if (await btn.count()) {
        await btn.click();
        await sleep(500);
        const discard = review.getByRole("button", {name: "Discard", exact: true}).first();
        if (await discard.count()) { await discard.click(); await sleep(500); }
      }
    };
    const setTime = async (selector, value) => {
      const field = review.locator(selector);
      await field.click();
      await page.keyboard.press("Control+A");
      await page.keyboard.type(value);
      await page.keyboard.press("Tab");
      await sleep(400);
    };

    // 1. deploy job's row -> its OWN record (auto headline)
    await gotoReview(keyDeploy);
    const deployInput = await openEdit();
    const deployHeadline = await deployInput.inputValue();
    out.evidence.deployJobHeadline = deployHeadline;
    check("deploy row opens deploy job's own record", deployHeadline.startsWith("Okay, then let me ask"), deployHeadline);
    await cancelClose();

    // 2. jo's row -> JO's record (saved headline)
    await gotoReview(keyJo);
    const joInput = await openEdit();
    const joHeadline = await joInput.inputValue();
    const joLine = (await review.locator(".edit-saved-headline").textContent())?.trim();
    out.evidence.joJobHeadline = joHeadline;
    out.evidence.joSavedLine = joLine;
    check("jo row opens jo job's own record (saved headline)", joHeadline === "what is an invasion?", joHeadline);
    check("saved-headline line confirms jo's job", /Saved headline: "what is an invasion\?"/.test(joLine || ""), joLine);
    await page.screenshot({path: path.join(outDir, "fixcheck_jo_edit.png")}).catch(() => {});

    // 3. trim save on jo's clip
    await openGroup("Trim");
    await setTime(".trim-time-start", "299.27");
    await setTime(".trim-time-end", "349.59");
    await saveAndDone();
    check("trim save completed on jo's clip", true, "299.27/349.59");

    // 4. restore trim on jo's clip
    const joInput2 = await openEdit();
    check("reopen still jo's record", (await joInput2.inputValue()) === "what is an invasion?", await joInput2.inputValue());
    await openGroup("Trim");
    await setTime(".trim-time-start", "291.11");
    await setTime(".trim-time-end", "358.79");
    await saveAndDone();
    check("trim restore save completed", true, "291.11/358.79");
  } catch (error) {
    out.harnessError = String(error && error.message || error);
  } finally {
    await browser.close().catch(() => {});
  }
  console.log("RESULT:" + JSON.stringify(out));
})();
