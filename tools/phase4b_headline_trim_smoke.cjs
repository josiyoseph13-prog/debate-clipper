"use strict";

/* Phase 4B browser acceptance: Headline and Trim only. */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "..");
const staticRoot = path.join(root, "dc", "studio", "static");
const records = [{
  id: "c_phase4b",
  job_id: "job_phase4b",
  source_group_id: "source_phase4b",
  run_id: "job_phase4b",
  start: 10,
  end: 55,
  duration: 45,
  score: 94,
  text: "Headline and trim fixture",
  hook: {headline_options: ["Original fixture headline"]},
  components: {},
  decision: {},
  source: {title: "Phase 4B source", duration: 120, source_group_id: "source_phase4b", run_id: "job_phase4b", run_created_at: "2026-10-11T10:00:00Z"},
}];
const decisions = [];
const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Debate Clipper</title><link rel="stylesheet" href="/static/studio.css"></head><body><main id="studio-app" data-token="phase4b-test" data-lan="false"><header class="brand-bar"><a class="brand" href="/" aria-label="Debate Clipper home"><span class="brand-mark">DC</span><span>Debate Clipper</span></a><div class="system-mini" id="system"></div><button type="button" class="header-button" id="help-button">Help</button><button type="button" class="header-button" id="my-exports">My exports</button><a class="classic-link" href="/classic">Classic view</a></header><nav class="steps"><button type="button" class="step active" data-view="home"><b>1</b><span>Add video</span></button><button type="button" class="step" data-view="find"><b>2</b><span>Find clips</span></button><button type="button" class="step" data-view="review"><b>3</b><span>Review</span></button><button type="button" class="step" data-view="export"><b>4</b><span>Export</span></button></nav><div id="connection-bar" hidden></div><div id="app-message" class="sr-only"></div><section id="home-view" class="view"></section><section id="find-view" class="view"></section><section id="review-view" class="view"></section><section id="export-view" class="view"></section><section id="exports-view" class="view"></section></main><script src="/static/speaker-frame.js"></script><script src="/static/studio.js"></script></body></html>`;
const json = (response, status, value) => { response.writeHead(status, {"Content-Type": "application/json"}); response.end(JSON.stringify(value)); };
const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  if (url.pathname === "/") { response.writeHead(200, {"Content-Type": "text/html"}); response.end(html); return; }
  if (url.pathname === "/api/jobs") { json(response, 200, {jobs: [{job_id: "job_phase4b", state: "awaiting_review", stage: "review", title: "Phase 4B source", is_test: false, progress: {percent: null, known: false, label: "Done"}}], candidates: records, review_exports: []}); return; }
  if (url.pathname === "/api/exports" || url.pathname === "/api/system") { json(response, 200, url.pathname.endsWith("exports") ? {exports: []} : {cpu_percent: null, ram_percent: null}); return; }
  if (request.method === "POST") {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", () => {
      const payload = JSON.parse(body || "{}");
      if (url.pathname === "/api/decisions") {
        decisions.push(payload);
        json(response, 200, {status: "recorded", ...payload, edit_revision: `revision-${decisions.length}`});
        return;
      }
      json(response, 200, {status: "recorded"});
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
    const review = page.locator("#review-view");
    await page.locator(".step[data-view='review']").click();
    await review.locator(".clip-row").first().waitFor();
    await review.getByRole("button", {name: "Edit", exact: true}).click();
    const headline = review.locator(".edit-headline-field input");
    assert.equal(await headline.inputValue(), "Original fixture headline");
    await headline.fill("A saved Phase 4B headline");
    await review.locator(".edit-accordion-trigger").filter({hasText: "Trim"}).click();
    const start = review.locator(".trim-time-start");
    const end = review.locator(".trim-time-end");
    assert.equal(await start.inputValue(), "10.00");
    assert.equal(await end.inputValue(), "55.00");
    await end.fill("50"); await end.dispatchEvent("change");
    await start.fill("20"); await start.dispatchEvent("change");
    assert.match(await review.locator(".trim-summary").textContent(), /0:30/);
    await start.fill("60"); await start.dispatchEvent("change");
    assert.match(await review.locator(".trim-error").textContent(), /Start must be before end/);
    await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
    assert.equal(decisions.length, 0, "invalid trim does not send a save");
    await start.fill("20"); await start.dispatchEvent("change");
    await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
    await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"));
    assert.equal(decisions.length, 1);
    assert.equal(decisions[0].headline, "A saved Phase 4B headline");
    assert.deepEqual(decisions[0].edits, {start: 20, end: 50});
    await review.getByRole("button", {name: "Edit", exact: true}).click();
    assert.equal(await review.locator(".edit-headline-field input").inputValue(), "A saved Phase 4B headline");
    await review.locator(".edit-accordion-trigger").filter({hasText: "Trim"}).click();
    assert.equal(await review.locator(".trim-time-start").inputValue(), "20.00");
    assert.equal(await review.locator(".trim-time-end").inputValue(), "50.00");
    await review.locator(".edit-headline-field input").fill("");
    await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
    await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"));
    await review.getByRole("button", {name: "Edit", exact: true}).click();
    assert.equal(await review.locator(".edit-headline-field input").inputValue(), "", "empty headline remains empty after save");
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({status: "passed", test_id: "PHASE4B-HEADLINE-TRIM", checks: ["headline field is at top of Edit", "trim start/end controls show current values", "trim length updates plainly", "invalid trim stays local and does not save", "Save & Done persists headline and trim", "reopening restores headline and trim", "empty headline remains empty after save", "no JavaScript errors"]}));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exit(1); });
