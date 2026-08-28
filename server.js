const express = require("express");
const path = require("path");
const fs = require("fs").promises;
const os = require("os");
const child_process = require("child_process");
const util = require("util");

const exec = util.promisify(child_process.exec);

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

/*
 * Demo/static data.
 *
 * CPU, memory, and storage are measured at runtime by /api/metrics.
 * GPU and temperature return null unless actually available.
 */
const demo = {
  status: {
    online: true,
    systemStatus: "OPTIMAL",
    deployment: 100,
    mode: "LIVE"
  },

  metrics: {
    cpu: null,
    gpu: null,
    memory: null,
    storage: null,
    temperatureC: null
  },

  workloads: [
    "AI model training",
    "Physics simulation",
    "Neural rendering",
    "Data analytics",
    "Real-world testing",
    "Digital twins"
  ],

  deployment: {
    progress: 100,
    stage: "LIVE",
    success: true
  }
};

/*
 * Optional upstream API adapters.
 *
 * Existing environment variables are preserved:
 * STATUS_URL
 * METRICS_URL
 * WORKLOADS_URL
 * DEPLOYMENT_URL
 */
async function upstream(url, fallback) {
  if (!url) return fallback;

  try {
    const r = await fetch(url, {
      headers: {
        accept: "application/json"
      }
    });

    if (!r.ok) {
      throw new Error(`HTTP ${r.status}`);
    }

    return await r.json();
  } catch (e) {
    return {
      ...fallback,
      upstreamError: e.message
    };
  }
}

/* Safe file reader */
async function readFileSafe(file) {
  try {
    const value = await fs.readFile(file, "utf8");
    return value.trim();
  } catch {
    return null;
  }
}

/*
 * ------------------------------------------------------------
 * CPU
 * ------------------------------------------------------------
 */

/* Read cgroup CPU usage in nanoseconds. */
async function readCgroupCpuUsageNs() {
  /*
   * cgroup v2:
   * /sys/fs/cgroup/cpu.stat
   *
   * Contains:
   * usage_usec <value>
   */
  const cpuStat = await readFileSafe(
    "/sys/fs/cgroup/cpu.stat"
  );

  if (cpuStat) {
    const match = cpuStat.match(
      /(?:^|\n)usage_usec\s+(\d+)/
    );

    if (match) {
      return Number(match[1]) * 1000;
    }
  }

  /*
   * cgroup v1:
   * cpuacct.usage
   */
  const v1Paths = [
    "/sys/fs/cgroup/cpuacct/cpuacct.usage",
    "/sys/fs/cgroup/cpuacct.usage",
    "/sys/fs/cgroup/cpu,cpuacct/cpuacct.usage"
  ];

  for (const file of v1Paths) {
    const value = await readFileSafe(file);

    if (value && /^\d+$/.test(value)) {
      return Number(value);
    }
  }

  return null;
}

/*
 * Read the CPU quota assigned to the container.
 *
 * Returns the number of CPUs available to the cgroup.
 *
 * Example:
 *   1    = one CPU
 *   0.5  = half a CPU
 *   2    = two CPUs
 *
 * null means no CPU quota was detected.
 */
async function getCgroupCpuQuotaRatio() {
  /*
   * cgroup v2:
   * cpu.max
   *
   * Example:
   * 100000 100000
   *
   * means one CPU.
   */
  const v2 = await readFileSafe(
    "/sys/fs/cgroup/cpu.max"
  );

  if (v2) {
    const parts = v2.split(/\s+/);

    if (parts[0] === "max") {
      return null;
    }

    if (parts.length >= 2) {
      const quota = Number(parts[0]);
      const period = Number(parts[1]);

      if (
        Number.isFinite(quota) &&
        Number.isFinite(period) &&
        quota > 0 &&
        period > 0
      ) {
        return quota / period;
      }
    }
  }

  /*
   * cgroup v1.
   */
  const paths = [
    {
      quota:
        "/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
      period:
        "/sys/fs/cgroup/cpu/cpu.cfs_period_us"
    },
    {
      quota:
        "/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_quota_us",
      period:
        "/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_period_us"
    },
    {
      quota:
        "/sys/fs/cgroup/cpu.cfs_quota_us",
      period:
        "/sys/fs/cgroup/cpu.cfs_period_us"
    }
  ];

  for (const item of paths) {
    const quotaValue = await readFileSafe(item.quota);
    const periodValue = await readFileSafe(item.period);

    if (quotaValue == null || periodValue == null) {
      continue;
    }

    const quota = Number(quotaValue);
    const period = Number(periodValue);

    /*
     * -1 means unlimited in cgroup v1.
     */
    if (quota === -1) {
      return null;
    }

    if (
      Number.isFinite(quota) &&
      Number.isFinite(period) &&
      quota > 0 &&
      period > 0
    ) {
      return quota / period;
    }
  }

  return null;
}

/*
 * Calculate CPU percentage over a short sampling interval.
 *
 * If a cgroup CPU quota exists, percentage is calculated
 * relative to that quota.
 */
async function getCpuPercent(sampleMs = 250) {
  const start = await readCgroupCpuUsageNs();

  if (start == null) {
    return null;
  }

  await new Promise(resolve =>
    setTimeout(resolve, sampleMs)
  );

  const end = await readCgroupCpuUsageNs();

  if (end == null) {
    return null;
  }

  const deltaNs = end - start;

  if (deltaNs < 0) {
    return null;
  }

  const deltaCpuSeconds = deltaNs / 1e9;
  const intervalSeconds = sampleMs / 1000;

  const quotaRatio =
    await getCgroupCpuQuotaRatio();

  let availableCpuSeconds;

  if (
    quotaRatio !== null &&
    quotaRatio > 0
  ) {
    availableCpuSeconds =
      intervalSeconds * quotaRatio;
  } else {
    /*
     * No quota detected.
     * Use the number of CPUs visible to Node.
     */
    const cpuCount =
      (os.cpus() || []).length || 1;

    availableCpuSeconds =
      intervalSeconds * cpuCount;
  }

  if (
    !Number.isFinite(availableCpuSeconds) ||
    availableCpuSeconds <= 0
  ) {
    return null;
  }

  const percent =
    (deltaCpuSeconds / availableCpuSeconds) * 100;

  return Math.round(
    Math.max(0, Math.min(100, percent))
  );
}

/*
 * ------------------------------------------------------------
 * MEMORY
 * ------------------------------------------------------------
 */

async function getMemoryPercent() {
  /*
   * cgroup v2.
   */
  const current = await readFileSafe(
    "/sys/fs/cgroup/memory.current"
  );

  const max = await readFileSafe(
    "/sys/fs/cgroup/memory.max"
  );

  if (current !== null) {
    const usage = Number(current);

    let limit;

    if (
      max === null ||
      max === "" ||
      max === "max"
    ) {
      limit = os.totalmem();
    } else {
      limit = Number(max);
    }

    if (
      Number.isFinite(usage) &&
      Number.isFinite(limit) &&
      limit > 0
    ) {
      return Math.round(
        Math.max(
          0,
          Math.min(100, (usage / limit) * 100)
        )
      );
    }
  }

  /*
   * cgroup v1.
   */
  const v1Usage =
    await readFileSafe(
      "/sys/fs/cgroup/memory/memory.usage_in_bytes"
    ) ||
    await readFileSafe(
      "/sys/fs/cgroup/memory.usage_in_bytes"
    );

  const v1Limit =
    await readFileSafe(
      "/sys/fs/cgroup/memory/memory.limit_in_bytes"
    );

  if (v1Usage !== null) {
    const usage = Number(v1Usage);

    let limit;

    if (
      v1Limit === null ||
      v1Limit === "" ||
      v1Limit === "max"
    ) {
      limit = os.totalmem();
    } else {
      limit = Number(v1Limit);
    }

    if (
      Number.isFinite(usage) &&
      Number.isFinite(limit) &&
      limit > 0
    ) {
      return Math.round(
        Math.max(
          0,
          Math.min(100, (usage / limit) * 100)
        )
      );
    }
  }

  /*
   * Final OS-level fallback.
   */
  try {
    const total = os.totalmem();
    const free = os.freemem();

    if (total <= 0) {
      return null;
    }

    return Math.round(
      Math.max(
        0,
        Math.min(
          100,
          ((total - free) / total) * 100
        )
      )
    );
  } catch {
    return null;
  }
}

/*
 * ------------------------------------------------------------
 * STORAGE
 * ------------------------------------------------------------
 */

async function getStoragePercent() {
  try {
    const { stdout } =
      await exec("df -k /");

    const lines =
      stdout.trim().split("\n");

    if (lines.length < 2) {
      return null;
    }

    /*
     * Filesystem
     * 1K-blocks
     * Used
     * Available
     * Use%
     * Mounted on
     */

    const parts =
      lines[1]
        .replace(/\s+/g, " ")
        .split(" ");

    const totalKb =
      Number(parts[1]);

    const usedKb =
      Number(parts[2]);

    if (
      !Number.isFinite(totalKb) ||
      !Number.isFinite(usedKb) ||
      totalKb <= 0
    ) {
      return null;
    }

    return Math.round(
      Math.max(
        0,
        Math.min(
          100,
          (usedKb / totalKb) * 100
        )
      )
    );
  } catch {
    return null;
  }
}

/*
 * ------------------------------------------------------------
 * GPU
 * ------------------------------------------------------------
 *
 * Only reports a GPU if nvidia-smi is actually available.
 * Otherwise returns null instead of inventing a value.
 */

async function getGpuPercent() {
  try {
    const { stdout } =
      await exec(
        "nvidia-smi",
        {
          timeout: 1500,
          maxBuffer: 1024 * 1024
        }
      );

    /*
     * Query GPU utilization directly.
     */
    const query =
      stdout.trim();

    if (!query) {
      return null;
    }

    const values =
      query
        .split(/\s+/)
        .map(Number)
        .filter(Number.isFinite);

    if (!values.length) {
      return null;
    }

    return Math.round(
      Math.max(
        0,
        Math.min(
          100,
          values.reduce(
            (sum, value) =>
              sum + value,
            0
          ) / values.length
        )
      )
    );
  } catch {
    return null;
  }
}

/*
 * ------------------------------------------------------------
 * TEMPERATURE
 * ------------------------------------------------------------
 */

async function getTemperatureC() {
  const thermalRoot =
    "/sys/class/thermal";

  try {
    const entries =
      await fs.readdir(thermalRoot);

    for (const entry of entries) {
      if (
        !entry.startsWith("thermal_zone")
      ) {
        continue;
      }

      const tempFile =
        path.join(
          thermalRoot,
          entry,
          "temp"
        );

      const value =
        await readFileSafe(tempFile);

      if (value === null) {
        continue;
      }

      const temp =
        Number(value);

      /*
       * Linux thermal sensors commonly
       * report millidegrees Celsius.
       */
      if (
        Number.isFinite(temp) &&
        temp > -100000 &&
        temp < 200000
      ) {
        return Math.round(temp / 1000);
      }
    }
  } catch {
    return null;
  }

  return null;
}

/*
 * ------------------------------------------------------------
 * API ROUTES
 * ------------------------------------------------------------
 */

app.get(
  "/api/status",
  async (_req, res) => {
    res.json(
      await upstream(
        process.env.STATUS_URL,
        demo.status
      )
    );
  }
);

app.get(
  "/api/metrics",
  async (_req, res) => {
    /*
     * Preserve existing METRICS_URL behavior.
     *
     * If METRICS_URL is configured, it remains the
     * authoritative metrics source.
     */
    if (process.env.METRICS_URL) {
      return res.json(
        await upstream(
          process.env.METRICS_URL,
          demo.metrics
        )
      );
    }

    /*
     * Otherwise collect metrics directly
     * from this running container.
     */
    try {
      const [
        cpu,
        memory,
        storage,
        gpu,
        temperatureC
      ] = await Promise.all([
        getCpuPercent(),
        getMemoryPercent(),
        getStoragePercent(),
        getGpuPercent(),
        getTemperatureC()
      ]);

      return res.json({
        cpu,
        gpu,
        memory,
        storage,
        temperatureC,

        source: "container",

        timestamp:
          new Date().toISOString()
      });
    } catch (error) {
      return res.json({
        cpu: null,
        gpu: null,
        memory: null,
        storage: null,
        temperatureC: null,

        source: "container",

        metricsError:
          error.message,

        timestamp:
          new Date().toISOString()
      });
    }
  }
);

app.get(
  "/api/workloads",
  async (_req, res) => {
    res.json(
      await upstream(
        process.env.WORKLOADS_URL,
        demo.workloads
      )
    );
  }
);

app.get(
  "/api/deployment",
  async (_req, res) => {
    res.json(
      await upstream(
        process.env.DEPLOYMENT_URL,
        demo.deployment
      )
    );
  }
);

app.get(
  "/api/health",
  (_req, res) => {
    res.json({
      ok: true,
      service: "live-command-center",
      uptimeSeconds:
        Math.round(process.uptime()),
      time:
        new Date().toISOString()
    });
  }
);

/*
 * Railway supplies PORT.
 * Bind to 0.0.0.0 so external traffic can reach
 * the application inside the container.
 */
app.listen(
  PORT,
  "0.0.0.0",
  () => {
    console.log(
      `Command Center live at http://0.0.0.0:${PORT}`
    );
  }
);
