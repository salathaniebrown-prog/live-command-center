package com.astra.command

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlin.math.PI
import kotlin.math.sin

private val AstraDarkColorScheme = darkColorScheme(
    primary = Color(0xFF58A6FF),
    onPrimary = Color(0xFF04101D),
    secondary = Color(0xFF3FB950),
    onSecondary = Color(0xFF031508),
    background = Color(0xFF05080D),
    onBackground = Color(0xFFF0F6FC),
    surface = Color(0xFF0D1117),
    onSurface = Color(0xFFF0F6FC),
    surfaceVariant = Color(0xFF161B22),
    onSurfaceVariant = Color(0xFF8B949E),
    outline = Color(0xFF30363D),
    error = Color(0xFFF85149)
)

@Immutable
data class Ryzen9950X3D2Telemetry(
    val packageTempC: Float = 64.5f,
    val vcacheCcdTempC: Float = 61.2f,
    val socketPowerW: Float = 148.0f,
    val imcMode: String = "DDR5-6400_SWEETSPOT",
    val uclkMclkRatio: String = "1:1 (3200 MHz)",
    val ddr59600Selected: Boolean = false
)

@Immutable
data class DeepSpaceSignalState(
    val vrNodeLabel: String = "ALSTRA-VR-01 // DEEP-SPACE",
    val snrDb: Float = 24.8f,
    val carrierHz: Float = 2.4f,
    val phaseTick: Float = 0f,
    val streamLines: List<String> = emptyList()
)

fun formatNexusPayload(endpoint: String, rawJson: String, asCurl: Boolean, targetUrl: String = "http://127.0.0.1:8169"): String {
    if (!asCurl) return rawJson.trim()
    val escaped = rawJson.trim().replace("'", "'\\''")
    return "curl -s -X POST \"$targetUrl$endpoint\" -H \"Content-Type: application/json\" -d '$escaped'"
}

@Composable
fun Ryzen9950X3D2Card(
    hw: Ryzen9950X3D2Telemetry,
    onToggleMemoryProfile: (Boolean) -> Unit,
    modifier: Modifier = Modifier
) {
    val activeProfile = if (hw.ddr59600Selected) "DDR5-9600 (OC 2:1)" else "DDR5-6400 (SWEETSPOT 1:1)"
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, Color(0xFF2B3544), RoundedCornerShape(10.dp)),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "RYZEN 9 9950X3D2 // IMC & THERMALS",
                        color = MaterialTheme.colorScheme.primary,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleSmall
                    )
                    Text(
                        text = "PKG ${hw.packageTempC}°C | 3D-VCACHE ${hw.vcacheCcdTempC}°C | ${hw.socketPowerW}W",
                        color = MaterialTheme.colorScheme.onSurface,
                        fontFamily = FontFamily.Monospace,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = if (hw.ddr59600Selected) "DDR5-9600" else "DDR5-6400",
                        color = if (hw.ddr59600Selected) Color(0xFFD29922) else MaterialTheme.colorScheme.secondary,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.labelLarge
                    )
                    Switch(
                        checked = hw.ddr59600Selected,
                        onCheckedChange = onToggleMemoryProfile
                    )
                }
            }
            Text(
                text = "PROFILE: $activeProfile | ${hw.uclkMclkRatio}",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.labelSmall
            )
        }
    }
}

@Composable
fun DeepSpaceSignalCanvas(
    signal: DeepSpaceSignalState,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, Color(0xFF1F3A52), RoundedCornerShape(10.dp)),
        shape = RoundedCornerShape(10.dp),
        color = Color(0xFF060B12)
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = signal.vrNodeLabel,
                    color = Color(0xFF58A6FF),
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge
                )
                Text(
                    text = "SNR ${signal.snrDb} dB",
                    color = Color(0xFF3FB950),
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge
                )
            }

            Canvas(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(104.dp)
                    .background(Color(0xFF04070C), RoundedCornerShape(6.dp))
            ) {
                val w = size.width
                val h = size.height
                val midY = h * 0.5f

                // Subtle grid baseline
                drawLine(
                    color = Color(0xFF16202C),
                    start = Offset(0f, midY),
                    end = Offset(w, midY),
                    strokeWidth = 1f
                )

                // Continuous composite waveform (VR telemetry + Deep Space carrier + SNR modulation)
                val path = Path()
                val steps = 128
                for (i in 0..steps) {
                    val frac = i.toFloat() / steps.toFloat()
                    val x = frac * w
                    val theta = (frac * 4.0 * PI) + signal.phaseTick.toDouble()
                    val harmonic = 0.65 * sin(theta) + 0.35 * sin(theta * 2.3 + 0.7)
                    val snrScale = (signal.snrDb / 30f).coerceIn(0.25f, 1.0f)
                    val y = midY - (harmonic * (h * 0.36f) * snrScale).toFloat()
                    if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }

                drawPath(
                    path = path,
                    color = Color(0xFF39D353),
                    style = Stroke(width = 2.5f, cap = StrokeCap.Round)
                )
            }
        }
    }
}

@Composable
fun NexusCurlJsonTerminal(
    endpoint: String,
    jsonPayload: String,
    curlMode: Boolean,
    logs: List<String>,
    onToggleCurlMode: (Boolean) -> Unit,
    onPayloadChange: (String) -> Unit,
    onSendPayload: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, Color(0xFF2B3544), RoundedCornerShape(10.dp)),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "NEXUS TERMINAL // ${if (curlMode) "cURL" else "JSON"}",
                    color = MaterialTheme.colorScheme.primary,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleSmall
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    FilterChip(
                        selected = !curlMode,
                        onClick = { onToggleCurlMode(false) },
                        label = { Text("JSON", fontFamily = FontFamily.Monospace) }
                    )
                    FilterChip(
                        selected = curlMode,
                        onClick = { onToggleCurlMode(true) },
                        label = { Text("cURL", fontFamily = FontFamily.Monospace) }
                    )
                }
            }

            val renderedText = formatNexusPayload(endpoint, jsonPayload, curlMode)
            OutlinedTextField(
                value = renderedText,
                onValueChange = { updated ->
                    if (!curlMode) onPayloadChange(updated)
                },
                readOnly = curlMode,
                modifier = Modifier.fillMaxWidth(),
                minLines = 3,
                maxLines = 5
            )

            Button(
                onClick = { onSendPayload(jsonPayload) },
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
            ) {
                Text(
                    text = "DISPATCH TELEMETRY",
                    color = MaterialTheme.colorScheme.onPrimary,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF05080D), RoundedCornerShape(6.dp))
                    .padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                Text(
                    text = "REAL-TIME STREAM (${logs.size})",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.labelSmall
                )
                logs.takeLast(8).forEach { line ->
                    Text(
                        text = line,
                        color = Color(0xFF7EE787),
                        fontFamily = FontFamily.Monospace,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Material3SovereignCommandScreen(
    clusterBadge: String = "36+ PORTS // MESH ONLINE",
    hw: Ryzen9950X3D2Telemetry = Ryzen9950X3D2Telemetry(),
    signal: DeepSpaceSignalState = DeepSpaceSignalState(),
    initialLogs: List<String> = listOf("[8090] SPINE STREAM CONNECTED", "[8169] RW LEDGER READY"),
    onDispatchJson: (String) -> Unit = {}
) {
    var curlMode by remember { mutableStateOf(false) }
    var ddr59600 by remember { mutableStateOf(hw.ddr59600Selected) }
    var payloadJson by remember {
        mutableStateOf("""{"type":"hash_payload","payload":{"lane":"NEXUS_M3","ddr5":${if (hw.ddr59600Selected) 9600 else 6400}}}""")
    }
    var logs by remember { mutableStateOf(initialLogs) }

    val activeHw = hw.copy(
        ddr59600Selected = ddr59600,
        imcMode = if (ddr59600) "DDR5-9600_OC" else "DDR5-6400_SWEETSPOT",
        uclkMclkRatio = if (ddr59600) "2:1 (4800 MHz UCLK)" else "1:1 (3200 MHz UCLK)"
    )

    MaterialTheme(colorScheme = AstraDarkColorScheme) {
        Scaffold(
            topBar = {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.surface,
                        titleContentColor = MaterialTheme.colorScheme.onSurface
                    ),
                    title = {
                        Column {
                            Text(
                                text = "ASTRA // ALSTRA M3 CORE",
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.titleMedium
                            )
                            Text(
                                text = clusterBadge,
                                color = MaterialTheme.colorScheme.secondary,
                                fontFamily = FontFamily.Monospace,
                                style = MaterialTheme.typography.labelSmall
                            )
                        }
                    }
                )
            },
            containerColor = MaterialTheme.colorScheme.background
        ) { innerPadding ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                item(key = "ryzen_hw") {
                    Ryzen9950X3D2Card(
                        hw = activeHw,
                        onToggleMemoryProfile = { enabled ->
                            ddr59600 = enabled
                            logs = logs + "[9950X3D2] Switched profile -> ${if (enabled) "DDR5-9600" else "DDR5-6400 sweetspot"}"
                        }
                    )
                }
                item(key = "deep_space_vr") {
                    DeepSpaceSignalCanvas(signal = signal)
                }
                item(key = "nexus_term") {
                    NexusCurlJsonTerminal(
                        endpoint = "/api/exec",
                        jsonPayload = payloadJson,
                        curlMode = curlMode,
                        logs = logs,
                        onToggleCurlMode = { curlMode = it },
                        onPayloadChange = { payloadJson = it },
                        onSendPayload = { sent ->
                            logs = logs + "[DISPATCH] $sent"
                            onDispatchJson(sent)
                        }
                    )
                }
                item(key = "bottom_pad") {
                    Spacer(modifier = Modifier.height(12.dp))
                }
            }
        }
    }
}

// ASTRA_DUAL_8173_COMPOSE
@Composable
fun DualModelDispatchCard(
    routerClient: DualModelRouterClient = DualModelRouterClient(),
    config: DualModelConfig = DualModelConfig(),
    onReceipt: (String) -> Unit = {}
) {
    var running by remember { mutableStateOf(false) }
    var receipt by remember { mutableStateOf("DUAL :8173 READY") }
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, Color(0xFF1F3A52), RoundedCornerShape(10.dp)),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                text = "DUAL MODEL ROUTER // :${config.routerPort}",
                color = MaterialTheme.colorScheme.primary,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleSmall
            )
            Text(
                text = "${config.modelA} + ${config.modelB}",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall
            )
            Button(
                onClick = {
                    if (!running) {
                        running = true
                        receipt = "DISPATCHING_DUAL..."
                        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Main).launch {
                            val res = routerClient.dispatchDual(config, "COMPOSE_M3_DUAL_DISPATCH")
                            res.onSuccess { body ->
                                receipt = body.take(180)
                                onReceipt(receipt)
                            }.onFailure { err ->
                                receipt = "ERR: ${err.message}"
                            }
                            running = false
                        }
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.secondary)
            ) {
                Text(
                    text = if (running) "RUNNING..." else "DISPATCH DUAL MODELS",
                    color = MaterialTheme.colorScheme.onSecondary,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            }
            Text(
                text = receipt,
                color = Color(0xFF7EE787),
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}
