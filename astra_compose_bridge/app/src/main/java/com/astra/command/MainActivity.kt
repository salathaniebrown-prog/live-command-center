package com.astra.command

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val viewModel = CommandDeckViewModel(SpineBridgeClient("http://127.0.0.1:8090"))

        setContent {
            var useLiveSpineDeck by remember { mutableStateOf(false) }

            DisposableEffect(viewModel) {
                viewModel.startPolling(2000L)
                onDispose { viewModel.stopPolling() }
            }

            Surface(
                modifier = Modifier.fillMaxSize(),
                color = Color(0xFF05080D)
            ) {
                Column(modifier = Modifier.fillMaxSize()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        FilterChip(
                            selected = !useLiveSpineDeck,
                            onClick = { useLiveSpineDeck = false },
                            label = { Text("M3 + 9950X3D2 + VR", fontFamily = FontFamily.Monospace) }
                        )
                        FilterChip(
                            selected = useLiveSpineDeck,
                            onClick = { useLiveSpineDeck = true },
                            label = { Text("LIVE :8090 SPINE", fontFamily = FontFamily.Monospace) }
                        )
                    }

                    if (useLiveSpineDeck) {
                        CommandDeckRoute(viewModel = viewModel)
                    } else {
                        Material3SovereignCommandScreen(
                            onDispatchJson = { rawJson ->
                                viewModel.triggerReadWriteExec(rawJson.take(120))
                            }
                        )
                    }
                }
            }
        }
    }
}
