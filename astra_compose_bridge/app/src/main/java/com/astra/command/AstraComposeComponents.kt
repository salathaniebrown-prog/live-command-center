package com.astra.command

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun TelemetryCard(
    card: TelemetryCardUi,
    modifier: Modifier = Modifier
) {
    val accent = if (card.status.equals("ONLINE", ignoreCase = true)) {
        Color(0xFF3FB950)
    } else {
        Color(0xFFF85149)
    }
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, Color(0xFF21262D), RoundedCornerShape(8.dp)),
        shape = RoundedCornerShape(8.dp),
        color = Color(0xFF0D1117)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = card.label,
                    color = Color(0xFF8B949E),
                    fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.labelMedium
                )
                Text(
                    text = card.valueText,
                    color = accent,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodyLarge
                )
            }
            if (card.latencyMs > 0f) {
                Text(
                    text = "${card.latencyMs.toInt()}ms",
                    color = Color(0xFF58A6FF),
                    fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.labelSmall
                )
            }
        }
    }
}

@Composable
fun AgentGrid(
    agents: List<AgentNodeUi>,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            text = "ACTIVE AGENTS (${agents.size})",
            color = Color(0xFF58A6FF),
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.labelLarge
        )
        agents.forEach { agent ->
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, Color(0xFF1F2937), RoundedCornerShape(6.dp)),
                shape = RoundedCornerShape(6.dp),
                color = Color(0xFF090D12)
            ) {
                Row(
                    modifier = Modifier.padding(10.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "${agent.name} :${agent.port}",
                        color = Color(0xFFE6EDF3),
                        fontFamily = FontFamily.Monospace,
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(
                        text = "${agent.state} (${agent.loadPct.toInt()}%)",
                        color = Color(0xFF34D399),
                        fontFamily = FontFamily.Monospace,
                        style = MaterialTheme.typography.labelSmall
                    )
                }
            }
        }
    }
}

@Composable
fun CommandDeckRoute(
    viewModel: CommandDeckViewModel,
    modifier: Modifier = Modifier
) {
    val state by viewModel.uiState.collectAsState()

    DisposableEffect(viewModel) {
        viewModel.startPolling(2000L)
        onDispose { viewModel.stopPolling() }
    }

    CommandDeck(
        state = state,
        onRefresh = { viewModel.refreshOnce() },
        onWriteAction = { viewModel.triggerReadWriteExec() },
        modifier = modifier
    )
}

@Composable
fun CommandDeck(
    state: CommandDeckState,
    onRefresh: () -> Unit,
    onWriteAction: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFF06090E))
            .padding(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "ASTRA COMPOSE DECK",
                    color = Color(0xFF58A6FF),
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium
                )
                Text(
                    text = if (state.connected) "LINK: ${state.spineHost} [LIVE]" else "LINK: ${state.spineHost} [RETRY]",
                    color = if (state.connected) Color(0xFF3FB950) else Color(0xFFD29922),
                    fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.labelSmall
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onRefresh,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF21262D)),
                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Text("SYNC", fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
                }
                Button(
                    onClick = onWriteAction,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1F6FEB)),
                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Text("RW EXEC", fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "RW RECEIPT: ${state.lastActionReceipt}",
            color = Color(0xFF7EE787),
            fontFamily = FontFamily.Monospace,
            style = MaterialTheme.typography.labelSmall,
            maxLines = 2
        )

        state.lastError?.let { err ->
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "ERR: $err",
                color = Color(0xFFF85149),
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.labelSmall
            )
        }

        Spacer(modifier = Modifier.height(10.dp))

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(state.cards, key = { it.id }) { card ->
                TelemetryCard(card = card)
            }
            if (state.agents.isNotEmpty()) {
                item(key = "agent_grid") {
                    AgentGrid(agents = state.agents)
                }
            }
        }
    }
}
