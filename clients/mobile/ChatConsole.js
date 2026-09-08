import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import { fetch as expoFetch } from "expo/fetch";

const STARTER_TASKS = [
  "Give me an Eagle Eyes mission brief and tell me what matters now.",
  "Audit the current Eagle Eyes system and prepare the next safest upgrades.",
  "Investigate the latest error I describe, find the root cause, and prepare the fix.",
  "Prepare a build plan for my next project using Eagle Eyes capabilities."
];

function parseSseBlock(block) {
  let event = "message";
  const data = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      data.push(line.slice(5).trimStart());
    }
  }

  if (!data.length) return null;

  try {
    return { event, data: JSON.parse(data.join("\n")) };
  } catch {
    return { event, data: { text: data.join("\n") } };
  }
}

function Message({ item }) {
  const assistant = item.role === "assistant";
  return (
    <View style={[styles.message, assistant ? styles.assistantMessage : styles.userMessage]}>
      <Text style={styles.messageRole}>{assistant ? "CHATGPT · EAGLE EYES" : "YOU"}</Text>
      <Text style={styles.messageText}>{item.text}</Text>
      {item.meta ? <Text style={styles.messageMeta}>{item.meta}</Text> : null}
    </View>
  );
}

export default function ChatConsole({ baseUrl }) {
  const [accessToken, setAccessToken] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      text:
        "Eagle Eyes ChatGPT command console ready. Connect your Command Center access token, then give me a task. I can stream answers while the backend routes GPT-5.6, web search, and Eagle Eyes tools without placing the OpenAI API key inside this APK.",
      meta: "SERVER-SIDE AI · STREAMING · TOOL ROUTING"
    }
  ]);
  const [assistantStatus, setAssistantStatus] = useState(null);
  const [statusError, setStatusError] = useState("");
  const [authState, setAuthState] = useState("LOCKED");
  const [streamState, setStreamState] = useState("IDLE");
  const [activeTool, setActiveTool] = useState("");
  const abortRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    expoFetch(baseUrl + "/api/assistant/status", {
      headers: { Accept: "application/json" }
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!cancelled) {
          setAssistantStatus(data);
          setStatusError("");
        }
      })
      .catch((error) => {
        if (!cancelled) setStatusError(error.message || "Assistant status unavailable");
      });

    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [baseUrl]);

  useEffect(() => {
    const id = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 60);
    return () => clearTimeout(id);
  }, [messages, streamState]);

  async function verifyAccess() {
    const token = accessToken.trim();
    if (!token) {
      setAuthState("LOCKED");
      return;
    }

    setAuthState("CHECKING");
    try {
      const response = await expoFetch(baseUrl + "/api/assistant/auth-check", {
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`
        }
      });
      if (!response.ok) throw new Error(response.status === 401 ? "Unauthorized" : `HTTP ${response.status}`);
      setAuthState("AUTHORIZED");
    } catch {
      setAuthState("DENIED");
    }
  }

  function updateAssistantMessage(id, updater) {
    setMessages((current) =>
      current.map((item) => (item.id === id ? { ...item, ...updater(item) } : item))
    );
  }

  function appendAssistantError(text) {
    setMessages((current) => [
      ...current,
      {
        id: `error-${Date.now()}`,
        role: "assistant",
        text,
        meta: "STREAM ERROR"
      }
    ]);
  }

  function stopStream() {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreamState("STOPPED");
    setActiveTool("");
  }

  async function sendTask(taskText) {
    const text = String(taskText || message).trim();
    const token = accessToken.trim();

    if (!text || streamState === "STREAMING" || streamState === "CONNECTING") return;

    if (!token) {
      appendAssistantError(
        "Command Center access is locked. Enter the COMMAND_CENTER_ACCESS_TOKEN for your Eagle Eyes backend. It stays in this running app session and is not compiled into the APK."
      );
      return;
    }

    const userId = `user-${Date.now()}`;
    const assistantId = `assistant-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const controller = new AbortController();
    abortRef.current = controller;

    setMessages((current) => [
      ...current,
      { id: userId, role: "user", text },
      { id: assistantId, role: "assistant", text: "", meta: "CONNECTING" }
    ]);
    setMessage("");
    setStreamState("CONNECTING");
    setActiveTool("");

    let buffer = "";
    let streamCompleted = false;

    function handleBlock(block) {
      const parsed = parseSseBlock(block);
      if (!parsed) return;

      const { event, data } = parsed;

      if (event === "ready") {
        setStreamState("STREAMING");
        updateAssistantMessage(assistantId, () => ({
          meta: `${data?.model || "GPT"} · ${String(data?.mode || "live").toUpperCase()} · STREAMING`
        }));
      } else if (event === "delta" && typeof data?.text === "string") {
        setStreamState("STREAMING");
        updateAssistantMessage(assistantId, (item) => ({ text: item.text + data.text }));
      } else if (event === "tool_call") {
        const name = data?.name || "Eagle Eyes tool";
        setActiveTool(name);
        updateAssistantMessage(assistantId, (item) => ({
          meta: `${item.meta || "GPT"} · TOOL ${name}`
        }));
      } else if (event === "tool_result") {
        setActiveTool("");
      } else if (event === "done") {
        streamCompleted = true;
        setStreamState("DONE");
        setActiveTool("");
        updateAssistantMessage(assistantId, () => ({
          meta: `${data?.model || "GPT"} · COMPLETE`
        }));
      } else if (event === "error") {
        throw new Error(data?.error || data?.message || "Streaming error");
      }
    }

    function consumeText(chunk, final = false) {
      buffer = (buffer + chunk).replace(/\r\n/g, "\n");
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        if (!block.trim()) continue;
        handleBlock(block);
      }

      if (final && buffer.trim()) {
        handleBlock(buffer);
        buffer = "";
      }
    }

    try {
      const response = await expoFetch(baseUrl + "/api/assistant/stream", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          accept: "text/event-stream",
          authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ message: text }),
        signal: controller.signal
      });

      if (!response.ok) {
        const raw = await response.text();
        let reason = `HTTP ${response.status}`;
        try {
          reason = JSON.parse(raw)?.error || reason;
        } catch {}
        if (response.status === 401) setAuthState("DENIED");
        throw new Error(reason);
      }

      if (!response.body) {
        throw new Error("Streaming response body is unavailable");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      setStreamState("STREAMING");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) consumeText(decoder.decode(value, { stream: true }));
      }

      consumeText(decoder.decode(), true);
      abortRef.current = null;

      if (!streamCompleted) {
        setStreamState("DONE");
        updateAssistantMessage(assistantId, (item) => ({
          text: item.text || "Stream ended without response text.",
          meta: "STREAM CLOSED"
        }));
      }
    } catch (error) {
      abortRef.current = null;
      setActiveTool("");

      if (error?.name === "AbortError") {
        setStreamState("STOPPED");
        updateAssistantMessage(assistantId, (item) => ({
          text: item.text || "Stream stopped.",
          meta: "STOPPED"
        }));
        return;
      }

      setStreamState("ERROR");
      updateAssistantMessage(assistantId, (item) => ({
        text: item.text || `Request failed: ${error?.message || "Unknown error"}`,
        meta: "REQUEST FAILED"
      }));
    }
  }

  const configured = assistantStatus?.configured === true;
  const model = assistantStatus?.model || "GPT-5.6";

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.commandHeader}>
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>EAGLE EYES · CHATGPT</Text>
          <Text style={styles.title}>STREAMING COMMAND CORE</Text>
          <Text style={styles.subtitle}>
            {configured ? `${model} API online` : "GPT API status not active"} · tool routing · live web search · free fallback
          </Text>
        </View>
        <View style={[styles.statePill, configured ? styles.stateGood : styles.stateWatch]}>
          <Text style={styles.stateText}>{configured ? "AI LIVE" : "FALLBACK"}</Text>
        </View>
      </View>

      {statusError ? <Text style={styles.statusError}>Assistant status: {statusError}</Text> : null}

      <View style={styles.authCard}>
        <Text style={styles.authLabel}>COMMAND CENTER ACCESS</Text>
        <View style={styles.authRow}>
          <TextInput
            value={accessToken}
            onChangeText={(value) => {
              setAccessToken(value);
              setAuthState(value ? "UNVERIFIED" : "LOCKED");
            }}
            placeholder="Enter access token for this session"
            placeholderTextColor="#756f64"
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            style={styles.authInput}
          />
          <Pressable style={styles.verifyButton} onPress={verifyAccess}>
            <Text style={styles.verifyText}>{authState === "CHECKING" ? "..." : "VERIFY"}</Text>
          </Pressable>
        </View>
        <Text style={styles.authMeta}>
          {authState} · OpenAI key stays on the server · this token is not saved by the APK
        </Text>
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.messages}
        contentContainerStyle={styles.messagesContent}
        keyboardShouldPersistTaps="handled"
      >
        {messages.map((item) => <Message key={item.id} item={item} />)}
        {streamState === "CONNECTING" ? (
          <View style={styles.thinkingRow}>
            <ActivityIndicator size="small" />
            <Text style={styles.thinkingText}>Connecting to Eagle Eyes ChatGPT…</Text>
          </View>
        ) : null}
        {activeTool ? <Text style={styles.toolText}>TOOL ACTIVE · {activeTool}</Text> : null}
      </ScrollView>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.starterScroller}
        contentContainerStyle={styles.starters}
        keyboardShouldPersistTaps="handled"
      >
        {STARTER_TASKS.map((task, index) => (
          <Pressable key={task} style={styles.starter} onPress={() => sendTask(task)}>
            <Text style={styles.starterText}>TASK {index + 1}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <View style={styles.composer}>
        <TextInput
          value={message}
          onChangeText={setMessage}
          placeholder="Tell ChatGPT what to research, build, inspect, prepare, or solve…"
          placeholderTextColor="#756f64"
          multiline
          maxLength={12000}
          style={styles.composerInput}
        />
        {streamState === "STREAMING" || streamState === "CONNECTING" ? (
          <Pressable style={styles.stopButton} onPress={stopStream}>
            <Text style={styles.stopText}>STOP</Text>
          </Pressable>
        ) : (
          <Pressable style={styles.sendButton} onPress={() => sendTask()}>
            <Text style={styles.sendText}>SEND</Text>
          </Pressable>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#070706" },
  commandHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingTop: 14,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(242,198,109,.16)"
  },
  headerCopy: { flex: 1, paddingRight: 10 },
  eyebrow: { color: "#f2c66d", fontSize: 9, fontWeight: "900", letterSpacing: 2 },
  title: { color: "#f7f1e7", fontSize: 18, fontWeight: "900", marginTop: 3 },
  subtitle: { color: "#8f8779", fontSize: 10, marginTop: 4, lineHeight: 15 },
  statePill: { borderWidth: 1, borderRadius: 18, paddingHorizontal: 10, paddingVertical: 6 },
  stateGood: { borderColor: "rgba(115,229,140,.45)" },
  stateWatch: { borderColor: "rgba(242,198,109,.38)" },
  stateText: { color: "#f2c66d", fontSize: 9, fontWeight: "900" },
  statusError: { color: "#ff9c9e", fontSize: 10, paddingHorizontal: 14, paddingTop: 8 },
  authCard: {
    margin: 10,
    marginBottom: 4,
    padding: 10,
    backgroundColor: "#11100d",
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.16)",
    borderRadius: 12
  },
  authLabel: { color: "#8f8779", fontSize: 9, fontWeight: "900", letterSpacing: 1.2 },
  authRow: { flexDirection: "row", gap: 8, marginTop: 7 },
  authInput: {
    flex: 1,
    color: "#f7f1e7",
    backgroundColor: "#070706",
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.24)",
    borderRadius: 9,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 12
  },
  verifyButton: { justifyContent: "center", paddingHorizontal: 12, borderRadius: 9, backgroundColor: "#262117" },
  verifyText: { color: "#f2c66d", fontSize: 9, fontWeight: "900" },
  authMeta: { color: "#70695e", fontSize: 9, marginTop: 7 },
  messages: { flex: 1 },
  messagesContent: { padding: 10, paddingBottom: 18 },
  message: { maxWidth: "94%", borderRadius: 14, padding: 12, marginBottom: 10, borderWidth: 1 },
  assistantMessage: { alignSelf: "flex-start", backgroundColor: "#11100d", borderColor: "rgba(242,198,109,.17)" },
  userMessage: { alignSelf: "flex-end", backgroundColor: "#1b1710", borderColor: "rgba(242,198,109,.3)" },
  messageRole: { color: "#f2c66d", fontSize: 8, fontWeight: "900", letterSpacing: 1.1, marginBottom: 6 },
  messageText: { color: "#eee8dd", fontSize: 13, lineHeight: 20 },
  messageMeta: { color: "#756f64", fontSize: 8, marginTop: 8, letterSpacing: 0.5 },
  thinkingRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 8 },
  thinkingText: { color: "#9b9387", fontSize: 11 },
  toolText: { color: "#f2c66d", fontSize: 9, fontWeight: "800", marginBottom: 8 },
  starterScroller: { flexGrow: 0, borderTopWidth: 1, borderTopColor: "rgba(242,198,109,.1)" },
  starters: { gap: 7, paddingHorizontal: 10, paddingVertical: 8 },
  starter: { borderWidth: 1, borderColor: "rgba(242,198,109,.22)", borderRadius: 18, paddingHorizontal: 11, paddingVertical: 7 },
  starterText: { color: "#b8aa91", fontSize: 9, fontWeight: "800" },
  composer: { flexDirection: "row", alignItems: "flex-end", gap: 8, padding: 10, backgroundColor: "#0b0a08", borderTopWidth: 1, borderTopColor: "rgba(242,198,109,.16)" },
  composerInput: { flex: 1, maxHeight: 110, minHeight: 44, color: "#f7f1e7", backgroundColor: "#11100d", borderWidth: 1, borderColor: "rgba(242,198,109,.25)", borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13 },
  sendButton: { minHeight: 44, justifyContent: "center", paddingHorizontal: 16, borderRadius: 12, backgroundColor: "#f2c66d" },
  sendText: { color: "#181108", fontSize: 10, fontWeight: "900" },
  stopButton: { minHeight: 44, justifyContent: "center", paddingHorizontal: 16, borderRadius: 12, borderWidth: 1, borderColor: "rgba(255,111,113,.5)" },
  stopText: { color: "#ff8f90", fontSize: 10, fontWeight: "900" }
});
