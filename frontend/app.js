const callListEl = document.getElementById("callList");
const transcriptEl = document.getElementById("transcript");
const statCount = document.getElementById("statCount");
const statP50 = document.getElementById("statP50");
const statP95 = document.getElementById("statP95");

let activeCallId = null;

function formatDuration(startedAt, endedAt) {
  if (!endedAt) return "in progress";
  const seconds = Math.round(endedAt - startedAt);
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleString();
}

async function loadStats() {
  const res = await fetch("/api/stats");
  const stats = await res.json();
  statCount.textContent = stats.count;
  statP50.textContent = stats.p50_ms ? `${Math.round(stats.p50_ms)}ms` : "–";
  statP95.textContent = stats.p95_ms ? `${Math.round(stats.p95_ms)}ms` : "–";
}

async function loadCalls() {
  const res = await fetch("/api/calls");
  const calls = await res.json();

  if (calls.length === 0) {
    callListEl.innerHTML = '<p class="empty">No calls yet — dial the number to see one show up here.</p>';
    return;
  }

  callListEl.innerHTML = "";
  for (const call of calls) {
    const row = document.createElement("div");
    row.className = "call-row" + (call.id === activeCallId ? " active" : "");
    row.innerHTML = `
      <span class="caller">${call.caller_number || "Unknown caller"}</span>
      <span class="meta">${formatTime(call.started_at)} · ${formatDuration(call.started_at, call.ended_at)}
        ${call.first_audio_latency_ms ? `· ${Math.round(call.first_audio_latency_ms)}ms first reply` : ""}</span>
    `;
    row.addEventListener("click", () => selectCall(call.id));
    callListEl.appendChild(row);
  }
}

async function selectCall(callId) {
  activeCallId = callId;
  await loadCalls();

  const res = await fetch(`/api/calls/${callId}`);
  const call = await res.json();

  if (!call.turns || call.turns.length === 0) {
    transcriptEl.innerHTML = '<p class="empty">No turns recorded for this call yet.</p>';
    return;
  }

  transcriptEl.innerHTML = "";
  for (const turn of call.turns) {
    const div = document.createElement("div");
    div.className = `line ${turn.role}`;
    div.textContent = turn.text;
    transcriptEl.appendChild(div);
  }
}

async function refresh() {
  await Promise.all([loadStats(), loadCalls()]);
}

refresh();
setInterval(refresh, 4000);
