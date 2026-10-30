"use strict";

/* Phase 4A browser acceptance: Edit shell, playback, accordion, mode, and save model. */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "..");
const staticRoot = path.join(root, "dc", "studio", "static");
const records = [{
  id: "c_edit_fixture",
  job_id: "job_edit_fixture",
  source_group_id: "source_edit_fixture",
  run_id: "job_edit_fixture",
  start: 10,
  end: 55,
  duration: 45,
  score: 94,
  text: "Edit shell fixture",
  hook: {headline_options: ["Edit shell fixture"]},
  components: {},
  decision: {},
  source: {title: "Edit phase source", source_group_id: "source_edit_fixture", run_id: "job_edit_fixture", run_created_at: "2026-10-09T10:00:00Z"},
}];
const decisions = [];
let saveFailures = 1;
let saveDelay = 1;
const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Debate Clipper</title><link rel="stylesheet" href="/static/studio.css"></head><body><main id="studio-app" data-token="phase4a-test" data-lan="false"><header class="brand-bar"><a class="brand" href="/" aria-label="Debate Clipper home"><span class="brand-mark">DC</span><span>Debate Clipper</span></a><div class="system-mini" id="system"></div><button type="button" class="header-button" id="help-button">Help</button><button type="button" class="header-button" id="my-exports">My exports</button><a class="classic-link" href="/classic">Classic view</a></header><nav class="steps"><button type="button" class="step active" data-view="home"><b>1</b><span>Add video</span></button><button type="button" class="step" data-view="find"><b>2</b><span>Find clips</span></button><button type="button" class="step" data-view="review"><b>3</b><span>Review</span></button><button type="button" class="step" data-view="export"><b>4</b><span>Export</span></button></nav><div id="connection-bar" hidden></div><div id="app-message" class="sr-only"></div><section id="home-view" class="view"></section><section id="find-view" class="view"></section><section id="review-view" class="view"></section><section id="export-view" class="view"></section><section id="exports-view" class="view"></section></main><script src="/static/speaker-frame.js"></script><script src="/static/studio.js"></script></body></html>`;

const json = (response, status, value) => { response.writeHead(status, {"Content-Type": "application/json"}); response.end(JSON.stringify(value)); };
const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  if (url.pathname === "/") { response.writeHead(200, {"Content-Type": "text/html"}); response.end(html); return; }
  if (url.pathname === "/api/jobs") { json(response, 200, {jobs: [{job_id: "job_edit_fixture", state: "awaiting_review", stage: "review", title: "Edit phase source", is_test: false, progress: {percent: null, known: false, label: "Done"}}], candidates: records, review_exports: []}); return; }
  if (url.pathname === "/api/exports" || url.pathname === "/api/system") { json(response, 200, url.pathname.endsWith("exports") ? {exports: []} : {cpu_percent: null, ram_percent: null}); return; }
  if (request.method === "POST") {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", async () => {
      const payload = JSON.parse(body || "{}");
      if (url.pathname === "/api/decisions") {
        decisions.push(payload);
        if (payload.action === "save" && saveFailures-- > 0) { json(response, 500, {detail: "The test save service is temporarily unavailable"}); return; }
        if (payload.action === "save" && saveDelay-- > 0) await new Promise(resolve => setTimeout(resolve, 150));
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
    await page.locator(".step[data-view='review']").click();
    const review = page.locator("#review-view");
    await review.locator(".clip-row").first().waitFor();
    await review.getByRole("button", {name: "Edit", exact: true}).click();
    assert.equal(await review.locator(".review-layout.editing").count(), 1);
    assert.equal(await review.locator(".clip-sidebar").isVisible(), true);
    assert.equal(await review.locator("video").count(), 1);
    assert.equal(await review.locator(".edit-panel").count(), 1);
    assert.match(await review.locator(".edit-panel").textContent(), /Edit phase source/);
    assert.equal(await review.locator(".edit-playback").count(), 1);
    assert.equal(await review.getByRole("button", {name: "−5 seconds", exact: true}).count(), 1);
    assert.equal(await review.getByRole("button", {name: "+5 seconds", exact: true}).count(), 1);
    assert.equal(await review.locator(".edit-seek").count(), 1);
    const playbackRects = await review.locator(".edit-playback-transport > button").evaluateAll(elements => elements.map(element => {
      const rect = element.getBoundingClientRect();
      return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom};
    }));
    assert.equal(playbackRects.length, 3);
    playbackRects.forEach((left, index) => playbackRects.slice(index + 1).forEach(right => {
      assert.equal(left.right > right.left && right.right > left.left && left.bottom > right.top && right.bottom > left.top, false, "Review playback buttons do not overlap");
    }));
    assert.equal(await review.locator(".edit-accordion-group.open").count(), 1);
    assert.equal(await review.locator(".edit-accordion-group.open .edit-accordion-trigger span").textContent(), "Speaker Frame");
    assert.match(await review.locator(".edit-headline-field").textContent(), /Headline/);
    assert.deepEqual(await review.locator(".edit-accordion-trigger span").allTextContents(), ["Speaker Frame", "Trim", "Framing", "Captions"]);
    assert.equal(await review.locator(".edit-mode-button.active").textContent(), "Simple");
    const wideGeometry = await review.evaluate(() => {
      const stage = document.querySelector(".review-stage").getBoundingClientRect();
      const panel = document.querySelector(".edit-panel").getBoundingClientRect();
      return {stageWidth: stage.width, panelWidth: panel.width, panelLeft: panel.left, stageRight: stage.right};
    });
    assert.ok(wideGeometry.stageWidth > wideGeometry.panelWidth, "wide Edit gives the video column more space than the options column");
    assert.ok(wideGeometry.panelLeft >= wideGeometry.stageRight, "wide Edit places options to the right of the video");
    await page.evaluate(() => { window.__phase4aVideo = document.querySelector("#review-view video"); });
    await review.locator(".edit-accordion-trigger").filter({hasText: "Captions"}).click();
    const captionsScroll = await review.evaluate(() => {
      const panel = document.querySelector(".edit-panel");
      const group = document.querySelector(".edit-accordion-group.open .edit-accordion-trigger");
      const panelRect = panel.getBoundingClientRect();
      const groupRect = group.getBoundingClientRect();
      return {scrollTop: panel.scrollTop, groupTop: groupRect.top, groupBottom: groupRect.bottom, panelTop: panelRect.top, panelBottom: panelRect.bottom, scrollHeight: panel.scrollHeight, clientHeight: panel.clientHeight};
    });
    assert.equal(await review.locator(".edit-accordion-group.open .edit-accordion-trigger span").textContent(), "Captions");
    assert.ok(captionsScroll.groupTop >= captionsScroll.panelTop && captionsScroll.groupBottom <= captionsScroll.panelBottom, "opened Captions group stays in view");
    if (captionsScroll.scrollHeight > captionsScroll.clientHeight) assert.ok(captionsScroll.scrollTop > 0, "opening Captions does not return the panel to the headline");
    await review.locator(".edit-accordion-trigger").filter({hasText: "Trim"}).click();
    assert.equal(await review.locator(".edit-accordion-group.open").count(), 1);
    assert.equal(await review.locator(".edit-accordion-group.open .edit-accordion-trigger span").textContent(), "Trim");
    const trimVisible = await review.evaluate(() => {
      const panel = document.querySelector(".edit-panel");
      const group = document.querySelector(".edit-accordion-group.open .edit-accordion-trigger");
      const panelRect = panel.getBoundingClientRect();
      const groupRect = group.getBoundingClientRect();
      return groupRect.top >= panelRect.top && groupRect.bottom <= panelRect.bottom;
    });
    assert.equal(trimVisible, true, "opened Trim group stays in view");
    assert.equal(await page.evaluate(() => document.querySelector("#review-view video") === window.__phase4aVideo), true);
    await review.getByRole("button", {name: "Advanced", exact: true}).click();
    assert.equal(await review.locator(".edit-mode-button.active").textContent(), "Advanced");
    assert.equal(await page.evaluate(() => localStorage.getItem("debate-clipper-edit-mode")), "advanced");
    await review.getByRole("button", {name: "Simple", exact: true}).click();
    await review.locator(".edit-accordion-trigger").filter({hasText: "Framing"}).click();
    await review.getByRole("button", {name: "Closer", exact: true}).click();
    assert.equal(await page.evaluate(() => document.querySelector("#review-view video") === window.__phase4aVideo), true);
    await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
    await review.locator(".edit-save-status").filter({hasText: "Save failed"}).waitFor();
    assert.equal(await review.locator(".edit-panel").count(), 1);
    await review.getByRole("button", {name: "Save & Done", exact: true}).first().click();
    await review.locator(".edit-save-status").filter({hasText: "Saving…"}).waitFor();
    assert.equal(await review.getByRole("button", {name: "Saving…", exact: true}).count(), 2);
    assert.equal(await review.getByRole("button", {name: "Saving…", exact: true}).first().isDisabled(), true);
    await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"));
    assert.equal(await review.locator(".edit-panel").count(), 0);
    assert.equal(decisions.filter(item => item.action === "save").length, 2);
    assert.equal(decisions.at(-1).framing_controls.zoom, 1.25);
    await review.getByRole("button", {name: "Edit", exact: true}).click();
    await review.locator(".edit-accordion-trigger").filter({hasText: "Framing"}).click();
    await review.getByRole("button", {name: "Farther", exact: true}).click();
    await review.getByRole("button", {name: "Cancel Edit", exact: true}).first().click();
    await review.locator(".edit-discard-confirm").waitFor();
    assert.match(await review.locator(".edit-discard-confirm").textContent(), /Discard changes that are not saved/);
    await review.getByRole("button", {name: "Discard", exact: true}).click();
    assert.equal(await review.locator(".edit-panel").count(), 0);
    assert.deepEqual(errors, []);
    const mobile = await browser.newPage({viewport: {width: 390, height: 844}});
    const mobileErrors = [];
    mobile.on("pageerror", error => mobileErrors.push(error.message));
    await mobile.goto(`http://127.0.0.1:${server.address().port}`);
    const mobileReview = mobile.locator("#review-view");
    await mobile.locator(".step[data-view='review']").click();
    await mobileReview.locator(".clip-row").first().waitFor();
    await mobileReview.getByRole("button", {name: "Edit", exact: true}).click();
    const mobileGeometry = await mobileReview.evaluate(() => ({
      stage: getComputedStyle(document.querySelector(".review-stage")).position,
      stageTop: document.querySelector(".review-stage").getBoundingClientRect().top,
      panelTop: document.querySelector(".edit-panel").getBoundingClientRect().top,
      panelOverflow: getComputedStyle(document.querySelector(".edit-panel")).overflowY,
    }));
    assert.equal(mobileGeometry.stage, "sticky");
    assert.ok(mobileGeometry.panelTop > mobileGeometry.stageTop, "narrow Edit places options below the sticky video");
    assert.equal(mobileGeometry.panelOverflow, "auto");
    const mobilePlaybackRects = await mobileReview.locator(".edit-playback-transport > button").evaluateAll(elements => elements.map(element => {
      const rect = element.getBoundingClientRect();
      return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom};
    }));
    mobilePlaybackRects.forEach((left, index) => mobilePlaybackRects.slice(index + 1).forEach(right => {
      assert.equal(left.right > right.left && right.right > left.left && left.bottom > right.top && right.bottom > left.top, false, "narrow Review playback buttons do not overlap");
    }));
    assert.deepEqual(mobileErrors, []);
    await mobile.close();
    console.log(JSON.stringify({status: "passed", test_id: "PHASE4A-EDIT", checks: ["wide split layout keeps sidebar and video visible", "narrow sticky video and independently scrolling options", "editor playback controls do not overlap", "opened Captions and Trim groups stay in view", "accordion switching does not return to the headline", "ordered one-open accordion", "Simple/Advanced preference persists", "edit interactions preserve the video element", "Save & Done shows failure without closing", "Save & Done shows Saving and locks duplicate clicks", "Save & Done persists and closes on success", "Cancel Edit confirms unsaved changes", "no JavaScript errors"]}));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exit(1); });
