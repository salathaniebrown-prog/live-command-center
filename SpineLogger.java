import java.nio.file.*;
import java.time.Instant;

public class SpineLogger {
    public static void main(String[] args) throws Exception {
        System.out.println("[JAVA-WORKER] Feeding telemetry into spine...");
        int cycle = 1;
        while (true) {
            String json = String.format(
                "{\"source\":\"java-worker\",\"timestamp\":\"%s\",\"status\":\"ACTIVE\",\"cycle\":%d}\n",
                Instant.now().toString(), cycle++
            );
            Files.writeString(Path.of("telemetry_spine.jsonl"), json, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            Thread.sleep(2000);
        }
    }
}
