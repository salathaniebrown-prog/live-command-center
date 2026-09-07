"use strict";

const CHAIN_SOURCE_URL = "https://chainid.network/chains.json";
const CACHE_MS = 15 * 60 * 1000;
const MAX_RESULTS = 20;

let cache = {
  chains: null,
  fetchedAtMs: 0,
  fetchedAt: null
};

function cleanString(value) {
  return typeof value === "string" && value.trim()
    ? value.trim()
    : null;
}

function cleanUrlList(values) {
  return Array.isArray(values)
    ? values.filter((value) => typeof value === "string" && value.trim())
    : [];
}

function normalizeChain(record) {
  if (!record || typeof record !== "object") {
    return null;
  }

  const chainId = Number(record.chainId);
  const name = cleanString(record.name);
  const shortName = cleanString(record.shortName);

  if (!Number.isSafeInteger(chainId) || chainId <= 0 || !name || !shortName) {
    return null;
  }

  const networkId = Number(record.networkId);
  const native = record.nativeCurrency || {};
  const parent = record.parent && typeof record.parent === "object"
    ? {
        type: cleanString(record.parent.type),
        chain: cleanString(record.parent.chain),
        bridges: Array.isArray(record.parent.bridges)
          ? record.parent.bridges
              .map((bridge) => ({ url: cleanString(bridge?.url) }))
              .filter((bridge) => bridge.url)
          : []
      }
    : null;

  return {
    name,
    chain: cleanString(record.chain),
    shortName,
    chainId,
    networkId: Number.isSafeInteger(networkId) ? networkId : null,
    caip2: `eip155:${chainId}`,
    repositoryFile: `eip155-${chainId}.json`,
    status: cleanString(record.status) || "active",
    nativeCurrency: {
      name: cleanString(native.name),
      symbol: cleanString(native.symbol),
      decimals: Number.isInteger(native.decimals) && native.decimals >= 0
        ? native.decimals
        : null
    },
    rpc: cleanUrlList(record.rpc),
    faucets: cleanUrlList(record.faucets),
    features: Array.isArray(record.features)
      ? record.features
          .map((feature) => cleanString(feature?.name))
          .filter(Boolean)
      : [],
    infoURL: cleanString(record.infoURL),
    icon: cleanString(record.icon),
    explorers: Array.isArray(record.explorers)
      ? record.explorers
          .map((explorer) => ({
            name: cleanString(explorer?.name),
            url: cleanString(explorer?.url),
            icon: cleanString(explorer?.icon),
            standard: cleanString(explorer?.standard)
          }))
          .filter((explorer) => explorer.name || explorer.url)
      : [],
    parent:
      parent && parent.type && parent.chain
        ? parent
        : null,
    redFlags: Array.isArray(record.redFlags)
      ? record.redFlags.filter((flag) => typeof flag === "string")
      : []
  };
}

function requestedChainId(query) {
  const q = String(query || "").trim();

  if (/^\d+$/.test(q)) {
    return Number(q);
  }

  const match = q.match(/\b(?:chain\s*id|chainid)\s*[:#-]?\s*(\d+)\b/i);
  return match ? Number(match[1]) : null;
}

function scoreChain(chain, query) {
  const q = String(query || "").trim().toLowerCase();

  if (!q) {
    return 1;
  }

  const id = requestedChainId(q);
  if (Number.isSafeInteger(id)) {
    return chain.chainId === id ? 1000 : -1;
  }

  const fields = [
    [chain.name, 100],
    [chain.shortName, 95],
    [chain.chain, 80],
    [chain.nativeCurrency?.symbol, 70],
    [chain.caip2, 90]
  ];

  let score = -1;

  for (const [value, weight] of fields) {
    const text = String(value || "").toLowerCase();
    if (!text) continue;
    if (text === q) score = Math.max(score, weight + 50);
    else if (text.startsWith(q)) score = Math.max(score, weight + 20);
    else if (text.includes(q)) score = Math.max(score, weight);
  }

  return score;
}

function filterEvmChains(records, query = "", limit = 10) {
  const n = Math.max(1, Math.min(MAX_RESULTS, Number(limit) || 10));

  return (records || [])
    .map(normalizeChain)
    .filter(Boolean)
    .map((chain) => ({ chain, score: scoreChain(chain, query) }))
    .filter((item) => item.score >= 0)
    .sort((a, b) => b.score - a.score || a.chain.chainId - b.chain.chainId)
    .slice(0, n)
    .map((item) => item.chain);
}

async function loadEvmChains({ fetchImpl = globalThis.fetch, force = false } = {}) {
  const now = Date.now();

  if (
    !force &&
    Array.isArray(cache.chains) &&
    now - cache.fetchedAtMs < CACHE_MS
  ) {
    return {
      chains: cache.chains,
      fetchedAt: cache.fetchedAt,
      cached: true
    };
  }

  if (typeof fetchImpl !== "function") {
    throw new Error("Fetch is unavailable in this runtime");
  }

  const response = await fetchImpl(CHAIN_SOURCE_URL, {
    headers: {
      accept: "application/json",
      "user-agent": "Eagle-Eyes-Live-Command-Center/1.0"
    },
    signal: AbortSignal.timeout(10000)
  });

  if (!response.ok) {
    throw new Error(`EVM chain registry returned HTTP ${response.status}`);
  }

  const raw = await response.json();
  if (!Array.isArray(raw)) {
    throw new Error("EVM chain registry returned an invalid payload");
  }

  const chains = raw.map(normalizeChain).filter(Boolean);
  const fetchedAt = new Date().toISOString();

  cache = {
    chains,
    fetchedAtMs: now,
    fetchedAt
  };

  return {
    chains,
    fetchedAt,
    cached: false
  };
}

async function queryEvmChains({ query = "", limit = 10, fetchImpl } = {}) {
  const loaded = await loadEvmChains({ fetchImpl });
  const matches = filterEvmChains(loaded.chains, query, limit);

  return {
    ok: true,
    source: CHAIN_SOURCE_URL,
    sourceType: "chainid.network aggregated EVM registry",
    observationOnly: true,
    simulated: false,
    query: String(query || ""),
    totalRegistryChains: loaded.chains.length,
    count: matches.length,
    chains: matches,
    fetchedAt: loaded.fetchedAt,
    cached: loaded.cached,
    timestamp: new Date().toISOString()
  };
}

function formatEvmChains(data) {
  const lines = (data.chains || []).map((chain, index) => {
    const currency = chain.nativeCurrency?.symbol || "N/A";
    const parent = chain.parent
      ? ` • ${chain.parent.type} of ${chain.parent.chain}`
      : "";
    const flags = chain.redFlags.length
      ? ` • RED FLAGS: ${chain.redFlags.join(", ")}`
      : "";

    return `${index + 1}. ${chain.name} • Chain ID ${chain.chainId} • ${currency} • ${chain.status}${parent}${flags}`;
  });

  return [
    "EVM CHAIN REGISTRY — READ ONLY",
    `Matches: ${data.count} • Registry chains: ${data.totalRegistryChains}`,
    ...(lines.length ? lines : ["No matching chain found."]),
    "RPC URLs and explorers are metadata only; Eagle Eyes does not sign or submit transactions.",
    `Source: ${data.source}`,
    `Checked: ${data.timestamp}`
  ].join("\n");
}

module.exports = {
  CHAIN_SOURCE_URL,
  normalizeChain,
  filterEvmChains,
  loadEvmChains,
  queryEvmChains,
  formatEvmChains
};
