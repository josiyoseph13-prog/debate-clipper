"use strict";

/* Phase 2 browser acceptance: the mock never runs media work. */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "..");
const staticRoot = path.join(root, "dc", "studio", "static");
const candidate = {id: "c_phase2", job_id: "job_phase2", start: 2, end: 18, duration: 16, score: 94, text: "A complete answer.", hook: {headline_options: ["A complete answer"]}, components: {}, decision: {}, source: {title: "Phase 2 debate", width: 1920, height: 1080}};
let mode = "running";
let startCount = 0;
let retryCount = 0;

const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Debate Clipper</title><link rel="stylesheet" href="/static/studio.css"></head><body><main id="studio-app" data-token="phase2-test" data-lan="false"><header class="brand-bar"><a class="brand" href="/" aria-label="Debate Clipper home"><span class="brand-mark">DC</span><span>Debate Clipper</span></a><div class="system-mini" id="system"></div><button type="button" class="header-button" id="help-button">Help</button><button type="button" class="header-button" id="my-exports">My exports</button><a class="classic-link" href="/classic">Classic view</a></header><nav class="steps"><button type="button" class="step active" data-view="home"><b>1</b><span>Add video</span></button><button type="button" class="step" data-view="find"><b>2</b><span>Find clips</span></button><button type="button" class="step" data-view="review"><b>3</b><span>Review</span></button><button type="button" class="step" data-view="export"><b>4</b><span>Export</span></button></nav><div id="connection-bar" hidden></div><div id="app-message" class="sr-only"></div><section id="home-view" class="view"></section><section id="find-view" class="view"></section><section id="review-view" class="view"></section><section id="export-view" class="view"></section><section id="exports-view" class="view"></section></main><script src="/static/speaker-frame.js"></script><script src="/static/studio.js"></script></body></html>`;

const jobs = () => {
  const terminal = mode === "ready" || mode === "failed" || mode === "cancelled";
  const state = mode === "ready" ? "awaiting_review" : mode;
  return {jobs: [{job_id: candidate.job_id, state, stage: mode === "failed" ? "transcribe" : "transcribe", title: "Phase 2 debate", is_test: false, error: mode === "failed" ? "The mock transcription failed." : null, progress: {percent: null, known: false, label: mode === "failed" ? "Listening to the debate" : terminal ? "Done" : "Listening to the debate", stage: "transcribe", stage_index: terminal ? 4 : 2, stage_count: 4}}], candidates: mode === "ready" ? [candidate] : []};
};

const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  if (url.pathname === "/") { response.writeHead(200, {"Content-Type": "text/html"}); response.end(html); return; }
  if (url.pathname === "/api/jobs") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify(jobs())); return; }
  if (url.pathname === "/api/exports") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({exports: []})); return; }
  if (url.pathname === "/api/system") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({cpu_percent: null, ram_percent: null})); return; }
  if (url.pathname === "/api/jobs/job_phase2/log") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({log: "Mock transcription failed."})); return; }
  if (url.pathname === "/__set") { mode = url.searchParams.get("state") || mode; response.writeHead(204); response.end(); return; }
  if (request.method === "POST") {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", () => {
      if (url.pathname === "/api/start-job") { startCount += 1; mode = "running"; response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({status: "started", job_id: candidate.job_id, title: "Phase 2 debate"})); return; }
      if (url.pathname === "/api/retry/job_phase2") { retryCount += 1; mode = "running"; response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({status: "started", job_id: candidate.job_id})); return; }
      if (url.pathname === "/api/cancel/job_phase2") { mode = "cancelled"; response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({status: "cancelled", job_id: candidate.job_id})); return; }
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
    await page.locator("#home-view input[type=url]").fill("https://youtu.be/dQw4w9WgXcQ");
    await page.getByRole("button", {name: "Find clips", exact: true}).click();
    await page.locator("#find-view .find-stage-summary").filter({hasText: "Listening to the debate"}).waitFor();
    assert.match(await page.locator("#find-view").textContent(), /Listening to the debate/);
    assert.match(await page.locator("#find-view").textContent(), /Stage 2 of 4/);
    assert.doesNotMatch(await page.locator("#find-view").textContent(), /\d+%/);
    assert.ok(await page.evaluate(() => Boolean(localStorage.getItem("debate-clipper-active-job"))));
    await page.waitForTimeout(2200);
    const elapsedBeforeReload = await page.locator("#find-view .elapsed-value").textContent();
    await page.reload();
    await page.locator("#find-view .find-stage-summary").filter({hasText: "Listening to the debate"}).waitFor();
    assert.match(await page.locator("#find-view").textContent(), /Listening to the debate/);
    assert.notEqual(await page.locator("#find-view .elapsed-value").textContent(), "0:00");
    await fetch(`${base}/__set?state=failed`);
    await page.locator("#find-view").filter({hasText: "Finding clips stopped"}).waitFor();
    assert.match(await page.locator("#find-view").textContent(), /Try again|Back to Add video|Show details/);
    assert.ok(await page.evaluate(() => Boolean(localStorage.getItem("debate-clipper-active-job"))));
    await page.getByRole("button", {name: "Try again", exact: true}).click();
    await page.locator("#find-view .find-stage-summary").filter({hasText: "Listening to the debate"}).waitFor();
    assert.match(await page.locator("#find-view").textContent(), /Starting|Listening/);
    assert.equal(retryCount, 1);
    await page.getByRole("button", {name: "Cancel", exact: true}).click();
    assert.match(await page.locator("#find-view").textContent(), /Stop finding clips\?/);
    await page.getByRole("button", {name: "Keep going", exact: true}).click();
    assert.doesNotMatch(await page.locator("#find-view").textContent(), /Stop finding clips\?/);
    await page.getByRole("button", {name: "Cancel", exact: true}).click();
    await page.getByRole("button", {name: "Yes, stop", exact: true}).click();
    await page.locator("#home-view .add-box").waitFor();
    assert.equal(await page.evaluate(() => localStorage.getItem("debate-clipper-active-job")), null);
    await page.locator("#home-view input[type=url]").fill("https://youtu.be/dQw4w9WgXcQ");
    await page.getByRole("button", {name: "Find clips", exact: true}).click();
    await fetch(`${base}/__set?state=ready`);
    await page.reload();
    await page.locator("#review-view .clip-row").first().waitFor();
    assert.match(await page.locator("#review-view").textContent(), /A complete answer/);
    assert.equal(startCount, 2);
    assert.ok(fs.readFileSync(path.join(staticRoot, "studio.js"), "utf8").includes("Still working"));
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({status: "passed", test_id: "PHASE2-FIND-CLIPS", checks: ["stage wording and stage position", "no fake percentage in Step 2", "active job survives reload", `elapsed timer continued from ${elapsedBeforeReload}`, "failure stays on Step 2", "retry restarts the saved job", "inline cancel confirmation", "cancel returns to Add video and clears active job", "ready job resumes directly to Review", "no JavaScript errors"]}));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exit(1); });
