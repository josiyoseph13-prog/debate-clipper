"use strict";

// Phase 4D verification in the real Studio UI (2026-10-12).
// Modes: caps1 (editor controls + persistence), caps2 (playback sync + drag).
// Headless Chromium cannot load the 822 MB source, so after opening Edit
// the trace points the player at the app's own proxy media (the same
// media Review uses); the exported-file rule is checked separately in
// caps2 by loading the /clip media on purpose.
// Jo's clip is confirmed by its saved headline before any save happens.

const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");
const base = process.argv[2];
const mode = process.argv[3];
const key = "job_7422d0f93cd1/c_b08dcd6a3b97";
const outDir = path.join("work", "deploy_validation", "phase4d_checks");
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
    const until = async (fn, timeout = 25000) => {
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
      // Drive the app's proxy media (headless cannot load the 822 MB source).
      await page.evaluate(() => {
        const v = document.querySelector("#review-view .video-shell video");
        if (v && !v.currentSrc.includes("/proxy")) {
          v.src = v.currentSrc.replace(/\/(source|clip)([?#]|$)/, "/proxy$2");
        }
      });
      await sleep(1500);
      return input;
    };
    const openCaptions = async () => {
      await review.locator(".edit-accordion-trigger", {hasText: "Captions"}).first().click();
      await review.locator(".caption-toggle").waitFor({timeout: 15000});
      await sleep(400);
    };
    const seekClip = async t => {
      await page.evaluate(tt => {
        const v = document.querySelector("#review-view .video-shell video");
        const clipLen = 358.79 - 291.11;
        const rel = Number.isFinite(v.duration) && v.duration > 0 && Math.abs(v.duration - clipLen) < 2;
        v.currentTime = rel ? tt : 291.11 + tt;
      }, t);
      await sleep(1200);
    };
    const overlayInfo = () => page.evaluate(() => {
      const el = document.querySelector("#review-view .caption-preview");
      if (!el) return null;
      const shell = el.parentElement;
      const active = el.querySelector(".caption-word-active");
      return {
        display: el.style.display,
        text: el.textContent,
        topPct: parseFloat(el.style.top),
        fontPx: parseFloat(el.style.fontSize),
        look: el.dataset.look,
        activeText: active ? active.textContent : "",
        activeColor: active ? active.style.color : "",
        shellH: shell ? shell.clientHeight : 0,
      };
    });
    const noteText = async () => ((await review.locator(".caption-cue-note").first().textContent().catch(() => "")) || "").trim();
    const cuesReady = () => until(async () => {
      const note = await noteText();
      return note.includes("exactly as Export") ? note : null;
    });

    if (mode === "caps1") {
      const input = await gotoEdit();
      check("job gate: jo's headline on the opened record", (await input.inputValue()) === "what is an invasion?", await input.inputValue());
      await openCaptions();
      check("captions toggle present, starts on", (await review.locator(".caption-toggle").textContent()).includes("Captions on"));
      check("size slider present", await review.locator(".caption-size-slider").count() === 1);
      check("old size buttons absent", (await review.locator(".edit-accordion-body").getByRole("button", {name: "Smaller"}).count()) === 0 && (await review.locator(".edit-accordion-body").getByRole("button", {name: "Bigger"}).count()) === 0);
      check("four colour swatches", await review.locator(".caption-swatch").count() === 4, await review.locator(".caption-swatch").count());
      const note = await cuesReady();
      check("cues loaded from the clip's own words", !!note, note || await noteText());
      await seekClip(0.3);
      const atStart = await until(async () => { const info = await overlayInfo(); return info && info.display !== "none" && info.activeText ? info : null; });
      check("overlay shows the current word at 0.3s", !!atStart, JSON.stringify(atStart));
      if (atStart) {
        check("active word is OKAY (the clip's first word)", atStart.activeText === "OKAY", atStart.activeText);
        check("default highlight is green", atStart.activeColor === "rgb(180, 248, 61)", atStart.activeColor);
        check("default position is the middle slot (~57.9%)", atStart.topPct > 54 && atStart.topPct < 62, atStart.topPct);
        check("look starts at Bold (hormozi_glow)", atStart.look === "hormozi_glow", atStart.look);
      }
      await page.screenshot({path: path.join(outDir, "caps1_bold.png")});
      // Yellow swatch recolours only the spoken word.
      await review.locator(".caption-swatch[data-color='#FFE14D']").click();
      await sleep(500);
      const yellow = await overlayInfo();
      check("yellow swatch recolours the active word", yellow && yellow.activeColor === "rgb(255, 225, 77)", yellow && yellow.activeColor);
      const otherColors = await page.evaluate(() => [...document.querySelectorAll("#review-view .caption-preview .caption-word")].filter(s => !s.classList.contains("caption-word-active")).map(s => s.style.color));
      check("other words stay base white", otherColors.length > 0 && otherColors.every(c => c === "rgb(255, 255, 255)"), otherColors.join(","));
      // Size slider resizes live.
      const before = await overlayInfo();
      await page.evaluate(() => {
        const el = document.querySelector(".caption-size-slider");
        el.value = "30";
        el.dispatchEvent(new Event("input", {bubbles: true}));
      });
      await sleep(500);
      const bigger = await overlayInfo();
      check("slider at 30 shows 127%", (await review.locator(".caption-size-value").textContent()).trim() === "127%", await review.locator(".caption-size-value").textContent());
      check("captions grow live with the slider", before && bigger && bigger.fontPx > before.fontPx * 1.15, `${before && before.fontPx} -> ${bigger && bigger.fontPx}`);
      // Position presets.
      await review.locator(".caption-position", {hasText: "Bottom"}).click();
      await sleep(600);
      const bottom = await overlayInfo();
      check("Bottom moves captions to ~73.5%", bottom && bottom.topPct > 69 && bottom.topPct < 78, bottom && bottom.topPct);
      await review.locator(".caption-position", {hasText: "Top"}).click();
      await sleep(600);
      const top = await overlayInfo();
      check("Top moves captions to ~42.3%", top && top.topPct > 38 && top.topPct < 47, top && top.topPct);
      await review.locator(".caption-position", {hasText: "Middle"}).click();
      await sleep(600);
      // Light look: no glow on the active word.
      await review.locator(".caption-look[data-look='karaoke_lite']").click();
      const lightSwitched = await until(async () => { const info = await overlayInfo(); return info && info.look === "karaoke_lite" ? info : null; }, 30000);
      check("Light look actually switches the preview", !!lightSwitched, lightSwitched && lightSwitched.look);
      await seekClip(0.3);
      const light = await until(async () => { const info = await overlayInfo(); return info && info.display !== "none" && info.activeText ? info : null; });
      check("Light look loads and shows words", !!light, JSON.stringify(light));
      if (light) {
        const glow = await page.evaluate(() => document.querySelector("#review-view .caption-preview .caption-word-active")?.style.textShadow || "");
        check("Light look has no glow", glow === "" || glow === "none", glow);
      }
      // Calm look: sentence case, no coloured active word.
      await review.locator(".caption-look[data-look='gravitas']").click();
      const calmSwitched = await until(async () => { const info = await overlayInfo(); return info && info.look === "gravitas" ? info : null; }, 30000);
      check("Calm look actually switches the preview", !!calmSwitched, calmSwitched && calmSwitched.look);
      await seekClip(0.3);
      const calm = await until(async () => { const info = await overlayInfo(); return info && info.display !== "none" && info.text.length > 3 ? info : null; });
      check("Calm look shows the sentence", !!calm, JSON.stringify(calm));
      if (calm) {
        check("Calm text keeps sentence case (not all caps)", calm.text !== calm.text.toUpperCase(), calm.text.slice(0, 60));
        const calmColors = await page.evaluate(() => [...document.querySelectorAll("#review-view .caption-preview .caption-word")].map(s => s.style.color));
        check("Calm colours every word base white", calmColors.length > 0 && calmColors.every(c => c === "rgb(255, 255, 255)"), calmColors.slice(0, 3).join(","));
      }
      await page.screenshot({path: path.join(outDir, "caps1_calm.png")});
      // Back to Bold for the persistence check, then off/on.
      await review.locator(".caption-look[data-look='hormozi_glow']").click();
      const boldBack = await until(async () => { const info = await overlayInfo(); return info && info.look === "hormozi_glow" ? info : null; }, 30000);
      check("Bold look switches back", !!boldBack, boldBack && boldBack.look);
      await review.locator(".caption-toggle").click();
      await sleep(600);
      const offInfo = await overlayInfo();
      check("captions off hides the overlay", offInfo && offInfo.display === "none", JSON.stringify(offInfo));
      check("off note explains the export", (await noteText()).includes("export will have no captions"), await noteText());
      await review.locator(".caption-toggle").click();
      await sleep(600);
      check("captions back on restores the editor", await review.locator(".caption-size-slider").count() === 1);
      // Save & Done, reopen: yellow + size 30 + Bold must persist.
      await review.locator(".edit-panel .done-button").first().click();
      await sleep(2500);
      const input2 = await gotoEdit();
      check("reopen: still jo's clip", (await input2.inputValue()) === "what is an invasion?", await input2.inputValue());
      await openCaptions();
      await cuesReady();
      check("persisted: yellow swatch active", await review.locator(".caption-swatch.active[data-color='#FFE14D']").count() === 1);
      check("persisted: size slider at 30 (127%)", (await review.locator(".caption-size-slider").inputValue()) === "30" && (await review.locator(".caption-size-value").textContent()).trim() === "127%");
      check("persisted: Bold look active", await review.locator(".caption-look.active[data-look='hormozi_glow']").count() === 1);
      check("persisted: Middle position active", await review.locator(".caption-position.active", {hasText: "Middle"}).count() === 1);
      await seekClip(0.3);
      const again = await until(async () => { const info = await overlayInfo(); return info && info.display !== "none" && info.activeText ? info : null; });
      check("persisted settings drive the reopened preview", !!again && again.activeColor === "rgb(255, 225, 77)", JSON.stringify(again));
    }

    if (mode === "caps2") {
      const input = await gotoEdit();
      check("job gate: jo's headline", (await input.inputValue()) === "what is an invasion?", await input.inputValue());
      await openCaptions();
      const note = await cuesReady();
      check("cues loaded", !!note, note || await noteText());
      // Playback sync: play muted and watch the active word change.
      await page.evaluate(() => {
        const v = document.querySelector("#review-view .video-shell video");
        v.muted = true;
        const clipLen = 358.79 - 291.11;
        const rel = Number.isFinite(v.duration) && Math.abs(v.duration - clipLen) < 2;
        v.currentTime = rel ? 0 : 291.11;
        v.play().catch(() => {});
      });
      const seen = new Set();
      const deadline = Date.now() + 12000;
      while (Date.now() < deadline && seen.size < 3) {
        const info = await overlayInfo().catch(() => null);
        if (info && info.activeText) seen.add(info.activeText);
        await sleep(300);
      }
      check("active word follows playback (3+ distinct words)", seen.size >= 3, [...seen].join(" | "));
      await page.evaluate(() => document.querySelector("#review-view .video-shell video")?.pause());
      // Drag the words down: top% must grow.
      await seekClip(0.3);
      const before = await until(async () => { const info = await overlayInfo(); return info && info.display !== "none" ? info : null; });
      check("overlay visible before drag", !!before, JSON.stringify(before));
      if (before) {
        const box = await page.evaluate(() => {
          const el = document.querySelector("#review-view .caption-preview");
          const r = el.getBoundingClientRect();
          return {x: r.x + r.width / 2, y: r.y + r.height / 2};
        });
        await page.mouse.move(box.x, box.y);
        await page.mouse.down();
        await page.mouse.move(box.x, box.y + 80, {steps: 8});
        await page.mouse.up();
        await sleep(800);
        const after = await overlayInfo();
        check("dragging the words moves them down", after && after.topPct > before.topPct + 3, `${before.topPct} -> ${after && after.topPct}`);
        await page.screenshot({path: path.join(outDir, "caps2_dragged.png")});
      }
      // Exported-file rule: point the player at the /clip media (the
      // rendered export) and the overlay must stay hidden.
      await page.evaluate(() => {
        const v = document.querySelector("#review-view .video-shell video");
        v.src = v.currentSrc.replace(/\/(source|proxy)([?#]|$)/, "/clip$2");
      });
      await sleep(2500);
      await page.evaluate(() => { const v = document.querySelector("#review-view .video-shell video"); if (v) v.currentTime = 0.3; });
      await sleep(1200);
      const onExport = await overlayInfo();
      check("no overlay over the finished export", onExport && onExport.display === "none", JSON.stringify(onExport));
      check("export-media note explains baked-in captions", (await noteText()).includes("baked into the picture"), await noteText());
    }

    out.passed = out.checks.filter(c => c.pass).length;
    out.total = out.checks.length;
  } catch (error) {
    out.fatal = String(error && error.stack || error);
  } finally {
    fs.writeFileSync(path.join(outDir, `trace_${mode}.json`), JSON.stringify(out, null, 2));
    await browser.close();
    console.log(JSON.stringify({mode: out.mode, passed: out.passed, total: out.total, errors: out.errors, fatal: out.fatal || null}));
  }
})();
