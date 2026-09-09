'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let latest = null;
  let lastMessage = 0;
  let lastCollection = '';
  let token = sessionStorage.getItem('eagleEyesToken') || '';
  let source;
  let busy = false;
  $('access-token').value = token;
  const slots = Array.from({ length: 32 }, (_, i) => {
    const slot = document.createElement('div'); slot.className = 'node';
    const label = document.createElement('strong'); label.textContent = `N-${String(i + 1).padStart(2, '0')}`;
    const status = document.createElement('small'); status.textContent = 'Waiting';
    slot.append(label, status); $('nodes').append(slot); return slot;
  });
  function log(message) {
    const row = document.createElement('p'); row.textContent = `${new Date().toLocaleTimeString()} · ${message}`;
    $('activity').prepend(row);
    while ($('activity').childElementCount > 80) $('activity').lastElementChild.remove();
  }
  function authHeaders() { return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }; }
  function nodes(values) {
    for (const node of values) {
      const slot = slots[node.nodeId - 1]; if (!slot) continue;
      const status = ['PASS', 'FAIL', 'STALE'].includes(node.status) ? node.status : 'WAITING';
      slot.className = `node ${status.toLowerCase()}`;
      slot.lastChild.textContent = status === 'WAITING' ? 'Waiting' : status;
      slot.title = node.receivedAt ? `Last signed report: ${new Date(node.receivedAt).toLocaleString()}` : 'No signed telemetry received';
    }
    $('active-nodes').textContent = `${values.filter(x => x.status === 'PASS').length} / 32`;
  }
  function controls() {
    $('deploy').disabled = busy || !token || !latest?.capabilities.deployConfigured || latest?.deployment.branch !== 'main' || !latest?.deployment.commitSha;
  }
  function render(data) {
    latest = data; lastMessage = Date.now();
    $('connection').className = 'badge online'; $('connection').textContent = 'Receiving telemetry';
    $('checked').textContent = `Collected ${new Date(data.checkedAt).toLocaleTimeString()} · refreshed every 30s`;
    $('system-state').textContent = data.systemState;
    $('runtime-note').textContent = `${data.feeds.filter(feed => feed.status === 'ONLINE').length} of 3 public feeds available`;
    nodes(data.nodes);
    $('enrolled').textContent = `${data.enrolledNodes} enrolled · ${32 - data.enrolledNodes} unassigned`;
    $('device-status').textContent = data.capabilities.mobileConfigured ? 'Signed reports enabled' : 'Device enrollment required';
    for (const [id, name] of [['usdc', 'USDC-USD'], ['btc', 'BTC-USD']]) {
      const item = data.markets.find(value => value.name === name);
      $(id).textContent = item?.status === 'ONLINE' ? Number(item.value).toLocaleString(undefined, { style: 'currency', currency: 'USD', minimumFractionDigits: id === 'usdc' ? 4 : 2 }) : 'Unavailable';
      $(id + '-note').textContent = item?.status === 'ONLINE' ? `Coinbase spot · ${item.latencyMs} ms fetch` : 'Coinbase feed unavailable';
    }
    $('environment').textContent = data.deployment.environment || 'Local runtime';
    $('commit').textContent = data.deployment.commitSha || 'Not supplied by host';
    $('deployment-id').textContent = data.deployment.deploymentId || 'Not supplied by host';
    $('service').textContent = data.deployment.serviceId || 'Local Command Center';
    $('feeds').replaceChildren(...data.feeds.map(feed => {
      const row = document.createElement('div'); row.className = 'feed';
      const name = document.createElement('strong'); name.textContent = ({ usgs: 'USGS earthquakes', nws: 'NOAA / NWS alerts', eonet: 'NASA EONET' })[feed.name] || feed.name;
      const state = document.createElement('span'); state.textContent = feed.status; state.className = feed.status === 'ONLINE' ? 'pass' : 'stale';
      const detail = document.createElement('p'); detail.textContent = feed.status === 'ONLINE' ? `${feed.value.count} events in response · ${feed.latencyMs} ms fetch` : 'No current data returned. Next refresh will retry.';
      row.append(name, state, detail); return row;
    }));
    $('host').replaceChildren(...[['CPU', 'cpu'], ['Memory', 'memory'], ['Storage', 'storage'], ['GPU', 'gpu']].map(([label, key]) => {
      const item = document.createElement('div'); const name = document.createElement('span'); name.textContent = label;
      const value = document.createElement('strong'); value.textContent = Number.isFinite(data.host.value?.[key]) ? `${data.host.value[key]}%` : 'Unavailable';
      item.append(name, value); return item;
    }));
    $('deploy-note').textContent = data.capabilities.deployConfigured ? 'Deploy requests run the fixed GitHub workflow. Follow its result before claiming success.' : 'Use the GitHub workflow link. An administrator can enable the protected button with a scoped deployment credential.';
    if (lastCollection !== data.checkedAt) { log(`${data.systemState} · ${data.feeds.filter(x => x.status === 'ONLINE').length}/3 feeds · revision ${(data.deployment.commitSha || 'unreported').slice(0, 8)}`); lastCollection = data.checkedAt; }
    controls();
  }
  function disconnected(message) {
    $('connection').className = 'badge offline'; $('connection').textContent = message;
    $('system-state').textContent = 'Connection unavailable';
    if (latest) nodes(latest.nodes.map(node => ({ ...node, status: node.receivedAt ? 'STALE' : 'WAITING' })));
    $('deploy').disabled = true;
  }
  async function check() {
    $('verify').disabled = true;
    try {
      const response = await fetch('/api/deployment-center/status', { cache: 'no-store', signal: AbortSignal.timeout(20000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json()); log('Deployment response received and runtime revision refreshed.');
    } catch (error) { disconnected('Check failed'); log(`Deployment check failed: ${error.message}`); }
    finally { $('verify').disabled = false; }
  }
  function connect() {
    source?.close();
    source = new EventSource('/api/deployment-center/stream');
    source.addEventListener('snapshot', event => { try { render(JSON.parse(event.data)); } catch { disconnected('Invalid response'); } });
    source.addEventListener('nodes', event => { try { const data = JSON.parse(event.data); if (latest) latest.nodes = data.nodes; nodes(data.nodes); lastMessage = Date.now(); } catch { disconnected('Invalid response'); } });
    source.addEventListener('unavailable', () => disconnected('Collection unavailable'));
    source.onerror = () => disconnected('Reconnecting');
  }
  $('verify').addEventListener('click', check);
  $('access-form').addEventListener('submit', event => { event.preventDefault(); token = $('access-token').value.trim(); if (token) sessionStorage.setItem('eagleEyesToken', token); else sessionStorage.removeItem('eagleEyesToken'); controls(); log(token ? 'Access token stored for this browser session.' : 'Session access cleared.'); });
  $('deploy').addEventListener('click', async () => {
    busy = true; controls(); log('Requesting GitHub deployment workflow…');
    try {
      const response = await fetch('/api/deployment-center/deploy', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ expectedCommit: latest.deployment.commitSha }), signal: AbortSignal.timeout(20000) });
      const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      log(data.message); $('deploy-note').textContent = 'Workflow requested. Open GitHub deployment workflow to follow the actual result.';
    } catch (error) { log(error.message); }
    finally { busy = false; controls(); }
  });
  $('download').addEventListener('click', async () => {
    if (!token) { log('Enter your Command Rail access token to download heartbeat logs.'); return; }
    try {
      const response = await fetch('/api/deployment-center/network.csv', { headers: authHeaders(), signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error((await response.json()).error || 'CSV unavailable');
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = 'network_stats.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { log(error.message); }
  });
  setInterval(() => { if (lastMessage && Date.now() - lastMessage > 15000) disconnected('Telemetry stale'); }, 5000);
  window.addEventListener('pagehide', () => source?.close());
  window.addEventListener('pageshow', event => { if (event.persisted) connect(); });
  connect();
})();
