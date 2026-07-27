class AudioStreamer {
  constructor(onAudioChunk, onAnalyserData) {
    this.onAudioChunk = onAudioChunk;
    this.onAnalyserData = onAnalyserData;
    this.audioContext = null;
    this.stream = null;
    this.source = null;
    this.workletNode = null;
    this.analyser = null;
    this.isRecording = false;
    this.targetSampleRate = 16000;
    this.fractionalReadIndex = 0;
  }

  async start(deviceId = null) {
    try {
      this.fractionalReadIndex = 0;
      const audioConstraints = {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      };
      if (deviceId) {
        audioConstraints.deviceId = { exact: deviceId };
      }

      this.stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      try {
        this.audioContext = new AudioCtx({ sampleRate: 16000 });
      } catch (e) {
        this.audioContext = new AudioCtx();
      }

      const inputSampleRate = this.audioContext.sampleRate;

      this.source = this.audioContext.createMediaStreamSource(this.stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.source.connect(this.analyser);

      const workletUrl = window.location.origin + (window.location.pathname.startsWith('/static') ? '' : '/static') + '/js/audio-processors/capture.worklet.js';
      try {
        await this.audioContext.audioWorklet.addModule(workletUrl);
      } catch (e) {
        await this.audioContext.audioWorklet.addModule('/static/js/audio-processors/capture.worklet.js');
      }

      this.workletNode = new AudioWorkletNode(this.audioContext, 'capture-worklet');

      this.workletNode.port.onmessage = (event) => {
        if (!this.isRecording) return;
        const msg = event.data;
        if (msg.type === 'audio' && msg.samples) {
          if (this.onAnalyserData && this.analyser) {
            const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            this.analyser.getByteFrequencyData(dataArray);
            this.onAnalyserData(dataArray);
          }

          const resampled = this.resampleBuffer(msg.samples, inputSampleRate, this.targetSampleRate);
          const pcm16 = this.floatTo16BitPCM(resampled);
          const base64Data = this.arrayBufferToBase64(pcm16.buffer);

          if (this.onAudioChunk && base64Data) {
            this.onAudioChunk(base64Data);
          }
        }
      };

      this.source.connect(this.workletNode);
      const muteGain = this.audioContext.createGain();
      muteGain.gain.value = 0;
      this.workletNode.connect(muteGain);
      muteGain.connect(this.audioContext.destination);

      this.isRecording = true;
      console.log("AudioStreamer started. Input rate:", inputSampleRate, "Target rate:", this.targetSampleRate);
    } catch (err) {
      console.error("AudioStreamer start error:", err);
      throw err;
    }
  }

  stop() {
    this.isRecording = false;
    this.fractionalReadIndex = 0;
    if (this.workletNode) {
      this.workletNode.disconnect();
      this.workletNode = null;
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
    console.log("AudioStreamer stopped.");
  }

  resampleBuffer(buffer, fromSampleRate, toSampleRate) {
    if (fromSampleRate === toSampleRate) return buffer;
    const ratio = fromSampleRate / toSampleRate;
    let readIndex = this.fractionalReadIndex;
    const outputSamples = [];

    while (readIndex < buffer.length - 1) {
      const index = Math.floor(readIndex);
      const frac = readIndex - index;
      const sample1 = buffer[index];
      const sample2 = buffer[index + 1];
      const interpolated = sample1 + frac * (sample2 - sample1);
      outputSamples.push(interpolated);
      readIndex += ratio;
    }

    this.fractionalReadIndex = readIndex - buffer.length;
    return new Float32Array(outputSamples);
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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = AudioStreamer;
}
