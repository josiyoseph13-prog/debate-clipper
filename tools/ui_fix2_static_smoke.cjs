"use strict";

/*
 * UI-only smoke test. It exercises the real Studio JavaScript and CSS against
 * a local mock API so the test never starts the media pipeline or changes an
 * exported video. Native Windows acceptance still uses studio_browser.py.
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "..");
const staticRoot = path.join(root, "dc", "studio", "static");
const reports = path.join(root, "reports", "ui_fix2");
const candidate = {
  id: "c_ui_demo", job_id: "job_ui_demo", start: 2, end: 18, duration: 16,
  score: 94, text: "A clear disagreement with a complete answer.",
  hook: {headline_options: ["A clear disagreement"]}, components: {hook: .94, clarity: .9, ending: .88},
  decision: {}, source: {title: "UI demo debate", width: 1920, height: 1080, rights_class: "own"},
};
const exportRow = {
  key: "demo/clip", stable_id: candidate.id, clip: "C:/demo/clip.mp4", clip_name: "01_a-clear-disagreement.mp4",
  file_url: "/api/exports/demo/clip/media", title: "A clear disagreement", source_title: "UI demo debate",
  start: 2, end: 18, date: new Date().toISOString(), size: 1000, status: "passed", cover: null,
};
let exported = false;
let startRequests = 0;

const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Debate Clipper</title><link rel="stylesheet" href="/static/studio.css"></head><body><main id="studio-app" data-token="ui-test" data-lan="false"><header class="brand-bar"><a class="brand" href="/" aria-label="Debate Clipper home"><span class="brand-mark">DC</span><span>Debate Clipper</span></a><div class="system-mini" id="system"></div><button type="button" class="header-button" id="help-button">Help</button><button type="button" class="header-button" id="my-exports">My exports</button><a class="classic-link" href="/classic">Classic view</a></header><nav class="steps"><button type="button" class="step active" data-view="home"><b>1</b><span>Add video</span></button><button type="button" class="step" data-view="find"><b>2</b><span>Find clips</span></button><button type="button" class="step" data-view="review"><b>3</b><span>Review</span></button><button type="button" class="step" data-view="export"><b>4</b><span>Export</span></button></nav><div id="connection-bar" hidden></div><div id="app-message" class="sr-only"></div><section id="home-view" class="view"></section><section id="find-view" class="view"></section><section id="review-view" class="view"></section><section id="export-view" class="view"></section><section id="exports-view" class="view"></section></main><script src="/static/speaker-frame.js"></script><script src="/static/studio.js"></script></body></html>`;

const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  if (url.pathname === "/") { response.writeHead(200, {"Content-Type": "text/html"}); response.end(html); return; }
  if (url.pathname === "/api/jobs") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({jobs: [{job_id: candidate.job_id, state: "awaiting_review", stage: "review", title: "UI demo debate", is_test: false, progress: {percent: 100, known: true, label: "Done"}}], candidates: [candidate]})); return; }
  if (url.pathname === "/api/exports") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({exports: exported ? [exportRow] : []})); return; }
  if (url.pathname === "/api/system") { response.writeHead(200, {"Content-Type": "application/json"}); response.end(JSON.stringify({cpu_percent: 12, ram_percent: 30})); return; }
  if (url.pathname.startsWith("/api/media/") || url.pathname.startsWith("/api/exports/")) { response.writeHead(404); response.end(); return; }
  if (request.method === "POST") {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", () => {
      let payload = {};
      try { payload = JSON.parse(body || "{}"); } catch {}
      if (url.pathname === "/api/start-job") {
        startRequests += 1;
        if (payload.source_url === "https://youtu.be/aaaaaaaaaaa") {
          response.writeHead(503, {"Content-Type": "application/json"});
          response.end(JSON.stringify({detail: "The mock downloader is unavailable."}));
          return;
        }
        response.writeHead(200, {"Content-Type": "application/json"});
        response.end(JSON.stringify({status: "started", job_id: candidate.job_id, title: "UI demo debate"}));
        return;
      }
      if (url.pathname === "/api/render") exported = true;
      response.writeHead(200, {"Content-Type": "application/json"});
      response.end(JSON.stringify(url.pathname === "/api/render" ? {status: "passed", export: exportRow} : {status: "recorded", ...payload}));
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
  fs.mkdirSync(reports, {recursive: true});
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const browserPath = [
    "C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe",
    "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe",
  ].find(candidate => fs.existsSync(candidate));
  const browser = await chromium.launch({headless: true, ...(browserPath ? {executablePath: browserPath} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const base = `http://127.0.0.1:${server.address().port}`;
    await page.goto(base);
    await page.locator("#home-view .add-box").waitFor();
    const source = page.locator("#home-view input[type=url]");
    await source.fill("https://example.com/not-a-youtube-video");
    await page.getByRole("button", {name: "Find clips", exact: true}).click();
    await page.locator("#app-message").filter({hasText: "does not look like a YouTube video"}).waitFor();
    assert.equal(startRequests, 0);
    await source.fill("https://youtu.be/aaaaaaaaaaa");
    await page.locator("#home-view details.more-options").click();
    await page.locator("#home-view select").nth(0).selectOption("permission");
    await page.locator("#home-view select").nth(1).selectOption("12");
    await page.getByRole("button", {name: "Find clips", exact: true}).click();
    await page.locator("#app-message").filter({hasText: "The video could not be started"}).waitFor();
    assert.equal(startRequests, 1);
    assert.equal(await source.inputValue(), "https://youtu.be/aaaaaaaaaaa");
    assert.equal(await page.locator("#home-view details.more-options").evaluate(element => element.open), true);
    assert.equal(await page.locator("#home-view select").nth(0).inputValue(), "permission");
    assert.equal(await page.locator("#home-view select").nth(1).inputValue(), "12");
    await source.fill("https://youtu.be/dQw4w9WgXcQ");
    await page.waitForTimeout(5500);
    assert.equal(await source.inputValue(), "https://youtu.be/dQw4w9WgXcQ");
    assert.equal(await page.locator("#home-view details.more-options").evaluate(element => element.open), true);
    assert.equal(await page.locator("#home-view select").nth(0).inputValue(), "permission");
    assert.equal(await page.locator("#home-view select").nth(1).inputValue(), "12");
    const fixture = path.join(require("node:os").tmpdir(), "debate-clipper-phase1-fixture.mp4");
    fs.writeFileSync(fixture, "phase1 fixture");
    await page.locator("#home-view input[type=file]").setInputFiles(fixture);
    await page.waitForTimeout(5500);
    assert.equal(await page.locator("#home-view input[type=file]").evaluate(element => element.files.length), 1);
    await page.getByRole("button", {name: "Remove file", exact: true}).click();
    await source.fill("https://youtu.be/dQw4w9WgXcQ");
    await page.getByRole("button", {name: "Find clips", exact: true}).click();
    await page.locator("#find-view").waitFor();
    assert.equal(startRequests, 2);
    const oneVideoRule = await page.evaluate(() => {
      const first = document.createElement("video");
      const second = document.createElement("video");
      let firstPaused = 0;
      first.pause = () => { firstPaused += 1; };
      document.body.append(first, second);
      window.DebateClipperVideoRegistry.register(first);
      window.DebateClipperVideoRegistry.register(second);
      second.dispatchEvent(new Event("play"));
      first.remove(); second.remove();
      return firstPaused;
    });
    assert.equal(oneVideoRule, 1);
    await page.screenshot({path: path.join(reports, "after_screen1_add_video.png"), fullPage: true});
    await page.locator(".step[data-view='find']").click();
    assert.match(await page.locator("#find-view").textContent(), /Working|Cancel/);
    await page.screenshot({path: path.join(reports, "after_screen2_finding_clips.png"), fullPage: true});
    await page.locator(".step[data-view='review']").click();
    await page.locator(".clip-row").first().waitFor();
    assert.equal(await page.locator("#review-view video").count(), 1);
    assert.equal(await page.locator(".review-actions > button").count(), 4);
    await page.screenshot({path: path.join(reports, "after_screen3_review_clips.png"), fullPage: true});
    await page.getByRole("button", {name: "Edit", exact: true}).click();
    assert.equal(await page.locator(".review-layout.editing").count(), 1);
    await page.screenshot({path: path.join(reports, "edit_side_by_side_desktop.png"), fullPage: true});
    const phone = await browser.newPage({viewport: {width: 390, height: 844}});
    await phone.goto(base);
    await phone.locator(".step[data-view='review']").click();
    await phone.locator(".clip-row").first().waitFor();
    await phone.getByRole("button", {name: "Edit", exact: true}).click();
    await phone.screenshot({path: path.join(reports, "edit_side_by_side_mobile.png"), fullPage: true});
    await phone.close();
     await page.getByRole("button", {name: "Save & Done", exact: true}).first().click();
     await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"));
     await page.getByRole("button", {name: "Export", exact: true}).click();
     await page.waitForFunction(() => document.querySelector("#export-view")?.textContent.includes("Your clip is ready"), null, {timeout: 10000});
    await page.screenshot({path: path.join(reports, "after_screen4_export_done.png"), fullPage: true});
    await page.getByRole("button", {name: "My exports", exact: true}).click();
    await page.locator("#exports-view").filter({hasText: "Your finished videos"}).waitFor();
    await page.screenshot({path: path.join(reports, "after_my_exports.png"), fullPage: true});
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({status: "passed", test_id: "UI-V2-01/02/07 + PHASE1", screenshots: 6, checks: ["invalid YouTube link rejected without starting a job", "failed start retains link and options", "rights and clip count survive refresh", "link survives refresh", "More options survives refresh", "local file survives refresh", "valid YouTube link starts a job", "one-video playback rule", "all four screens rendered", "one selected video", "four review actions", "desktop side-by-side edit", "mobile edit layout", "export done and My exports", "no JavaScript errors"]}));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exit(1); });
