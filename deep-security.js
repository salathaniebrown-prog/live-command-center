"use strict";

const ALLOWED_SCAN_TYPES = new Set([
  "recommendations",
  "malware",
  "integrity",
  "open-ports"
]);

const SCAN_DEFINITIONS = {
  recommendations: {
    type: "scan-for-recommendations",
    parameter: "scanForRecommendationsTaskParameters"
  },
  malware: {
    type: "scan-for-malware",
    parameter: "scanForMalwareTaskParameters"
  },
  integrity: {
    type: "scan-for-integrity-changes",
    parameter: "scanForIntegrityChangesTaskParameters"
  },
  "open-ports": {
    type: "scan-for-open-ports",
    parameter: "scanForOpenPortsTaskParameters"
  }
};

function asPositiveInt(value, name) {
  const number = Number(value);

  if (!Number.isInteger(number) || number <= 0) {
    throw new Error(`${name} must be a positive integer`);
  }

  return number;
}

function uniqueRuleIds(ruleIDs) {
  if (!Array.isArray(ruleIDs) || !ruleIDs.length) {
    throw new Error("ruleIDs must be a non-empty array");
  }

  return [
    ...new Set(
      ruleIDs.map((id) =>
        asPositiveInt(id, "ruleID")
      )
    )
  ];
}

function normalizeBaseUrl(value) {
  const raw = String(value || "").trim();

  if (!raw) return "";

  const parsed = new URL(raw);

  if (parsed.protocol !== "https:") {
    throw new Error(
      "DEEP_SECURITY_URL must use https"
    );
  }

  const cleanPath =
    parsed.pathname.replace(/\/+$/, "");

  if (!cleanPath || cleanPath === "/") {
    parsed.pathname = "/api";
  } else {
    parsed.pathname = cleanPath;
  }

  parsed.search = "";
  parsed.hash = "";

  return parsed
    .toString()
    .replace(/\/+$/, "");
}

function computerFilter(target = {}) {
  const type = String(
    target.type || "all-computers"
  );

  switch (type) {
    case "all-computers":
      return { type };

    case "computer":
      return {
        type,
        computerID:
          asPositiveInt(
            target.computerID,
            "computerID"
          )
      };

    case "computers-in-group":
    case "computers-in-group-or-subgroup":
      return {
        type,
        computerGroupID:
          asPositiveInt(
            target.computerGroupID,
            "computerGroupID"
          )
      };

    case "computers-using-policy":
    case "computers-using-policy-or-subpolicy":
      return {
        type,
        policyID:
          asPositiveInt(
            target.policyID,
            "policyID"
          )
      };

    case "computers-in-smart-folder":
      return {
        type,
        smartFolderID:
          asPositiveInt(
            target.smartFolderID,
            "smartFolderID"
          )
      };

    default:
      throw new Error(
        `Unsupported Deep Security target type: ${type}`
      );
  }
}

class DeepSecurityClient {
  constructor({
    baseUrl,
    apiKey,
    apiVersion,
    actionsEnabled = false,
    fetchImpl = globalThis.fetch
  } = {}) {
    this.baseUrl =
      normalizeBaseUrl(baseUrl);

    this.apiKey =
      String(apiKey || "").trim();

    this.apiVersion =
      String(apiVersion || "").trim();

    this.actionsEnabled =
      actionsEnabled === true;

    this.fetchImpl =
      fetchImpl;
  }

  configuration() {
    return {
      configured:
        Boolean(
          this.baseUrl &&
          this.apiKey &&
          this.apiVersion
        ),
      actionsEnabled:
        this.actionsEnabled,
      transport: "https",
      apiVersion:
        this.apiVersion || null,
      baseUrlConfigured:
        Boolean(this.baseUrl),
      apiKeyConfigured:
        Boolean(this.apiKey),
      timestamp:
        new Date().toISOString()
    };
  }

  requireConfigured() {
    const state =
      this.configuration();

    if (!state.configured) {
      const error =
        new Error(
          "Deep Security is not configured. Set DEEP_SECURITY_URL, DEEP_SECURITY_API_KEY, and DEEP_SECURITY_API_VERSION."
        );

      error.statusCode = 503;
      throw error;
    }
  }

  requireActions() {
    this.requireConfigured();

    if (!this.actionsEnabled) {
      const error =
        new Error(
          "Deep Security actions are locked. Set DEEP_SECURITY_ACTIONS_ENABLED=true to permit the action allowlist."
        );

      error.statusCode = 423;
      throw error;
    }
  }

  async request(
    method,
    pathname,
    {
      query,
      body,
      action = false,
      timeoutMs = 15000
    } = {}
  ) {
    if (action) {
      this.requireActions();
    } else {
      this.requireConfigured();
    }

    if (
      typeof this.fetchImpl !==
      "function"
    ) {
      throw new Error(
        "fetch is unavailable"
      );
    }

    const relativePath =
      String(pathname || "")
        .replace(/^\/+/, "");

    const url =
      new URL(
        relativePath,
        `${this.baseUrl}/`
      );

    for (
      const [key, value] of
      Object.entries(query || {})
    ) {
      if (
        value !== undefined &&
        value !== null
      ) {
        url.searchParams.set(
          key,
          String(value)
        );
      }
    }

    const response =
      await this.fetchImpl(
        url,
        {
          method,
          headers: {
            accept:
              "application/json",
            "content-type":
              "application/json",
            "api-secret-key":
              this.apiKey,
            "api-version":
              this.apiVersion
          },
          ...(body === undefined
            ? {}
            : {
                body:
                  JSON.stringify(body)
              }),
          signal:
            AbortSignal.timeout(
              timeoutMs
            )
        }
      );

    const raw =
      await response.text();

    let data = null;

    if (raw) {
      try {
        data =
          JSON.parse(raw);
      } catch {
        data = {
          raw:
            raw.slice(0, 4000)
        };
      }
    }

    if (!response.ok) {
      const error =
        new Error(
          data?.message ||
          data?.error ||
          `Deep Security returned HTTP ${response.status}`
        );

      error.statusCode =
        response.status;

      error.deepSecurity =
        data;

      throw error;
    }

    return {
      ok: true,
      status:
        response.status,
      data,
      timestamp:
        new Date().toISOString()
    };
  }

  currentApiKey() {
    return this.request(
      "GET",
      "/apikeys/current"
    );
  }

  listComputers() {
    return this.request(
      "GET",
      "/computers",
      {
        query: {
          expand: "none"
        }
      }
    );
  }

  runScan({
    scanType,
    target = {
      type: "all-computers"
    },
    name
  } = {}) {
    const normalized =
      String(scanType || "")
        .trim()
        .toLowerCase();

    if (
      !ALLOWED_SCAN_TYPES.has(
        normalized
      )
    ) {
      throw new Error(
        `scanType must be one of: ${[
          ...ALLOWED_SCAN_TYPES
        ].join(", ")}`
      );
    }

    const definition =
      SCAN_DEFINITIONS[
        normalized
      ];

    const filter =
      computerFilter(target);

    const parameters = {
      computerFilter:
        filter
    };

    if (
      normalized ===
      "malware"
    ) {
      parameters.timeout =
        "four-hours";
    }

    if (
      normalized ===
      "integrity"
    ) {
      parameters.trustedComputers =
        "all-computers";
    }

    const scheduledTask = {
      name:
        String(name || "").trim() ||
        `Eagle Eyes ${definition.type} ${new Date().toISOString()}`,
      type:
        definition.type,
      enabled: true,
      runNow: true,
      scheduleDetails: {
        recurrenceType:
          "none",
        onceOnlyScheduleParameters: {
          startTime:
            Date.now()
        }
      },
      [definition.parameter]:
        parameters
    };

    return this.request(
      "POST",
      "/scheduledtasks",
      {
        action: true,
        body:
          scheduledTask
      }
    );
  }

  addFirewallRulesToComputer(
    computerID,
    ruleIDs
  ) {
    return this.request(
      "POST",
      `/computers/${asPositiveInt(
        computerID,
        "computerID"
      )}/firewall/assignments`,
      {
        action: true,
        body: {
          ruleIDs:
            uniqueRuleIds(
              ruleIDs
            )
        }
      }
    );
  }

  addFirewallRulesToPolicy(
    policyID,
    ruleIDs
  ) {
    return this.request(
      "POST",
      `/policies/${asPositiveInt(
        policyID,
        "policyID"
      )}/firewall/assignments`,
      {
        action: true,
        body: {
          ruleIDs:
            uniqueRuleIds(
              ruleIDs
            )
        }
      }
    );
  }

  setPolicySetting(
    policyID,
    name,
    value
  ) {
    const setting =
      String(name || "").trim();

    if (
      !/^[A-Za-z0-9._-]+$/.test(
        setting
      )
    ) {
      throw new Error(
        "Invalid policy setting name"
      );
    }

    return this.request(
      "POST",
      `/policies/${asPositiveInt(
        policyID,
        "policyID"
      )}/settings/${encodeURIComponent(
        setting
      )}`,
      {
        action: true,
        body: {
          value:
            String(value)
        }
      }
    );
  }

  syncAwsConnector(
    awsConnectorID
  ) {
    return this.request(
      "POST",
      `/awsconnectors/${asPositiveInt(
        awsConnectorID,
        "awsConnectorID"
      )}`,
      {
        action: true,
        query: {
          sync: true
        },
        body: {}
      }
    );
  }
}

function createDeepSecurityFromEnv(
  env = process.env,
  options = {}
) {
  return new DeepSecurityClient({
    baseUrl:
      env.DEEP_SECURITY_URL,
    apiKey:
      env.DEEP_SECURITY_API_KEY,
    apiVersion:
      env.DEEP_SECURITY_API_VERSION,
    actionsEnabled:
      String(
        env.DEEP_SECURITY_ACTIONS_ENABLED ||
        ""
      ).toLowerCase() ===
      "true",
    ...options
  });
}

module.exports = {
  ALLOWED_SCAN_TYPES,
  DeepSecurityClient,
  computerFilter,
  createDeepSecurityFromEnv
};
