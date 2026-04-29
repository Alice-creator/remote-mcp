// Plexus UI — vanilla JS, no build step.

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

// =========================================================================
// Tabs
// =========================================================================
$$("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$("nav button, .tab").forEach((el) => el.classList.remove("active"));
    btn.classList.add("active");
    $("#" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "devices") loadDevices();
    if (btn.dataset.tab === "tools") loadTools();
  });
});

// =========================================================================
// Devices
// =========================================================================
async function loadDevices() {
  const list = $("#device-list");
  list.innerHTML = '<div class="muted">Loading…</div>';
  try {
    const r = await fetch("/api/devices");
    const data = await r.json();
    if (!data.length) {
      list.innerHTML = '<div class="muted">No devices yet. Add one below.</div>';
      return;
    }
    list.innerHTML = "";
    for (const d of data) {
      const div = document.createElement("div");
      div.className = "device";
      const spec = d.spec_url || d.spec_path || "";
      div.innerHTML = `
        <h3>${escapeHtml(d.name)}</h3>
        <div class="device-meta">${escapeHtml(d.description || "")}</div>
        <div class="device-meta"><code>${escapeHtml(d.base_url)}</code></div>
        <div class="device-meta">Spec: <code>${escapeHtml(spec)}</code></div>
        <button class="danger remove" data-name="${escapeHtml(d.name)}">Remove</button>
      `;
      list.appendChild(div);
    }
    list.querySelectorAll(".remove").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm(`Remove ${btn.dataset.name}?`)) return;
        const r = await fetch("/api/devices/" + btn.dataset.name, { method: "DELETE" });
        if (r.ok) loadDevices();
        else alert((await r.json()).error || "Failed");
      });
    });
  } catch (e) {
    list.innerHTML = `<div class="msg-error">${escapeHtml(e.message)}</div>`;
  }
}

$("#add-device-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = {};
  for (const [k, v] of fd.entries()) if (v) body[k] = v;
  const r = await fetch("/api/devices", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.ok) {
    e.target.reset();
    e.target.closest("details").open = false;
    loadDevices();
  } else {
    alert((await r.json()).error || "Failed");
  }
});

$("#reload-btn").addEventListener("click", async () => {
  const r = await fetch("/api/reload", { method: "POST" });
  const data = await r.json();
  alert(`Reloaded: ${data.devices} device(s), ${data.tools} tool(s).`);
  loadDevices();
});

// =========================================================================
// Tools
// =========================================================================
async function loadTools() {
  const list = $("#tool-list");
  list.innerHTML = '<div class="muted">Loading…</div>';
  try {
    const r = await fetch("/api/tools");
    const data = await r.json();
    $("#tool-count").textContent = `(${data.length})`;
    if (!data.length) {
      list.innerHTML = '<div class="muted">No tools registered. Add a device first.</div>';
      return;
    }
    list.innerHTML = "";
    for (const t of data) {
      const div = document.createElement("div");
      div.className = "tool";
      const methodCls = "method-" + (t.method || "get").toLowerCase();
      div.innerHTML = `
        <h3>${escapeHtml(t.name)}</h3>
        <div class="tool-meta">
          <span class="method ${methodCls}">${escapeHtml(t.method || "GET")}</span>
          <code>${escapeHtml(t.path || "")}</code>
        </div>
        <div class="tool-meta">${escapeHtml(t.description || "")}</div>
        <details>
          <summary>Schema</summary>
          <pre>${escapeHtml(JSON.stringify(t.input_schema, null, 2))}</pre>
        </details>
        <details class="invoke">
          <summary>Invoke manually</summary>
          <textarea rows="4" placeholder='{"light_id": "bedroom"}'>{}</textarea>
          <button data-name="${escapeHtml(t.name)}">Call</button>
          <pre class="result"></pre>
        </details>
      `;
      list.appendChild(div);
    }
    list.querySelectorAll(".invoke button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const tool = btn.dataset.name;
        const ta = btn.previousElementSibling;
        const result = btn.nextElementSibling;
        let args = {};
        try { args = JSON.parse(ta.value || "{}"); }
        catch (e) { result.textContent = "Invalid JSON: " + e.message; return; }
        result.textContent = "…";
        const r = await fetch("/api/call", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tool, args }),
        });
        const data = await r.json();
        result.textContent = data.result ?? data.error;
      });
    });
  } catch (e) {
    list.innerHTML = `<div class="msg-error">${escapeHtml(e.message)}</div>`;
  }
}

$("#refresh-tools").addEventListener("click", loadTools);

// =========================================================================
// Chat — single rendering path used for live events AND replay.
// =========================================================================
//
// State model:
//   history  — canonical OpenAI message list. Persisted to localStorage.
//              This is what we send to /api/chat on each turn.
//   pending  — UI-only cards for the in-flight request (cleared on "final").
//
// Both initial render (after page reload) and live SSE updates go through
// the same `render()` → `messagesToCards()` → `renderCard()` pipeline,
// so the DOM looks identical either way.

const CFG_KEY = "plexus-cfg";
const HISTORY_KEY = "plexus-history";
const HISTORY_CAP = 100;  // last N messages persisted; older ones drop off
const cfgFields = ["cfg-base-url", "cfg-model", "cfg-api-key", "cfg-system"];

function loadCfg() {
  try {
    const cfg = JSON.parse(localStorage.getItem(CFG_KEY) || "{}");
    for (const id of cfgFields) {
      if (cfg[id] !== undefined) $("#" + id).value = cfg[id];
    }
  } catch {}
}
function saveCfg() {
  const cfg = {};
  for (const id of cfgFields) cfg[id] = $("#" + id).value;
  localStorage.setItem(CFG_KEY, JSON.stringify(cfg));
}
cfgFields.forEach((id) => $("#" + id).addEventListener("change", saveCfg));
loadCfg();

let history = loadHistory();
let pending = [];

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); }
  catch { return []; }
}
function saveHistory() {
  const trimmed = history.slice(-HISTORY_CAP);
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed)); } catch {}
}

// Convert an OpenAI message list into a flat list of UI cards.
// Pairs each assistant tool_call with its matching role=tool result.
function messagesToCards(messages) {
  const cards = [];
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (m.role === "system") continue;
    if (m.role === "user") {
      cards.push({ type: "user", content: m.content });
      continue;
    }
    if (m.role === "assistant") {
      if (Array.isArray(m.tool_calls)) {
        for (const tc of m.tool_calls) {
          let result = null;
          for (let j = i + 1; j < messages.length; j++) {
            const next = messages[j];
            if (next.role === "tool" && next.tool_call_id === tc.id) {
              result = next.content;
              break;
            }
          }
          let args = tc.function?.arguments ?? {};
          if (typeof args === "string") {
            try { args = JSON.parse(args); } catch {}
          }
          cards.push({
            type: "tool",
            id: tc.id,
            name: tc.function?.name || "",
            args,
            result,
          });
        }
      }
      if (m.content) cards.push({ type: "assistant", content: m.content });
    }
    // role === "tool" handled inline above
  }
  return cards;
}

function renderCard(card) {
  const div = document.createElement("div");

  if (card.type === "user") {
    div.className = "msg msg-user";
    div.innerHTML = `<div class="label">USER</div><div class="body"></div>`;
    div.querySelector(".body").textContent = card.content || "";
    return div;
  }

  if (card.type === "assistant") {
    div.className = "msg msg-assistant";
    div.innerHTML = `<div class="label">ASSISTANT</div><div class="body"></div>`;
    div.querySelector(".body").textContent = card.content || "";
    return div;
  }

  if (card.type === "error") {
    div.className = "msg msg-error";
    div.innerHTML = `<div class="label">ERROR</div><div class="body"></div>`;
    div.querySelector(".body").textContent = card.error || "Unknown error";
    return div;
  }

  // type === "tool"
  const isPending = card.result === null || card.result === undefined;
  div.className = "msg msg-tool" + (isPending ? " tool-pending" : "");
  if (card.id) div.dataset.callId = card.id;

  const argsStr = typeof card.args === "string" ? card.args : JSON.stringify(card.args);
  const result = String(card.result ?? "");
  const truncated = result.length > 600 ? result.slice(0, 600) + "…" : result;

  div.innerHTML = `
    <div class="label">TOOL · ${escapeHtml(card.name)}</div>
    <div class="tool-call">→ ${escapeHtml(argsStr)}</div>
    <div class="body${isPending ? " muted" : ""}"></div>
  `;
  div.querySelector(".body").textContent = isPending ? "running…" : truncated;

  if (!isPending && result.length > 600) {
    const det = document.createElement("details");
    det.innerHTML = `<summary>full result (${result.length} chars)</summary><pre></pre>`;
    det.querySelector("pre").textContent = result;
    div.appendChild(det);
  }
  return div;
}

function render() {
  const container = $("#messages");
  container.innerHTML = "";
  for (const card of messagesToCards(history)) container.appendChild(renderCard(card));
  for (const card of pending) container.appendChild(renderCard(card));
  container.scrollTop = container.scrollHeight;
}

// Apply one streamed SSE event to `pending` and re-render.
function applyEvent(evt) {
  if (evt.type === "tool_call") {
    pending.push({ type: "tool", id: evt.id, name: evt.name, args: evt.args, result: null });
  } else if (evt.type === "tool_result") {
    const entry = pending.find((p) => p.type === "tool" && p.id === evt.id);
    if (entry) entry.result = evt.result;
  } else if (evt.type === "message") {
    pending.push({ type: "assistant", content: evt.content });
  } else if (evt.type === "error") {
    pending.push({ type: "error", error: evt.error });
  }
  render();
}

async function streamChat(body) {
  const r = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!r.ok || !r.body) {
    let errMsg = `HTTP ${r.status}`;
    try { errMsg = (await r.json()).error || errMsg; } catch {}
    applyEvent({ type: "error", error: errMsg });
    return null;
  }

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalMessages = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by blank lines; lines start with "data: ".
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        let evt;
        try { evt = JSON.parse(line.slice(6)); } catch { continue; }
        if (evt.type === "final") finalMessages = evt.messages;
        else applyEvent(evt);
      }
    }
  }

  return finalMessages;
}

$("#chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#user-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";

  // Optimistic: show the user's message right away.
  history.push({ role: "user", content: text });
  pending = [];
  render();

  const overrides = {
    base_url: $("#cfg-base-url").value || undefined,
    model: $("#cfg-model").value || undefined,
    api_key: $("#cfg-api-key").value || undefined,
    system: $("#cfg-system").value || undefined,
  };
  for (const k of Object.keys(overrides)) if (!overrides[k]) delete overrides[k];

  const body = { messages: history, ...overrides };

  try {
    const finalMessages = await streamChat(body);
    if (finalMessages) {
      // Server's reconciled history is canonical (includes the system prompt
      // it injected, plus the assistant's tool_calls and results).
      history = finalMessages;
    }
    pending = [];
    saveHistory();
    render();
  } catch (err) {
    applyEvent({ type: "error", error: String(err) });
  }
});

$("#cfg-clear").addEventListener("click", () => {
  history = [];
  pending = [];
  saveHistory();
  render();
});

// Initial paint (replays anything from localStorage).
render();
loadDevices();
