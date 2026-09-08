import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View
} from "react-native";

const DOMAIN_LABELS = {
  api: "API TRAFFIC",
  shell: "SHELL SIGNALS",
  air: "AIR",
  water: "WATER",
  ground: "GROUND",
  system: "SYSTEM"
};

export default function ProtectionConsole({ baseUrl }) {
  const [shell, setShell] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");

    const results = await Promise.allSettled([
      fetch(baseUrl + "/api/eagle-eyes/shell-catcher/health", {
        headers: { Accept: "application/json" },
        cache: "no-store"
      }).then(async (response) => {
        if (!response.ok) throw new Error(`Shell Catcher HTTP ${response.status}`);
        return response.json();
      }),
      fetch(baseUrl + "/api/health", {
        headers: { Accept: "application/json" },
        cache: "no-store"
      }).then(async (response) => {
        if (!response.ok) throw new Error(`Health HTTP ${response.status}`);
        return response.json();
      })
    ]);

    if (results[0].status === "fulfilled") setShell(results[0].value);
    else setShell(null);

    if (results[1].status === "fulfilled") setHealth(results[1].value);

    const failures = results.filter((item) => item.status === "rejected");
    if (failures.length) {
      setError(failures.map((item) => item.reason?.message || "Protection endpoint unavailable").join(" • "));
    }

    setLoading(false);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [baseUrl]);

  const operational = shell?.operational === true;
  const domains = Array.isArray(shell?.domains)
    ? shell.domains
    : ["api", "shell", "air", "water", "ground", "system"];

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>EAGLE EYES · PROTECTION</Text>
      <Text style={styles.title}>SHELL CATCHER</Text>
      <Text style={styles.subtitle}>
        Defensive observation layer for command, API, environmental, and system signals.
      </Text>

      <View style={styles.hero}>
        <View style={[styles.dot, operational ? styles.good : styles.bad]} />
        <View style={styles.heroCopy}>
          <Text style={styles.heroLabel}>PROTECTION STATE</Text>
          <Text style={styles.heroValue}>
            {operational ? "OPERATIONAL" : loading ? "CHECKING" : "PENDING BACKEND"}
          </Text>
          <Text style={styles.meta}>
            {operational
              ? shell?.mode || "LIVE_DEFENSIVE_OBSERVATION"
              : "APK surface installed · waiting for the Shell Catcher endpoint on the selected backend"}
          </Text>
        </View>
        {loading ? <ActivityIndicator size="small" /> : null}
      </View>

      {error ? (
        <View style={styles.errorCard}>
          <Text style={styles.errorTitle}>LIVE SOURCE NOTICE</Text>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <Text style={styles.section}>COVERAGE</Text>
      <View style={styles.grid}>
        {domains.map((domain) => (
          <View key={domain} style={styles.domainCard}>
            <Text style={styles.domainName}>{DOMAIN_LABELS[domain] || String(domain).toUpperCase()}</Text>
            <Text style={[styles.domainState, !operational && styles.domainPending]}>
              {operational ? "WATCHING" : "PENDING"}
            </Text>
          </View>
        ))}
      </View>

      <Text style={styles.section}>CAPTURE STATE</Text>
      <View style={styles.card}>
        <Text style={styles.label}>EVENTS SEEN</Text>
        <Text style={styles.value}>{operational ? shell?.records?.total ?? 0 : "N/A"}</Text>
        <Text style={styles.meta}>
          {operational
            ? `Flagged: ${shell?.records?.flagged ?? 0} · retained: ${shell?.records?.retained ?? 0}/${shell?.records?.maxRetained ?? "N/A"}`
            : "No detector counts are claimed until the backend endpoint is live."}
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>INGEST</Text>
        <Text style={styles.value}>
          {operational ? (shell?.ingestConfigured ? "CONFIGURED" : "LOCKED") : "PENDING"}
        </Text>
        <Text style={styles.meta}>
          Remote ingest requires the backend SHELL_CATCHER_INGEST_TOKEN. No ingest secret is stored in this APK.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>COMMAND AUTHORITY</Text>
        <Text style={styles.value}>{shell?.commandAuthority ? "ENABLED" : "BLOCKED"}</Text>
        <Text style={styles.meta}>
          Arbitrary shell execution: {shell?.arbitraryShellExecution ? "enabled" : "blocked"}. This surface observes and detects; it does not become a remote shell.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>COMMAND CENTER HEALTH</Text>
        <Text style={styles.value}>{health?.ok ? "ONLINE" : "CHECKING"}</Text>
        <Text style={styles.meta}>
          Uptime: {Number.isFinite(health?.uptimeSeconds) ? `${health.uptimeSeconds}s` : "N/A"}
        </Text>
      </View>

      <Pressable style={styles.refresh} onPress={load}>
        <Text style={styles.refreshText}>REFRESH PROTECTION STATE</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#070706" },
  content: { padding: 18, paddingBottom: 40 },
  eyebrow: { color: "#f2c66d", fontSize: 10, fontWeight: "900", letterSpacing: 2.4 },
  title: { color: "#f7f1e7", fontSize: 28, fontWeight: "900", marginTop: 4 },
  subtitle: { color: "#8f8779", fontSize: 12, lineHeight: 18, marginTop: 6, marginBottom: 16 },
  hero: { flexDirection: "row", alignItems: "center", borderRadius: 14, borderWidth: 1, borderColor: "rgba(242,198,109,.2)", backgroundColor: "#11100d", padding: 15 },
  heroCopy: { flex: 1 },
  dot: { width: 10, height: 10, borderRadius: 10, marginRight: 11 },
  good: { backgroundColor: "#73e58c" },
  bad: { backgroundColor: "#ff6f71" },
  heroLabel: { color: "#8f8779", fontSize: 9, fontWeight: "900", letterSpacing: 1 },
  heroValue: { color: "#f7f1e7", fontSize: 20, fontWeight: "900", marginTop: 3 },
  section: { color: "#f2c66d", marginTop: 22, marginBottom: 10, fontWeight: "900", letterSpacing: 1.7 },
  grid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" },
  domainCard: { width: "48%", padding: 13, marginBottom: 10, borderRadius: 12, borderWidth: 1, borderColor: "rgba(242,198,109,.16)", backgroundColor: "#11100d" },
  domainName: { color: "#d4c8b4", fontSize: 10, fontWeight: "900" },
  domainState: { color: "#73e58c", fontSize: 9, marginTop: 6, fontWeight: "900", letterSpacing: 1 },
  domainPending: { color: "#f2c66d" },
  card: { padding: 15, marginBottom: 10, borderRadius: 13, borderWidth: 1, borderColor: "rgba(242,198,109,.16)", backgroundColor: "#11100d" },
  label: { color: "#8f8779", fontSize: 9, fontWeight: "900", letterSpacing: 1 },
  value: { color: "#f7f1e7", fontSize: 18, fontWeight: "900", marginTop: 5 },
  meta: { color: "#8f8779", fontSize: 10, lineHeight: 16, marginTop: 4 },
  errorCard: { marginTop: 12, padding: 12, borderRadius: 11, borderWidth: 1, borderColor: "rgba(255,111,113,.38)" },
  errorTitle: { color: "#ff8f90", fontSize: 10, fontWeight: "900" },
  errorText: { color: "#efc4c4", fontSize: 10, marginTop: 4 },
  refresh: { marginTop: 8, paddingVertical: 13, borderRadius: 11, backgroundColor: "#f2c66d", alignItems: "center" },
  refreshText: { color: "#181108", fontSize: 10, fontWeight: "900", letterSpacing: 0.8 }
});
