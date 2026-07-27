class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 2048;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input && input.length > 0) {
      const channel = input[0];
      for (let i = 0; i < channel.length; i++) {
        this.buffer[this.bufferIndex++] = channel[i];
        if (this.bufferIndex >= this.bufferSize) {
          const copy = new Float32Array(this.buffer);
          this.port.postMessage({ type: 'audio', samples: copy }, [copy.buffer]);
          this.buffer = new Float32Array(this.bufferSize);
          this.bufferIndex = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor('capture-worklet', CaptureProcessor);
