const fs = require('fs');

function renderDashboard() {
  try {
    if (!fs.existsSync('telemetry_spine.jsonl')) return;
    const lines = fs.readFileSync('telemetry_spine.jsonl', 'utf8').trim().split('\n');
    const recent = lines.slice(-30).map(l => {
      try { return JSON.parse(l); } catch { return null; }
    }).filter(Boolean);

    const nodeData = [...recent].reverse().find(x => x.source === 'node-spine') || {};
    const pyData = [...recent].reverse().find(x => x.source === 'python-worker') || {};
    const javaData = [...recent].reverse().find(x => x.source === 'java-worker') || {};
    const fileSizeKB = (fs.statSync('telemetry_spine.jsonl').size / 1024).toFixed(1);

    console.clear();
    console.log('======================================================');
    console.log('       ASTRA ENTERPRISE CORE :: TELEMETRY SPINE       ');
    console.log('======================================================');
    console.log(` TIME (UTC) : ${new Date().toISOString()}`);
    console.log(` LOG SIZE   : ${fileSizeKB} KB / 5120.0 KB (Auto-Gzip)`);
    console.log('------------------------------------------------------');
    if (nodeData.memory) {
      console.log(` [NODE] RAM : ${nodeData.memory.usedMB} MB / ${nodeData.memory.totalMB} MB`);
      console.log(` [NODE] LOAD: ${nodeData.loadAvg.map(n => n.toFixed(2)).join(' | ')}`);
      console.log(` [BATT] PWR : ${nodeData.battery.percentage}% (${nodeData.battery.status}) | ${nodeData.battery.tempC}°C | ${nodeData.battery.voltageMV}mV`);
      console.log(` [NET]  IPs : ${JSON.stringify(nodeData.network)}`);
    }
    console.log('------------------------------------------------------');
    console.log(` [PY]   STAT: ${pyData.status || 'WAITING'} | Tasks: ${pyData.data?.tasks_completed ?? 0}`);
    console.log(` [JAVA] STAT: ${javaData.status || 'WAITING'} | Cycle: ${javaData.cycle ?? 0}`);
    console.log('======================================================');
    console.log(' Press Ctrl+C to exit dashboard (workers stay active) ');
  } catch (err) {
    console.error('Dashboard read error:', err.message);
  }
}

setInterval(renderDashboard, 1000);
