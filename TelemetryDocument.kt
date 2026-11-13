// Simple pure-Kotlin vector quantization and distance test
class TelemetryDocument(val id: Long, val title: String, val embedding: FloatArray)

fun cosineSimilarity(a: FloatArray, b: FloatArray): Float {
    var dot = 0f; var normA = 0f; var normB = 0f
    for (i in a.indices) {
        dot += a[i] * b[i]
        normA += a[i] * a[i]
        normB += b[i] * b[i]
    }
    return dot / (Math.sqrt(normA.toDouble()) * Math.sqrt(normB.toDouble())).toFloat()
}

fun main() {
    println("[+] Initializing Kotlin Vector Telemetry Engine...")
    val doc = TelemetryDocument(1, "Astra Core Vector", floatArrayOf(0.1f, 0.5f, 0.9f))
    val query = floatArrayOf(0.12f, 0.48f, 0.88f)
    
    val score = cosineSimilarity(doc.embedding, query)
    println("[+] Telemetry Entity ID: ${doc.id} | Title: ${doc.title}")
    println("[+] Calculated Cosine Similarity Score: $score")
}
