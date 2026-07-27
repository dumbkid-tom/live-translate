document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const targetLanguageSelect = document.getElementById('target-language');
  const modeAudioBtn = document.getElementById('mode-audio');
  const modeTextBtn = document.getElementById('mode-text');
  const toggleBtn = document.getElementById('toggle-btn');
  const statusIndicator = document.getElementById('status-indicator');
  const statusText = document.getElementById('status-text');
  const canvas = document.getElementById('audio-visualizer');
  const canvasCtx = canvas.getContext('2d');
  const visualizerOverlay = document.getElementById('visualizer-overlay');
  const transcriptContainer = document.getElementById('transcript-container');
  const emptyState = document.getElementById('empty-state');
  const clearBtn = document.getElementById('clear-btn');
  const exportJsonBtn = document.getElementById('export-json-btn');
  const exportTxtBtn = document.getElementById('export-txt-btn');

  // Application State
  let currentMode = 'audio'; // 'audio' or 'text'
  let isRunning = false;
  let ws = null;
  let audioRecorder = null;
  let audioPlayer = null;
  let transcriptEntries = [];
  let currentTurnText = '';
  let currentTurnElement = null;

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
    updateStatus('connecting', 'Connecting...');
    try {
      const targetLang = targetLanguageSelect.value;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/translate?target_language=${encodeURIComponent(targetLang)}&mode=${currentMode}`;

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("WebSocket connected to backend proxy.");
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        updateStatus('error', 'Connection Error');
        stopTranslation();
      };

      ws.onclose = () => {
        if (isRunning) {
          updateStatus('idle', 'Disconnected');
          stopTranslation();
        }
      };

      // Start Audio Recorder
      audioRecorder = new AudioRecorder(
        (pcmBase64) => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: 'audio_chunk',
              data: pcmBase64
            }));
          }
        },
        (analyserData) => {
          drawVisualizer(analyserData);
        }
      );

      await audioRecorder.start();

      isRunning = true;
      updateUIForRunningState(true);
      updateStatus('live', 'Live Translating');
    } catch (err) {
      console.error("Failed to start translation:", err);
      updateStatus('error', 'Mic / Connection Error');
      stopTranslation();
    }
  }

  function stopTranslation() {
    isRunning = false;
    updateUIForRunningState(false);
    updateStatus('idle', 'Ready');

    if (audioRecorder) {
      audioRecorder.stop();
      audioRecorder = null;
    }

    if (ws) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'stop' }));
        ws.close();
      }
      ws = null;
    }

    if (audioPlayer) {
      audioPlayer.stop();
    }

    clearVisualizer();
    finalizeCurrentTurn();
  }

  function handleServerMessage(msg) {
    if (msg.type === 'connected') {
      console.log(`Connected to Gemini Live API (${msg.model}).`);
    } else if (msg.type === 'text') {
      appendTranscriptText(msg.text);
    } else if (msg.type === 'audio') {
      if (currentMode === 'audio' && audioPlayer) {
        audioPlayer.playChunk(msg.data);
      }
    } else if (msg.type === 'interrupted') {
      if (audioPlayer) {
        audioPlayer.clear();
      }
    } else if (msg.type === 'turn_complete') {
      finalizeCurrentTurn();
    } else if (msg.type === 'error') {
      alert(`Server Error: ${msg.message}`);
      stopTranslation();
    }
  }

  // Transcript Management
  function appendTranscriptText(textChunk) {
    if (emptyState) {
      emptyState.style.display = 'none';
    }

    if (!currentTurnElement) {
      const now = new Date();
      const timeFormatted = now.toLocaleTimeString();

      currentTurnElement = document.createElement('div');
      currentTurnElement.className = 'transcript-entry';
      
      const meta = document.createElement('div');
      meta.className = 'entry-meta';
      meta.innerHTML = `<span>Translator &bull; ${targetLanguageSelect.value}</span><span>${timeFormatted}</span>`;
      
      const textDiv = document.createElement('div');
      textDiv.className = 'entry-text';
      textDiv.textContent = '';
      
      currentTurnElement.appendChild(meta);
      currentTurnElement.appendChild(textDiv);
      transcriptContainer.appendChild(currentTurnElement);
    }

    const textDiv = currentTurnElement.querySelector('.entry-text');
    currentTurnText += textChunk;
    textDiv.textContent = currentTurnText;
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
  }

  function finalizeCurrentTurn() {
    if (currentTurnText.trim().length > 0) {
      const now = new Date();
      transcriptEntries.push({
        timestamp: now.toISOString(),
        timeFormatted: now.toLocaleTimeString(),
        targetLanguage: targetLanguageSelect.value,
        mode: currentMode,
        text: currentTurnText.trim()
      });
    }
    currentTurnText = '';
    currentTurnElement = null;
  }

  // Clear Transcript
  clearBtn.addEventListener('click', () => {
    transcriptEntries = [];
    currentTurnText = '';
    currentTurnElement = null;
    transcriptContainer.innerHTML = '';
    transcriptContainer.appendChild(emptyState);
    emptyState.style.display = 'flex';
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

    transcriptEntries.forEach((entry, idx) => {
      mdContent += `### [${entry.timeFormatted}] ${entry.targetLanguage}\n${entry.text}\n\n`;
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
    visualizerOverlay.classList.add('hidden');
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
    visualizerOverlay.classList.remove('hidden');
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
      targetLanguageSelect.disabled = true;
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
      targetLanguageSelect.disabled = false;
      modeAudioBtn.disabled = false;
      modeTextBtn.disabled = false;
    }
  }

  function updateStatus(state, text) {
    statusIndicator.className = `status-badge status-${state}`;
    statusText.textContent = text;
  }
});
