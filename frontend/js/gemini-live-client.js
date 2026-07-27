class GeminiLiveClient {
  constructor(options = {}) {
    this.wsEndpoint = options.wsEndpoint;
    this.setupPayload = options.setupPayload;
    this.tokenExpiresAt = options.tokenExpiresAt;
    this.onEvent = options.onEvent || (() => {});
    this.onClose = options.onClose || (() => {});
    this.onError = options.onError || (() => {});

    this.ws = null;
    this.isConnected = false;
    this.setupComplete = false;
    this.expirationTimer = null;
  }

  connect(timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
      let isSettled = false;
      let setupTimer = null;

      const cleanupSetupTimer = () => {
        if (setupTimer) {
          clearTimeout(setupTimer);
          setupTimer = null;
        }
      };

      const safeResolve = () => {
        if (!isSettled) {
          isSettled = true;
          cleanupSetupTimer();
          resolve();
        }
      };

      const safeReject = (err) => {
        if (!isSettled) {
          isSettled = true;
          cleanupSetupTimer();
          reject(err instanceof Error ? err : new Error(String(err.message || err)));
        }
      };

      setupTimer = setTimeout(() => {
        if (!this.setupComplete) {
          const timeoutErr = new Error(`Gemini Live connection setup timed out after ${timeoutMs}ms`);
          safeReject(timeoutErr);
          this.disconnect();
        }
      }, timeoutMs);

      try {
        this.ws = new WebSocket(this.wsEndpoint);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
          console.log("WebSocket connected directly to Gemini API.");
          this.isConnected = true;
          const setupMsg = this.setupPayload.setup ? this.setupPayload : { setup: this.setupPayload };
          this.ws.send(JSON.stringify(setupMsg));
          this.scheduleExpirationWarning();
        };

        this.ws.onmessage = async (event) => {
          try {
            let data = event.data;
            if (typeof Blob !== 'undefined' && data instanceof Blob) {
              data = await data.text();
            }
            const parsedEvents = GeminiLiveProtocol.parseGeminiMessage(data);
            for (const ev of parsedEvents) {
              if (ev.type === 'setup_complete') {
                this.setupComplete = true;
                safeResolve();
              } else if (ev.type === 'error') {
                console.error("Received error frame from Gemini server:", ev.error);
                this.onError(ev);
                if (!this.setupComplete) {
                  safeReject(new Error(typeof ev.error === 'string' ? ev.error : ev.error?.message || JSON.stringify(ev.error)));
                }
              } else if (ev.type === 'go_away') {
                console.warn("Received goAway from Gemini server.");
              }
              this.onEvent(ev);
            }
          } catch (e) {
            console.error("Error processing Gemini message:", e);
          }
        };

        this.ws.onerror = (err) => {
          console.error("Gemini WebSocket error:", err);
          this.onError(err);
          safeReject(err);
        };

        this.ws.onclose = (event) => {
          console.log(`Gemini WebSocket closed (code=${event.code}).`);
          this.isConnected = false;
          this.setupComplete = false;
          if (this.expirationTimer) clearTimeout(this.expirationTimer);
          if (!isSettled) {
            safeReject(new Error(`WebSocket closed before setup complete (code=${event.code})`));
          }
          this.onClose(event);
        };
      } catch (err) {
        safeReject(err);
      }
    });
  }

  sendAudio(pcmBase64, mimeType = "audio/pcm;rate=16000") {
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.setupComplete) {
      const msg = GeminiLiveProtocol.buildAudioFrame ?
        GeminiLiveProtocol.buildAudioFrame(pcmBase64, mimeType) :
        GeminiLiveProtocol.buildRealtimeAudioChunk(pcmBase64, mimeType);
      this.ws.send(JSON.stringify(msg));
    }
  }

  sendText(text) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.setupComplete) {
      const msg = GeminiLiveProtocol.buildTextFrame ?
        GeminiLiveProtocol.buildTextFrame(text) :
        GeminiLiveProtocol.buildRealtimeTextChunk(text);
      this.ws.send(JSON.stringify(msg));
    }
  }

  scheduleExpirationWarning() {
    if (!this.tokenExpiresAt) return;
    const expiresMs = new Date(this.tokenExpiresAt).getTime() - Date.now();
    const warningLeadMs = 2 * 60 * 1000;
    const delay = Math.max(0, expiresMs - warningLeadMs);

    if (this.expirationTimer) clearTimeout(this.expirationTimer);
    this.expirationTimer = setTimeout(() => {
      this.onEvent({ type: 'token_expiring_soon' });
    }, delay);
  }

  disconnect() {
    if (this.expirationTimer) clearTimeout(this.expirationTimer);
    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.close();
      }
      this.ws = null;
    }
    this.isConnected = false;
    this.setupComplete = false;
  }
}
