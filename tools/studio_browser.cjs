"use strict";
const {chromium}=require("playwright");
const assert=require("node:assert/strict");
const fs=require("node:fs");
(async()=>{
  const browserPath=[
    "C:/Users/pc/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe",
    "C:/Users/pc/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe",
  ].find(candidate=>fs.existsSync(candidate));
  const browser=await chromium.launch({headless:true,...(browserPath?{executablePath:browserPath}:{})});
  try {
    const page=await browser.newPage({viewport:{width:390,height:844}});
     const errors=[];
     page.on("pageerror",error=>errors.push(error.message));
    const base=process.argv[2];
    const token=process.argv[3] || "";
    const url=path=>`${base}${path}${token ? `?token=${encodeURIComponent(token)}` : ""}`;

    await page.goto(url("/classic"));
    await page.locator("#queue section").first().waitFor();
    const card=page.locator("#queue section").first();
    const classicText=await card.textContent();
    const xssFixturePresent=classicText.includes("<img src=x");
    if (xssFixturePresent) { assert.equal(await page.evaluate(()=>window.__xss),undefined); assert.match(classicText,/<img src=x/); }
    await card.getByRole("button",{name:"Save edits",exact:true}).click();
    await card.locator(".status").filter({hasText:"save saved"}).waitFor();
    await card.getByRole("button",{name:"Approve",exact:true}).click();
    await card.locator(".status").filter({hasText:"approve saved"}).waitFor();
    await page.locator("#label-mode").check();
    await page.getByRole("button",{name:"Save golden label",exact:true}).first().click();
    await page.locator(".status").filter({hasText:"Label saved"}).first().waitFor();

    await page.goto(url("/"));
    await page.locator("#home-view .add-box").waitFor();
    assert.match(await page.locator("#home-view").textContent(),/Paste a YouTube link or drop a video file here/);
    assert.match(await page.locator("#home-view").textContent(),/More options/);
    await page.locator(".step[data-view='review']").click();
    const review=page.locator("#review-view");
    await review.locator(".clip-row").first().waitFor();
    const reviewText=await review.textContent();
     assert.doesNotMatch(reviewText,/c_[a-z0-9]{8,}/i);
     assert.equal(await review.locator("video").count(),1);
     assert.equal(await review.locator(".review-actions > button").count(),4);
     await review.locator(".review-actions").scrollIntoViewIfNeeded();
     const normalReviewOverlap=await page.evaluate(()=>{
       const stage=document.querySelector("#review-view .review-stage").getBoundingClientRect();
       const actions=document.querySelector("#review-view .review-actions").getBoundingClientRect();
       return stage.right>actions.left && actions.right>stage.left && stage.bottom>actions.top && actions.bottom>stage.top;
     });
     assert.equal(normalReviewOverlap,false,"Review video stage does not cover Review action buttons");
     await review.getByRole("button",{name:"Edit",exact:true}).click();
     assert.equal(await review.locator(".review-layout.editing").count(),1);
     await review.locator(".review-actions").scrollIntoViewIfNeeded();
     const editReviewOverlap=await page.evaluate(()=>{
       const stage=document.querySelector("#review-view .review-stage").getBoundingClientRect();
       const actions=document.querySelector("#review-view .review-actions").getBoundingClientRect();
       const overlaps=stage.right>actions.left && actions.right>stage.left && stage.bottom>actions.top && actions.bottom>stage.top;
       return {overlaps, stageZ:Number(getComputedStyle(document.querySelector("#review-view .review-stage")).zIndex)||0, actionsZ:Number(getComputedStyle(document.querySelector("#review-view .review-actions")).zIndex)||0};
     });
     if(editReviewOverlap.overlaps) assert.ok(editReviewOverlap.actionsZ>editReviewOverlap.stageZ,"Edit Review buttons render above the sticky video stage");
     await review.locator(".edit-headline-field input").fill("Browser headline");
     await review.locator(".edit-accordion-trigger").filter({hasText:"Trim"}).evaluate(element=>element.click());
     await review.locator(".trim-time-start").fill("2");
     await review.locator(".trim-time-start").dispatchEvent("change");
     await review.locator(".trim-time-end").fill("8");
     await review.locator(".trim-time-end").dispatchEvent("change");
     assert.match(await review.locator(".trim-summary").textContent(),/0:06/);
      assert.equal(await review.getByRole("button",{name:"Save & Done",exact:true}).count(),2);
      await review.getByRole("button",{name:"Save & Done",exact:true}).first().click();
     await page.waitForFunction(() => !document.querySelector("#review-view .edit-panel"));
     await review.getByRole("button",{name:"Edit",exact:true}).click();
     assert.equal(await review.locator(".edit-headline-field input").inputValue(),"Browser headline");
     await review.locator(".edit-accordion-trigger").filter({hasText:"Trim"}).evaluate(element=>element.click());
     assert.equal(await review.locator(".trim-time-start").inputValue(),"2.00");
     assert.equal(await review.locator(".trim-time-end").inputValue(),"8.00");
     await review.getByRole("button",{name:"Cancel Edit",exact:true}).first().evaluate(element=>element.click());
    await page.locator("#review-view .review-actions").waitFor();
    assert.match(await page.locator("#review-view").textContent(),/Approve/,await page.locator("#review-view").textContent());
    await page.locator("#review-view .review-actions").getByRole("button",{name:/^Approve/}).click();
    await page.locator("#app-message").filter({hasText:"Approved"}).waitFor();
    await page.locator(".step[data-view='export']").click();
    await page.locator("#export-view").filter({hasText:/Approve a clip|finished videos/}).waitFor();
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({status:"passed",viewport:[390,844],checks:[xssFixturePresent?"text-node XSS inert":"XSS fixture not present in current queue","classic save edits","classic approve","classic blind label action","real candidate review list","single selected video","side-by-side edit mode","four review actions","plain-language export view","no JavaScript errors"]}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
