class AudioPlayer {
  constructor(sampleRate = 24000) {
    this.sampleRate = sampleRate;
    this.audioCtx = null;
    this.workletNode = null;
    this.gainNode = null;
    this.volume = 1.0;
    this.initPromise = null;
    this.playPromise = Promise.resolve();
  }

  async init() {
    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = (async () => {
      if (!this.audioCtx || this.audioCtx.state === 'closed') {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.audioCtx = new AudioCtx({ sampleRate: this.sampleRate });
        this.gainNode = this.audioCtx.createGain();
        this.gainNode.gain.value = this.volume;

        const workletUrl = window.location.origin + (window.location.pathname.startsWith('/static') ? '' : '/static') + '/js/audio-processors/playback.worklet.js';
        try {
          await this.audioCtx.audioWorklet.addModule(workletUrl);
        } catch (e) {
          await this.audioCtx.audioWorklet.addModule('/static/js/audio-processors/playback.worklet.js');
        }

        this.workletNode = new AudioWorkletNode(this.audioCtx, 'playback-worklet');
        this.workletNode.connect(this.gainNode);
        this.gainNode.connect(this.audioCtx.destination);
      }

      if (this.audioCtx.state === 'suspended') {
        await this.audioCtx.resume();
      }
    })().catch((err) => {
      this.initPromise = null;
      throw err;
    });

    return this.initPromise;
  }

  setVolume(val) {
    this.volume = Math.max(0, Math.min(1, val));
    if (this.gainNode && this.audioCtx) {
      this.gainNode.gain.setValueAtTime(this.volume, this.audioCtx.currentTime);
    }
  }

  playChunk(base64Data) {
    this.playPromise = this.playPromise.then(async () => {
      await this.init();

      const binaryString = window.atob(base64Data);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      const int16Array = new Int16Array(bytes.buffer);
      const float32Array = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / (int16Array[i] < 0 ? 32768 : 32767);
      }

      if (this.workletNode) {
        this.workletNode.port.postMessage({
          command: 'play',
          samples: float32Array
        });
      }
    }).catch(err => {
      console.error("Error playing audio chunk:", err);
    });
    return this.playPromise;
  }

  clear() {
    if (this.workletNode) {
      this.workletNode.port.postMessage({ command: 'clear' });
    }
  }

  stop() {
    this.clear();
    this.initPromise = null;
    this.playPromise = Promise.resolve();
    if (this.audioCtx && this.audioCtx.state !== 'closed') {
      this.audioCtx.close();
      this.audioCtx = null;
      this.workletNode = null;
      this.gainNode = null;
    }
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = AudioPlayer;
}
