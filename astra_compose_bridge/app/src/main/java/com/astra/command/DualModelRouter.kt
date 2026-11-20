package com.astra.command

import androidx.compose.runtime.Immutable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

@Immutable
data class DualModelConfig(
    val preset: String = "alstra_core_dual",
    val modelA: String = "alstra-core-primary",
    val modelB: String = "alstra-core-secondary",
    val routerPort: Int = 8173
)

class DualModelRouterClient(
    private val host: String = "127.0.0.1"
) {
    suspend fun dispatchDual(config: DualModelConfig, prompt: String): Result<String> =
        withContext(Dispatchers.IO) {
            runCatching {
                val payload = JSONObject().apply {
                    put("preset", config.preset)
                    put("model_a", config.modelA)
                    put("model_b", config.modelB)
                    put("prompt", prompt)
                }.toString()

                val conn = (URL("http://$host:${config.routerPort}/api/dual/dispatch").openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 1500
                    readTimeout = 2500
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json")
                }
                OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use {
                    it.write(payload)
                    it.flush()
                }
                val code = conn.responseCode
                val body = BufferedReader(InputStreamReader(
                    if (code in 200..299) conn.inputStream else conn.errorStream
                )).use { it.readText() }
                conn.disconnect()
                if (code !in 200..299) error("HTTP $code: $body")
                body
            }
        }
}
