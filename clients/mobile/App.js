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


function LaunchDeck({ productionState, onOpenWorld, onOpenCommand, onOpenSearch, onOpenStatus }) {
  const statusLabel =
    productionState === "online"
      ? "PRODUCTION ONLINE"
      : productionState === "offline"
        ? "PRODUCTION UNREACHABLE"
        : "CHECKING PRODUCTION";

  return (
    <ScrollView style={styles.launch} contentContainerStyle={styles.launchContent}>
      <Text style={styles.eyebrow}>EAGLE EYES</Text>
      <Text style={styles.launchTitle}>WORLD COMMAND</Text>
      <Text style={styles.launchSubtitle}>
        Real production systems · live intelligence · no simulated telemetry
      </Text>

      <View style={styles.launchStatus}>
        <View
          style={[
            styles.dot,
            productionState === "online"
              ? styles.online
              : productionState === "offline"
                ? styles.offline
                : styles.checking
          ]}
        />
        <View style={styles.launchStatusTextWrap}>
          <Text style={styles.launchStatusLabel}>{statusLabel}</Text>
          <Text style={styles.launchStatusMeta}>
            {productionState === "checking"
              ? "Verifying /api/status before reporting live state"
              : productionState === "online"
                ? "Verified against the Eagle Eyes production backend"
                : "No live claim is shown until the backend responds"}
          </Text>
        </View>
      </View>

      <Pressable style={styles.launchPrimary} onPress={onOpenWorld}>
        <Text style={styles.launchPrimaryEyebrow}>ENTER EAGLE EYES</Text>
        <Text style={styles.launchPrimaryText}>OPEN FULL COMMAND OS</Text>
      </Pressable>

      <View style={styles.launchGrid}>
        <Pressable style={styles.launchCard} onPress={onOpenCommand}>
          <Text style={styles.launchCardLabel}>COMMAND RAIL</Text>
          <Text style={styles.launchCardText}>Open the protected command surface</Text>
        </Pressable>

        <Pressable style={styles.launchCard} onPress={onOpenSearch}>
          <Text style={styles.launchCardLabel}>LIVE WEB SEARCH</Text>
          <Text style={styles.launchCardText}>Search the live web inside Eagle Eyes</Text>
        </Pressable>

        <Pressable style={styles.launchCard} onPress={onOpenStatus}>
          <Text style={styles.launchCardLabel}>SYSTEM STATUS</Text>
          <Text style={styles.launchCardText}>Check Railway, metrics, and command mode</Text>
        </Pressable>

        <Pressable style={styles.launchCard} onPress={() => onOpenWorld("runtime")}>
          <Text style={styles.launchCardLabel}>RUNTIME</Text>
          <Text style={styles.launchCardText}>Open the production runtime surface</Text>
        </Pressable>
      </View>

      <Text style={styles.launchFoot}>
        Eagle Eyes does not invent telemetry. Unavailable live values remain unavailable or N/A.
      </Text>
    </ScrollView>
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
  const [tab, setTab] = useState("launch");
  const [section, setSection] = useState("overview");
  const [productionState, setProductionState] = useState("checking");

  const openWorld = (nextSection = "overview") => {
    setSection(nextSection);
    setTab("world");
  };

  useEffect(() => {
    let active = true;

    async function verifyProduction() {
      try {
        const response = await fetch(BASE_URL + "/api/status", {
          headers: { Accept: "application/json" }
        });
        const data = response.ok ? await response.json() : null;
        if (active) setProductionState(response.ok && data?.online ? "online" : "offline");
      } catch {
        if (active) setProductionState("offline");
      }
    }

    verifyProduction();
    const id = setInterval(verifyProduction, 15000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <View>
          <Text style={styles.brand}>EAGLE EYES</Text>
          <Text style={styles.brandSub}>WORLD COMMAND MOBILE · FULL SYSTEM</Text>
        </View>
        <View style={styles.livePill}>
          <View
            style={[
              styles.dot,
              productionState === "online"
                ? styles.online
                : productionState === "offline"
                  ? styles.offline
                  : styles.checking
            ]}
          />
          <Text
            style={[
              styles.liveText,
              productionState === "offline" && styles.liveTextOffline,
              productionState === "checking" && styles.liveTextChecking
            ]}
          >
            {productionState === "online"
              ? "ONLINE"
              : productionState === "offline"
                ? "OFFLINE"
                : "CHECKING"}
          </Text>
        </View>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.tabScroller}
        contentContainerStyle={styles.tabs}
      >
        <TabButton active={tab === "launch"} label="HOME" onPress={() => setTab("launch")} />
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
        {tab === "launch" ? (
          <LaunchDeck
            productionState={productionState}
            onOpenWorld={() => openWorld("overview")}
            onOpenCommand={() => openWorld("command")}
            onOpenSearch={() => setTab("search")}
            onOpenStatus={() => setTab("status")}
          />
        ) : null}
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
  liveTextOffline: { color: "#ff8f90" },
  liveTextChecking: { color: "#f2c66d" },
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
  launch: { flex: 1, backgroundColor: "#070706" },
  launchContent: { padding: 20, paddingTop: 28, paddingBottom: 44 },
  launchTitle: {
    color: "#f7f1e7",
    fontSize: 34,
    fontWeight: "900",
    letterSpacing: 0.8,
    marginTop: 7
  },
  launchSubtitle: {
    color: "#9f978a",
    fontSize: 13,
    lineHeight: 20,
    marginTop: 7,
    marginBottom: 20
  },
  launchStatus: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#11100d",
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.22)",
    borderRadius: 14,
    padding: 15,
    marginBottom: 16
  },
  launchStatusTextWrap: { flex: 1 },
  launchStatusLabel: { color: "#f7f1e7", fontSize: 12, fontWeight: "900", letterSpacing: 1 },
  launchStatusMeta: { color: "#8f8779", fontSize: 10, lineHeight: 15, marginTop: 4 },
  launchPrimary: {
    backgroundColor: "#f2c66d",
    borderRadius: 16,
    padding: 20,
    marginBottom: 12
  },
  launchPrimaryEyebrow: { color: "#5c421b", fontSize: 9, fontWeight: "900", letterSpacing: 1.8 },
  launchPrimaryText: { color: "#181108", fontSize: 20, fontWeight: "900", marginTop: 5 },
  launchGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between"
  },
  launchCard: {
    width: "48.5%",
    minHeight: 118,
    backgroundColor: "#11100d",
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.18)",
    borderRadius: 14,
    padding: 15,
    marginTop: 10
  },
  launchCardLabel: { color: "#f2c66d", fontSize: 10, fontWeight: "900", letterSpacing: 1.1 },
  launchCardText: { color: "#c9c1b4", fontSize: 11, lineHeight: 17, marginTop: 9 },
  launchFoot: { color: "#746e64", fontSize: 10, lineHeight: 16, marginTop: 20 },
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
  checking: { backgroundColor: "#f2c66d" },
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
