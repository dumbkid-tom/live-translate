document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const headphoneBanner = document.getElementById('headphone-banner');
  const dismissBannerBtn = document.getElementById('dismiss-banner-btn');
  const translationModeSelect = document.getElementById('translation-mode-select');
  const targetLanguageSelect = document.getElementById('target-language');
  const sourceLanguageSelect = document.getElementById('source-language');
  const modeAudioBtn = document.getElementById('mode-audio');
  const modeTextBtn = document.getElementById('mode-text');
  const toggleBtn = document.getElementById('toggle-btn');
  const statusIndicator = document.getElementById('status-indicator');
  const statusText = document.getElementById('status-text');
  const canvas = document.getElementById('audio-visualizer');
  const canvasCtx = canvas.getContext('2d');
  const visualizerOverlay = document.getElementById('visualizer-overlay');
  
  const micSelect = document.getElementById('mic-select');
  const volumeSlider = document.getElementById('volume-slider');
  const volumeVal = document.getElementById('volume-val');
  const silenceSlider = document.getElementById('silence-slider');
  const silenceVal = document.getElementById('silence-val');
  const echoTargetGroup = document.getElementById('echo-target-group');
  const echoTargetCheckbox = document.getElementById('echo-target-checkbox');
  const vadSilenceGroup = document.getElementById('vad-silence-group');

  const sourceTranscriptContainer = document.getElementById('source-transcript-container');
  const sourceEmptyState = document.getElementById('source-empty-state');
  const transcriptContainer = document.getElementById('transcript-container');
  const emptyState = document.getElementById('empty-state');

  const clearBtn = document.getElementById('clear-btn');
  const exportJsonBtn = document.getElementById('export-json-btn');
  const exportTxtBtn = document.getElementById('export-txt-btn');

  // Application State
  let currentMode = 'audio';
  let activeTranslationMode = 'simultaneous';
  let isRunning = false;
  let geminiLiveClient = null;
  let audioStreamer = null;
  let audioPlayer = null;

  let transcriptEntries = [];
  let currentTranslationText = '';
  let currentTranslationElement = null;
  let currentSourceText = '';
  let currentSourceElement = null;

  // Banner Dismissal
  if (dismissBannerBtn && headphoneBanner) {
    dismissBannerBtn.addEventListener('click', () => {
      headphoneBanner.style.display = 'none';
    });
  }

  // Translation Mode Change Handler
  function updateEngineModeUI() {
    const mode = translationModeSelect ? translationModeSelect.value : 'simultaneous';
    if (mode === 'simultaneous') {
      if (vadSilenceGroup) vadSilenceGroup.style.display = 'none';
      if (echoTargetGroup) echoTargetGroup.style.display = 'block';
    } else {
      if (vadSilenceGroup) vadSilenceGroup.style.display = 'block';
      if (echoTargetGroup) echoTargetGroup.style.display = 'none';
    }
  }

  if (translationModeSelect) {
    translationModeSelect.addEventListener('change', updateEngineModeUI);
    updateEngineModeUI();
  }

  // Populate Microphones
  async function populateMicrophones() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = devices.filter(d => d.kind === 'audioinput');
      if (micSelect && audioInputs.length > 0) {
        micSelect.innerHTML = '<option value="">Default Microphone</option>';
        audioInputs.forEach((dev, idx) => {
          const opt = document.createElement('option');
          opt.value = dev.deviceId;
          opt.textContent = dev.label || `Microphone ${idx + 1}`;
          micSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn("Could not enumerate audio devices:", e);
    }
  }
  populateMicrophones();

  // Volume Slider
  if (volumeSlider) {
    volumeSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      if (volumeVal) volumeVal.textContent = `${Math.round(val * 100)}%`;
      if (audioPlayer) audioPlayer.setVolume(val);
    });
  }

  // Silence Threshold Slider
  if (silenceSlider) {
    silenceSlider.addEventListener('input', (e) => {
      if (silenceVal) silenceVal.textContent = `${e.target.value}ms`;
    });
  }

  // Initialize Audio Player
  audioPlayer = new AudioPlayer();

  // Mode Selection Handlers
  modeAudioBtn.addEventListener('click', () => setOutputMode('audio'));
  modeTextBtn.addEventListener('click', () => setOutputMode('text'));

  function setOutputMode(mode) {
    if (isRunning) return;
    currentMode = mode;
    if (mode === 'audio') {
      modeAudioBtn.classList.add('active');
      modeTextBtn.classList.remove('active');
    } else {
      modeTextBtn.classList.add('active');
      modeAudioBtn.classList.remove('active');
    }
  }

  // Toggle Start / Stop
  toggleBtn.addEventListener('click', async () => {
    if (isRunning) {
      stopTranslation();
    } else {
      await startTranslation();
    }
  });

  async function startTranslation() {
    updateStatus('connecting', 'Minting token...');
    try {
      // Pre-initialize Audio Context on user gesture
      if (audioPlayer) {
        await audioPlayer.init();
      }

      const targetLang = targetLanguageSelect.value;
      const sourceLang = sourceLanguageSelect ? sourceLanguageSelect.value : null;
      const trMode = translationModeSelect ? translationModeSelect.value : 'simultaneous';
      const echoTarget = echoTargetCheckbox ? echoTargetCheckbox.checked : false;
      const silenceDuration = silenceSlider ? parseInt(silenceSlider.value, 10) : 600;

      // Step 1: Request Ephemeral Token from backend
      const tokenResp = await fetch('/api/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_language: targetLang,
          mode: currentMode,
          source_language: sourceLang,
          translation_mode: trMode,
          echo_target_language: echoTarget,
          silence_duration_ms: silenceDuration
        })
      });

      if (!tokenResp.ok) {
        const errJson = await tokenResp.json().catch(() => ({ detail: tokenResp.statusText }));
        throw new Error(errJson.detail || 'Failed to mint ephemeral token');
      }

      const tokenData = await tokenResp.json();
      console.log("Token minted successfully.");
      activeTranslationMode = tokenData.translation_mode || trMode;

      updateStatus('connecting', 'Connecting Gemini WS...');

      // Step 2: Direct WebSocket connection to Gemini API
      geminiLiveClient = new GeminiLiveClient({
        wsEndpoint: tokenData.ws_endpoint,
        setupPayload: { setup: tokenData.setup },
        tokenExpiresAt: tokenData.expires_at,
        onEvent: handleGeminiEvent,
        onError: (err) => {
          console.error("Gemini Live Client error:", err);
          updateStatus('error', 'Connection Error');
        },
        onClose: () => {
          if (isRunning) {
            updateStatus('idle', 'Disconnected');
            stopTranslation();
          }
        }
      });

      // Connect and wait for SETUP_COMPLETE
      await geminiLiveClient.connect();
      console.log("Gemini Live Client setup complete!");

      // Step 3: Start microphone audio capture worklet
      audioStreamer = new AudioStreamer(
        (pcmBase64) => {
          if (geminiLiveClient) {
            geminiLiveClient.sendAudio(pcmBase64);
          }
        },
        (analyserData) => {
          drawVisualizer(analyserData);
        }
      );

      const selectedMic = micSelect ? micSelect.value : null;
      await audioStreamer.start(selectedMic);

      isRunning = true;
      updateUIForRunningState(true);
      updateStatus('live', activeTranslationMode === 'simultaneous' ? 'Live Translate' : 'Turn-based Translate');
    } catch (err) {
      console.error("Failed to start translation:", err);
      alert(`Error starting translation: ${err.message}`);
      updateStatus('error', 'Connection Error');
      stopTranslation();
    }
  }

  function stopTranslation() {
    isRunning = false;
    updateUIForRunningState(false);
    updateStatus('idle', 'Ready');

    if (audioStreamer) {
      audioStreamer.stop();
      audioStreamer = null;
    }

    if (geminiLiveClient) {
      geminiLiveClient.disconnect();
      geminiLiveClient = null;
    }

    if (audioPlayer) {
      audioPlayer.stop();
    }

    clearVisualizer();
    finalizeCurrentTurn();
  }

  function handleGeminiEvent(ev) {
    if (ev.type === 'text') {
      appendTranslationText(ev.text);
    } else if (ev.type === 'source_text') {
      appendSourceText(ev.text);
    } else if (ev.type === 'audio') {
      if (currentMode === 'audio' && audioPlayer) {
        audioPlayer.playChunk(ev.data);
      }
    } else if (ev.type === 'interrupted') {
      if (activeTranslationMode === 'turn_based' && audioPlayer) {
        audioPlayer.clear();
      }
    } else if (ev.type === 'turn_complete') {
      if (activeTranslationMode === 'turn_based') {
        finalizeCurrentTurn();
      }
    } else if (ev.type === 'token_expiring_soon') {
      console.warn("Ephemeral token expiring soon.");
    }
  }

  // Translation Transcript
  function appendTranslationText(textChunk) {
    if (emptyState) emptyState.style.display = 'none';

    if (!currentTranslationElement) {
      const timeFormatted = new Date().toLocaleTimeString();
      currentTranslationElement = document.createElement('div');
      currentTranslationElement.className = 'transcript-entry';

      const meta = document.createElement('div');
      meta.className = 'entry-meta';
      meta.innerHTML = `<span>Translation &bull; ${targetLanguageSelect.value}</span><span>${timeFormatted}</span>`;

      const textDiv = document.createElement('div');
      textDiv.className = 'entry-text';
      textDiv.textContent = '';

      currentTranslationElement.appendChild(meta);
      currentTranslationElement.appendChild(textDiv);
      transcriptContainer.appendChild(currentTranslationElement);
    }

    const textDiv = currentTranslationElement.querySelector('.entry-text');
    currentTranslationText += textChunk;
    textDiv.textContent = currentTranslationText;
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
  }

  // Source Speech Transcript
  function appendSourceText(textChunk) {
    if (sourceEmptyState) sourceEmptyState.style.display = 'none';

    if (!currentSourceElement) {
      const timeFormatted = new Date().toLocaleTimeString();
      currentSourceElement = document.createElement('div');
      currentSourceElement.className = 'transcript-entry entry-source';

      const meta = document.createElement('div');
      meta.className = 'entry-meta';
      meta.innerHTML = `<span>Original Speech</span><span>${timeFormatted}</span>`;

      const textDiv = document.createElement('div');
      textDiv.className = 'entry-text';
      textDiv.textContent = '';

      currentSourceElement.appendChild(meta);
      currentSourceElement.appendChild(textDiv);
      sourceTranscriptContainer.appendChild(currentSourceElement);
    }

    const textDiv = currentSourceElement.querySelector('.entry-text');
    currentSourceText += textChunk;
    textDiv.textContent = currentSourceText;
    sourceTranscriptContainer.scrollTop = sourceTranscriptContainer.scrollHeight;
  }

  function finalizeCurrentTurn() {
    if (currentTranslationText.trim().length > 0 || currentSourceText.trim().length > 0) {
      const now = new Date();
      transcriptEntries.push({
        timestamp: now.toISOString(),
        timeFormatted: now.toLocaleTimeString(),
        targetLanguage: targetLanguageSelect.value,
        sourceText: currentSourceText.trim(),
        translationText: currentTranslationText.trim()
      });
    }
    currentTranslationText = '';
    currentTranslationElement = null;
    currentSourceText = '';
    currentSourceElement = null;
  }

  // Clear Transcript
  clearBtn.addEventListener('click', () => {
    transcriptEntries = [];
    currentTranslationText = '';
    currentTranslationElement = null;
    currentSourceText = '';
    currentSourceElement = null;

    transcriptContainer.innerHTML = '';
    transcriptContainer.appendChild(emptyState);
    emptyState.style.display = 'block';

    sourceTranscriptContainer.innerHTML = '';
    sourceTranscriptContainer.appendChild(sourceEmptyState);
    sourceEmptyState.style.display = 'block';
  });

  // Export JSON Transcript
  exportJsonBtn.addEventListener('click', () => {
    finalizeCurrentTurn();
    if (transcriptEntries.length === 0) {
      alert('No transcript entries to save.');
      return;
    }
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(transcriptEntries, null, 2));
    downloadFile(dataStr, `translation_transcript_${Date.now()}.json`);
  });

  // Export Markdown Transcript
  exportTxtBtn.addEventListener('click', () => {
    finalizeCurrentTurn();
    if (transcriptEntries.length === 0) {
      alert('No transcript entries to save.');
      return;
    }
    let mdContent = `# Live Translation Transcript\n\n`;
    mdContent += `**Date:** ${new Date().toLocaleString()}\n`;
    mdContent += `**Target Language:** ${targetLanguageSelect.value}\n\n---\n\n`;

    transcriptEntries.forEach((entry) => {
      mdContent += `### [${entry.timeFormatted}]\n`;
      if (entry.sourceText) mdContent += `**Original Speech:** ${entry.sourceText}\n\n`;
      if (entry.translationText) mdContent += `**Translation (${entry.targetLanguage}):** ${entry.translationText}\n\n`;
      mdContent += `---\n\n`;
    });

    const dataStr = "data:text/markdown;charset=utf-8," + encodeURIComponent(mdContent);
    downloadFile(dataStr, `translation_transcript_${Date.now()}.md`);
  });

  function downloadFile(dataUri, fileName) {
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataUri);
    downloadAnchor.setAttribute("download", fileName);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  }

  // Visualizer Rendering
  function drawVisualizer(dataArray) {
    if (visualizerOverlay) visualizerOverlay.classList.add('hidden');
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);

    const barWidth = (canvas.width / dataArray.length) * 2.5;
    let x = 0;

    for (let i = 0; i < dataArray.length; i++) {
      const barHeight = (dataArray[i] / 255) * canvas.height;
      const gradient = canvasCtx.createLinearGradient(0, canvas.height, 0, 0);
      gradient.addColorStop(0, '#00f2fe');
      gradient.addColorStop(1, '#4facfe');

      canvasCtx.fillStyle = gradient;
      canvasCtx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
      x += barWidth + 1;
    }
  }

  function clearVisualizer() {
    if (visualizerOverlay) visualizerOverlay.classList.remove('hidden');
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
  }

  // UI Helpers
  function updateUIForRunningState(running) {
    if (running) {
      toggleBtn.classList.remove('start-btn');
      toggleBtn.classList.add('stop-btn');
      toggleBtn.innerHTML = `
        <span class="btn-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12"/>
          </svg>
        </span>
        <span>Stop Translation</span>
      `;
      if (translationModeSelect) translationModeSelect.disabled = true;
      targetLanguageSelect.disabled = true;
      if (sourceLanguageSelect) sourceLanguageSelect.disabled = true;
      if (silenceSlider) silenceSlider.disabled = true;
      if (echoTargetCheckbox) echoTargetCheckbox.disabled = true;
      modeAudioBtn.disabled = true;
      modeTextBtn.disabled = true;
    } else {
      toggleBtn.classList.remove('stop-btn');
      toggleBtn.classList.add('start-btn');
      toggleBtn.innerHTML = `
        <span class="btn-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5,3 19,12 5,21"/>
          </svg>
        </span>
        <span>Start Translation</span>
      `;
      if (translationModeSelect) translationModeSelect.disabled = false;
      targetLanguageSelect.disabled = false;
      if (sourceLanguageSelect) sourceLanguageSelect.disabled = false;
      if (silenceSlider) silenceSlider.disabled = false;
      if (echoTargetCheckbox) echoTargetCheckbox.disabled = false;
      modeAudioBtn.disabled = false;
      modeTextBtn.disabled = false;
    }
  }

  function updateStatus(state, text) {
    statusIndicator.className = `status-badge status-${state}`;
    statusText.textContent = text;
  }
});
