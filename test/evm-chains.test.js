"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  normalizeChain,
  filterEvmChains,
  queryEvmChains
} = require("../evm-chains");

const sample = [
  {
    name: "Ethereum Mainnet",
    chain: "ETH",
    rpc: ["https://mainnet.infura.io/v3/${INFURA_API_KEY}"],
    nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
    features: [{ name: "EIP155" }, { name: "EIP1559" }],
    infoURL: "https://ethereum.org",
    shortName: "eth",
    chainId: 1,
    networkId: 1,
    icon: "ethereum",
    explorers: [
      {
        name: "etherscan",
        url: "https://etherscan.io",
        icon: "etherscan",
        standard: "EIP3091"
      }
    ]
  },
  {
    name: "Example Rollup",
    chain: "EXR",
    rpc: ["https://rpc.example"],
    nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
    shortName: "exr",
    chainId: 900001,
    networkId: 900001,
    status: "incubating",
    parent: {
      type: "L2",
      chain: "eip155-1",
      bridges: [{ url: "https://bridge.example" }]
    },
    redFlags: ["reusedChainID"]
  }
];

test("normalizes canonical chain metadata without adding execution capability", () => {
  const chain = normalizeChain(sample[0]);

  assert.equal(chain.chainId, 1);
  assert.equal(chain.caip2, "eip155:1");
  assert.equal(chain.repositoryFile, "eip155-1.json");
  assert.equal(chain.status, "active");
  assert.deepEqual(chain.features, ["EIP155", "EIP1559"]);
  assert.equal(chain.rpc[0], "https://mainnet.infura.io/v3/${INFURA_API_KEY}");
});

test("preserves L2 parent relationships and reused-chain warnings", () => {
  const chain = normalizeChain(sample[1]);

  assert.equal(chain.parent.type, "L2");
  assert.equal(chain.parent.chain, "eip155-1");
  assert.equal(chain.parent.bridges[0].url, "https://bridge.example");
  assert.deepEqual(chain.redFlags, ["reusedChainID"]);
});

test("finds a chain by explicit chain ID and by name", () => {
  assert.equal(filterEvmChains(sample, "chain id 1", 10)[0].name, "Ethereum Mainnet");
  assert.equal(filterEvmChains(sample, "Example Rollup", 10)[0].chainId, 900001);
});

test("query results are explicitly observation-only", async () => {
  const fakeFetch = async () => ({
    ok: true,
    json: async () => sample
  });

  const result = await queryEvmChains({
    query: "ethereum",
    limit: 5,
    fetchImpl: fakeFetch
  });

  assert.equal(result.ok, true);
  assert.equal(result.observationOnly, true);
  assert.equal(result.simulated, false);
  assert.equal(result.chains[0].chainId, 1);
});
