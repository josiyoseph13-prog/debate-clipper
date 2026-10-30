"use strict";

// Pax Phase 4B FIX2 acceptance trace.
// Modes: main | restartcheck | restore
// - main: clip1 full sequence with FULL PAGE RELOADS + read-back line checks,
//   then a second existing clip test (restored afterwards). Clip1 ends at SECOND 678.
// - restartcheck: after a server restart, clip1 reopened headline must be SECOND 678.
// - restore: clip1 headline cleared back to today's starting state (empty) and verified after reload.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const {chromium} = require("playwright");

const base = process.argv[2];
const mode = process.argv[3] || "main";
const jobId = "job_7422d0f93cd1";
const candidateId = "c_b08dcd6a3b97";
const reviewKey = `${jobId}/${candidateId}`;

(async () => {
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(value => fs.existsSync(value));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  const out = {mode, steps: [], errors: []};
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    page.on("pageerror", error => out.errors.push(error.message));
    const review = page.locator("#review-view");

    const gotoReview = async key => {
      await page.goto(base);
      await page.locator("#home-view .add-box").waitFor({timeout: 20000});
      await page.locator(".step[data-view='review']").click();
      const row = review.locator(`.clip-row[data-review-key='${key}']`);
      await row.waitFor({timeout: 15000});
      await row.click();
    };
    const reloadToClip = async key => {
      await page.reload();
      await page.locator("#home-view .add-box").waitFor({timeout: 20000});
      await page.locator(".step[data-view='review']").click();
      const row = review.locator(`.clip-row[data-review-key='${key}']`);
      await row.waitFor({timeout: 15000});
      await row.click();
    };
    const openEdit = async () => {
      await review.getByRole("button", {name: "Edit", exact: true}).click();
      const input = review.locator(".edit-headline-field input");
      await input.waitFor({timeout: 15000});
      await page.waitForFunction(() => {
        const el = document.querySelector("#review-view .edit-saved-headline");
        return el && (el.textContent.startsWith("Saved headline:") || el.textContent.startsWith("Could not load"));
      }, null, {timeout: 15000});
      return input;
    };
    const panelLine = () => review.locator(".edit-saved-headline").textContent();
    const saveAndReadback = async () => {
      await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
      await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"), null, {timeout: 15000});
      const line = review.locator(".saved-headline-readback");
      await line.waitFor({timeout: 10000});
      return (await line.textContent()).trim();
    };
    const apiHeadline = async key => {
      const [job, cand] = key.split("/");
      const resp = await page.request.get(`${base}/api/candidates/${job}/${cand}`);
      const data = await resp.json();
      return data.decision && Object.prototype.hasOwnProperty.call(data.decision, "headline") ? data.decision.headline : null;
    };

    if (mode === "main") {
      await gotoReview(reviewKey);
      // 1. Open: fresh-from-server line + field show today's stored value (empty)
      let input = await openEdit();
      out.steps.push({step: "open_initial_panel_line", value: await panelLine()});
      assert.equal(await panelLine(), "Saved headline: (empty)");
      assert.equal(await input.inputValue(), "");
      // 2. Type TEST HEADLINE 12345 -> Save & Done -> read-back line on Review
      await input.fill("TEST HEADLINE 12345");
      const rb1 = await saveAndReadback();
      out.steps.push({step: "readback_after_test_headline", value: rb1});
      assert.equal(rb1, 'Saved headline: "TEST HEADLINE 12345"');
      // 3. FULL PAGE RELOAD -> reopen -> field from server
      await reloadToClip(reviewKey);
      input = await openEdit();
      assert.equal(await input.inputValue(), "TEST HEADLINE 12345");
      assert.equal(await panelLine(), 'Saved headline: "TEST HEADLINE 12345"');
      out.steps.push({step: "after_reload_test_headline", value: "TEST HEADLINE 12345"});
      // 4. Clear -> save -> read-back (empty) -> reload -> reopen -> still empty
      await input.fill("");
      const rb2 = await saveAndReadback();
      assert.equal(rb2, "Saved headline: (empty)");
      await reloadToClip(reviewKey);
      input = await openEdit();
      assert.equal(await input.inputValue(), "");
      assert.equal(await panelLine(), "Saved headline: (empty)");
      out.steps.push({step: "clear_stays_empty_after_reload", value: ""});
      // 5. SECOND 678 -> save -> reload -> reopen
      await input.fill("SECOND 678");
      const rb3 = await saveAndReadback();
      assert.equal(rb3, 'Saved headline: "SECOND 678"');
      await reloadToClip(reviewKey);
      input = await openEdit();
      assert.equal(await input.inputValue(), "SECOND 678");
      out.steps.push({step: "second_678_after_reload", value: "SECOND 678"});
      // Close edit without changes: Cancel (not dirty -> closes)
      await review.getByRole("button", {name: "Cancel Edit", exact: true}).first().click();
      await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"), null, {timeout: 10000});

      // 6. Second existing clip (one that already has a saved headline string)
      const keys = await review.locator(".clip-row").evaluateAll(rows => rows.map(item => item.dataset.reviewKey));
      let clip2 = null;
      for (const key of keys) {
        if (key === reviewKey) continue;
        const headline = await apiHeadline(key);
        if (typeof headline === "string") { clip2 = {key, headline}; break; }
      }
      if (clip2) {
        await reloadToClip(clip2.key);
        let input2 = await openEdit();
        assert.equal(await input2.inputValue(), clip2.headline);
        await input2.fill("PAX CLIP2 999");
        const rbc = await saveAndReadback();
        assert.equal(rbc, 'Saved headline: "PAX CLIP2 999"');
        await reloadToClip(clip2.key);
        input2 = await openEdit();
        assert.equal(await input2.inputValue(), "PAX CLIP2 999");
        await input2.fill(clip2.headline);
        const rbr = await saveAndReadback();
        assert.equal(rbr, clip2.headline ? `Saved headline: "${clip2.headline}"` : "Saved headline: (empty)");
        out.steps.push({step: "second_clip_test_and_restore", key: clip2.key, initial: clip2.headline, afterReload: "PAX CLIP2 999", restored: true});
      } else {
        out.steps.push({step: "second_clip", value: "no other clip with a saved headline string was available"});
      }
    } else if (mode === "restartcheck") {
      await gotoReview(reviewKey);
      const input = await openEdit();
      const value = await input.inputValue();
      out.steps.push({step: "after_server_restart_reopen", value});
      assert.equal(value, "SECOND 678");
      assert.equal(await panelLine(), 'Saved headline: "SECOND 678"');
    } else if (mode === "restore") {
      await gotoReview(reviewKey);
      const input = await openEdit();
      await input.fill("");
      const rb = await saveAndReadback();
      assert.equal(rb, "Saved headline: (empty)");
      await reloadToClip(reviewKey);
      const input2 = await openEdit();
      assert.equal(await input2.inputValue(), "");
      out.steps.push({step: "restored_to_empty_and_verified_after_reload", value: ""});
    } else {
      throw new Error(`unknown mode ${mode}`);
    }
    assert.deepEqual(out.errors, []);
    console.log(JSON.stringify({status: "passed", test_id: "PAX-PHASE4B-FIX2", ...out}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
