"use strict";

const $ = (id) => document.getElementById(id);
const apiStatus = $("apiStatus");
const authStatus = $("authStatus");
const modelStatus = $("modelStatus");
const modeStatus = $("modeStatus");
const accessToken = $("accessToken");
const verifyButton = $("verifyButton");
const messages = $("messages");
const messageInput = $("messageInput");
const sendButton = $("sendButton");
const modeButton = $("modeButton");
const newSessionButton = $("newSessionButton");

let assistantConfigured = false;
let authorized = false;
let triMode = true;
let activeController = null;
let turns = [];

function setPill(node, text, state = "") {
  node.textContent = text;
  node.className = `pill${state ? ` ${state}` : ""}`;
}

function addMessage(role, text, meta = "") {
  const box = document.createElement("div");
  box.className = `message ${role === "user" ? "user" : "assistant"}`;

  const roleNode = document.createElement("span");
  roleNode.className = "role";
  roleNode.textContent = role === "user" ? "YOU" : "EAGLE EYES";

  const textNode = document.createElement("span");
  textNode.textContent = text;

  const metaNode = document.createElement("span");
  metaNode.className = "meta";
  metaNode.textContent = meta;

  box.append(roleNode, textNode);
  if (meta) box.append(metaNode);
  messages.append(box);
  messages.scrollTop = messages.scrollHeight;
  return { box, textNode, metaNode };
}

function clip(value, max) {
  const text = String(value || "");
  if (text.length <= max) return text;
  return text.slice(0, max) + "\n[trimmed]";
}

async function loadStatus() {
  try {
    const response = await fetch("/api/assistant/status", {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    assistantConfigured = data?.configured === true;
    setPill(apiStatus, assistantConfigured ? "AI LIVE" : "FREE FALLBACK", assistantConfigured ? "good" : "");
    setPill(modelStatus, String(data?.model || "MODEL N/A").toUpperCase());
  } catch (error) {
    assistantConfigured = false;
    setPill(apiStatus, "API UNAVAILABLE", "bad");
    addMessage("assistant", `Status check failed: ${error.message}`, "STATUS ERROR");
  }
}

async function verifyAccess() {
  const token = accessToken.value.trim();
  if (!token) {
    authorized = false;
    setPill(authStatus, "LOCKED", "bad");
    return;
  }

  setPill(authStatus, "CHECKING");
  verifyButton.disabled = true;
  try {
    const response = await fetch("/api/assistant/auth-check", {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`
      },
      cache: "no-store"
    });
    if (!response.ok) throw new Error(response.status === 401 ? "Unauthorized" : `HTTP ${response.status}`);
    authorized = true;
    setPill(authStatus, "AUTHORIZED", "good");
  } catch (error) {
    authorized = false;
    setPill(authStatus, "DENIED", "bad");
    addMessage("assistant", `Access verification failed: ${error.message}`, "AUTH ERROR");
  } finally {
    verifyButton.disabled = false;
  }
}

function boundedSession(currentMessage) {
  const recent = turns.slice(-6).map((turn) =>
    `${turn.role === "user" ? "USER" : "ASSISTANT"}: ${clip(turn.text, 600)}`
  );

  return [
    "Use only the browser-session context below as prior conversational context.",
    "Do not claim it came from ChatGPT account memory or any external conversation.",
    recent.length ? `PRIOR SESSION:\n${recent.join("\n\n")}` : "PRIOR SESSION: none",
    `CURRENT USER MESSAGE:\n${clip(currentMessage, 4000)}`
  ].join("\n\n");
}

async function assistantRequest(message, token, signal) {
  const response = await fetch("/api/assistant", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      accept: "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ message }),
    signal
  });

  const raw = await response.text();
  let data = null;
  try { data = JSON.parse(raw); } catch {}

  if (!response.ok) {
    if (response.status === 401) {
      authorized = false;
      setPill(authStatus, "DENIED", "bad");
    }
    throw new Error(data?.error || `HTTP ${response.status}`);
  }

  if (!data?.text) throw new Error("Assistant returned no response text");
  return data;
}

function isFreeResult(result) {
  return result?.model === "free-command-mode" || String(result?.mode || "").startsWith("free");
}

async function tripleConsensus(currentMessage, token, signal, assistantNode) {
  const context = boundedSession(currentMessage);

  assistantNode.metaNode.textContent = "TRI 1/3 · ANALYST";
  const analyst = await assistantRequest([
    "EAGLE EYES TRIPLE CONSENSUS — PASS 1 OF 3: ANALYST.",
    "Produce a concise candidate answer. Use live Eagle Eyes tools when current facts are required. Separate verified facts from assumptions and unknowns. Do not provide private chain-of-thought.",
    context
  ].join("\n\n"), token, signal);

  if (isFreeResult(analyst)) return analyst;

  assistantNode.metaNode.textContent = "TRI 2/3 · CHALLENGER";
  const challenger = await assistantRequest([
    "EAGLE EYES TRIPLE CONSENSUS — PASS 2 OF 3: CHALLENGER.",
    "Audit the candidate for unsupported claims, stale facts, contradictions, missing caveats, unsafe assumptions, and weak next actions. Return concise audit findings only; do not provide private chain-of-thought.",
    `ORIGINAL USER MESSAGE:\n${clip(currentMessage, 4000)}`,
    `CANDIDATE:\n${clip(analyst.text, 3000)}`
  ].join("\n\n"), token, signal);

  if (isFreeResult(challenger)) return analyst;

  assistantNode.metaNode.textContent = "TRI 3/3 · ARBITER";
  const arbiter = await assistantRequest([
    "EAGLE EYES TRIPLE CONSENSUS — PASS 3 OF 3: ARBITER.",
    "Deliver the final answer to the user. Resolve valid audit findings, preserve only supported claims, distinguish uncertainty, and choose the smallest safe useful next action. Re-check live facts with Eagle Eyes tools if necessary. Do not mention hidden reasoning or fabricate tool results.",
    `ORIGINAL USER MESSAGE:\n${clip(currentMessage, 3500)}`,
    `ANALYST CANDIDATE:\n${clip(analyst.text, 2200)}`,
    `CHALLENGER AUDIT:\n${clip(challenger.text, 2200)}`
  ].join("\n\n"), token, signal);

  return arbiter;
}

async function sendMessage() {
  const currentMessage = messageInput.value.trim();
  const token = accessToken.value.trim();

  if (!currentMessage || activeController) return;
  if (!token || !authorized) {
    addMessage("assistant", "Verify your Command Center access token before sending.", "LOCKED");
    return;
  }

  addMessage("user", currentMessage);
  messageInput.value = "";
  const assistantNode = addMessage("assistant", "", triMode ? "TRI STARTING" : "FAST CONNECTING");

  activeController = new AbortController();
  sendButton.disabled = true;
  modeButton.disabled = true;

  try {
    let result;
    if (triMode && assistantConfigured) {
      try {
        result = await tripleConsensus(currentMessage, token, activeController.signal, assistantNode);
      } catch (error) {
        if (error?.name === "AbortError") throw error;
        assistantNode.metaNode.textContent = "TRI DEGRADED · FAST FALLBACK";
        result = await assistantRequest(boundedSession(currentMessage), token, activeController.signal);
      }
    } else {
      result = await assistantRequest(boundedSession(currentMessage), token, activeController.signal);
    }

    assistantNode.textNode.textContent = result.text;
    assistantNode.metaNode.textContent = `${result.model || "EAGLE EYES"} · ${triMode && assistantConfigured ? "TRI COMPLETE" : "FAST COMPLETE"}`;
    turns.push({ role: "user", text: currentMessage });
    turns.push({ role: "assistant", text: result.text });
    turns = turns.slice(-10);
    messages.scrollTop = messages.scrollHeight;
  } catch (error) {
    assistantNode.metaNode.textContent = error?.name === "AbortError" ? "STOPPED" : "REQUEST FAILED";
    assistantNode.textNode.textContent = error?.name === "AbortError" ? "Request stopped." : `Request failed: ${error.message}`;
  } finally {
    activeController = null;
    sendButton.disabled = false;
    modeButton.disabled = false;
    messageInput.focus();
  }
}

function toggleMode() {
  triMode = !triMode;
  setPill(modeStatus, triMode ? "TRI 3-PASS" : "FAST 1-PASS", triMode ? "good" : "");
  modeButton.textContent = triMode ? "USE FAST MODE" : "USE TRI MODE";
}

function newSession() {
  activeController?.abort();
  turns = [];
  [...messages.querySelectorAll(".message")].slice(1).forEach((node) => node.remove());
  addMessage("assistant", "New browser session started. No prior turn context will be sent.", "SESSION RESET");
}

verifyButton.addEventListener("click", verifyAccess);
accessToken.addEventListener("input", () => {
  authorized = false;
  setPill(authStatus, accessToken.value ? "UNVERIFIED" : "LOCKED");
});
modeButton.addEventListener("click", toggleMode);
sendButton.addEventListener("click", sendMessage);
newSessionButton.addEventListener("click", newSession);
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

loadStatus();
