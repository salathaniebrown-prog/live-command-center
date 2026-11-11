import java.io.*;
import java.nio.file.*;
import java.time.Instant;
import java.util.concurrent.*;

public class SpineLogger {
    public static void main(String[] args) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(4);
        long cycle = 0;
        while (true) {
            long t0 = System.nanoTime();
            Future<Double>[] tasks = new Future[4];
            for (int t = 0; t < 4; t++) {
                final int id = t + 1;
                tasks[t] = pool.submit(() -> {
                    double sum = 0;
                    for (int i = 1; i <= 150000; i++) {
                        sum += Math.sqrt(i * id) * Math.tanh(i * 0.0001);
                    }
                    return sum;
                });
            }
            double total = 0;
            for (Future<Double> f : tasks) total += f.get();
            double ms = (System.nanoTime() - t0) / 1e6;
            double mops = Math.round(((4.0 * 150000.0) / (ms / 1000.0)) / 1e4) / 100.0;
            cycle++;
            String json = String.format(
                "{\"ts\":\"%s\",\"source\":\"java-worker\",\"status\":\"JVM21-4T %.2f MOPS (%.1fms)\",\"cycle\":%d,\"hash\":%.2f}\n",
                Instant.now().toString(), mops, ms, cycle, total
            );
            Files.write(Paths.get("telemetry_spine.jsonl"), json.getBytes(),
                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            Thread.sleep(900);
        }
    }
}
