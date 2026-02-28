const chatLog = document.getElementById('chatLog');
const sendBtn = document.getElementById('sendBtn');
const textInput = document.getElementById('textInput');
const voiceBtn = document.getElementById('voiceBtn');
const providerSelect = document.getElementById('providerSelect');
const modelInput = document.getElementById('modelInput');
const resetBtn = document.getElementById('resetBtn');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');

let recognition = null;
let voiceEnabled = false;
let wakeArmed = false;
let defaults = { gemini: 'gemini-2.5-flash', ollama: 'llama3.1' };
const wakeWord = 'hey jarvis';

function setStatus(text, state = 'idle') {
  statusText.textContent = text;
  statusDot.className = `dot ${state}`;
}

function addMessage(role, text) {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  wrap.appendChild(bubble);
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function fetchConfig() {
  try {
    const res = await fetch('/api/config');
    const data = await res.json();
    defaults = data.defaults || defaults;
    providerSelect.innerHTML = '';
    (data.providers || ['gemini', 'ollama']).forEach((p) => {
      const option = document.createElement('option');
      option.value = p;
      option.textContent = p === 'gemini' ? 'API (Gemini)' : 'Local (Ollama)';
      providerSelect.appendChild(option);
    });
    providerSelect.value = data.provider || 'gemini';
    modelInput.value = data.model || defaults[providerSelect.value];
  } catch (err) {
    setStatus('Failed to load config', 'error');
  }
}

async function sendMessage(text, source = 'typed') {
  const message = text.trim();
  if (!message) return;

  addMessage('user', message);
  textInput.value = '';

  const payload = {
    message,
    provider: providerSelect.value,
    model: modelInput.value.trim() || undefined,
    source,
  };

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.ok) {
      addMessage('bot', `Error: ${data.error || 'Request failed'}`);
      return;
    }
    addMessage('bot', data.response || '');
  } catch (err) {
    addMessage('bot', 'Error: Could not reach server.');
  }
}

function initRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    setStatus('Speech recognition not supported', 'error');
    return null;
  }

  const rec = new SpeechRecognition();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = 'en-US';

  rec.onresult = (event) => {
    let finalTranscript = '';
    let interimTranscript = '';

    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      const transcript = result[0].transcript;
      if (result.isFinal) {
        finalTranscript += transcript;
      } else {
        interimTranscript += transcript;
      }
    }

    if (interimTranscript) {
      setStatus(`Listening: ${interimTranscript}`, 'listening');
    }

    if (finalTranscript) {
      handleFinalTranscript(finalTranscript.trim());
    }
  };

  rec.onerror = (event) => {
    setStatus(`Voice error: ${event.error}`, 'error');
  };

  rec.onend = () => {
    if (voiceEnabled) {
      rec.start();
    }
  };

  return rec;
}

function handleFinalTranscript(text) {
  const lower = text.toLowerCase();
  if (lower.includes(wakeWord)) {
    const idx = lower.indexOf(wakeWord);
    const after = text.slice(idx + wakeWord.length).trim();
    if (after) {
      wakeArmed = false;
      setStatus('Command captured', 'listening');
      sendMessage(after, 'voice');
    } else {
      wakeArmed = true;
      setStatus('Wake word detected. Listening for command...', 'wake');
    }
    return;
  }

  if (wakeArmed) {
    wakeArmed = false;
    setStatus('Command captured', 'listening');
    sendMessage(text, 'voice');
  }
}

voiceBtn.addEventListener('click', () => {
  if (!recognition) {
    recognition = initRecognition();
    if (!recognition) return;
  }

  if (voiceEnabled) {
    voiceEnabled = false;
    wakeArmed = false;
    recognition.stop();
    voiceBtn.classList.remove('listening');
    setStatus('Voice idle', 'idle');
  } else {
    voiceEnabled = true;
    recognition.start();
    voiceBtn.classList.add('listening');
    setStatus('Listening for "hey jarvis"...', 'listening');
  }
});

sendBtn.addEventListener('click', () => {
  sendMessage(textInput.value);
});

textInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    sendMessage(textInput.value);
  }
});

providerSelect.addEventListener('change', () => {
  const provider = providerSelect.value;
  if (!modelInput.value || modelInput.value === defaults.gemini || modelInput.value === defaults.ollama) {
    modelInput.value = defaults[provider] || '';
  }
});

resetBtn.addEventListener('click', async () => {
  await fetch('/api/reset', { method: 'POST' });
  chatLog.innerHTML = '';
});

fetchConfig();
setStatus('Voice idle', 'idle');
