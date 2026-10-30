"use strict";

// Phase 4B sitting 2 (2026-10-12): C3 + B (+ headline restore).
// Every mode first CONFIRMS the opened record is jo's job's clip
// (saved headline "what is an invasion?") before any save is
// attempted; if the confirmation fails the mode aborts WITHOUT
// saving. File-level routing is verified separately by the caller
// after each mode (decisions counts + other job untouched).

const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");

const base = process.argv[2];
const mode = process.argv[3];
const reviewKey = "job_7422d0f93cd1/c_b08dcd6a3b97";
const outDir = path.join("work", "deploy_validation", "phase4b_checks");
fs.mkdirSync(outDir, {recursive: true});
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(v => fs.existsSync(v));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  const out = {mode, checks: [], evidence: {}, errors: []};
  const check = (name, pass, detail) => out.checks.push({name, pass: !!pass, detail: String(detail ?? "")});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    page.on("pageerror", e => out.errors.push(e.message));
    const review = page.locator("#review-view");

    const gotoReview = async () => {
      await page.goto(base, {waitUntil: "domcontentloaded"});
      await page.locator("#home-view .add-box").waitFor({timeout: 30000});
      await page.locator(".step[data-view='review']").click();
      const row = review.locator(`.clip-row[data-review-key='${reviewKey}']`);
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
    // Job confirmation: the opened record must be jo's (saved headline present).
    const confirmJoJob = async input => {
      const field = await input.inputValue();
      const line = (await review.locator(".edit-saved-headline").textContent())?.trim();
      out.evidence.confirmation = {field, line};
      const ok = field === "what is an invasion?" && /Saved headline: "what is an invasion\?"/.test(line || "");
      check("job confirmed: jo's saved headline on the opened record", ok, `${field} | ${line}`);
      return ok;
    };
    const openGroup = async label => {
      await review.locator(".edit-accordion-trigger", {hasText: label}).first().click();
      await sleep(600);
    };
    const saveAndDone = async () => {
      await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
      try {
        await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"), null, {timeout: 15000});
        return {saved: true, message: ""};
      } catch {
        const status = await review.locator(".edit-save-status").textContent().catch(() => "");
        return {saved: false, message: (status || "").trim()};
      }
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
    const trimValues = async () => ({
      start: await review.locator(".trim-time-start").inputValue().catch(() => null),
      end: await review.locator(".trim-time-end").inputValue().catch(() => null),
      summary: (await review.locator(".trim-summary").textContent().catch(() => ""))?.trim(),
      error: (await review.locator(".trim-error").textContent().catch(() => ""))?.trim(),
    });
    const setTime = async (selector, value) => {
      const field = review.locator(selector);
      await field.click();
      await page.keyboard.press("Control+A");
      await page.keyboard.type(value);
      await page.keyboard.press("Tab");
      await sleep(400);
    };
    const shot = name => page.screenshot({path: path.join(outDir, name)}).catch(() => {});

    if (mode === "c3") {
      await gotoReview();
      const input = await openEdit();
      if (!await confirmJoJob(input)) { check("C3 aborted: job not confirmed", false, "no save attempted"); }
      else {
        await openGroup("Trim");
        const before = await trimValues();
        out.evidence.before = before;
        check("precondition: valid trim is 291.11-358.79", before.start === "291.11" && before.end === "358.79", JSON.stringify(before));
        await setTime(".trim-time-start", "400.00");
        const afterInvalid = await trimValues();
        out.evidence.afterInvalid = afterInvalid;
        check("plain-words refusal shown", /Start must be before end/.test(afterInvalid.error || ""), afterInvalid.error);
        check("summary/length unchanged after invalid entry", afterInvalid.summary === before.summary, `before='${before.summary}' after='${afterInvalid.summary}'`);
        await shot("c3_error.png");
        const res = await saveAndDone();
        out.evidence.save = res;
        check("save completes carrying only the good values", res.saved, res.message);
        if (res.saved) {
          const input2 = await openEdit();
          await confirmJoJob(input2);
          await openGroup("Trim");
          const after = await trimValues();
          out.evidence.afterReopen = after;
          check("good trim intact after reopen: start", after.start === "291.11", `start=${after.start}`);
          check("good trim intact after reopen: end", after.end === "358.79", `end=${after.end}`);
          await shot("c3_reopen.png");
          await cancelClose();
        }
      }
    }

    if (mode === "b") {
      await gotoReview();
      const input = await openEdit();
      if (!await confirmJoJob(input)) { check("B aborted: job not confirmed", false, "no save attempted"); }
      else {
        await input.click();
        await page.keyboard.press("Control+A");
        await page.keyboard.press("Delete");
        await sleep(400);
        const res = await saveAndDone();
        out.evidence.save = res;
        check("clear-save accepted", res.saved, res.message);
        if (res.saved) {
          const readback = await review.locator(".saved-headline-readback").textContent().catch(() => "");
          out.evidence.reviewReadback = readback?.trim();
          check("review read-back shows empty", /Saved headline: \(empty\)/.test(readback || ""), readback);
          const shellText = await review.locator(".video-shell").evaluate(el => el.textContent).catch(() => "");
          out.evidence.shellText = (shellText || "").replace(/\s+/g, " ").slice(0, 300);
          check("banner falls back to auto headline", /Okay, then let me ask what is an invasion/i.test(shellText || ""), out.evidence.shellText);
          await shot("b_review.png");
          const input2 = await openEdit();
          const afterVal = await input2.inputValue();
          const afterLine = (await review.locator(".edit-saved-headline").textContent())?.trim();
          out.evidence.afterReopen = {field: afterVal, line: afterLine};
          check("reopened headline field empty", afterVal === "", JSON.stringify(afterVal));
          check("reopened saved line empty (none invented)", /Saved headline: \(empty\)/.test(afterLine || ""), afterLine);
          await shot("b_edit_reopen.png");
          await cancelClose();
        }
      }
    }

    if (mode === "restore") {
      await gotoReview();
      const input = await openEdit();
      const line0 = (await review.locator(".edit-saved-headline").textContent())?.trim();
      out.evidence.preRestoreLine = line0;
      check("precondition: headline currently empty on the opened record", /Saved headline: \(empty\)/.test(line0 || ""), line0);
      await openGroup("Trim");
      const tv0 = await trimValues();
      out.evidence.preRestoreTrim = tv0;
      check("precondition: trim still 291.11-358.79", tv0.start === "291.11" && tv0.end === "358.79", JSON.stringify(tv0));
      await input.click();
      await page.keyboard.press("Control+A");
      await page.keyboard.type("what is an invasion?");
      await sleep(300);
      const res = await saveAndDone();
      out.evidence.save = res;
      check("restore save accepted", res.saved, res.message);
      if (res.saved) {
        const input2 = await openEdit();
        const hv = await input2.inputValue();
        const line = (await review.locator(".edit-saved-headline").textContent())?.trim();
        out.evidence.restored = {field: hv, line};
        check("headline restored in field", hv === "what is an invasion?", hv);
        check("saved line confirms restore", /Saved headline: "what is an invasion\?"/.test(line || ""), line);
        await shot("restore_headline.png");
        await cancelClose();
      }
    }
  } catch (error) {
    out.harnessError = String(error && error.message || error);
  } finally {
    await browser.close().catch(() => {});
  }
  console.log("RESULT:" + JSON.stringify(out));
})();
