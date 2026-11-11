const os = require('os');
const fs = require('fs');
const zlib = require('zlib');
const { execSync } = require('child_process');

const LOG_FILE = 'telemetry_spine.jsonl';
const MAX_SIZE_BYTES = 5 * 1024 * 1024;
const MAX_ARCHIVES = 5;

function rotateAndCompressLogs() {
  try {
    if (!fs.existsSync(LOG_FILE)) return;
    const stats = fs.statSync(LOG_FILE);
    if (stats.size >= MAX_SIZE_BYTES) {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const tempFile = `telemetry_spine_${timestamp}.jsonl`;
      const gzFile = `${tempFile}.gz`;
      fs.renameSync(LOG_FILE, tempFile);

      const input = fs.createReadStream(tempFile);
      const output = fs.createWriteStream(gzFile);
      const gzip = zlib.createGzip();

      input.pipe(gzip).pipe(output).on('finish', () => {
        fs.unlinkSync(tempFile);
        const archives = fs.readdirSync('.')
          .filter(f => f.startsWith('telemetry_spine_') && f.endsWith('.jsonl.gz'))
          .sort();
        while (archives.length > MAX_ARCHIVES) {
          fs.unlinkSync(archives.shift());
        }
      });
    }
  } catch (err) {
    fs.appendFileSync('telemetry_errors.log', `[${new Date().toISOString()}] ${err.message}\n`);
  }
}

function getBatteryStats() {
  try {
    const raw = execSync('termux-battery-status', { timeout: 1500 }).toString();
    const b = JSON.parse(raw);
    return {
      percentage: b.percentage,
      status: b.status,
      tempC: b.temperature,
      voltageMV: b.voltage
    };
  } catch {
    return { percentage: 'N/A', status: 'UNAVAILABLE', tempC: 'N/A', voltageMV: 'N/A' };
  }
}

function getNetworkStats() {
  const nets = os.networkInterfaces();
  const active = {};
  for (const [name, addrs] of Object.entries(nets)) {
    const ipv4 = addrs.find(a => a.family === 'IPv4' && !a.internal);
    if (ipv4) active[name] = ipv4.address;
  }
  return active;
}

function collectTelemetry() {
  rotateAndCompressLogs();
  const totalMem = os.totalmem();
  const freeMem = os.freemem();

  const snapshot = {
    source: 'node-spine',
    timestamp: new Date().toISOString(),
    uptimeSec: os.uptime(),
    loadAvg: os.loadavg(),
    memory: {
      totalMB: Math.round(totalMem / 1024 / 1024),
      usedMB: Math.round((totalMem - freeMem) / 1024 / 1024),
      freeMB: Math.round(freeMem / 1024 / 1024)
    },
    battery: getBatteryStats(),
    network: getNetworkStats()
  };
  fs.appendFileSync(LOG_FILE, JSON.stringify(snapshot) + '\n');
}

setInterval(collectTelemetry, 2000);
