"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DeepSecurityClient,
  computerFilter
} = require("../deep-security");

function jsonResponse(
  data,
  status = 200
) {
  return {
    ok:
      status >= 200 &&
      status < 300,
    status,
    async text() {
      return JSON.stringify(data);
    }
  };
}

test(
  "computerFilter builds supported scoped targets",
  () => {
    assert.deepEqual(
      computerFilter({
        type: "computer",
        computerID: 7
      }),
      {
        type: "computer",
        computerID: 7
      }
    );

    assert.deepEqual(
      computerFilter({
        type: "computers-using-policy",
        policyID: 12
      }),
      {
        type: "computers-using-policy",
        policyID: 12
      }
    );
  }
);

test(
  "write actions stay locked until explicitly enabled",
  async () => {
    const client =
      new DeepSecurityClient({
        baseUrl:
          "https://deep.example.test",
        apiKey: "secret",
        apiVersion: "v1",
        actionsEnabled: false,
        fetchImpl:
          async () =>
            jsonResponse({})
      });

    await assert.rejects(
      () =>
        client.runScan({
          scanType:
            "recommendations"
        }),
      /actions are locked/i
    );
  }
);

test(
  "Deep Security API base path is preserved and auto-added",
  async () => {
    const urls = [];

    const capture =
      async (url) => {
        urls.push(String(url));
        return jsonResponse({});
      };

    const hostOnly =
      new DeepSecurityClient({
        baseUrl:
          "https://deep.example.test",
        apiKey: "secret",
        apiVersion: "v1",
        fetchImpl: capture
      });

    const explicitApi =
      new DeepSecurityClient({
        baseUrl:
          "https://deep.example.test/api",
        apiKey: "secret",
        apiVersion: "v1",
        fetchImpl: capture
      });

    await hostOnly.listComputers();
    await explicitApi.listComputers();

    assert.deepEqual(
      urls,
      [
        "https://deep.example.test/api/computers?expand=none",
        "https://deep.example.test/api/computers?expand=none"
      ]
    );
  }
);

test(
  "runScan sends an immediate allowlisted recommendation scan",
  async () => {
    let captured;

    const client =
      new DeepSecurityClient({
        baseUrl:
          "https://deep.example.test",
        apiKey: "secret",
        apiVersion: "v1",
        actionsEnabled: true,
        fetchImpl:
          async (url, options) => {
            captured = {
              url:
                String(url),
              options
            };

            return jsonResponse({
              ID: 44
            });
          }
      });

    const result =
      await client.runScan({
        scanType:
          "recommendations",
        target: {
          type: "computer",
          computerID: 9
        },
        name:
          "Eagle Eyes protect node 9"
      });

    assert.equal(
      result.data.ID,
      44
    );

    assert.equal(
      captured.url,
      "https://deep.example.test/api/scheduledtasks"
    );

    assert.equal(
      captured.options.method,
      "POST"
    );

    assert.equal(
      captured.options.headers[
        "api-secret-key"
      ],
      "secret"
    );

    assert.equal(
      captured.options.headers[
        "api-version"
      ],
      "v1"
    );

    const body =
      JSON.parse(
        captured.options.body
      );

    assert.equal(
      body.type,
      "scan-for-recommendations"
    );

    assert.equal(
      body.runNow,
      true
    );

    assert.deepEqual(
      body.scanForRecommendationsTaskParameters.computerFilter,
      {
        type: "computer",
        computerID: 9
      }
    );
  }
);

test(
  "firewall action adds unique rule IDs to a computer",
  async () => {
    let captured;

    const client =
      new DeepSecurityClient({
        baseUrl:
          "https://deep.example.test",
        apiKey: "secret",
        apiVersion: "v1",
        actionsEnabled: true,
        fetchImpl:
          async (url, options) => {
            captured = {
              url:
                String(url),
              options
            };

            return jsonResponse({
              assignedRuleIDs:
                [10, 20]
            });
          }
      });

    await client
      .addFirewallRulesToComputer(
        3,
        [10, 20, 10]
      );

    assert.equal(
      captured.url,
      "https://deep.example.test/api/computers/3/firewall/assignments"
    );

    assert.deepEqual(
      JSON.parse(
        captured.options.body
      ),
      {
        ruleIDs:
          [10, 20]
      }
    );
  }
);

test(
  "policy setting action uses the exact allowlisted endpoint",
  async () => {
    let captured;

    const client =
      new DeepSecurityClient({
        baseUrl:
          "https://deep.example.test",
        apiKey: "secret",
        apiVersion: "v1",
        actionsEnabled: true,
        fetchImpl:
          async (url, options) => {
            captured = {
              url:
                String(url),
              options
            };

            return jsonResponse({
              value: "true"
            });
          }
      });

    await client
      .setPolicySetting(
        5,
        "platformSettingRecommendationOngoingScansEnabled",
        "true"
      );

    assert.equal(
      captured.url,
      "https://deep.example.test/api/policies/5/settings/platformSettingRecommendationOngoingScansEnabled"
    );

    assert.deepEqual(
      JSON.parse(
        captured.options.body
      ),
      {
        value: "true"
      }
    );
  }
);

test(
  "AWS connector synchronization requests immediate sync without replacing connector fields",
  async () => {
    let captured;

    const client =
      new DeepSecurityClient({
        baseUrl:
          "https://deep.example.test",
        apiKey: "secret",
        apiVersion: "v1",
        actionsEnabled: true,
        fetchImpl:
          async (url, options) => {
            captured = {
              url:
                String(url),
              options
            };

            return jsonResponse({
              ID: 8
            });
          }
      });

    await client
      .syncAwsConnector(8);

    assert.equal(
      captured.url,
      "https://deep.example.test/api/awsconnectors/8?sync=true"
    );

    assert.deepEqual(
      JSON.parse(
        captured.options.body
      ),
      {}
    );
  }
);
