import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View
} from "react-native";
import { WebView } from "react-native-webview";

const CORE_SECTIONS = [
  {
    id: "live",
    label: "LIVE MAP",
    title: "LIVE EARTH + ORBITAL OPERATIONS",
    detail: "Recovered tactical world view with verified public-event feeds and CelesTrak satellite operations."
  },
  {
    id: "intel",
    label: "INTEL",
    title: "VERIFIED EVENT INTELLIGENCE",
    detail: "USGS earthquakes, NASA EONET natural events, NOAA/NWS alerts and source-grounded intelligence."
  },
  {
    id: "world",
    label: "MISSION",
    title: "TELEMETRY + MISSION WALL",
    detail: "Railway runtime, deployment state, container telemetry and the recovered World Command operating picture."
  },
  {
    id: "lab",
    label: "CHRONICLE",
    title: "CHRONICLE LAB V13",
    detail: "Chronicle Scribe, signed telemetry, oracle truth surfaces and the preserved V13 laboratory lane."
  },
  {
    id: "max",
    label: "EXEC AI",
    title: "EXECUTIVE AI + COMMAND RAIL",
    detail: "Executive Chief decision support and Eagle Eyes MAX command intelligence with existing access controls preserved."
  }
];

function CoreButton({ active, label, onPress }) {
  return (
    <Pressable onPress={onPress} style={[styles.coreButton, active && styles.coreButtonActive]}>
      <Text style={[styles.coreButtonText, active && styles.coreButtonTextActive]}>{label}</Text>
    </Pressable>
  );
}

export default function MissionCore({ baseUrl }) {
  const [section, setSection] = useState("live");
  const [loaded, setLoaded] = useState(false);
  const [webError, setWebError] = useState("");
  const [reloadNonce, setReloadNonce] = useState(0);

  const selected = useMemo(
    () => CORE_SECTIONS.find((item) => item.id === section) || CORE_SECTIONS[0],
    [section]
  );
  const uri = `${baseUrl}/#${section}`;

  const openSection = (nextSection) => {
    setLoaded(false);
    setWebError("");
    setSection(nextSection);
    setReloadNonce((value) => value + 1);
  };

  return (
    <View style={styles.flex}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>EAGLE EYES · MISSION CORE</Text>
          <Text style={styles.title}>RECOVERED MIDDLE STACK</Text>
          <Text style={styles.subtitle}>
            Map · satellites · verified intelligence · telemetry · Chronicle · Executive AI
          </Text>
        </View>
        <View style={[styles.statePill, webError ? styles.statePillError : styles.statePillLive]}>
          <View style={[styles.dot, webError ? styles.dotError : styles.dotLive]} />
          <Text style={[styles.stateText, webError ? styles.stateTextError : styles.stateTextLive]}>
            {webError ? "VIEW ERROR" : loaded ? "LIVE VIEW" : "LOADING"}
          </Text>
        </View>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.navScroller}
        contentContainerStyle={styles.nav}
      >
        {CORE_SECTIONS.map((item) => (
          <CoreButton
            key={item.id}
            active={section === item.id}
            label={item.label}
            onPress={() => openSection(item.id)}
          />
        ))}
      </ScrollView>

      <View style={styles.sectionBar}>
        <View style={styles.sectionCopy}>
          <Text style={styles.sectionTitle}>{selected.title}</Text>
          <Text style={styles.sectionDetail}>{selected.detail}</Text>
        </View>
      </View>

      {webError ? (
        <View style={styles.notice}>
          <Text style={styles.noticeTitle}>LIVE VIEW NOTICE</Text>
          <Text style={styles.noticeText}>{webError}</Text>
          <Pressable style={styles.retry} onPress={() => openSection(section)}>
            <Text style={styles.retryText}>RETRY MISSION CORE</Text>
          </Pressable>
        </View>
      ) : null}

      <WebView
        key={`${section}-${reloadNonce}`}
        source={{ uri }}
        style={styles.web}
        originWhitelist={["https://*", "http://*"]}
        javaScriptEnabled
        domStorageEnabled
        sharedCookiesEnabled
        thirdPartyCookiesEnabled
        setSupportMultipleWindows={false}
        startInLoadingState
        renderLoading={() => (
          <View style={styles.loading}>
            <ActivityIndicator size="large" />
            <Text style={styles.loadingText}>Opening {selected.label}…</Text>
          </View>
        )}
        onLoadEnd={() => setLoaded(true)}
        onError={(event) => {
          setLoaded(false);
          setWebError(event?.nativeEvent?.description || "Mission Core could not open the live section.");
        }}
        onHttpError={(event) => {
          setLoaded(false);
          const code = event?.nativeEvent?.statusCode;
          setWebError(code ? `Mission Core live section returned HTTP ${code}.` : "Mission Core live section returned an HTTP error.");
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#070706" },
  header: {
    minHeight: 86,
    paddingHorizontal: 14,
    paddingVertical: 11,
    backgroundColor: "#0b0a08",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(242,198,109,.18)",
    flexDirection: "row",
    alignItems: "center"
  },
  headerCopy: { flex: 1, paddingRight: 10 },
  eyebrow: { color: "#f2c66d", fontSize: 9, fontWeight: "900", letterSpacing: 1.7 },
  title: { color: "#f7f1e7", fontSize: 18, fontWeight: "900", marginTop: 4, letterSpacing: 0.4 },
  subtitle: { color: "#8f8779", fontSize: 10, lineHeight: 14, marginTop: 4 },
  statePill: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 18,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 6
  },
  statePillLive: { borderColor: "rgba(115,229,140,.32)" },
  statePillError: { borderColor: "rgba(255,111,113,.4)" },
  dot: { width: 7, height: 7, borderRadius: 7, marginRight: 6 },
  dotLive: { backgroundColor: "#73e58c" },
  dotError: { backgroundColor: "#ff6f71" },
  stateText: { fontSize: 8, fontWeight: "900", letterSpacing: 0.6 },
  stateTextLive: { color: "#73e58c" },
  stateTextError: { color: "#ff8f90" },
  navScroller: {
    flexGrow: 0,
    backgroundColor: "#0b0a08",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(242,198,109,.14)"
  },
  nav: { paddingHorizontal: 8, paddingVertical: 7, gap: 6 },
  coreButton: {
    minWidth: 82,
    minHeight: 34,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 10,
    borderRadius: 9,
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.12)",
    backgroundColor: "#11100d"
  },
  coreButtonActive: {
    borderColor: "rgba(242,198,109,.45)",
    backgroundColor: "#1a160f"
  },
  coreButtonText: { color: "#81796c", fontSize: 8, fontWeight: "900", letterSpacing: 0.7 },
  coreButtonTextActive: { color: "#f2c66d" },
  sectionBar: {
    paddingHorizontal: 14,
    paddingVertical: 9,
    backgroundColor: "#0d0c09",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(242,198,109,.12)"
  },
  sectionCopy: { flex: 1 },
  sectionTitle: { color: "#f2c66d", fontSize: 10, fontWeight: "900", letterSpacing: 1 },
  sectionDetail: { color: "#958d80", fontSize: 9, lineHeight: 13, marginTop: 3 },
  web: { flex: 1, backgroundColor: "#070706" },
  loading: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#070706"
  },
  loadingText: { color: "#a39a8c", marginTop: 10, fontSize: 11 },
  notice: {
    margin: 10,
    padding: 12,
    borderRadius: 11,
    borderWidth: 1,
    borderColor: "rgba(255,111,113,.35)",
    backgroundColor: "#140d0d"
  },
  noticeTitle: { color: "#ff8f90", fontSize: 9, fontWeight: "900", letterSpacing: 0.9 },
  noticeText: { color: "#efc4c4", fontSize: 10, lineHeight: 15, marginTop: 5 },
  retry: {
    marginTop: 9,
    alignSelf: "flex-start",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.35)",
    paddingHorizontal: 10,
    paddingVertical: 7
  },
  retryText: { color: "#f2c66d", fontSize: 8, fontWeight: "900", letterSpacing: 0.7 }
});
