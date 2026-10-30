(() => {
  "use strict";
  const root = document.getElementById("queue");
  if (!root) return;
  const token = root.dataset.token;
  const lan = root.dataset.lan === "true";
  const headers = {"Content-Type":"application/json", "X-DC-Token":token};
  const node = (parent, tag, value) => {const result=document.createElement(tag); if(value!==undefined)result.textContent=String(value); parent.appendChild(result); return result;};
  const input = (parent,type,value) => {const result=node(parent,"input"); result.type=type; result.value=value ?? ""; return result;};
  const select = (parent, values, current) => {const result=node(parent,"select"); for(const value of values){const option=node(result,"option",value);option.value=value;}result.value=current;return result;};
  const post = async (path,payload) => {const response=await fetch(path,{method:"POST",headers,body:JSON.stringify(payload)}); const data=await response.json();if(!response.ok)throw Error(data.detail||"Request failed");return data;};
  const button = (parent,title,handler) => {const result=node(parent,"button",title);result.type="button"; result.addEventListener("click",handler);return result;};
  const show = async (records) => {
    root.replaceChildren();
    const blind=document.getElementById("label-mode").checked;
    for(const record of records){
      const card=node(root,"section"); const decision=record.decision||{};
      node(card,"h2",blind?record.id:`${record.id} · ${record.score} · ${record.archetype}`);
      node(card,"p",record.source?.title||"");
      if(!blind){for(const [component,value] of Object.entries(record.components||{})){const label=node(card,"div",`${component}: ${Number(value).toFixed(2)}`);const meter=node(label,"progress");meter.max=1;meter.value=value;}}
      node(card,"p",(record.integrity_flags||[]).map(flag=>`${flag.code}: ${flag.reason}`).join(" · ")).className="warning";
      node(card,"p",Object.entries(record.fairness?.shares||{}).map(([key,value])=>`${key}: ${Math.round(value*100)}%`).join(" · ")+" — speaking time, not correctness");
      node(card,"p",record.text||"");
       const video=node(card,"video");video.controls=true;video.preload="none";video.width=540;video.src=`/api/media/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/source`;window.DebateClipperVideoRegistry?.register(video);
      video.addEventListener("loadedmetadata",()=>{video.currentTime=record.start;},{once:true});
      const tools=node(card,"div");tools.className="tools";
      const headline=input(tools,"text",decision.headline||record.hook?.headline_options?.[0]);headline.maxLength=78;
      const option=select(tools,record.hook?.headline_options||[],headline.value);option.addEventListener("change",()=>{headline.value=option.value;});
      const fit=node(card,"p"); headline.addEventListener("change",async()=>{try{const result=await post("/api/fit",{headline:headline.value});fit.textContent=`${result.fit?"Fits":"Overflow"} · ${result.font_px}px · ${result.lines.length} lines`;}catch(error){fit.textContent=error.message;}});
      const start=input(tools,"number",decision.edits?.start??record.start);start.step="0.01";
      const end=input(tools,"number",decision.edits?.end??record.end);end.step="0.01";
      const captionMode=select(tools,["hormozi_glow","gravitas","karaoke_lite"],decision.caption_mode||"hormozi_glow");
      const layout=select(tools,["auto","dual","manual"],decision.layout||"auto");
      const palette=input(tools,"color",decision.palette||"#B4F83D");
      const crop=input(tools,"text",decision.crop?Object.values(decision.crop).join(","):"");crop.placeholder="Manual crop x,y,w,h";
      const labels=input(tools,"text",JSON.stringify(decision.speaker_labels||{}));labels.placeholder="Speaker labels JSON";
      const status=node(card,"p");status.className="status"; let boundary=0;
      const words=node(card,"div");words.className="words";for(const word of record.words||[]){button(words,word.text,()=>{if(boundary++%2===0){start.value=Math.max(0,word.start-.08).toFixed(3);video.currentTime=word.start;}else{end.value=(word.end+.25).toFixed(3);}status.textContent="Word-based trim selected; render guard checks neighboring speech.";});}
      const payload=(action)=>{const value={job_id:record.job_id,candidate_id:record.id,action,headline:headline.value,edits:{start:Number(start.value),end:Number(end.value)}};if(!lan){Object.assign(value,{layout:layout.value,palette:palette.value,caption_mode:captionMode.value,speaker_labels:JSON.parse(labels.value)});if(crop.value.trim()){const values=crop.value.split(",").map(Number);value.crop=Object.fromEntries(["x","y","w","h"].map((key,i)=>[key,values[i]]));}}return value;};
      const save=async(action)=>{try{await post("/api/decisions",payload(action));status.textContent=`${action} saved.`;}catch(error){status.textContent=error.message;throw error;}};
      button(tools,"Approve",()=>save("approve"));button(tools,"Reject",()=>save("reject"));
      if(!lan){button(tools,"Save edits",()=>save("save"));button(tools,"Render + export",async()=>{try{await save("approve");status.textContent="Rendering…";const result=await post("/api/render",{job_id:record.job_id,candidate_id:record.id,variants:1});status.textContent=result.status;video.src=`/api/media/${record.job_id}/${record.id}/clip`;video.preload="metadata";}catch(error){status.textContent=error.message;}});button(tools,"3 headline variants",async()=>{try{await save("approve");status.textContent="Rendering variants…";await post("/api/render",{job_id:record.job_id,candidate_id:record.id,variants:3});status.textContent="Variants ready.";}catch(error){status.textContent=error.message;}});}
      if(blind){const rating=select(tools,["would_post","as_is","trivial_trim","not_usable"],"would_post");button(tools,"Save golden label",async()=>{try{await post("/api/labels",{job_id:record.job_id,candidate_id:record.id,start:Number(start.value),end:Number(end.value),rating:rating.value});status.textContent="Label saved.";}catch(error){status.textContent=error.message;}});}
    }
  };
  let queue=[];
  const reload=async()=>{const response=await fetch("/api/jobs");const data=await response.json();queue=data.candidates||[];await show(queue);};
  document.getElementById("label-mode").addEventListener("change",()=>show(queue));
  document.getElementById("search-button").addEventListener("click",async()=>{const q=document.getElementById("search").value;const response=await fetch(`/api/search?q=${encodeURIComponent(q)}`);await show((await response.json()).candidates||[]);});
  setInterval(async()=>{try{const response=await fetch("/api/system");const data=await response.json();document.getElementById("system").textContent=`CPU ${data.cpu_percent??"?"}% · RAM ${data.ram_percent??"?"}%`;}catch{}},5000);
  reload().catch(error=>{root.textContent=error.message;});
})();
