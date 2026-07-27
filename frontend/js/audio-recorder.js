class AudioRecorder {
  constructor(onAudioChunk, onAnalyserData) {
    self = this;
    this.onAudioChunk = onAudioChunk;
    this.onAnalyserData = onAnalyserData;
    this.audioContext = null;
    this.stream = null;
    this.source = null;
    this.processor = null;
    this.analyser = null;
    this.isRecording = false;
    this.targetSampleRate = 16000;
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const inputSampleRate = this.audioContext.sampleRate;

      this.source = this.audioContext.createMediaStreamSource(this.stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.source.connect(this.analyser);

      // Buffer size 4096 frames
      const bufferSize = 4096;
      this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

      this.processor.onaudioprocess = (event) => {
        if (!this.isRecording) return;
        
        const inputData = event.inputBuffer.getChannelData(0);
        
        // Visualize waveform data
        if (this.onAnalyserData && this.analyser) {
          const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
          this.analyser.getByteFrequencyData(dataArray);
          this.onAnalyserData(dataArray);
        }

        // Resample input audio data to 16,000 Hz 16-bit PCM
        const resampledData = this.resampleBuffer(inputData, inputSampleRate, this.targetSampleRate);
        const pcm16 = this.floatTo16BitPCM(resampledData);
        const base64Data = this.arrayBufferToBase64(pcm16.buffer);

        if (this.onAudioChunk && base64Data) {
          this.onAudioChunk(base64Data);
        }
      };

      this.source.connect(this.processor);
      this.processor.connect(this.audioContext.destination);
      this.isRecording = true;
      console.log("AudioRecorder started successfully. Input rate:", inputSampleRate);
    } catch (err) {
      console.error("Microphone access error:", err);
      throw err;
    }
  }

  stop() {
    this.isRecording = false;
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.audioContext && this.audioContext.state !== 'closed') {
      this.audioContext.close();
      this.audioContext = null;
    }
    console.log("AudioRecorder stopped.");
  }

  resampleBuffer(buffer, fromSampleRate, toSampleRate) {
    if (fromSampleRate === toSampleRate) return buffer;
    const ratio = fromSampleRate / toSampleRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const originIndex = Math.floor(i * ratio);
      result[i] = buffer[originIndex];
    }
    return result;
  }

  floatTo16BitPCM(output) {
    const buffer = new ArrayBuffer(output.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < output.length; i++) {
      const s = Math.max(-1, Math.min(1, output[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return new Int16Array(buffer);
  }

  arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }
}
