class AudioPlayer {
  constructor(sampleRate = 24000) {
    this.sampleRate = sampleRate;
    this.audioCtx = null;
    this.nextStartTime = 0;
  }

  init() {
    if (!this.audioCtx || this.audioCtx.state === 'closed') {
      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: this.sampleRate });
      this.nextStartTime = this.audioCtx.currentTime;
    }
  }

  playChunk(base64Data) {
    this.init();
    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }

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

    const audioBuffer = this.audioCtx.createBuffer(1, float32Array.length, this.sampleRate);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = this.audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioCtx.destination);

    const currentTime = this.audioCtx.currentTime;
    const startTime = Math.max(currentTime, this.nextStartTime);
    source.start(startTime);
    this.nextStartTime = startTime + audioBuffer.duration;
  }

  clear() {
    if (this.audioCtx) {
      this.nextStartTime = this.audioCtx.currentTime;
    }
  }

  stop() {
    if (this.audioCtx && this.audioCtx.state !== 'closed') {
      this.audioCtx.close();
      this.audioCtx = null;
    }
    this.nextStartTime = 0;
  }
}
