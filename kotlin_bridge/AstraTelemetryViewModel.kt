package com.astra.sovereign.telemetry

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.net.URL
import org.json.JSONObject

data class TelemetryUiState(
    val cpuFrequency: String = "3.20 GHz",
    val socketLatency: String = "1.2 ms",
    val activeWorkers: Int = 4,
    val isOnline: Boolean = true
)

class AstraTelemetryViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(TelemetryUiState())
    val uiState: StateFlow<TelemetryUiState> = _uiState.asStateFlow()

    init {
        pollTelemetrySpine()
    }

    private fun pollTelemetrySpine() {
        viewModelScope.launch {
            try {
                val response = URL("http://127.0.0.1:8080/api/telemetry").readText()
                val json = JSONObject(response)
                _uiState.value = _uiState.value.copy(
                    cpuFrequency = json.optString("cpu", "3.20 GHz"),
                    socketLatency = json.optString("latency", "1.2 ms")
                )
            } catch (e: Exception) {
                // Fallback state on network jitter
            }
        }
    }
}
