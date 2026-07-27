const GeminiLiveProtocol = {
  parseGeminiMessage(input) {
    let msg = input;
    if (typeof input === 'string') {
      try {
        msg = JSON.parse(input);
      } catch (e) {
        return [];
      }
    } else if (typeof ArrayBuffer !== 'undefined' && (input instanceof ArrayBuffer || ArrayBuffer.isView(input))) {
      try {
        const decoder = new TextDecoder('utf-8');
        const str = decoder.decode(input);
        msg = JSON.parse(str);
      } catch (e) {
        return [];
      }
    }
    if (!msg || typeof msg !== 'object') return [];

    const events = [];

    if (msg.error !== undefined) {
      events.push({ type: 'error', error: msg.error });
    }

    if (msg.setupComplete !== undefined) {
      events.push({ type: 'setup_complete' });
    }

    if (msg.goAway !== undefined) {
      events.push({ type: 'go_away' });
    }

    if (msg.serverContent) {
      const sc = msg.serverContent;

      if (sc.interrupted) {
        events.push({ type: 'interrupted' });
      }

      if (sc.modelTurn && Array.isArray(sc.modelTurn.parts)) {
        for (const part of sc.modelTurn.parts) {
          if (part.text) {
            events.push({ type: 'text', text: part.text });
          }
          if (part.inlineData) {
            events.push({
              type: 'audio',
              data: part.inlineData.data,
              mimeType: part.inlineData.mimeType || 'audio/pcm;rate=24000'
            });
          }
        }
      }

      if (sc.outputTranscription && sc.outputTranscription.text) {
        events.push({
          type: 'text',
          text: sc.outputTranscription.text,
          finished: sc.outputTranscription.finished,
          languageCode: sc.outputTranscription.languageCode
        });
      }

      if (sc.inputAudioTranscription && sc.inputAudioTranscription.text) {
        events.push({
          type: 'source_text',
          text: sc.inputAudioTranscription.text,
          finished: sc.inputAudioTranscription.finished,
          languageCode: sc.inputAudioTranscription.languageCode
        });
      } else if (sc.inputTranscription && sc.inputTranscription.text) {
        events.push({
          type: 'source_text',
          text: sc.inputTranscription.text,
          finished: sc.inputTranscription.finished,
          languageCode: sc.inputTranscription.languageCode
        });
      }

      if (sc.turnComplete) {
        events.push({ type: 'turn_complete' });
      }
    }

    return events;
  },

  buildAudioFrame(pcmBase64, mimeType = 'audio/pcm;rate=16000') {
    return {
      realtimeInput: {
        audio: {
          mimeType: mimeType || 'audio/pcm;rate=16000',
          data: pcmBase64
        }
      }
    };
  },

  buildRealtimeAudioChunk(pcmBase64, mimeType = 'audio/pcm;rate=16000') {
    return this.buildAudioFrame(pcmBase64, mimeType);
  },

  buildTextFrame(text) {
    return {
      clientContent: {
        turns: [
          {
            role: 'user',
            parts: [{ text: text }]
          }
        ],
        turnComplete: true
      }
    };
  },

  buildRealtimeTextChunk(text) {
    return this.buildTextFrame(text);
  }
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = GeminiLiveProtocol;
}
