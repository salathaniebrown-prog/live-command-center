package com.astra.command

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class CommandDeckViewModel(
    private val client: SpineBridgeClient = SpineBridgeClient("http://127.0.0.1:8090"),
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
) {
    private val _uiState = MutableStateFlow(CommandDeckState())
    val uiState: StateFlow<CommandDeckState> = _uiState.asStateFlow()

    private var pollJob: Job? = null

    fun startPolling(intervalMs: Long = 2000L) {
        if (pollJob?.isActive == true) return
        pollJob = scope.launch {
            while (isActive) {
                refreshOnce()
                delay(intervalMs)
            }
        }
    }

    fun stopPolling() {
        pollJob?.cancel()
        pollJob = null
    }

    fun refreshOnce() {
        scope.launch {
            val res = client.fetchSnapshot()
            val nowSec = System.currentTimeMillis() / 1000L
            res.onSuccess { (cards, agents) ->
                _uiState.update {
                    it.copy(
                        connected = true,
                        lastSyncEpochSec = nowSec,
                        cards = cards,
                        agents = agents,
                        lastError = null
                    )
                }
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        connected = false,
                        lastSyncEpochSec = nowSec,
                        lastError = err.message ?: "SPINE_UNREACHABLE"
                    )
                }
            }
        }
    }

    fun triggerReadWriteExec(goal: String = "COMPOSE_LIVE_WRITE") {
        scope.launch {
            val body = """{"type":"hash_payload","payload":{"goal":"$goal","ts":${System.currentTimeMillis() / 1000L}}}"""
            val res = client.dispatchReadWriteAction(
                endpoint = "/api/exec",
                targetPort = 8169,
                payloadJson = body
            )
            res.onSuccess { receipt ->
                _uiState.update { it.copy(lastActionReceipt = receipt, lastError = null) }
            }.onFailure { err ->
                _uiState.update { it.copy(lastError = err.message ?: "RW_DISPATCH_FAILED") }
            }
        }
    }
}
