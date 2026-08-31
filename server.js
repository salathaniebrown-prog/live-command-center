"use strict";

const express = require("express");
const os = require("os");
const path = require("path");
const { execFile } = require("child_process");
const { promisify } = require("util");

const app = express();
const runFile = promisify(execFile);
const PORT = Number(process.env.PORT) || 3000;
const startedAt = new Date();
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-5.6";
const OPENAI_URL = "https://api.openai.com/v1/responses";

const SOURCES = {
  usgs: "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
  eonet: "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100",
  nws: "https://api.weather.gov/alerts/active"
};

const EMPTY = {
  type: "object",
  properties: {},
  required: [],
  additionalProperties: false
};

const TOOLS = [
  {
    type: "function",
    name: "get_command_center_status",
    description: "Get current Command Center status and uptime.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_command_center_metrics",
    description:
      "Get live container CPU, GPU if exposed, memory, storage and temperature if exposed.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_deployment_status",
    description:
      "Get current Railway deployment state and runtime IDs when exposed.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_system_health",
    description: "Get current API health and uptime.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_world_events",
    description:
      "Get current public events from USGS, NASA EONET, or NOAA/NWS. Never simulate missing data.",
    strict: true,
    parameters: {
      type: "object",
      properties: {
        source: {
          type: "string",
          enum: ["usgs", "eonet", "nws"]
        },
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 20
        }
      },
      required: ["source", "limit"],
      additionalProperties: false
    }
  }
];

const INSTRUCTIONS = [
  "You are Eagle Eyes inside the Live Command Center.",
  "Use tools for current system state, metrics, deployment state, health, or world-event feeds.",
  "Never invent telemetry, alerts, sensor values, or deployment state.",
  "If a value is unavailable, say N/A or unavailable.",
  "All tools are read-only; never claim you changed infrastructure, files, credentials, accounts, or deployments."
].join(" ");

app.disable("x-powered-by");
app.use(express.json({ limit: "256kb" }));
app.use(express.static(path.join(__dirname, "public")));

function cpuTimes() {
  return os.cpus().reduce(
    (s, c) => {
      const t = c.times;
      s.idle += t.idle;
      s.total += t.user + t.nice + t.sys + t.idle + t.irq;
      return s;
    },
    { idle: 0, total: 0 }
  );
}

async function cpuPercent() {
  const a = cpuTimes();

  await new Promise((r) => setTimeout(r, 200));

  const b = cpuTimes();
  const total = b.total - a.total;

  return total > 0
    ? Number(((1 - (b.idle - a.idle) / total) * 100).toFixed(1))
    : null;
}

async function storagePercent() {
  try {
    const { stdout } = await runFile("df", ["-P", "/"]);

    return Number(
      stdout
        .trim()
        .split("\n")
        .at(-1)
        .trim()
        .split(/\s+/)[4]
        .replace("%", "")
    );
  } catch {
    return null;
  }
}

async function gpuPercent() {
  try {
    const { stdout } = await runFile("nvidia-smi", [
      "--query-gpu=utilization.gpu",
      "--format=csv,noheader,nounits"
    ]);

    const v = stdout
      .trim()
      .split("\n")
      .map(Number)
      .filter(Number.isFinite);

    return v.length
      ? Number(
          (v.reduce((a, b) => a + b, 0) / v.length).toFixed(1)
        )
      : null;
  } catch {
    return null;
  }
}

function status() {
  return {
    online: true,
    systemStatus: "ONLINE",
    mode: "LIVE",
    source: "running-container",
    startedAt: startedAt.toISOString(),
    uptimeSeconds: Math.floor(process.uptime()),
    timestamp: new Date().toISOString()
  };
}

async function metrics() {
  const total = os.totalmem();
  const used = total - os.freemem();

  const [cpu, storage, gpu] = await Promise.all([
    cpuPercent(),
    storagePercent(),
    gpuPercent()
  ]);

  return {
    cpu,
    gpu,
    memory: total
      ? Number(((used / total) * 100).toFixed(1))
      : null,
    storage,
    temperatureC: null,
    source: "container",
    timestamp: new Date().toISOString()
  };
}

function deployment() {
  return {
    stage: "RUNNING",
    serviceId: process.env.RAILWAY_SERVICE_ID || null,
    deploymentId: process.env.RAILWAY_DEPLOYMENT_ID || null,
    environment: process.env.RAILWAY_ENVIRONMENT_NAME || null,
    source: "runtime-environment",
    timestamp: new Date().toISOString()
  };
}

function health() {
  return {
    ok: true,
    uptimeSeconds: Math.floor(process.uptime()),
    time: new Date().toISOString()
  };
}

async function jsonFetch(url, headers = {}) {
  const r = await fetch(url, {
    headers,
    signal: AbortSignal.timeout(10000)
  });

  if (!r.ok) {
    throw new Error(`Upstream returned HTTP ${r.status}`);
  }

  return r.json();
}

async function world(source, limit = 10) {
  if (!SOURCES[source]) {
    throw new Error("Unsupported world-event source");
  }

  const n = Math.max(
    1,
    Math.min(20, Number(limit) || 10)
  );

  const headers =
    source === "nws"
      ? {
          accept: "application/geo+json",
          "user-agent":
            "Eagle-Eyes-Live-Command-Center/1.0"
        }
      : {
          accept: "application/json"
        };

  const data = await jsonFetch(
    SOURCES[source],
    headers
  );

  let events;

  if (source === "usgs") {
    events = (data.features || [])
      .slice(0, n)
      .map((f) => ({
        id: f.id || null,
        title: f.properties?.title || null,
        magnitude: Number.isFinite(
          f.properties?.mag
        )
          ? f.properties.mag
          : null,
        place: f.properties?.place || null,
        time: Number.isFinite(
          f.properties?.time
        )
          ? new Date(
              f.properties.time
            ).toISOString()
          : null,
        url: f.properties?.url || null
      }));
  } else if (source === "eonet") {
    events = (data.events || [])
      .slice(0, n)
      .map((e) => ({
        id: e.id || null,
        title: e.title || null,
        categories: (e.categories || [])
          .map((x) => x.title)
          .filter(Boolean),
        time:
          e.geometry?.at(-1)?.date || null,
        link: e.link || null
      }));
  } else {
    events = (data.features || [])
      .slice(0, n)
      .map((f) => ({
        id: f.id || null,
        event:
          f.properties?.event || null,
        headline:
          f.properties?.headline || null,
        severity:
          f.properties?.severity || null,
        area:
          f.properties?.areaDesc || null,
        effective:
          f.properties?.effective || null,
        expires:
          f.properties?.expires || null,
        url:
          f.properties?.web ||
          f.properties?.uri ||
          null
      }));
  }

  return {
    ok: true,
    source,
    sourceUrl: SOURCES[source],
    simulated: false,
    count: events.length,
    events,
    timestamp: new Date().toISOString()
  };
}

async function runTool(call) {
  const args = call.arguments
    ? JSON.parse(call.arguments)
    : {};

  switch (call.name) {
    case "get_command_center_status":
      return status();

    case "get_command_center_metrics":
      return metrics();

    case "get_deployment_status":
      return deployment();

    case "get_system_health":
      return health();

    case "get_world_events":
      return world(
        args.source,
        args.limit
      );

    default:
      throw new Error(
        `Unknown tool: ${call.name}`
      );
  }
}

const callsFrom = (r) =>
  (r?.output || []).filter(
    (x) =>
      x?.type === "function_call"
  );

function textFrom(r) {
  const out = [];

  for (const item of r?.output || []) {
    const parts =
      item?.type === "message" &&
      Array.isArray(item.content)
        ? item.content
        : [];

    for (const p of parts) {
      if (
        p?.type === "output_text" &&
        typeof p.text === "string"
      ) {
        out.push(p.text);
      }
    }
  }

  return out.join("");
}

async function openAI(
  body,
  signal,
  stream = false
) {
  if (!OPENAI_API_KEY) {
    const e = new Error(
      "OPENAI_API_KEY is not configured"
    );

    e.statusCode = 503;

    throw e;
  }

  const r = await fetch(OPENAI_URL, {
    method: "POST",

    headers: {
      authorization:
        `Bearer ${OPENAI_API_KEY}`,

      "content-type":
        "application/json",

      ...(stream
        ? {
            accept:
              "text/event-stream"
          }
        : {})
    },

    body: JSON.stringify({
      ...body,
      ...(stream
        ? {
            stream: true
          }
        : {})
    }),

    signal
  });

  if (!r.ok) {
    const raw = await r.text();

    let msg = raw;

    try {
      msg =
        JSON.parse(raw)?.error?.message ||
        raw;
    } catch {}

    const e = new Error(
      msg ||
        `OpenAI returned HTTP ${r.status}`
    );

    e.statusCode = 502;

    throw e;
  }

  return r;
}

async function assistant(
  message,
  signal
) {
  let input = [
    {
      role: "user",

      content: [
        {
          type: "input_text",
          text: message
        }
      ]
    }
  ];

  for (
    let step = 0;
    step < 6;
    step++
  ) {
    const r = await openAI(
      {
        model: OPENAI_MODEL,
        instructions: INSTRUCTIONS,
        input,
        tools: TOOLS,
        tool_choice: "auto",
        store: false
      },
      signal
    );

    const response = await r.json();

    const calls =
      callsFrom(response);

    if (!calls.length) {
      return {
        responseId:
          response.id || null,

        model:
          response.model ||
          OPENAI_MODEL,

        text:
          textFrom(response)
      };
    }

    input.push(
      ...response.output
    );

    for (const call of calls) {
      try {
        input.push({
          type:
            "function_call_output",

          call_id:
            call.call_id,

          output: JSON.stringify({
            ok: true,

            result:
              await runTool(call)
          })
        });
      } catch (e) {
        input.push({
          type:
            "function_call_output",

          call_id:
            call.call_id,

          output: JSON.stringify({
            ok: false,
            error: e.message
          })
        });
      }
    }
  }

  throw new Error(
    "Eagle Eyes exceeded the tool-call step limit"
  );
}

function sendSSE(
  res,
  event,
  data
) {
  res.write(
    `event: ${event}\n` +
      `data: ${JSON.stringify(data)}\n\n`
  );
}

async function streamedResponse(
  body,
  signal,
  onEvent
) {
  const r = await openAI(
    body,
    signal,
    true
  );

  if (!r.body) {
    throw new Error(
      "OpenAI stream returned no body"
    );
  }

  const reader =
    r.body.getReader();

  const decoder =
    new TextDecoder();

  let buffer = "";
  let completed = null;

  while (true) {
    const {
      value,
      done
    } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(
      value,
      {
        stream: true
      }
    );

    buffer =
      buffer.replace(
        /\r\n/g,
        "\n"
      );

    let i;

    while (
      (i =
        buffer.indexOf(
          "\n\n"
        )) !== -1
    ) {
      const block =
        buffer.slice(
          0,
          i
        );

      buffer =
        buffer.slice(
          i + 2
        );

      const payload =
        block
          .split("\n")
          .filter(
            (x) =>
              x.startsWith(
                "data:"
              )
          )
          .map((x) =>
            x
              .slice(5)
              .trimStart()
          )
          .join("\n");

      if (
        !payload ||
        payload === "[DONE]"
      ) {
        continue;
      }

      let event;

      try {
        event =
          JSON.parse(
            payload
          );
      } catch {
        continue;
      }

      if (
  event.type ===
  "response.failed"
) {
  throw new Error(
    event.response?.error?.message ||
      event.response?.error?.code ||
      "OpenAI response failed"
  );
}

if (
  event.type ===
  "response.incomplete"
) {
  const reason =
    event.response?.incomplete_details?.reason ||
    "unknown reason";

  throw new Error(
    `OpenAI response incomplete: ${reason}`
  );
}

if (
  event.type ===
  "error"
) {
  throw new Error(
    event.message ||
      event.error?.message ||
      event.error?.code ||
      "OpenAI streaming error"
  );
}

if (
  event.type ===
  "response.completed"
) {
  completed =
    event.response;
}

await onEvent(event);
    }
  }

  if (!completed) {
    throw new Error(
      "OpenAI stream ended before response.completed"
    );
  }

  return completed;
}

async function assistantStream(
  message,
  res,
  signal
) {
  let input = [
    {
      role: "user",

      content: [
        {
          type: "input_text",
          text: message
        }
      ]
    }
  ];

  for (
    let step = 0;
    step < 6;
    step++
  ) {
    const completed =
      await streamedResponse(
        {
          model:
            OPENAI_MODEL,

          instructions:
            INSTRUCTIONS,

          input,

          tools:
            TOOLS,

          tool_choice:
            "auto",

          store:
            false
        },

        signal,

        async (event) => {
          if (
            event.type ===
              "response.output_text.delta" &&
            typeof event.delta ===
              "string"
          ) {
            sendSSE(
              res,
              "delta",
              {
                text:
                  event.delta
              }
            );
          }

          if (
            event.type ===
            "response.function_call_arguments.done"
          ) {
            sendSSE(
              res,
              "tool_call",
              {
                name:
                  event.name
              }
            );
          }
        }
      );

    const calls =
      callsFrom(completed);

    if (!calls.length) {
      sendSSE(
        res,
        "done",
        {
          responseId:
            completed.id ||
            null,

          model:
            completed.model ||
            OPENAI_MODEL
        }
      );

      return;
    }

    input.push(
      ...completed.output
    );

    for (const call of calls) {
      try {
        const result =
          await runTool(
            call
          );

        input.push({
          type:
            "function_call_output",

          call_id:
            call.call_id,

          output:
            JSON.stringify({
              ok: true,
              result
            })
        });

        sendSSE(
          res,
          "tool_result",
          {
            name:
              call.name,

            ok: true
          }
        );
      } catch (e) {
        input.push({
          type:
            "function_call_output",

          call_id:
            call.call_id,

          output:
            JSON.stringify({
              ok: false,
              error:
                e.message
            })
        });

        sendSSE(
          res,
          "tool_result",
          {
            name:
              call.name,

            ok: false
          }
        );
      }
    }
  }

  throw new Error(
    "Eagle Eyes exceeded the tool-call step limit"
  );
}

app.get(
  "/api/status",
  (_req, res) =>
    res.json(status())
);

app.get(
  "/api/metrics",
  async (_req, res, next) => {
    try {
      res.json(
        await metrics()
      );
    } catch (e) {
      next(e);
    }
  }
);

app.get(
  "/api/workloads",
  (_req, res) =>
    res.json([])
);

app.get(
  "/api/deployment",
  (_req, res) =>
    res.json(
      deployment()
    )
);

app.get(
  "/api/health",
  (_req, res) =>
    res.json(
      health()
    )
);

app.get(
  "/api/eagle-eyes/sources",
  (_req, res) =>
    res.json({
      ok: true,
      simulated: false,
      sources:
        Object.keys(
          SOURCES
        ),
      urls:
        SOURCES,
      timestamp:
        new Date().toISOString()
    })
);

app.get(
  "/api/eagle-eyes/events",
  async (req, res) => {
    try {
      res.json(
        await world(
          String(
            req.query.source ||
              ""
          ).toLowerCase(),

          Number(
            req.query.limit ||
              10
          )
        )
      );
    } catch (e) {
      res.status(502).json({
        ok: false,
        error:
          e.message,
        timestamp:
          new Date().toISOString()
      });
    }
  }
);

app.get(
  "/api/assistant/status",
  (_req, res) =>
    res.json({
      ok: true,

      configured:
        Boolean(
          OPENAI_API_KEY
        ),

      model:
        OPENAI_MODEL,

      transport:
        "responses-api-sse",

      readOnlyTools:
        TOOLS.map(
          (t) =>
            t.name
        ),

      timestamp:
        new Date().toISOString()
    })
);

app.post(
  "/api/assistant",
  async (req, res) => {
    const message =
      typeof req.body?.message ===
      "string"
        ? req.body.message.trim()
        : "";

    if (!message) {
      return res
        .status(400)
        .json({
          ok: false,
          error:
            "message is required"
        });
    }

    if (
      message.length >
      12000
    ) {
      return res
        .status(413)
        .json({
          ok: false,
          error:
            "message is too large"
        });
    }

    try {
      return res.json({
        ok: true,

        ...(await assistant(
          message
        ))
      });
    } catch (e) {
      return res
        .status(
          e.statusCode ||
            502
        )
        .json({
          ok: false,
          error:
            e.message
        });
    }
  }
);

app.post(
  "/api/assistant/stream",
  async (req, res) => {
    const message =
      typeof req.body?.message ===
      "string"
        ? req.body.message.trim()
        : "";

    if (!message) {
      return res
        .status(400)
        .json({
          ok: false,
          error:
            "message is required"
        });
    }

    if (
      message.length >
      12000
    ) {
      return res
        .status(413)
        .json({
          ok: false,
          error:
            "message is too large"
        });
    }

    if (
      !OPENAI_API_KEY
    ) {
      return res
        .status(503)
        .json({
          ok: false,
          error:
            "OPENAI_API_KEY is not configured"
        });
    }

    res
      .status(200)
      .set({
        "content-type":
          "text/event-stream; charset=utf-8",

        "cache-control":
          "no-cache, no-transform",

        connection:
          "keep-alive",

        "x-accel-buffering":
          "no"
      });

    res.flushHeaders();

    const controller =
      new AbortController();

    res.on(
      "close",
      () =>
        controller.abort()
    );

    sendSSE(
      res,
      "ready",
      {
        model:
          OPENAI_MODEL
      }
    );

    try {
      await assistantStream(
        message,
        res,
        controller.signal
      );
    } catch (e) {
      if (
        !controller
          .signal
          .aborted
      ) {
        sendSSE(
          res,
          "error",
          {
            message:
              e.message
          }
        );
      }
    } finally {
      if (
        !res.writableEnded
      ) {
        res.end();
      }
    }
  }
);

app.get(
  "/api/dedalus/health",
  async (_req, res) => {
    const key =
      process.env
        .DEDALUS_API_KEY;

    if (!key) {
      return res
        .status(503)
        .json({
          ok: false,
          service:
            "dedalus",
          error:
            "DEDALUS_API_KEY is not configured"
        });
    }

    try {
      const r =
        await fetch(
          "https://api.dedaluslabs.ai/v1/models",
          {
            headers: {
              Authorization:
                `Bearer ${key}`
            },

            signal:
              AbortSignal.timeout(
                10000
              )
          }
        );

      if (!r.ok) {
        return res
          .status(502)
          .json({
            ok: false,
            service:
              "dedalus",
            error:
              `Dedalus returned HTTP ${r.status}`
          });
      }

      return res.json({
        ok: true,
        service:
          "dedalus",
        connected:
          true,
        timestamp:
          new Date().toISOString()
      });
    } catch {
      return res
        .status(502)
        .json({
          ok: false,
          service:
            "dedalus",
          error:
            "Dedalus connection failed"
        });
    }
  }
);

app.use(
  (
    err,
    _req,
    res,
    _next
  ) => {
    console.error(err);

    res
      .status(500)
      .json({
        ok: false,
        error:
          "Internal server error"
      });
  }
);

app.listen(
  PORT,
  "0.0.0.0",
  () =>
    console.log(
      `Command Center listening on port ${PORT}`
    )
);
