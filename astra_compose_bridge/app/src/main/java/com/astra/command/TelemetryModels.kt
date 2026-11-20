package com.astra.command

import androidx.compose.runtime.Immutable

@Immutable
data class TelemetryCardUi(
    val id: String,
    val label: String,
    val valueText: String,
    val status: String = "ONLINE",
    val latencyMs: Float = 0f
)

@Immutable
data class AgentNodeUi(
    val name: String,
    val port: Int,
    val state: String,
    val loadPct: Float
)

@Immutable
data class CommandDeckState(
    val spineHost: String = "http://127.0.0.1:8090",
    val connected: Boolean = false,
    val lastSyncEpochSec: Long = 0L,
    val cards: List<TelemetryCardUi> = emptyList(),
    val agents: List<AgentNodeUi> = emptyList(),
    val lastActionReceipt: String = "READY_RW",
    val lastError: String? = null
)
