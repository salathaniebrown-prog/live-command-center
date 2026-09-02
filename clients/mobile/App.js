import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { WebView } from "react-native-webview";

const BASE_URL = (
  process.env.EXPO_PUBLIC_EAGLE_EYES_BASE_URL ||
  "https://live-command-center-production-31ed.up.railway.app"
).replace(/\/$/, "");
const SEARCH_HOME = "https://www.google.com/";

function LoadingView({ label }) {
  return (
    <View style={styles.loading}>
      <ActivityIndicator size="large" />
      <Text style={styles.loadingText}>{label}</Text>
    </View>
  );
}

function TabButton({ active, label, onPress }) {
  return (
    <Pressable onPress={onPress} style={[styles.tab, active && styles.tabActive]}>
      <Text style={[styles.tabText, active && styles.tabTextActive]}>{label}</Text>
    </Pressable>
  );
}

function WorldOS({ section = "overview" }) {
  const ref = useRef(null);
  const uri = BASE_URL + "/#" + section;

  return (
    <WebView
      key={section}
      ref={ref}
      source={{ uri }}
      style={styles.web}
      originWhitelist={["https://*", "http://*"]}
      javaScriptEnabled
      domStorageEnabled
      sharedCookiesEnabled
      thirdPartyCookiesEnabled
      setSupportMultipleWindows={false}
      startInLoadingState
      renderLoading={() => <LoadingView label="Opening full Eagle Eyes World OS…" />}
    />
  );
}

function WebSearch() {
  const ref = useRef(null);
  const [query, setQuery] = useState("");
  const [url, setUrl] = useState(SEARCH_HOME);
  const [nav, setNav] = useState({ canGoBack: false, canGoForward: false });

  const search = () => {
    const q = query.trim();
    if (!q) return;
    setUrl("https://www.google.com/search?q=" + encodeURIComponent(q));
  };

  return (
    <View style={styles.flex}>
      <View style={styles.searchRow}>
        <TextInput
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={search}
          placeholder="Search the live web…"
          placeholderTextColor="#756f64"
          returnKeyType="search"
          autoCapitalize="none"
          style={styles.searchInput}
        />
        <Pressable style={styles.searchButton} onPress={search}>
          <Text style={styles.searchButtonText}>SEARCH</Text>
        </Pressable>
      </View>

      <View style={styles.browserRow}>
        <Pressable disabled={!nav.canGoBack} onPress={() => ref.current?.goBack()}>
          <Text style={[styles.browserText, !nav.canGoBack && styles.dim]}>BACK</Text>
        </Pressable>
        <Pressable disabled={!nav.canGoForward} onPress={() => ref.current?.goForward()}>
          <Text style={[styles.browserText, !nav.canGoForward && styles.dim]}>FORWARD</Text>
        </Pressable>
        <Pressable onPress={() => setUrl(SEARCH_HOME)}>
          <Text style={styles.browserText}>HOME</Text>
        </Pressable>
        <Pressable onPress={() => ref.current?.reload()}>
          <Text style={styles.browserText}>REFRESH</Text>
        </Pressable>
      </View>

      <WebView
        ref={ref}
        source={{ uri: url }}
        style={styles.web}
        originWhitelist={["https://*", "http://*"]}
        javaScriptEnabled
        domStorageEnabled
        sharedCookiesEnabled
        thirdPartyCookiesEnabled
        setSupportMultipleWindows={false}
        startInLoadingState
        renderLoading={() => <LoadingView label="Loading live Web Search…" />}
        onNavigationStateChange={(state) =>
          setNav({ canGoBack: state.canGoBack, canGoForward: state.canGoForward })
        }
      />
    </View>
  );
}

function Metric({ label, value }) {
  const shown =
    value === null || value === undefined || Number.isNaN(value) ? "N/A" : value + "%";
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{shown}</Text>
    </View>
  );
}

function LiveStatus() {
  const [status, setStatus] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [deployment, setDeployment] = useState(null);
  const [assistant, setAssistant] = useState(null);
  const [error, setError] = useState("");

  async function getJson(path) {
    const response = await fetch(BASE_URL + path, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(path + " unavailable");
    return response.json();
  }

  async function load() {
    setError("");

    const results = await Promise.allSettled([
      getJson("/api/status"),
      getJson("/api/metrics"),
      getJson("/api/deployment"),
      getJson("/api/assistant/status")
    ]);

    if (results[0].status === "fulfilled") setStatus(results[0].value);
    if (results[1].status === "fulfilled") setMetrics(results[1].value);
    if (results[2].status === "fulfilled") setDeployment(results[2].value);
    if (results[3].status === "fulfilled") setAssistant(results[3].value);

    const failures = results.filter((item) => item.status === "rejected");
    if (failures.length) {
      setError(
        failures
          .map((item) => item.reason?.message || "Live endpoint unavailable")
          .join(" • ")
      );
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <ScrollView style={styles.status} contentContainerStyle={styles.statusContent}>
      <Text style={styles.eyebrow}>EAGLE EYES</Text>
      <Text style={styles.title}>FULL SYSTEM STATUS</Text>
      <Text style={styles.subtitle}>Production backend · live sources · no demo telemetry</Text>

      <View style={styles.connection}>
        <View style={[styles.dot, status?.online ? styles.online : styles.offline]} />
        <Text style={styles.connectionText}>{status?.systemStatus || "CONNECTING"}</Text>
        <Text style={styles.connectionMeta}>{status?.source || "production"}</Text>
      </View>

      {error ? (
        <View style={styles.error}>
          <Text style={styles.errorTitle}>LIVE ENDPOINT NOTICE</Text>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <Text style={styles.section}>LIVE METRICS</Text>
      <View style={styles.grid}>
        <Metric label="CPU" value={metrics?.cpu} />
        <Metric label="MEMORY" value={metrics?.memory} />
        <Metric label="STORAGE" value={metrics?.storage} />
        <Metric label="GPU" value={metrics?.gpu} />
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.infoLabel}>RAILWAY</Text>
        <Text style={styles.infoValue}>{deployment?.stage || "N/A"}</Text>
        <Text style={styles.infoMeta}>{deployment?.environment || "production"}</Text>
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.infoLabel}>COMMAND INTELLIGENCE</Text>
        <Text style={styles.infoValue}>
          {assistant?.commandMode || (assistant?.freeMode ? "FREE" : "CHECKING")}
        </Text>
        <Text style={styles.infoMeta}>
          GPT-5.6 when available · protected free-command fallback stays online
        </Text>
      </View>

      <Pressable style={styles.refresh} onPress={load}>
        <Text style={styles.refreshText}>REFRESH ALL LIVE STATUS</Text>
      </Pressable>

      <Text style={styles.section}>RESTORED FULL CAPABILITY SET</Text>
      <View style={styles.capabilityCard}>
        <Text style={styles.capability}>• Eagle Eyes World Command Operating System</Text>
        <Text style={styles.capability}>• Executive Mission Brief / operational snapshot</Text>
        <Text style={styles.capability}>• Protected Eagle Eyes Command Rail</Text>
        <Text style={styles.capability}>• GPT-5.6 tool routing when API access is active</Text>
        <Text style={styles.capability}>• Free command mode when API credits are unavailable</Text>
        <Text style={styles.capability}>• Real Railway runtime and deployment telemetry</Text>
        <Text style={styles.capability}>• Real container CPU, memory, storage, GPU and temperature availability</Text>
        <Text style={styles.capability}>• NOAA / NWS live weather alerts</Text>
        <Text style={styles.capability}>• USGS live earthquake intelligence</Text>
        <Text style={styles.capability}>• NASA EONET active natural events</Text>
        <Text style={styles.capability}>• Live Global Operations Map / Data Spine geography</Text>
        <Text style={styles.capability}>• Wikipedia world knowledge lookup</Text>
        <Text style={styles.capability}>• Open-Meteo global current weather</Text>
        <Text style={styles.capability}>• PX4 validated observation-only telemetry surface</Text>
        <Text style={styles.capability}>• Built-in live Web Search browser</Text>
      </View>
    </ScrollView>
  );
}

export default function App() {
  const [tab, setTab] = useState("world");
  const [section, setSection] = useState("overview");

  const openWorld = (nextSection) => {
    setSection(nextSection);
    setTab("world");
  };

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <View>
          <Text style={styles.brand}>EAGLE EYES</Text>
          <Text style={styles.brandSub}>WORLD COMMAND MOBILE · FULL SYSTEM</Text>
        </View>
        <View style={styles.livePill}>
          <View style={[styles.dot, styles.online]} />
          <Text style={styles.liveText}>LIVE</Text>
        </View>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.tabScroller}
        contentContainerStyle={styles.tabs}
      >
        <TabButton
          active={tab === "world" && section === "overview"}
          label="FULL OS"
          onPress={() => openWorld("overview")}
        />
        <TabButton
          active={tab === "world" && section === "runtime"}
          label="RUNTIME"
          onPress={() => openWorld("runtime")}
        />
        <TabButton
          active={tab === "world" && section === "intelligence"}
          label="INTEL"
          onPress={() => openWorld("intelligence")}
        />
        <TabButton
          active={tab === "world" && section === "command"}
          label="COMMAND"
          onPress={() => openWorld("command")}
        />
        <TabButton active={tab === "search"} label="WEB SEARCH" onPress={() => setTab("search")} />
        <TabButton active={tab === "status"} label="STATUS" onPress={() => setTab("status")} />
      </ScrollView>

      <View style={styles.flex}>
        {tab === "world" ? <WorldOS section={section} /> : null}
        {tab === "search" ? <WebSearch /> : null}
        {tab === "status" ? <LiveStatus /> : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#070706" },
  flex: { flex: 1 },
  header: {
    minHeight: 62,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(242,198,109,.18)",
    backgroundColor: "#0b0a08",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  brand: { color: "#f2c66d", fontSize: 17, fontWeight: "900", letterSpacing: 2.5 },
  brandSub: { color: "#8f8779", fontSize: 9, marginTop: 3, letterSpacing: 1.1 },
  livePill: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(115,229,140,.35)",
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 6
  },
  liveText: { color: "#73e58c", fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  tabScroller: {
    flexGrow: 0,
    backgroundColor: "#0b0a08",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(242,198,109,.18)"
  },
  tabs: { alignItems: "stretch" },
  tab: { minWidth: 86, alignItems: "center", justifyContent: "center", paddingVertical: 12, paddingHorizontal: 12 },
  tabActive: { backgroundColor: "rgba(242,198,109,.08)" },
  tabText: { color: "#81796c", fontSize: 10, fontWeight: "800", letterSpacing: 0.8 },
  tabTextActive: { color: "#f2c66d" },
  web: { flex: 1, backgroundColor: "#070706" },
  loading: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#070706"
  },
  loadingText: { color: "#a39a8c", marginTop: 12 },
  searchRow: {
    flexDirection: "row",
    gap: 8,
    padding: 10,
    backgroundColor: "#0b0a08",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(242,198,109,.15)"
  },
  searchInput: {
    flex: 1,
    color: "#f7f1e7",
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.3)",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#11100d"
  },
  searchButton: {
    justifyContent: "center",
    paddingHorizontal: 14,
    borderRadius: 10,
    backgroundColor: "#f2c66d"
  },
  searchButtonText: { color: "#181108", fontSize: 10, fontWeight: "900" },
  browserRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    paddingVertical: 9,
    backgroundColor: "#0b0a08"
  },
  browserText: { color: "#f2c66d", fontSize: 9, fontWeight: "800" },
  dim: { opacity: 0.35 },
  status: { flex: 1, backgroundColor: "#070706" },
  statusContent: { padding: 18, paddingBottom: 40 },
  eyebrow: { color: "#f2c66d", fontSize: 10, letterSpacing: 3, fontWeight: "800" },
  title: { color: "#f7f1e7", fontSize: 25, fontWeight: "900", marginTop: 5 },
  subtitle: { color: "#8f8779", marginTop: 6, marginBottom: 18 },
  connection: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.2)",
    borderRadius: 14,
    backgroundColor: "#11100d",
    padding: 14
  },
  dot: { width: 8, height: 8, borderRadius: 8, marginRight: 9 },
  online: { backgroundColor: "#73e58c" },
  offline: { backgroundColor: "#ff6f71" },
  connectionText: { color: "#f7f1e7", fontWeight: "800" },
  connectionMeta: { marginLeft: "auto", color: "#8f8779", fontSize: 10 },
  error: {
    marginTop: 14,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,111,113,.4)"
  },
  errorTitle: { color: "#ff8f90", fontWeight: "900", fontSize: 11 },
  errorText: { color: "#efc4c4", marginTop: 5 },
  section: { color: "#f2c66d", marginTop: 22, marginBottom: 10, fontWeight: "900", letterSpacing: 1.8 },
  grid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" },
  metric: {
    width: "48%",
    backgroundColor: "#11100d",
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.16)",
    padding: 15,
    marginBottom: 10
  },
  metricLabel: { color: "#8f8779", fontSize: 9, letterSpacing: 1 },
  metricValue: { color: "#f7f1e7", fontSize: 22, fontWeight: "900", marginTop: 6 },
  infoCard: {
    backgroundColor: "#11100d",
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.16)",
    padding: 15,
    marginTop: 10
  },
  infoLabel: { color: "#8f8779", fontSize: 9, letterSpacing: 1 },
  infoValue: { color: "#f7f1e7", fontSize: 18, fontWeight: "900", marginTop: 6 },
  infoMeta: { color: "#958d80", fontSize: 11, marginTop: 5, lineHeight: 17 },
  refresh: {
    marginTop: 14,
    backgroundColor: "#f2c66d",
    paddingVertical: 13,
    borderRadius: 11,
    alignItems: "center"
  },
  refreshText: { color: "#181108", fontWeight: "900", fontSize: 11, letterSpacing: 0.8 },
  capabilityCard: {
    backgroundColor: "#11100d",
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.16)",
    padding: 15
  },
  capability: { color: "#c9c1b4", fontSize: 12, lineHeight: 20 }
});
