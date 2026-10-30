"use strict";

/* Phase 3B browser acceptance: Review buttons only. */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "..");
const staticRoot = path.join(root, "dc", "studio", "static");
const records = [
  {id: "c_approve", job_id: "job_buttons", source_group_id: "source_buttons", run_id: "job_buttons", start: 10, end: 45, duration: 35, score: 94, text: "Approve this clip", hook: {headline_options: ["Approve this clip"]}, components: {}, decision: {}, source: {title: "Button fixture", source_group_id: "source_buttons", run_id: "job_buttons", run_created_at: "2026-10-08T10:00:00Z"}},
  {id: "c_reject", job_id: "job_buttons", source_group_id: "source_buttons", run_id: "job_buttons", start: 50, end: 82, duration: 32, score: 82, text: "Reject this clip", hook: {headline_options: ["Reject this clip"]}, components: {}, decision: {}, source: {title: "Button fixture", source_group_id: "source_buttons", run_id: "job_buttons", run_created_at: "2026-10-08T10:00:00Z"}},
  {id: "c_export", job_id: "job_buttons", source_group_id: "source_buttons", run_id: "job_buttons", start: 90, end: 135, duration: 45, score: 88, text: "Export this clip", hook: {headline_options: ["Export this clip"]}, components: {}, decision: {}, source: {title: "Button fixture", source_group_id: "source_buttons", run_id: "job_buttons", run_created_at: "2026-10-08T10:00:00Z"}},
];
const decisions = [];
const renders = [];
let rejectFailures = 1;
let exportFailures = 1;
const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Debate Clipper</title><link rel="stylesheet" href="/static/studio.css"></head><body><main id="studio-app" data-token="phase3b-test" data-lan="false"><header class="brand-bar"><a class="brand" href="/" aria-label="Debate Clipper home"><span class="brand-mark">DC</span><span>Debate Clipper</span></a><div class="system-mini" id="system"></div><button type="button" class="header-button" id="help-button">Help</button><button type="button" class="header-button" id="my-exports">My exports</button><a class="classic-link" href="/classic">Classic view</a></header><nav class="steps"><button type="button" class="step active" data-view="home"><b>1</b><span>Add video</span></button><button type="button" class="step" data-view="find"><b>2</b><span>Find clips</span></button><button type="button" class="step" data-view="review"><b>3</b><span>Review</span></button><button type="button" class="step" data-view="export"><b>4</b><span>Export</span></button></nav><div id="connection-bar" hidden></div><div id="app-message" class="sr-only"></div><section id="home-view" class="view"></section><section id="find-view" class="view"></section><section id="review-view" class="view"></section><section id="export-view" class="view"></section><section id="exports-view" class="view"></section></main><script src="/static/speaker-frame.js"></script><script src="/static/studio.js"></script></body></html>`;

const exportRow = id => ({export_id: id, stable_id: "c_export", key: `source/clip_${id}`, clip_name: `${id}.mp4`, file_url: `/api/exports/${id}/media`, title: "Export this clip", source_title: "Button fixture", start: 90, end: 135, size: 1234, date: "2026-10-08T12:00:00Z", edit_revision: "revision-1"});
const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  if (url.pathname === "/") { response.writeHead(200, {"Content-Type": "text/html"}); response.end(html); return; }
  if (url.pathname === "/api/jobs") {
    response.writeHead(200, {"Content-Type": "application/json"});
    response.end(JSON.stringify({jobs: [{job_id: "job_buttons", state: "awaiting_review", stage: "review", title: "Button fixture", is_test: false, progress: {percent: null, known: false, label: "Done"}}], candidates: records, review_exports: []}));
    return;
  }
  if (url.pathname === "/api/exports") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({exports: []})); return; }
  if (url.pathname === "/api/system") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({cpu_percent: null, ram_percent: null})); return; }
  if (request.method === "POST") {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", async () => {
      const payload = JSON.parse(body || "{}");
      if (url.pathname === "/api/decisions") {
        decisions.push(payload);
        if (payload.action === "reject" && rejectFailures-- > 0) { response.writeHead(500, {"Content-Type": "application/json"}); response.end(JSON.stringify({detail: "The decision service is temporarily unavailable"})); return; }
        response.writeHead(200, {"Content-Type": "application/json"});
        response.end(JSON.stringify({status: "recorded", action: payload.action, job_id: payload.job_id, candidate_id: payload.candidate_id, headline: payload.headline, edits: payload.edits, framing_controls: payload.framing_controls, caption_controls: payload.caption_controls, edit_revision: "revision-1"}));
        return;
      }
      if (url.pathname === "/api/render") {
        renders.push(payload);
        await new Promise(resolve => setTimeout(resolve, 300));
        if (exportFailures-- > 0) {
          response.writeHead(200, {"Content-Type": "application/json"});
          response.end(JSON.stringify({status: "failed", attempt: {export_id: payload.export_id, job_id: payload.job_id, candidate_id: payload.candidate_id, title: "Export this clip", source_title: "Button fixture", status: "failed", reason: "The test renderer failed"}}));
        } else {
          const exported = exportRow(payload.export_id);
          response.writeHead(200, {"Content-Type": "application/json"});
          response.end(JSON.stringify({status: "exported", attempt: {export_id: payload.export_id, job_id: payload.job_id, candidate_id: payload.candidate_id, title: "Export this clip", source_title: "Button fixture", status: "exported", edit_revision: "revision-1", export: exported}, export: exported}));
        }
        return;
      }
      response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({status: "recorded"}));
    });
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    const name = path.basename(url.pathname);
    const file = path.join(staticRoot, name);
    if (file.startsWith(staticRoot) && fs.existsSync(file)) { response.writeHead(200, {"Content-Type": name.endsWith(".css") ? "text/css" : "text/javascript"}); response.end(fs.readFileSync(file)); return; }
  }
  response.writeHead(404); response.end();
});

(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const browserPath = ["C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe", "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe"].find(value => fs.existsSync(value));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.locator(".step[data-view='review']").click();
    await page.locator("#review-view .clip-row").first().waitFor();
    const review = page.locator("#review-view");
    const actions = review.locator(".review-actions");
    const heights = await actions.locator(".review-action").evaluateAll(elements => elements.map(element => element.getBoundingClientRect().height));
    assert.equal(new Set(heights).size, 1, "Review action buttons have a stable height");

    await actions.getByRole("button", {name: "Approve Approve this clip", exact: true}).click();
    await page.waitForFunction(() => document.querySelector(".review-actions .approve")?.disabled === false);
    assert.match(await review.textContent(), /Approved/);
    assert.match(await review.textContent(), /1 of 3 reviewed — 1 approved · 0 exported/);

    await review.getByRole("button", {name: /Reject this clip/}).first().click();
    await actions.getByRole("button", {name: "Reject", exact: true}).click();
    await page.waitForFunction(() => document.querySelector(".review-actions .reject")?.disabled === false);
    assert.match(await review.textContent(), /Could not reject this clip/);
    assert.equal(await review.locator(".review-actions .reject").isDisabled(), false);
    await actions.getByRole("button", {name: "Reject", exact: true}).click();
    await page.waitForFunction(() => document.querySelector(".review-actions .reject")?.disabled === false);
    assert.match(await review.textContent(), /Rejected/);
    assert.match(await review.textContent(), /2 of 3 reviewed — 1 approved · 0 exported/);

    await review.getByRole("button", {name: /Approve this clip/}).first().click();
    await review.getByRole("button", {name: "Edit", exact: true}).click();
     assert.equal(await review.locator(".edit-headline-field input").inputValue(), "Approve this clip");
    assert.equal(await review.locator("video").count(), 1);
     await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
     await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"));
     assert.equal(await review.locator(".edit-panel").count(), 0);

    await review.getByRole("button", {name: /Export this clip/}).last().click();
    await actions.getByRole("button", {name: "Export", exact: true}).click();
    assert.equal(await review.locator(".review-actions .export").textContent(), "Exporting…");
    assert.equal(await review.locator(".review-actions .export").isDisabled(), true);
    const exportingHeights = await actions.locator(".review-action").evaluateAll(elements => elements.map(element => element.getBoundingClientRect().height));
    assert.equal(new Set(exportingHeights).size, 1, "Working export state keeps button height stable");
    await page.locator("#export-view").filter({hasText: "Exporting…"}).waitFor();
    await page.locator(".step[data-view='review']").click();
    assert.equal(await page.locator("#review-view .review-actions .export").textContent(), "Exporting…");
    assert.equal(await page.locator("#review-view .review-actions .export").isDisabled(), true);
    await page.locator("#review-view .view-export").click();
    await page.locator("#export-view").filter({hasText: "Exporting…"}).waitFor();
    await page.waitForFunction(() => document.querySelector("#export-view")?.textContent.includes("Export failed"));
    assert.match(await page.locator("#export-view").textContent(), /The test renderer failed/);
     await page.locator(".step[data-view='review']").click();
     assert.match(await page.locator("#review-view").textContent(), /Export failed — Try again/);
     const failedExportGeometry = await page.locator("#review-view .review-actions .export").evaluate(element => {
       const rect = element.getBoundingClientRect();
       return {left: rect.left, right: rect.right, clientHeight: element.clientHeight, scrollHeight: element.scrollHeight};
     });
     assert.ok(failedExportGeometry.left >= 0 && failedExportGeometry.right <= 1280, "failed Export button stays inside Review action column");
     assert.ok(failedExportGeometry.scrollHeight <= failedExportGeometry.clientHeight, "Export failed — Try again is fully visible");

     await page.locator("#review-view .review-actions .export").click();
    await page.locator("#export-view").filter({hasText: "Exporting…"}).waitFor();
    await page.locator("#export-view").filter({hasText: "Exported ✓"}).waitFor();
    assert.equal(renders.length, 2);
    assert.notEqual(renders[0].export_id, renders[1].export_id, "Retry gets a new export request ID");
    assert.equal(decisions.filter(item => item.candidate_id === "c_export").map(item => item.action).join(","), "approve,approve");
    await page.locator(".step[data-view='review']").click();
    await page.locator("#review-view .review-actions .export").filter({hasText: "Exported ✓"}).waitFor();
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({status: "passed", test_id: "PHASE3B-REVIEW-BUTTONS", checks: ["Approve saves and updates badge/count", "Reject failure is clear and retryable", "Reject success updates badge/count", "Edit opens the selected clip and preserves one player", "Export immediately shows Exporting and locks", "Export moves to Step 4 without using Find clips", "returning to Review preserves Exporting", "export failure is clear and retryable", "retry uses a new export ID", "Export auto-approves before rendering", "successful retry shows Exported", "button heights remain stable", "no JavaScript errors"]}));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exit(1); });
