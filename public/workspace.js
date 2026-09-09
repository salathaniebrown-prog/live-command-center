'use strict';
(() => {
  const repo = 'https://github.com/salathaniebrown-prog/live-command-center/blob/79be758/';
  const modules = [
    ['Command Deployment Center', '/deployment-center.html', 'Runtime monitoring', 'Serving revision, public feeds, signed device heartbeats and deployment checks.'],
    ['Earth & satellites', '#live', 'Public observations', 'CelesTrak orbital positions and world events.'],
    ['Chronicle Lab & Scribe', '#lab', 'Source synthesis', 'USGS, NOAA/NWS and NASA EONET event records.'],
    ['Executive council', '#intel', 'Decision support', 'CEO, President, CFO and CTO alongside the mission brief.'],
    ['Eagle Eyes MAX', '#max', 'Access required', 'World knowledge, weather, AI and free command tools.'],
    ['NexusBrown compute', '#compute', 'Runtime telemetry', 'CPU, memory, storage and available NVIDIA GPU readings.'],
    ['BCI observations', '#bci', 'Device setup required', 'Registered observation lane; no connected-device claim.'],
    ['EVM chains', '#chains', 'Registry lookup', 'Find networks by name or chain ID.'],
    ['Base USDC', '#crypto', 'Sandbox', 'Receive requests and unsigned wallet preparation.'],
    ['Future Command Lab', '#future', 'Planning', 'Project builder, GitHub and deployment action register.'],
    ['NASA imagery', '/nasa-imagery-test.html', 'Separate preview', 'Inspect the recovered Earth imagery resolver.'],
    ['Airspace', '/airspace.html', 'Observation view', 'Open the recovered airspace interface.'],
    ['Business & requests', '/business.html', 'Business workspace', 'Project information and deployment requests.'],
    ['MCP / UDP hub', repo+'README.md#mcp--udp-supercomputer-hub', 'Local setup', 'Separate local broker; live and simulated packet counts stay distinct.'],
    ['Cloud coding agents', repo+'README.md#cloud-coding-agents', 'Setup reference', 'Existing Claude and Vercel coding-agent guidance.'],
    ['Android client', repo+'clients/mobile/README.md', 'Device validation required', 'Recovered native client and installation guidance.'],
    ['VR / XR', repo+'vr/README.md', 'Runtime validation required', 'Recovered baseline; headset rendering remains unverified.'],
    ['ASSM & Reality Engine', repo+'RECOVERY-STATUS.md', 'Isolated modules', 'Worker pool and real-frame contracts awaiting runtime integration.'],
    ['Power Blueprint', repo+'deploy/power-blueprint-deploy/README.md', 'Host setup required', 'Physical storage, MQTT and database stack.'],
    ['Security & telemetry', '#links', 'Protected integrations', 'Deep Security, Shell Catcher and signed telemetry retain existing access boundaries.']
  ];
  const byId = id => document.getElementById(id);
  function render() {
    const q = byId('moduleSearch').value.toLowerCase().trim();
    const shown = modules.filter(row => row.join(' ').toLowerCase().includes(q));
    byId('moduleDirectory').replaceChildren(...shown.map(([name, href, state, description]) => {
      const a = document.createElement('a'); a.href = href; a.className = 'moduleCard';
      if (href.startsWith('https:')) { a.target = '_blank'; a.rel = 'noopener noreferrer'; }
      const title = document.createElement('strong'); title.textContent = name;
      const badge = document.createElement('span'); badge.textContent = state;
      const detail = document.createElement('p'); detail.textContent = description;
      a.append(title, badge, detail); return a;
    }));
    byId('moduleEmpty').hidden = shown.length > 0;
  }
  async function read(url) {
    const response = await fetch(url, {signal: AbortSignal.timeout(15000), cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP '+response.status);
    const data = await response.json();
    if (data.ok === false) throw new Error('Source unavailable');
    return data;
  }
  async function refresh() {
    byId('refreshBci').disabled = true;
    try {
      const data = await read('/api/eagle-eyes/bci/status');
      byId('bciState').textContent = data.status || 'UNKNOWN';
      byId('bciDetail').textContent = (data.message || 'No observation received.') + ' Device profile: ' + (data.deviceProfile || 'unconfigured');
    } catch (error) {
      byId('bciState').textContent = 'UNAVAILABLE';
      byId('bciDetail').textContent = 'Could not refresh BCI status: '+error.message;
    } finally { byId('refreshBci').disabled = false; }
    try {
      const data = await read('/api/deployment');
      byId('workspaceRevision').textContent = data.commitSha || 'Not supplied by host';
    } catch { byId('workspaceRevision').textContent = 'UNAVAILABLE'; }
  }
  byId('chainSearch').addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button'); button.disabled = true;
    const output = byId('chainResults'); output.textContent = 'Searching registry…';
    try {
      const data = await read('/api/eagle-eyes/chains?limit=10&q='+encodeURIComponent(byId('chainQuery').value.trim()));
      output.replaceChildren();
      for (const chain of data.chains || []) {
        const row = document.createElement('p');
        row.textContent = `${chain.name} · ID ${chain.chainId} · ${chain.nativeCurrency?.symbol || 'N/A'} · ${chain.status || 'Unknown status'}`;
        if (chain.redFlags?.length) row.textContent += ' · Flags: '+chain.redFlags.join(', ');
        output.append(row);
      }
      if (!output.childNodes.length) output.textContent = 'No matching networks.';
    } catch (error) { output.textContent = 'Registry unavailable: '+error.message; }
    finally { button.disabled = false; }
  });
  byId('moduleSearch').addEventListener('input', render);
  byId('refreshBci').addEventListener('click', refresh);
  render(); refresh();
})();
