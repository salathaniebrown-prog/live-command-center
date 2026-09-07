"use strict";

const NETWORKS = Object.freeze({
  "base-sepolia": Object.freeze({
    key: "base-sepolia",
    name: "Base Sepolia",
    chainId: 84532,
    usdcAddress: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    mainnet: false
  }),
  "base-mainnet": Object.freeze({
    key: "base-mainnet",
    name: "Base Mainnet",
    chainId: 8453,
    usdcAddress: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    mainnet: true
  })
});

const DEFAULT_NETWORK = "base-sepolia";
const USDC_DECIMALS = 6;
const MAX_MEMO_LENGTH = 140;

function normalizeAddress(value) {
  const address = String(value || "").trim();
  return /^0x[a-fA-F0-9]{40}$/.test(address) ? address : null;
}

function parseBoolean(value) {
  return /^(1|true|yes|on)$/i.test(String(value || "").trim());
}

function parseUsdcAmount(value) {
  const text = String(value ?? "").trim();
  const match = text.match(/^(\d+)(?:\.(\d{1,6}))?$/);

  if (!match) {
    throw new Error("amountUsdc must be a positive decimal with at most 6 decimal places");
  }

  const whole = BigInt(match[1]);
  const fractionalText = (match[2] || "").padEnd(USDC_DECIMALS, "0");
  const fractional = BigInt(fractionalText || "0");
  const minorUnits = whole * 10n ** BigInt(USDC_DECIMALS) + fractional;

  if (minorUnits <= 0n) {
    throw new Error("amountUsdc must be greater than zero");
  }

  const trimmedFraction = (match[2] || "").replace(/0+$/, "");
  const normalizedAmount = trimmedFraction
    ? `${whole.toString()}.${trimmedFraction}`
    : whole.toString();

  return {
    amountUsdc: normalizedAmount,
    minorUnits: minorUnits.toString()
  };
}

function getCryptoConfig(env = process.env) {
  const requestedNetwork = String(env.CRYPTO_NETWORK || DEFAULT_NETWORK)
    .trim()
    .toLowerCase();
  const network = NETWORKS[requestedNetwork] || NETWORKS[DEFAULT_NETWORK];
  const receiveAddress = normalizeAddress(env.CRYPTO_RECEIVE_ADDRESS);
  const liveEnabled = parseBoolean(env.CRYPTO_LIVE);

  return {
    network,
    receiveAddress,
    liveEnabled,
    configured: Boolean(receiveAddress),
    mainnetLocked: network.mainnet && !liveEnabled,
    mode: network.mainnet && liveEnabled ? "mainnet-receive-only" : "sandbox"
  };
}

function getCryptoStatus(env = process.env) {
  const config = getCryptoConfig(env);

  return {
    ok: true,
    configured: config.configured,
    mode: config.mode,
    network: {
      key: config.network.key,
      name: config.network.name,
      chainId: config.network.chainId,
      mainnet: config.network.mainnet
    },
    asset: {
      symbol: "USDC",
      decimals: USDC_DECIMALS,
      contract: config.network.usdcAddress
    },
    receiveAddress: config.receiveAddress,
    mainnetLocked: config.mainnetLocked,
    capabilities: {
      receivePaymentRequests: true,
      signTransactions: false,
      sendFunds: false,
      swap: false,
      bridge: false,
      withdraw: false
    },
    privateKeyRequired: false,
    timestamp: new Date().toISOString()
  };
}

function createPaymentRequest({ amountUsdc, memo = "", env = process.env } = {}) {
  const config = getCryptoConfig(env);

  if (!config.receiveAddress) {
    throw new Error("CRYPTO_RECEIVE_ADDRESS is not configured");
  }

  if (config.network.mainnet && !config.liveEnabled) {
    throw new Error("Base mainnet is locked until CRYPTO_LIVE=true is explicitly configured");
  }

  const parsed = parseUsdcAmount(amountUsdc);
  const safeMemo = String(memo || "").trim().slice(0, MAX_MEMO_LENGTH);
  const paymentUri =
    `ethereum:${config.network.usdcAddress}@${config.network.chainId}` +
    `/transfer?address=${config.receiveAddress}&uint256=${parsed.minorUnits}`;

  return {
    ok: true,
    mode: config.mode,
    network: {
      key: config.network.key,
      name: config.network.name,
      chainId: config.network.chainId
    },
    asset: {
      symbol: "USDC",
      decimals: USDC_DECIMALS,
      contract: config.network.usdcAddress
    },
    recipient: config.receiveAddress,
    amountUsdc: parsed.amountUsdc,
    amountMinorUnits: parsed.minorUnits,
    memo: safeMemo || null,
    paymentUri,
    transactionCreated: false,
    transactionSigned: false,
    transactionSubmitted: false,
    timestamp: new Date().toISOString()
  };
}

module.exports = {
  NETWORKS,
  DEFAULT_NETWORK,
  USDC_DECIMALS,
  normalizeAddress,
  parseUsdcAmount,
  getCryptoConfig,
  getCryptoStatus,
  createPaymentRequest
};
