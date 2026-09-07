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
const ERC20_TRANSFER_SELECTOR = "a9059cbb";

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

function encodeTransferData(recipient, minorUnits) {
  const normalizedRecipient = normalizeAddress(recipient);
  if (!normalizedRecipient) {
    throw new Error("toAddress must be a valid 0x EVM address");
  }

  const amount = BigInt(String(minorUnits));
  if (amount <= 0n) {
    throw new Error("transfer amount must be greater than zero");
  }

  const addressWord = normalizedRecipient.slice(2).toLowerCase().padStart(64, "0");
  const amountWord = amount.toString(16).padStart(64, "0");
  return `0x${ERC20_TRANSFER_SELECTOR}${addressWord}${amountWord}`;
}

function getCryptoConfig(env = process.env) {
  const requestedNetwork = String(env.CRYPTO_NETWORK || DEFAULT_NETWORK)
    .trim()
    .toLowerCase();
  const network = NETWORKS[requestedNetwork] || NETWORKS[DEFAULT_NETWORK];
  const receiveAddress = normalizeAddress(env.CRYPTO_RECEIVE_ADDRESS);
  const sendAddress = normalizeAddress(env.CRYPTO_SEND_ADDRESS);
  const liveEnabled = parseBoolean(env.CRYPTO_LIVE);

  return {
    network,
    receiveAddress,
    sendAddress,
    liveEnabled,
    configured: Boolean(receiveAddress),
    mainnetLocked: network.mainnet && !liveEnabled,
    mode: network.mainnet && liveEnabled ? "mainnet-wallet-approved" : "sandbox"
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
    sendAddress: config.sendAddress,
    mainnetLocked: config.mainnetLocked,
    capabilities: {
      receivePaymentRequests: true,
      prepareSendTransactions: true,
      walletApprovalRequired: true,
      signTransactions: false,
      submitTransactions: false,
      serverCustody: false,
      swap: false,
      bridge: false,
      withdraw: false
    },
    privateKeyRequired: false,
    timestamp: new Date().toISOString()
  };
}

function assertNetworkUnlocked(config) {
  if (config.network.mainnet && !config.liveEnabled) {
    throw new Error("Base mainnet is locked until CRYPTO_LIVE=true is explicitly configured");
  }
}

function createPaymentRequest({ amountUsdc, memo = "", env = process.env } = {}) {
  const config = getCryptoConfig(env);

  if (!config.receiveAddress) {
    throw new Error("CRYPTO_RECEIVE_ADDRESS is not configured");
  }

  assertNetworkUnlocked(config);

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

function createTransferRequest({
  fromAddress,
  toAddress,
  amountUsdc,
  memo = "",
  env = process.env
} = {}) {
  const config = getCryptoConfig(env);
  assertNetworkUnlocked(config);

  const sender = normalizeAddress(fromAddress) || config.sendAddress;
  const recipient = normalizeAddress(toAddress);

  if (!sender) {
    throw new Error("fromAddress or CRYPTO_SEND_ADDRESS must be a valid 0x EVM address");
  }

  if (!recipient) {
    throw new Error("toAddress must be a valid 0x EVM address");
  }

  const parsed = parseUsdcAmount(amountUsdc);
  const safeMemo = String(memo || "").trim().slice(0, MAX_MEMO_LENGTH);
  const data = encodeTransferData(recipient, parsed.minorUnits);

  return {
    ok: true,
    mode: config.mode,
    network: {
      key: config.network.key,
      name: config.network.name,
      chainId: config.network.chainId,
      chainIdHex: `0x${config.network.chainId.toString(16)}`
    },
    asset: {
      symbol: "USDC",
      decimals: USDC_DECIMALS,
      contract: config.network.usdcAddress
    },
    sender,
    recipient,
    amountUsdc: parsed.amountUsdc,
    amountMinorUnits: parsed.minorUnits,
    memo: safeMemo || null,
    unsignedTransaction: {
      from: sender,
      to: config.network.usdcAddress,
      value: "0x0",
      data,
      chainId: `0x${config.network.chainId.toString(16)}`
    },
    transactionPrepared: true,
    walletApprovalRequired: true,
    transactionSigned: false,
    transactionSubmitted: false,
    privateKeyRequiredByServer: false,
    timestamp: new Date().toISOString()
  };
}

module.exports = {
  NETWORKS,
  DEFAULT_NETWORK,
  USDC_DECIMALS,
  normalizeAddress,
  parseUsdcAmount,
  encodeTransferData,
  getCryptoConfig,
  getCryptoStatus,
  createPaymentRequest,
  createTransferRequest
};
