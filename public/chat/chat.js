"use strict";

const $ = (id) => document.getElementById(id);
const apiStatus = $("apiStatus");
const authStatus = $("authStatus");
const modelStatus = $("modelStatus");
const accessToken = $("accessToken");
const verifyButton = $("verifyButton");
const messages = $("messages");
const messageInput = $("messageInput");
const sendButton = $("sendButton");
const stopButton = $("stopButton");
const newSessionButton = $("newSessionButton");

let assistantConfigured = false;
let authorized = false;
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

function sessionPrompt(currentMessage) {
  if (!assistantConfigured || turns.length === 0) return currentMessage;

  const header = [
    "Continue this Eagle Eyes browser session using the prior turns below only as conversational context.",
    "Do not claim these turns came from the user's ChatGPT account, saved memory, or any session outside this page.",
    "PRIOR SESSION:"
  ].join("\n");

  const footer = `\nCURRENT USER MESSAGE:\n${currentMessage}`;
  const maxPriorChars = Math.max(0, 11000 - header.length - footer.length);
  const recent = turns.slice(-10).map((turn) => `${turn.role === "user" ? "USER" : "ASSISTANT"}: ${turn.text}`);

  let prior = recent.join("\n\n");
  if (prior.length > maxPriorChars) {
    prior = prior.slice(prior.length - maxPriorChars);
    const firstBreak = prior.indexOf("\n\n");
    if (firstBreak !== -1) prior = prior.slice(firstBreak + 2);
  }

  return `${header}\n${prior}${footer}`;
}

function parseSseBlock(block) {
  let event = "message";
  const data = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }

  if (!data.length) return null;
  const raw = data.join("\n");
  try {
    return { event, data: JSON.parse(raw) };
  } catch {
    return { event, data: { text: raw } };
  }
}

async function sendMessage() {
  const currentMessage = messageInput.value.trim();
  const token = accessToken.value.trim();

  if (!currentMessage || activeController) return;
  if (!token || !authorized) {
    addMessage("assistant", "Verify your Command Center access token before sending.", "LOCKED");
    return;
  }

  const payloadMessage = sessionPrompt(currentMessage);
  addMessage("user", currentMessage);
  messageInput.value = "";

  const assistantNode = addMessage("assistant", "", "CONNECTING");
  let assistantText = "";
  let buffer = "";
  let completed = false;
  activeController = new AbortController();
  sendButton.disabled = true;
  stopButton.disabled = false;

  function handleBlock(block) {
    const parsed = parseSseBlock(block);
    if (!parsed) return;

    const { event, data } = parsed;
    if (event === "ready") {
      assistantNode.metaNode.textContent = `${data?.model || "GPT"} · STREAMING`;
    } else if (event === "delta" && typeof data?.text === "string") {
      assistantText += data.text;
      assistantNode.textNode.textContent = assistantText;
      messages.scrollTop = messages.scrollHeight;
    } else if (event === "tool_call") {
      assistantNode.metaNode.textContent = `TOOL · ${data?.name || "EAGLE EYES"}`;
    } else if (event === "done") {
      completed = true;
      assistantNode.metaNode.textContent = `${data?.model || "GPT"} · COMPLETE`;
    } else if (event === "error") {
      throw new Error(data?.message || data?.error || "Streaming error");
    }
  }

  function consume(chunk, final = false) {
    buffer = (buffer + chunk).replace(/\r\n/g, "\n");
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) if (block.trim()) handleBlock(block);
    if (final && buffer.trim()) handleBlock(buffer);
    if (final) buffer = "";
  }

  try {
    const response = await fetch("/api/assistant/stream", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "text/event-stream",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ message: payloadMessage }),
      signal: activeController.signal
    });

    if (!response.ok) {
      const raw = await response.text();
      let reason = `HTTP ${response.status}`;
      try { reason = JSON.parse(raw)?.error || reason; } catch {}
      if (response.status === 401) {
        authorized = false;
        setPill(authStatus, "DENIED", "bad");
      }
      throw new Error(reason);
    }
    if (!response.body) throw new Error("Streaming response body unavailable");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) consume(decoder.decode(value, { stream: true }));
    }
    consume(decoder.decode(), true);

    if (!assistantText) assistantText = "Stream completed without response text.";
    assistantNode.textNode.textContent = assistantText;
    if (!completed) assistantNode.metaNode.textContent = "STREAM CLOSED";

    turns.push({ role: "user", text: currentMessage });
    turns.push({ role: "assistant", text: assistantText });
  } catch (error) {
    if (error?.name === "AbortError") {
      assistantNode.metaNode.textContent = "STOPPED";
      if (!assistantText) assistantNode.textNode.textContent = "Stream stopped.";
    } else {
      assistantNode.metaNode.textContent = "REQUEST FAILED";
      assistantNode.textNode.textContent = assistantText || `Request failed: ${error.message}`;
    }
  } finally {
    activeController = null;
    sendButton.disabled = false;
    stopButton.disabled = true;
    messageInput.focus();
  }
}

function newSession() {
  if (activeController) activeController.abort();
  turns = [];
  [...messages.querySelectorAll(".message")].slice(1).forEach((node) => node.remove());
  addMessage("assistant", "New browser session started. No prior turn context will be sent.", "SESSION RESET");
}

verifyButton.addEventListener("click", verifyAccess);
accessToken.addEventListener("input", () => {
  authorized = false;
  setPill(authStatus, accessToken.value ? "UNVERIFIED" : "LOCKED");
});
sendButton.addEventListener("click", sendMessage);
stopButton.addEventListener("click", () => activeController?.abort());
newSessionButton.addEventListener("click", newSession);
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

loadStatus();
