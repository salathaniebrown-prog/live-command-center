// Dedicated SimliAvatar component using simli-client@^3.2.0 over LiveKit (default transport, ICE servers = null)
export class SimliAvatar {
  constructor({ videoEl, audioEl, onStatus, onLog, onVideoInfo, onWarning, onStart }) {
    this.videoEl = videoEl;
    this.audioEl = audioEl;
    this.onStatus = onStatus || (() => {});
    this.onLog = onLog || (() => {});
    this.onVideoInfo = onVideoInfo || (() => {});
    this.onWarning = onWarning || (() => {});
    this.onStart = onStart || (() => {});
    this.client = null;
    this.isStarted = false;
    this.isStopping = false;
    this.faceId = "80459b57-2d66-4ca7-8682-59e1c649bc53/92f24a0c-f046-45df-8df0-af7449c04571";
  }

  async _loadSimliSDK() {
    // Load simli-client@^3.2.0 from local server bundle (/simli-client.js) or ESM CDN fallback
    try {
      return await import('/simli-client.js');
    } catch (_) {
      return await import('https://esm.sh/simli-client@^3.2.0');
    }
  }

  async _mintSessionToken() {
    const resp = await fetch('/api/simli/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ faceId: this.faceId })
    });
    const data = await resp.json();
    if (!resp.ok || !data.session_token) {
      const err = new Error(data.error || `Simli refused session (${resp.status})`);
      err.isRefusal = true; // Do not retry server/Simli policy refusals (missing key, expired token, 0 minutes)
      throw err;
    }
    return data;
  }

  async start() {
    this.isStopping = false;
    const { SimliClient } = await this._loadSimliSDK();

    let attempt = 0;
    const maxNetworkRetries = 3;

    while (!this.isStopping) {
      attempt += 1;
      try {
        this.onStatus(attempt > 1 ? `RECONNECTING (${attempt})...` : 'MINTING TOKEN...');
        const tokenData = await this._mintSessionToken();

        // Initialize SimliClient with HTML <video> & <audio> refs, LiveKit default transport, and ICE servers = null
        this.client = new SimliClient(
          tokenData.session_token,
          this.videoEl,
          this.audioEl,
          null,           // LiveKit default transport: pass null for ICE servers (no generateIceServers call)
          undefined,      // logLevel default
          'livekit'       // LiveKit transport
        );

        this.client.on('start', () => {
          this.isStarted = true;
          this.onStatus('SIMLI LIVE // 768x768');
          this.onLog('[SIMLI]: Probable Lamprey session started (Trinity-2 | LiveKit).');
          // Say the first message as soon as Simli's start event fires (do not wait for mic permissions)
          this.onStart(tokenData.first_message || 'Hello! What can I help you with today?');
        });

        this.client.on('stop', () => {
          this.isStarted = false;
          this.onStatus('SESSION STOPPED');
          this.onLog('[SIMLI]: Session stopped.');
        });

        this.client.on('video_info', (info) => {
          const meta = (info && info.video_metadata) ? info.video_metadata : info;
          this.onVideoInfo(meta);
          if (meta && meta.width && meta.height) {
            this.videoEl.style.aspectRatio = `${meta.width} / ${meta.height}`;
            this.onLog(`[SIMLI VIDEO]: ${meta.width}x${meta.height} @ ${meta.fps || 25} FPS`);
          }
        });

        this.client.on('warning', (warn) => {
          const msg = typeof warn === 'string' ? warn : JSON.stringify(warn);
          this.onWarning(msg);
          this.onLog(`[SIMLI WARNING]: ${msg}`);
        });

        this.client.on('error', (err) => {
          const msg = err && err.message ? err.message : String(err);
          this.onLog(`[SIMLI ERROR]: ${msg}`);
        });

        this.onStatus('CONNECTING LIVEKIT...');
        await this.client.start();
        return;
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        // Reject immediately if Simli refused the session (expired token, invalid key, no minutes left)
        const isSimliRefusal = err.isRefusal || /expired|unauthorized|invalid|minute|quota|refused|401|402|403/i.test(msg);
        if (isSimliRefusal || attempt > maxNetworkRetries || this.isStopping) {
          this.onStatus('SESSION REFUSED');
          this.onLog(`[SIMLI START FAILED]: ${msg}`);
          throw err;
        }
        // Retry network failures only, with exponential backoff
        const backoffMs = Math.min(4000, 600 * Math.pow(2, attempt - 1));
        this.onLog(`[SIMLI NETWORK RETRY ${attempt}/${maxNetworkRetries} in ${backoffMs}ms]: ${msg}`);
        await new Promise((r) => setTimeout(r, backoffMs));
      }
    }
  }

  // Raw PCM16 at 16 kHz -> Simli sendAudioData
  sendAudioData(pcm16Uint8Array) {
    if (this.client && this.isStarted && pcm16Uint8Array && pcm16Uint8Array.byteLength > 0) {
      this.client.sendAudioData(pcm16Uint8Array);
    }
  }

  // MediaStreamTrack (or <audio>.captureStream()) -> Simli listenToMediastreamTrack
  listenToMediastreamTrack(track) {
    if (this.client && this.isStarted && track) {
      this.client.listenToMediastreamTrack(track);
    }
  }

  // Clear queued audio immediately when user interrupts
  clearBuffer() {
    if (this.client && this.isStarted) {
      if (typeof this.client.ClearBuffer === 'function') this.client.ClearBuffer();
      else if (typeof this.client.clearBuffer === 'function') this.client.clearBuffer();
    }
  }

  // Trinity-2 live camera, background, and foreground controls
  setCamera(params) {
    if (this.client && this.isStarted && typeof this.client.setCamera === 'function') {
      this.client.setCamera(params);
    }
  }

  setBackground(bg) {
    if (this.client && this.isStarted && typeof this.client.setBackground === 'function') {
      this.client.setBackground(bg);
    }
  }

  setForeground(fg) {
    if (this.client && this.isStarted && typeof this.client.setForeground === 'function') {
      this.client.setForeground(fg);
    }
  }

  async stop() {
    this.isStopping = true;
    this.isStarted = false;
    if (this.client) {
      try {
        await this.client.stop();
      } catch (_) {}
      this.client = null;
    }
    this.onStatus('OFFLINE');
  }
}
