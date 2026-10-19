// Video Helper Studio - Frontend Client Logic

let audioClips = [];
let currentPlayingPath = null;
let activeAudioObj = null;
let lastStitchedResult = null;

// DOM Elements
const docRoot = document.documentElement;
const themeToggleBtn = document.getElementById('themeToggleBtn');
const themeText = document.getElementById('themeText');
const dropzone = document.getElementById('dropzone');
const clipsList = document.getElementById('clipsList');
const addFilesBtn = document.getElementById('addFilesBtn');
const clearAllBtn = document.getElementById('clearAllBtn');
const sortNaturalBtn = document.getElementById('sortNaturalBtn');
const statClipCount = document.getElementById('statClipCount');
const statTotalDuration = document.getElementById('statTotalDuration');
const htmlAudioInput = document.getElementById('htmlAudioInput');

// Settings Elements
const gapSlider = document.getElementById('gapSlider');
const gapDisplay = document.getElementById('gapDisplay');
const gapChips = document.querySelectorAll('.chip[data-gap]');
const normalizeCheckbox = document.getElementById('normalizeAudio');
const formatRadios = document.querySelectorAll('input[name="outFormat"]');
const sampleRateSelect = document.getElementById('sampleRateSelect');
const outputPathInput = document.getElementById('outputPathInput');
const browseDestBtn = document.getElementById('browseDestBtn');
const startStitchBtn = document.getElementById('startStitchBtn');

// Progress & Success Cards
const progressCard = document.getElementById('progressCard');
const progressStatusText = document.getElementById('progressStatusText');
const progressPercent = document.getElementById('progressPercent');
const progressBarFill = document.getElementById('progressBarFill');
const cancelStitchBtn = document.getElementById('cancelStitchBtn');

const successCard = document.getElementById('successCard');
const successDetails = document.getElementById('successDetails');
const masterAudioPlayer = document.getElementById('masterAudioPlayer');
const openFolderBtn = document.getElementById('openFolderBtn');
const dismissSuccessBtn = document.getElementById('dismissSuccessBtn');
const gpuLabel = document.getElementById('gpuLabel');

// Splash Elements
const splashScreen = document.getElementById('splashScreen');
const splashFill = document.getElementById('splashFill');
const splashStatusText = document.getElementById('splashStatusText');

// Global Client Error Logger to debug_log.txt
function sendClientLog(level, message) {
  try {
    fetch('/client_log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: level, message: message })
    }).catch(() => {});
  } catch (e) {}
}

window.onerror = function(msg, url, lineNo, columnNo, error) {
  const errStr = `${msg} at ${url}:${lineNo}:${columnNo} - ${error ? error.stack : ''}`;
  console.error(errStr);
  sendClientLog('error', errStr);
  return false;
};

window.onunhandledrejection = function(event) {
  const reason = event.reason ? (event.reason.stack || event.reason) : 'Unknown rejection';
  console.error('Unhandled Promise Rejection:', reason);
  sendClientLog('error', 'Unhandled Promise Rejection: ' + reason);
};

// =============================================================================
// 1. THEME MANAGEMENT
// =============================================================================
function initTheme() {
  const savedTheme = localStorage.getItem('vh_theme') || 'dark';
  applyTheme(savedTheme);

  themeToggleBtn.addEventListener('click', () => {
    const current = docRoot.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  });
}

function applyTheme(theme) {
  docRoot.setAttribute('data-theme', theme);
  localStorage.setItem('vh_theme', theme);
  themeText.textContent = theme === 'dark' ? 'Dark Obsidian' : 'Crisp Light';
}

// =============================================================================
// 2. INITIALIZATION & HARDWARE DETECTION (OpenVox Style Splash Loading)
// =============================================================================
window.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initSettings();
  setupEventListeners();
  initSilenceRemover();
  initTimelineAligner();
  initAppLoadingSequence();
});

async function initAppLoadingSequence() {
  function updateSplash(percent, text) {
    if (splashFill) splashFill.style.width = `${percent}%`;
    if (splashStatusText) splashStatusText.textContent = text;
  }

  updateSplash(20, "Connecting to local backend engines...");

  let initialized = false;

  async function checkBackend() {
    if (initialized) return;

    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.initialize_app === 'function') {
      try {
        updateSplash(50, "Verifying FFmpeg hardware acceleration...");
        const res = await window.pywebview.api.initialize_app();
        
        updateSplash(80, "Checking NVIDIA RTX 3060 12GB NVENC...");
        if (res && res.gpu) {
          gpuLabel.textContent = `${res.gpu} • Ready`;
        }

        await new Promise(r => setTimeout(r, 300));
        updateSplash(100, "Hardware Acceleration Ready!");

        await new Promise(r => setTimeout(r, 400));
        dismissSplashScreen();
        suggestDefaultOutputPath();
        initialized = true;
        return;
      } catch (err) {
        console.error("Initialization error:", err);
      }
    }

    if (!initialized) {
      setTimeout(checkBackend, 100);
    }
  }

  window.addEventListener('pywebviewready', () => {
    checkBackend();
  });

  checkBackend();
}

function dismissSplashScreen() {
  if (splashScreen && !splashScreen.classList.contains('fade-out')) {
    splashScreen.classList.add('fade-out');
    setTimeout(() => {
      splashScreen.style.display = 'none';
    }, 550);
  }
}

function suggestDefaultOutputPath() {
  const fmt = getSelectedFormat();
  const timestamp = new Date().toISOString().slice(0, 10);
  const defaultPath = `master_audio_${timestamp}.${fmt}`;
  if (!outputPathInput.value) {
    outputPathInput.value = defaultPath;
  }
}

// =============================================================================
// 3. SETTINGS & PARAMETERS
// =============================================================================
function initSettings() {
  // Gap slider & chips sync
  gapSlider.addEventListener('input', (e) => {
    updateGapValue(parseFloat(e.target.value));
  });

  gapChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const val = parseFloat(chip.getAttribute('data-gap'));
      gapSlider.value = val;
      updateGapValue(val);
    });
  });

  // Format selection
  formatRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      document.querySelectorAll('.radio-card').forEach(c => c.classList.remove('active'));
      radio.closest('.radio-card').classList.add('active');
      updateOutputPathExtension(radio.value);
    });
  });

  // Browse output destination
  browseDestBtn.addEventListener('click', async () => {
    sendClientLog('info', 'User clicked Browse Destination');
    if (!window.pywebview || !window.pywebview.api) {
      sendClientLog('warn', 'pywebview API not ready yet for browse destination');
      return;
    }
    const currentName = outputPathInput.value.split(/[\\/]/).pop() || "master_audio.mp3";
    try {
      const selected = await window.pywebview.api.select_save_destination(currentName);
      if (selected) {
        outputPathInput.value = selected;
        sendClientLog('info', `Destination selected: ${selected}`);
      }
    } catch (err) {
      sendClientLog('error', `Error in select_save_destination: ${err}`);
      alert("Could not open save dialog: " + err);
    }
  });
}

function updateGapValue(val) {
  gapDisplay.textContent = `${val.toFixed(2)}s`;
  gapChips.forEach(chip => {
    const chipVal = parseFloat(chip.getAttribute('data-gap'));
    if (Math.abs(chipVal - val) < 0.04) {
      chip.classList.add('active');
    } else {
      chip.classList.remove('active');
    }
  });
  updateStats();
}

function getSelectedFormat() {
  const checked = document.querySelector('input[name="outFormat"]:checked');
  return checked ? checked.value : 'mp3';
}

function updateOutputPathExtension(ext) {
  let cur = outputPathInput.value;
  if (cur) {
    const dotIdx = cur.lastIndexOf('.');
    if (dotIdx !== -1) {
      outputPathInput.value = cur.substring(0, dotIdx + 1) + ext;
    } else {
      outputPathInput.value = cur + '.' + ext;
    }
  }
}

// =============================================================================
// 4. CLIP LIST MANAGEMENT & RENDERING
// =============================================================================
function setupEventListeners() {
  // Prevent browser default file open behavior across the whole window
  window.addEventListener('dragover', (e) => e.preventDefault(), false);
  window.addEventListener('drop', (e) => e.preventDefault(), false);

  // Sidebar navigation tab switcher
  document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('disabled')) return;
      const tab = btn.getAttribute('data-tab');
      switchTab(tab);
    });
  });

  // File add triggers
  addFilesBtn.addEventListener('click', openAddFilesDialog);
  dropzone.addEventListener('click', openAddFilesDialog);

  // HTML File Input fallback listener
  if (htmlAudioInput) {
    htmlAudioInput.addEventListener('change', async (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        await uploadFilesToServer(files);
        htmlAudioInput.value = ''; // Reset so the same file can be selected again
      }
    });
  }

  // Clear all
  clearAllBtn.addEventListener('click', () => {
    if (audioClips.length === 0) return;
    if (confirm("Remove all clips from the stitcher list?")) {
      stopPlayback();
      audioClips = [];
      renderClips();
    }
  });

  // Natural Sort
  sortNaturalBtn.addEventListener('click', () => {
    if (audioClips.length <= 1) return;
    const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
    audioClips.sort((a, b) => collator.compare(a.filename, b.filename));
    renderClips();
  });

  // Drag and drop onto dropzone
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('drag-over');
    });
  });

  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;

    // Check if files contain a direct filesystem path (pywebview / desktop environment)
    const paths = [];
    for (let i = 0; i < files.length; i++) {
      if (files[i].path) {
        paths.push(files[i].path);
      }
    }

    if (paths.length > 0 && window.pywebview && window.pywebview.api) {
      try {
        const metadataList = await window.pywebview.api.inspect_dropped_files(paths);
        appendClips(metadataList);
        return;
      } catch (err) {
        console.warn("inspect_dropped_files failed, falling back to upload:", err);
      }
    }

    // Standard web Drag & Drop (WebView2 security hides absolute path) -> Upload directly
    await uploadFilesToServer(files);
  });

  // Start stitch
  startStitchBtn.addEventListener('click', executeStitch);

  // Cancel stitch
  cancelStitchBtn.addEventListener('click', async () => {
    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.cancel_stitch();
    }
  });

  // Success actions
  openFolderBtn.addEventListener('click', async () => {
    if (lastStitchedResult && window.pywebview && window.pywebview.api) {
      await window.pywebview.api.open_folder(lastStitchedResult.path);
    }
  });

  const sendToSilenceBtn = document.getElementById('sendToSilenceBtn');
  if (sendToSilenceBtn) {
    sendToSilenceBtn.addEventListener('click', () => {
      if (!lastStitchedResult) return;
      setSilenceActiveFile(lastStitchedResult);
      switchTab('silence');
      successCard.style.display = 'none';
      if (masterAudioPlayer) {
        masterAudioPlayer.pause();
      }
    });
  }

  const sendStitchToTimelineBtn = document.getElementById('sendStitchToTimelineBtn');
  if (sendStitchToTimelineBtn) {
    sendStitchToTimelineBtn.addEventListener('click', () => {
      if (!lastStitchedResult) return;
      setTimelineActiveAudio(lastStitchedResult);
      switchTab('timeline');
      successCard.style.display = 'none';
      if (masterAudioPlayer) {
        masterAudioPlayer.pause();
      }
    });
  }

  dismissSuccessBtn.addEventListener('click', () => {
    successCard.style.display = 'none';
    if (masterAudioPlayer) {
      masterAudioPlayer.pause();
    }
  });
}

async function openAddFilesDialog() {
  sendClientLog("info", "User triggered Add Audio Clips / Dropzone click");
  if (htmlAudioInput) {
    htmlAudioInput.click();
  }
}

async function uploadFilesToServer(files) {
  const formData = new FormData();
  let validCount = 0;
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    formData.append('audio_files', f, f.name);
    validCount++;
  }

  if (validCount === 0) return;

  const prevText = dropzone.querySelector('h3').textContent;
  dropzone.querySelector('h3').textContent = `Importing ${validCount} audio file(s)...`;

  try {
    const response = await fetch('/upload_audio', {
      method: 'POST',
      body: formData
    });
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (parseErr) {
      throw new Error(`Server status ${response.status}: ${text.slice(0, 150)}`);
    }
    if (data.success && data.clips && data.clips.length > 0) {
      appendClips(data.clips);
    } else if (data.error) {
      alert("Error importing files: " + data.error);
    }
  } catch (err) {
    console.error("Upload error:", err);
    alert("Could not import audio files:\n" + err.message);
  } finally {
    dropzone.querySelector('h3').textContent = prevText;
  }
}

function appendClips(newClips) {
  newClips.forEach(clip => {
    if (!clip.error) {
      audioClips.push(clip);
    }
  });
  renderClips();
}

function renderClips() {
  if (audioClips.length === 0) {
    dropzone.style.display = 'block';
    clipsList.style.display = 'none';
    clipsList.innerHTML = '';
  } else {
    dropzone.style.display = 'none';
    clipsList.style.display = 'flex';
    clipsList.innerHTML = '';

    audioClips.forEach((clip, index) => {
      const card = createClipCard(clip, index);
      clipsList.appendChild(card);
    });
  }

  updateStats();
}

function createClipCard(clip, index) {
  const card = document.createElement('div');
  card.className = 'clip-card';
  card.draggable = true;
  card.dataset.index = index;

  const isPlaying = (currentPlayingPath === clip.path);

  card.innerHTML = `
    <div class="drag-handle" title="Drag to reorder sequence">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
        <circle cx="9" cy="6" r="1"></circle>
        <circle cx="15" cy="6" r="1"></circle>
        <circle cx="9" cy="12" r="1"></circle>
        <circle cx="15" cy="12" r="1"></circle>
        <circle cx="9" cy="18" r="1"></circle>
        <circle cx="15" cy="18" r="1"></circle>
      </svg>
    </div>
    <div class="clip-index-badge">#${index + 1}</div>
    <div class="clip-info">
      <div class="clip-name" title="${clip.path}">${clip.filename}</div>
      <div class="clip-meta-row">
        <span class="meta-pill">${clip.format_name}</span>
        <span class="meta-pill">${clip.duration_formatted}</span>
        <span class="meta-pill">${(clip.sample_rate / 1000).toFixed(1)} kHz</span>
        <span class="meta-pill">${clip.size_formatted}</span>
      </div>
    </div>
    <div class="clip-controls">
      <button class="clip-play-btn" data-action="play" data-index="${index}" title="${isPlaying ? 'Pause' : 'Play Preview'}">
        ${isPlaying ? `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="6" y="4" width="4" height="16"></rect>
            <rect x="14" y="4" width="4" height="16"></rect>
          </svg>
        ` : `
          <svg viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
        `}
      </button>
      <button class="clip-order-btn" data-action="up" data-index="${index}" title="Move Up" ${index === 0 ? 'disabled style="opacity:0.3"' : ''}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="18 15 12 9 6 15"></polyline>
        </svg>
      </button>
      <button class="clip-order-btn" data-action="down" data-index="${index}" title="Move Down" ${index === audioClips.length - 1 ? 'disabled style="opacity:0.3"' : ''}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
      <button class="clip-del-btn" data-action="delete" data-index="${index}" title="Remove Clip">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>
  `;

  // Attach button events
  card.querySelector('[data-action="play"]').addEventListener('click', (e) => {
    e.stopPropagation();
    togglePlayClip(clip);
  });

  const upBtn = card.querySelector('[data-action="up"]');
  if (upBtn) {
    upBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      moveClip(index, index - 1);
    });
  }

  const downBtn = card.querySelector('[data-action="down"]');
  if (downBtn) {
    downBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      moveClip(index, index + 1);
    });
  }

  card.querySelector('[data-action="delete"]').addEventListener('click', (e) => {
    e.stopPropagation();
    removeClip(index);
  });

  // Drag to reorder
  setupDragReordering(card, index);

  return card;
}

function moveClip(fromIdx, toIdx) {
  if (toIdx < 0 || toIdx >= audioClips.length) return;
  const item = audioClips.splice(fromIdx, 1)[0];
  audioClips.splice(toIdx, 0, item);
  renderClips();
}

function removeClip(idx) {
  if (idx < 0 || idx >= audioClips.length) return;
  if (currentPlayingPath === audioClips[idx].path) {
    stopPlayback();
  }
  audioClips.splice(idx, 1);
  renderClips();
}

// Drag & Drop reordering between cards
let draggedCardIndex = null;

function setupDragReordering(card, index) {
  card.addEventListener('dragstart', (e) => {
    draggedCardIndex = index;
    card.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  });

  card.addEventListener('dragend', () => {
    card.classList.remove('dragging');
    draggedCardIndex = null;
  });

  card.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  });

  card.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (draggedCardIndex !== null && draggedCardIndex !== index) {
      moveClip(draggedCardIndex, index);
    }
  });
}

// =============================================================================
// 5. AUDIO PLAYBACK PREVIEW
// =============================================================================
function togglePlayClip(clip) {
  if (currentPlayingPath === clip.path && activeAudioObj && !activeAudioObj.paused) {
    stopPlayback();
    renderClips();
    return;
  }

  stopPlayback();

  const streamUrl = `/stream_audio?path=${encodeURIComponent(clip.path)}`;
  activeAudioObj = new Audio(streamUrl);
  currentPlayingPath = clip.path;

  activeAudioObj.play().catch(err => {
    console.error("Playback error:", err);
    stopPlayback();
  });

  activeAudioObj.onended = () => {
    stopPlayback();
    renderClips();
  };

  renderClips();
}

function stopPlayback() {
  if (activeAudioObj) {
    activeAudioObj.pause();
    activeAudioObj = null;
  }
  currentPlayingPath = null;
}

// =============================================================================
// 6. STATS CALCULATION
// =============================================================================
function updateStats() {
  statClipCount.textContent = audioClips.length;

  if (audioClips.length === 0) {
    statTotalDuration.textContent = "00:00";
    return;
  }

  const gap = parseFloat(gapSlider.value) || 0;
  const clipDurations = audioClips.reduce((sum, c) => sum + (c.duration || 0), 0);
  const totalGaps = Math.max(0, audioClips.length - 1) * gap;
  const totalSec = Math.round(clipDurations + totalGaps);

  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  statTotalDuration.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// =============================================================================
// 7. STITCH EXECUTION & BACKGROUND CALLBACKS
// =============================================================================
async function executeStitch() {
  if (audioClips.length === 0) {
    alert("Please add at least one audio clip to stitch.");
    return;
  }

  let outPath = outputPathInput.value.trim();
  if (!outPath) {
    alert("Please specify an export destination file.");
    return;
  }

  // Ensure absolute path
  if (!outPath.includes(':') && !outPath.startsWith('/') && !outPath.startsWith('\\')) {
    outPath = `A:\\My Video Hwelper APP\\${outPath}`;
    outputPathInput.value = outPath;
  }

  stopPlayback();

  const filePaths = audioClips.map(c => c.path);
  const gapSec = parseFloat(gapSlider.value) || 0.0;
  const normalize = normalizeCheckbox.checked;
  const format = getSelectedFormat();
  const sampleRate = parseInt(sampleRateSelect.value, 10) || 48000;
  const bitrate = 320;

  // Show progress card
  progressCard.style.display = 'flex';
  successCard.style.display = 'none';
  startStitchBtn.disabled = true;
  progressBarFill.style.width = '5%';
  progressPercent.textContent = '5%';
  progressStatusText.textContent = "Initializing stitching pipeline...";

  try {
    await window.pywebview.api.start_stitch(
      filePaths,
      outPath,
      gapSec,
      normalize,
      sampleRate,
      format,
      bitrate
    );
  } catch (err) {
    alert("Error starting stitch: " + err);
    resetProgress();
  }
}

// Global callbacks evaluated from Python ApiBridge
window.onStitchProgress = function(percent, statusMsg) {
  progressBarFill.style.width = `${percent}%`;
  progressPercent.textContent = `${Math.round(percent)}%`;
  progressStatusText.textContent = statusMsg;
};

window.onStitchComplete = function(result) {
  resetProgress();
  lastStitchedResult = result;

  // Show success card
  successCard.style.display = 'block';
  successDetails.textContent = `Total: ${result.duration_formatted} • ${result.size_formatted} • ${result.filename}`;

  // Load preview in master player
  const streamUrl = `/stream_audio?path=${encodeURIComponent(result.path)}&t=${Date.now()}`;
  masterAudioPlayer.src = streamUrl;
  masterAudioPlayer.load();
};

window.onStitchCancelled = function() {
  resetProgress();
  alert("Audio stitching was cancelled.");
};

window.onStitchError = function(errMsg) {
  resetProgress();
  alert("Stitching Error:\n" + errMsg);
};

function resetProgress() {
  progressCard.style.display = 'none';
  startStitchBtn.disabled = false;
  progressBarFill.style.width = '0%';
  progressPercent.textContent = '0%';
}

// =============================================================================
// 8. TAB NAVIGATION
// =============================================================================
function switchTab(tabName) {
  document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
    if (btn.getAttribute('data-tab') === tabName) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  const stitcherView = document.getElementById('stitcherView');
  const silenceView = document.getElementById('silenceView');
  const timelineView = document.getElementById('timelineView');

  if (stitcherView) stitcherView.style.display = (tabName === 'stitcher') ? 'flex' : 'none';
  if (silenceView) silenceView.style.display = (tabName === 'silence') ? 'flex' : 'none';
  if (timelineView) timelineView.style.display = (tabName === 'timeline') ? 'flex' : 'none';
}

// =============================================================================
// 9. SILENCE REMOVER CONTROLLER
// =============================================================================
let silenceActiveFile = null;
let lastSilenceResult = null;

// DOM Elements
let silenceDropzone, silenceFileInput, silenceAudioCard, silenceFileName;
let silenceFileFmt, silenceFileDur, silenceFileSr, silenceFileSize;
let changeSilenceFileBtn, silenceOriginalPlayer;
let silenceCountStat, silenceSavedStat, silenceNewDurStat;
let silenceTelemetryCard, silenceBadgeStats, silenceListContainer;
let thresholdSlider, threshDisplay, threshChips;
let minDurationSlider, minDurDisplay, durChips;
let marginSlider, marginDisplay, marginChips;
let silenceNormalize, silenceFormatRadios, silenceOutputPathInput, browseSilenceDestBtn;
let analyzeSilencesBtn, startSilenceRemovalBtn;
let silenceProgressCard, silenceProgressStatusText, silenceProgressPercent, silenceProgressBarFill, cancelSilenceBtn;
let silenceSuccessCard, silenceSuccessDetails, silenceCleanPlayer;
let openSilenceFolderBtn, sendToStitcherBtn, dismissSilenceSuccessBtn;

function initSilenceRemover() {
  silenceDropzone = document.getElementById('silenceDropzone');
  silenceFileInput = document.getElementById('silenceFileInput');
  silenceAudioCard = document.getElementById('silenceAudioCard');
  silenceFileName = document.getElementById('silenceFileName');
  silenceFileFmt = document.getElementById('silenceFileFmt');
  silenceFileDur = document.getElementById('silenceFileDur');
  silenceFileSr = document.getElementById('silenceFileSr');
  silenceFileSize = document.getElementById('silenceFileSize');
  changeSilenceFileBtn = document.getElementById('changeSilenceFileBtn');
  silenceOriginalPlayer = document.getElementById('silenceOriginalPlayer');

  silenceCountStat = document.getElementById('silenceCountStat');
  silenceSavedStat = document.getElementById('silenceSavedStat');
  silenceNewDurStat = document.getElementById('silenceNewDurStat');

  silenceTelemetryCard = document.getElementById('silenceTelemetryCard');
  silenceBadgeStats = document.getElementById('silenceBadgeStats');
  silenceListContainer = document.getElementById('silenceListContainer');

  thresholdSlider = document.getElementById('thresholdSlider');
  threshDisplay = document.getElementById('threshDisplay');
  threshChips = document.querySelectorAll('.chip[data-thresh]');

  minDurationSlider = document.getElementById('minDurationSlider');
  minDurDisplay = document.getElementById('minDurDisplay');
  durChips = document.querySelectorAll('.chip[data-dur]');

  marginSlider = document.getElementById('marginSlider');
  marginDisplay = document.getElementById('marginDisplay');
  marginChips = document.querySelectorAll('.chip[data-margin]');

  silenceNormalize = document.getElementById('silenceNormalize');
  silenceFormatRadios = document.querySelectorAll('input[name="silenceFormat"]');
  silenceOutputPathInput = document.getElementById('silenceOutputPathInput');
  browseSilenceDestBtn = document.getElementById('browseSilenceDestBtn');

  analyzeSilencesBtn = document.getElementById('analyzeSilencesBtn');
  startSilenceRemovalBtn = document.getElementById('startSilenceRemovalBtn');

  silenceProgressCard = document.getElementById('silenceProgressCard');
  silenceProgressStatusText = document.getElementById('silenceProgressStatusText');
  silenceProgressPercent = document.getElementById('silenceProgressPercent');
  silenceProgressBarFill = document.getElementById('silenceProgressBarFill');
  cancelSilenceBtn = document.getElementById('cancelSilenceBtn');

  silenceSuccessCard = document.getElementById('silenceSuccessCard');
  silenceSuccessDetails = document.getElementById('silenceSuccessDetails');
  silenceCleanPlayer = document.getElementById('silenceCleanPlayer');
  openSilenceFolderBtn = document.getElementById('openSilenceFolderBtn');
  sendToStitcherBtn = document.getElementById('sendToStitcherBtn');
  dismissSilenceSuccessBtn = document.getElementById('dismissSilenceSuccessBtn');

  setupSilenceEventListeners();
}

function setupSilenceEventListeners() {
  if (!silenceDropzone) return;

  // Silence Dropzone
  silenceDropzone.addEventListener('click', () => silenceFileInput.click());
  changeSilenceFileBtn.addEventListener('click', () => silenceFileInput.click());

  silenceFileInput.addEventListener('change', async (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      await handleSilenceFiles(files);
      silenceFileInput.value = '';
    }
  });

  // Drag and drop for silence dropzone
  ['dragenter', 'dragover'].forEach(name => {
    silenceDropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      silenceDropzone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    silenceDropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      silenceDropzone.classList.remove('drag-over');
    });
  });

  silenceDropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      await handleSilenceFiles(files);
    }
  });

  // Slider controls: Threshold
  thresholdSlider.addEventListener('input', (e) => {
    updateSilenceThresh(parseFloat(e.target.value));
  });
  threshChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const val = parseFloat(chip.getAttribute('data-thresh'));
      thresholdSlider.value = val;
      updateSilenceThresh(val);
    });
  });

  // Slider controls: Min duration
  minDurationSlider.addEventListener('input', (e) => {
    updateSilenceMinDur(parseFloat(e.target.value));
  });
  durChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const val = parseFloat(chip.getAttribute('data-dur'));
      minDurationSlider.value = val;
      updateSilenceMinDur(val);
    });
  });

  // Slider controls: Margin
  marginSlider.addEventListener('input', (e) => {
    updateSilenceMargin(parseFloat(e.target.value));
  });
  marginChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const val = parseFloat(chip.getAttribute('data-margin'));
      marginSlider.value = val;
      updateSilenceMargin(val);
    });
  });

  // Format radios
  silenceFormatRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      document.querySelectorAll('#silenceView .radio-card').forEach(c => c.classList.remove('active'));
      radio.closest('.radio-card').classList.add('active');
      updateSilenceOutputPathExtension(radio.value);
    });
  });

  // Destination browse button
  browseSilenceDestBtn.addEventListener('click', async () => {
    if (!window.pywebview || !window.pywebview.api) return;
    const currentName = silenceOutputPathInput.value.split(/[\\/]/).pop() || "cleaned_voiceover.mp3";
    try {
      const selected = await window.pywebview.api.select_save_destination(currentName);
      if (selected) {
        silenceOutputPathInput.value = selected;
      }
    } catch (err) {
      alert("Could not select destination: " + err);
    }
  });

  // Analyze pauses button
  analyzeSilencesBtn.addEventListener('click', executeDetectSilences);

  // Cut silences button
  startSilenceRemovalBtn.addEventListener('click', executeRemoveSilences);

  // Cancel button
  cancelSilenceBtn.addEventListener('click', async () => {
    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.cancel_silence_removal();
    }
  });

  // Success card buttons
  openSilenceFolderBtn.addEventListener('click', async () => {
    if (lastSilenceResult && window.pywebview && window.pywebview.api) {
      await window.pywebview.api.open_folder(lastSilenceResult.path);
    }
  });

  sendToStitcherBtn.addEventListener('click', () => {
    if (!lastSilenceResult) return;
    audioClips.push(lastSilenceResult);
    renderClips();
    switchTab('stitcher');
    silenceSuccessCard.style.display = 'none';
    if (silenceCleanPlayer) silenceCleanPlayer.pause();
  });

  const sendSilenceToTimelineBtn = document.getElementById('sendSilenceToTimelineBtn');
  if (sendSilenceToTimelineBtn) {
    sendSilenceToTimelineBtn.addEventListener('click', () => {
      if (!lastSilenceResult) return;
      setTimelineActiveAudio(lastSilenceResult);
      switchTab('timeline');
      silenceSuccessCard.style.display = 'none';
      if (silenceCleanPlayer) silenceCleanPlayer.pause();
    });
  }

  dismissSilenceSuccessBtn.addEventListener('click', () => {
    silenceSuccessCard.style.display = 'none';
    if (silenceCleanPlayer) silenceCleanPlayer.pause();
  });
}

function updateSilenceThresh(val) {
  threshDisplay.textContent = `${val} dB`;
  threshChips.forEach(chip => {
    const chipVal = parseFloat(chip.getAttribute('data-thresh'));
    if (Math.abs(chipVal - val) < 1.0) {
      chip.classList.add('active');
    } else {
      chip.classList.remove('active');
    }
  });
}

function updateSilenceMinDur(val) {
  minDurDisplay.textContent = `${val.toFixed(2)}s`;
  durChips.forEach(chip => {
    const chipVal = parseFloat(chip.getAttribute('data-dur'));
    if (Math.abs(chipVal - val) < 0.05) {
      chip.classList.add('active');
    } else {
      chip.classList.remove('active');
    }
  });
}

function updateSilenceMargin(val) {
  marginDisplay.textContent = `${Math.round(val)} ms`;
  marginChips.forEach(chip => {
    const chipVal = parseFloat(chip.getAttribute('data-margin'));
    if (Math.abs(chipVal - val) < 5) {
      chip.classList.add('active');
    } else {
      chip.classList.remove('active');
    }
  });
}

function getSilenceSelectedFormat() {
  const checked = document.querySelector('input[name="silenceFormat"]:checked');
  return checked ? checked.value : 'mp3';
}

function updateSilenceOutputPathExtension(ext) {
  let cur = silenceOutputPathInput.value;
  if (cur) {
    const dotIdx = cur.lastIndexOf('.');
    if (dotIdx !== -1) {
      silenceOutputPathInput.value = cur.substring(0, dotIdx + 1) + ext;
    } else {
      silenceOutputPathInput.value = cur + '.' + ext;
    }
  }
}

async function handleSilenceFiles(files) {
  if (!files || files.length === 0) return;

  // If path is directly accessible
  if (files[0].path && window.pywebview && window.pywebview.api) {
    try {
      const metadataList = await window.pywebview.api.inspect_dropped_files([files[0].path]);
      if (metadataList && metadataList.length > 0 && !metadataList[0].error) {
        setSilenceActiveFile(metadataList[0]);
        return;
      }
    } catch (err) {
      console.warn("inspect_dropped_files failed, falling back to upload:", err);
    }
  }

  // Fallback to upload endpoint
  const formData = new FormData();
  formData.append('audio_files', files[0], files[0].name);

  try {
    const res = await fetch('/upload_audio', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.success && data.clips && data.clips.length > 0) {
      setSilenceActiveFile(data.clips[0]);
    } else {
      alert("Error uploading file: " + (data.error || "Unknown"));
    }
  } catch (err) {
    alert("Could not load audio file: " + err.message);
  }
}

function setSilenceActiveFile(clip) {
  silenceActiveFile = clip;

  silenceFileName.textContent = clip.filename;
  silenceFileFmt.textContent = clip.format_name.toUpperCase();
  silenceFileDur.textContent = clip.duration_formatted;
  silenceFileSr.textContent = `${(clip.sample_rate / 1000).toFixed(1)} kHz`;
  silenceFileSize.textContent = clip.size_formatted;

  silenceOriginalPlayer.src = `/stream_audio?path=${encodeURIComponent(clip.path)}&t=${Date.now()}`;

  silenceDropzone.style.display = 'none';
  silenceAudioCard.style.display = 'block';

  const baseName = clip.filename.replace(/\.[^/.]+$/, "");
  const fmt = getSilenceSelectedFormat();
  silenceOutputPathInput.value = `${baseName}_cleaned.${fmt}`;

  analyzeSilencesBtn.disabled = false;
  startSilenceRemovalBtn.disabled = false;

  // Auto trigger analysis for instant feedback
  executeDetectSilences();
}

async function executeDetectSilences() {
  if (!silenceActiveFile || !window.pywebview || !window.pywebview.api) return;

  const thresh = parseFloat(thresholdSlider.value) || -40.0;
  const minDur = parseFloat(minDurationSlider.value) || 0.4;

  silenceBadgeStats.textContent = "Analyzing Audio...";
  analyzeSilencesBtn.disabled = true;

  try {
    const res = await window.pywebview.api.detect_silences(silenceActiveFile.path, thresh, minDur);
    if (res.success) {
      silenceCountStat.textContent = res.silence_count;
      silenceSavedStat.textContent = `${res.total_silence_sec}s (${res.percent_saved}%)`;
      silenceNewDurStat.textContent = res.expected_trimmed_formatted;

      renderDetectedSilencesList(res.silence_segments);
      silenceTelemetryCard.style.display = 'block';
      silenceBadgeStats.textContent = `${res.silence_count} Pauses Detected`;
    } else {
      alert("Silence analysis error: " + (res.error || "Unknown"));
    }
  } catch (err) {
    console.error("detect_silences error:", err);
  } finally {
    analyzeSilencesBtn.disabled = false;
  }
}

function formatSecondsToTime(sec) {
  if (typeof sec !== 'number' || isNaN(sec)) return '00:00';
  const mins = Math.floor(sec / 60);
  const secs = (sec % 60).toFixed(2);
  return `${String(mins).padStart(2, '0')}:${secs.padStart(5, '0')}`;
}

function renderDetectedSilencesList(segments) {
  silenceListContainer.innerHTML = '';
  if (!segments || segments.length === 0) {
    silenceListContainer.innerHTML = `
      <div class="silence-empty-state">
        No silences found exceeding the duration threshold. Your audio is already tight!
      </div>
    `;
    return;
  }

  segments.forEach((seg, idx) => {
    const item = document.createElement('div');
    item.className = 'silence-item';
    const startStr = seg.start_formatted || formatSecondsToTime(seg.start);
    const endStr = seg.end_formatted || formatSecondsToTime(seg.end);
    const durSec = (typeof seg.duration === 'number') ? seg.duration : ((seg.end || 0) - (seg.start || 0));
    const durStr = seg.duration_formatted || `${durSec.toFixed(2)}s`;

    item.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="silence-item-num">#${idx + 1}</span>
        <span class="silence-item-range">${startStr} ➔ ${endStr}</span>
      </div>
      <span class="silence-item-dur">-${durStr}</span>
    `;
    silenceListContainer.appendChild(item);
  });
}

async function executeRemoveSilences() {
  if (!silenceActiveFile || !window.pywebview || !window.pywebview.api) return;

  let outPath = silenceOutputPathInput.value.trim();
  if (!outPath) {
    alert("Please specify an export destination file.");
    return;
  }

  // Ensure absolute path
  if (!outPath.includes(':') && !outPath.startsWith('/') && !outPath.startsWith('\\')) {
    outPath = `A:\\My Video Hwelper APP\\${outPath}`;
    silenceOutputPathInput.value = outPath;
  }

  const thresh = parseFloat(thresholdSlider.value) || -40.0;
  const minDur = parseFloat(minDurationSlider.value) || 0.4;
  const margin = parseFloat(marginSlider.value) || 80.0;
  const normalize = silenceNormalize.checked;
  const fmt = getSilenceSelectedFormat();

  silenceProgressCard.style.display = 'block';
  silenceSuccessCard.style.display = 'none';
  startSilenceRemovalBtn.disabled = true;
  analyzeSilencesBtn.disabled = true;

  silenceProgressBarFill.style.width = '5%';
  silenceProgressPercent.textContent = '5%';
  silenceProgressStatusText.textContent = "Analyzing audio waveform...";

  try {
    await window.pywebview.api.start_remove_silences(
      silenceActiveFile.path,
      outPath,
      thresh,
      minDur,
      margin,
      normalize,
      48000,
      fmt,
      320
    );
  } catch (err) {
    alert("Error starting silence removal: " + err);
    resetSilenceProgress();
  }
}

// Global Silence Callbacks from Python ApiBridge
window.onSilenceProgress = function(percent, statusMsg) {
  silenceProgressBarFill.style.width = `${percent}%`;
  silenceProgressPercent.textContent = `${Math.round(percent)}%`;
  silenceProgressStatusText.textContent = statusMsg;
};

window.onSilenceComplete = function(result) {
  resetSilenceProgress();
  const outputClip = result.output_info || result;
  const filePath = result.path || outputClip.path;
  const durationFormatted = result.trimmed_duration_formatted || result.duration_formatted || outputClip.duration_formatted || "00:00";
  const savedSec = result.silence_removed_sec ?? result.time_saved_sec ?? 0;
  const savedPct = result.percent_saved ?? result.time_saved_percent ?? 0;
  const pauseCount = result.silence_count ?? 0;

  lastSilenceResult = {
    path: filePath,
    filename: result.filename || outputClip.filename || (filePath ? filePath.split(/[\\/]/).pop() : "cleaned_voiceover.mp3"),
    duration: result.trimmed_duration || result.duration || outputClip.duration || 0,
    duration_formatted: durationFormatted,
    format_name: result.format_name || outputClip.format_name || "MP3",
    sample_rate: result.sample_rate || outputClip.sample_rate || 48000,
    size_formatted: result.size_formatted || outputClip.size_formatted || "0 KB"
  };

  silenceSuccessCard.style.display = 'block';
  silenceSuccessDetails.textContent = `Saved ${savedSec}s (${savedPct}%) • ${pauseCount} pauses cut • New Duration: ${durationFormatted}`;

  if (filePath) {
    const streamUrl = `/stream_audio?path=${encodeURIComponent(filePath)}&t=${Date.now()}`;
    silenceCleanPlayer.src = streamUrl;
    silenceCleanPlayer.load();
  }
};

window.onSilenceCancelled = function() {
  resetSilenceProgress();
  alert("Silence removal was cancelled.");
};

window.onSilenceError = function(errMsg) {
  resetSilenceProgress();
  alert("Silence Removal Error:\n" + errMsg);
};

function resetSilenceProgress() {
  silenceProgressCard.style.display = 'none';
  startSilenceRemovalBtn.disabled = false;
  analyzeSilencesBtn.disabled = false;
  silenceProgressBarFill.style.width = '0%';
  silenceProgressPercent.textContent = '0%';
}

// =============================================================================
// 10. TIMELINE ALIGNER CONTROLLER
// =============================================================================
let timelineActiveAudio = null;
let timelineImagesList = [];
let alignedTimelineItems = [];
let lastTimelineRenderResult = null;

// DOM Elements
let timelineAudioDropzone, timelineAudioInput, timelineActiveAudioBar;
let timelineAudioName, timelineAudioMeta, timelineAudioPlayer, changeTimelineAudioBtn;
let statTimelineImgCount, statTimelineAudioDur, statTimelineCoverage;
let timelineImagesDropzone, timelineImageInput, timelineSequenceContainer;
let addMoreImagesBtn, realignTimelineBtn, exportCueSheetBtn, clearImagesBtn, timelineCardsGrid;
let timelineNvencToggle, timelineOutputPathInput, browseTimelineDestBtn, startRenderVideoBtn;
let timelineProgressCard, timelineProgressStatusText, timelineProgressPercent, timelineProgressBarFill, cancelTimelineRenderBtn;
let timelineSuccessCard, timelineSuccessDetails, timelineVideoPlayer, openTimelineVideoFolderBtn, dismissTimelineSuccessBtn;

function initTimelineAligner() {
  timelineAudioDropzone = document.getElementById('timelineAudioDropzone');
  timelineAudioInput = document.getElementById('timelineAudioInput');
  timelineActiveAudioBar = document.getElementById('timelineActiveAudioBar');
  timelineAudioName = document.getElementById('timelineAudioName');
  timelineAudioMeta = document.getElementById('timelineAudioMeta');
  timelineAudioPlayer = document.getElementById('timelineAudioPlayer');
  changeTimelineAudioBtn = document.getElementById('changeTimelineAudioBtn');

  statTimelineImgCount = document.getElementById('statTimelineImgCount');
  statTimelineAudioDur = document.getElementById('statTimelineAudioDur');
  statTimelineCoverage = document.getElementById('statTimelineCoverage');

  timelineImagesDropzone = document.getElementById('timelineImagesDropzone');
  timelineImageInput = document.getElementById('timelineImageInput');
  timelineSequenceContainer = document.getElementById('timelineSequenceContainer');

  addMoreImagesBtn = document.getElementById('addMoreImagesBtn');
  realignTimelineBtn = document.getElementById('realignTimelineBtn');
  exportCueSheetBtn = document.getElementById('exportCueSheetBtn');
  clearImagesBtn = document.getElementById('clearImagesBtn');
  timelineCardsGrid = document.getElementById('timelineCardsGrid');

  timelineNvencToggle = document.getElementById('timelineNvencToggle');
  timelineOutputPathInput = document.getElementById('timelineOutputPathInput');
  browseTimelineDestBtn = document.getElementById('browseTimelineDestBtn');
  startRenderVideoBtn = document.getElementById('startRenderVideoBtn');

  timelineProgressCard = document.getElementById('timelineProgressCard');
  timelineProgressStatusText = document.getElementById('timelineProgressStatusText');
  timelineProgressPercent = document.getElementById('timelineProgressPercent');
  timelineProgressBarFill = document.getElementById('timelineProgressBarFill');
  cancelTimelineRenderBtn = document.getElementById('cancelTimelineRenderBtn');

  timelineSuccessCard = document.getElementById('timelineSuccessCard');
  timelineSuccessDetails = document.getElementById('timelineSuccessDetails');
  timelineVideoPlayer = document.getElementById('timelineVideoPlayer');
  openTimelineVideoFolderBtn = document.getElementById('openTimelineVideoFolderBtn');
  dismissTimelineSuccessBtn = document.getElementById('dismissTimelineSuccessBtn');

  setupTimelineEventListeners();
}

function setupTimelineEventListeners() {
  if (!timelineAudioDropzone) return;

  // Audio slot triggers
  timelineAudioDropzone.addEventListener('click', () => timelineAudioInput.click());
  changeTimelineAudioBtn.addEventListener('click', () => timelineAudioInput.click());

  timelineAudioInput.addEventListener('change', async (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      await handleTimelineAudioUpload(files[0]);
      timelineAudioInput.value = '';
    }
  });

  // Audio drag & drop
  ['dragenter', 'dragover'].forEach(name => {
    timelineAudioDropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      timelineAudioDropzone.classList.add('drag-over');
    });
  });
  ['dragleave', 'drop'].forEach(name => {
    timelineAudioDropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      timelineAudioDropzone.classList.remove('drag-over');
    });
  });
  timelineAudioDropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      await handleTimelineAudioUpload(files[0]);
    }
  });

  // Images input & dropzone triggers
  timelineImagesDropzone.addEventListener('click', () => timelineImageInput.click());
  addMoreImagesBtn.addEventListener('click', () => timelineImageInput.click());

  timelineImageInput.addEventListener('change', async (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      await handleTimelineImagesUpload(files);
      timelineImageInput.value = '';
    }
  });

  // Images drag & drop on dropzone & workspace
  [timelineImagesDropzone, timelineSequenceContainer].forEach(target => {
    if (!target) return;
    ['dragenter', 'dragover'].forEach(name => {
      target.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        target.classList.add('drag-over');
      });
    });
    ['dragleave', 'drop'].forEach(name => {
      target.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        target.classList.remove('drag-over');
      });
    });
    target.addEventListener('drop', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        await handleTimelineImagesUpload(files);
      }
    });
  });

  // FPS chips
  document.querySelectorAll('#timelineView .chip[data-fps]').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('#timelineView .chip[data-fps]').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      document.getElementById('fpsDisplay').textContent = `${chip.getAttribute('data-fps')} FPS`;
    });
  });

  // Resolution radio cards
  document.querySelectorAll('input[name="videoRes"]').forEach(radio => {
    radio.addEventListener('change', () => {
      document.querySelectorAll('#timelineView .radio-card').forEach(c => c.classList.remove('active'));
      radio.closest('.radio-card').classList.add('active');
    });
  });

  // Re-align button
  realignTimelineBtn.addEventListener('click', () => {
    recalculateTimelineAlignment();
  });

  // Clear images
  clearImagesBtn.addEventListener('click', () => {
    if (timelineImagesList.length === 0) return;
    if (confirm("Remove all images from timeline?")) {
      timelineImagesList = [];
      alignedTimelineItems = [];
      renderTimelineCards();
    }
  });

  // Export CSV Cue Sheet
  exportCueSheetBtn.addEventListener('click', async () => {
    if (alignedTimelineItems.length === 0) {
      alert("No images to export in cue sheet.");
      return;
    }
    const defaultCsv = "timeline_cue_sheet.csv";
    try {
      const saveDest = await window.pywebview.api.select_save_destination(defaultCsv);
      if (saveDest) {
        await window.pywebview.api.export_timeline_csv(alignedTimelineItems, saveDest);
        alert(`Cue sheet exported to:\n${saveDest}`);
      }
    } catch (err) {
      alert("Error exporting CSV: " + err);
    }
  });

  // Browse output destination
  browseTimelineDestBtn.addEventListener('click', async () => {
    if (!window.pywebview || !window.pywebview.api) return;
    const currentName = timelineOutputPathInput.value.split(/[\\/]/).pop() || "aligned_video.mp4";
    try {
      const selected = await window.pywebview.api.select_save_destination(currentName);
      if (selected) {
        timelineOutputPathInput.value = selected;
      }
    } catch (err) {
      alert("Could not select destination: " + err);
    }
  });

  // Start Render Video button
  startRenderVideoBtn.addEventListener('click', executeTimelineRender);

  // Cancel Render button
  cancelTimelineRenderBtn.addEventListener('click', async () => {
    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.cancel_timeline_video();
    }
  });

  // Success Card actions
  openTimelineVideoFolderBtn.addEventListener('click', async () => {
    if (lastTimelineRenderResult && window.pywebview && window.pywebview.api) {
      await window.pywebview.api.open_folder(lastTimelineRenderResult.path);
    }
  });

  dismissTimelineSuccessBtn.addEventListener('click', () => {
    timelineSuccessCard.style.display = 'none';
    if (timelineVideoPlayer) {
      timelineVideoPlayer.pause();
    }
  });
}

async function handleTimelineAudioUpload(file) {
  if (file.path && window.pywebview && window.pywebview.api) {
    try {
      const metadataList = await window.pywebview.api.inspect_dropped_files([file.path]);
      if (metadataList && metadataList.length > 0 && !metadataList[0].error) {
        setTimelineActiveAudio(metadataList[0]);
        return;
      }
    } catch (err) {
      console.warn("inspect_dropped_files failed for audio:", err);
    }
  }

  const formData = new FormData();
  formData.append('audio_files', file, file.name);

  try {
    const res = await fetch('/upload_audio', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.success && data.clips && data.clips.length > 0) {
      setTimelineActiveAudio(data.clips[0]);
    } else {
      alert("Error uploading audio: " + (data.error || "Unknown"));
    }
  } catch (err) {
    alert("Audio upload failed: " + err.message);
  }
}

function setTimelineActiveAudio(audioMeta) {
  timelineActiveAudio = audioMeta;

  timelineAudioName.textContent = audioMeta.filename;
  timelineAudioMeta.textContent = `${audioMeta.duration_formatted} • ${audioMeta.format_name}`;
  timelineAudioPlayer.src = `/stream_audio?path=${encodeURIComponent(audioMeta.path)}&t=${Date.now()}`;

  timelineAudioDropzone.style.display = 'none';
  timelineActiveAudioBar.style.display = 'flex';
  changeTimelineAudioBtn.style.display = 'inline-block';

  statTimelineAudioDur.textContent = audioMeta.duration_formatted;

  suggestTimelineVideoOutputPath();
  recalculateTimelineAlignment();
}

async function handleTimelineImagesUpload(files) {
  const directPaths = [];
  for (let i = 0; i < files.length; i++) {
    if (files[i].path) directPaths.push(files[i].path);
  }

  if (directPaths.length > 0 && window.pywebview && window.pywebview.api) {
    try {
      const inspected = await window.pywebview.api.inspect_dropped_images(directPaths);
      if (inspected && inspected.length > 0) {
        appendTimelineImages(inspected);
        return;
      }
    } catch (err) {
      console.warn("inspect_dropped_images failed:", err);
    }
  }

  // Upload images to local server
  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append('image_files', files[i], files[i].name);
  }

  try {
    const res = await fetch('/upload_images', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.success && data.images && data.images.length > 0) {
      appendTimelineImages(data.images);
    } else {
      alert("Error importing images: " + (data.error || "Unknown"));
    }
  } catch (err) {
    alert("Failed to upload images: " + err.message);
  }
}

function appendTimelineImages(newImages) {
  newImages.forEach(img => {
    // Avoid exact duplicate file paths
    if (!timelineImagesList.some(existing => existing.path === img.path)) {
      timelineImagesList.push(img);
    }
  });
  recalculateTimelineAlignment();
}

async function recalculateTimelineAlignment() {
  if (timelineImagesList.length === 0) {
    alignedTimelineItems = [];
    renderTimelineCards();
    return;
  }

  const audioPath = timelineActiveAudio ? timelineActiveAudio.path : "";
  const imagePaths = timelineImagesList.map(img => img.path);

  if (audioPath && window.pywebview && window.pywebview.api) {
    try {
      const res = await window.pywebview.api.align_timeline(imagePaths, audioPath);
      if (res.success) {
        alignedTimelineItems = res.aligned_images;
      } else {
        console.error("align_timeline error:", res.error);
        fallbackClientAlignment();
      }
    } catch (err) {
      console.warn("API align_timeline failed:", err);
      fallbackClientAlignment();
    }
  } else {
    fallbackClientAlignment();
  }

  renderTimelineCards();
}

function fallbackClientAlignment() {
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
  const sorted = [...timelineImagesList].sort((a, b) => collator.compare(a.filename, b.filename));
  const audioDur = timelineActiveAudio ? timelineActiveAudio.duration : 60.0;
  const count = sorted.length;

  alignedTimelineItems = sorted.map((img, idx) => {
    const start = (idx / Math.max(1, count)) * audioDur;
    const end = ((idx + 1) / Math.max(1, count)) * audioDur;
    const dur = end - start;
    return {
      index: idx,
      path: img.path,
      filename: img.filename,
      start_sec: start,
      end_sec: end,
      duration: dur,
      start_formatted: formatSecondsToTime(start),
      end_formatted: formatSecondsToTime(end),
      duration_formatted: `${dur.toFixed(2)}s`
    };
  });
}

function renderTimelineCards() {
  if (alignedTimelineItems.length === 0) {
    timelineImagesDropzone.style.display = 'block';
    timelineSequenceContainer.style.display = 'none';
    timelineCardsGrid.innerHTML = '';
    statTimelineImgCount.textContent = '0';
    statTimelineCoverage.textContent = '0%';
    startRenderVideoBtn.disabled = true;
    return;
  }

  timelineImagesDropzone.style.display = 'none';
  timelineSequenceContainer.style.display = 'block';
  timelineCardsGrid.innerHTML = '';

  alignedTimelineItems.forEach((item, idx) => {
    const card = document.createElement('div');
    card.className = 'timeline-card';
    card.innerHTML = `
      <div class="timeline-card-thumb-box">
        <img class="timeline-card-thumb" src="/stream_image?path=${encodeURIComponent(item.path)}" alt="${item.filename}" loading="lazy">
        <span class="timeline-card-seq-badge">#${idx + 1}</span>
        <button class="timeline-card-del-btn" title="Remove image" data-index="${idx}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="timeline-card-body">
        <div class="timeline-card-title" title="${item.filename}">${item.filename}</div>
        <div class="timeline-card-timing">
          <span class="timeline-pill-time">${item.start_formatted} ➔ ${item.end_formatted}</span>
          <span class="timeline-pill-dur">${item.duration_formatted}</span>
        </div>
      </div>
    `;

    card.querySelector('.timeline-card-del-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      timelineImagesList.splice(idx, 1);
      recalculateTimelineAlignment();
    });

    timelineCardsGrid.appendChild(card);
  });

  statTimelineImgCount.textContent = alignedTimelineItems.length;
  statTimelineCoverage.textContent = timelineActiveAudio ? '100%' : 'No Audio';

  startRenderVideoBtn.disabled = !(timelineActiveAudio && alignedTimelineItems.length > 0);
  suggestTimelineVideoOutputPath();
}

function suggestTimelineVideoOutputPath() {
  if (!timelineOutputPathInput.value) {
    const ts = new Date().toISOString().slice(0, 10);
    timelineOutputPathInput.value = `aligned_video_${ts}.mp4`;
  }
}

async function executeTimelineRender() {
  if (!timelineActiveAudio || alignedTimelineItems.length === 0) {
    alert("Please ensure both voiceover audio and images are added to the timeline.");
    return;
  }

  let outPath = timelineOutputPathInput.value.trim();
  if (!outPath) {
    alert("Please specify a video export destination.");
    return;
  }

  if (!outPath.includes(':') && !outPath.startsWith('/') && !outPath.startsWith('\\')) {
    outPath = `A:\\My Video Hwelper APP\\${outPath}`;
    timelineOutputPathInput.value = outPath;
  }

  const resRadio = document.querySelector('input[name="videoRes"]:checked');
  const resVal = resRadio ? resRadio.value : '1080p';
  let width = 1920;
  let height = 1080;
  if (resVal === '4k') {
    width = 3840;
    height = 2160;
  } else if (resVal === '720p') {
    width = 1280;
    height = 720;
  }

  const activeFpsChip = document.querySelector('#timelineView .chip[data-fps].active');
  const fps = activeFpsChip ? parseInt(activeFpsChip.getAttribute('data-fps'), 10) : 30;
  const useNvenc = timelineNvencToggle.checked;

  timelineProgressCard.style.display = 'block';
  timelineSuccessCard.style.display = 'none';
  startRenderVideoBtn.disabled = true;

  timelineProgressBarFill.style.width = '5%';
  timelineProgressPercent.textContent = '5%';
  timelineProgressStatusText.textContent = "Initializing video rendering pipeline...";

  try {
    await window.pywebview.api.start_render_timeline_video(
      alignedTimelineItems,
      timelineActiveAudio.path,
      outPath,
      width,
      height,
      fps,
      useNvenc
    );
  } catch (err) {
    alert("Error rendering video: " + err);
    resetTimelineRenderProgress();
  }
}

// Global Timeline Video Callbacks from Python ApiBridge
window.onTimelineVideoProgress = function(percent, statusMsg) {
  timelineProgressBarFill.style.width = `${percent}%`;
  timelineProgressPercent.textContent = `${Math.round(percent)}%`;
  timelineProgressStatusText.textContent = statusMsg;
};

window.onTimelineVideoComplete = function(result) {
  resetTimelineRenderProgress();
  lastTimelineRenderResult = result;

  timelineSuccessCard.style.display = 'block';
  timelineSuccessDetails.textContent = `${result.duration_formatted} • ${result.size_formatted} • ${result.resolution} @ ${result.fps}fps • ${result.image_count} images`;

  const videoStreamUrl = `/stream_video?path=${encodeURIComponent(result.path)}&t=${Date.now()}`;
  timelineVideoPlayer.src = videoStreamUrl;
  timelineVideoPlayer.load();
};

window.onTimelineVideoCancelled = function() {
  resetTimelineRenderProgress();
  alert("Timeline video render was cancelled.");
};

window.onTimelineVideoError = function(errMsg) {
  resetTimelineRenderProgress();
  alert("Timeline Video Render Error:\n" + errMsg);
};

function resetTimelineRenderProgress() {
  timelineProgressCard.style.display = 'none';
  startRenderVideoBtn.disabled = !(timelineActiveAudio && alignedTimelineItems.length > 0);
  timelineProgressBarFill.style.width = '0%';
  timelineProgressPercent.textContent = '0%';
}
