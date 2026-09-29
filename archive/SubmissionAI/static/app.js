"use strict";
const $ = (id) => document.getElementById(id);
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const state = {settings:null, packages:[], runs:[], package:null, run:null, memories:{active:[],stale:[]}, source:null, busy:false, tab:"review"};
const nodes = [
  ["prepare", "Recall & prepare", "Load study memory and compare source versions."],
  ["endpoint_alignment", "Check endpoint timing", "Compare the protocol and statistical analysis plan."],
  ["referenced_documents", "Check document coverage", "Verify each reference against the complete inventory."],
  ["finalize", "Preserve the review", "Save evidence, findings, and an auditable record."]
];

async function api(path, method="GET", data) {
  const token = sessionStorage.getItem("continuity-token");
  const response = await fetch(path, {method, headers:{...(data !== undefined ? {"Content-Type":"application/json"}:{}), ...(token ? {Authorization:`Bearer ${token}`}:{})}, body:data !== undefined ? JSON.stringify(data) : undefined});
  let body;
  try { body = await response.json(); } catch { throw new Error("The server did not return a valid response. Check that it is running."); }
  if (!response.ok) {
    if (response.status === 401) { if (!$('connection-dialog').open) $('connection-dialog').showModal(); }
    const detail = Array.isArray(body.detail) ? body.detail.map(d => `${d.loc?.slice(1).join(".") || "Package"}: ${d.msg}`).join("; ") : body.detail;
    throw new Error(detail || "The request could not be completed.");
  }
  return body;
}

function message(text, success=false) {
  $("message").textContent = text;
  $("message").className = `message${success ? " success" : ""}${text ? "" : " hidden"}`;
}

async function task(fn) {
  if (state.busy) return;
  state.busy = true; message(""); document.body.classList.add("busy"); renderControls();
  try { await fn(); } catch (error) { message(error.message); }
  finally { state.busy = false; document.body.classList.remove("busy"); renderControls(); }
}

function switchTab(tab) {
  state.tab = tab;
  for (const name of ["review","evidence","history"]) $(name+"-view").classList.toggle("hidden", name !== tab);
  document.querySelectorAll("[data-tab]").forEach(button => {button.classList.toggle("active", button.dataset.tab === tab); if (button.hasAttribute("role")) button.setAttribute("aria-selected", button.dataset.tab === tab ? "true" : "false");});
  $("breadcrumb").textContent = {review:"Review workspace",evidence:"Evidence library",history:"Review history"}[tab];
}

async function refreshLists() {
  [state.packages, state.runs] = await Promise.all([api("/api/packages"), api("/api/runs")]);
  renderPackages(); renderHistory();
}

async function selectPackage(id, run=null) {
  state.package = await api(`/api/packages/${encodeURIComponent(id)}`);
  state.memories = await api(`/api/packages/${encodeURIComponent(id)}/memory`);
  state.run = run;
  state.source = null;
  localStorage.setItem("continuity-package", id);
  if (run) localStorage.setItem("continuity-run", run.id); else localStorage.removeItem("continuity-run");
  renderAll();
}

function renderControls() {
  const hasPackage = !!state.package, paused = state.run && !["completed","ready"].includes(state.run.status);
  $("run-button").disabled = !hasPackage || state.busy;
  $("step-button").disabled = !hasPackage || state.busy;
  $("run-button").textContent = state.busy ? "Working…" : paused ? "Resume review →" : state.run?.status === "completed" ? "Review again →" : "Start review →";
  $("step-button").textContent = paused ? "Next checkpoint" : "Run one step";
  $("add-memory").disabled = !hasPackage || state.busy;
  $("export-button").disabled = !state.run || state.busy;
  $("full-review-button").disabled = !hasPackage || state.busy || (state.run && state.run.status !== "completed");
  ["load-demo","import-button","import-sidebar","sample-version","refresh-history"].forEach(id => $(id).disabled = state.busy);
}

function renderPackages() {
  $("package-list").innerHTML = state.packages.length ? state.packages.map(p => `<button class="package-item ${p.id === state.package?.id ? "active" : ""}" data-package="${escapeHTML(p.id)}"><span class="package-dot"></span><b>${escapeHTML(p.study_id)}</b><small>v${escapeHTML(p.version)}</small></button>`).join("") : '<p class="sidebar-empty">Your first study starts here.</p>';
}

function renderPackage() {
  const p = state.package;
  $("package-version").textContent = p ? `VERSION ${p.version}` : "NO PACKAGE";
  if (p) $("package-heading").innerHTML = `<span class="folder-icon">▱</span><div><h2>${escapeHTML(p.study_id)} <span class="muted">/</span> Document review</h2><p>${p.documents.length} source documents · Immutable package version · ${escapeHTML(p.id.slice(0,8))}</p></div>`;
  $("document-count").textContent = p?.documents.length || 0;
}

function renderWorkflow() {
  const done = state.run?.state.completed_nodes || [];
  const next = state.run?.next_nodes?.[0];
  $("workflow").innerHTML = nodes.map(([id,title,description],i) => `<div class="workflow-step ${done.includes(id) ? "complete" : next === id ? "next" : ""}"><div class="step-number">${done.includes(id) ? "✓" : `0${i+1}`}</div><div class="step-copy"><h3>${title}</h3><p>${description}</p></div><span class="step-status">${done.includes(id) ? "SAVED" : next === id ? "UP NEXT" : ""}</span></div>`).join("");
  const status = state.run?.status || "neutral";
  $("run-status").className = `status ${status}`;
  $("run-status").textContent = {neutral:"Ready to start",ready:"Ready to start",paused:"Checkpoint saved",running:"In progress",completed:state.run?.state.objective_status === "needs_input" ? "Needs input" : "Review complete",failed:"Interrupted"}[status] || status;
  $("checkpoint-summary").textContent = state.run?.checkpoint_id ? `◇ Saved checkpoint · ${state.run.checkpoint_id.slice(-8)}` : "◇ Progress is saved after every step.";
  if (state.run?.error) message(state.run.error);
}

function renderFindings() {
  const entries = Object.values(state.run?.state.results || {});
  $("findings-count").textContent = `${entries.length} of 2 checks completed`;
  if (!entries.length) {
    $("findings").innerHTML = '<div class="empty-state"><div class="empty-symbol">⌕</div><h3>Your findings will appear here.</h3><p>Each conclusion is checked against the current source.<br>Missing evidence stays an open question.</p></div>';
    return;
  }
  $("findings").innerHTML = entries.map(f => {
    const label = f.transition === "unchanged" ? (f.status === "open" ? "Still open" : "Still clear") : {new:"Open finding",clear:"Verified clear",resolved:"Resolved",reopened:"Reopened",unresolved:"Needs evidence"}[f.transition];
    return `<article class="finding"><div class="finding-heading"><h3>${escapeHTML(f.title)}</h3><span class="status ${escapeHTML(f.status)}">${label}</span></div><p>${escapeHTML(f.explanation)}</p><div class="citations">${f.citations.map((c,i) => `<button class="citation" data-check="${escapeHTML(f.check_id)}" data-citation="${i}" title="${escapeHTML(c.quote)}">▤ ${escapeHTML(c.document_id)}${f.citations.filter(other=>other.document_id===c.document_id).length>1 ? ` · ${i+1}` : ""} ↗</button>`).join("")}</div><div class="finding-meta"><span>${f.status === "unresolved" ? "Human review needed" : "Source verified"}</span><span>·</span>${f.reused ? '<span class="reused">↺ Reused from prior review</span>' : '<span>Checked this run</span>'}${f.memory_ids.length ? `<span>· ${f.memory_ids.length} ${f.memory_ids.length===1?"memory":"memories"} recalled</span>` : ""}</div></article>`;
  }).join("");
}

function renderSource() {
  const source = state.source;
  if (!source || !state.package) {
    $("source-content").innerHTML = '<div class="source-empty"><span>▤</span><h3>See the source, not just the answer.</h3><p>Select a citation to inspect its exact passage in the current document.</p></div>';
    return;
  }
  const doc = state.package.documents.find(d => d.id === source.document_id);
  if (!doc) return;
  const index = source.quote ? doc.text.indexOf(source.quote) : -1;
  const contents = index >= 0 ? escapeHTML(doc.text.slice(0,index)) + `<mark>${escapeHTML(source.quote)}</mark>` + escapeHTML(doc.text.slice(index+source.quote.length)) : escapeHTML(doc.text);
  $("source-content").innerHTML = `<h3 class="source-title">${escapeHTML(doc.title)}</h3><div class="source-meta">${escapeHTML(doc.id)} · Version ${escapeHTML(state.package.version)}<br>Source hash ${doc.hash.slice(0,16)}</div><pre class="source-text">${contents}</pre><div class="source-foot"><span>✓</span>${index >= 0 ? "Exact quote verified against this version" : "Original document · Unmodified source"}</div><button class="text-button source-note" id="source-note">Add a note from this source ＋</button>`;
  $("source-content").querySelector("mark")?.scrollIntoView({block:"nearest",behavior:"smooth"});
}

function renderMemory() {
  $("memory-count").textContent = `${state.memories.active.length} ${state.memories.active.length===1?"NOTE":"NOTES"}`;
  $("memories").innerHTML = state.memories.active.length ? state.memories.active.map(m => `<div class="memory-item">${escapeHTML(m.summary)}<small>✓ Approved · ${escapeHTML(m.document_id)}${m.kind === "document_alias" ? ` · Alias: ${escapeHTML(m.alias)}` : ""}</small><button data-revoke="${escapeHTML(m.id)}">Revoke note</button></div>`).join("") : '<p class="memory-empty">No corrections yet.<br>Keep the reasoning that matters for the next review.</p>';
  if (state.memories.stale.length) $("memories").innerHTML += `<p class="stale-note">${state.memories.stale.length} previous note(s) excluded because their source changed or is missing.</p>`;
}

function renderMetrics() {
  const metrics = state.run?.state.metrics;
  $("metrics").innerHTML = `<span>Completed steps</span><b>${state.run?.state.completed_nodes.length || 0} / 4</b><span>Reused checks</span><b>${metrics?.checks_reused || 0}</b><span>Model calls</span><b>${metrics?.model_calls || 0}</b><span>Evidence searches</span><b>${metrics?.retrieval_calls || 0}</b><span>Active check time</span><b>${metrics ? (metrics.active_ms < 1000 ? `${metrics.active_ms.toFixed(1)} ms` : `${(metrics.active_ms/1000).toFixed(2)} s`) : "—"}</b>`;
}

function renderTrace() {
  const events = state.run?.state.events || [];
  $("event-count").textContent = `${events.length} ${events.length===1?"event":"events"}`;
  $("trace").innerHTML = events.length ? events.map(event => `<div class="trace-event"><time>${new Date(event.at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"})}</time><strong>${escapeHTML(event.node.replaceAll("_"," "))}</strong><div>${escapeHTML(event.detail)}</div>${(event.trace || []).map(t => `<div class="trace-tool">↳ ${escapeHTML(t.tool)}: ${escapeHTML(t.detail)}${t.query ? `<br>Query: ${escapeHTML(t.query)}` : ""}</div>`).join("")}</div>`).join("") : '<p class="memory-empty">A timestamped record of each completed step will appear here.</p>';
}

function renderEvidence() {
  $("evidence-list").innerHTML = state.package ? state.package.documents.map(doc => `<article class="document-card card"><div class="card-label">${escapeHTML(doc.kind)}<span class="subtle-tag">v${escapeHTML(state.package.version)}</span></div><h3>${escapeHTML(doc.title)}</h3><p>${escapeHTML(doc.id)} · ${doc.text.length.toLocaleString()} characters</p><pre class="source-text">${escapeHTML(doc.text)}</pre><button class="text-button" data-source="${escapeHTML(doc.id)}">Inspect document ↗</button></article>`).join("") : '<div class="empty-state"><h3>No source documents yet.</h3><p>Load a sample package in the review workspace, or import your own JSON package.</p></div>';
}

function renderHistory() {
  $("history-count").textContent = state.runs.length;
  $("history-list").innerHTML = state.runs.length ? state.runs.map(run => `<article class="history-item"><span class="folder-icon">↺</span><div class="history-copy"><h3>${escapeHTML(run.study_id)} · Version ${escapeHTML(run.version)}</h3><p>${new Date(run.created_at).toLocaleString()} · ${escapeHTML(run.id.slice(0,8))}</p></div><span class="status ${escapeHTML(run.status)}">${escapeHTML(run.status)}</span><div class="metrics-small">${run.metrics.checks_reused} checks reused<br>${run.metrics.model_calls} model calls</div><button class="button secondary small" data-run="${escapeHTML(run.id)}">${run.status === "completed" ? "View review" : "Open checkpoint"} ↗</button></article>`).join("") : '<div class="empty-state"><h3>Your history starts with the first review.</h3><p>Reviews and checkpoints survive app restarts.</p></div>';
}

function renderAll() {renderPackages();renderPackage();renderWorkflow();renderFindings();renderSource();renderMemory();renderMetrics();renderTrace();renderEvidence();renderHistory();renderControls();}

async function execute(mode, forceFull=false) {
  if (!state.run || state.run.status === "completed" || forceFull) state.run = await api("/api/runs","POST",{package_id:state.package.id,force_full:forceFull});
  localStorage.setItem("continuity-run", state.run.id);
  renderAll();
  const runId=state.run.id;
  let polling=true;
  const timer = setInterval(async () => {
    try { const current = await api(`/api/runs/${runId}`); if(polling && state.run?.id===runId){state.run=current;renderWorkflow();renderFindings();renderMetrics();renderTrace();} } catch {}
  }, 900);
  try {const completed=await api(`/api/runs/${runId}/execute`,"POST",{mode});polling=false;state.run=completed;}
  finally {polling=false;clearInterval(timer);}
  await refreshLists(); renderAll();
}

function openMemory() {
  if (!state.package) return;
  $("memory-form").reset(); $("memory-error").textContent="";
  $("memory-document").innerHTML = state.package.documents.map(d => `<option value="${escapeHTML(d.id)}">${escapeHTML(d.title)} · ${escapeHTML(d.id)}</option>`).join("");
  if (state.source) {$("memory-document").value = state.source.document_id; $("memory-quote").value = state.source.quote || "";}
  $("memory-dialog").showModal();
}

function download(data, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)], {type:"application/json"}));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
}

document.addEventListener("click", event => {
  const button = event.target.closest("button"); if (!button) return;
  if (button.dataset.tab) switchTab(button.dataset.tab);
  if (button.dataset.close) $(button.dataset.close).close();
  if (button.dataset.package) task(async () => {await selectPackage(button.dataset.package);switchTab("review");});
  if (button.dataset.run) task(async () => {const run = await api(`/api/runs/${button.dataset.run}`);await selectPackage(run.package_id,run);switchTab("review");});
  if (button.dataset.check) {const f = state.run.state.results[button.dataset.check];state.source=f.citations[Number(button.dataset.citation)];renderSource();}
  if (button.dataset.source) {state.source={document_id:button.dataset.source,quote:""};switchTab("review");renderSource();}
  if (button.id === "source-note") openMemory();
  if (button.dataset.revoke) task(async () => {await api(`/api/memory/${button.dataset.revoke}/revoke`,"POST");state.memories=await api(`/api/packages/${state.package.id}/memory`);renderMemory();message("Note revoked. It will be excluded from new reviews; historical runs are preserved.",true);});
});

$("load-demo").addEventListener("click", () => task(async () => {
  const p=await api(`/api/demo/${$("sample-version").value}/load`,"POST",{study_id:"SYN-014"});
  await refreshLists();await selectPackage(p.id);switchTab("review");
}));
$("run-button").addEventListener("click",()=>task(()=>execute("continue")));
$("step-button").addEventListener("click",()=>task(()=>execute("step")));
$("trace-toggle").addEventListener("click",()=>{const open=$("trace").classList.toggle("hidden");$("trace-toggle").setAttribute("aria-expanded",String(!open));});
$("add-memory").addEventListener("click",openMemory);
$("refresh-history").addEventListener("click",()=>task(refreshLists));
$("export-button").addEventListener("click",()=>task(async()=>download(await api(`/api/runs/${state.run.id}/export`),`review-${state.run.id.slice(0,8)}.json`)));
$("full-review-button").addEventListener("click",()=>task(()=>execute("continue",true)));
$("download-sample").addEventListener("click",()=>task(async()=>download(await api("/api/demo/v1"),"sample-package.json")));
for(const id of ["import-button","import-sidebar"]) $(id).addEventListener("click",()=>$("file-input").click());
$("file-input").addEventListener("change", event=>task(async()=>{
  const file=event.target.files[0];event.target.value="";if(!file)return;
  if(file.size>1_000_000)throw new Error("Package size limit is 1 MB.");
  let data;try{data=JSON.parse(await file.text());}catch{throw new Error("Please select a valid JSON package. Download the sample in Evidence library for the required format.");}
  const p=await api("/api/packages","POST",data);await refreshLists();await selectPackage(p.id);switchTab("review");message("Package imported. Start a review when you’re ready.",true);
}));
$("memory-form").addEventListener("submit",async event=>{
  event.preventDefault();const form=new FormData(event.target);const alias=String(form.get("alias")||"").trim();const submit=event.target.querySelector('[type="submit"]');submit.disabled=true;
  try{
    await api("/api/memory","POST",{package_id:state.package.id,document_id:form.get("document_id"),quote:form.get("quote"),summary:form.get("summary"),check_ids:[alias?"referenced_documents":form.get("check_id")],kind:alias?"document_alias":"review_note",alias});
    state.memories=await api(`/api/packages/${state.package.id}/memory`);renderMemory();$("memory-dialog").close();message("Reviewer note saved. A new review will recall it while the source remains unchanged.",true);
  }catch(error){$("memory-error").textContent=error.message;}finally{submit.disabled=false;}
});
function connectionDialog(){const s=state.settings;$("connection-content").innerHTML=s?`<div class="connection-row"><span>Persistent storage</span><strong>${escapeHTML(s.storage)}</strong></div><div class="connection-row"><span>Review engine</span><strong>${escapeHTML(s.review_mode)}</strong></div><div class="connection-row"><span>Evidence retrieval</span><strong>${escapeHTML(s.retrieval)}</strong></div><p>Configure cloud services in your local .env file and restart the server. Secrets never appear in this interface.</p>`:'<p>Enter an access token if your server requires one.</p>';if(!$("connection-dialog").open)$("connection-dialog").showModal();}
$("environment").addEventListener("click",connectionDialog);$("settings-button").addEventListener("click",connectionDialog);
$("token-form").addEventListener("submit",async event=>{event.preventDefault();sessionStorage.setItem("continuity-token",$("access-token").value);$("access-token").value="";$("connection-dialog").close();await initialize();});

async function initialize(){
  renderAll();
  await task(async()=>{
    state.settings=await api("/api/status");const s=state.settings;
    $("environment").innerHTML=`<i></i> ${s.storage === "sqlite" ? "Local development" : "MongoDB connected"}`;
    $("mode-notice").innerHTML=`<strong>${s.storage === "sqlite" ? "LOCAL DEVELOPMENT" : "CONNECTED ENVIRONMENT"}</strong> &nbsp; ${escapeHTML(s.notice)}${s.review_mode === "deterministic" && s.storage !== "sqlite" ? " Deterministic checks; no live model configured." : ""}`;
    await refreshLists();const runId=localStorage.getItem("continuity-run"),packageId=localStorage.getItem("continuity-package");
    if(runId){try{const run=await api(`/api/runs/${encodeURIComponent(runId)}`);await selectPackage(run.package_id,run);return;}catch{localStorage.removeItem("continuity-run");}}
    if(packageId && state.packages.some(p=>p.id===packageId))await selectPackage(packageId);
  });
}
initialize();
