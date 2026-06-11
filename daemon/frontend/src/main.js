import { AskNeo, HideWindow, Quit, ToggleAutoStart, GetAutoStartStatus, SetHotkey, GetCurrentHotkey, GetWhatsAppStatus, GetGeminiAPIKey, SetGeminiAPIKey } from '../wailsjs/go/main/App.js';
import { EventsOn } from '../wailsjs/runtime/runtime.js';

const inputElement = document.getElementById('prompt-input');
const chatHistory = document.getElementById('chat-history');

EventsOn("focus-input", () => {
    inputElement.focus();
});

EventsOn("show-chat", () => {
    const settingsOverlay = document.getElementById('settings-overlay');
    if (settingsOverlay) {
        settingsOverlay.classList.add('hidden');
    }
    inputElement.focus();
});

async function loadAndShowSettings() {
    const settingsOverlay = document.getElementById('settings-overlay');
    if (settingsOverlay) {
        settingsOverlay.classList.remove('hidden');
    }
    try {
        const status = await GetAutoStartStatus();
        document.getElementById('autostart-toggle').checked = status;
    } catch (e) {}
    try {
        const hotkey = await GetCurrentHotkey();
        document.getElementById('record-hotkey').innerText = hotkey;
    } catch (e) {}
    try {
        const geminiKey = await GetGeminiAPIKey();
        document.getElementById('gemini-key-input').value = geminiKey;
    } catch (e) {}
}

EventsOn("open-settings", loadAndShowSettings);

inputElement.addEventListener('keydown', async (e) => {
    if (e.key === 'Escape') {
        HideWindow();
        return;
    }

    if (e.key === 'Enter' && inputElement.value.trim() !== '') {
        const text = inputElement.value.trim();
        inputElement.value = '';
        
        appendMessage('user', text);
        const loadingId = appendMessage('neo', 'Pensando...');

        try {
            const response = await AskNeo(text);
            updateMessage(loadingId, response);
        } catch (err) {
            updateMessage(loadingId, `Erro: ${err}`);
        }
    }
});

let msgCount = 0;
function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.id = `msg-${msgCount++}`;
    div.innerText = text;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return div.id;
}

function updateMessage(id, newText) {
    const el = document.getElementById(id);
    if (el) {
        el.innerText = newText;
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
}

// Initial focus
setTimeout(() => { inputElement.focus(); }, 100);

// --- Settings Logic ---
const settingsBtn = document.getElementById('settings-btn');
const closeWindowBtn = document.getElementById('close-window-btn');
const closeSettingsBtn = document.getElementById('close-settings');
const settingsOverlay = document.getElementById('settings-overlay');
const autostartToggle = document.getElementById('autostart-toggle');
const recordBtn = document.getElementById('record-hotkey');
const settingMsg = document.getElementById('setting-msg');
const quitBtn = document.getElementById('quit-neo-btn');

closeWindowBtn.addEventListener('click', () => {
    HideWindow();
});

let isRecording = false;

quitBtn.addEventListener('click', () => {
    Quit();
});

settingsBtn.addEventListener('click', loadAndShowSettings);

closeSettingsBtn.addEventListener('click', () => {
    settingsOverlay.classList.add('hidden');
    inputElement.focus();
});

autostartToggle.addEventListener('change', async (e) => {
    const res = await ToggleAutoStart(e.target.checked);
    settingMsg.innerText = "Autostart: " + res;
    setTimeout(() => { settingMsg.innerText = ''; }, 3000);
});

document.getElementById('gemini-key-input').addEventListener('change', async (e) => {
    const key = e.target.value.trim();
    const success = await SetGeminiAPIKey(key);
    if (success) {
        settingMsg.innerText = "API Key salva!";
        settingMsg.style.color = "#4ade80";
    } else {
        settingMsg.innerText = "Erro ao salvar API Key!";
        settingMsg.style.color = "#ef4444";
    }
    setTimeout(() => { settingMsg.innerText = ''; }, 3000);
});

recordBtn.addEventListener('click', () => {
    isRecording = true;
    recordBtn.innerText = "Pressione as teclas...";
    recordBtn.classList.add('recording');
});

window.addEventListener('keydown', async (e) => {
    if (isRecording) {
        e.preventDefault();
        
        let mod = '';
        if (e.ctrlKey) mod = 'Ctrl';
        if (e.altKey) mod = 'Mod1';
        if (e.metaKey) mod = 'Mod4';
        if (e.shiftKey) mod = 'Shift';

        const key = e.key;
        
        if (key === 'Control' || key === 'Alt' || key === 'Meta' || key === 'Shift') {
            return;
        }
        
        if (mod && key) {
            isRecording = false;
            recordBtn.classList.remove('recording');
            
            const displayKey = key === ' ' ? 'Space' : key.toUpperCase();
            recordBtn.innerText = `Salvando ${mod}+${displayKey}...`;
            
            const success = await SetHotkey(mod, displayKey);
            if (success) {
                settingMsg.innerText = "Atalho salvo!";
                settingMsg.style.color = "#4ade80";
                recordBtn.innerText = `${mod} + ${displayKey}`;
            } else {
                settingMsg.innerText = "Atalho indisponível!";
                settingMsg.style.color = "#ef4444";
                recordBtn.innerText = "Gravar Atalho";
            }
            setTimeout(() => { settingMsg.innerText = ''; }, 3000);
        }
    }
});

// --- WhatsApp Setup Logic ---
const connectWhatsappBtn = document.getElementById('connect-whatsapp-btn');
const whatsappOverlay = document.getElementById('whatsapp-overlay');
const closeWhatsappOverlay = document.getElementById('close-whatsapp-overlay');
const qrImage = document.getElementById('qr-image');
const qrLoading = document.getElementById('qr-loading');
const whatsappStatusText = document.getElementById('whatsapp-status-text');
const qrContainer = document.getElementById('qr-container');

let whatsappTimeout = null;

connectWhatsappBtn.addEventListener('click', () => {
    whatsappOverlay.classList.remove('hidden');
    if (whatsappTimeout) clearTimeout(whatsappTimeout);
    checkWhatsAppStatus();
});

closeWhatsappOverlay.addEventListener('click', () => {
    whatsappOverlay.classList.add('hidden');
    if (whatsappTimeout) clearTimeout(whatsappTimeout);
});

async function checkWhatsAppStatus() {
    try {
        const res = await GetWhatsAppStatus();
        if (res.connected) {
            whatsappStatusText.innerText = "✅ WhatsApp Conectado!";
            whatsappStatusText.style.color = "#4ade80";
            qrContainer.style.display = "none";
            return; // Stop checking
        } else if (res.qr) {
            qrContainer.style.display = "flex";
            qrLoading.style.display = "none";
            qrImage.style.display = "block";
            qrImage.src = `https://quickchart.io/qr?size=256&text=${encodeURIComponent(res.qr)}`;
            whatsappStatusText.innerText = "Escaneie o QR Code acima...";
            whatsappStatusText.style.color = "#fbbc04";
        } else {
            qrContainer.style.display = "flex";
            qrLoading.style.display = "block";
            qrImage.style.display = "none";
            whatsappStatusText.innerText = "Aguardando geração do QR Code...";
            whatsappStatusText.style.color = "#fbbc04";
        }
    } catch (err) {
        console.error("Erro ao verificar WhatsApp", err);
        whatsappStatusText.innerText = "Erro: " + err;
        whatsappStatusText.style.color = "#ef4444";
    }
    
    // Only schedule next check if overlay is still visible
    if (!whatsappOverlay.classList.contains('hidden')) {
        whatsappTimeout = setTimeout(checkWhatsAppStatus, 3000);
    }
}

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        HideWindow();
    }
});
