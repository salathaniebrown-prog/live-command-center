package com.astra.command

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class SpineBridgeClient(
    private val baseUrl: String = "http://127.0.0.1:8090"
) {
    suspend fun fetchSnapshot(): Result<Pair<List<TelemetryCardUi>, List<AgentNodeUi>>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val conn = (URL("$baseUrl/api/telemetry/spine").openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 1500
                    readTimeout = 2000
                    setRequestProperty("Accept", "application/json")
                }
                val code = conn.responseCode
                val body = BufferedReader(InputStreamReader(
                    if (code in 200..299) conn.inputStream else conn.errorStream
                )).use { it.readText() }
                conn.disconnect()

                val root = JSONObject(body)
                val cards = mutableListOf<TelemetryCardUi>()
                val portsObj = root.optJSONObject("ports")
                if (portsObj != null) {
                    val keys = portsObj.keys()
                    var idx = 0
                    while (keys.hasNext() && idx < 12) {
                        val k = keys.next()
                        val st = portsObj.optString(k, "UNKNOWN")
                        cards.add(
                            TelemetryCardUi(
                                id = "port_$k",
                                label = "PORT :$k",
                                valueText = st,
                                status = st
                            )
                        )
                        idx++
                    }
                }
                if (cards.isEmpty()) {
                    cards.add(
                        TelemetryCardUi(
                            id = "spine_8090",
                            label = "SPINE :8090",
                            valueText = root.optString("status", "ONLINE"),
                            status = root.optString("status", "ONLINE")
                        )
                    )
                }

                val agents = mutableListOf<AgentNodeUi>()
                val arr: JSONArray? = root.optJSONArray("agents")
                if (arr != null) {
                    for (i in 0 until arr.length()) {
                        val item = arr.optJSONObject(i) ?: continue
                        agents.add(
                            AgentNodeUi(
                                name = item.optString("name", "agent_$i"),
                                port = item.optInt("port", 8090),
                                state = item.optString("status", "ONLINE"),
                                loadPct = item.optDouble("load", 0.0).toFloat()
                            )
                        )
                    }
                }
                Pair(cards, agents)
            }
        }

    suspend fun dispatchReadWriteAction(
        endpoint: String = "/api/exec",
        targetPort: Int = 8169,
        payloadJson: String = """{"type":"hash_payload","payload":{"source":"compose_bridge_8090"}}"""
    ): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val urlStr = if (targetPort == 8090) "$baseUrl$endpoint" else "http://127.0.0.1:$targetPort$endpoint"
            val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 2000
                readTimeout = 3000
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
            }
            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use {
                it.write(payloadJson)
                it.flush()
            }
            val code = conn.responseCode
            val resp = BufferedReader(InputStreamReader(
                if (code in 200..299) conn.inputStream else conn.errorStream
            )).use { it.readText() }
            conn.disconnect()
            if (code !in 200..299) error("HTTP $code: $resp")
            resp.take(240)
        }
    }
}
