"use strict";

/* Phase 3A browser acceptance: Review list/player only; no media pipeline. */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "..");
const staticRoot = path.join(root, "dc", "studio", "static");
const records = [
  {id: "c_real_a1", job_id: "job_real_a", source_group_id: "source_a", run_id: "job_real_a", start: 10, end: 55, duration: 45, score: 94, text: "First real clip", hook: {headline_options: ["First real clip"]}, components: {}, decision: {action: "approve"}, source: {title: "Debate source A", source_group_id: "source_a", run_id: "job_real_a", run_created_at: "2026-10-08T10:00:00Z"}},
  {id: "c_real_a2", job_id: "job_real_a", source_group_id: "source_a", run_id: "job_real_a", start: 70, end: 102, duration: 32, score: 82, text: "Second real clip", hook: {headline_options: ["Second real clip"]}, components: {}, decision: {action: "reject"}, source: {title: "Debate source A", source_group_id: "source_a", run_id: "job_real_a", run_created_at: "2026-10-08T10:00:00Z"}},
  {id: "c_real_b1", job_id: "job_real_b", source_group_id: "source_b", run_id: "job_real_b", start: 125, end: 180, duration: 55, score: 76, text: "Third real clip", hook: {headline_options: ["Third real clip"]}, components: {}, decision: {}, export: {stable_id: "c_real_b1", cover: null}, source: {title: "Debate source B", source_group_id: "source_b", run_id: "job_real_b", run_created_at: "2026-10-08T11:00:00Z"}},
  {id: "c_test_only", job_id: "job_test_fixture", source_group_id: "test_source", run_id: "job_test_fixture", start: 0, end: 90, duration: 90, score: 99, text: "Test-only clip", hook: {headline_options: ["Test-only clip"]}, components: {}, decision: {}, source: {title: "Test fixture", source_group_id: "test_source", run_id: "job_test_fixture"}},
];
let decisions = [];
const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Debate Clipper</title><link rel="stylesheet" href="/static/studio.css"></head><body><main id="studio-app" data-token="phase3a-test" data-lan="false"><header class="brand-bar"><a class="brand" href="/" aria-label="Debate Clipper home"><span class="brand-mark">DC</span><span>Debate Clipper</span></a><div class="system-mini" id="system"></div><button type="button" class="header-button" id="help-button">Help</button><button type="button" class="header-button" id="my-exports">My exports</button><a class="classic-link" href="/classic">Classic view</a></header><nav class="steps"><button type="button" class="step active" data-view="home"><b>1</b><span>Add video</span></button><button type="button" class="step" data-view="find"><b>2</b><span>Find clips</span></button><button type="button" class="step" data-view="review"><b>3</b><span>Review</span></button><button type="button" class="step" data-view="export"><b>4</b><span>Export</span></button></nav><div id="connection-bar" hidden></div><div id="app-message" class="sr-only"></div><section id="home-view" class="view"></section><section id="find-view" class="view"></section><section id="review-view" class="view"></section><section id="export-view" class="view"></section><section id="exports-view" class="view"></section></main><script src="/static/speaker-frame.js"></script><script src="/static/studio.js"></script></body></html>`;

const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  if (url.pathname === "/") { response.writeHead(200, {"Content-Type": "text/html"}); response.end(html); return; }
  if (url.pathname === "/api/jobs") {
    response.writeHead(200, {"Content-Type": "application/json"});
    response.end(JSON.stringify({jobs: [{job_id: "job_real_a", state: "awaiting_review", stage: "review", title: "Debate source A", is_test: false, progress: {percent: null, known: false, label: "Done"}}, {job_id: "job_real_b", state: "awaiting_review", stage: "review", title: "Debate source B", is_test: false, progress: {percent: null, known: false, label: "Done"}}, {job_id: "job_test_fixture", state: "awaiting_review", stage: "review", title: "Test fixture", is_test: true, progress: {percent: null, known: false, label: "Done"}}], candidates: records}));
    return;
  }
  if (url.pathname === "/api/exports") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({exports: []})); return; }
  if (url.pathname === "/api/system") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({cpu_percent: null, ram_percent: null})); return; }
  if (request.method === "POST") {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", () => {
      if (url.pathname === "/api/decisions") {
        const payload = JSON.parse(body || "{}");
        decisions.push(payload);
        response.writeHead(200, {"Content-Type": "application/json"});
        response.end(JSON.stringify({status: "recorded", ...payload}));
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
    const base = `http://127.0.0.1:${server.address().port}`;
    await page.goto(base);
    await page.locator(".step[data-view='review']").click();
    await page.locator("#review-view .clip-row").first().waitFor();
    const review = page.locator("#review-view");
    assert.equal(await review.locator(".source-group").count(), 2);
    assert.equal(await review.locator(".source-group .clip-row").count(), 3);
    assert.equal(await review.locator("video").count(), 1);
    assert.equal(await review.locator(".preview-caption").count(), 0);
    assert.match(await review.textContent(), /Debate source A/);
    assert.match(await review.textContent(), /Debate source B/);
    assert.match(await review.textContent(), /0:45 · 0:10–0:55/);
    assert.match(await review.textContent(), /0:32 · 1:10–1:42/);
    assert.match(await review.textContent(), /Approved/);
    assert.match(await review.textContent(), /Rejected/);
    assert.match(await review.textContent(), /Exported/);
    assert.doesNotMatch(await review.textContent(), /Test-only clip|Test fixture/);
    assert.match(await review.textContent(), /2 of 2 reviewed — 1 approved · 0 exported/);
    await review.getByRole("button", {name: /Second real clip/}).click();
    assert.equal(await review.locator("video").count(), 1);
    await review.getByRole("button", {name: /First real clip/}).click();
    assert.equal(await review.locator("video").count(), 1);
    await review.getByRole("button", {name: /Second real clip/}).click();
    assert.equal(await review.locator("video").count(), 1);
    await review.getByRole("button", {name: "Approve Second real clip", exact: true}).click();
    await page.waitForFunction(() => document.querySelector(".review-actions .approve")?.disabled === false);
    await page.waitForTimeout(100);
    assert.match(await review.textContent(), /2 of 2 reviewed — 2 approved · 0 exported/);
    assert.equal(decisions.length, 1);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({status: "passed", test_id: "PHASE3A-REVIEW", checks: ["two source groups", "filtered sidebar and preview use real clips only", "one active player", "no unrelated preview overlay", "clip length and source start-end", "Approved/Rejected/Exported badges", "source-scoped reviewed count", "approve updates badge and count", "no JavaScript errors"]}));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exit(1); });
