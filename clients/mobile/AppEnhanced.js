import React, { useState } from "react";
import {
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View
} from "react-native";
import { StatusBar } from "expo-status-bar";
import ExistingEagleEyesApp from "./App";
import ChatConsole from "./ChatConsole";
import MissionCore from "./MissionCore";
import ProtectionConsole from "./ProtectionConsole";

const BASE_URL = (
  process.env.EXPO_PUBLIC_EAGLE_EYES_BASE_URL ||
  "https://live-command-center-production-31ed.up.railway.app"
).replace(/\/$/, "");

function ModeButton({ active, label, onPress }) {
  return (
    <Pressable onPress={onPress} style={[styles.modeButton, active && styles.modeButtonActive]}>
      <Text style={[styles.modeText, active && styles.modeTextActive]}>{label}</Text>
    </Pressable>
  );
}

export default function AppEnhanced() {
  const [mode, setMode] = useState("core");

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="light" />
      <View style={styles.modeBar}>
        <ModeButton active={mode === "chat"} label="CHATGPT" onPress={() => setMode("chat")} />
        <ModeButton active={mode === "core"} label="MISSION CORE" onPress={() => setMode("core")} />
        <ModeButton active={mode === "command"} label="COMMAND" onPress={() => setMode("command")} />
        <ModeButton active={mode === "protect"} label="PROTECT" onPress={() => setMode("protect")} />
      </View>
      <View style={styles.flex}>
        {mode === "chat" ? <ChatConsole baseUrl={BASE_URL} /> : null}
        {mode === "core" ? <MissionCore baseUrl={BASE_URL} /> : null}
        {mode === "command" ? <ExistingEagleEyesApp /> : null}
        {mode === "protect" ? <ProtectionConsole baseUrl={BASE_URL} /> : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#070706" },
  flex: { flex: 1 },
  modeBar: {
    flexDirection: "row",
    backgroundColor: "#070706",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(242,198,109,.2)",
    paddingHorizontal: 6,
    paddingVertical: 7,
    gap: 5
  },
  modeButton: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 40,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(242,198,109,.12)",
    backgroundColor: "#0d0c09",
    paddingHorizontal: 3
  },
  modeButtonActive: {
    borderColor: "rgba(242,198,109,.45)",
    backgroundColor: "#1a160f"
  },
  modeText: {
    color: "#81796c",
    fontSize: 8,
    fontWeight: "900",
    letterSpacing: 0.55,
    textAlign: "center"
  },
  modeTextActive: { color: "#f2c66d" }
});
