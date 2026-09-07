"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  NETWORKS,
  parseUsdcAmount,
  getCryptoStatus,
  createPaymentRequest
} = require("../crypto-payments");

const RECEIVE_ADDRESS = "0x1111111111111111111111111111111111111111";

test("Base Sepolia uses Circle test USDC and stays sandboxed by default", () => {
  const status = getCryptoStatus({
    CRYPTO_RECEIVE_ADDRESS: RECEIVE_ADDRESS
  });

  assert.equal(status.mode, "sandbox");
  assert.equal(status.network.chainId, 84532);
  assert.equal(status.asset.contract, NETWORKS["base-sepolia"].usdcAddress);
  assert.equal(status.receiveAddress, RECEIVE_ADDRESS);
  assert.equal(status.capabilities.signTransactions, false);
  assert.equal(status.privateKeyRequired, false);
});

test("USDC amount parsing preserves six decimal minor units", () => {
  assert.deepEqual(parseUsdcAmount("12.345678"), {
    amountUsdc: "12.345678",
    minorUnits: "12345678"
  });

  assert.deepEqual(parseUsdcAmount("25.00"), {
    amountUsdc: "25",
    minorUnits: "25000000"
  });
});

test("payment request creates an ERC-681 transfer URI without creating a transaction", () => {
  const result = createPaymentRequest({
    amountUsdc: "4.25",
    memo: "Eagle Eyes test invoice",
    env: {
      CRYPTO_RECEIVE_ADDRESS: RECEIVE_ADDRESS,
      CRYPTO_NETWORK: "base-sepolia"
    }
  });

  assert.equal(result.mode, "sandbox");
  assert.equal(result.amountMinorUnits, "4250000");
  assert.match(result.paymentUri, /^ethereum:/);
  assert.match(result.paymentUri, /@84532\/transfer\?/);
  assert.equal(result.transactionCreated, false);
  assert.equal(result.transactionSigned, false);
  assert.equal(result.transactionSubmitted, false);
});

test("mainnet stays locked unless CRYPTO_LIVE is explicitly enabled", () => {
  assert.throws(
    () =>
      createPaymentRequest({
        amountUsdc: "1",
        env: {
          CRYPTO_RECEIVE_ADDRESS: RECEIVE_ADDRESS,
          CRYPTO_NETWORK: "base-mainnet"
        }
      }),
    /mainnet is locked/
  );
});

test("mainnet receive-only mode can be enabled without a private key", () => {
  const result = createPaymentRequest({
    amountUsdc: "1",
    env: {
      CRYPTO_RECEIVE_ADDRESS: RECEIVE_ADDRESS,
      CRYPTO_NETWORK: "base-mainnet",
      CRYPTO_LIVE: "true"
    }
  });

  assert.equal(result.mode, "mainnet-receive-only");
  assert.equal(result.network.chainId, 8453);
  assert.equal(result.asset.contract, NETWORKS["base-mainnet"].usdcAddress);
  assert.equal(result.transactionSigned, false);
});

test("invalid address and invalid amount fail closed", () => {
  assert.throws(
    () =>
      createPaymentRequest({
        amountUsdc: "1",
        env: { CRYPTO_RECEIVE_ADDRESS: "not-an-address" }
      }),
    /CRYPTO_RECEIVE_ADDRESS/
  );

  assert.throws(
    () =>
      createPaymentRequest({
        amountUsdc: "0.0000001",
        env: { CRYPTO_RECEIVE_ADDRESS: RECEIVE_ADDRESS }
      }),
    /at most 6 decimal places/
  );
});
