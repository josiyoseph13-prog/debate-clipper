"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");

const base = process.argv[2];
const stage = process.argv[3] || "edit";
const jobId = "job_7422d0f93cd1";
const candidateId = "c_b08dcd6a3b97";
const reviewKey = `${jobId}/${candidateId}`;
const decisionPath = path.join(process.cwd(), "work", jobId, "decisions.json");

const readStoredHeadline = () => {
  const artifact = JSON.parse(fs.readFileSync(decisionPath, "utf8"));
  const rows = artifact.decisions.filter(row => row.candidate_id === candidateId && row.action === "save");
  const row = rows.at(-1);
  return {headline: row?.headline, action: row?.action, time: row?.time, count: rows.length};
};

(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(value => fs.existsSync(value));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [];
    const requests = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("request", request => {
      if (request.url().includes("/api/decisions") && request.method() === "POST") {
        try { requests.push({url: request.url(), payload: request.postDataJSON()}); }
        catch { requests.push({url: request.url(), payloadText: request.postData()}); }
      }
    });
    await page.goto(base);
    await page.locator("#home-view .add-box").waitFor();
    const review = page.locator("#review-view");
    await page.locator(".step[data-view='review']").click();
    const row = review.locator(`.clip-row[data-review-key='${reviewKey}']`);
    try { await row.waitFor({timeout: 10000}); }
    catch (error) {
      console.error("REAL_REVIEW_ROWS", await review.locator(".clip-row").evaluateAll(rows => rows.map(item => item.dataset.reviewKey)));
      throw error;
    }
    await row.click();
    const openEdit = async () => {
      await review.getByRole("button", {name: "Edit", exact: true}).click();
      await review.locator(".edit-headline-field input").waitFor();
      return review.locator(".edit-headline-field input");
    };
    const save = async () => {
      await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
      await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"));
    };
    if (stage === "baseline") {
      const first = await openEdit();
      const before = await first.inputValue();
      await first.fill("TEST HEADLINE 12345");
      await save();
      const stored = readStoredHeadline();
      const reopened = await openEdit();
      const after = await reopened.inputValue();
      assert.notEqual(after, "TEST HEADLINE 12345");
      assert.deepEqual(errors, []);
      console.log(JSON.stringify({stage, before, typed: "TEST HEADLINE 12345", after, stored, requests: requests.map(item => item.payload), errors}));
    } else if (stage === "edit") {
      const first = await openEdit();
      const before = await first.inputValue();
      await first.fill("TEST HEADLINE 12345");
      await save();
      const storedAfterTest = readStoredHeadline();
      const reopenedTest = await openEdit();
      const afterTest = await reopenedTest.inputValue();
      await reopenedTest.fill("");
      await save();
      const storedAfterClear = readStoredHeadline();
      const reopenedClear = await openEdit();
      const afterClear = await reopenedClear.inputValue();
      await reopenedClear.fill("SECOND 678");
      await save();
      const storedAfterSecond = readStoredHeadline();
      const reopenedSecond = await openEdit();
      const afterSecond = await reopenedSecond.inputValue();
      assert.equal(afterTest, "TEST HEADLINE 12345");
      assert.equal(afterClear, "");
      assert.equal(afterSecond, "SECOND 678");
      assert.deepEqual(errors, []);
      console.log(JSON.stringify({stage, before, afterTest, afterClear, afterSecond, storedAfterTest, storedAfterClear, storedAfterSecond, requests: requests.map(item => item.payload), errors}));
    } else {
      const field = await openEdit();
      const afterRestart = await field.inputValue();
      const stored = readStoredHeadline();
      assert.equal(afterRestart, "SECOND 678");
      assert.deepEqual(errors, []);
      console.log(JSON.stringify({stage, afterRestart, stored, requests: requests.map(item => item.payload), errors}));
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
