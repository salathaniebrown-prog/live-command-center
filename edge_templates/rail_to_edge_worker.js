export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const railOrigin = env.RAIL_ORIGIN || "https://your-app.up.railway.app";
    const edgeOrigin = env.EDGE_ORIGIN || "https://your-tunnel-domain.com";
    const timeoutMs = Number(env.RAIL_TIMEOUT_MS || 3000);

    const buildForward = (origin) => {
      const target = new URL(url.pathname + url.search, origin);
      return new Request(target.toString(), {
        method: request.method,
        headers: request.headers,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "manual",
      });
    };

    const fetchWithTimeout = async (req, ms) => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), ms);
      try {
        return await fetch(req, { signal: ctrl.signal });
      } finally {
        clearTimeout(timer);
      }
    };

    try {
      const railResp = await fetchWithTimeout(buildForward(railOrigin), timeoutMs);
      if (railResp.status < 500) {
        const res = new Response(railResp.body, railResp);
        res.headers.set("X-Salathanie-Origin", "RAIL-PRIMARY");
        return res;
      }
    } catch (_) {
      // Railway unreachable or timed out -> fall through to Edge
    }

    const edgeResp = await fetch(buildForward(edgeOrigin));
    const failover = new Response(edgeResp.body, edgeResp);
    failover.headers.set("X-Salathanie-Origin", "EDGE-FAILOVER");
    return failover;
  },
};
