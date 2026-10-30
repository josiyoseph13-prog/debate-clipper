/* Opt-in canvas editor. User names are rendered only as text/canvas text. */
window.DebateClipperVideoRegistry = window.DebateClipperVideoRegistry || (() => {
  const videos = new Set();
  const cleanup = () => [...videos].forEach(video => { if (!video.isConnected) videos.delete(video); });
  const stopAll = (unload = false) => {
    cleanup();
    videos.forEach(video => {
      video.pause();
      if (unload) { video.removeAttribute("src"); video.load(); }
    });
  };
  document.addEventListener("play", event => {
    cleanup();
    videos.forEach(video => { if (video !== event.target) video.pause(); });
  }, true);
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (!entry.isIntersecting) entry.target.pause(); }), {threshold: .08});
    window.__debateClipperVideoObserver = observer;
  }
  return {
    register(video) { videos.add(video); window.__debateClipperVideoObserver?.observe(video); return video; },
    stopAll,
  };
})();
(() => {
  "use strict";
  window.SpeakerFrame = {open: async (record, api) => {
    const {post, node, button, input, select, withToken, showMessage, addActivity, actionButton, refresh, renderReview} = api;
    const identity = {job_id: record.job_id, candidate_id: record.id};
    let seed;
    try { seed = await post("/api/speaker-frame/open", identity); }
    catch (error) { showMessage("error", "Could not open Speaker Frame", error.message); addActivity("Speaker Frame open failed", "error"); return; }
    const requestedLayout = {one: "single", blended: "blended", stacked: "stacked", duo: "duo"}[api.layoutHint];
    const initial = {enabled: true, layout: requestedLayout || (seed.auto.segments[0].mode === "DUAL" ? "stacked" : "single"), selected: "A", frame_t: 0, boxes: seed.suggestions, blend: {width: .18, position: .5, direction: "horizontal", swap: false}, duo: {style: "smart", full_after: 3, duo_after: .6}, voice_map: {}, overrides: [], shots: [], both_blended: false};
    let spec = structuredClone(seed.saved?.enabled ? seed.saved : initial), framing = seed.auto, changed = Boolean(seed.saved?.enabled), pending = 0, drag = null, stopped = false;
    spec.duo ||= structuredClone(initial.duo);
    const dialog = node(document.body, "dialog", undefined, "sf-dialog");
    node(dialog, "h2", "Speaker Frame"); node(dialog, "p", "Auto Reframe ran first. Fix its suggestions only if you need to. Names are labels you type.", "help");
    const guide = node(dialog, "section", undefined, "sf-guide");
    node(guide, "h3", "Start here");
    node(guide, "p", "Step 1 · Pick how you want it to look. Choose one person, both people, or Duo style.");
    node(guide, "p", "Step 2 · Check the boxes around each person. A box tells the video where a person is.");
    node(guide, "p", "Step 3 · Preview and save. Your changes appear in the live picture below.");
    const beginnerLabel = node(dialog, "label", "Beginner mode ", "sf-beginner-toggle");
    const beginnerMode = input(beginnerLabel, "checkbox"); beginnerMode.checked = true;
    const message = node(dialog, "p", "Suggested by Auto Reframe", "sf-message");
    const picker = node(dialog, "section", undefined, "sf-picker");
    const video = node(picker, "video"); video.hidden = true; video.preload = "auto"; video.playsInline = true; video.src = withToken(seed.picker_url || `/api/media/${record.job_id}/${record.id}/source`); window.DebateClipperVideoRegistry.register(video);
    const canvas = node(picker, "canvas"); canvas.width = seed.source.width; canvas.height = seed.source.height; canvas.className = "sf-source"; canvas.setAttribute("aria-label", "Draw, move, or resize speaker boxes on the source picture");
    const rawCanvas = document.createElement("canvas"); rawCanvas.width = seed.source.width; rawCanvas.height = seed.source.height;
    const slider = input(picker, "range", 0); slider.min = 0; slider.max = seed.duration; slider.step = .033; slider.setAttribute("aria-label", "Choose a frame");
    const timeLabel = node(picker, "p", "Frame 0.00 seconds");
    const playback = node(picker, "div", undefined, "control-grid");
    button(playback, "Play / pause", () => { if (video.paused) video.play().catch(error => showMessage("error", "Could not play", error.message)); else video.pause(); addActivity("Speaker Frame playback"); });
    node(picker, "p", "Draw up to two boxes around a face and upper body. Drag inside to move; drag the bottom-right corner to resize. The dashed white outline is Auto Reframe's crop.", "help");
    node(dialog, "h3", "Step 2 · Check the boxes around each person");
    const boxList = node(dialog, "div", undefined, "sf-box-list");
    const advanced = node(dialog, "details", undefined, "sf-advanced");
    node(advanced, "summary", "Advanced");
    const controls = node(advanced, "div", undefined, "sf-controls");
    const helpIcon = text => { const help = button(controls, "?", () => { message.textContent = text; message.className = "sf-message"; }, "sf-help"); help.title = text; help.setAttribute("aria-label", text); return help; };
    const layout = select(controls, ["single", "stacked", "blended", "auto", "duo"], spec.layout, {single: "One speaker", stacked: "Both (stacked)", blended: "Both (blended side-by-side)", auto: "Auto — switch by voice", duo: "Duo — like the reference"}); layout.setAttribute("aria-label", "Speaker Frame layout");
    const beginnerLayouts = node(dialog, "section", undefined, "sf-beginner-layouts");
    dialog.insertBefore(beginnerLayouts, advanced);
    node(beginnerLayouts, "h3", "Step 1 · Pick how you want it to look");
    node(beginnerLayouts, "p", "Choose a picture style. You can change it later in Advanced.", "help");
    const layoutCards = node(beginnerLayouts, "div", undefined, "sf-layout-cards");
    [["single", "One person", "Only the speaker"], ["blended", "Both blended", "A soft join"], ["stacked", "Both stacked", "One above the other"], ["duo", "Duo style", "Switches by voice"]].forEach(([value, label, note]) => {
      const card = button(layoutCards, undefined, () => { layout.value = value; layout.dispatchEvent(new Event("change")); [...layoutCards.children].forEach(item => item.classList.toggle("active", item.dataset.layout === value)); }, "sf-layout-card");
      card.dataset.layout = value;
      node(card, "i", undefined, `sf-layout-icon sf-${value}`);
      node(card, "strong", label);
      node(card, "small", note);
      card.classList.toggle("active", spec.layout === value);
    });
    layout.addEventListener("change", () => [...layoutCards.children].forEach(card => card.classList.toggle("active", card.dataset.layout === layout.value)));
    const selected = select(controls, ["A", "B"], spec.selected, {A: "Show Speaker A", B: "Show Speaker B"}); helpIcon("Choose which person's box the controls affect.");
    const blendWidth = input(controls, "range", spec.blend.width); blendWidth.min = .04; blendWidth.max = .35; blendWidth.step = .01; blendWidth.setAttribute("aria-label", "How soft the join between the two people is"); node(controls, "span", "How soft is the join between the two people?"); helpIcon("A softer join hides the line between people.");
    const join = input(controls, "range", spec.blend.position); join.min = .3; join.max = .7; join.step = .01; join.setAttribute("aria-label", "Move the soft join left or right"); helpIcon("Move the soft join left or right.");
    const direction = select(controls, ["horizontal", "vertical"], spec.blend.direction, {horizontal: "Side by side", vertical: "Top and bottom with soft fade"}); helpIcon("Choose side by side or top and bottom.");
    const swapLabel = node(controls, "label", "Swap sides "); const swap = input(swapLabel, "checkbox"); swap.checked = spec.blend.swap; helpIcon("Swap Person A and Person B.");
    const bothLabel = node(controls, "label", "Use blended when both talk "); const both = input(bothLabel, "checkbox"); both.checked = spec.both_blended; helpIcon("Use the blended view when both people talk.");
    const duoStyle = select(controls, ["always_duo", "always_full", "smart"], spec.duo.style, {always_duo: "Duo style: Always Duo", always_full: "Duo style: Always Full", smart: "Duo style: Smart (like reference)"}); duoStyle.setAttribute("aria-label", "Duo style"); helpIcon("Choose how Duo style switches between both people and one person.");
    const fullAfter = input(controls, "range", spec.duo.full_after); fullAfter.min = .5; fullAfter.max = 12; fullAfter.step = .1; fullAfter.setAttribute("aria-label", "When does it jump to one person?"); node(controls, "span", "When does it jump to one person?"); helpIcon("This is the shortest talking time before a full-screen jump.");
    const duoAfter = input(controls, "range", spec.duo.duo_after); duoAfter.min = 0; duoAfter.max = 5; duoAfter.step = .1; duoAfter.setAttribute("aria-label", "Shortest time on one shot"); node(controls, "span", "Shortest time on one shot"); helpIcon("This keeps the picture from flickering back and forth.");
    const voices = node(advanced, "section"); node(voices, "h3", "Which voice is which?");
    if (!seed.voices.length) node(voices, "p", seed.audio_note, "sf-warning");
    seed.voices.forEach(voice => { const row = node(voices, "div"); node(row, "span", voice.id); const audio = node(row, "audio"); audio.controls = true; audio.src = withToken(voice.url); const choice = select(row, ["", "A", "B"], spec.voice_map[voice.id] || "", {"": "Link this voice", A: "Speaker A", B: "Speaker B"}); choice.addEventListener("change", () => { if (choice.value) spec.voice_map[voice.id] = choice.value; else delete spec.voice_map[voice.id]; changed = true; update(); }); });
    node(dialog, "h3", "Step 3 · Preview and save");
    const preview = node(dialog, "canvas", undefined, "sf-preview"); preview.width = seed.canvas.w; preview.height = seed.canvas.h; preview.setAttribute("aria-label", "Debate Clipper live preview with safe area");
    const chrome = new Image(); chrome.src = withToken(seed.chrome_url); chrome.onload = () => draw();
    const timelineDetails = node(dialog, "details", undefined, "sf-advanced");
    node(timelineDetails, "summary", "Advanced timeline");
    const timeline = node(timelineDetails, "div", undefined, "sf-timeline"); timeline.setAttribute("aria-label", "Who is shown at each time");
    const fixes = node(timelineDetails, "div", undefined, "sf-controls");
    const rangeStart = input(fixes, "number", 0); rangeStart.min = 0; rangeStart.max = seed.duration; rangeStart.step = .1; rangeStart.setAttribute("aria-label", "Correction start");
    const rangeEnd = input(fixes, "number", seed.duration); rangeEnd.min = 0; rangeEnd.max = seed.duration; rangeEnd.step = .1; rangeEnd.setAttribute("aria-label", "Correction end");
    const rangeChoice = select(fixes, ["A", "B", "both", "wide"], "A", {A: "Speaker A", B: "Speaker B", both: "Both", wide: "Wide"});
    button(fixes, "Fix this time range", () => { const start = Number(rangeStart.value), end = Number(rangeEnd.value); spec.overrides = spec.overrides.filter(row => end <= row.start || start >= row.end); spec.overrides.push({start, end, choice: rangeChoice.value}); changed = true; update(); addActivity("Speaker Frame timeline corrected"); });
    button(fixes, "Clear timeline corrections", () => { spec.overrides = []; changed = true; update(); addActivity("Speaker Frame timeline reset"); });
    const cutList = node(timelineDetails, "section"); node(cutList, "h3", "Camera changes");
    if (!seed.camera_cuts.length) node(cutList, "p", "No camera cut detected in this clip. Camera-cut detection accuracy: Not measured.");
    seed.camera_cuts.forEach(t => button(cutList, `Camera changed here: ${t.toFixed(2)}s`, () => { seek(t + .1); message.textContent = "Camera changed. Check the boxes, then set them for this part."; }));
    button(cutList, "Set current boxes for this camera part", () => { const t = Math.max(0, ...seed.camera_cuts.filter(cut => cut <= Number(slider.value))); spec.shots = spec.shots.filter(row => row.t !== t); spec.shots.push({t, boxes: structuredClone(spec.boxes)}); changed = true; update(); addActivity("Speaker Frame camera-part boxes saved locally"); });
    const actions = node(dialog, "div", undefined, "primary-actions");
    const close = () => { stopped = true; clearTimeout(pending); video.pause(); video.removeAttribute("src"); video.load(); dialog.close(); dialog.remove(); };
    const save = button(actions, "Save", element => actionButton(element, "Saving…", async () => { try { spec.frame_t = Number(slider.value); const result = await post("/api/speaker-frame/save", {...identity, speaker_frame: spec}); record.decision = {...record.decision, speaker_frame: result.speaker_frame}; addActivity("Speaker Frame saved"); showMessage("success", "Speaker Frame saved for this clip.", "The renderer will use these boxes."); close(); await refresh(); renderReview(); } catch (error) { showMessage("error", "Could not save Speaker Frame", error.message); addActivity("Speaker Frame save failed", "error"); } }), "button-primary");
    button(actions, "Reset", () => { spec = structuredClone(initial); changed = false; framing = seed.auto; layout.value = spec.layout; selected.value = spec.selected; blendWidth.value = spec.blend.width; join.value = spec.blend.position; direction.value = spec.blend.direction; swap.checked = false; both.checked = false; duoStyle.value = spec.duo.style; fullAfter.value = spec.duo.full_after; duoAfter.value = spec.duo.duo_after; listBoxes(); drawTimeline(); draw(); message.textContent = "Reset to Auto Reframe's suggestions. Save to apply."; addActivity("Speaker Frame reset locally"); });
    button(actions, "Cancel", () => { addActivity("Speaker Frame cancelled"); close(); });
    button(actions, "Reset to Auto", element => actionButton(element, "Saving…", async () => { try { await post("/api/speaker-frame/save", {...identity, speaker_frame: {enabled: false}}); record.decision = {...record.decision, speaker_frame: {enabled: false}}; addActivity("Reset Speaker Frame to Auto"); showMessage("success", "Reset to Auto", "The automatic framing is back for this clip."); close(); await refresh(); renderReview(); } catch (error) { showMessage("error", "Could not reset to Auto", error.message); } }));
    button(actions, "Re-run Auto Reframe", element => actionButton(element, "Reframing…", async () => { let choice = "keep"; if (record.decision?.speaker_frame?.enabled) { choice = window.prompt("Keep your Speaker Frame changes or replace them? Type keep or replace.", "keep"); if (!["keep", "replace"].includes(choice)) return; } try { seed = await post("/api/speaker-frame/open", {...identity, rerun: true, choice}); framing = seed.auto; if (choice === "replace") { record.decision = {...record.decision, speaker_frame: {enabled: false}}; spec = structuredClone({...initial, boxes: seed.suggestions}); changed = false; listBoxes(); } update(); addActivity(`Auto Reframe re-run: ${choice}`); showMessage("success", "Auto Reframe ready", choice === "keep" ? "Your saved Speaker Frame changes were kept." : "Speaker Frame changes were replaced."); } catch (error) { showMessage("error", "Could not re-run Auto Reframe", error.message); } }));
    function seek(t) { video.pause(); slider.value = Math.max(0, Math.min(seed.duration, t)); video.currentTime = (seed.picker_url ? 0 : seed.start) + Number(slider.value); timeLabel.textContent = `Frame ${Number(slider.value).toFixed(2)} seconds`; }
    function listBoxes() { boxList.replaceChildren(); spec.boxes.forEach(box => { const row = node(boxList, "div", undefined, "sf-box-row"); const name = input(row, "text", box.name); name.maxLength = 40; name.setAttribute("aria-label", `Name for Speaker ${box.id}`); name.addEventListener("change", () => { box.name = name.value; changed = true; update(); }); node(row, "span", `${box.id}${box.suggested ? " — Suggested by Auto Reframe" : " — edited by you"}`); button(row, "Select", () => { spec.selected = box.id; selected.value = box.id; changed = true; draw(); addActivity(`Selected Speaker ${box.id}`); }); button(row, "Delete", () => { spec.boxes = spec.boxes.filter(b => b.id !== box.id); changed = true; listBoxes(); update(); addActivity(`Deleted Speaker ${box.id}`); }); const label = node(row, "label", "Off screen "); const off = input(label, "checkbox"); off.checked = Boolean(box.offscreen); off.addEventListener("change", () => { box.offscreen = off.checked; changed = true; update(); addActivity(`Speaker ${box.id} off-screen setting changed`); }); }); }
    function drawTimeline() { timeline.replaceChildren(); (framing.segments || []).forEach(segment => { const label = segment.choice || ({SINGLE: "A", DUAL: "Both", BLEND: "Both", WIDE: "Wide"}[segment.mode]); const bar = button(timeline, `${label} ${segment.t0.toFixed(1)}–${segment.t1.toFixed(1)}s`, () => { seek(segment.t0 + .01); rangeStart.value = segment.t0; rangeEnd.value = segment.t1; rangeChoice.value = ["A", "B", "both", "wide"].includes(segment.choice) ? segment.choice : "both"; addActivity("Speaker Frame timeline moment selected"); }, `sf-bar sf-${segment.choice || segment.mode}`); bar.style.flexGrow = Math.max(.1, segment.t1 - segment.t0); }); }
    function update() { clearTimeout(pending); pending = setTimeout(async () => { save.disabled = true; message.textContent = "Rendering preview…"; try { const result = await post("/api/speaker-frame/preview", {...identity, speaker_frame: spec}); if (stopped) return; framing = result.framing; const warnings = framing.debug.warnings.map(row => row.text); message.textContent = warnings.length ? [...new Set(warnings)].join(" ") : "Live preview ready. Face safety will be measured on export."; message.className = warnings.length ? "sf-warning" : "sf-message"; drawTimeline(); draw(); } catch (error) { message.textContent = error.message; message.className = "sf-warning"; } finally { if (!stopped) save.disabled = false; } }, 180); }
    function cropDraw(ctx, segment) {
      const f = seed.feed;
      if (segment.mode === "WIDE") { const scale = Math.min(f.w / seed.source.width, f.h / seed.source.height); ctx.fillStyle = "#555"; ctx.fillRect(0, 0, f.w, f.h); ctx.drawImage(rawCanvas, (f.w - seed.source.width * scale) / 2, (f.h - seed.source.height * scale) / 2, seed.source.width * scale, seed.source.height * scale); return; }
      const rects = segment.regions;
      if (segment.mode !== "BLEND") { rects.forEach((r, i) => ctx.drawImage(rawCanvas, r.x, r.y, r.w, r.h, 0, i * f.h / rects.length, f.w, f.h / rects.length)); return; }
      const blend = segment.blend, horizontal = blend.direction === "horizontal", size = horizontal ? f.w : f.h, joinAt = Math.round(size * blend.position), band = Math.max(2, Math.round(size * blend.width)), left = Math.max(1, joinAt - Math.floor(band / 2)), right = Math.min(size - 1, left + band);
      const slots = horizontal ? [[0, 0, right, f.h], [left, 0, f.w - left, f.h]] : [[0, 0, f.w, right], [0, left, f.w, f.h - left]];
      const layers = rects.map((r, i) => { const c = document.createElement("canvas"); c.width = f.w; c.height = f.h; c.getContext("2d").drawImage(rawCanvas, r.x, r.y, r.w, r.h, ...slots[i]); return c; });
      ctx.drawImage(layers[0], 0, 0); const mask = layers[1].getContext("2d"); mask.globalCompositeOperation = "destination-in"; const gradient = horizontal ? mask.createLinearGradient(left, 0, right, 0) : mask.createLinearGradient(0, left, 0, right); for (let i = 0; i <= 32; i++) { const u = i / 32; gradient.addColorStop(u, `rgba(0,0,0,${u * u * (3 - 2 * u)})`); } mask.fillStyle = gradient; mask.fillRect(0, 0, f.w, f.h); ctx.drawImage(layers[1], 0, 0);
    }
    function draw() {
      if (!video.videoWidth || video.readyState < 2) return;
      const t = Number(slider.value), ctx = canvas.getContext("2d");
      rawCanvas.getContext("2d").drawImage(video, 0, 0, rawCanvas.width, rawCanvas.height); ctx.drawImage(rawCanvas, 0, 0);
      const auto = structuredClone(seed.auto.segments.find(s => s.t0 <= t && t < s.t1) || seed.auto.segments[0]);
      if (auto.mode === "SINGLE" && seed.auto.path) {
        const path = seed.auto.path;
        const pair = path.slice(1).map((p, i) => [path[i], p]).find(([a, b]) => a.t <= t && t <= b.t && b.t > a.t);
        if (pair) { const [a, b] = pair, weight = (t - a.t) / (b.t - a.t); auto.regions = [Object.fromEntries(["x", "y", "w", "h"].map(k => [k, a[k] + weight * (b[k] - a[k])]))]; }
      }
      ctx.lineWidth = Math.max(2, canvas.width / 300); ctx.setLineDash([12, 8]); ctx.strokeStyle = "white"; auto.regions.forEach(r => ctx.strokeRect(r.x, r.y, r.w, r.h)); ctx.setLineDash([]);
      spec.boxes.forEach(box => { ctx.strokeStyle = box.id === "A" ? "#B4F83D" : "#4DD0E2"; ctx.strokeRect(box.x, box.y, box.w, box.h); ctx.fillStyle = ctx.strokeStyle; ctx.fillRect(box.x + box.w - 15, box.y + box.h - 15, 15, 15); ctx.font = `${Math.max(16, canvas.width / 55)}px sans-serif`; ctx.fillText(`${box.id}: ${box.name}`, box.x + 6, box.y + 30); });
      const out = preview.getContext("2d"); out.fillStyle = "white"; out.fillRect(0, 0, preview.width, preview.height); if (chrome.complete && chrome.naturalWidth) out.drawImage(chrome, 0, 0);
      const segment = changed ? framing.segments.find(s => s.t0 <= t && t < s.t1) || framing.segments[0] : auto;
      const feedCanvas = document.createElement("canvas"); feedCanvas.width = seed.feed.w; feedCanvas.height = seed.feed.h; cropDraw(feedCanvas.getContext("2d"), segment); out.drawImage(feedCanvas, seed.feed.x, seed.feed.y);
      out.strokeStyle = "#B4F83D"; out.setLineDash([12, 8]);
      const panels = segment.mode === "DUAL" ? [[0, 0, seed.feed.w, seed.feed.h / 2], [0, seed.feed.h / 2, seed.feed.w, seed.feed.h / 2]] : [[0, 0, seed.feed.w, seed.feed.h]];
      panels.forEach(([x, y, w, h]) => out.strokeRect(seed.feed.x + x + w * .02, seed.feed.y + y + h * .02, w * .96, h * .96)); out.setLineDash([]);
    }
    function pointer(event) { const r = canvas.getBoundingClientRect(); return {x: Math.max(0, Math.min(canvas.width, (event.clientX - r.left) * canvas.width / r.width)), y: Math.max(0, Math.min(canvas.height, (event.clientY - r.top) * canvas.height / r.height))}; }
    canvas.addEventListener("pointerdown", event => { video.pause(); const p = pointer(event); const box = [...spec.boxes].reverse().find(b => p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h); if (box) drag = {kind: Math.abs(p.x - box.x - box.w) < 35 && Math.abs(p.y - box.y - box.h) < 35 ? "resize" : "move", box, x: p.x, y: p.y, old: structuredClone(box)}; else if (spec.boxes.length < 2) { const id = spec.boxes.some(b => b.id === "A") ? "B" : "A"; const b = {id, name: `Speaker ${id}`, x: p.x, y: p.y, w: 8, h: 8}; spec.boxes.push(b); drag = {kind: "draw", box: b, x: p.x, y: p.y}; } else { message.textContent = "Up to two boxes. Delete one before drawing another."; return; } canvas.setPointerCapture(event.pointerId); });
    canvas.addEventListener("pointermove", event => { if (!drag) return; const p = pointer(event), b = drag.box; delete b.face; b.suggested = false; if (drag.kind === "move") { b.x = Math.max(0, Math.min(canvas.width - b.w, drag.old.x + p.x - drag.x)); b.y = Math.max(0, Math.min(canvas.height - b.h, drag.old.y + p.y - drag.y)); } else if (drag.kind === "resize") { b.w = Math.max(8, Math.min(canvas.width - b.x, drag.old.w + p.x - drag.x)); b.h = Math.max(8, Math.min(canvas.height - b.y, drag.old.h + p.y - drag.y)); } else { b.x = Math.min(p.x, drag.x); b.y = Math.min(p.y, drag.y); b.w = Math.max(8, Math.abs(p.x - drag.x)); b.h = Math.max(8, Math.abs(p.y - drag.y)); } changed = true; draw(); });
    canvas.addEventListener("pointerup", () => { if (drag) { addActivity(`Speaker ${drag.box.id} box edited`); drag = null; listBoxes(); update(); } });
    [layout, selected, direction, swap, both, duoStyle].forEach(control => control.addEventListener("change", () => { spec.layout = layout.value; spec.selected = selected.value; spec.blend.direction = direction.value; spec.blend.swap = swap.checked; spec.both_blended = both.checked; spec.duo.style = duoStyle.value; changed = true; update(); addActivity("Speaker Frame layout changed"); }));
    [blendWidth, join].forEach(control => control.addEventListener("input", () => { spec.blend.width = Number(blendWidth.value); spec.blend.position = Number(join.value); changed = true; update(); }));
    [fullAfter, duoAfter].forEach(control => control.addEventListener("input", () => { spec.duo.full_after = Number(fullAfter.value); spec.duo.duo_after = Number(duoAfter.value); changed = true; update(); }));
    slider.addEventListener("input", () => seek(Number(slider.value))); video.addEventListener("loadedmetadata", () => seek(spec.frame_t || 0)); video.addEventListener("seeked", draw);
    video.addEventListener("loadeddata", draw);
    video.addEventListener("timeupdate", () => { if (!video.paused) { if (video.currentTime >= (seed.picker_url ? seed.duration : seed.end)) video.pause(); slider.value = Math.max(0, video.currentTime - (seed.picker_url ? 0 : seed.start)); timeLabel.textContent = `Frame ${Number(slider.value).toFixed(2)} seconds`; draw(); } });
    beginnerMode.addEventListener("change", () => { advanced.open = !beginnerMode.checked; timelineDetails.open = !beginnerMode.checked; });
    dialog.addEventListener("cancel", event => { event.preventDefault(); close(); }); listBoxes(); drawTimeline(); dialog.showModal(); if (changed) update(); addActivity("Speaker Frame opened");
  }};
})();
