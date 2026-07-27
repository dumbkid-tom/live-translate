class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.currentChunk = null;
    this.chunkOffset = 0;
    this.bufferedSamples = 0;
    this.isPlaying = false;
    this.initialThreshold = 1200; // ~50ms jitter buffer threshold at 24kHz

    this.port.onmessage = (event) => {
      const data = event.data;
      if (!data) return;
      if (data.command === 'clear') {
        this.queue = [];
        this.currentChunk = null;
        this.chunkOffset = 0;
        this.bufferedSamples = 0;
        this.isPlaying = false;
      } else if (data.command === 'play' && data.samples) {
        this.queue.push(data.samples);
        this.bufferedSamples += data.samples.length;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const output = outputs[0];
    if (!output || output.length === 0) return true;

    const channel0 = output[0];
    const channel1 = output.length > 1 ? output[1] : null;
    const frameCount = channel0.length;

    if (!this.isPlaying) {
      if (this.bufferedSamples >= this.initialThreshold || this.queue.length >= 3) {
        this.isPlaying = true;
      } else {
        channel0.fill(0);
        if (channel1) channel1.fill(0);
        return true;
      }
    }

    for (let i = 0; i < frameCount; i++) {
      while (!this.currentChunk || this.chunkOffset >= this.currentChunk.length) {
        if (this.queue.length === 0) {
          this.currentChunk = null;
          this.chunkOffset = 0;
          this.bufferedSamples = 0;
          this.isPlaying = false;
          break;
        }
        this.currentChunk = this.queue.shift();
        this.chunkOffset = 0;
      }

      if (this.currentChunk && this.chunkOffset < this.currentChunk.length) {
        const val = this.currentChunk[this.chunkOffset++];
        this.bufferedSamples--;
        channel0[i] = val;
        if (channel1) channel1[i] = val;
      } else {
        channel0[i] = 0;
        if (channel1) channel1[i] = 0;
      }
    }

    return true;
  }
}

registerProcessor('playback-worklet', PlaybackProcessor);
