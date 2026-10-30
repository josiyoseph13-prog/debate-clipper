"use strict";

// Pax Phase 4B checks 4-7 + Phase 4A parked retests R1/R2.
// Modes: c1 | c2 | c3 | b | restore | r1 | r2
// Drives jo's real Studio UI (headless Chromium on the PC) against the
// test clip c_b08dcd6a3b97 in job_7422d0f93cd1. Soft assertions: every
// mode prints a RESULT JSON with per-check pass/fail + raw evidence.

const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");

const base = process.argv[2];
const mode = process.argv[3];
const sizeArg = process.argv[4] || "1440x1000";
const [vw, vh] = sizeArg.split("x").map(Number);
const jobId = "job_7422d0f93cd1";
const candidateId = "c_b08dcd6a3b97";
const reviewKey = `${jobId}/${candidateId}`;
const outDir = path.join("work", "deploy_validation", "phase4b_checks");
fs.mkdirSync(outDir, {recursive: true});

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(v => fs.existsSync(v));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  const out = {mode, viewport: sizeArg, checks: [], evidence: {}, errors: []};
  const check = (name, pass, detail) => out.checks.push({name, pass: !!pass, detail: String(detail ?? "")});
  try {
    const page = await browser.newPage({viewport: {width: vw, height: vh}});
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
      const trigger = review.locator(".edit-accordion-trigger", {hasText: label}).first();
      await trigger.waitFor({timeout: 10000});
      await trigger.click();
      await sleep(600);
    };
    const saveAndDone = async () => {
      await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
      try {
        await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"), null, {timeout: 15000});
        return {saved: true, message: ""};
      } catch {
        const status = await review.locator(".edit-save-status").textContent().catch(() => "");
        const trimErr = await review.locator(".trim-error").textContent().catch(() => "");
        return {saved: false, message: (status || trimErr || "").trim()};
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
      await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"), null, {timeout: 10000}).catch(() => {});
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

    if (mode === "c1") {
      await gotoReview(reviewKey);
      await openEdit();
      await openGroup("Trim");
      const tv = await trimValues();
      out.evidence.trim = tv;
      check("trim group visible with controls", tv.start !== null && tv.end !== null, JSON.stringify(tv));
      check("start = 291.11", tv.start === "291.11", `start=${tv.start}`);
      check("end = 358.79", tv.end === "358.79", `end=${tv.end}`);
      check("summary length 1:08 (67.68s)", /Current length: 1:08/.test(tv.summary || ""), tv.summary);
      await shot("c1_trim.png");
      await cancelClose();
      check("edit closed without saving", await page.locator("#review-view .edit-panel").count() === 0, "");
    }

    if (mode === "c2") {
      await gotoReview(reviewKey);
      await openEdit();
      await openGroup("Trim");
      const before = await trimValues();
      out.evidence.before = before;
      await setTime(".trim-time-start", "299.27");
      await setTime(".trim-time-end", "349.59");
      const edited = await trimValues();
      out.evidence.edited = edited;
      check("summary updates to 0:50 (50.32s)", /Current length: 0:50/.test(edited.summary || ""), edited.summary);
      await shot("c2_before_save.png");
      const res = await saveAndDone();
      out.evidence.save = res;
      check("save accepted (no word-boundary refusal)", res.saved, res.message);
      if (res.saved) {
        await openEdit();
        await openGroup("Trim");
        const after = await trimValues();
        out.evidence.afterReopen = after;
        check("reopened start = 299.27", after.start === "299.27", `start=${after.start}`);
        check("reopened end = 349.59", after.end === "349.59", `end=${after.end}`);
        check("reopened length 0:50", /Current length: 0:50/.test(after.summary || ""), after.summary);
        const headline = await review.locator(".edit-headline-field input").inputValue();
        out.evidence.headlineAfterTrimSave = headline;
        check("headline untouched by trim save", headline === "what is an invasion?", headline);
        await shot("c2_reopen.png");
        await cancelClose();
      }
    }

    if (mode === "c3") {
      await gotoReview(reviewKey);
      await openEdit();
      await openGroup("Trim");
      const before = await trimValues();
      out.evidence.before = before;
      await setTime(".trim-time-start", "400.00");
      const afterInvalid = await trimValues();
      out.evidence.afterInvalid = afterInvalid;
      check("plain-words refusal shown", /Start must be before end/.test(afterInvalid.error || ""), afterInvalid.error);
      check("length unchanged after invalid entry", afterInvalid.summary === before.summary, `before='${before.summary}' after='${afterInvalid.summary}'`);
      await shot("c3_error.png");
      const res = await saveAndDone();
      out.evidence.save = res;
      check("save completes (good values only)", res.saved, res.message);
      if (res.saved) {
        await openEdit();
        await openGroup("Trim");
        const after = await trimValues();
        out.evidence.afterReopen = after;
        check("good trim intact: start", after.start === before.start, `start=${after.start} expected=${before.start}`);
        check("good trim intact: end", after.end === before.end, `end=${after.end} expected=${before.end}`);
        await shot("c3_reopen.png");
        await cancelClose();
      }
    }

    if (mode === "b") {
      await gotoReview(reviewKey);
      const input = await openEdit();
      const beforeVal = await input.inputValue();
      const beforeLine = (await review.locator(".edit-saved-headline").textContent())?.trim();
      out.evidence.before = {field: beforeVal, line: beforeLine};
      check("precondition: saved headline present", beforeVal === "what is an invasion?", beforeVal);
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
        check("reopened saved line empty", /Saved headline: \(empty\)/.test(afterLine || ""), afterLine);
        await shot("b_edit_reopen.png");
        await cancelClose();
      }
    }

    if (mode === "restore") {
      await gotoReview(reviewKey);
      const input = await openEdit();
      await input.click();
      await page.keyboard.press("Control+A");
      await page.keyboard.type("what is an invasion?");
      await sleep(300);
      await openGroup("Trim");
      await setTime(".trim-time-start", "291.11");
      await setTime(".trim-time-end", "358.79");
      const res = await saveAndDone();
      out.evidence.save = res;
      check("restore save accepted", res.saved, res.message);
      if (res.saved) {
        const input2 = await openEdit();
        const hv = await input2.inputValue();
        await openGroup("Trim");
        const tv = await trimValues();
        out.evidence.restored = {headline: hv, trim: tv};
        check("headline restored", hv === "what is an invasion?", hv);
        check("trim restored", tv.start === "291.11" && tv.end === "358.79", JSON.stringify(tv));
        await shot("restore.png");
        await cancelClose();
      }
    }

    if (mode === "r1") {
      await gotoReview(reviewKey);
      const dump = async scope => page.evaluate(sel => {
        const root = document.querySelector(sel);
        if (!root) return [];
        const els = [...root.querySelectorAll("button, input[type='range'], [role='button']")];
        return els.filter(el => {
          const r = el.getBoundingClientRect();
          const s = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
        }).map(el => {
          const r = el.getBoundingClientRect();
          return {text: (el.textContent || el.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim().slice(0, 40), cls: el.className.toString().slice(0, 60), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), bottom: Math.round(r.bottom)};
        });
      }, scope);
      const overlaps = list => {
        const pairs = [];
        for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
          const a = list[i], b = list[j];
          const ox = Math.min(a.right, b.right) - Math.max(a.x, b.x);
          const oy = Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y);
          if (ox > 2 && oy > 2) pairs.push(`${a.text || a.cls} <-> ${b.text || b.cls} (${ox}x${oy})`);
        }
        return pairs;
      };
      const stageControls = await dump("#review-view .review-stage");
      const actionControls = await dump("#review-view .review-actions");
      out.evidence.stageControls = stageControls;
      out.evidence.actionControls = actionControls;
      const ov = [...overlaps(stageControls), ...overlaps(actionControls)];
      out.evidence.overlaps = ov;
      check("no overlapping controls in Review stage/actions", ov.length === 0, ov.join(" | ") || "none");
      const cutOff = [...stageControls, ...actionControls].filter(c => c.right > vw + 1 || c.x < -1);
      check("no control cut off at viewport edge", cutOff.length === 0, JSON.stringify(cutOff));
      await shot("r1_review.png");
      await openEdit();
      await sleep(500);
      const editControls = await dump("#review-view .review-stage");
      out.evidence.editStageControls = editControls;
      const ov2 = overlaps(editControls);
      out.evidence.editOverlaps = ov2;
      check("no overlapping controls in Edit playback", ov2.length === 0, ov2.join(" | ") || "none");
      await shot("r1_edit.png");
      await cancelClose();
    }

    if (mode === "r2") {
      await gotoReview(reviewKey);
      await openEdit();
      const probe = () => page.evaluate(() => {
        const panel = document.querySelector("#review-view .edit-panel");
        let scroller = panel;
        let el = panel;
        while (el && el !== document.body) {
          const s = getComputedStyle(el);
          if ((s.overflowY === "auto" || s.overflowY === "scroll") && el.scrollHeight > el.clientHeight + 4) { scroller = el; break; }
          el = el.parentElement;
        }
        return {scrollerClass: scroller.className.toString(), scrollTop: scroller.scrollTop, scrollHeight: scroller.scrollHeight, clientHeight: scroller.clientHeight};
      });
      const triggerState = label => page.evaluate(lbl => {
        const panel = document.querySelector("#review-view .edit-panel");
        let scroller = panel, el = panel;
        while (el && el !== document.body) {
          const s = getComputedStyle(el);
          if ((s.overflowY === "auto" || s.overflowY === "scroll") && el.scrollHeight > el.clientHeight + 4) { scroller = el; break; }
          el = el.parentElement;
        }
        const trig = [...document.querySelectorAll("#review-view .edit-accordion-trigger")].find(t => t.textContent.includes(lbl));
        if (!trig) return {found: false};
        const tr = trig.getBoundingClientRect(), sr = scroller.getBoundingClientRect();
        return {found: true, scrollTop: scroller.scrollTop, triggerTop: Math.round(tr.top), scrollerTop: Math.round(sr.top), scrollerBottom: Math.round(sr.bottom), inView: tr.top >= sr.top - 2 && tr.bottom <= sr.bottom + 2};
      }, label);
      const scrollBottom = () => page.evaluate(() => {
        const panel = document.querySelector("#review-view .edit-panel");
        let scroller = panel, el = panel;
        while (el && el !== document.body) {
          const s = getComputedStyle(el);
          if ((s.overflowY === "auto" || s.overflowY === "scroll") && el.scrollHeight > el.clientHeight + 4) { scroller = el; break; }
          el = el.parentElement;
        }
        scroller.scrollTop = scroller.scrollHeight;
      });
      const p0 = await probe();
      out.evidence.scroller = p0;
      check("panel actually scrolls at this viewport", p0.scrollHeight > p0.clientHeight + 4, JSON.stringify(p0));
      for (const label of ["Captions", "Trim", "Framing"]) {
        await scrollBottom();
        await sleep(300);
        const beforeSt = await triggerState(label);
        await openGroup(label);
        const afterSt = await triggerState(label);
        out.evidence[label] = {before: beforeSt, after: afterSt};
        check(`${label}: opened group stays in view (no jump to top)`, afterSt.inView === true && afterSt.scrollTop > 0, JSON.stringify(afterSt));
        await shot(`r2_${label.toLowerCase()}.png`);
      }
      await cancelClose();
    }
  } catch (error) {
    out.harnessError = String(error && error.message || error);
  } finally {
    await browser.close().catch(() => {});
  }
  console.log("RESULT:" + JSON.stringify(out));
})();
