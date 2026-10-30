"use strict";

// Phase 4C verification in the real Studio UI (2026-10-12), v2 with
// polling waits. Modes: pins1 (build pins), pins2 (persist + delete),
// play (playback switches at a pin). Jo's clip is confirmed by its
// saved headline before any save happens.

const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");
const base = process.argv[2];
const mode = process.argv[3];
const key = "job_7422d0f93cd1/c_b08dcd6a3b97";
const outDir = path.join("work", "deploy_validation", "phase4c_checks");
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
    const until = async (fn, timeout = 20000) => {
      const deadline = Date.now() + timeout;
      let value = await fn().catch(() => null);
      while (!value && Date.now() < deadline) { await sleep(700); value = await fn().catch(() => null); }
      return value;
    };
    const gotoEdit = async () => {
      await page.goto(base, {waitUntil: "domcontentloaded"});
      await page.locator("#home-view .add-box").waitFor({timeout: 30000});
      await page.locator(".step[data-view='review']").click();
      const row = review.locator(`.clip-row[data-review-key='${key}']`);
      await row.waitFor({timeout: 25000});
      await row.click();
      await sleep(700);
      await review.getByRole("button", {name: "Edit", exact: true}).click();
      const input = review.locator(".edit-headline-field input");
      await input.waitFor({timeout: 20000});
      await page.waitForFunction(() => {
        const el = document.querySelector("#review-view .edit-saved-headline");
        return el && el.textContent.startsWith("Saved headline:");
      }, null, {timeout: 20000});
      await sleep(500);
      return input;
    };
    const openFraming = async () => {
      await review.locator(".edit-accordion-trigger", {hasText: "Framing"}).first().click();
      await review.locator(".framing-pin-strip").waitFor({timeout: 15000});
      await sleep(600);
    };
    const header = async () => ((await review.locator(".framing-pin-header").textContent().catch(() => "")) || "").trim();
    const status = async () => ((await review.locator(".framing-save-status").textContent().catch(() => "")) || "").trim();
    const savedOk = () => until(async () => (await status()) === "Saved ✓" ? true : null);
    const dots = async () => await review.locator(".framing-pin-dot").count();
    const seekClip = async t => {
      await page.evaluate(tt => {
        const v = document.querySelector("#review-view .video-shell video");
        const clipLen = 358.79 - 291.11;
        const rel = Number.isFinite(v.duration) && v.duration > 0 && Math.abs(v.duration - clipLen) < 2;
        v.currentTime = rel ? tt : 291.11 + tt;
      }, t);
      await sleep(1300);
    };
    const setZoom = async pct => {
      await page.evaluate(value => {
        const el = document.querySelector(".framing-zoom");
        el.value = String(value);
        el.dispatchEvent(new Event("input", {bubbles: true}));
        el.dispatchEvent(new Event("change", {bubbles: true}));
      }, pct);
    };

    if (mode === "pins1") {
      const input = await gotoEdit();
      check("job gate: jo's headline on the opened record", (await input.inputValue()) === "what is an invasion?", await input.inputValue());
      await openFraming();
      const panelText = await review.locator(".edit-panel").evaluate(el => el.textContent);
      check("no rejected controls in Framing", !/Farther|Show more room|Who should be on screen|How close should it feel|Move the picture/.test(panelText), "");
      check("pin editor present", (await review.locator(".framing-add-pin").count()) === 1 && (await dots()) >= 1 && (await review.locator(".framing-zoom").count()) === 1, await header());
      check("header starts at 0:00 Auto", /Editing pin: 0:00 — Auto/.test(await header()), await header());
      check("safe-area guide visible in shell", (await page.locator(".video-shell .framing-safe-guide").count()) === 1, "");
      check("0:00 pin protected (nudge disabled, no delete)", await review.locator(".framing-nudge-back").isDisabled() && (await review.locator(".framing-delete-pin").count()) === 0, "");
      await setZoom(200);
      check("zoom 200% auto-saved", !!(await savedOk()), await status());
      check("zoom value label 200%", ((await review.locator(".framing-zoom-value").textContent().catch(() => "")) || "").includes("200"), "");
      await seekClip(20);
      await review.locator(".framing-add-pin").click();
      check("pin added at 0:20 — two pins", !!(await until(async () => (await dots()) === 2 ? true : null, 15000)), `dots=${await dots()}`);
      check("header shows new pin at 0:20", !!(await until(async () => /Editing pin: 0:20/.test(await header()) ? true : null, 10000)), await header());
      await review.getByRole("button", {name: "Person A", exact: true}).click();
      check("Person A preset applied (A Close)", !!(await until(async () => /A Close/.test(await header()) ? true : null, 25000)), await header());
      await review.locator(".framing-nudge-fwd").click();
      check("pin nudged to 0:21", !!(await until(async () => /Editing pin: 0:21/.test(await header()) ? true : null, 12000)), await header());
      await review.getByRole("button", {name: "1:1 Square", exact: true}).click();
      const aspect = await until(async () => {
        const a = await page.evaluate(() => document.querySelector(".video-shell").style.aspectRatio);
        return /1 \/ 1/.test(a) ? a : null;
      }, 12000);
      check("shape 1:1 reshapes shell live", !!aspect, String(aspect));
      await review.getByRole("button", {name: "9:16 Vertical", exact: true}).click();
      await sleep(1200);
      const shellBox = await page.locator(".video-shell").boundingBox();
      const dragX = shellBox.x + shellBox.width * .32, dragY = shellBox.y + shellBox.height * .3;
      await page.mouse.move(dragX, dragY);
      await page.mouse.down();
      await page.mouse.move(dragX + 70, dragY + 24, {steps: 8});
      await page.mouse.up();
      check("drag auto-saved", !!(await savedOk()), await status());
      check("drag turned the pin Custom", !!(await until(async () => /Custom/.test(await header()) ? true : null, 10000)), await header());
      await page.screenshot({path: path.join(outDir, "pins1_editor.png")}).catch(() => {});
    }

    if (mode === "pins2") {
      const input = await gotoEdit();
      check("job gate: jo's headline", (await input.inputValue()) === "what is an invasion?", "");
      await openFraming();
      check("pins persisted after reopen (2 dots)", (await dots()) === 2, `dots=${await dots()}`);
      const zoomVal = await page.evaluate(() => document.querySelector(".framing-zoom")?.value);
      check("0:00 pin zoom persisted at 200%", String(zoomVal) === "200", `zoom=${zoomVal}`);
      await review.locator(".framing-pin-dot").nth(1).click();
      check("second pin selected (0:21)", !!(await until(async () => /0:21/.test(await header()) ? true : null, 12000)), await header());
      await review.locator(".framing-delete-pin").click();
      check("pin deleted — one dot left", !!(await until(async () => (await dots()) === 1 ? true : null, 15000)), `dots=${await dots()}`);
      check("delete auto-saved", !!(await savedOk()), await status());
      await page.screenshot({path: path.join(outDir, "pins2_after_delete.png")}).catch(() => {});
    }

    if (mode === "play") {
      const input = await gotoEdit();
      check("job gate: jo's headline", (await input.inputValue()) === "what is an invasion?", "");
      await openFraming();
      // Normalize to a known setup: one pin at 0:00 (zoom 200), then a
      // fresh pin at 0:10 set to zoom 240.
      if ((await dots()) === 2) {
        await review.locator(".framing-pin-dot").nth(1).click();
        await sleep(1000);
        await review.locator(".framing-delete-pin").click();
        await until(async () => (await dots()) === 1 ? true : null, 15000);
      }
      await seekClip(10);
      await review.locator(".framing-add-pin").click();
      await until(async () => (await dots()) === 2 ? true : null, 15000);
      await setZoom(240);
      await savedOk();
      check("two pins for playback test (0:00 @200, 0:10 @240)", (await dots()) === 2, `dots=${await dots()}`);
      const widthAt = async () => page.evaluate(() => document.querySelector("#review-view .video-shell video").style.width);
      const waitWidth = async notEqual => {
        const deadline = Date.now() + 18000;
        let w = await widthAt();
        while (w === notEqual && Date.now() < deadline) { await sleep(600); w = await widthAt(); }
        return w;
      };
      const w0 = await widthAt();
      await seekClip(3);
      const w1 = await waitWidth(w0);
      await seekClip(14);
      const w2 = await waitWidth(w1);
      out.evidence.widths = {before: w0, at3: w1, at14: w2};
      check("preview framing switches across the pin (seek-driven)", w1 !== w2 && parseFloat(w2) > parseFloat(w1), `w(3s)=${w1} w(14s)=${w2}`);
      const played = await page.evaluate(async () => {
        const v = document.querySelector("#review-view .video-shell video");
        v.muted = true;
        const clipLen = 358.79 - 291.11;
        const rel = Number.isFinite(v.duration) && v.duration > 0 && Math.abs(v.duration - clipLen) < 2;
        v.currentTime = rel ? 7 : 291.11 + 7;
        try { await v.play(); } catch { return "play-rejected"; }
        return "playing";
      });
      out.evidence.playState = played;
      if (played === "playing") {
        await page.waitForFunction(() => {
          const v = document.querySelector("#review-view .video-shell video");
          const rel = Number.isFinite(v.duration) && v.duration > 0 && Math.abs(v.duration - 67.68) < 2;
          return v.currentTime > (rel ? 11.5 : 291.11 + 11.5);
        }, null, {timeout: 25000}).catch(() => {});
        const w3 = await waitWidth(w1);
        out.evidence.widthAfterPlayCrossing = w3;
        check("playback crossing the pin switches framing", w3 === w2, `w=${w3} expected ${w2}`);
        await page.evaluate(() => document.querySelector("#review-view .video-shell video").pause());
      }
      await page.screenshot({path: path.join(outDir, "play_switched.png")}).catch(() => {});
    }
  } catch (error) {
    out.harnessError = String(error && error.message || error);
  } finally {
    await browser.close().catch(() => {});
  }
  console.log("RESULT:" + JSON.stringify(out));
})();
